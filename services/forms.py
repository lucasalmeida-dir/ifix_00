import os

from django import forms
from django.utils import timezone

from accounts.services import BRASIL_BBOX

from .catalogo import CATALOGO_SERVICOS, subservico_valido
from .models import (
    Servico,
    SolicitacaoServico,
    CategoriaServico,
    MensagemSolicitacao,
    Avaliacao,
    Orcamento,
    DiaVisitaOrcamento,
)


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


def _opcoes_servico():
    """
    Choices + atributos do campo 'Serviços'.

    Existe só pras categorias com subserviços agrupados no catálogo (hoje,
    Elétrica): cada opção é um dos grupos (ex.: "Instalações novas"),
    valor prefixado com o slug da categoria ("slug|Grupo"). Escolher um
    "Serviço" aqui filtra as opções do campo 'Subserviços' logo abaixo.
    Categorias sem grupos (Hidráulica, Pintura, Marcenaria) não têm essa
    etapa - o profissional vai direto para 'Subserviços'.
    """
    choices = [('', '---------')]
    attrs = {}
    for slug, dados in CATALOGO_SERVICOS.items():
        grupos_vistos = set()
        for sub in dados['subservicos']:
            grupo = sub.get('grupo')
            if grupo and grupo not in grupos_vistos:
                grupos_vistos.add(grupo)
                valor = f'{slug}|{grupo}'
                choices.append((valor, grupo))
                attrs[valor] = {'data-categoria': slug}
    return choices, attrs


def _opcoes_subservico():
    """
    Choices + atributos do campo 'Subserviços'.

    O valor de cada opção é prefixado com o slug da categoria
    ("slug|Subserviço") para permitir subserviços com o mesmo nome em
    categorias diferentes (ex.: "Instalação" em Elétrica e em
    Hidráulica). O prefixo é removido em `ServicoForm.clean_subservico`
    antes de gravar no banco.

    Itens com 'grupo' no catálogo (caso de Elétrica) ganham também o
    atributo data-servico, usado em JS para só aparecerem depois que o
    profissional escolher o 'Serviço' (grupo) correspondente no campo
    de cima.
    """
    choices = [('', '---------')]
    attrs = {}
    for slug, dados in CATALOGO_SERVICOS.items():
        for sub in dados['subservicos']:
            valor = f"{slug}|{sub['nome']}"
            choices.append((valor, sub['nome']))
            item_attrs = {'data-categoria': slug, 'data-observacao': sub['observacao']}
            grupo = sub.get('grupo')
            if grupo:
                item_attrs['data-servico'] = grupo
            attrs[valor] = item_attrs
    return choices, attrs


