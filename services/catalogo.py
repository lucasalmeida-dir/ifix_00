# Catálogo fixo de Categoria -> Serviço -> Subserviços (+ Observação padrão),
# usado no formulário "Adicionar serviço" do painel profissional.
#
# A chave de cada entrada é o slug da CategoriaServico correspondente
# (ver services/migrations/0002_categorias_iniciais.py e
# 0008_renomear_desentupimento_para_pintura.py), para que o formulário
# consiga filtrar "Nome do serviço" e "Subserviço" de acordo com a
# categoria escolhida.

CATALOGO_SERVICOS = {
    'eletrica': {
        'servico': 'Eletricista',
        'subservicos': [
            {'nome': 'Conserto ou manutenção', 'observacao': 'Reparos elétricos'},
            {'nome': 'Instalação', 'observacao': 'Instalações elétricas'},
            {'nome': 'Instalação de ventilador de teto', 'observacao': 'Instalação'},
            {'nome': 'Instalação de painel solar', 'observacao': 'Energia solar'},
            {'nome': 'Limpeza de painel solar', 'observacao': 'Energia solar'},
            {'nome': 'Manutenção de painel solar', 'observacao': 'Energia solar'},
        ],
    },
    'hidraulica': {
        'servico': 'Encanador',
        'subservicos': [
            {'nome': 'Conserto e manutenção', 'observacao': 'Reparos hidráulicos'},
            {'nome': 'Desentupimento', 'observacao': 'Tubulações e esgoto'},
            {'nome': 'Instalação', 'observacao': 'Instalações hidráulicas'},
            {'nome': 'Outros', 'observacao': 'Serviços hidráulicos diversos'},
        ],
    },
    'pintura': {
        'servico': 'Pintor',
        'subservicos': [
            {'nome': 'Casa ou apartamento', 'observacao': 'Pintura residencial'},
            {'nome': 'Móvel', 'observacao': 'Pintura de móveis'},
            {'nome': 'Interno', 'observacao': 'Áreas internas'},
            {'nome': 'Externo', 'observacao': 'Áreas externas'},
            {'nome': 'Textura', 'observacao': 'Texturas e acabamentos'},
            {'nome': 'Grafiato', 'observacao': 'Acabamento decorativo'},
        ],
    },
    'marcenaria': {
        'servico': 'Marceneiro',
        'subservicos': [
            {'nome': 'Reparo e acabamento', 'observacao': 'Reparos em móveis'},
            {'nome': 'Restauração', 'observacao': 'Restauração'},
            {'nome': 'Projeto e fabricação', 'observacao': 'Móveis sob medida'},
            {'nome': 'Móveis convencionais', 'observacao': 'Fabricação/montagem'},
            {'nome': 'Móveis corporativos', 'observacao': 'Móveis para empresas'},
            {'nome': 'Móveis modulados', 'observacao': 'Móveis modulados'},
            {'nome': 'Móveis planejados', 'observacao': 'Móveis planejados'},
            {'nome': 'Pisos e decks', 'observacao': 'Madeira e decks'},
        ],
    },
}


def slug_por_servico(nome_servico):
    """Retorna o slug de categoria dono do 'Serviço' informado (ex.: 'Eletricista' -> 'eletrica')."""
    for slug, dados in CATALOGO_SERVICOS.items():
        if dados['servico'] == nome_servico:
            return slug
    return None


def subservico_valido(slug_categoria, nome_subservico):
    """Confere se o subserviço pertence à categoria informada e devolve sua Observação padrão."""
    dados = CATALOGO_SERVICOS.get(slug_categoria)
    if not dados:
        return False, None
    for sub in dados['subservicos']:
        if sub['nome'] == nome_subservico:
            return True, sub['observacao']
    return False, None
