# Divisão de tarefas

Sete blocos independentes. Cada um tem entrada, saída e critério de aceite, para
que ninguém precise perguntar se terminou. Ninguém deve começar a escrever a
seção de resultados antes de T2.

Dependências: T1 e T5 começam já. T2 precisa de acesso ao Drive. T3 e T4
precisam da amostra que sai de T2. T6 fecha depois de T2. T7 acompanha do
início.

---

## T1. Levar as correções para o código que roda a campanha

**Por que existe.** O branch `fix/medicao-de-linhagem` saiu de um commit de
setembro e está 37 commits atrás da `main`. A `main` já integrou todo o trabalho
de pesquisa, moveu os runners para `scripts/` e tem o `content_review.py`. As
correções de medição estão só no branch. Nenhum dos dois lados é suficiente
sozinho.

**Entrada.** O branch e a `main` atualizada. Buscar antes com `git fetch origin`:
é fácil analisar contra uma `main` local velha e chegar a conclusão errada.

**Passos.**

1. `git merge origin/main` dentro do branch. São 15 arquivos em conflito.
2. Resolver primeiro os fáceis: `.gitignore`, `README.md`, e os dois
   modify/delete de `run_subjects.py` e `run_supplementary.py`, que a `main`
   moveu para `scripts/`. Nesses dois, a versão da `main` ganha.
3. Resolver os de conteúdo em `src/agents/agent.py`, `src/llm/client.py`,
   `src/simulation/engine.py` e `src/metrics/analysis.py`. **A base é a versão
   da `main`**, e as correções do branch são reaplicadas por cima. O inverso
   descarta o trabalho de outubro sem avisar.
4. Os `add/add` em `persistence.py` e nos testes de campanha são a mesma
   funcionalidade escrita duas vezes. Ficar com a da `main` e conferir que os
   testes do branch ainda passam contra ela.
5. Rodar a suíte inteira.

**Saída.** Um branch que contém a `main` e as correções, suíte verde.

**Critério de aceite.** Todos os testes passam, incluindo os de pesquisa que só
existem na `main`, como `test_research_campaign.py` e
`test_research_mechanisms.py`. Nenhum teste foi apagado para passar, e
`git diff origin/main` não remove nada que a `main` tenha.

**Tamanho.** Cerca de um dia. É a tarefa mais técnica e a mais arriscada do
pacote: um conflito resolvido para o lado errado apaga trabalho sem deixar
rastro no diff final.

---

## T2. Regerar as tabelas e as figuras do recálculo

**Por que existe.** Tabela de artigo precisa sair de script versionado que
qualquer pessoa roda de novo, não de sessão interativa.

**Entrada.** A campanha `conclusao` copiada para
`data/outputs/tcc2/conclusao/`. Os scripts `scripts/recompute_lineage.py`,
`scripts/analisar_corrigido.py` e `scripts/amostrar_textos.py`, em `scripts/`.

**Situação.** O recálculo já rodou uma vez sobre a campanha fechada e deu
**1.723 execuções, 1.641 contrastes pareados, nenhuma execução sem auditoria e
nenhuma divergência**. Rodar de novo localmente serve de conferência: o número
tem que bater.

**Antes de tudo, confira se a cópia está completa.** O Google Drive para
Desktop entrega a pasta antes de terminar de indexar: os arquivos aparecem, o
`runs.csv` abre, e tem menos linhas do que a campanha tem. Uma análise rodada
nesse estado produz tabela plausível e errada, sem nenhum sinal. O total é
1.723 execuções; abaixo disso, a cópia ainda não chegou.

**Passos.**

1. Rodar `scripts/recompute_lineage.py` apontando para a pasta da campanha. Ele percorre
   os oito shards e grava `runs_corrigido.csv` e `paired_effects_corrigido.csv`
   em cada um.
2. Conferir o relatório: a contagem de divergências tem que ser zero e o total
   tem que ser 1.723. Divergência acima de zero invalida o resto e precisa ser
   investigada antes de seguir.
3. Rodar `scripts/analisar_corrigido.py` com `--esperado 1723`, que grava as tabelas em
   `tabelas/` com o bootstrap agrupado pela seed estrutural. A opção existe
   justamente para barrar a cópia incompleta.
4. Extrair do `decision_audit` a taxa de recusa do emissor por estímulo. É a
   única parte que ainda não tem script.
5. Rodar `scripts/amostrar_textos.py` com a seed declarada e entregar o CSV a T3 e T4.
6. Gerar as figuras.

**Saída.** As tabelas em CSV, as figuras, e `amostra_anotacao.csv`.

**Critério de aceite.** Rodar duas vezes produz arquivos idênticos. Zero
divergências na conferência, e o total bate com os 1.723. A seed do sorteio está
escrita no arquivo e no plano de análise.

**Onde rodar.** Local, a partir do repositório. Os dados têm cerca de 2,3 GB, e
quase tudo é o `decision_audit` com o prompt de cada chamada.

**Tamanho.** Meio dia, já descontado o que está feito.

---

## T3. Anotação de postura, primeiro anotador

