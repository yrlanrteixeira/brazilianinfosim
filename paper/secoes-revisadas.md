# BrazilianInfoSim: seções revisadas do TCC

Texto de substituição para o artigo “Simulação de Sociedades com Agentes Baseados em LLM para Análise da Desinformação no Brasil”.

Esta revisão reorganiza a Introdução, separa Metodologia e Desenvolvimento e explicita métricas, hipóteses e limites dos resultados. Foi elaborada a partir do TCC.pdf fornecido e do código da main no commit eb57dbb, com as correções desta branch identificadas na Seção 4.5. A numeração reserva a Seção 2 para a revisão bibliográfica já existente. As referências citadas devem permanecer na bibliografia do artigo. Este documento contém os trechos de substituição; não reproduz capa, resumos, revisão bibliográfica, apêndice e referências do original.

# 1 INTRODUÇÃO

A circulação de conteúdos falsos ou enganosos constitui um problema de pesquisa que envolve o conteúdo das mensagens, as relações entre seus participantes e as decisões de retransmissão. A distinção entre informação incorreta e desinformação também exige considerar a intencionalidade de sua produção e disseminação (Wardle e Derakhshan, 2017). Neste trabalho, a designação desinformação identifica o tema e as alegações usadas nos cenários experimentais. Não se atribui intenção humana aos agentes computacionais, nem se pressupõe que toda mensagem gerada por eles seja falsa.

O estudo dessas dinâmicas demanda distinguir exposição, retransmissão, transformação textual e apoio à alegação inicial. Receber uma mensagem não implica aceitá-la, e publicar uma contestação não garante que todas as afirmações acrescentadas sejam corretas. Essa distinção é necessária tanto na interpretação de dados quanto na construção de métricas para ambientes simulados.

O BrazilianInfoSim foi desenvolvido para explorar essas questões em redes sintéticas com mensagens em português e perfis descritos por atributos comportamentais e referências brasileiras. A proposta integra um modelo baseado em agentes a um modelo de linguagem de grande escala, denominado LLM, que seleciona ações e pode produzir novos textos. A abordagem permite observar interações sob condições computacionais registradas, mas a plausibilidade da linguagem produzida não demonstra correspondência com o comportamento de pessoas reais (Törnberg et al., 2025).

## 1.1 Motivação

A motivação do estudo é construir um ambiente em que configurações de rede, perfis e intervenções possam ser examinados sem introduzir deliberadamente mensagens falsas em comunidades reais. O recorte brasileiro orienta a língua das interações, os temas das mensagens e os atributos utilizados para descrever os agentes. Pesquisas e relatórios discutidos na revisão bibliográfica ajudam a contextualizar esse recorte, mas não fornecem automaticamente as probabilidades necessárias para calibrar o simulador.

O interesse por mensagens encaminhadas entre contatos também motiva a representação de vizinhanças e nós de maior grau. Entretanto, as redes geradas são abstrações computacionais: uma topologia de mundo pequeno não constitui, por si só, uma reprodução de grupos de WhatsApp, assim como um nó de maior grau não equivale necessariamente a um influenciador real. Essa delimitação permite estudar mecanismos específicos sem atribuir representatividade populacional aos cenários.

## 1.2 Problema de pesquisa

O problema central consiste em investigar quais padrões de circulação e transformação de mensagens emergem de configurações controladas de redes sintéticas e agentes LLM, e quais limites precisam ser considerados ao medir os efeitos de intervenções nesses ambientes.

O programa de investigação é organizado pelas seguintes questões, cuja cobertura efetiva é apresentada na Seção 5.4:

- **QP1, estrutura de rede:** como alcance, tempo até patamares de exposição e persistência variam entre as topologias implementadas, consideradas as diferenças de conectividade e de composição dos cenários?
- **QP2, perfis:** como os perfis e a proporção de agentes céticos se relacionam com as decisões e a circulação observadas? Há evidência suficiente para identificar um limiar de contenção?
- **QP3, transformação textual:** quais alterações ocorrem durante a retransmissão e em que medida os registros permitem distinguir reformulação, contestação e mudança factual?
- **QP4, intervenções:** quais diferenças de alcance são observadas entre controles e condições com conversão de nós em verificadores ou remoção de hubs?
- **QP5, plausibilidade:** quais evidências seriam necessárias para comparar quantitativamente o simulador com modelos SIR/SEIR e com cascatas observadas no Brasil?

As questões delimitam a investigação, sem pressupor que todas tenham sido respondidas. O limiar de ceticismo, a comparação empiricamente calibrada com modelos epidemiológicos e a avaliação de limites de retransmissão permanecem além das conclusões sustentadas pelos resultados disponíveis.

## 1.3 Justificativa

A justificativa metodológica é combinar o controle das condições de uma simulação com a possibilidade de registrar transformações em linguagem natural. A integração de LLMs amplia o repertório textual disponível para os agentes, ao mesmo tempo que introduz dependência do modelo, do prompt e dos parâmetros de geração. Esses elementos precisam integrar a descrição experimental.

A contribuição do protótipo está na explicitação desse vínculo entre configuração, execução e evidência. Registrar a rede inicial, os perfis, as mensagens, as decisões e as condições de parada permite examinar por que um resultado foi produzido e quais interpretações permanecem abertas. Essa contribuição é distinta de demonstrar que os agentes reproduzem a população brasileira ou que uma intervenção seria eficaz em uma plataforma real.

O trabalho também se justifica pela necessidade de separar o funcionamento do software da validade de suas medidas. Um contador de mensagens pode estar correto em relação à lógica do programa e, ainda assim, ser inadequado para estimar exposição a uma alegação falsa. A inconsistência entre ação de refutação e sentido textual observada nas campanhas torna essa distinção parte central da avaliação.

## 1.4 Objetivos

### 1.4.1 Objetivo geral

