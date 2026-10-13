# Protocolo para concluir as questões de pesquisa

Registro anterior à nova campanha. As campanhas históricas permanecem separadas.
A classificação de uma questão só muda após a produção e análise da evidência
correspondente. Resultado nulo ou contrário à hipótese também é uma resposta.

## Escopo e hipóteses de projeto

O objeto é o comportamento do BrazilianInfoSim, condicionado ao modelo local,
ao prompt e às redes sintéticas. Nenhuma proporção de perfil representa uma
estimativa da população brasileira. O prompt da main será preservado nesta
campanha para estudar o sistema auditado. O Qwen local será usado no piloto
por caber na memória da GPU; essa escolha antecede a observação dos efeitos.

As rodadas experimentais são síncronas: mensagens recebidas durante uma rodada
só podem ser processadas na seguinte. O denominador de alcance é sempre a
população inicial, incluindo exposições anteriores à remoção de nós.
Perfis indiferentes também consultam o LLM na nova campanha. Essa condição
é explícita e seus resultados não são agregados aos lotes históricos.

São hipóteses de simulação: grau médio quatro, rede inicialmente conexa,
temperatura 0,3, histórico de cinco interações, limite de dois destinatários,
intervenções antes das rodadas zero e dois, níveis nominais de ceticismo
0%, 20%, 40%, 60%, 80% e 100% dos agentes exceto o emissor. Registrar também
as contagens e proporções efetivas após arredondamento. O emissor inicial
é escolhido uniformemente, com perfil amplificador na referência.

A grade padrão preparada após o piloto prevê 50 agentes, 12 rodadas, doze
sementes de cenário e duas réplicas de LLM por redação. Cada bloco tem 22
condições, incluindo horizonte duplo, totalizando 2.112 casos. O piloto não
integra estimativas da campanha principal. O autor executará os experimentos
na semana de 19 a 25 de outubro, para o ponto de controle de 8 de novembro.
O orçamento é definido por sessão e registrado. Não se interrompe a coleta
por significância ou direção do efeito. Mudanças de grade anteriores à coleta
devem ser registradas; não se misturam desenhos dentro da mesma campanha.

## Critérios por questão

| Questão | Comparação necessária | Evidência para a resposta |
| --- | --- | --- |
| QP1 | Três famílias de grafos com os mesmos N, número de arestas, mensagem, perfis, emissor e sementes de LLM | Alcance por conteúdo, curvas de exposição, T25/T50/T75, incidência por rodada e persistência; distribuição das propriedades dos grafos e contrastes pareados |
| QP2 | Cinco perfis do emissor e seis níveis de ceticismo, em subconjuntos aninhados | Distribuição de ações por perfil; curva de alcance e probabilidade de contenção; limiar operacional com incerteza ou ausência de limiar identificável |
| QP3 | Mesma condição com mutação habilitada e suprimida, preservando encaminhamento | Diferenças de alcance e persistência; inventário de reformulações e contestações; distância textual/semântica e revisão factual separadas |
| QP4 | Controle e quatro intervenções nos dois momentos | Contrastes pareados; aplicação efetiva e intenção de tratar; preservar como zero efeito casos extintos antes da intervenção |
| QP5 | Simulador, referências SIR/SEIR e registros brasileiros públicos | Comparação quantitativa de observáveis compatíveis; separar calibração e avaliação; informar divergências e limites de generalização |

Normalizar o número de arestas modifica os grafos originais. Relatar “grafos
derivados de Erdős–Rényi, Barabási–Albert e Watts–Strogatz com densidade
controlada”. Registrar quantas arestas existiam antes da normalização.
Distribuição de graus e agrupamento permanecem propriedades das famílias,
não confundidores que se alegue ter eliminado.

## Medição e análise

Unidade experimental: cenário identificado por rede, perfis, estímulo e semente
de LLM. Agentes, mensagens e rodadas não são repetições independentes.
Comparações preservam as sementes dentro de cada bloco. Compartilhar o mesmo
controle entre contrastes não cria novos controles independentes.

O alcance principal usa a posição do texto perante a alegação inicial:
apoio, contestação, misto e não relacionado. Ação REFUTAR e prefixos não são
classificadores. Texto original literal é uma medida secundária verificável.
Anotações por IA serão identificadas como tal; validação humana independente
deve registrar autoria, divergências e adjudicação antes de alegar confiabilidade
humana. Ausências e ambiguidades geram limites, não estimativas inventadas.

Tempo até 50% é ausente quando o patamar não é atingido; não substituir por
zero. Persistência é censurada no horizonte se ainda há mensagens pendentes.
Comparar também tempo restrito de atividade no mesmo horizonte, deixando claro
que ele não estima o tempo de extinção além da janela observada.

Contenção operacional significa alcance de apoio à alegação de no máximo 10%
da população inicial. O limiar exploratório é o menor nível de ceticismo em
que pelo menos 80% dos cenários atendem a essa condição e os níveis superiores
também a atendem. Ambos os cortes são convenções do estudo. Reportar contagens,
intervalos e todos os níveis; uma grade finita não identifica um ponto crítico
universal. Verificar a sensibilidade a cortes de alcance de 5% e 20%.

Reportar média, mediana, diferenças pareadas e intervalos por reamostragem de
sementes de cenário, mantendo juntas mensagens e réplicas de LLM da mesma
semente. Sem sementes suficientes, reportar apenas descrição. Não usar número
de mensagens como tamanho amostral. Contrastes múltiplos são exploratórios;
não converter intervalos individuais em alegação de significância global.

## Referência externa e rastreabilidade

Candidato público: Reis et al. (2020), *A Dataset of Fact-Checked Images Shared
on WhatsApp During the Brazilian and Indian Elections*, versão 3:
https://doi.org/10.5281/zenodo.3779157.

Os registros contêm publicações de imagens, remetentes e grupos anonimizados,
e horários. Não contêm leitores nem caminhos completos de encaminhamento.
Comparar publicadores únicos, tamanho observado e forma temporal normalizada;
não comparar percentuais de leitores ou chamar a similaridade de calibração
da população brasileira. Imagens políticas e textos sintéticos têm diferenças
de conteúdo e período que limitam a validade externa. Uma divergência medida
é evidência relevante para QP5.

Guardar URLs, versão, hash dos arquivos, filtros e exclusões. A separação
realizada usa clusters de imagens, pois não há identificador de alegação
semântica: 94 para ajuste e 41 para avaliação, com semente 20261013. Essa
limitação deve ser preservada na interpretação. O conjunto de avaliação fica
fora da escolha de parâmetros. A grade SIR/SEIR contém transmissão em
{0,05; 0,1; 0,2; 0,4; 0,8} e recuperação em {0,2; 0,5; 1}. O critério de ajuste
soma W1 de log(1+publicadores) e W1 de u50; ausência de u50 recebe penalidade
um. São trinta realizações por combinação no ajuste e 120 novas realizações
por modelo na avaliação. Essas escolhas constam no script usado antes do
primeiro ajuste e são hipóteses operacionais, não parâmetros epidemiológicos
humanos. Não escolher a referência após observar sua avaliação.

Toda execução válida conserva configuração, código, versão/digest do modelo,
mensagens, chamadas ao LLM e motivo de parada. Falhas e interrupções ficam no
manifesto e não entram como alcance zero. Os testes de software usam provedores
controlados, que não produzem evidência empírica sobre as questões de pesquisa.
