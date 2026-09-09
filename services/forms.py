from django import forms

from .catalogo import CATALOGO_SERVICOS, subservico_valido
from .models import Servico, SolicitacaoServico, CategoriaServico, MensagemSolicitacao, Avaliacao


class SelectComAtributos(forms.Select):
    """Select cujas <option> recebem atributos HTML extras (ex.: data-categoria,
    data-observacao), indexados pelo valor da própria opção.

    Usado nos campos 'categoria' e 'subservico' do formulário de serviço
    para permitir, via JavaScript, filtrar as opções de acordo com a
    categoria escolhida.
    """

    def __init__(self, *args, choice_attrs=None, **kwargs):
        super().__init__(*args, **kwargs)
        # choice_attrs: dict {valor_da_opcao: {atributo: valor, ...}}
        self.choice_attrs = choice_attrs or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        extra = self.choice_attrs.get(str(value))
        if extra:
            option['attrs'].update(extra)
        return option


def _opcoes_categoria():
    """Mapa {pk_categoria: {'data-slug': slug}} para filtrar nome/subserviço em JS."""
    return {
        str(categoria.pk): {'data-slug': categoria.slug}
        for categoria in CategoriaServico.objects.all()
    }


def _opcoes_subservico():
    """
    Choices + atributos do campo 'Subserviço'.

    O valor de cada opção é prefixado com o slug da categoria
    ("slug|Subserviço") para permitir subserviços com o mesmo nome em
    categorias diferentes (ex.: "Instalação" em Elétrica e em
    Hidráulica). O prefixo é removido em `ServicoForm.clean_subservico`
    antes de gravar no banco.
    """
    choices = [('', '---------')]
    attrs = {}
    for slug, dados in CATALOGO_SERVICOS.items():
        for sub in dados['subservicos']:
            valor = f"{slug}|{sub['nome']}"
            choices.append((valor, sub['nome']))
            attrs[valor] = {'data-categoria': slug, 'data-observacao': sub['observacao']}
    return choices, attrs


class ServicoForm(forms.ModelForm):
    """
    P3-P8: Adicionar/editar serviço.

    O profissional só escolhe Categoria, Subserviço, faixa de preço e
    duração. Os campos "Nome do serviço" e "Observação" não aparecem no
    formulário: são preenchidos automaticamente em `save()` a partir do
    catálogo (services/catalogo.py) — "nome" vira a profissão da
    categoria (ex.: Elétrica -> Eletricista) e "descricao" vira a
    Observação padrão do subserviço escolhido.
    """

    subservico = forms.ChoiceField(label='Subserviço', required=True)

    class Meta:
        model = Servico
        fields = ['categoria', 'subservico', 'preco_min', 'preco_max', 'duracao_minutos', 'disponivel']
        labels = {
            'categoria': 'Categoria',
            'preco_min': 'Preço estimado de (R$)',
            'preco_max': 'até (R$)',
            'duracao_minutos': 'Duração estimada (minutos)',
            'disponivel': 'Disponível para usuários',
        }
        widgets = {
            'categoria': SelectComAtributos(),
            'preco_min': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'preco_max': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['categoria'].widget.choice_attrs = _opcoes_categoria()

        # Importante: o widget novo precisa nascer já com `choices`, pois
        # trocar `self.fields[...].widget` por uma instância nova NÃO
        # herda as choices que o field já tinha — sem isso, o <select>
        # fica sem nenhuma <option>.
        sub_choices, sub_attrs = _opcoes_subservico()
        self.fields['subservico'].widget = SelectComAtributos(choices=sub_choices, choice_attrs=sub_attrs)
        self.fields['subservico'].choices = sub_choices

        # Ao editar um serviço já cadastrado, o valor de 'subservico' vem
        # "limpo" do banco (sem o prefixo "slug|"); refaz o prefixo para
        # que o <select> venha com a opção certa selecionada.
        if self.instance and self.instance.pk and self.instance.subservico and self.instance.categoria_id:
            categoria = self.instance.categoria
            self.initial['subservico'] = f"{categoria.slug}|{self.instance.subservico}"

    def clean_subservico(self):
        valor = self.cleaned_data.get('subservico')
        if not valor:
            return ''
        if '|' not in valor:
            return valor
        slug, _, nome_subservico = valor.partition('|')
        categoria = self.cleaned_data.get('categoria')
        if categoria and categoria.slug != slug:
            raise forms.ValidationError('Esse subserviço não pertence à categoria escolhida.')
        valido, _observacao = subservico_valido(slug, nome_subservico)
        if not valido:
            raise forms.ValidationError('Subserviço inválido.')
        return nome_subservico

    def save(self, commit=True):
        # Preenche "nome" (a profissão da categoria) e "descricao" (a
        # Observação padrão do subserviço) automaticamente, já que esses
        # dois campos não aparecem mais no formulário.
        categoria = self.cleaned_data.get('categoria')
        subservico = self.cleaned_data.get('subservico')
        if categoria:
            dados_categoria = CATALOGO_SERVICOS.get(categoria.slug)
            if dados_categoria:
                self.instance.nome = dados_categoria['servico']
            if subservico:
                _valido, observacao = subservico_valido(categoria.slug, subservico)
                if observacao:
                    self.instance.descricao = observacao
        return super().save(commit=commit)


class SolicitarServicoForm(forms.ModelForm):
    """U8 - Solicitar serviço."""

    class Meta:
        model = SolicitacaoServico
        fields = ['mensagem']
        labels = {'mensagem': 'Mensagem para o profissional (opcional)'}
        widgets = {
            'mensagem': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Detalhe o que você precisa...'}),
        }


class MensagemSolicitacaoForm(forms.ModelForm):
    class Meta:
        model = MensagemSolicitacao
        fields = ['texto']
        labels = {'texto': 'Mensagem'}
        widgets = {
            'texto': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Escreva uma mensagem sobre o serviço...',
            }),
        }


class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ['estrelas', 'comentario']
        labels = {
            'estrelas': 'Como você avalia o profissional?',
            'comentario': 'Comentário (opcional)',
        }
        widgets = {
            'estrelas': forms.RadioSelect(attrs={'class': 'rating-options'}),
            'comentario': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Conte como foi o serviço...'}),
        }


class BuscaServicoForm(forms.Form):
    """U5/U6 - Buscar profissionais e filtrar por categoria."""

    q = forms.CharField(
        required=False, label='Buscar profissional ou serviço',
        widget=forms.TextInput(attrs={'placeholder': 'Nome do profissional ou serviço...'}),
    )
    categoria = forms.ModelChoiceField(
        required=False, label='Categoria', queryset=CategoriaServico.objects.all(),
        empty_label='Todas as categorias',
    )