Desenvolver e avaliar exploratoriamente um simulador de circulação de mensagens com agentes LLM e redes sintéticas contextualizadas no Brasil, documentando suas hipóteses, métricas e mecanismos, e delimitando as conclusões permitidas pelos experimentos realizados.

### 1.4.2 Objetivos específicos

1. Implementar perfis sintéticos com parâmetros explícitos e documentar como seus atributos participam das decisões, distinguindo descrições fornecidas ao LLM, regras probabilísticas e campos sem efeito operacional.
2. Gerar redes Erdős-Rényi, Barabási-Albert e Watts-Strogatz com parâmetros registrados, tratando-as como abstrações e considerando diferenças de conectividade na análise.
3. Desenvolver o motor de execução e o registro das condições experimentais, das decisões e das mensagens efetivamente publicadas e recebidas.
4. Definir operacionalmente alcance, tempo até patamares de exposição, extinção, alteração semântica e diferenças pareadas de alcance, explicitando denominadores, unidades, condições de cálculo e dados ausentes.
5. Descrever os resultados das campanhas disponíveis e comparar, nos blocos compatíveis, controles com conversão de nós existentes em verificadores e remoção de hubs.
6. Identificar limitações de mensuração, cobertura e validade, estabelecendo requisitos para revisão independente do conteúdo, análise de sensibilidade e futura comparação com dados empíricos e modelos epidemiológicos.

Os objetivos descrevem o escopo efetivamente desenvolvido e avaliado. A implementação de limites de retransmissão e a validação empírica nacional não são apresentadas como entregas concluídas.

## 1.5 Organização do trabalho

A Seção 2 apresenta a revisão bibliográfica. A Seção 3 define o desenho experimental, as variáveis, as hipóteses de simulação e as métricas. A Seção 4 descreve a arquitetura e o funcionamento do simulador. A Seção 5 apresenta os resultados históricos por campanha e discute seus limites. A Seção 6 sintetiza as conclusões e as etapas futuras.

# 3 METODOLOGIA

## 3.1 Natureza do estudo e unidade de análise

O trabalho combina desenvolvimento de software, experimentos em redes sintéticas e análise descritiva dos registros produzidos. A unidade de análise é uma execução completa do simulador, definida por configuração, rede, população, mensagem inicial e condições de geração do LLM. Mensagens e decisões de uma mesma execução são dependentes e não constituem réplicas independentes.

As duas campanhas históricas descritas na Seção 5 são analisadas separadamente. Elas diferem em modelo de linguagem, prompt, regras de atualização, horizonte e versão do código. Assim, diferenças entre seus resultados não identificam o efeito isolado da troca de modelo. A implementação auditada a partir da main é descrita na Seção 4; não se presume que essa versão reproduza a configuração histórica Qwen3.

## 3.2 Desenho experimental e variáveis

Na campanha Llama 3.1, um bloco reúne uma condição de referência e tratamentos associados a uma configuração comum de rede, população, mensagem e sementes. A comparação usa o controle do mesmo bloco. Para a comparação conjunta das três estratégias preventivas, utilizam-se os 38 blocos completos, evitando que estratégias sejam comparadas sobre conjuntos diferentes de controles.

As variáveis manipuladas ou estratificadas incluem topologia, mensagem inicial, estratégia de intervenção e momento de aplicação. Número de agentes, horizonte, parâmetros de geração da rede, composição dos perfis, prompt, temperatura e cache precisam ser informados como condições do experimento. O fato de um parâmetro ser configurável não significa que seu efeito tenha sido investigado.

Os desfechos são alcance, marcos temporais, condição de parada, ações produzidas e alterações textuais. A classificação da posição do texto em relação à alegação inicial constitui uma etapa distinta. As quantidades de chamadas, tentativas e recusas descrevem o processo computacional, sem aumentar o número de réplicas científicas.

Na campanha Qwen3, o relatório apresenta contrastes entre perfis de emissor, proporções nominais de céticos e condições de alteração ou encaminhamento textual. O lote concluído contém uma realização por condição e uma semente de geração do LLM. Sua função na análise é exploratória, sem inferência de efeitos populacionais ou de limiares estáveis.

## 3.3 Hipóteses de simulação e parametrização

Neste trabalho, **hipótese de simulação** designa uma escolha usada para construir o cenário; **hipótese de pesquisa** designa uma relação a investigar. Um valor definido pelos autores para permitir a execução não é uma estimativa observada na sociedade. Sem fonte, população de referência e procedimento de calibração documentados, os valores abaixo são tratados como hipóteses de projeto.

As hipóteses investigativas são: diferenças de estrutura e composição podem acompanhar diferenças de circulação; alterações de perfil ou remoção de nós podem modificar o alcance; e o rótulo da ação pode divergir da posição expressa no texto. As campanhas disponíveis oferecem evidência descritiva para examinar essas possibilidades, sem constituir testes confirmatórios de todas elas.

### 3.3.1 Composição e parâmetros dos agentes

A geração padrão atribui pesos de 25% a amplificadores, 40% a indiferentes, 20% a céticos, 10% a influenciadores e 5% a verificadores nativos. Esses pesos são probabilidades de sorteio de cada agente, e não quotas exatas em cada população nem estimativas de prevalência no Brasil. A escolha estabelece heterogeneidade no cenário. Não foi apresentada análise de sensibilidade suficiente para validar essa composição.

**Tabela 2. Parâmetros dos perfis que consultam o LLM. Cada célula apresenta média e desvio-padrão da normal usada no sorteio.**

| Perfil | Ceticismo (média; DP) | Propensão a compartilhar (média; DP) | Viés de confirmação (média; DP) |
| --- | --- | --- | --- |
| Amplificador | 0,15; 0,10 | 0,85; 0,10 | 0,75; 0,10 |
| Cético | 0,80; 0,10 | 0,30; 0,15 | 0,25; 0,10 |
| Influenciador | 0,40; 0,15 | 0,70; 0,15 | 0,55; 0,15 |
| Verificador nativo | 0,90; 0,05 | 0,60; 0,15 | 0,10; 0,05 |

