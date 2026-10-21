# BrazilianInfoSim

Framework de simulação de sociedades com agentes LLM para estudar a propagação de desinformação no contexto brasileiro.

> TCC — Engenharia de Computação | PUC Minas  
> Orientador: Prof. Pedro Américo Almeida Magalhães Júnior

---

## Estrutura do Projeto

```
brazilianinfosim/
├── src/
│   ├── agents/
│   │   ├── profiles.py       # Perfis comportamentais dos agentes
│   │   └── agent.py          # Agente Mesa integrado com LLM
│   ├── network/
│   │   └── topology.py       # Geração de grafos (Erdős-Rényi, BA, WS)
│   ├── llm/
│   │   └── client.py         # Cliente multi-provider (Ollama/Anthropic) com cache semântico
│   ├── simulation/
│   │   ├── engine.py         # Motor de simulação (Mesa)
│   │   ├── messages.py       # Mensagens iniciais das campanhas
│   │   ├── research_messages.py  # Estímulos da campanha de pesquisa
│   │   ├── baseline.py       # Referências SIR e SEIR
│   │   ├── persistence.py    # Proveniência e gravação atômica
│   │   └── recorder.py, replay.py  # Gravação e replay de execuções
│   └── metrics/
│       ├── analysis.py       # Métricas e visualizações
│       └── content_review.py # Medição por conteúdo
├── scripts/
│   ├── run_simulation.py     # Simulação única ou matriz completa
│   ├── run_impact.py         # Campanha de intervenções com orçamento de tempo
│   ├── run_research.py       # Campanha de pesquisa com contrastes pareados
│   ├── run_content_review.py # Revisão por conteúdo de uma campanha
│   └── legacy/               # Runners das campanhas históricas (expandida, assuntos, suplementar, mutação)
├── analysis/                 # Análise da campanha de pesquisa e referência externa
├── notebooks/                # Execução de fatias da campanha no Colab
├── tests/                    # Suíte pytest, sem chamadas reais a LLM
├── data/outputs/             # Resultados, gravações e CSVs (fora do git)
├── app.py                    # Replay visual (solara run app.py)
├── requirements.txt
└── .env.example
```

Os comandos abaixo partem da raiz do repositório, porque as saídas são gravadas
em `data/outputs/` relativo à pasta atual.

---

## Setup

> Requer **Python 3.14** (dependências fixadas e validadas nessa versão).

```bash
# 1. Clone o repositório
git clone https://github.com/yrlanrteixeira/brazilianinfosim.git
cd brazilianinfosim

# 2. Crie o ambiente virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# O default é Ollama (local). Para usar a API da Anthropic,
# ajuste LLM_PROVIDER=anthropic e preencha ANTHROPIC_API_KEY no .env
```

### Provedor de LLM

O projeto roda por padrão com **Ollama** (LLM local, sem custo de API). Configure via `.env`
(`LLM_PROVIDER`, `LLM_MODEL`, `OLLAMA_BASE_URL`) ou pelas flags `--provider` / `--model`.

```bash
# Ollama (default): suba o servidor e baixe o modelo antes
ollama serve
ollama pull llama3.1:8b

# Anthropic: defina LLM_PROVIDER=anthropic e ANTHROPIC_API_KEY no .env
```

---

## Uso

### Simulação única
```bash
# Configuração padrão (scale_free, 50 agentes)
python scripts/run_simulation.py

# Topologia específica com intervenção
python scripts/run_simulation.py --topology small_world --intervention factcheckers_hub

# Mais agentes, menos ticks
python scripts/run_simulation.py --agents 100 --ticks 50 --topology random
```

### Matriz experimental completa (PC4)
```bash
python scripts/run_simulation.py --all
# Salva os 36 cenários em uma nova pasta data/outputs/tcc2/matrix_<id>/
```

### Replay visual

```bash
python scripts/run_simulation.py --record --intervention remove_hubs --intervention-tick 1
pip install -r requirements-viz.txt
solara run app.py
```

`--record` também funciona com `--all`. Cada execução recebe um JSON exclusivo
em `data/outputs/recordings/`. O replay acompanha os nós ativos de cada tick,
preserva o alcance histórico e não chama o LLM.

### Testes unitários (sem precisar de API)
```bash
pytest tests/ -v
```

---

## Topologias Disponíveis

| Flag | Modelo | Estrutura idealizada |
|---|---|---|
| `random` | Erdős-Rényi | Arestas sorteadas independentemente |
| `scale_free` | Barabási-Albert | Crescimento por conexão preferencial |
| `small_world` | Watts-Strogatz | Vizinhanças locais com reconexões |