**Por que existe.** Hoje o artigo tem um limite inferior e um superior para o
alcance, e a distância entre eles é grande demais para uma tabela. Só a leitura
dos textos fecha o intervalo. É a tarefa mais demorada em tempo de pessoa e a
que não pode ser substituída por mais execução.

**Entrada.** O arquivo `amostra_anotacao.csv`, vindo de T2. O codebook está em
[PROTOCOLO-ANOTACAO.md](PROTOCOLO-ANOTACAO.md).

**Passos.** Preencher `rotulo` e `justificativa` em todas as linhas, sem
conversar com o segundo anotador e sem olhar a coluna `refutation_depth` antes
de decidir.

**Saída.** O CSV preenchido, com o nome do anotador na coluna `anotador`.

**Critério de aceite.** Nenhuma linha em branco. Todo rótulo está entre os
quatro do codebook. Toda linha tem justificativa.

**Tamanho.** Cerca de três horas.

---

## T4. Anotação de postura, segundo anotador, concordância e adjudicação

**Entrada.** A mesma amostra de T3, e depois os dois arquivos preenchidos.

**Passos.**

1. Anotar de forma independente, nas mesmas condições de T3.
2. Calcular o kappa de Cohen entre os dois anotadores, por estrato e no total.
3. Listar as divergências e levar a um terceiro integrante, que decide o rótulo
   final sem saber quem votou o quê.
4. Gravar a coluna de rótulo final e a origem de cada decisão.

**Saída.** Planilha consolidada e o valor do kappa.

**Critério de aceite.** O kappa está calculado e reportado, inclusive se for
baixo. Kappa baixo é resultado, e entra no artigo como limite, não vira motivo
para refazer a anotação até subir.

**Tamanho.** Cerca de três horas de anotação mais meio dia de consolidação.

---

## T5. Trabalhos relacionados e originalidade

**Por que existe.** É a pergunta 1 do parecer e está parada desde setembro.
Não depende de dado nenhum, então pode começar hoje.

**Entrada.** O arquivo [BIBLIOGRAFIA.md](../revisao-tcc-ii/BIBLIOGRAFIA.md) e
`docs/revisao-tcc-ii/referencias.bib`.

**Passos.** Montar uma tabela comparativa com uma linha por trabalho e estas
colunas: mecanismo de decisão dos agentes, origem dos dados, idioma, forma de
validação, métrica de alcance usada, e se o trabalho separa a mensagem original
da correção. A última coluna é a que sustenta a contribuição deste artigo.

**Saída.** A tabela e dois parágrafos de posicionamento.

**Critério de aceite.** Cada linha cita o trabalho pela referência, e a coluna de
separação entre mensagem e correção está preenchida com evidência do texto do
trabalho, não com suposição.

**Tamanho.** Cerca de dois dias.

---

## T6. Pacote de reprodução

**Por que existe.** É a pergunta 10 do parecer. O artigo afirma que um terceiro
reproduz as tabelas, então alguém de fora precisa tentar.

**Entrada.** O branch de T1, as saídas de T2 e a campanha no Drive.

**Passos.**

1. Marcar uma versão identificada do código.
2. Empacotar os dados com `runs.csv`, `runs_corrigido.csv`, os JSON de resultado
   e o manifesto de modelo e seeds.
3. Escrever o passo a passo que vai do pacote até cada tabela.
4. Entregar a um integrante que não participou de T2 e pedir que reproduza uma
   tabela do zero, cronometrando e anotando onde travou.

**Saída.** A versão marcada, o pacote e o relato da reprodução.

**Critério de aceite.** A pessoa de fora chegou ao mesmo número. Se não chegou, o
relato diz onde parou, e isso entra no artigo.

**Tamanho.** Cerca de dois dias.

---

## T7. Reescrita das seções do artigo

**Por que existe.** O trabalho entra como próxima versão do artigo do PC2, não
como artigo separado. A estrutura já existe; o que muda são seções específicas.

**Entrada.** O PDF do PC2, a tabela de mudanças por seção no
[README.md](README.md), e as saídas das demais tarefas conforme ficam prontas.

**Passos.** Começar pelas seções que não dependem de dado novo: 1, 5.2, 6.3,
6.4, 7.2 e o apêndice. Reescrever 7.1 e 7.3 conforme T2 entrega. Acrescentar as
duas seções novas de resultados com T2, T3 e T4. Fechar 2.2 com T5, e 7.4, 7.5 e
8 por último, porque dependem de tudo.

**Saída.** A próxima versão do artigo.

**Critério de aceite.** Nenhuma afirmação da seção de resultados sem a tabela que
a sustenta. Nenhum número no texto que não apareça em um CSV versionado. As
quatro perguntas do parecer que continuam abertas estão declaradas como abertas,
e não descritas como respondidas.

---

## O que este artigo não vai afirmar

Vale para todo mundo, e está detalhado no plano de análise. O artigo não ordena
topologias, não aponta uma intervenção mais eficaz, não estabelece limiar
brasileiro de céticos e não afirma validade populacional. Esses pontos
continuam abertos no parecer e vão para a seção de limites.