Fonte: parâmetros da implementação auditada. Valores propostos para distinguir descrições comportamentais, sem calibração com respostas humanas.

Para cada dimensão, sorteia-se um valor normal e aplica-se o limite inferior 0 e superior 1. Trata-se de recorte por saturação: valores fora do intervalo são deslocados para a extremidade, sem novo sorteio. Portanto, as médias e os desvios indicados descrevem a normal antes desse recorte.

Os valores de ceticismo e propensão são convertidos em descrições qualitativas pelos limiares 0,4 e 0,7; o viés de confirmação usa 0,35 e 0,6. Esses pontos de corte são convenções do prompt. Não representam escalas psicométricas validadas, e a propensão a compartilhar não é usada diretamente como probabilidade de uma decisão do LLM.

Agentes indiferentes seguem outra hipótese operacional: a cada mensagem processada, encaminham o texto com probabilidade fixa de 0,10 e, caso contrário, não o retransmitem. Eles não consultam o LLM. Seus parâmetros comportamentais sorteados não participam dessa decisão e, por isso, não integram a Tabela 2. Caso um indiferente seja convertido em verificador, passa a utilizar o procedimento de decisão correspondente ao novo perfil.

O campo capital social não determina o grau dos nós nem participa da descrição enviada ao LLM na versão auditada. Por essa razão, foi retirado da tabela de parâmetros operacionais. Uma relação entre esse atributo, posição na rede e comportamento exigiria um mecanismo adicional e sua avaliação, ficando indicada como trabalho futuro.

### 3.3.2 Atributos contextuais

**Tabela 3. Atributos que compõem a descrição textual dos agentes que consultam o LLM.**

| Atributo | Configuração padrão | Participação e hipótese |
| --- | --- | --- |
| Região | Norte 8%; Nordeste 27%; Centro-Oeste 8%; Sudeste 42%; Sul 15% | O nome da região aparece no prompt. Pesos usados como hipótese contextual, sem calibração documentada. |
| Escolaridade | Fundamental 40%; médio 37%; superior 23% | A escolaridade integra a descrição textual. Não há regra direta que altere a retransmissão a partir desse atributo. |
| Faixa etária | 18 a 30, 31 a 50 e 51 anos ou mais, com sorteio uniforme | A faixa aparece no prompt. A distribuição uniforme é uma convenção da simulação. |
| Referência a WhatsApp | Probabilidade de 0,92 | Quando verdadeiro, acrescenta “Usa WhatsApp frequentemente.” ao prompt. Não cria grupos, encaminhamentos ou regras da plataforma. |

Fonte: implementação auditada. Os números são hipóteses de geração; não se atribui origem estatística validada a comentários presentes no código.

Esses atributos permanecem na descrição porque têm participação verificável no prompt. Essa participação não demonstra um efeito causal medido: as campanhas não isolaram o efeito de cada atributo. Nos agentes indiferentes que continuam usando a regra probabilística, tais descrições não são submetidas ao LLM.

### 3.3.3 Redes e intervenções

**Tabela 4. Hipóteses de geração das redes sintéticas.**

| Topologia | Parâmetros padrão | Interpretação no experimento |
| --- | --- | --- |
| Erdős-Rényi | Probabilidade de aresta p = 0,08 | Referência com conexão independente entre pares de nós. |
| Barabási-Albert | m = 3 arestas por novo nó | Cenário com crescimento por conexão preferencial. |
| Watts-Strogatz | k = 6 vizinhos iniciais; probabilidade de reconexão p = 0,15 | Cenário com vizinhanças locais e reconexão de arestas. |

Fonte: implementação auditada. Valores fixados para construir cenários distintos, sem ajuste a uma rede brasileira observada.

Os grafos são simples e não direcionados. Se o grafo gerado não for conexo, componentes são ligados por arestas adicionais sorteadas com semente registrada. Essa regra é outra hipótese do modelo e modifica o grafo originalmente amostrado. As redes com os parâmetros da Tabela 4 não têm necessariamente a mesma densidade ou grau médio. Portanto, uma comparação entre elas não separa automaticamente o efeito da topologia do efeito da conectividade.

**Tabela 5. Intervenções implementadas e população afetada.**

| Intervenção | Seleção | Efeito |
| --- | --- | --- |
| Verificadores em hubs | max(1, piso(N inicial / 10)) nós de maior grau | Converte perfis existentes; mantém nós e arestas. |
| Verificadores periféricos | max(1, piso(N inicial / 10)) nós de menor grau | Converte perfis existentes; mantém nós e arestas. |
| Remoção de hubs | Cinco nós de maior grau | Remove os agentes ativos selecionados, suas filas e as arestas incidentes. |

Fonte: implementação auditada. Com 50 agentes, cada intervenção seleciona cinco nós. Para outras populações, a remoção continua fixada em cinco nós e não equivale necessariamente a 10%.

A conversão fixa ceticismo em 0,90, propensão a compartilhar em 0,05 e viés de confirmação em 0,10, além de incluir a descrição do papel de verificador. Esses valores são hipóteses de tratamento e diferem dos parâmetros sorteados para verificadores nativos. A intervenção deve ser descrita como conversão de nós, sem atribuir a ela adição de agentes.

O momento t = 0 aplica a intervenção antes da primeira decisão, após a exposição inicial do emissor. Os momentos 1, 3 e 10 são alternativas de projeto para comparar atuação posterior; não representam atrasos de duração conhecida no mundo real. Nos resultados consolidados Llama, os tratamentos analisados foram preventivos. A existência de momentos tardios no planejamento não significa que tenham sido avaliados.

### 3.3.4 Horizonte, geração e sementes

Os lotes históricos utilizaram 50 agentes. O horizonte foi de 30 ticks no lote Llama e 12 ticks no lote Qwen. São escolhas de escala e de orçamento computacional, sem correspondência estabelecida entre um tick e minutos, horas ou dias de interação humana. O padrão de 100 ticks do executor principal é uma configuração do programa, distinta dos horizontes efetivamente usados nesses lotes.