Essas estruturas não equivalem a plataformas reais validadas. Os parâmetros
padrão produzem densidades diferentes; comparações entre topologias devem
declarar esse fator.

## Intervenções Disponíveis

| Flag | Efeito |
|---|---|
| `factcheckers_hub` | Converte os 10% de nós de maior grau em verificadores |
| `factcheckers_peripheral` | Converte os 10% de nós de menor grau em verificadores |
| `remove_hubs` | Remove os 5 maiores supernós da rede |

---

## Campanha com orçamento de tempo

```bash
python scripts/run_impact.py --dry-run
python scripts/run_impact.py --pilot --agents 20 --ticks 3 --hours 0.1 --output data/outputs/tcc2/piloto
python scripts/run_impact.py --hours 16 --output data/outputs/tcc2/nova_campanha
python scripts/run_impact.py --output data/outputs/tcc2/nova_campanha --resume
```

A grade padrão tem 6.240 casos possíveis, com Ollama local e `llama3.1:8b`.
O número concluído depende do orçamento e da duração das cascatas. A retomada
preserva o prazo original e recusa mudanças no código, desenho ou modelo.
Cache desligado, prompts e respostas auditáveis, métricas por execução e
contrastes pareados são gravados incrementalmente. `status.json` informa o
progresso; `campaign.json` identifica o modelo e o prazo.

Para 24 horas, defina `--hours 24` ao iniciar uma campanha em outra pasta.
O orçamento conta tempo corrido desde o início, incluindo períodos com o
computador suspenso ou o processo parado. `--resume --hours 24` não renova
uma campanha vencida. A retomada pula tentativas já registradas, inclusive
falhas e interrupções; ela não continua uma simulação a partir de um tick.

O piloto deve terminar com quatro sucessos e nenhuma falha antes da campanha
longa. Mantenha a máquina ligada, conectada à energia e sem suspensão. Não
atualize código, dependências, modelo ou Ollama durante a campanha.

A fila de novas campanhas completa cada bloco de 13 casos: um controle e três
intervenções nos momentos `t=0`, `t=1`, `t=3` e `t=10`. A réplica seguinte
mantém rede, população e mensagem, variando a semente do LLM. Com os dois
valores padrão, os primeiros 26 casos cobrem esses contrastes e suas réplicas.
Isso antecipa a cobertura temporal, mas concentra o início em uma configuração
de rede e mensagem. Não garante concluir um bloco dentro do orçamento.
Campanhas históricas usaram outra ordem; mudanças no código ou na fila exigem
uma nova campanha e nunca devem ser aplicadas aos dados congelados.

Compartilhe a pasta completa da campanha, incluindo `results/`, `attempts/`,
`campaign.json`, `status.json` e CSVs. Os JSONs preservam a auditoria e os CSVs
podem ser regenerados. Resultados de computadores diferentes devem ficar
separados e ser conferidos por configuração e caso antes de qualquer união.

Os novos executores salvam em `data/outputs/tcc2`. Os alcances das linhagens
operacionais do boato e da refutação são separados. Extinção exige filas vazias; encerrar por limite de
ticks não significa extinção. Intervenções registram se e quando ocorreram.
No CLI principal, `--intervention-tick 0` aplica antes da primeira decisão;
`--cache-mode off` mantém amostragens independentes de reutilização do cache.

Custos e quantidade de chamadas devem ser medidos na máquina de execução;
um piloto curto não prevê o custo de cascatas longas. Os resultados
dos testes controlados verificam o software; a eficácia das intervenções
depende da campanha com LLM. As personas e mensagens contextualizam o modelo
em português; os resultados não estabelecem validade populacional brasileira.

## Medição por conteúdo

`final_reach_pct` acompanha a linhagem operacional do boato, enquanto
`final_correction_reach_pct` acompanha a linhagem de refutação. A ação
`REFUTAR` alterna essa linhagem: refutar uma correção pode produzir outro texto
que também rejeita a alegação inicial. Portanto, nenhum desses contadores
classifica o sentido ou a veracidade do texto. `belief_level` e `final_believers`
são estados calculados a partir das ações, sem validação como crenças humanas.
Os nomes históricos foram preservados por compatibilidade, com a interpretação
registrada em `metric_semantics` no JSON.

Cada resultado novo grava `message_audit`: publicações efetivas e recebimentos
aceitos após deduplicação, incluindo a exposição inicial, mensagens ainda nas
filas e agentes removidos. Propostas de texto descartadas não contam como
publicação. Tentativas interrompidas preservam os eventos disponíveis, mas
permanecem fora dos resultados completos.

