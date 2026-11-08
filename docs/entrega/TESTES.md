# Testes e verificações

O que foi corrigido no simulador, o que foi medido sobre a campanha, e como
rodar cada coisa de novo.

Esta pasta tem só dois itens: o `TCC-PC3.tex`, que é o artigo, e este
documento. Todo o resto são scripts versionados em `scripts/` e testes em
`tests/`.

---

## Começando

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```

Esperado: **320 testes passando**. Se algum falhar, pare: os números do artigo
dependem desse código.

O artigo compila no Overleaf. Suba o `TCC-PC3.tex` e as duas imagens de
`figuras/`. O `abakos.sty` e o `figuras/pucmg.png` já estão lá e não vão nesta
pasta.

---

## Parte 1. O que foi corrigido no simulador

### 1.1 A classificação de linhagem

**O problema.** A ação de refutar inverte a marca de linhagem da mensagem. Isso
é necessário para a entrega: sem inverter, a correção seria deduplicada junto
com o boato e não alcançaria quem já o recebeu. Mas a mesma marca era usada
para classificar. Como ela alterna, contestar uma correção devolvia o texto à
contagem do boato, sem que nada no conteúdo tivesse voltado à alegação
original.

**A correção.** A marca continua alternando, porque a entrega depende disso. A
classificação passou a usar `refutation_depth`, que conta refutações
acumuladas e nunca decresce.

**Arquivos.** `src/agents/agent.py`, `src/simulation/engine.py`,
`src/metrics/analysis.py`.

**Teste.** `tests/test_lineage_stance.py`, 7 testes. O que importa ali:

- `test_contested_correction_is_not_counted_as_rumor` reproduz o caso em três
  saltos, boato, correção e contestação, e verifica que o terceiro texto não
  volta à profundidade 0.
- `test_delivery_channel_is_unchanged` garante que a correção **continua**
  sendo entregue. Sem esse teste, seria fácil consertar a medida quebrando a
  entrega.

Um teste que já existia, `test_refuting_a_correction_does_not_count_as_textual_support`
em `tests/test_content_review.py`, afirmava que o contador de linhagem
**passava** do apoio medido na anotação de conteúdo. Essa diferença era o
defeito, registrado como comportamento esperado. Com a correção os dois
coincidem, e a asserção foi trocada para cobrir o comportamento certo.

### 1.2 O bloco condicional do prompt

**O problema.** O parágrafo que explica o marcador `[REFUTAÇÃO]` entrava em
toda decisão, inclusive na decisão sobre o boato original. Ele informava ao
agente que havia uma fake news circulando antes de o agente avaliar a alegação,
o que mistura o tratamento experimental com a instrução dada ao modelo.

**A correção.** O bloco passou a ser preenchido apenas quando a mensagem
recebida começa pelo marcador.

**Arquivo.** `src/llm/client.py`.

**Teste.** `tests/test_prompt_framing.py`, 4 testes. O decisivo é
`test_the_two_prompts_differ_only_by_the_block`: removido o bloco, o prompt da
correção fica idêntico ao prompt do boato. Se alguém mexer no template e
introduzir qualquer outra diferença, o teste quebra.

### 1.3 O que não foi corrigido

A contagem de agentes convencidos usa a mesma marca para decidir a direção da
atualização de crença, e herda o mesmo defeito. Esse caso **não pode** ser
corrigido sobre os resultados gravados, porque a crença evolui durante a
execução e condiciona as decisões seguintes: corrigir exigiria reexecutar a
campanha inteira. A métrica não é usada como desfecho no artigo.

---

## Parte 2. As verificações sobre a campanha

Os quatro scripts rodam sobre a pasta da campanha, que está no Google Drive em
`brazilianinfosim/conclusao/`. São 1.723 execuções e cerca de 2,3 GB, quase
tudo em registro de prompt por chamada.

### 2.1 Recálculo da linhagem

```bash
python scripts/recompute_lineage.py <pasta da campanha>
```

Reconstrói a profundidade de refutação a partir dos eventos de mensagem já
gravados e reescreve o alcance, sem reexecutar nada. Grava
`runs_corrigido.csv` e `paired_effects_corrigido.csv` em cada shard.

**Resultado esperado: 1.723 execuções, 1.641 contrastes pareados, 0 sem
auditoria, 0 divergentes.** Leva cerca de 1,5 minuto.

A conferência que importa é a coluna de divergências. O script recalcula também
a contagem antiga a partir dos mesmos eventos e compara com o valor gravado
durante a execução. **Divergência acima de zero significa que a leitura da
auditoria está errada, e invalida tudo o que vem depois.** Zero divergências em
1.723 execuções é o que dá valor ao alcance reconstruído.

### 2.2 Tabelas de alcance

```bash
python scripts/analisar_corrigido.py <pasta da campanha> --esperado 1723
```

A opção `--esperado` existe por um motivo prático: cópia parcial de campanha
produz tabela com cara de completa. Durante este trabalho uma cópia interrompida
chegou a 852 execuções e teria gerado números plausíveis e errados. Use sempre.

Esperado, nos 82 controles e 23 sementes estruturais:

| Medida | Média | IC 95% |
|---|---:|---:|
| Alcance pelo critério de marca | 36,20% | 26,60 a 45,92 |
| Alcance estrito do boato | 6,80% | 2,49 a 14,53 |
| Alcance da correção | 60,98% | 49,41 a 73,68 |
| Alcance ambíguo | 31,59% | 22,61 a 41,15 |

E sobre as 1.723: diferença pareada entre os dois critérios de **27,13 pontos
percentuais**, intervalo de 21,47 a 33,00; proporção de execuções em que o
boato não passou do emissor de **0,85**, intervalo de 0,75 a 0,95.

Os intervalos vêm de reamostragem com 10.000 repetições sorteando **sementes
inteiras**, não execuções. Execuções da mesma semente compartilham grafo e
população inicial; tratá-las como independentes produziria intervalos estreitos
demais.

### 2.3 Contrastes por condição

```bash
python scripts/contrastes.py <pasta da campanha> --bonferroni
```

Compara cada tratamento ao controle do seu próprio bloco, nas duas métricas
lado a lado, nas 22 condições. Com `--bonferroni` o nível sobe para 99,77%,
porque o risco de erro de 5% é repartido entre as condições.

Nas intervenções, o efeito é calculado só sobre as execuções em que o tratamento
foi de fato aplicado. Em `t=0` isso vale para as 311; em `t=2`, 126 de 314 não
receberam o tratamento porque a circulação se extinguiu antes do segundo tick.
**As linhas de `t=2` descrevem um subconjunto condicionado à sobrevivência da
cascata e não respondem ao efeito do momento de aplicação.**

Três resultados em que os dois critérios discordam na conclusão, e não só na
magnitude:

| Condição | Critério de marca | Critério de profundidade |
|---|---:|---:|
| Emissor verificador | +27,69 [5,35; 50,10] | −5,05 [−18,65; −0,18] |
| Proibir alteração do texto | −26,90 [−44,55; −9,54] | +0,23 [−1,15; 2,24] |
| Limite de retransmissão em t=0 | −25,82 [−41,03; −10,33] | −4,13 [−16,51; 0,09] |

No primeiro, os dois intervalos excluem o zero em direções opostas. No segundo,
o efeito desaparece. No terceiro, deixa de se sustentar.

### 2.4 Comparação com SIR e SEIR

```bash
python scripts/comparar_seir.py <pasta da campanha>
```

Roda as referências epidemiológicas **no mesmo grafo, com o mesmo nó de injeção
e o mesmo horizonte** de cada execução, de modo que a diferença medida não
inclua estrutura nem ponto de partida. As 23 sementes são divididas em dois
conjuntos disjuntos: 12 para ajustar transmissão e recuperação em uma grade, 11
para avaliar.

Esperado: melhor ajuste em transmissão 0,05 e recuperação 0,50, com distância
de 0,106 no ajuste. Na amostra retida, com 892 execuções:

| | Agentes | Referência |
|---|---:|---:|
| Alcance médio | 2,61 | 2,60 (SIR), 2,69 (SEIR) |
| Só o emissor | 0,918 | 0,756 |
| Distância | | 0,163 |

A referência acerta a média e erra a forma. A distância da avaliação ser maior
que a do ajuste, 0,163 contra 0,106, é o sinal de que a separação funcionou.

### 2.5 Figuras

```bash
python scripts/figuras.py <pasta da campanha> --saida figuras
```

Gera três PNG a 300 dpi; o artigo usa duas delas. As cores vêm da paleta
Okabe-Ito e foram validadas para daltonismo, com separação de 21,9 em
protanopia e 31,2 em visão normal. Cada série também se distingue por traço e
marcador, porque a revista imprime em escala de cinza.

### 2.6 Amostra para anotação de postura

```bash
python scripts/amostrar_textos.py <pasta da campanha> --saida amostra.csv --seed 0
```

Sorteia 300 textos estratificados por profundidade, de 225.082 distintos: 60 do
boato, 60 da correção e 180 da faixa ambígua. Cada linha leva a alegação
original contra a qual o texto será julgado, e um peso que devolve o estrato ao
tamanho da população.

Isso ainda **não foi feito**. É o que falta para o alcance da alegação falsa
deixar de ser um intervalo, hoje entre 6,80% e 36,20% nos controles, e virar um
ponto. Precisa de dois anotadores independentes e medida de concordância.

---

## Parte 3. A suíte de testes

320 testes. Doze arquivos foram criados neste trabalho; os demais já existiam.

| Arquivo | Testes | O que protege |
|---|---:|---|
| `test_lineage_stance.py` | 7 | A classificação por profundidade, e que a entrega não quebrou junto |
| `test_prompt_framing.py` | 4 | O bloco condicional do prompt |
| `test_recompute_lineage.py` | 10 | A reconstrução da profundidade a partir dos eventos |
| `test_analisar_corrigido.py` | 23 | Agrupamento por semente, bootstrap, identificação do controle |
| `test_contrastes.py` | 15 | Filtro de tratamento aplicado, ajuste de multiplicidade, saída LaTeX |
| `test_comparar_seir.py` | 15 | Divisão entre ajuste e avaliação, distância entre distribuições |
| `test_amostrar_textos.py` | 13 | Estratificação, reprodutibilidade do sorteio, peso dos estratos |
| `test_figuras.py` | 7 | Agregação por trás das figuras, não o desenho |
| `test_simulation_integrity.py` | 20 | Integridade do motor |
| `test_campaign_persistence.py` | 17 | Gravação e retomada de campanha |
| `test_impact_campaign.py` | 10 | Geração da grade de casos |
| `test_backend_failure.py` | 9 | Backend fora do ar aborta em vez de fabricar decisão |

### Três testes que pegaram erro real

Vale citar, porque mostram o que a suíte está de fato comprando.

**Divisão por semente com repetição.** Em `test_comparar_seir.py`, o teste
`test_the_same_seed_never_falls_on_both_sides` pegou que a função recebia a
lista com uma entrada por execução, e sem deduplicar a mesma semente caía nos
dois lados. A separação entre ajuste e avaliação teria sido ficção, e o número
teria saído bonito.

**Identificação do controle.** A campanha grava `intervention='none'` em toda
condição sem intervenção de rede, não só no controle. A função procurava
intervenção vazia, achava zero controles e a tabela caía em silêncio para a
campanha inteira, rotulada como controles. Hoje o controle é a condição de
referência e a tabela carrega uma coluna de escopo.

**Intervalo ajustado mais estreito que o de 95%.** Em `test_contrastes.py`,
`test_the_adjusted_interval_is_never_narrower_than_the_unadjusted` existe
porque estreitar o intervalo ao corrigir multiplicidade anularia a correção, e é
o tipo de erro que passa sem ninguém notar.

---

## Parte 4. O que não está coberto

Para evitar leitura otimista da suíte.

- **Os números do artigo não foram conferidos por ninguém além de quem os
  produziu.** Os scripts são versionados e rodaram a partir de clone limpo, mas
  uma segunda pessoa reproduzir os quatro comandos da Parte 2 é o que valida o
  resultado. É o próximo passo mais útil.
- **O desenho das figuras não é testado**, só a agregação por trás delas.
- **A anotação de postura não foi feita**, então o alcance da alegação falsa
  continua delimitado por um intervalo.
- **A ablação de cache e regra de difusão não foi executada.**
- **A calibração social não foi feita**, e a campanha indica que ela não seria
  identificável neste desenho: os quatro perfis de emissor produzem efeitos
  entre −4,92 e −5,12, e as cinco frações de céticos deixam a mediana no
  emissor isolado. Se o desfecho não responde à composição da população, não há
  a que ajustar a composição.