O planejamento padrão de run_impact.py combina três topologias, quatro mensagens, vinte sementes de configuração e duas sementes de geração do LLM. Cada bloco possui um controle e doze tratamentos, totalizando 6.240 casos planejados. A configuração desse executor fixa Llama 3.1 8B, temperatura 0,3, cache desligado e ponto de injeção sorteado. Esses números definem a grade de uma campanha, sem garantir que ela seja concluída dentro do orçamento.

As sementes de rede, perfis, ordem de ativação e geração são registradas separadamente. O executor usa sequências numéricas distintas para esses componentes e uma semente fixa para ordenar os blocos. Tais números são convenções de reprodutibilidade, não parâmetros calibrados. Mesmo com sementes registradas, a reprodução do LLM depende do provedor, modelo e ambiente; por isso, respostas e condições de execução também precisam ser preservadas.

O limite de tempo da campanha é uma regra de parada computacional. Execuções interrompidas são identificadas como incompletas e não entram na análise como observações de alcance zero. A cobertura observada deve sempre acompanhar a descrição da grade planejada.

## 3.4 Definição operacional das métricas

Seja V₀ o conjunto inicial de agentes, N₀ seu tamanho e Vₜ o conjunto ainda ativo no instante de coleta t. As categorias de mensagem precisam ser indicadas antes do cálculo: texto inicial literal, linhagem operacional do boato, linhagem de refutação ou posição textual revisada. Elas não são intercambiáveis.

### 3.4.1 Alcance acumulado

Para uma categoria c, E_c(t) representa o conjunto de agentes que recebeu ao menos uma mensagem dessa categoria até t. O alcance acumulado é:

$$
A_c(t) = 100 \frac{|E_c(t)|}{N_0}
$$

Equação 1. Alcance em porcentagem da população inicial.

O recebimento aceito pelo motor caracteriza exposição, mesmo que a mensagem permaneça na fila ao término da execução. O agente é contado uma única vez por categoria. Exposições anteriores à remoção de nós continuam no numerador histórico, e o denominador N₀ permanece fixo.

Como medida complementar, o alcance entre agentes ativos é:

$$
A_c^{ativo}(t) = 100 \frac{|E_c(t) \cap V_t|}{|V_t|}
$$

Equação 2. Alcance sobre a população ainda ativa.

A Equação 2 deve ser identificada separadamente porque seu denominador muda com a remoção. Se não houver agentes ativos, a proporção é indefinida. Nas configurações admitidas pela versão auditada, a remoção de cinco nós mantém agentes na rede.

O alcance do texto inicial usa igualdade literal de conteúdo. Ele não inclui paráfrases nem mede automaticamente apoio à alegação. Os campos históricos final_reach_pct e final_correction_reach_pct representam as linhagens definidas pelo motor, e não uma classificação factual.

### 3.4.2 Tempo até patamares de exposição

A expressão velocidade de propagação é operacionalizada como tempo até alcançar um patamar, em ticks:

$$
T_{q,c} = \min \{t : A_c(t) \geq q\}, \quad q \in \{25,50,75\}
$$

Equação 3. Primeiro instante de coleta em que o alcance atinge q por cento.

Valores menores indicam chegada mais rápida ao patamar sob a mesma convenção temporal. Essa métrica não é uma taxa em agentes por unidade de tempo. Se o patamar não for atingido durante a observação, registra-se “não atingido”, representado por valor ausente no resultado, sem substituir por zero ou pelo horizonte final. O resultado deve identificar a categoria c usada no cálculo.

Na implementação, tick_to_25pct, tick_to_50pct e tick_to_75pct utilizam o alcance da linhagem operacional do boato. Um nome mais preciso no artigo é “tempo até 25%, 50% e 75% de exposição à linhagem”. Não se convertem esses tempos em velocidade de difusão na sociedade.

### 3.4.3 Extinção e persistência observada

Se Q(t) é o total de mensagens nas filas dos agentes ativos no instante de coleta, define-se:

$$
T_{ext} = \min \{t : Q(t)=0\}
$$

Equação 4. Instante observado de extinção da circulação.

A extinção depende de filas vazias, e não da estabilização do alcance. Quando há mensagens pendentes ao atingir o limite T máximo, o tempo de extinção é desconhecido e a observação é censurada à direita. Nesse caso, informa-se que a circulação permaneceu ativa até o horizonte; não se afirma que ela terminou nele. A remoção de um agente também elimina sua fila ativa, mas preserva a exposição histórica já ocorrida.

### 3.4.4 Diferença pareada de alcance

Para o bloco b e a estratégia j, o contraste é:

$$
\Delta A_{b,j} = A_{b,j}^{tratamento}(T) - A_b^{controle}(T)
$$

Equação 5. Diferença em pontos percentuais entre tratamento e controle compatíveis.

Valores negativos representam menor alcance no tratamento, zero representa empate e valores positivos representam maior alcance. Usa-se a mesma categoria, o mesmo denominador inicial e o mesmo horizonte planejado. Quando a circulação se extingue antes de T, o alcance final permanece acumulado. Tentativas interrompidas por falha ou orçamento não fornecem esse desfecho completo.

O termo “diferença pareada de alcance” substitui “taxa de contenção”, que poderia sugerir uma proporção de verificações bem-sucedidas ou uma taxa temporal. A síntese apresenta média, mediana e contagens de redução, empate e aumento. Controles compartilhados por tratamentos do mesmo bloco não são considerados observações independentes.

### 3.4.5 Índice de alteração semântica

Se K é o número de pares elegíveis de mensagem publicada e sua versão imediatamente anterior, e e_j e e_parent(j) são seus vetores de representação textual, define-se:

$$
M = \frac{1}{K}\sum_{j=1}^{K}\left[1-\frac{e_j\cdot e_{parent(j)}}{\|e_j\|\,\|e_{parent(j)}\|}\right]
$$

