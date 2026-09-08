import time

from django.core.management.base import BaseCommand

from accounts.models import Profile
from accounts.services import CepInvalidoError, consultar_cep


class Command(BaseCommand):
    help = (
        'Recalcula latitude/longitude (via ViaCEP + AwesomeAPI/Nominatim) de todos os '
        'perfis que já têm CEP cadastrado mas ainda estão sem coordenadas. '
        'Útil para corrigir contas criadas antes do cálculo de distância existir, '
        'ou depois de qualquer correção na lógica de geocodificação (use --todos).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Recalcula TODOS os perfis com CEP, mesmo os que já têm coordenadas '
                 '(necessário depois de corrigir a lógica de geocodificação).',
        )

    def handle(self, *args, **options):
        perfis = Profile.objects.exclude(cep='')
        if not options['todos']:
            perfis = perfis.filter(latitude__isnull=True) | perfis.filter(longitude__isnull=True)
        perfis = perfis.order_by('id')

        total = perfis.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nenhum perfil para atualizar.'))
            return

        atualizados = 0
        falhas = 0
        for indice, perfil in enumerate(perfis, start=1):
            try:
                info = consultar_cep(perfil.cep)
            except CepInvalidoError as exc:
                falhas += 1
                self.stdout.write(self.style.WARNING(
                    f'[{perfil.user.username}] CEP {perfil.cep}: {exc}'
                ))
            else:
                if info['latitude'] is None or info['longitude'] is None:
                    falhas += 1
                    self.stdout.write(self.style.WARNING(
                        f'[{perfil.user.username}] CEP {perfil.cep}: não foi possível localizar '
                        f'coordenadas confiáveis (endereço: {info["logradouro"]}, {info["bairro"]}, '
                        f'{info["cidade"]}/{info["uf"]}).'
                    ))
                else:
                    perfil.latitude = info['latitude']
                    perfil.longitude = info['longitude']
                    perfil.save(update_fields=['latitude', 'longitude'])
                    atualizados += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'[{perfil.user.username}] CEP {perfil.cep} -> '
                        f'({info["latitude"]}, {info["longitude"]})'
                    ))

            # Respeita a política de uso do Nominatim (no máx. ~1 requisição/segundo)
            # quando o lote tiver mais perfis pela frente.
            if indice < total:
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluído: {atualizados} atualizado(s), {falhas} sem coordenadas de {total} perfil(is).'
        ))
        if falhas:
            self.stdout.write(
                'Dica: rode "python manage.py debug_cep <CEP>" nos que falharam para ver '
                'exatamente o que cada API está respondendo.'
            )
