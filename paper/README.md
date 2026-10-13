# Revisão do TCC

[secoes-revisadas.md](secoes-revisadas.md) contém a redação pronta para substituir
Introdução, Metodologia, Desenvolvimento, Resultados e Considerações Finais.
O PDF de conferência é gerado em `output/pdf/TCC-secoes-revisadas.pdf`.
O fonte institucional do artigo não estava disponível; o TCC.pdf original foi
preservado. Este material não substitui capa, resumos, revisão bibliográfica,
apêndice ou referências.

## Integração ao artigo

| Estrutura anterior | Estrutura revisada |
| --- | --- |
| 1 Introdução; 3 Motivação; 4 Problema de Pesquisa; 5 Objetivos | 1 Introdução, com Motivação, Problema, Justificativa, Objetivos e Organização |
| 2 Revisão Bibliográfica | 2 Revisão Bibliográfica |
| 6 Metodologia, incluindo arquitetura e fluxo | 3 Metodologia e 4 Desenvolvimento do Simulador |
| 7 Resultados e Discussão | 5 Resultados e Discussão |
| 8 Considerações Finais | 6 Considerações Finais |

A revisão atende à hierarquia da Introdução solicitada no parecer. Não foi
certificada conformidade integral com um regulamento institucional completo.
O texto preserva as questões de pesquisa e indica quais continuam sem resposta;
os objetivos foram delimitados às entregas e avaliações realizadas.

Na revisão bibliográfica mantida, ajuste a remissão da página 6 do PDF à
“validação multinível na Seção 6.4”: o procedimento e seus limites estão agora
na Seção 3.5; a validação empírica permanece pendente. Substitua a frase por:

> A Seção 3.5 distingue a verificação do software da calibração comportamental
> e da validação externa. As duas últimas não foram concluídas nas campanhas
> apresentadas.

A Tabela 1 da revisão bibliográfica permanece com sua numeração. As Tabelas
2 a 10 são substituídas pelas novas versões. Use referências automáticas no
fonte institucional. O template de prompt do apêndice deve continuar identificado
como pertencente à versão de código correspondente, sem atribuí-lo ao lote
Qwen `contextual_v5` sem comprovação nos registros históricos.

As citações Wardle e Derakhshan (2017) e Törnberg et al. (2025) foram mantidas
a partir do documento fornecido. Esta revisão não refaz a verificação de toda
a bibliografia. A revisão da literatura e os resumos precisam permanecer
coerentes com o escopo delimitado e não afirmar calibração brasileira concluída.

## Correspondência com o código

| Ponto do parecer | Aplicação |
| --- | --- |
| Introdução deve conter os elementos iniciais | Seções 1.1 a 1.5, incluindo Justificativa |
| Definir velocidade e outras métricas | Seção 3.4, Equações 1 a 7, unidades e casos ausentes |
| Separar método e construção do software | Desenho e hipóteses na Seção 3; arquitetura e fluxo na Seção 4 |
| Declarar valores escolhidos para simulação | Seção 3.3 e convenções operacionais na Seção 4 |
| Retirar atributos sem efeito das tabelas | Capital social retirado; parâmetros inativos dos indiferentes excluídos |
| Não confundir ação com sentido ou verdade | Auditoria de mensagens e revisão por conteúdo; limites dos resultados nas Seções 3.4 e 5 |

O campo de WhatsApp permanece na tabela contextual porque altera o prompt
dos agentes que consultam o LLM. Seu efeito isolado não foi medido. O estado
numérico de crença permanece descrito como regra operacional. A alternância
histórica de linhagem não foi convertida em um classificador sem validação.

## Proveniência

- Documento de origem: `../TCC.pdf`, 23 páginas, fornecido pelo usuário.
- Base de implementação: `origin/main`, commit `eb57dbb0e583c252799a2acccc3498a6f9a72f30`.
- Os números das campanhas foram transcritos das páginas 14 a 19 do PDF,
  sem executar novamente experimentos com LLM e sem juntar os lotes.
- O registro local `docs/revisao-tcc-ii/ajustes-20260924/AJUSTES.md`, na
  pasta original do projeto, explicita que as revisões prévias de conteúdo
  foram realizadas por IA, sem validação humana independente. Essa informação
  foi incorporada à Seção 5.3.
- A Seção 4.5 descreve as melhorias desta revisão, posteriores aos resultados.
- Mudanças no código e na fila exigem nova campanha; os registros antigos não
  são regravados nem transformados em novas amostras.

## Gerar o PDF de conferência

```bash
python -m pip install -r paper/requirements.txt
python paper/build_pdf.py
```

O PDF usa diagramação própria para revisão e equações renderizadas a partir
do Markdown. A aplicação ao template institucional depende do fonte original.

## Verificação da entrega

- 184 testes passaram em Python 3.14.3, com provedores controlados e sem
  chamadas reais a LLM.
- Os novos testes incluem inversão de linhagem sem mudança de posição textual,
  recebimentos deduplicados, exposição anterior à remoção, anotações pendentes,
  proteção do texto anotado, pareamento, gravação pelo CLI e replay após remoção.
- A simulação de planejamento confirmou 6.240 casos sem iniciar a campanha.
- A compilação dos módulos e a verificação de whitespace passaram.
- O workflow de CI foi incluído e seu YAML foi validado localmente; a execução
  remota depende da publicação da branch.
- O PDF de 21 páginas foi renderizado e inspecionado. As sete equações e
  as nove tabelas de substituição foram conferidas.
- SHA-256 do TCC.pdf de origem:
  `d9ea69d8200501cf8a173754913147ea9437f08650132f9e79e06573bb3aa90d`.

Os testes demonstram contratos do software. Nenhuma nova campanha científica
foi realizada nesta revisão.