Equação 6. Distância média de cosseno entre versões consecutivas na cadeia de transmissão.

O índice é adimensional e tem intervalo teórico de 0 a 2 para vetores não nulos. A implementação usa o modelo paraphrase-multilingual-MiniLM-L12-v2 e um estabilizador de 10 elevado a menos 9 no denominador. Compara-se cada publicação à sua mensagem de origem imediata, não a uma ordem cronológica arbitrária entre textos.

O coletor atual inclui publicações textualmente alteradas cuja mensagem e predecessora pertencem à linhagem operacional do boato; ele exclui refutações e transições vindas de uma refutação. Portanto, o índice caracteriza esse subconjunto selecionado pela lógica do programa, sem abranger automaticamente todas as reformulações produzidas.

O relatório deve informar K e se o cálculo foi realizado. Sem pares elegíveis, a média da Equação 6 é indefinida; com cálculo desabilitado ou sem representação disponível, deve constar “não calculado”. O resumo persistido das campanhas desabilita o cálculo de embeddings. A rotina auxiliar possui retornos convencionais para situações sem pares ou sem a dependência, que não devem ser interpretados como estimativas científicas de M.

Uma contagem de alterações textuais não equivale ao índice M. Além disso, distância semântica não mede falsidade: uma correção pode alterar substancialmente o texto, enquanto uma pequena alteração pode mudar uma afirmação factual. Não foi produzida uma estimativa validada desse índice nos lotes apresentados.

### 3.4.6 Posição textual, estados internos e medidas futuras

A revisão por conteúdo classifica a posição de cada texto em relação à alegação inicial como apoio, rejeição, posição mista, conteúdo alheio, ambiguidade ou revisão pendente. A unidade de anotação é o par formado pela alegação inicial e pelo texto recebido. Cada revisão registra autoria e justificativa. A exatidão de afirmações adicionais exige avaliação própria, mesmo quando o texto rejeita a alegação central.

Para cada categoria revisada, aplica-se a Equação 1 aos recebimentos. Um agente pode ter recebido textos de posições diferentes; assim, os alcances das categorias podem se sobrepor. Casos pendentes ou ambíguos impedem a apresentação de um alcance completo por posição.

Se L_c é o conjunto de agentes com exposição já confirmada na categoria c e U é o conjunto exposto a textos pendentes ou ambíguos, apresentam-se:

$$
A_c^{inf} = 100\frac{|L_c|}{N_0}, \qquad A_c^{sup} = 100\frac{|L_c \cup U|}{N_0}
$$

Equação 7. Limites decorrentes de classificação incompleta.

Esses limites não são intervalos de confiança. Diferenças pareadas de apoio textual só são calculadas quando controle e tratamento possuem classificação completa. A nova instrumentação permite esse procedimento em execuções futuras, mas não reclassifica automaticamente as campanhas históricas.

O estado belief_level inicia em 0,5 e é atualizado por regras associadas às ações, com limites entre 0 e 1. A contagem de agentes acima de 0,5 é um diagnóstico operacional, sem validação como crença psicológica. Tampouco foi implementada e validada uma medida de reprodução efetiva para os resultados apresentados; essa medida permanece como possibilidade futura.

## 3.5 Procedimento de análise e validade

A análise começa pela identificação da campanha, versão do código, configuração e condição de encerramento. Resultados completos são separados de tentativas inválidas ou interrompidas. Em seguida, são descritas a cobertura das condições, a distribuição dos alcances, os marcos temporais disponíveis e a circulação ainda ativa no horizonte.

Contrastes utilizam controles compatíveis e identificam a quantidade de blocos analisados. A análise do conteúdo exige um protocolo de anotação e revisão independente antes de sustentar conclusões factuais. As revisões históricas do lote Qwen foram exploratórias e não incluíram medida de concordância entre revisores.

A verificação do software por testes controlados avalia se regras, registros e métricas obedecem aos contratos definidos. Ela não substitui calibração comportamental nem validação externa. Estas últimas exigiriam dados de referência, critérios comparativos e experimentos próprios, ainda não concluídos.

# 4 DESENVOLVIMENTO DO SIMULADOR

## 4.1 Organização da implementação

O protótipo é implementado em Python. A biblioteca Mesa organiza os agentes, sua ativação e a coleta de estados; NetworkX gera e manipula os grafos. A integração com o LLM é encapsulada em um cliente, enquanto a persistência mantém os resultados e suas configurações.

AgentProfile armazena os atributos do perfil e produz a descrição textual. InfoAgent mantém a caixa de entrada, o histórico e as mensagens publicadas. Message representa texto, origem, predecessor, remetente, número de saltos e linhagem operacional. SimulationConfig define uma execução; InfoSimModel constrói e executa o cenário; SimulationResult reúne os dados finais e a auditoria.

LLMClient prepara a solicitação, consulta o provedor configurado e interpreta a resposta. As rotinas de análise calculam resumos e gráficos; as de persistência gravam os dados; RunRecorder e ReplayModel permitem reproduzir visualmente estados já registrados. Esses componentes constituem a implementação do desenho definido na Seção 3.

## 4.2 Inicialização e ciclo de execução

A inicialização gera o grafo, sorteia os perfis e registra a estrutura inicial e o nó emissor. A mensagem inicial é inserida na fila desse agente. A coleta em t = 0 já contabiliza essa exposição, embora ainda não tenha ocorrido uma decisão de retransmissão.

Em cada rodada da versão auditada, aplica-se a intervenção prevista para o instante corrente e os agentes são ativados em ordem aleatória. Agentes com mensagens na fila processam as entradas disponíveis no início de sua ativação. Publicações são encaminhadas aos vizinhos existentes no grafo.

