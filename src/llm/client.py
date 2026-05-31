"""
llm/client.py
Cliente LLM com suporte a múltiplos provedores (Anthropic, Ollama) e cache semântico.

Provedores suportados:
  - "anthropic": API Anthropic (Claude). Requer ANTHROPIC_API_KEY.
  - "ollama":    LLM local via Ollama. Requer Ollama rodando (host ou Docker).

Configuração via variáveis de ambiente:
  LLM_PROVIDER          = "ollama" | "anthropic"   (default: "ollama")
  LLM_MODEL             = nome do modelo (default depende do provider)
  OLLAMA_BASE_URL       = URL do Ollama (default: "http://localhost:11434")
  ANTHROPIC_API_KEY     = chave da API (obrigatória se provider="anthropic")
  ENABLE_CACHE          = "true" | "false"        (default: "true")
  CACHE_SIMILARITY_THRESHOLD = float [0,1]        (default: 0.92)
"""

from __future__ import annotations
import json
import os
from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger

from agents.agent import Decision


# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

DECISION_PROMPT = """\
{agent_description}

Você recebeu a seguinte mensagem em uma rede social:
\"\"\"{message}\"\"\"

{history_block}

ATENÇÃO: Se a mensagem começar com "[REFUTAÇÃO]", ela é uma CORREÇÃO de uma fake news
que estava circulando. Considere isso ao decidir: se você é cético ou fact-checker,
provavelmente vai REPASSAR a refutação para conter a desinformação. Se você é
amplificador, pode IGNORAR ou QUESTIONAR a refutação por dissonância cognitiva.

Com base no seu perfil, escolha UMA das ações abaixo e responda APENAS com JSON válido:

{{
  "decision": "<IGNORAR | COMPARTILHAR | COMPARTILHAR_COM_COMENTARIO | QUESTIONAR | REFUTAR>",
  "content": "<texto que você enviaria, ou vazio se IGNORAR/QUESTIONAR>"
}}

Regras:
- IGNORAR: você não acredita ou não tem interesse.
- COMPARTILHAR: você acredita e repassa sem alterar.
- COMPARTILHAR_COM_COMENTARIO: você acredita e adiciona seu comentário.
- QUESTIONAR: você duvida e pede fonte (não repassa).
- REFUTAR: você sabe que é falso e escreve uma correção.

Responda SOMENTE com o JSON, sem texto adicional.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Provider interface
# ─────────────────────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Interface comum para todos os provedores de LLM."""

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 300) -> str:
        """Executa a chamada ao LLM e retorna o texto bruto."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        ...


class AnthropicProvider(LLMProvider):
    """Provedor Anthropic (Claude via API)."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY não definida. Configure no .env ou troque "
                "LLM_PROVIDER para 'ollama'."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, max_tokens: int = 300) -> str:
        response = self.client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model