class ServicoForm(forms.ModelForm):
    """
    P3-P8: Adicionar/editar serviço.

    O profissional escolhe Categoria, (quando a categoria tiver grupos,
    como Elétrica) Serviços, Subserviços, faixa de preço e duração. Os
    campos "Nome do serviço" e "Observação" não aparecem no formulário:
    são preenchidos automaticamente em `save()` a partir do catálogo
    (services/catalogo.py) — "nome" vira a profissão da categoria (ex.:
    Elétrica -> Eletricista) e "descricao" vira a Observação padrão do
    subserviço escolhido.

    O campo "Serviços" é só um filtro para o "Subserviços" logo abaixo -
    ele não é salvo no banco (Servico não tem esse campo).
    """

    servico = forms.ChoiceField(label='Serviços', required=False)
    subservico = forms.ChoiceField(label='Subserviços', required=True)

    class Meta:
        model = Servico
        fields = ['categoria', 'subservico', 'preco_min', 'preco_max', 'duracao_minutos']
        labels = {
            'categoria': 'Categoria',
            'preco_min': 'Preço da visita de (R$)',
            'preco_max': 'até (R$)',
            'duracao_minutos': 'Duração estimada (minutos)',
        }
        widgets = {
            'categoria': SelectComAtributos(),
            'preco_min': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'inputmode': 'decimal'}),
            'preco_max': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'inputmode': 'decimal'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # O profissional só pode cadastrar serviço nas categorias que ele
        # escolheu como especialidade no cadastro (ex.: quem marcou só
        # "Elétrica" não pode criar serviço de "Pintura"). Ao editar um
        # serviço já existente, a categoria atual continua disponível
        # mesmo que não esteja mais entre as especialidades, para não
        # quebrar o formulário de um serviço antigo.
        if user is not None:
            perfil = getattr(user, 'profile', None)
            if perfil is not None:
                queryset = perfil.especialidades.all()
                if self.instance and self.instance.pk and self.instance.categoria_id:
                    queryset = queryset | CategoriaServico.objects.filter(pk=self.instance.categoria_id)
                self.fields['categoria'].queryset = queryset.distinct()

        self.fields['categoria'].widget.choice_attrs = _opcoes_categoria()

        # Importante: o widget novo precisa nascer já com `choices`, pois
        # trocar `self.fields[...].widget` por uma instância nova NÃO
        # herda as choices que o field já tinha — sem isso, o <select>
        # fica sem nenhuma <option>.
        servico_choices, servico_attrs = _opcoes_servico()
        self.fields['servico'].widget = SelectComAtributos(choices=servico_choices, choice_attrs=servico_attrs)
        self.fields['servico'].choices = servico_choices

        sub_choices, sub_attrs = _opcoes_subservico()
        self.fields['subservico'].widget = SelectComAtributos(choices=sub_choices, choice_attrs=sub_attrs)
        self.fields['subservico'].choices = sub_choices

        self.order_fields([
            'categoria', 'servico', 'subservico',
            'preco_min', 'preco_max', 'duracao_minutos',
        ])

        # Ao editar um serviço já cadastrado, o valor de 'subservico' vem
        # "limpo" do banco (sem o prefixo "slug|"); refaz o prefixo para
        # que o <select> venha com a opção certa selecionada - e, se esse
        # subserviço pertencer a um grupo, refaz também o valor de
        # 'servico' para o <select> de cima vir com o grupo certo.
        if self.instance and self.instance.pk and self.instance.subservico and self.instance.categoria_id:
            categoria = self.instance.categoria
            self.initial['subservico'] = f"{categoria.slug}|{self.instance.subservico}"
            dados_categoria = CATALOGO_SERVICOS.get(categoria.slug)
            if dados_categoria:
                for sub in dados_categoria['subservicos']:
                    if sub['nome'] == self.instance.subservico and sub.get('grupo'):
                        self.initial['servico'] = f"{categoria.slug}|{sub['grupo']}"
                        break

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


