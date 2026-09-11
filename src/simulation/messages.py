"""
simulation/messages.py
Mensagens iniciais compartilhadas entre as campanhas experimentais.

Ficam aqui, e não dentro de um script de campanha, para que os experimentos
de assunto e de mutação usem exatamente o mesmo estímulo. Registro
linguístico e extensão são deliberadamente comparáveis entre os temas.
"""

SUBJECTS = {
    "Saúde/vacinas": (
        "URGENTE: a vacina da gripe deste ano está causando arritmia em idosos "
        "e o Ministério da Saúde está escondendo. Repasse para sua família!"
    ),
    "Política/eleições": (
        "ATENÇÃO: documento vazado prova que as urnas eletrônicas foram "
        "adulteradas na última eleição. Compartilhe antes que apaguem!"
    ),
    "Economia/benefícios": (
        "URGENTE: o governo vai liberar um novo auxílio de R$ 1.200 para quem "
        "se cadastrar até sexta neste link. Avise todo mundo!"
    ),
    "Segurança/crime": (
        "ALERTA: uma quadrilha está sequestrando crianças na saída das escolas "
        "usando vans brancas. Já são 5 casos esta semana. Repasse!"
    ),
}
