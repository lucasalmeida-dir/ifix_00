from django.core.management.base import BaseCommand

from services.notificacoes import gerar_lembretes


class Command(BaseCommand):
    help = (
        'Cria (e envia por e-mail) os lembretes de visita "amanhã" e "hoje" para todos os usuários. '
        'Agende para rodar a cada 30 minutos, por exemplo: */30 * * * * python manage.py enviar_lembretes'
    )

    def handle(self, *args, **options):
        criados = gerar_lembretes()
        self.stdout.write(self.style.SUCCESS(f'{criados} lembrete(s) criado(s).'))
