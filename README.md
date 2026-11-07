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
python run_impact.py --dry-run
python run_impact.py --hours 8 --output data/outputs/tcc2/nova_campanha
python run_impact.py --output data/outputs/tcc2/nova_campanha --resume
```

A grade padrão tem 6.240 casos possíveis, com Ollama local e `llama3.1:8b`.
O número concluído depende do orçamento e da duração das cascatas. A retomada
preserva o prazo original e recusa mudanças no código, desenho ou modelo.
Cache desligado, prompts e respostas auditáveis, métricas por execução e
contrastes pareados são gravados incrementalmente. `status.json` informa o
progresso; `campaign.json` identifica o modelo e o prazo.

Os novos executores salvam em `data/outputs/tcc2`. O alcance do boato e o da
correção são separados. Extinção exige filas vazias; encerrar por limite de
ticks não significa extinção. Intervenções registram se e quando ocorreram.
No CLI principal, `--intervention-tick 0` aplica antes da primeira decisão;
`--cache-mode off` mantém amostragens independentes de reutilização do cache.

Custos e quantidade de chamadas devem ser medidos no piloto. Os resultados
dos testes controlados verificam o software; a eficácia das intervenções
depende da campanha com LLM. O protocolo e as limitações estão em
[RECORTE-DEFESA.md](docs/revisao-tcc-ii/RECORTE-DEFESA.md).
