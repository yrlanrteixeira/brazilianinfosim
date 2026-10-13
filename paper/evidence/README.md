# Evidências da preparação

- `completion-pilot/`: configurações, tentativas, resultados brutos e análises
  das quatro simulações curtas. O piloto é diagnóstico e antecede o congelamento
  final do executor; não deve ser retomado ou agregado à campanha principal.
- `completion-pilot-annotations.json`: onze textos revisados por IA, com
  justificativa, fonte e identificação da ausência de validação humana.
- `external-source-manifest.json`: URL, versão, CRC e hashes dos metadados
  brasileiros obtidos do Zenodo. As imagens e os registros de usuários não são
  redistribuídos neste diretório.
- `external-benchmark.json`: separação dos 135 clusters, grade de calibração,
  parâmetros, distâncias e contagens de elegibilidade das referências SIR/SEIR.
  O componente LLM informa explicitamente a exclusão do piloto.

Os hashes de resultados vinculam as análises aos arquivos brutos. O manifesto
do piloto conserva o hash do código usado durante seu desenvolvimento; o
arquivo automático de código `source_snapshot.zip` foi acrescentado ao executor
depois do piloto e estará presente nas novas campanhas. A análise dos registros
do piloto pode ser reproduzida com os scripts em `paper/` e a anotação fornecida.

As respostas do LLM são dados do experimento, incluindo textos incorretos.
Nenhum desses arquivos comprova representatividade dos perfis brasileiros.