Esse procedimento permite que uma mensagem enviada alcance, na mesma rodada, um vizinho que ainda não tenha sido ativado. Um vizinho já ativado processará a mensagem em uma rodada posterior. Essa ordem faz parte da dinâmica da main e não deve ser descrita como atualização síncrona. A campanha histórica Qwen é documentada com dinâmica síncrona própria.

O motor avança o contador, registra os estados e verifica as condições de continuidade. A execução termina por ausência de mensagens pendentes ou pelo limite de ticks. O controle de orçamento pode interromper a execução; essa tentativa é registrada separadamente de um resultado completo.

## 4.3 Recebimento, deduplicação e ações

O recebimento é deduplicado por alegação de origem e linhagem operacional. Não se aceita uma nova mensagem dessa combinação se ela já foi recebida no tick ou permanece na fila. Variantes textuais da mesma linhagem competem por essa entrada. Em rodadas posteriores, a reexposição volta a ser admitida quando não houver entrada pendente equivalente. Essa regra reduz processamento duplicado e também limita quais variantes são efetivamente observadas pelos agentes.

Agentes indiferentes seguem a regra probabilística descrita na Seção 3.3. Os demais enviam ao LLM a descrição do perfil, a mensagem e até cinco interações recentes. O modelo seleciona uma das cinco ações:

- **IGNORAR:** não publica mensagem.
- **COMPARTILHAR:** retransmite o texto recebido, sem usar um novo texto proposto na resposta.
- **COMPARTILHAR_COM_COMENTARIO:** publica o conteúdo retornado; quando vazio, encaminha o texto recebido.
- **QUESTIONAR:** registra a decisão e altera o estado operacional, sem transmitir a mensagem.
- **REFUTAR:** publica o conteúdo retornado e alterna a linhagem operacional.

O número de saltos é incrementado a cada publicação retransmitida. Ele representa a posição na cadeia de encaminhamento, não o tick nem o número de indivíduos únicos alcançados.

A atualização do estado numérico usa incrementos de menos 0,10 para questionar, menos 0,20 para refutar, mais 0,15 para compartilhar e mais 0,10 para compartilhar com comentário, ao receber a linhagem do boato. O sinal é invertido para a linhagem de refutação. Ignorar ou receber uma recusa do provedor não altera o estado. Esses valores são hipóteses operacionais sem calibração psicológica.

A inversão de linhagem e do sinal do estado baseia-se na ação escolhida, sem examinar o sentido do texto. Por isso, mesmo uma resposta que mantém a negação da alegação pode retornar à linhagem denominada boato. A arquitetura preserva esse mecanismo histórico como regra explícita e trata a classificação textual em uma camada de análise separada.

## 4.4 Prompt, provedor e persistência

O prompt combina perfil, mensagem, histórico e instruções sobre as ações disponíveis. A orientação para que céticos e verificadores encaminhem refutações integra a condição experimental; não constitui uma descoberta sobre comportamento humano. O template deve ser identificado por versão, e o texto efetivamente enviado precisa acompanhar o registro da execução.

O cliente permite provedor local via Ollama e integração com a API Anthropic. Cache desligado é a configuração das campanhas científicas descritas para o executor de impacto. Reutilização exata ou semântica de respostas representa outra condição de execução e não deve ser misturada a amostragens sem cache.

A configuração registra sementes, provedor, modelo, temperatura e demais opções. A auditoria de decisões conserva solicitações ao provedor, respostas e falhas. Os resultados incluem estados coletados, estrutura inicial, perfis e alterações textuais. Um manifesto associa a execução ao código e às versões das dependências. A escrita atômica evita substituir um resultado completo por um arquivo parcialmente gravado.

Na implementação auditada, limites como cinco interações de histórico, até 300 tokens solicitados por resposta, até três tentativas de consulta e timeout padrão de 120 segundos são escolhas operacionais. O limiar 0,85 de aproximação dos rótulos de decisão e o limiar padrão 0,92 do cache semântico também são convenções de implementação. Este último não participa de campanhas com cache desligado. Esses valores não foram inferidos a partir de dados sociais.

## 4.5 Correções decorrentes da auditoria

A revisão do código acrescenta uma auditoria de mensagens efetivas, independente da auditoria de chamadas ao LLM. Cada evento identifica publicação ou recebimento aceito, agente, tick, texto, origem e linhagem. Assim, a medição por conteúdo inclui a exposição inicial, mensagens ainda enfileiradas e exposições anteriores à remoção de agentes. Propostas de texto descartadas por uma ação de compartilhamento literal não são confundidas com publicações.

O comando de revisão de conteúdo prepara um inventário para anotação e calcula alcances por agente único. Os resultados e as anotações recebem hashes para vincular a análise aos arquivos utilizados. Nenhuma chamada ao LLM é necessária nessa etapa. Resultados antigos sem auditoria de recebimentos não fornecem automaticamente essa informação: uma reconstrução exigiria reprodução validada com as respostas e o código históricos.

O executor principal passa a aceitar a opção --record e gera uma gravação distinta por execução. O replay atualiza o grafo de acordo com os agentes ativos de cada estado, preservando posições visuais e alcance histórico. Com isso, a remoção de hubs deixa de produzir referências a agentes ausentes.

Os executores por assunto e de experimentos suplementares passam a iniciar campanhas apenas quando executados explicitamente. Para novas campanhas de impacto, a fila completa os treze casos de cada bloco antes de avançar e coloca as réplicas de geração em sequência. Essa ordenação antecipa o exame de momentos tardios, com a contrapartida de concentrar o início em uma configuração de rede e mensagem. Ela não é aplicada retroativamente às campanhas históricas.

Os testes de regressão verificam esses contratos usando decisões controladas. As correções são melhorias de implementação e mensuração posteriores às campanhas relatadas; não representam novos resultados de eficácia das intervenções.

# 5 RESULTADOS E DISCUSSÃO

## 5.1 Configurações e cobertura observada

Os números desta seção são preservados do TCC.pdf e dos resultados nele consolidados. Não foram recalculados como uma nova campanha nesta revisão. A comparação mantém separados os lotes de oito horas de 23 de setembro e de 23 a 24 de setembro de 2026.

