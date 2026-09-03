from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def estrelas_da_media(media):
    if media is None:
        return ''
    estrelas_preenchidas = min(5, max(0, int(float(media) + 0.5)))
    return '★' * estrelas_preenchidas + '☆' * (5 - estrelas_preenchidas)


class CategoriaServico(models.Model):
    """
    Categorias de serviço (O1 a O5 do diagrama):
    Hidráulica, Elétrica, Desentupimento, Marcenaria e Seu problema (outros).
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
    descricao = models.TextField(verbose_name='Descrição')  # P5
    preco = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Preço (R$)')  # P6
    duracao_minutos = models.PositiveIntegerField(verbose_name='Duração estimada (minutos)')  # P7
    disponivel = models.BooleanField(default=True, verbose_name='Disponível para usuários')  # P9
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Serviço'
        verbose_name_plural = 'Serviços'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.nome} ({self.profissional.username})'

    def get_absolute_url(self):
        return reverse('services:servico_detail', args=[self.pk])


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
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Solicitação de serviço'
        verbose_name_plural = 'Solicitações de serviço'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Solicitação de {self.usuario.username} para {self.servico.nome}'


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
    texto = models.TextField(verbose_name='Mensagem')
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mensagem da solicitação'
        verbose_name_plural = 'Mensagens das solicitações'
        ordering = ['criada_em']

    def __str__(self):
        return f'Mensagem de {self.autor.username} na solicitação {self.solicitacao_id}'


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
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.profissional.username} - {self.estrelas}★'