class ServicoEmLoteForm(forms.Form):
    """Cria de uma vez um card de serviço para cada subserviço de um
    "Serviço" (grupo) inteiro - ex.: escolher Elétrica + "Iluminação" cria
    um Servico para cada um dos subserviços desse grupo (Instalação e
    troca de lâmpadas e luminárias, Instalação de lustres, etc.), todos
    com o mesmo preço e duração. Evita cadastrar um por um quando o
    profissional atende a área inteira.
    """

    categoria = forms.ModelChoiceField(
        queryset=CategoriaServico.objects.all(), label='Categoria',
        widget=SelectComAtributos(),
    )
    servico = forms.ChoiceField(label='Serviços', required=True)
    preco_min = forms.DecimalField(
        label='Preço da visita de (R$)', min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
    )
    preco_max = forms.DecimalField(
        label='até (R$)', min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
    )
    duracao_minutos = forms.IntegerField(
        label='Duração estimada (minutos)', min_value=1,
        widget=forms.NumberInput(attrs={'inputmode': 'numeric'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Mesma regra do ServicoForm: só pode escolher uma categoria que
        # seja especialidade do profissional.
        if user is not None:
            perfil = getattr(user, 'profile', None)
            if perfil is not None:
                self.fields['categoria'].queryset = perfil.especialidades.all()
        self.fields['categoria'].widget.choice_attrs = _opcoes_categoria()

        servico_choices, servico_attrs = _opcoes_servico()
        self.fields['servico'].widget = SelectComAtributos(choices=servico_choices, choice_attrs=servico_attrs)
        self.fields['servico'].choices = servico_choices

    def clean(self):
        cleaned_data = super().clean()
        preco_min = cleaned_data.get('preco_min')
        preco_max = cleaned_data.get('preco_max')
        if preco_min is not None and preco_max is not None and preco_max < preco_min:
            self.add_error('preco_max', 'O preço máximo não pode ser menor que o preço mínimo.')

        categoria = cleaned_data.get('categoria')
        valor_servico = cleaned_data.get('servico')
        if categoria and valor_servico:
            slug, _, grupo = valor_servico.partition('|')
            if slug != categoria.slug:
                self.add_error('servico', 'Esse Serviço não pertence à categoria escolhida.')
            else:
                cleaned_data['servico'] = grupo
        return cleaned_data


MAX_ANEXOS = 5
MAX_FOTO_MB = 8
MAX_VIDEO_MB = 30
EXT_FOTO = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.heif')
EXT_VIDEO = ('.mp4', '.mov', '.webm', '.m4v')


def _assinatura_confere(extensao, cabecalho):
    """Confere os primeiros bytes do arquivo com o formato que a extensão
    promete - impede enviar, por exemplo, uma página HTML/script renomeada
    para .jpg."""
    if extensao in ('.jpg', '.jpeg'):
        return cabecalho.startswith(b'\xff\xd8\xff')
    if extensao == '.png':
        return cabecalho.startswith(b'\x89PNG\r\n\x1a\n')
    if extensao == '.gif':
        return cabecalho[:6] in (b'GIF87a', b'GIF89a')
    if extensao == '.webp':
        return cabecalho[:4] == b'RIFF' and cabecalho[8:12] == b'WEBP'
    if extensao in ('.heic', '.heif', '.mp4', '.mov', '.m4v'):
        return cabecalho[4:8] == b'ftyp'
    if extensao == '.webm':
        return cabecalho.startswith(b'\x1a\x45\xdf\xa3')
    return False


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Campo de vários arquivos (fotos/vídeos) de uma vez só."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'image/*,video/*'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpar = super().clean
        if isinstance(data, (list, tuple)):
            return [limpar(arquivo, initial) for arquivo in data if arquivo]
        return [limpar(data, initial)] if data else []


class SolicitarServicoForm(forms.ModelForm):
    """U8 - Solicitar visita: o cliente escolhe, no calendário, o dia (e o
    turno) em que deseja receber o profissional, pode marcar o pedido como
    urgente, descrever o problema, anexar fotos/vídeos e compartilhar a
    localização do celular (GPS). A conversa só começa depois que o
    profissional aceita a solicitação, direto na aba Mensagens.
    """

    anexos = MultipleFileField(
        required=False, label='Fotos ou vídeo do problema',
        help_text=f'Até {MAX_ANEXOS} arquivos (foto até {MAX_FOTO_MB} MB, vídeo até {MAX_VIDEO_MB} MB).',
    )

    class Meta:
        model = SolicitacaoServico
        fields = ['data_visita', 'turno', 'urgente', 'mensagem', 'endereco_visita', 'latitude', 'longitude']
        labels = {
            'data_visita': 'Dia da visita',
            'turno': 'Melhor horário',
            'mensagem': 'Descreva o problema',
            'endereco_visita': 'Endereço ou ponto de referência',
        }
        widgets = {
            'data_visita': forms.HiddenInput(),
            'urgente': forms.CheckboxInput(),
            'turno': forms.RadioSelect(),
            'mensagem': forms.Textarea(attrs={
                'rows': 3, 'maxlength': 1000,
                'placeholder': 'Ex.: a torneira da cozinha está pingando desde ontem...',
            }),
            'endereco_visita': forms.TextInput(attrs={
                'maxlength': 255, 'placeholder': 'Rua, número, bairro, ponto de referência',
                'autocomplete': 'street-address',
            }),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_visita'].required = False
        self.fields['mensagem'].required = False
        self.fields['endereco_visita'].required = False
        self.fields['turno'].choices = list(SolicitacaoServico.TURNO_CHOICES)
        self.fields['turno'].initial = SolicitacaoServico.TURNO_QUALQUER

    def clean_anexos(self):
        arquivos = self.cleaned_data.get('anexos') or []
        if len(arquivos) > MAX_ANEXOS:
            raise forms.ValidationError(f'Envie no máximo {MAX_ANEXOS} arquivos.')
        for arquivo in arquivos:
            extensao = os.path.splitext(arquivo.name)[1].lower()
            if extensao in EXT_FOTO:
                limite_mb = MAX_FOTO_MB
            elif extensao in EXT_VIDEO:
                limite_mb = MAX_VIDEO_MB
            else:
                raise forms.ValidationError(f'"{arquivo.name}" não é uma foto ou vídeo aceito.')
            if arquivo.size > limite_mb * 1024 * 1024:
                raise forms.ValidationError(f'"{arquivo.name}" passa de {limite_mb} MB.')
            cabecalho = arquivo.read(16)
            arquivo.seek(0)
            if not _assinatura_confere(extensao, cabecalho):
                raise forms.ValidationError(f'"{arquivo.name}" não parece ser um arquivo válido.')
        return arquivos

    def clean(self):
        dados = super().clean()
        hoje = timezone.localdate()
        data_visita = dados.get('data_visita')

        if dados.get('urgente'):
            dados['data_visita'] = hoje
            data_visita = hoje
        if not data_visita:
            self.add_error('data_visita', 'Escolha, no calendário, o dia desejado para a visita.')
        elif data_visita < hoje:
            self.add_error('data_visita', 'Escolha uma data igual ou posterior a hoje.')

        latitude, longitude = dados.get('latitude'), dados.get('longitude')
        if (latitude is None) != (longitude is None):
            dados['latitude'] = dados['longitude'] = None
        elif latitude is not None:
            lat_min, lat_max, lon_min, lon_max = BRASIL_BBOX
            if not (lat_min <= latitude <= lat_max and lon_min <= longitude <= lon_max):
                dados['latitude'] = dados['longitude'] = None
        return dados


EXT_CHAT_IMAGEM = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.heif')
EXT_CHAT_AUDIO = ('.webm', '.ogg', '.oga', '.mp3', '.m4a', '.mp4', '.wav', '.aac')
MAX_CHAT_IMAGEM_MB = 8
MAX_CHAT_AUDIO_MB = 10


def _audio_confere(extensao, cabecalho):
    if extensao == '.webm':
        return cabecalho.startswith(b'\x1a\x45\xdf\xa3')
    if extensao in ('.ogg', '.oga'):
        return cabecalho.startswith(b'OggS')
    if extensao == '.wav':
        return cabecalho[:4] == b'RIFF' and cabecalho[8:12] == b'WAVE'
    if extensao == '.mp3':
        return cabecalho.startswith(b'ID3') or (cabecalho[0] == 0xFF and (cabecalho[1] & 0xE0) == 0xE0)
    if extensao in ('.m4a', '.mp4'):
        return cabecalho[4:8] == b'ftyp'
    if extensao == '.aac':
        return cabecalho[0] == 0xFF and (cabecalho[1] & 0xF0) == 0xF0
    return False


class MensagemSolicitacaoForm(forms.ModelForm):
    """Mensagem do chat: texto, foto ou áudio (gravado no próprio celular).
    Pelo menos um dos três precisa vir preenchido."""

    class Meta:
        model = MensagemSolicitacao
        fields = ['texto', 'anexo']
        labels = {'texto': '', 'anexo': ''}
        widgets = {
            'texto': forms.Textarea(attrs={
                'rows': 1,
                'placeholder': 'Digite uma mensagem...',
                'class': 'chat-input',
                'autocomplete': 'off',
                'maxlength': 2000,
            }),
            'anexo': forms.FileInput(attrs={'accept': 'image/*,audio/*', 'class': 'chat-file-input'}),
        }

    def clean_anexo(self):
        arquivo = self.cleaned_data.get('anexo')
        if not arquivo or not hasattr(arquivo, 'read'):
            return arquivo
        extensao = os.path.splitext(arquivo.name)[1].lower()
        cabecalho = arquivo.read(16).ljust(16, b'\0')
        arquivo.seek(0)
        if extensao in EXT_CHAT_IMAGEM:
            limite, confere, self._tipo = MAX_CHAT_IMAGEM_MB, _assinatura_confere(extensao, cabecalho), 'imagem'
        elif extensao in EXT_CHAT_AUDIO:
            limite, confere, self._tipo = MAX_CHAT_AUDIO_MB, _audio_confere(extensao, cabecalho), 'audio'
        else:
            raise forms.ValidationError('Envie uma foto ou um áudio.')
        if arquivo.size > limite * 1024 * 1024:
            raise forms.ValidationError(f'O arquivo passa de {limite} MB.')
        if not confere:
            raise forms.ValidationError('Esse arquivo não parece ser válido.')
        return arquivo

    def clean(self):
        dados = super().clean()
        texto = (dados.get('texto') or '').strip()
        dados['texto'] = texto
        if not texto and not dados.get('anexo') and not self.errors:
            raise forms.ValidationError('Escreva uma mensagem, envie uma foto ou grave um áudio.')
        return dados

    def tipo_da_mensagem(self):
        if self.cleaned_data.get('anexo'):
            return getattr(self, '_tipo', 'imagem')
        return 'texto'


class AvaliacaoForm(forms.ModelForm):
    # Campo declarado explicitamente (em vez de deixar o ModelForm gerar
    # sozinho) porque, como o model não tem valor padrão, o Django
    # acrescentaria uma opção vazia ("---------") às 5 escolhas de
    # ESTRELAS_CHOICES - e o template, que desenha uma estrela para cada
    # opção do campo, acabava mostrando 6 estrelas em vez de 5.
    estrelas = forms.TypedChoiceField(
        choices=Avaliacao.ESTRELAS_CHOICES,
        coerce=int,
        label='Como você avalia o profissional?',
        widget=forms.RadioSelect(attrs={'class': 'rating-options'}),
    )

    class Meta:
        model = Avaliacao
        fields = ['estrelas', 'comentario']
        labels = {
            'comentario': 'Comentário (opcional)',
        }
        widgets = {
            'comentario': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Conte como foi o serviço...'}),
        }


class AvaliacaoRespostaForm(forms.ModelForm):
    """O profissional responde a uma avaliação e pode anexar uma foto do
    serviço já concluído."""

    class Meta:
        model = Avaliacao
        fields = ['resposta_profissional', 'foto_resposta']
        labels = {
            'resposta_profissional': 'Sua resposta',
            'foto_resposta': 'Foto do serviço concluído (opcional)',
        }
        widgets = {
            'resposta_profissional': forms.Textarea(attrs={
                'rows': 3, 'maxlength': 1000, 'placeholder': 'Agradeça ou esclareça algum ponto da avaliação...',
            }),
            'foto_resposta': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean(self):
        dados = super().clean()
        if not dados.get('resposta_profissional') and not dados.get('foto_resposta'):
            raise forms.ValidationError('Escreva uma resposta ou anexe uma foto do serviço concluído.')
        return dados


class BuscaServicoForm(forms.Form):
    """U5/U6 - Buscar, filtrar e ordenar profissionais."""

    # Sem opção de "mais relevante": sem nenhuma escolhida, a listagem só
    # usa a ordem padrão (mais recentes primeiro) - essas três viram botões
    # de atalho na tela, não um <select>.
    ORDENAR_CHOICES = (
        ('preco', 'Menor preço'),
        ('distancia', 'Mais próximos'),
        ('avaliacao', 'Melhor avaliados'),
    )

    q = forms.CharField(
        required=False, label='Buscar serviço',
        widget=forms.TextInput(attrs={'placeholder': 'Buscar serviço...'}),
    )
    categoria = forms.ModelChoiceField(
        required=False, label='Categoria', queryset=CategoriaServico.objects.all(),
        empty_label='Todas as categorias',
    )
    ordenar = forms.ChoiceField(required=False, label='Ordenar por', choices=ORDENAR_CHOICES)


class OrcamentoForm(forms.ModelForm):
    """O profissional preenche o valor real do serviço depois de visitar o
    cliente pela primeira vez."""

    class Meta:
        model = Orcamento
        fields = ['valor', 'observacoes']
        labels = {
            'valor': 'Valor total do orçamento (R$)',
            'observacoes': 'Observações para o cliente (opcional)',
        }
        widgets = {
            'valor': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0,00', 'inputmode': 'decimal'}),
            'observacoes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Detalhe o que será feito, materiais, etc.',
            }),
        }


DiaVisitaFormSet = forms.modelformset_factory(
    DiaVisitaOrcamento,
    fields=['data'],
    widgets={'data': forms.DateInput(attrs={'type': 'date'})},
    labels={'data': 'Dia da visita'},
    extra=1,
    can_delete=True,
)
