# Protocolo de anotação de postura

## A pergunta que a anotação responde

O recálculo separa as mensagens por profundidade de refutação. Profundidade 0 é
o boato, 1 é a correção dele. De 2 em diante a profundidade sozinha não diz a
postura do texto: contestar uma correção pode ser uma volta ao boato ou pode ser
uma segunda correção que reforça a mesma coisa.

Por isso o alcance do boato hoje tem dois limites. O inferior conta só a
profundidade 0. O superior soma todo o estrato ambíguo. A anotação mede qual
fração do estrato ambíguo de fato apoia a alegação falsa, e com isso fecha o
intervalo.

Nada disso é opinião sobre a qualidade dos textos. É uma classificação de
postura em relação a uma alegação específica.

## A unidade

Uma linha é um texto distinto publicado na campanha. O mesmo texto publicado por
vários agentes aparece uma vez só, e a coluna `ocorrencias` diz quantas vezes
circulou. O anotador julga o texto, não a execução.

## Os quatro rótulos

Todo julgamento é em relação ao texto da coluna `alegacao`, que é a alegação
original daquela linhagem. Leia a alegação primeiro, depois o texto.

| Rótulo | Quando usar |
|---|---|
| `apoia` | O texto afirma a alegação central como verdadeira, no todo ou em reformulação equivalente, ou a repassa tratando como fato estabelecido |
| `rejeita` | O texto nega a alegação central ou afirma que ela é falsa |
| `misto` | O texto nega uma parte e afirma outra, ou mantém a alegação viva como possibilidade sem tomar posição |
| `nao_relacionado` | O texto não trata da alegação central |

## Regras de decisão

1. **Julgue a postura, não a qualidade.** Uma rejeição correta que acrescenta um
   detalhe sem fonte continua sendo `rejeita`. Anote o detalhe na justificativa.
   A qualidade factual é outra análise.
2. **Não premie nem puna o tom.** Texto agressivo que nega a alegação é
   `rejeita`. Texto educado que a repassa é `apoia`.
3. **Perguntar sem se posicionar é `misto`** quando a pergunta mantém a alegação
   como algo que pode ser verdade. É `nao_relacionado` quando o texto só pede
   fonte sem repetir a alegação.
4. **Não olhe a coluna `refutation_depth` antes de decidir.** Ela é exatamente o
   que a anotação está testando. Se ajudar, esconda a coluna na planilha antes
   de começar.
5. **Não converse com o outro anotador** enquanto estiver anotando. As duas
   leituras só valem se forem independentes.
6. **Na dúvida depois de duas leituras, marque `misto`** e escreva na
   justificativa o que ficou ambíguo. Dúvida registrada é informação. Chute
   disfarçado de certeza não é.
7. **Não reordene nem apague linhas.** A consolidação cruza pelo `text_id`.

## Justificativa

Uma frase por linha, dizendo qual trecho decidiu o rótulo. Serve para a
adjudicação e para o artigo poder citar exemplos. Linha sem justificativa volta
para o anotador.

## Procedimento

1. T2 entrega `amostra_anotacao.csv`, com os três estratos já sorteados.
2. Cada anotador faz sua cópia e preenche `rotulo`, `justificativa` e `anotador`.
3. Os dois arquivos vão para a consolidação sem passar um pelo outro.
4. A consolidação calcula o kappa de Cohen, no total e por estrato.
5. As divergências vão para um terceiro integrante, que decide sem saber quem
   votou o quê. De preferência alguém que não anotou.
6. A planilha final tem o rótulo decidido e a origem de cada decisão: acordo
   entre os dois, ou adjudicação.

## Como o resultado entra na análise

A fração de cada rótulo é ponderada pela coluna `peso`, porque os estratos foram
sorteados em proporções diferentes do tamanho real de cada um. Sem o peso, o
estrato ambíguo apareceria com importância maior do que tem.

Da fração do estrato ambíguo rotulada como `apoia` sai o alcance ajustado,
definido no [PLANO-DE-ANALISE.md](PLANO-DE-ANALISE.md). O artigo reporta também
a variante conservadora, somando `apoia` e `misto`, e deixa claro qual das duas
está sendo citada em cada frase.

O kappa entra no artigo como está. Concordância baixa descreve um limite real da
classificação e é um resultado legítimo. Reanotar até o número subir invalidaria
a medida.

## Os estratos e por que o ambíguo tem mais linhas

| Estrato | Profundidade | Linhas sorteadas | Papel |
|---|---|---:|---|
| `boato` | 0 | 60 | Conferência: espera-se predominância de `apoia` |
| `correcao` | 1 | 60 | Conferência: espera-se predominância de `rejeita` |
| `ambiguo` | 2 ou mais | 180 | É aqui que o limite superior do alcance se decide |

Os dois primeiros estratos servem de controle do próprio instrumento. Se o
estrato `boato` não vier predominantemente `apoia`, o problema está na anotação
ou na reconstrução, e isso precisa ser resolvido antes de usar o estrato
ambíguo.

## Como a amostra é sorteada

Pelo script `amostrar_textos.py`, na raiz do repositório:

```
python amostrar_textos.py <pasta da campanha> --saida amostra_anotacao.csv --seed <seed declarada>
```

O sorteio ordena os textos por identificador antes de sortear, então não depende
da ordem de leitura dos arquivos. Com a mesma seed, a mesma amostra. A seed fica
registrada no plano de análise antes do sorteio.