```bash
python scripts/run_content_review.py data/outputs/tcc2/nova_campanha --output data/outputs/tcc2/revisao
# Preencha stance, reviewer e rationale em revisao/review_template.json.
python scripts/run_content_review.py data/outputs/tcc2/nova_campanha --annotations data/outputs/tcc2/revisao/review_template.json --output data/outputs/tcc2/revisao
```

A entrada também pode ser um JSON de resultado ou uma pasta de resultados.
As posições admitidas, sempre relativas à alegação inicial, são `supports`
(apoia), `rejects` (rejeita), `mixed` (mista), `unrelated` (alheia),
`ambiguous` (ambígua) e `pending` (pendente). Toda revisão exige autoria e
justificativa. Nas reexecuções, o modelo de anotações recebe os textos novos e
preserva os itens já editados.
Os hashes vinculam a revisão aos resultados, às anotações e aos pares de textos.
Edite apenas os campos de revisão; alterações nos textos identificados pelo
hash são recusadas. Se usar um arquivo de anotações separado, incorpore nele os
novos itens pendentes do template antes de concluir a revisão.

O alcance conta agentes únicos sobre a população inicial. Pendências e
ambiguidades deixam o alcance por posição ausente (`null`); o relatório
mostra limites de classificação, que não são intervalos de confiança.
Textos mistos têm categoria própria, e os alcances podem se sobrepor quando
um agente recebeu textos de posições diferentes. O alcance do texto original
mede igualdade literal, sem presumir sua posição. Diferenças pareadas de apoio
só são calculadas quando ambos os casos estão completamente classificados.
A revisão da posição não verifica a exatidão das afirmações adicionais.

Resultados antigos sem auditoria de recebimentos são recusados por esse
comando. Eles precisam de reprodução validada, com o código e as respostas
originais, antes de receberem uma nova medição. Instrumentação e testes
controlados não constituem novas amostras experimentais.

## Campanha de pesquisa

O `run_research.py` prepara contrastes pareados de rede, perfis, ceticismo,
mutação e intervenções. A grade padrão tem 2.112 casos: 12 sementes de cenário,
quatro redações de duas alegações, duas sementes de LLM e 22 condições por bloco.
Ao contrário do `run_impact.py`, cada sessão tem orçamento próprio.

```bash
python scripts/run_research.py --output data/outputs/tcc2/conclusao --dry-run
python scripts/run_research.py --output data/outputs/tcc2/conclusao --hours 6
python scripts/run_research.py --output data/outputs/tcc2/conclusao --hours 6 --resume --retry-incomplete
```

Execuções completas não são repetidas. Falhas e interrupções só são retentadas
com `--retry-incomplete`, e a tentativa anterior fica em `attempt_history`.
O manifesto recusa retomar com outro código, modelo ou desenho, e
`source_snapshot.zip` preserva o código do início da campanha.

### Em várias máquinas

`--shard I/N` divide a grade pelas sementes de cenário: cada fatia contém blocos
pareados completos e as três topologias. Cada fatia roda em uma única máquina,
em pasta própria, com o mesmo commit e o mesmo digest do modelo.

```bash
python scripts/run_research.py --output data/outputs/tcc2/conclusao-shard-0-de-4 --shard 0/4 --hours 6
```

[notebooks/campanha_colab.ipynb](notebooks/campanha_colab.ipynb) roda outra fatia
no Colab, gravando no Google Drive, e confere o digest do modelo antes de começar.
Uma máquina que termina pode assumir uma fatia ainda não iniciada. Os scripts de
análise recebem as pastas das fatias juntas e recusam misturar código, modelo,
desenho ou fatias repetidas. O `analysis.json` registra em `campaigns` a pasta,
a fatia, o Python e a versão do Ollama de cada máquina.

Os scripts de análise ficam em `analysis/`; com fatias, passe todas as pastas no lugar de uma:

```bash
# Template de revisão e CSVs; repita com --annotations após anotar os textos.
python analysis/analyze_completion.py data/outputs/tcc2/conclusao --output data/outputs/tcc2/conclusao/review
# Distância de embeddings entre versões publicadas; não mede veracidade.
python analysis/measure_semantic_change.py data/outputs/tcc2/conclusao --model-path <snapshot-local> --output data/outputs/tcc2/conclusao/review/semantic.json
# Referência externa SIR/SEIR com metadados brasileiros do ICWSM (Zenodo).
python analysis/fetch_reference_data.py --output data/outputs/tcc2/external/metadata --member icwsm_dataset_share/brazil/misinfo_anonymized.txt
python analysis/benchmark_external.py data/outputs/tcc2/external/metadata/misinfo_anonymized.txt --campaign data/outputs/tcc2/conclusao --annotations <anotacoes.json> --output data/outputs/tcc2/conclusao/benchmark
```
