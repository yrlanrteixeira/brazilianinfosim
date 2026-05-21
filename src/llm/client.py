"""
llm/client.py
Cliente LLM com cache semântico para reduzir custo de API.
"""

from __future__ import annotations
import json
import os
from typing import Optional
from loguru import logger

from ..agents.agent import Decision


DECISION_PROMPT = """\
{agent_description}

Você recebeu a seguinte mensagem em uma rede social:
\"\"\"{message}\"\"\"

{history_block}

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


class LLMClient:
    """
    Wrapper para a API Anthropic com cache semântico local.
    O cache evita chamadas repetidas para mensagens similares
    do mesmo tipo de agente, reduzindo custo significativamente.
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        enable_cache: bool = True,
        similarity_threshold: float = 0.92,
    ):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model
        self.enable_cache = enable_cache
        self.similarity_threshold = similarity_threshold
        self._cache: list[dict] = []   # lista de {embedding, response}
        self._embedder = None
        self._call_count = 0
        self._cache_hits = 0

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
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

    def decide(
        self,
        agent_description: str,
        message_content: str,
        history: list[dict],
    ) -> tuple[Decision, str]:
        """
        Chama o LLM para decidir o que o agente faz com a mensagem.

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

        # Tenta cache primeiro
        cached = self._find_in_cache(prompt)
        if cached:
            self._cache_hits += 1
            logger.debug(f"Cache hit ({self._cache_hits} total)")
            return Decision(cached["decision"]), cached.get("content", "")

        # Chama a API
        self._call_count += 1
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            parsed = json.loads(raw)
            decision = Decision(parsed.get("decision", Decision.IGNORE.value))
            content = parsed.get("content", "")
            self._add_to_cache(prompt, {"decision": decision.value, "content": content})
            return decision, content

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Erro ao parsear resposta LLM: {e}. Usando IGNORAR.")
            return Decision.IGNORE, ""

    @property
    def stats(self) -> dict:
        total = self._call_count + self._cache_hits
        hit_rate = self._cache_hits / total if total > 0 else 0
        return {
            "api_calls": self._call_count,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": f"{hit_rate:.1%}",
        }
