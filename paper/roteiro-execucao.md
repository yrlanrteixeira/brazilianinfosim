# Execução para concluir QP1 a QP5

Ponto de controle informado pelo autor: **8 de novembro de 2026**.
Os experimentos principais serão executados pelo autor na semana seguinte à
preparação, de **19 a 25 de outubro**. O piloto curto já realizado serve para
verificar o fluxo e medir custo; está excluído da campanha principal.

## Entregas até o ponto de controle

| Período | Trabalho | Critério de verificação |
| --- | --- | --- |
| Até 18/10 | Congelar desenho, modelo e código | Testes passando, grade conferida e commit registrado |
| 19 a 25/10 | Executar a campanha por sessões | Blocos completos, auditoria de falhas e retomada, dados brutos preservados |
| 26/10 a 01/11 | Revisar textos e analisar resultados | Anotações com autoria, contrastes pareados, sensibilidade e comparação externa |
| 02 a 07/11 | Integrar respostas às cinco questões | Cada conclusão vinculada a tabela, medida, amostra e limite; PDF conferido |
| 08/11 | Ponto de controle | Texto, código, dados, tabelas e pendências claramente identificados |

O protocolo científico está em [protocolo-conclusao.md](protocolo-conclusao.md).
A grade padrão tem **2.112 casos**, não 2.112 sementes independentes: são
12 sementes de cenário, quatro redações de duas alegações, duas sementes de
LLM e 22 condições por bloco. Ela ainda não foi executada.

O piloto consumiu 256,7 segundos para quatro casos pequenos e 16 chamadas.
A configuração principal usa mais agentes e rodadas, podendo exigir vários
dias. O piloto não permite prometer um tempo de conclusão. Antes de iniciar,
confira a disponibilidade do computador; uma eventual mudança de tamanho ou
grade deve ser registrada antes da coleta principal. Reduzir o tamanho não
produz automaticamente a mesma evidência.

## Ambiente e planejamento, sem executar experimentos

Abra PowerShell na pasta desta branch, `brazilianinfosim-tcc-auditoria`.
No ambiente atual, o interpretador está na pasta irmã do projeto:

```powershell
$taskPython = '../brazilianinfosim/venv/Scripts/python.exe'
$taskCampaign = 'data/outputs/tcc2/conclusao-20261019'
& $taskPython -m pytest -q
& $taskPython run_research.py --output $taskCampaign --dry-run
ollama list
```

O modelo previsto é `qwen3:4b-instruct-2507-q4_K_M`, já instalado na máquina
usada na preparação. A execução exige o Ollama ativo: abra o aplicativo Ollama
ou execute `ollama serve` em um terminal separado. Se usar outra máquina,
instale `requirements.txt` em um ambiente próprio e ajuste apenas o caminho do
interpretador. O digest e a versão do servidor são registrados no início.

## Executar e retomar

```powershell
& $taskPython run_research.py --output $taskCampaign --hours 6
```

Seis horas são o orçamento dessa sessão, não uma previsão de término. Para
continuar em outra sessão, com o mesmo código, modelo e desenho:

```powershell
& $taskPython run_research.py --output $taskCampaign --hours 6 --resume --retry-incomplete
```

As execuções completas não são repetidas. Falhas e interrupções são retentadas
somente com `--retry-incomplete`; a tentativa anterior fica em `attempt_history`.
Cada sessão tem registro próprio em `budget_sessions`. O arquivo `status.json`
mostra casos tentados, sucessos, falhas, interrupções e blocos completos.
Só considerar a grade concluída com `status: completed`, 2.112 sucessos e
96 blocos completos. Conferir também o histórico de falhas antes da inferência.

Não altere código, modelo, corpus ou parâmetros durante essa campanha. O
manifesto rejeita misturas ao retomar, e `source_snapshot.zip` preserva os bytes
do código no início. O comando de impacto histórico mantém sua regra anterior
de orçamento; a renovação por sessão descrita aqui é a do `run_research.py`.

## Revisão e análise de conteúdo

```powershell
& $taskPython paper/analyze_completion.py $taskCampaign --output "$taskCampaign/review"
```

O comando gera `review_template.json`, `content_runs.csv`,
`decisions_by_profile.csv`, `paired_effects.csv`, `containment.csv` e
`analysis.json`. Copie o template para um arquivo de anotações e revise os
textos com o protocolo. As categorias são `supports`, `rejects`, `mixed`,
`unrelated`, `ambiguous` e `pending`; cada anotação precisa de autor e
justificativa. O texto e seu hash não devem ser modificados.

Classifique a posição perante a alegação inicial. Verifique separadamente
novas afirmações factuais e suas fontes. O exemplo de anotação do piloto
é revisão por IA, não padrão de validação humana. Para medir concordância,
dois revisores devem anotar separadamente antes da adjudicação; não atribua
validação humana a uma segunda execução automática do mesmo classificador.

```powershell
& $taskPython paper/analyze_completion.py $taskCampaign --output "$taskCampaign/review" --annotations "$taskCampaign/annotations.json"
```

Alcances por posição permanecem ausentes enquanto a classificação necessária
estiver incompleta. Os tempos até patamares não atingidos também ficam ausentes.
O limiar de ceticismo só é avaliado com a grade da família completa e revisada;
não identificar um limiar dentro da grade é um resultado possível.

Para distância semântica, use o snapshot local já disponível:

```powershell
$taskEmbedding = "$env:USERPROFILE/.cache/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
& $taskPython paper/measure_semantic_change.py $taskCampaign --model-path $taskEmbedding --output "$taskCampaign/review/semantic.json"
```

O cálculo é local, na CPU, e não baixa outro modelo. Ele mede distância textual
no espaço de embeddings, incluindo contestações; não mede veracidade.

## Comparação externa

Os metadados brasileiros já foram obtidos e seus hashes estão no manifesto
versionado em `paper/evidence/external-source-manifest.json`. Para reproduzir
a obtenção em outra máquina, sem baixar as imagens:

```powershell
& $taskPython paper/fetch_reference_data.py --output data/outputs/tcc2/external/metadata --member icwsm_dataset_share/brazil/misinfo_anonymized.txt --member icwsm_dataset_share/brazil/README.txt
```

Depois da campanha e da revisão:

```powershell
& $taskPython paper/benchmark_external.py data/outputs/tcc2/external/metadata/misinfo_anonymized.txt --campaign $taskCampaign --annotations "$taskCampaign/annotations.json" --output "$taskCampaign/benchmark" --agents 50 --ticks 12
```

O relatório preserva os clusters de ajuste e avaliação, os parâmetros escolhidos,
as distâncias e a quantidade de observações elegíveis. Exclui pilotos e condições
com população ou horizonte incompatíveis. Não converte publicações em leitores
nem ticks em horas. Se o LLM não produzir publicações de apoio suficientes,
o resultado deve explicitar essa ausência, sem apresentar distância nula.

## Fechamento do texto

Para cada QP, escrever: contraste realizado, número de blocos completos,
resultado com magnitude e incerteza, interpretação e limite. Conservar
resultados nulos e contraditórios. Substituir o estado provisório da campanha
complementar somente depois de analisar os dados.

A Tabela 10 do texto continua descrevendo a cobertura dos lotes históricos.
Ela não é uma lista de funcionalidades que faltam implementar. As novas
respostas devem integrar uma seção própria da campanha complementar.
O PDF de conferência é gerado com `python paper/build_pdf.py`; a integração
ao template institucional depende do fonte editável original do artigo.
