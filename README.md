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
│   │   └── engine.py         # Motor de simulação (Mesa)
│   └── metrics/
│       └── analysis.py       # Métricas e visualizações
├── tests/
│   ├── test_profiles.py      # Testes unitários dos agentes
│   └── test_network.py       # Testes das topologias
├── data/
│   ├── inputs/               # Mensagens e configurações de experimento
│   └── outputs/              # Resultados, gráficos e CSVs
├── run_simulation.py         # Ponto de entrada principal
├── requirements.txt
└── .env.example
```

---

## Setup

> Requer **Python 3.14** (dependências fixadas e validadas nessa versão).

```bash
# 1. Clone o repositório
git clone https://github.com/seu-grupo/brazilianinfosim.git
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
python run_simulation.py

# Topologia específica com intervenção
python run_simulation.py --topology small_world --intervention factcheckers_hub

# Mais agentes, menos ticks
python run_simulation.py --agents 100 --ticks 50 --topology random
```

### Matriz experimental completa (PC4)
```bash
python run_simulation.py --all
# Gera data/outputs/experiment_matrix.csv com todos os 36 cenários
```

### Testes unitários (sem precisar de API)
```bash
pytest tests/ -v
```

---

## Topologias Disponíveis

| Flag | Modelo | Analogia |
|---|---|---|
| `random` | Erdős-Rényi | Comunidade genérica |
| `scale_free` | Barabási-Albert | Twitter / Instagram |
| `small_world` | Watts-Strogatz | WhatsApp (grupos de família) |

## Intervenções Disponíveis

| Flag | Efeito |
|---|---|
| `factcheckers_hub` | Insere fact-checkers nos nós com maior grau |
| `factcheckers_peripheral` | Insere fact-checkers nos nós periféricos |
| `remove_hubs` | Remove os 5 maiores supernós da rede |

---

## Custo de API (estimativa)

| Cenário | Chamadas | Custo (claude-haiku) |
|---|---|---|
| 50 agentes, 100 ticks | ~180 | ~USD 0,04 |
| 100 agentes, 100 ticks | ~400 | ~USD 0,09 |
| Matriz completa (60 runs) | ~10.800 | ~USD 2,40 |

O cache semântico reduz em ~40% as chamadas reais à API.