**Tabela 6. Configuração e cobertura das campanhas históricas.**

| Aspecto | Lote Llama 3.1 | Lote Qwen3 |
| --- | --- | --- |
| Modelo e dinâmica | Llama 3.1 8B; 30 ticks; dinâmica anterior | Qwen3 4B; contextual_v5; 12 ticks; dinâmica síncrona |
| Resultados completos | 154 execuções: 39 controles e 115 tratamentos | 11 execuções; uma tentativa interrompida |
| Comparações | 38 blocos completos com as três estratégias preventivas | Oito contrastes pareados |
| Rede e população | 50 agentes; três topologias; quatro mensagens nos controles | 50 agentes; três grafos Erdős-Rényi; uma semente de geração |
| Decisões válidas reportadas | 7.567: 4.062 compartilhar e 3.505 questionar | 6.794, com contestações e alterações textuais |

Fonte: TCC.pdf, resultados consolidados. As contagens de decisões não devem ser substituídas pela quantidade de tentativas de chamada ao provedor.

A campanha exploratória anterior de 330 execuções mencionada no documento original não é somada a esses lotes. Como sua configuração completa e seus dados brutos não fundamentam as comparações apresentadas nesta seção, seus números não são usados para ampliar a evidência das duas campanhas consolidadas.

## 5.2 Lote Llama 3.1

Nos 39 controles, o alcance médio foi de 25,64%, com mediana de 2%. Em 27 execuções, a mensagem permaneceu restrita ao emissor; em 12, alcançou outros agentes. Dez controles atingiram ao menos 74% da população e três atingiram 100%. A concentração entre ausência de propagação e grandes alcances exige interpretar a média em conjunto com a mediana e as contagens.

**Tabela 7. Alcance nos controles do lote Llama 3.1.**

| Topologia | Controles | Média | Mediana | Além do emissor |
| --- | --- | --- | --- | --- |
| Erdős-Rényi | 16 | 17,63% | 2% | 5 de 16 |
| Barabási-Albert | 16 | 19,75% | 2% | 3 de 16 |
| Watts-Strogatz | 7 | 57,43% | 96% | 4 de 7 |

Fonte: resultados reportados no TCC.pdf. Comparação descritiva, sem isolamento do efeito da topologia.

Os grupos diferiam em conectividade, emissores e cobertura de textos. O maior alcance observado em Watts-Strogatz nesse recorte não permite atribuir o resultado exclusivamente à estrutura da rede.

As doze propagações além do emissor ocorreram em controles com emissor amplificador. Nas primeiras decisões diante do boato, amplificadores compartilharam em 139 de 147 casos, céticos questionaram em 86 de 86 e verificadores questionaram em 39 de 39. Essas frequências descrevem o LLM condicionado pelos perfis e pelo prompt utilizados. Elas não estimam probabilidades de comportamento de brasileiros.

Nos 38 blocos completos, as três estratégias foram aplicadas preventivamente em t = 0.

**Tabela 8. Diferença pareada de alcance, em pontos percentuais, calculada como tratamento menos controle.**

| Intervenção | Média | Mediana | Redução / empate / aumento |
| --- | --- | --- | --- |
| Verificadores nos hubs | -13,79 | 0 | 8 / 30 / 0 |
| Remoção de hubs | -12,26 | 0 | 11 / 27 / 0 |
| Verificadores periféricos | -3,84 | 0 | 3 / 34 / 1 |

Fonte: resultados reportados no TCC.pdf, com 38 blocos comuns às três estratégias.

A mediana foi zero em todas as estratégias. As diferenças descritivas não sustentam uma intervenção vencedora geral. Os agentes convertidos em verificadores questionaram as mensagens, sem publicar correções; assim, os efeitos observados se relacionam à interrupção de encaminhamentos e, na remoção, à alteração da rede. Não se deve descrevê-los como sucesso comprovado da difusão de checagens.

Oito controles permaneceram com mensagens pendentes ao atingir 30 ticks. Nesses casos, a extinção não foi observada e o horizonte representa censura da duração. Não houve mutação textual nem circulação de correções no lote, de modo que ele não permite avaliar os efeitos desses mecanismos sobre alcance e persistência.

## 5.3 Lote Qwen3

Nos onze resultados completos, o emissor refutou a alegação inicial na primeira decisão. O texto original permaneceu restrito ao emissor, correspondendo a 1 de 50 agentes, ou 2%. Esse resultado se refere à igualdade literal do texto. As contestações circularam amplamente, mas parte delas foi alternada para a linhagem operacional do boato quando o LLM escolheu REFUTAR diante de outra contestação.

**Tabela 9. Alcances e contagem operacional de alterações no lote Qwen3.**

| Condição | Texto inicial literal | Linhagem do boato | Linhagem da contestação | Alterações |
| --- | --- | --- | --- | --- |
| Emissor amplificador | 2% | 100% | 100% | 142 |
| Emissor verificador | 2% | 98% | 100% | 80 |
| Emissor influenciador | 2% | 2% | 100% | 0 |
| Emissor indiferente | 2% | 100% | 100% | 166 |
| Emissor cético | 2% | 100% | 100% | 59 |
| Céticos: 0% nominal | 2% | 2% | 100% | 0 |
| Céticos: 20% nominal | 2% | 2% | 100% | 0 |
| Céticos: 40% nominal | 2% | 90% | 90% | 45 |
| Céticos: 60% nominal | 2% | 90% | 90% | 44 |
| Alteração permitida | 2% | 2% | 100% | 0 |
| Encaminhamento literal | 2% | 98% | 98% | 0 |

Fonte: resultados reportados no TCC.pdf. Linhagens e alterações são diagnósticos do mecanismo, sem classificação factual completa.

O contador totalizou 536 alterações em mensagens da linhagem operacional do boato. Esse número não é o índice de alteração semântica da Equação 6 nem uma contagem validada de novas falsidades. Também não inclui todas as mudanças nas contestações.