class OllamaProvider(LLMProvider):
    """
    Provedor Ollama (LLM local).
    Usa a API OpenAI-compatível exposta pelo Ollama em /v1/chat/completions.
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ):
        from openai import OpenAI
        self.client = OpenAI(
            base_url=f"{base_url.rstrip('/')}/v1",
            api_key="ollama",  # Ollama ignora, mas o SDK exige algum valor
            timeout=timeout,
        )
        self._model = model
        self.base_url = base_url

    def complete(self, prompt: str, max_tokens: int = 300) -> str:
        response = self.client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            # Pede resposta determinística para reprodutibilidade
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def make_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    """
    Cria o provider com base em variáveis de ambiente ou argumentos explícitos.
    Argumentos têm prioridade sobre env vars.
    """
    provider = (provider or os.environ.get("LLM_PROVIDER", "ollama")).lower()

    if provider == "anthropic":
        model = model or os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")
        logger.info(f"LLM provider: Anthropic | model: {model}")
        return AnthropicProvider(model=model)

    elif provider == "ollama":
        model = model or os.environ.get("LLM_MODEL", "llama3.1:8b")
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        logger.info(f"LLM provider: Ollama | model: {model} | url: {base_url}")
        return OllamaProvider(model=model, base_url=base_url)

    raise ValueError(
        f"LLM_PROVIDER desconhecido: '{provider}'. Use 'ollama' ou 'anthropic'."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cliente principal com cache semântico
# ─────────────────────────────────────────────────────────────────────────────

class LLMClient:
    """
    Wrapper que orquestra:
      - chamada ao provider (Anthropic ou Ollama)
      - cache semântico via embeddings multilíngues
      - parsing robusto da resposta JSON
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        enable_cache: Optional[bool] = None,
        similarity_threshold: Optional[float] = None,
    ):
        self.provider = make_provider(provider=provider, model=model)

        # Cache config (env var tem prioridade se argumento não for passado)
        if enable_cache is None:
            enable_cache = os.environ.get("ENABLE_CACHE", "true").lower() == "true"
        if similarity_threshold is None:
            similarity_threshold = float(
                os.environ.get("CACHE_SIMILARITY_THRESHOLD", "0.92")
            )

        self.enable_cache = enable_cache
        self.similarity_threshold = similarity_threshold
        self._cache: list[dict] = []
        self._embedder = None
        self._call_count = 0
        self._cache_hits = 0
        self._parse_errors = 0

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            logger.debug("Carregando embedder (sentence-transformers)...")
            self._embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return self._embedder

    def _find_in_cache(self, prompt: str) -> Optional[dict]:
        if not self.enable_cache or not self._cache:
            return None
        import numpy as np
        embedder = self._get_embedder()
        query_emb = embedder.encode(prompt)
        for entry in self._cache:
            cos_sim = np.dot(query_emb, entry["embedding"]) / (
                np.linalg.norm(query_emb) * np.linalg.norm(entry["embedding"]) + 1e-9
            )
            if cos_sim >= self.similarity_threshold:
                return entry["response"]
        return None

    def _add_to_cache(self, prompt: str, response: dict) -> None:
        if not self.enable_cache:
            return
        embedder = self._get_embedder()
        embedding = embedder.encode(prompt)
        self._cache.append({"embedding": embedding, "response": response})

    def _extract_json(self, raw: str) -> dict:
        """
        Extrai JSON da resposta, tolerando texto antes/depois.
        Modelos locais às vezes adicionam preâmbulo apesar da instrução.
        """
        # Tenta parsing direto primeiro
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Procura o primeiro { e o último } e tenta o miolo
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            candidate = raw[start : end + 1]
            return json.loads(candidate)

        raise json.JSONDecodeError("Nenhum JSON encontrado", raw, 0)

    def decide(
        self,
        agent_description: str,
        message_content: str,
        history: list[dict],
    ) -> tuple[Decision, str]:
        """
        Pede ao LLM uma decisão sobre a mensagem.

        Returns:
            (Decision, conteúdo a enviar)
        """
        history_block = ""
        if history:
            history_lines = "\n".join(
                f"- Você {h['decision']}: \"{h['received'][:80]}...\""
                for h in history[-3:]
            )
            history_block = f"Suas últimas interações:\n{history_lines}\n"

        prompt = DECISION_PROMPT.format(
            agent_description=agent_description,
            message=message_content,
            history_block=history_block,
        )

        # Cache primeiro
        cached = self._find_in_cache(prompt)
        if cached:
            self._cache_hits += 1
            return Decision(cached["decision"]), cached.get("content", "")

        # Chama o provider
        self._call_count += 1
        try:
            raw = self.provider.complete(prompt=prompt, max_tokens=300)
            parsed = self._extract_json(raw)
            decision = Decision(parsed.get("decision", Decision.IGNORE.value))
            content = parsed.get("content", "")
            self._add_to_cache(prompt, {"decision": decision.value, "content": content})
            return decision, content

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self._parse_errors += 1
            logger.warning(
                f"Erro ao parsear resposta LLM ({self._parse_errors} total): {e}. "
                f"Usando IGNORAR."
            )
            return Decision.IGNORE, ""

        except Exception as e:
            self._parse_errors += 1
            logger.error(f"Erro inesperado na chamada LLM: {type(e).__name__}: {e}")
            return Decision.IGNORE, ""

    @property
    def stats(self) -> dict:
        total = self._call_count + self._cache_hits
        hit_rate = self._cache_hits / total if total > 0 else 0
        return {
            "provider": self.provider.name,
            "model": self.provider.model,
            "api_calls": self._call_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": f"{hit_rate:.1%}",
            "parse_errors": self._parse_errors,
        }
