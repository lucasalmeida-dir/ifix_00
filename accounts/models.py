import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .storage import armazenamento_privado


def caminho_verificacao(instance, filename):
    """Nome aleatório: o endereço do arquivo não pode ser adivinhado."""
    extensao = os.path.splitext(filename)[1].lower()
    return f'verificacao/{uuid.uuid4().hex}{extensao}'


class Profile(models.Model):
    """
    Estende o User padrão do Django com o tipo de conta
    (Usuário ou Profissional), conforme os dois ramos do diagrama:
    "Área do Usuário" e "Área do Profissional".
    """

    TIPO_USUARIO = 'usuario'
    TIPO_PROFISSIONAL = 'profissional'
    TIPO_CHOICES = (
        (TIPO_USUARIO, 'Usuário'),
        (TIPO_PROFISSIONAL, 'Profissional'),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, verbose_name='Tipo de conta')
    telefone = models.CharField(max_length=20, blank=True, verbose_name='Telefone')
    cep = models.CharField(max_length=9, blank=True, verbose_name='CEP')
    latitude = models.FloatField(null=True, blank=True, verbose_name='Latitude')
    longitude = models.FloatField(null=True, blank=True, verbose_name='Longitude')
    endereco = models.CharField(max_length=255, blank=True, verbose_name='Endereço')
    numero = models.CharField(max_length=10, blank=True, verbose_name='Número')
    complemento = models.CharField(max_length=100, blank=True, verbose_name='Complemento')
    bairro = models.CharField(max_length=120, blank=True, verbose_name='Bairro')
    cidade = models.CharField(max_length=120, blank=True, verbose_name='Cidade')
    uf = models.CharField(max_length=2, blank=True, verbose_name='UF')
    cidade_slug = models.SlugField(
        max_length=140, blank=True, db_index=True,
        help_text='Gerado sozinho a partir da cidade - usado nas páginas "Eletricista em Campinas".',
    )
    foto = models.FileField(upload_to='fotos_perfil/', blank=True, verbose_name='Foto de perfil')
    especialidades = models.ManyToManyField(
        'services.CategoriaServico',
        blank=True,
        related_name='profissionais',
        verbose_name='Especialidades/Áreas de atuação',
        help_text='Preenchido apenas para contas de profissionais. Um profissional pode atuar em mais de uma área.',
    )
    chave_pix = models.CharField(
        max_length=140, blank=True, verbose_name='Chave Pix para receber',
        help_text='Só para profissionais: chave (CPF, e-mail, telefone ou aleatória) onde o IFIX repassa o valor dos serviços concluídos.',
    )
    termos_aceitos = models.BooleanField(
        default=False,
        verbose_name='Termo de Condições de Uso aceito',
        help_text='Indica se o usuário já leu e aceitou o Termo de Condições de Uso e Prestação de Serviços.',
    )
    termos_aceitos_em = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Data/hora do aceite do Termo',
    )
    site_url = models.URLField(
        max_length=200, blank=True, verbose_name='Link da sua página/site (opcional)',
        help_text='Só profissionais. Aparece na sua página pública (ex.: https://meusite.com.br).',
    )

    # --- Verificação de identidade (selo "Profissional verificado") ---
    # O profissional só ENVIA foto + documento; quem concede o selo é a
    # equipe do IFIX, pelo painel administrativo (nunca pelo próprio usuário).
    VERIF_NAO_ENVIADO = 'nao_enviado'
    VERIF_PENDENTE = 'pendente'
    VERIF_VERIFICADO = 'verificado'
    VERIF_RECUSADO = 'recusado'
    VERIF_CHOICES = (
        (VERIF_NAO_ENVIADO, 'Não enviado'),
        (VERIF_PENDENTE, 'Aguardando análise'),
        (VERIF_VERIFICADO, 'Verificado'),
        (VERIF_RECUSADO, 'Recusado'),
    )
    documento = models.FileField(
        upload_to=caminho_verificacao, storage=armazenamento_privado, blank=True,
        verbose_name='Documento com foto (RG/CNH)',
    )
    foto_verificacao = models.FileField(
        upload_to=caminho_verificacao, storage=armazenamento_privado, blank=True,
        verbose_name='Foto do rosto (selfie)',
    )
    verificacao_status = models.CharField(
        max_length=12, choices=VERIF_CHOICES, default=VERIF_NAO_ENVIADO,
        verbose_name='Situação da verificação',
    )
    verificacao_enviada_em = models.DateTimeField(null=True, blank=True, verbose_name='Enviado em')
    verificado_em = models.DateTimeField(null=True, blank=True, verbose_name='Verificado em')
    verificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='verificacoes_feitas', verbose_name='Verificado por',
    )
    verificacao_motivo_recusa = models.TextField(blank=True, verbose_name='Motivo da recusa')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.get_tipo_display()})'

    def save(self, *args, **kwargs):
        self.cidade_slug = slugify(self.cidade) if self.cidade else ''
        super().save(*args, **kwargs)

    @property
    def is_profissional(self):
        return self.tipo == self.TIPO_PROFISSIONAL

    @property
    def verificado(self):
        return self.is_profissional and self.verificacao_status == self.VERIF_VERIFICADO

    @property
    def is_usuario(self):
        return self.tipo == self.TIPO_USUARIO

    @property
    def tem_localizacao(self):
        """Indica se há coordenadas (obtidas via CEP) para calcular distância."""
        return self.latitude is not None and self.longitude is not None

    @property
    def especialidades_texto(self):
        """Nomes das especialidades já escolhidas, separados por vírgula -
        usado no admin e em qualquer lugar que precise de um resumo em texto."""
        return ', '.join(self.especialidades.values_list('nome', flat=True))


