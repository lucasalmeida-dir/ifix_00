import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify


def estrelas_da_media(media):
    if media is None:
        return ''
    estrelas_preenchidas = min(5, max(0, int(float(media) + 0.5)))
    return '★' * estrelas_preenchidas + '☆' * (5 - estrelas_preenchidas)


class CategoriaServico(models.Model):
    """
    Categorias de serviço (O1 a O4 do diagrama):
    Hidráulica, Elétrica, Marcenaria e Pintura.
    """

    nome = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    icone = models.CharField(
        max_length=30, blank=True,
        help_text='Nome de um emoji/ícone simples para exibir na listagem.',
    )

    class Meta:
        verbose_name = 'Categoria de serviço'
        verbose_name_plural = 'Categorias de serviço'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('services:servico_categoria', args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)


class Servico(models.Model):
    """
    Representa o "Banco de dados de serviços" (D1) do diagrama:
    cada linha é um serviço cadastrado por um profissional
    (P3 Adicionar serviço -> P4..P8 -> D1).
    """

    profissional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='servicos',
        limit_choices_to={'profile__tipo': 'profissional'},
    )
    categoria = models.ForeignKey(
        CategoriaServico,
        on_delete=models.PROTECT,
        related_name='servicos',
    )
    nome = models.CharField(max_length=150, verbose_name='Nome do serviço')  # P4
    slug = models.SlugField(
        max_length=180, unique=True, blank=True,
        help_text='Gerado sozinho (ex.: eletricista-joao-silva-12) - usado na URL da página do serviço.',
    )
    subservico = models.CharField(
        max_length=150, blank=True, verbose_name='Subserviço',
    )  # P4.1 - opção específica dentro do serviço, conforme a categoria
    descricao = models.TextField(verbose_name='Observação')  # P5
    preco_min = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Preço da visita a partir de (R$)',
    )  # P6
    preco_max = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Preço da visita até (R$)',
    )  # P6
    duracao_minutos = models.PositiveIntegerField(verbose_name='Duração estimada (minutos)')  # P7
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Serviço'
        verbose_name_plural = 'Serviços'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.nome} ({self.profissional.username})'

    def clean(self):
        super().clean()
        if self.preco_min is not None and self.preco_max is not None and self.preco_max < self.preco_min:
            raise ValidationError({
                'preco_max': 'O preço máximo não pode ser menor que o preço mínimo.',
            })

    @property
    def faixa_preco(self):
        """Texto pronto para exibir a estimativa de preço ao cliente."""
        if self.preco_min == self.preco_max:
            return f'R$ {self.preco_min}'
        return f'R$ {self.preco_min} - R$ {self.preco_max}'

    def get_absolute_url(self):
        return reverse('services:servico_detail', args=[self.slug])

    def _gerar_slug(self):
        from .catalogo import CATALOGO_SERVICOS
        profissao = CATALOGO_SERVICOS.get(self.categoria.slug, {}).get('servico') or self.categoria.nome
        nome_profissional = self.profissional.get_full_name() or self.profissional.username
        base = slugify(f'{profissao} {nome_profissional}') or 'servico'
        return f'{base}-{self.pk}'

    def save(self, *args, **kwargs):
        novo = self.pk is None
        super().save(*args, **kwargs)
        if novo and not self.slug:
            # O slug leva o pk (ex.: eletricista-joao-silva-12), então só dá
            # para montá-lo depois do primeiro save, quando o pk já existe.
            self.slug = self._gerar_slug()
            super().save(update_fields=['slug'])


