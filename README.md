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
python run_simulation.py

# Topologia específica com intervenção
python run_simulation.py --topology small_world --intervention factcheckers_hub

# Mais agentes, menos ticks
python run_simulation.py --agents 100 --ticks 50 --topology random
```

### Matriz experimental completa (PC4)
```bash
python run_simulation.py --all
# Salva os 36 cenários em uma nova pasta data/outputs/tcc2/matrix_<id>/
```

### Replay visual

```bash
python run_simulation.py --record --intervention remove_hubs --intervention-tick 1
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
python run_impact.py --dry-run
python run_impact.py --pilot --agents 20 --ticks 3 --hours 0.1 --output data/outputs/tcc2/piloto
python run_impact.py --hours 16 --output data/outputs/tcc2/nova_campanha
python run_impact.py --output data/outputs/tcc2/nova_campanha --resume
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
python run_content_review.py data/outputs/tcc2/nova_campanha --output data/outputs/tcc2/revisao
# Preencha stance, reviewer e rationale em revisao/review_template.json.
python run_content_review.py data/outputs/tcc2/nova_campanha --annotations data/outputs/tcc2/revisao/review_template.json --output data/outputs/tcc2/revisao
```

A entrada também pode ser um JSON de resultado ou uma pasta de resultados.
As posições admitidas, sempre relativas à alegação inicial, são `supports`
(apoia), `rejects` (rejeita), `mixed` (mista), `unrelated` (alheia),
`ambiguous` (ambígua) e `pending` (pendente). Toda revisão exige autoria e
justificativa. O modelo de anotações existente é preservado nas reexecuções.
Os hashes vinculam a revisão aos resultados, às anotações e aos pares de textos.
Edite apenas os campos de revisão; alterações nos textos identificados pelo
hash são recusadas. Se novas execuções acrescentarem textos, use outra pasta
de saída para gerar o inventário ampliado com as anotações anteriores.

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

## Texto do TCC

A revisão acadêmica fica em [paper/README.md](paper/README.md), com o texto
editável de substituição, as equações, as hipóteses de simulação e a delimitação
dos resultados históricos. Os documentos não apresentam os testes desta branch
como campanhas realizadas com LLM.