As proporções nominais de céticos foram aplicadas aos 49 agentes não emissores. As proporções realizadas sobre a população de 50 agentes foram 0%, 20%, 40% e 58%. A existência de uma realização por condição impede identificar um limiar estável a partir dessa sequência.

Todas as onze execuções permaneceram ativas ao atingir 12 ticks. Foram registradas 7.155 tentativas de chamada, das quais 6.802 pertenciam às execuções completas e 353 à tentativa interrompida. Após recuperação de falhas, 6.794 respostas válidas produziram decisões. Tentativas, respostas e execuções são contagens diferentes.

A revisão exploratória examinou 46 respostas REFUTAR, correspondentes a 36 textos distintos; 29 respostas ocorreram após uma mensagem já classificada operacionalmente como contestação. A revisão identificou manutenção da negação central, sem validar todas as afirmações acrescentadas. O registro complementar de auditoria informa que as anotações foram produzidas por IA, sem validação humana independente. Não foi medida concordância entre revisores.

O documento original também relata um detalhe adicional, em uma contestação sobre benefício social, que não era sustentado pela fonte consultada naquela análise. A observação indica a necessidade de avaliar separadamente a posição central e os detalhes factuais de uma correção. Não demonstra um limiar geral de contenção nem substitui uma avaliação completa dos textos recebidos.

## 5.4 Cobertura das questões de pesquisa

**Tabela 10. Situação das questões diante da evidência disponível.**

| Questão | Situação | Evidência e limite |
| --- | --- | --- |
| QP1: estrutura, alcance e tempo | Parcial | Há diferenças descritivas entre cenários. Conectividade, textos e emissores não foram completamente isolados. |
| QP2: perfis e ceticismo | Parcial | Há decisões distintas no lote Llama e contrastes exploratórios no Qwen. Não foi estabelecido limiar de ceticismo. |
| QP3: transformação textual | Parcial | O lote Qwen apresentou reformulações e divergência entre ação e sentido. Não foi estimado efeito causal da mutação sobre alcance ou duração. |
| QP4: intervenções | Parcial | Há diferenças preventivas pareadas, com mediana zero. Intervenções tardias e limites de retransmissão não foram avaliados nos resultados consolidados. |
| QP5: plausibilidade | Não respondida empiricamente | Não houve calibração nacional nem comparação quantitativa validada com cascatas brasileiras e modelos SIR/SEIR. |

Fonte: síntese dos resultados e de sua cobertura experimental.

## 5.5 Limitações e ameaças à validade

Os resultados dependem do modelo, prompt, mensagens, regras de transmissão, parâmetros e grafos utilizados. A mudança simultânea de vários componentes entre campanhas impede identificar a causa isolada de suas diferenças. A seleção de casos concluídos dentro de um orçamento também condiciona a cobertura; uma grade planejada não equivale a um experimento integralmente realizado.

A validade de construção é limitada pela diferença entre exposição, posição textual e estado numérico do agente. A linhagem não certifica veracidade, e o estado derivado das ações não foi validado como crença humana. A nova auditoria de recebimentos reduz uma lacuna de mensuração, mas depende de anotações adequadas e não resolve, por si só, a validação do conteúdo.

A validade externa é limitada pela ausência de calibração comportamental e de redes observadas. Os atributos brasileiros são escolhas de contextualização. O simulador não representa integralmente recomendação algorítmica, grupos fechados, circulação entre plataformas ou formação de nichos. Nenhum desses mecanismos deve ser inferido apenas da escolha de uma topologia.

As trajetórias SEIR teóricas exploratórias mencionadas no material original não constituem réplicas LLM nem uma validação empírica do protótipo. Comparações futuras precisam definir variáveis equivalentes, procedimento de ajuste e critérios de avaliação antes de sustentar correspondência entre modelos.

# 6 CONSIDERAÇÕES FINAIS

O BrazilianInfoSim permite executar e registrar cenários de circulação de mensagens com agentes LLM em redes sintéticas. A contribuição demonstrada é a construção de um ambiente exploratório e a identificação dos cuidados necessários para interpretar seus resultados, incluindo a separação entre regra operacional, conteúdo textual e afirmação factual.

No lote Llama 3.1, a maioria dos controles não ultrapassou o emissor, enquanto uma parcela alcançou grande parte da rede. As intervenções preventivas produziram diferenças em alguns blocos, mas tiveram mediana de efeito zero e não estabeleceram uma estratégia vencedora geral. Os verificadores questionaram mensagens, sem difundir correções.

No lote Qwen3, o texto inicial literal não foi retransmitido e contestações circularam. A alternância de linhagem revelou que um contador interno pode registrar alto alcance do boato sem demonstrar apoio textual à alegação inicial. Esse resultado motivou a separação da medição por conteúdo, com auditoria de recebimentos e explicitação de classificações pendentes.

As correções de implementação e os testes de regressão melhoram a verificabilidade do simulador, mas não acrescentam réplicas às campanhas históricas. As conclusões permanecem condicionadas às configurações observadas e não são generalizadas para o comportamento da sociedade brasileira.

Os próximos estudos devem priorizar revisão independente dos textos, avaliação das afirmações adicionais, maior cobertura de blocos e réplicas, análise de sensibilidade dos parâmetros e comparação de redes com conectividade controlada. A avaliação de limites de retransmissão e de intervenções tardias depende de experimentos específicos.

Capital social só deverá integrar tabelas de mecanismos efetivos após ser conectado a uma regra operacional e avaliado. Sua possível relação com grau, exposição ou decisão constitui trabalho futuro. Também permanecem futuras a validação dos perfis com respostas humanas, a calibração com dados brasileiros e a comparação quantitativa com modelos SIR/SEIR. Até então, o trabalho deve ser apresentado como simulação de agentes contextualizada no Brasil, com evidência exploratória e limites de validade explicitados.