class SolicitacaoServico(models.Model):
    """Solicitação feita pelo usuário (U8 - Solicitar serviço)."""

    STATUS_PENDENTE = 'pendente'
    STATUS_CONFIRMADO = 'confirmado'
    STATUS_CONCLUIDO = 'concluido'
    STATUS_CANCELADO = 'cancelado'
    STATUS_CHOICES = (
        (STATUS_PENDENTE, 'Pendente'),
        (STATUS_CONFIRMADO, 'Confirmado'),
        (STATUS_CONCLUIDO, 'Concluído'),
        (STATUS_CANCELADO, 'Cancelado'),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='solicitacoes',
    )
    servico = models.ForeignKey(
        Servico,
        on_delete=models.CASCADE,
        related_name='solicitacoes',
    )
    mensagem = models.TextField(blank=True, verbose_name='Mensagem/observações')
    data_visita = models.DateField(
        null=True, blank=True,
        verbose_name='Dia da visita solicitado',
        help_text='Dia escolhido pelo cliente, no calendário, para a visita do profissional.',
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    visita_concluida_em = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Visita concluída em',
        help_text='Preenchido quando o cliente confirma que o profissional foi até a casa dele, liberando a aba Orçamentos para essa solicitação.',
    )
    TURNO_MANHA = 'manha'
    TURNO_TARDE = 'tarde'
    TURNO_NOITE = 'noite'
    TURNO_QUALQUER = 'qualquer'
    TURNO_CHOICES = (
        (TURNO_MANHA, 'Manhã (8h às 12h)'),
        (TURNO_TARDE, 'Tarde (12h às 18h)'),
        (TURNO_NOITE, 'Noite (18h às 21h)'),
        (TURNO_QUALQUER, 'Qualquer horário'),
    )
    TURNOS_CURTOS = {
        TURNO_MANHA: 'Manhã',
        TURNO_TARDE: 'Tarde',
        TURNO_NOITE: 'Noite',
        TURNO_QUALQUER: 'Qualquer horário',
    }

    turno = models.CharField(
        max_length=10, choices=TURNO_CHOICES, default=TURNO_QUALQUER,
        verbose_name='Turno preferido',
    )
    urgente = models.BooleanField(
        default=False, verbose_name='Urgente (hoje)',
        help_text='O cliente precisa do atendimento hoje; o pedido aparece em destaque para o profissional.',
    )
    grupo = models.UUIDField(
        null=True, blank=True, db_index=True, editable=False,
        help_text='Pedidos criados juntos, para vários profissionais ao mesmo tempo, dividem o mesmo grupo (usado na comparação).',
    )
    latitude = models.FloatField(null=True, blank=True, verbose_name='Latitude do local da visita')
    longitude = models.FloatField(null=True, blank=True, verbose_name='Longitude do local da visita')
    endereco_visita = models.CharField(
        max_length=255, blank=True, verbose_name='Endereço / ponto de referência da visita',
    )
    a_caminho_em = models.DateTimeField(
        null=True, blank=True, verbose_name='Profissional avisou que está a caminho (1ª visita)',
    )
    reagendamentos = models.PositiveSmallIntegerField(
        default=0, verbose_name='Reagendamentos aceitos (1ª visita)',
    )
    cancelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='solicitacoes_canceladas', verbose_name='Cancelado por',
    )
    cancelado_em = models.DateTimeField(null=True, blank=True, verbose_name='Cancelado em')
    motivo_cancelamento = models.TextField(blank=True, verbose_name='Motivo do cancelamento')
    cancelamento_tardio = models.BooleanField(
        default=False, verbose_name='Cancelamento tardio',
        help_text='Cancelado com menos antecedência do que a regra permite (ver services/regras.py).',
    )
    respondida_em = models.DateTimeField(
        null=True, blank=True, verbose_name='Respondida pelo profissional em',
        help_text='Quando o profissional aceitou ou recusou o pedido (base do tempo de resposta do perfil).',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Solicitação de serviço'
        verbose_name_plural = 'Solicitações de serviço'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Solicitação de {self.usuario.username} para {self.servico.nome}'

    @property
    def turno_curto(self):
        return self.TURNOS_CURTOS.get(self.turno, '')

    @property
    def tem_gps(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def mapa_url(self):
        """Link para abrir a localização exata (GPS) no app de mapas do celular."""
        if not self.tem_gps:
            return ''
        return f'https://www.google.com/maps?q={self.latitude},{self.longitude}'


def caminho_anexo(instance, filename):
    """Nome aleatório: o endereço do arquivo não pode ser adivinhado."""
    extensao = os.path.splitext(filename)[1].lower()
    return f'solicitacoes/{uuid.uuid4().hex}{extensao}'


class AnexoSolicitacao(models.Model):
    """Foto ou vídeo do problema, enviado pelo cliente junto com o pedido."""

    EXTENSOES_VIDEO = ('.mp4', '.mov', '.webm', '.m4v')

    solicitacao = models.ForeignKey(
        SolicitacaoServico, on_delete=models.CASCADE, related_name='anexos',
    )
    arquivo = models.FileField(upload_to=caminho_anexo, verbose_name='Foto ou vídeo')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Anexo da solicitação'
        verbose_name_plural = 'Anexos da solicitação'
        ordering = ['id']

    def __str__(self):
        return f'Anexo de {self.solicitacao}'

    @property
    def is_video(self):
        return os.path.splitext(self.arquivo.name)[1].lower() in self.EXTENSOES_VIDEO


class Orcamento(models.Model):
    """Orçamento real, enviado pelo profissional depois da primeira visita
    (quando ele já sabe o que precisa ser feito): valor final do serviço e,
    em Dias de visita, quantas idas à casa do cliente serão necessárias."""

    solicitacao = models.OneToOneField(
        SolicitacaoServico,
        on_delete=models.CASCADE,
        related_name='orcamento',
    )
    valor = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Valor do orçamento (R$)',
    )
    observacoes = models.TextField(blank=True, verbose_name='Observações para o cliente')
    STATUS_PENDENTE = 'pendente'
    STATUS_APROVADO = 'aprovado'
    STATUS_RECUSADO = 'recusado'
    STATUS_CHOICES = (
        (STATUS_PENDENTE, 'Aguardando aprovação'),
        (STATUS_APROVADO, 'Aprovado'),
        (STATUS_RECUSADO, 'Recusado'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    respondido_em = models.DateTimeField(null=True, blank=True)
    motivo_recusa = models.TextField(blank=True, verbose_name='Motivo da recusa')
    resposta_vista_pelo_profissional = models.BooleanField(default=True)
    visualizado_pelo_cliente = models.BooleanField(
        default=False,
        verbose_name='Visualizado pelo cliente',
        help_text='Marca se o cliente já abriu a tela deste orçamento, para controlar o aviso de "novo orçamento" no menu.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Orçamento'
        verbose_name_plural = 'Orçamentos'

    def __str__(self):
        return f'Orçamento de {self.solicitacao}'


class DiaVisitaOrcamento(models.Model):
    """Um dos dias de visita previstos em um orçamento - a quantidade de
    linhas aqui é, na prática, "quantas visitas o profissional vai
    precisar fazer" para concluir o serviço."""

    orcamento = models.ForeignKey(
        Orcamento,
        on_delete=models.CASCADE,
        related_name='dias_visita',
    )
    data = models.DateField(verbose_name='Dia da visita')
    STATUS_PROPOSTA = 'proposta'
    STATUS_AGENDADA = 'agendada'
    STATUS_CANCELADA = 'cancelada'
    STATUS_CHOICES = (
        (STATUS_PROPOSTA, 'Proposta (aguardando aprovação do orçamento)'),
        (STATUS_AGENDADA, 'Agendada'),
        (STATUS_CANCELADA, 'Cancelada'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PROPOSTA)
    turno = models.CharField(
        max_length=10, choices=SolicitacaoServico.TURNO_CHOICES,
        default=SolicitacaoServico.TURNO_QUALQUER, verbose_name='Turno',
    )
    a_caminho_em = models.DateTimeField(null=True, blank=True, verbose_name='Profissional avisou que está a caminho')
    reagendamentos = models.PositiveSmallIntegerField(default=0, verbose_name='Reagendamentos aceitos')

    class Meta:
        verbose_name = 'Dia de visita do orçamento'
        verbose_name_plural = 'Dias de visita do orçamento'
        ordering = ['data']

    def __str__(self):
        return self.data.strftime('%d/%m/%Y')


def caminho_chat(instance, filename):
    extensao = os.path.splitext(filename)[1].lower()
    return f'chat/{uuid.uuid4().hex}{extensao}'


class MensagemSolicitacao(models.Model):
    solicitacao = models.ForeignKey(
        SolicitacaoServico,
        on_delete=models.CASCADE,
        related_name='mensagens',
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mensagens_solicitacao',
    )
    TIPO_TEXTO = 'texto'
    TIPO_IMAGEM = 'imagem'
    TIPO_AUDIO = 'audio'
    TIPO_CHOICES = (
        (TIPO_TEXTO, 'Texto'),
        (TIPO_IMAGEM, 'Foto'),
        (TIPO_AUDIO, 'Áudio'),
    )
    texto = models.TextField(blank=True, verbose_name='Mensagem')
    anexo = models.FileField(upload_to=caminho_chat, blank=True, verbose_name='Foto ou áudio')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default=TIPO_TEXTO)
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mensagem da solicitação'
        verbose_name_plural = 'Mensagens das solicitações'
        ordering = ['criada_em']

    def __str__(self):
        return f'Mensagem de {self.autor.username} na solicitação {self.solicitacao_id}'

    @property
    def resumo(self):
        """Texto curto para prévias (lista de conversas, e-mails)."""
        if self.tipo == self.TIPO_IMAGEM:
            return 'Foto' + (f': {self.texto}' if self.texto else '')
        if self.tipo == self.TIPO_AUDIO:
            return 'Mensagem de áudio'
        return self.texto


class Avaliacao(models.Model):
    ESTRELAS_CHOICES = [
        (5, '★★★★★'),
        (4, '★★★★☆'),
        (3, '★★★☆☆'),
        (2, '★★☆☆☆'),
        (1, '★☆☆☆☆'),
    ]

    solicitacao = models.OneToOneField(
        SolicitacaoServico,
        on_delete=models.CASCADE,
        related_name='avaliacao',
    )
    profissional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='avaliacoes_recebidas',
        limit_choices_to={'profile__tipo': 'profissional'},
        verbose_name='Profissional avaliado',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='avaliacoes_feitas',
        verbose_name='Avaliado por',
    )
    estrelas = models.PositiveSmallIntegerField(choices=ESTRELAS_CHOICES)
    comentario = models.TextField(blank=True, verbose_name='Comentário (opcional)')
    resposta_profissional = models.TextField(blank=True, verbose_name='Resposta do profissional')
    resposta_em = models.DateTimeField(null=True, blank=True, verbose_name='Respondido em')
    foto_resposta = models.FileField(
        upload_to='fotos_servico_concluido/', blank=True,
        verbose_name='Foto do serviço concluído',
        help_text='Foto do resultado do trabalho, anexada pelo profissional junto com a resposta.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.profissional.username} - {self.estrelas}★'

    @property
    def respondida(self):
        return bool(self.resposta_profissional or self.foto_resposta)


@receiver(post_delete, sender=AnexoSolicitacao)
def apagar_arquivo_do_anexo(sender, instance, **kwargs):
    """Remove o arquivo do disco quando o último anexo que o usa é apagado
    (pedidos para vários profissionais compartilham o mesmo arquivo)."""
    nome = instance.arquivo.name
    if nome and not AnexoSolicitacao.objects.filter(arquivo=nome).exists():
        instance.arquivo.storage.delete(nome)


class PropostaReagendamento(models.Model):
    """Pedido de troca de data/turno de uma visita. Só vale depois que a
    outra parte aceita (regras em services/regras.py)."""

    STATUS_PENDENTE = 'pendente'
    STATUS_ACEITA = 'aceita'
    STATUS_RECUSADA = 'recusada'
    STATUS_CANCELADA = 'cancelada'
    STATUS_CHOICES = (
        (STATUS_PENDENTE, 'Aguardando resposta'),
        (STATUS_ACEITA, 'Aceita'),
        (STATUS_RECUSADA, 'Recusada'),
        (STATUS_CANCELADA, 'Cancelada'),
    )

    solicitacao = models.ForeignKey(
        SolicitacaoServico, on_delete=models.CASCADE, related_name='propostas_reagendamento',
    )
    dia_visita = models.ForeignKey(
        DiaVisitaOrcamento, null=True, blank=True, on_delete=models.CASCADE,
        related_name='propostas_reagendamento',
        help_text='Vazio = reagendamento da primeira visita (dia pedido na solicitação).',
    )
    proposto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reagendamentos_propostos',
    )
    nova_data = models.DateField()
    novo_turno = models.CharField(
        max_length=10, choices=SolicitacaoServico.TURNO_CHOICES, default=SolicitacaoServico.TURNO_QUALQUER,
    )
    motivo = models.CharField(max_length=255, blank=True)
    data_anterior = models.DateField()
    turno_anterior = models.CharField(max_length=10, default=SolicitacaoServico.TURNO_QUALQUER)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    criada_em = models.DateTimeField(auto_now_add=True)
    respondida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Proposta de reagendamento'
        verbose_name_plural = 'Propostas de reagendamento'
        ordering = ['-criada_em']

    def __str__(self):
        return f'Reagendar {self.solicitacao_id} para {self.nova_data}'

    @property
    def turno_novo_curto(self):
        return SolicitacaoServico.TURNOS_CURTOS.get(self.novo_turno, '')

    @property
    def turno_anterior_curto(self):
        return SolicitacaoServico.TURNOS_CURTOS.get(self.turno_anterior, '')


class Notificacao(models.Model):
    """Aviso dentro do app (sino da navbar). Também é o ponto único por
    onde passam e-mail, push e WhatsApp no futuro: quem gera um aviso
    chama `services.notificacoes.notificar()` e só ali se decide o canal."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificacoes',
    )
    tipo = models.CharField(max_length=30, default='geral')
    titulo = models.CharField(max_length=120)
    texto = models.CharField(max_length=255, blank=True)
    url = models.CharField(max_length=255, blank=True)
    chave = models.CharField(
        max_length=120, blank=True, db_index=True,
        help_text='Evita avisos repetidos (ex.: lembrete da mesma visita).',
    )
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-criada_em']

    def __str__(self):
        return f'{self.titulo} -> {self.usuario_id}'


class Pagamento(models.Model):
    """Pagamento do orçamento via Pix, com retenção: o dinheiro fica com o
    IFIX até o cliente confirmar que o serviço foi concluído; só então é
    repassado ao profissional, já descontada a comissão. Toda a conversa
    com o provedor (Asaas, Mercado Pago...) fica em `services/pagamentos/`."""

    STATUS_PENDENTE = 'pendente'
    STATUS_RETIDO = 'retido'
    STATUS_LIBERADO = 'liberado'
    STATUS_REEMBOLSADO = 'reembolsado'
    STATUS_EXPIRADO = 'expirado'
    STATUS_CHOICES = (
        (STATUS_PENDENTE, 'Aguardando pagamento do Pix'),
        (STATUS_RETIDO, 'Pago - retido até a conclusão do serviço'),
        (STATUS_LIBERADO, 'Repassado ao profissional'),
        (STATUS_REEMBOLSADO, 'Reembolsado ao cliente'),
        (STATUS_EXPIRADO, 'Pix expirado'),
    )

    solicitacao = models.ForeignKey(
        SolicitacaoServico, on_delete=models.PROTECT, related_name='pagamentos',
    )
    orcamento = models.ForeignKey(
        Orcamento, null=True, blank=True, on_delete=models.SET_NULL, related_name='pagamentos',
    )
    provedor = models.CharField(max_length=20, default='simulado')
    id_externo = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDENTE)

    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    comissao_percentual = models.DecimalField(max_digits=5, decimal_places=2)
    valor_comissao = models.DecimalField(max_digits=10, decimal_places=2)
    valor_profissional = models.DecimalField(max_digits=10, decimal_places=2)

    pix_copia_cola = models.TextField(blank=True)
    pix_qrcode_base64 = models.TextField(blank=True, help_text='Imagem PNG do QR Code, em base64.')
    expira_em = models.DateTimeField(null=True, blank=True)
    pago_em = models.DateTimeField(null=True, blank=True)
    liberado_em = models.DateTimeField(null=True, blank=True)
    reembolsado_em = models.DateTimeField(null=True, blank=True)
    id_repasse = models.CharField(max_length=100, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pagamento (Pix)'
        verbose_name_plural = 'Pagamentos (Pix)'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Pagamento {self.pk} - R$ {self.valor_total} ({self.get_status_display()})'

    @property
    def em_aberto(self):
        return self.status in (self.STATUS_PENDENTE, self.STATUS_RETIDO)


class Favorito(models.Model):
    """Serviço que o cliente marcou como favorito, para achar de novo
    rápido em "Meus favoritos" e usar o botão "Contratar de novo"."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favoritos',
    )
    servico = models.ForeignKey(
        Servico, on_delete=models.CASCADE, related_name='favoritado_por',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Favorito'
        verbose_name_plural = 'Favoritos'
        ordering = ['-criado_em']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'servico'], name='favorito_unico_por_usuario'),
        ]

    def __str__(self):
        return f'{self.usuario.username} favoritou {self.servico}'
