"""
Comando de diagnóstico para o cálculo de distância por CEP.

Uso:
    python manage.py debug_cep 22790587
    python manage.py debug_cep 22790587 22790671   # já calcula a distância entre os dois

Mostra, passo a passo, o que cada fonte (ViaCEP, AwesomeAPI, Nominatim)
está devolvendo de verdade no seu ambiente, e o resultado final que o
sistema vai gravar no perfil. Use isto sempre que a distância parecer
errada — o problema quase sempre fica claro aqui (API bloqueada pela
rede/firewall, CEP com endereço genérico, coordenada rejeitada pela
checagem de UF, etc.).
"""
import json

from django.core.management.base import BaseCommand

from accounts import services as s


class Command(BaseCommand):
    help = 'Mostra o que cada API de CEP devolve (bruto) e o resultado final calculado, para diagnóstico.'

    def add_arguments(self, parser):
        parser.add_argument('ceps', nargs='+', type=str, help='Um ou dois CEPs para consultar/comparar.')

    def _linha(self, titulo):
        self.stdout.write('')
        self.stdout.write(self.style.NOTICE(f'--- {titulo} ---'))

    def _debug_um_cep(self, cep):
        cep_limpo = s.somente_digitos(cep)
        self.stdout.write(self.style.NOTICE(f'\n=== CEP informado: {cep} (normalizado: {cep_limpo}) ==='))

        self._linha('ViaCEP (endereço)')
        dados_viacep = s._consultar_viacep(cep_limpo)
        self.stdout.write(json.dumps(dados_viacep, ensure_ascii=False, indent=2))

        uf = (dados_viacep or {}).get('uf', '')

        self._linha('AwesomeAPI CEP (coordenadas por CEP)')
        lat_awe, lon_awe = s._consultar_awesomeapi(cep_limpo)
        plausivel_awe = s._coordenada_plausivel(lat_awe, lon_awe, uf)
        self.stdout.write(f'lat={lat_awe}, lon={lon_awe} | plausível para UF={uf}? {plausivel_awe}')

        self._linha('Nominatim - bounding box da cidade')
        cidade = (dados_viacep or {}).get('localidade', '')
        bbox_cidade = s._bbox_da_cidade(cidade, uf)
        self.stdout.write(f'cidade={cidade!r}, uf={uf!r} -> bbox={bbox_cidade}')

        self._linha('Resultado final (consultar_cep)')
        try:
            info = s.consultar_cep(cep)
            self.stdout.write(self.style.SUCCESS(json.dumps(info, ensure_ascii=False, indent=2)))
        except s.CepInvalidoError as exc:
            info = None
            self.stdout.write(self.style.ERROR(str(exc)))
        return info

    def handle(self, *args, **options):
        ceps = options['ceps']
        resultados = [self._debug_um_cep(cep) for cep in ceps]

        if len(ceps) == 2 and all(resultados):
            a, b = resultados
            self._linha('Distância calculada entre os dois CEPs')
            dist = s.calcular_distancia_km(a['latitude'], a['longitude'], b['latitude'], b['longitude'])
            if dist is None:
                self.stdout.write(self.style.WARNING(
                    'Não foi possível calcular: pelo menos um dos dois CEPs ficou sem coordenadas.'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(f'{dist} km'))