class Bloqueio(models.Model):
    """Um usuário bloqueia outro: some das buscas um do outro, não dá para
    pedir serviço nem trocar mensagens enquanto o bloqueio existir."""

    bloqueador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bloqueios_feitos',
    )
    bloqueado = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bloqueios_recebidos',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bloqueio entre usuários'
        verbose_name_plural = 'Bloqueios entre usuários'
        constraints = [
            models.UniqueConstraint(fields=['bloqueador', 'bloqueado'], name='bloqueio_unico'),
        ]

    def __str__(self):
        return f'{self.bloqueador} bloqueou {self.bloqueado}'


class Denuncia(models.Model):
    """Denúncia de um usuário contra outro, analisada pela equipe no admin."""

    MOTIVO_GOLPE = 'golpe'
    MOTIVO_COMPORTAMENTO = 'comportamento'
    MOTIVO_NAO_REALIZADO = 'nao_realizado'
    MOTIVO_PERFIL_FALSO = 'perfil_falso'
    MOTIVO_SPAM = 'spam'
    MOTIVO_OUTRO = 'outro'
    MOTIVO_CHOICES = (
        (MOTIVO_GOLPE, 'Golpe ou fraude'),
        (MOTIVO_COMPORTAMENTO, 'Comportamento ofensivo ou assédio'),
        (MOTIVO_NAO_REALIZADO, 'Serviço não realizado / não compareceu'),
        (MOTIVO_PERFIL_FALSO, 'Perfil falso'),
        (MOTIVO_SPAM, 'Spam ou propaganda'),
        (MOTIVO_OUTRO, 'Outro'),
    )
    STATUS_ABERTA = 'aberta'
    STATUS_ANALISE = 'em_analise'
    STATUS_RESOLVIDA = 'resolvida'
    STATUS_ARQUIVADA = 'arquivada'
    STATUS_CHOICES = (
        (STATUS_ABERTA, 'Aberta'),
        (STATUS_ANALISE, 'Em análise'),
        (STATUS_RESOLVIDA, 'Resolvida'),
        (STATUS_ARQUIVADA, 'Arquivada'),
    )

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='denuncias_feitas',
        verbose_name='Denunciante',
    )
    denunciado = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='denuncias_recebidas',
        verbose_name='Denunciado',
    )
    solicitacao = models.ForeignKey(
        'services.SolicitacaoServico', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='denuncias', verbose_name='Solicitação relacionada',
    )
    motivo = models.CharField(max_length=15, choices=MOTIVO_CHOICES)
    descricao = models.TextField(verbose_name='O que aconteceu', max_length=2000)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ABERTA)
    observacao_equipe = models.TextField(blank=True, verbose_name='Observações da equipe (internas)')
    criada_em = models.DateTimeField(auto_now_add=True)
    resolvida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Denúncia'
        verbose_name_plural = 'Denúncias'
        ordering = ['-criada_em']

    def __str__(self):
        return f'Denúncia #{self.pk}: {self.denunciado} ({self.get_motivo_display()})'

    def save(self, *args, **kwargs):
        if self.status in (self.STATUS_RESOLVIDA, self.STATUS_ARQUIVADA) and not self.resolvida_em:
            self.resolvida_em = timezone.now()
        super().save(*args, **kwargs)
