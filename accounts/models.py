from django.conf import settings
from django.db import models


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
    endereco = models.CharField(max_length=255, blank=True, verbose_name='Endereço')
    especialidade = models.CharField(
        max_length=255, blank=True,
        verbose_name='Especialidade/Área de atuação',
        help_text='Preenchido apenas para contas de profissionais.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.get_tipo_display()})'

    @property
    def is_profissional(self):
        return self.tipo == self.TIPO_PROFISSIONAL

    @property
    def is_usuario(self):
        return self.tipo == self.TIPO_USUARIO
