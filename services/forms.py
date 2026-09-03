from django import forms

from .models import Servico, SolicitacaoServico, CategoriaServico, MensagemSolicitacao, Avaliacao


class ServicoForm(forms.ModelForm):
    """P3-P8: Adicionar/editar serviço (nome, descrição, preço, duração)."""

    class Meta:
        model = Servico
        fields = ['categoria', 'nome', 'descricao', 'preco', 'duracao_minutos', 'disponivel']
        labels = {
            'categoria': 'Categoria',
            'nome': 'Nome do serviço',
            'descricao': 'Descrição',
            'preco': 'Preço (R$)',
            'duracao_minutos': 'Duração estimada (minutos)',
            'disponivel': 'Disponível para usuários',
        }
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }


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
