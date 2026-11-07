# Plano de análise

Fixado antes de T2 rodar. O que mudar depois disso entra no artigo como mudança
declarada, com a razão, e não como se sempre tivesse sido assim.

## Unidade e agrupamento

A unidade de análise é a execução. O agrupamento é a seed estrutural, porque
execuções que compartilham a seed compartilham o grafo e a população inicial, e
portanto não são independentes. Toda reamostragem sorteia seeds inteiras, não
execuções soltas.

Um controle pertence a um bloco e só pode ser pareado com os tratamentos do seu
próprio bloco. O mesmo controle não conta como várias observações independentes.

## Desfechos

**Primário.** Diferença pareada, em pontos percentuais, entre `reach_legacy_pct` e
`reach_strict_pct` na mesma execução. É o tamanho do artefato de medição.
Reportado como média, mediana e intervalo de 95%.

**Primário binário.** Proporção de execuções em que o boato não passou do
emissor, ou seja, `reach_strict_pct` menor ou igual a uma exposição sobre o
total de agentes. Reportado com intervalo de 95%.

**Secundários.** Distribuição de `reach_strict_pct`, `correction_strict_pct`,
`reach_ambiguous_pct` e `reach_upper_pct`. Taxa de recusa do emissor por
estímulo, extraída do `decision_audit`. Nenhum deles decide a conclusão do
artigo sozinho.

**Derivado da anotação.** A fração ponderada de textos do estrato ambíguo
rotulados como apoiando a alegação falsa. O alcance ajustado é o alcance estrito
mais essa fração aplicada ao alcance ambíguo. Essa soma assume que a fração
medida na amostra vale para a população do estrato, e essa suposição vai escrita
no artigo junto com o número.

## Inferência

Bootstrap agrupado por seed estrutural, com 10.000 reamostragens e intervalos de
percentil. Para o desfecho binário pareado, teste de sinais exato, que não supõe
distribuição.

O intervalo é descritivo das condições executadas. Ele não estende a conclusão
para redes, estímulos ou modelos que não entraram na campanha.

## Multiplicidade

Correção de Bonferroni sobre o número de condições declaradas. O número exato
sai da contagem de condições em T2 e é escrito aqui antes de qualquer teste.
Comparação que não estava declarada entra como exploratória e recebe esse rótulo
no texto.

## O que é descritivo e o que é confirmatório

Esta separação é obrigatória no artigo, porque as duas metades deste trabalho
têm estatutos diferentes.

| Análise | Estatuto | Por quê |
|---|---|---|
| Tamanho do artefato, alcance estrito, alcance da correção | **Descritivo** | Os números foram observados antes deste plano existir. Reportar como descrição das execuções, com incerteza, e não como teste confirmatório |
| Conferência contra a contagem antiga | Verificação | Zero divergências é pré-requisito, não resultado |
| Anotação de postura, kappa e alcance ajustado | **Confirmatório** | Protocolo, estratos, tamanhos e seed estão fixados antes de o dado existir |
| Recusa do emissor por estímulo | **Descritivo** | Observado antes do plano. Vira confirmatório só com um preflight próprio |
| A/B do bloco de refutação | Exploratório | Amostra pequena, e o resultado não separa o efeito do enquadramento do efeito do tema |

Apresentar a primeira linha como se fosse confirmatória seria o mesmo erro de
método que o artigo denuncia.

## Regras que não mudam depois

1. Os tamanhos dos estratos e a seed do sorteio são fixados antes do sorteio e
   escritos aqui.
2. Nenhuma execução sai da análise depois de ver seu resultado. Execução
   excluída precisa de critério declarado antes, como falha de backend
   registrada ou intervenção configurada que não foi aplicada.
3. Kappa baixo é reportado como está. Não se reanota até o número subir.
4. Divergência na conferência da reconstrução para a investigação. Não se
   descarta a execução divergente para zerar a contagem.

## O que o artigo não vai afirmar

Nenhuma destas afirmações é sustentada pelos dados que existem, e todas devem
ficar na seção de limites:

- Que uma topologia favorece mais a propagação do que outra.
- Que uma estratégia de intervenção é mais eficaz do que outra.
- Que existe um limiar de ceticismo, brasileiro ou não.
- Que os perfis reproduzem comportamento de pessoas brasileiras.
- Que o alcance observado se transfere para outro modelo de linguagem.
- Que a ausência de propagação do boato demonstra que o simulador contém
  desinformação. Ela demonstra que o modelo recusou repassar aquele estímulo.

## Parâmetros a preencher em T2

| Parâmetro | Valor |
|---|---|
| Seed do sorteio da amostra | 0, declarada antes do sorteio |
| Tamanhos dos estratos | boato 60, correção 60, ambíguo 180 |
| Número de condições para Bonferroni | a contar em T2 |
| Reamostragens do bootstrap | 10.000 |

## Conferência de integridade antes de qualquer tabela

A campanha fechada tem **1.723 execuções e 1.641 contrastes pareados**, todas
com auditoria de mensagens e nenhuma divergência na reconstrução. Esses números
são o gabarito.

Qualquer análise que carregue um total diferente está lendo uma cópia
incompleta, e o resultado sai com cara de completo. Por isso
`scripts/analisar_corrigido.py` aceita `--esperado 1723` e para quando não bate. Use
sempre.
