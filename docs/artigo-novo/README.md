# Próxima versão do artigo: o que muda e onde cada peça está

Pacote de entrega para o grupo. Quem for mexer no artigo começa por aqui.

**Formato decidido:** o trabalho novo entra como próxima versão do artigo do
PC2, não como artigo separado. O PC2 já tem introdução, revisão, motivação, as
cinco questões de pesquisa, metodologia e a estrutura de resultados. Entra um
terceiro lote de execuções, a correção da medição e a anotação de postura. As
seções 6.3, 6.4, 7.1, 7.3, 7.4, 7.5, 8 e o apêndice são reescritos.

## Por que esta é a continuação natural

O próprio PC2 anuncia este trabalho. Na página 19:

> A próxima etapa deve priorizar a auditabilidade do prompt e do modelo por
> execução, uma classificação factual de mensagens com critérios explícitos e
> revisão independente, além de desenhos pareados com réplicas suficientes para
> as perguntas selecionadas.

São exatamente os três itens deste pacote. E o PC2 já declara os dois defeitos,
só que como limitação, não como medida:

- Seção 6.3, sobre a linhagem: "na campanha Qwen3 foram observadas inversões de
  rótulo quando o LLM escolhia REFUTAR ao responder a uma mensagem corretiva".
- Seção 6.3, sobre o prompt: "Ele também sugere explicitamente que céticos e
  verificadores provavelmente encaminhem refutações. Essa orientação faz parte
  do tratamento experimental e pode induzir o comportamento observado".
- O apêndice reproduz o bloco ATENÇÃO, que é o trecho corrigido.

O grupo não precisa descobrir nada. Precisa medir e consertar o que já escreveu
que estava errado.

## O salto de amostra

O PC2 reporta 165 execuções somando os dois lotes, 154 do Llama 3.1 e 11 do
Qwen3. A campanha `conclusao` tem 1.723 resultados gravados e é a única com
auditoria de mensagens evento a evento. É a única que pode ser recalculada sem
reexecutar.

## A tese

Em simulações de desinformação com agentes de linguagem, a linhagem que o
programa usa para classificar uma mensagem é um canal de entrega, não a postura
do texto. A flag alterna a cada refutação, então contestar uma correção devolve
o texto à contagem do boato. O que circulou foram as correções e suas
contestações, não a alegação falsa.

O segundo achado é a pré-condição que quase nunca aparece em trabalhos desse
tipo. Antes de medir alcance, é preciso que o modelo aceite repassar o estímulo.
Com um modelo alinhado, o emissor refuta o próprio boato e a linhagem morre no
primeiro nó na maioria das execuções. A taxa de recusa depende do tema do
estímulo e, em parte, do enquadramento do prompt.

## O que muda em cada seção do PC2

| Seção | O que está escrito hoje | O que fazer | Tarefa |
|---|---|---|---|
| 1 Introdução | Contribuição descrita como metodológica e exploratória | Acrescentar a correção de medição à contribuição. Mudança pequena | T7 |
| 2.2 e Tabela 1 | Tabela comparativa sem a dimensão que sustenta a contribuição | Acrescentar a coluna sobre separar mensagem original de correção. É a pergunta 1 do parecer | T5 |
| 5.2, objetivo 4 | Prevê "taxa de mutação semântica" como métrica | Reescrever: o contador de mutações incluía correções na linhagem do boato | T7 |
| 6.3 Motor e prompt | Diz que os anexos não trazem os prompts das campanhas | Descrever a correção do bloco condicional e que a campanha nova grava o prompt de cada chamada | T7 |
| 6.4 Métricas | Linhagem em duas categorias, sem limite superior | Reescrever com profundidade de refutação: alcance estrito, da correção, ambíguo e o limite superior | T7 |
| 7.1 Tabela 6 | Dois lotes | Acrescentar a coluna do terceiro lote | T2 |
| 7.2 Lote Llama | Resultados do lote de 154 | Manter, e dizer que esse lote não grava auditoria de mensagens, logo não pode ser recalculado. Isso é em si um argumento de reprodutibilidade | T7 |
| 7.3 Lote Qwen3 | A inversão aparece em 11 execuções, com um exemplo | Reescrever com a medida sobre o lote novo e a conferência contra a contagem antiga | T2 |
| 7.x nova | Não existe | Resultados da anotação de postura, com kappa e o intervalo fechado | T3, T4 |
| 7.x nova | Não existe | Repasse como pré-condição: taxa de recusa do emissor por estímulo | T2 |
| 7.4 Tabela 10 | QP3 e QP4 como "parcial" | Atualizar: as duas dependiam de uma métrica contaminada. Consertá-la é pré-condição, não detalhe | T7 |
| 7.5 Limitações | "baseada em um revisor, sem medida de concordância" | Substituir por dois anotadores independentes, kappa e adjudicação | T4 |
| 8 Considerações finais | Conclusão dos dois lotes | Reescrever incorporando o terceiro lote e a correção | T7 |
| Apêndice A | Template com o bloco ATENÇÃO incondicional | Mostrar os dois prompts, antes e depois, e o teste que garante que o bloco só entra na refutação | T7 |

O ponto mais forte para a defesa: QP3 e QP4 dependem de uma métrica que o
próprio artigo diz que não pode ser confiada. Consertar a métrica não é ajuste
técnico, é pré-condição para responder duas das cinco questões de pesquisa.

## O que continua sem resposta

QP5, plausibilidade e aderência ao Brasil, continua não respondida, e nada neste
pacote a responde. SIR/SEIR validado é outro bloco de pesquisa. O mesmo vale
para as perguntas 1, 5, 7 e 9 do parecer, com a ressalva de que a 1 é a tarefa
T5 e só depende de leitura. O quadro completo está em
[PERGUNTAS-DO-PARECER.md](../revisao-tcc-ii/PERGUNTAS-DO-PARECER.md).

## Onde cada coisa está

| Peça | Caminho |
|---|---|
| Correções no simulador | `src/agents/agent.py`, `src/llm/client.py`, `src/simulation/engine.py`, `src/metrics/analysis.py` |
| Testes das correções | `tests/test_lineage_stance.py`, `tests/test_prompt_framing.py` |
| Recálculo offline | `recompute_lineage.py` e seu teste |
| Sorteio da amostra de anotação | `amostrar_textos.py` e seu teste |
| Dados da campanha nova | Google Drive, `brazilianinfosim/conclusao/shard-*-de-8/` |
| Campanha do lote Llama | `data/outputs/tcc2/impacto-20260923/`, 154 execuções |
| Campanha do lote Qwen3 | `data/outputs/tcc2/ciencia-20260923-8h/`, 11 execuções, sem `message_audit` |
| Consolidação que virou a seção 7.3 | `docs/revisao-tcc-ii/consolidacao-20260924/` |
| Quadro do parecer | `docs/revisao-tcc-ii/PERGUNTAS-DO-PARECER.md` |

## Estado do código, e por que isso importa

O repositório tem três estados que não se encontram:

| Estado | Onde | O que tem |
|---|---|---|
| Correções novas | branch `fix/acoplamento-intervencao` | As três correções e o recálculo. Saiu de um commit de setembro, antes de toda a pesquisa |
| Código de pesquisa | `main` | `baseline.py` com a referência SEIR, `replay.py`, `recorder.py`, `research_messages.py`, `run_research.py` |
| Código que rodou a campanha | branch `feat/campanha-em-fatias`, não integrado à `main` | Tudo acima mais `content_review.py` e o notebook do Colab |

O branch atual **não contém** o código que gerou os dados. Qualquer execução
nova precisa do porte da tarefa T1. Enquanto isso não acontecer, as correções
não alcançam a campanha.

A suíte do branch atual está verde, com 170 testes.

## Ordem de trabalho

T1 e T5 começam já e não dependem de nada. T2 depende dos dados locais. T3 e T4
dependem de T2 ter rodado o sorteio. T6 fecha. T7 acompanha do início. Detalhe
de cada uma em [TAREFAS.md](TAREFAS.md).
