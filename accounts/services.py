"""
Integração com APIs públicas de CEP (ViaCEP, AwesomeAPI, Nominatim/OSM) e
utilitários de geolocalização.

Como nenhuma API brasileira de CEP sozinha resolve tudo que precisamos
(endereço confiável + coordenadas precisas), a consulta segue esta cadeia,
toda com APIs gratuitas e sem chave:

    ENDEREÇO (rua/bairro/cidade/UF):
        1) ViaCEP -> GET https://viacep.com.br/ws/{cep}/json/
           (API de CEP mais estável do Brasil; não traz coordenadas)

    COORDENADAS (latitude/longitude), nesta ordem:
        1) AwesomeAPI CEP -> GET https://cep.awesomeapi.com.br/json/{cep}
           (base própria de coordenadas por CEP, dados do IBGE)
        2) Nominatim (OSM) -> geocodifica o ENDEREÇO acima, em DUAS etapas:
             a) primeiro localiza a CIDADE (pega a bounding box dela)
             b) depois busca a RUA *restrita a essa bounding box*
           Isso evita o erro clássico de "casar" com uma rua de nome
           parecido só que em outra cidade/bairro, o que gerava distâncias
           completamente erradas (dezenas de km de diferença).

    Toda coordenada obtida (de qualquer fonte) passa por uma checagem de
    sanidade: se cair fora da área aproximada do estado (UF) do próprio
    endereço, é descartada e a próxima fonte é tentada. Isso impede que um
    resultado "estapafúrdio" (ex.: match errado de rua em outro estado)
    seja aceito silenciosamente.
"""
import math

import requests

VIACEP_URL = 'https://viacep.com.br/ws/{cep}/json/'
AWESOMEAPI_CEP_URL = 'https://cep.awesomeapi.com.br/json/{cep}'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
# Nominatim exige um User-Agent identificando a aplicação (política de uso).
NOMINATIM_HEADERS = {'User-Agent': 'IFIX-app (contato@ifix.local)'}
TIMEOUT_SEGUNDOS = 6

# Bounding boxes aproximadas (min_lat, max_lat, min_lon, max_lon) por UF.
# Usadas só como checagem de sanidade (descartar coordenadas absurdas),
# não precisam ser cirurgicamente exatas nas bordas.
UF_BBOX = {
    'AC': (-11.2, -7.0, -74.0, -66.5), 'AL': (-10.6, -8.8, -38.3, -35.1),
    'AP': (-1.3, 4.5, -54.9, -49.8), 'AM': (-9.9, 2.3, -73.9, -56.0),
    'BA': (-18.4, -8.5, -46.7, -37.3), 'CE': (-7.9, -2.7, -41.5, -37.2),
    'DF': (-16.1, -15.4, -48.3, -47.3), 'ES': (-21.4, -17.8, -41.9, -39.6),
    'GO': (-19.5, -12.3, -53.3, -45.9), 'MA': (-10.3, -1.0, -48.9, -41.7),
    'MT': (-18.1, -7.3, -61.8, -50.2), 'MS': (-24.1, -17.2, -58.3, -50.9),
    'MG': (-22.9, -14.2, -51.1, -39.9), 'PA': (-9.9, 2.6, -58.9, -46.0),
    'PB': (-8.4, -6.0, -38.8, -34.7), 'PR': (-26.8, -22.5, -54.6, -48.0),
    'PE': (-9.5, -7.3, -41.4, -34.8), 'PI': (-11.0, -2.7, -45.9, -40.4),
    'RJ': (-23.4, -20.7, -44.9, -40.9), 'RN': (-6.9, -4.8, -38.6, -34.9),
    'RS': (-33.8, -27.0, -57.7, -49.6), 'RO': (-13.7, -7.9, -66.8, -59.7),
    'RR': (-1.5, 5.3, -64.9, -58.9), 'SC': (-29.4, -25.9, -53.9, -48.3),
    'SP': (-25.4, -19.8, -53.2, -44.1), 'SE': (-11.6, -9.5, -38.3, -36.4),
    'TO': (-13.5, -5.0, -50.9, -45.6),
}
BRASIL_BBOX = (-33.9, 5.3, -74.0, -34.7)  # fallback quando a UF não é conhecida


class CepInvalidoError(Exception):
    """Erro de validação/consulta de CEP, com mensagem amigável para o usuário."""
    pass


def somente_digitos(valor):
    return ''.join(filter(str.isdigit, valor or ''))


# Alias interno mantido por clareza de leitura dentro deste módulo.
_somente_digitos = somente_digitos


def _coordenada_valida(valor):
    try:
        return float(valor) if valor not in (None, '', 0, '0', '0.0') else None
    except (TypeError, ValueError):
        return None


def _dentro_da_bbox(lat, lon, bbox):
    if lat is None or lon is None or bbox is None:
        return False
    min_lat, max_lat, min_lon, max_lon = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def _coordenada_plausivel(lat, lon, uf):
    """
    Checagem de sanidade: a coordenada precisa cair (pelo menos) dentro do
    Brasil e, se soubermos a UF, idealmente dentro da UF esperada. Isso
    evita aceitar um match errado de geocodificação que caia em outro
    estado (ou fora do país).
    """
    if lat is None or lon is None:
        return False
    if not _dentro_da_bbox(lat, lon, BRASIL_BBOX):
        return False
    bbox_uf = UF_BBOX.get((uf or '').upper())
    if bbox_uf and not _dentro_da_bbox(lat, lon, bbox_uf):
        return False
    return True


def _consultar_awesomeapi(cep_limpo):
    """
    Consulta a AwesomeAPI CEP (base IBGE, coordenadas por CEP) e retorna
    (lat, lon) ou (None, None). Gratuita, sem chave.
    """
    url = AWESOMEAPI_CEP_URL.format(cep=cep_limpo)
    try:
        resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException:
        return None, None
    if resposta.status_code != 200:
        return None, None
    try:
        dados = resposta.json()
    except ValueError:
        return None, None
    lat = _coordenada_valida(dados.get('lat'))
    lon = _coordenada_valida(dados.get('lng'))
    return lat, lon


def _nominatim_get(params_extra):
    """Uma chamada crua ao Nominatim. Retorna a lista de resultados (pode ser vazia)."""
    params = {
        'format': 'json',
        'limit': 1,
        'countrycodes': 'br',
        'addressdetails': 0,
        **params_extra,
    }
    try:
        resposta = requests.get(
            NOMINATIM_URL, params=params, headers=NOMINATIM_HEADERS, timeout=TIMEOUT_SEGUNDOS,
        )
        resposta.raise_for_status()
        return resposta.json() or []
    except (requests.RequestException, ValueError):
        return []


def _bbox_da_cidade(cidade, uf):
    """
    1ª etapa da geocodificação: localiza a CIDADE e devolve sua bounding
    box (min_lat, max_lat, min_lon, max_lon), já convertida do formato do
    Nominatim (que vem como [south, north, west, east] em string).
    Retorna None se não achar.
    """
    if not cidade or not uf:
        return None
    resultados = _nominatim_get({'city': cidade, 'state': uf, 'country': 'Brazil'})
    if not resultados:
        return None
    bb = resultados[0].get('boundingbox')
    if not bb or len(bb) != 4:
        return None
    try:
        south, north, west, east = (float(v) for v in bb)
    except (TypeError, ValueError):
        return None
    return (south, north, west, east)


def _geocodificar_endereco(logradouro, bairro, cidade, uf, cep):
    """
    Geocodifica o endereço em duas etapas para evitar "casar" com uma rua
    de nome parecido em outra cidade/bairro:

        1) resolve a bounding box da cidade (cidade + UF)
        2) busca a rua *restringindo a busca a essa bounding box*
           (view box + bounded=1 do Nominatim)

    Se a etapa 1 falhar, cai para uma busca de bairro/cidade sem bounding
    box como último recurso. Toda coordenada candidata passa pela
    checagem `_coordenada_plausivel` antes de ser aceita.
    """
    bbox_cidade = _bbox_da_cidade(cidade, uf)

    tentativas = []
    if logradouro and cidade and uf:
        base = {'street': logradouro, 'city': cidade, 'state': uf, 'country': 'Brazil'}
        if bbox_cidade:
            south, north, west, east = bbox_cidade
            # Nominatim espera viewbox como "left,top,right,bottom" (lon,lat,lon,lat)
            viewbox = {'viewbox': f'{west},{north},{east},{south}', 'bounded': 1}
            tentativas.append({**base, **viewbox})
        # Sem bounding box (caso a etapa 1 tenha falhado), como reforço.
        tentativas.append(base)

    if bairro and cidade and uf:
        tentativas.append({'q': f'{bairro}, {cidade}, {uf}, Brasil'})

    if cidade and uf:
        tentativas.append({'city': cidade, 'state': uf, 'country': 'Brazil'})

    for params_extra in tentativas:
        resultados = _nominatim_get(params_extra)
        if not resultados:
            continue
        try:
            lat, lon = float(resultados[0]['lat']), float(resultados[0]['lon'])
        except (KeyError, TypeError, ValueError):
            continue
        if _coordenada_plausivel(lat, lon, uf):
            return lat, lon

    return None, None


def _consultar_viacep(cep_limpo):
    """
    Consulta a ViaCEP (https://viacep.com.br/ws/{cep}/json/) e retorna o
    dicionário bruto da API (com logradouro/bairro/localidade/uf), ou
    None se o CEP não existir ou a API estiver indisponível.

    A ViaCEP responde HTTP 200 mesmo para CEP inexistente, só que com o
    corpo `{"erro": true}` — por isso o tratamento abaixo verifica esse
    campo, além do status HTTP.
    """
    url = VIACEP_URL.format(cep=cep_limpo)
    try:
        resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException:
        return None
    if resposta.status_code != 200:
        return None
    try:
        dados = resposta.json()
    except ValueError:
        return None
    if dados.get('erro'):
        return None
    return dados


def consultar_cep(cep):
    """
    Consulta um CEP e retorna um dicionário:

        {
            'cep': '01310930',
            'logradouro': 'Avenida Paulista',
            'bairro': 'Bela Vista',
            'cidade': 'São Paulo',
            'uf': 'SP',
            'latitude': -23.561,   # ou None se não foi possível localizar com confiança
            'longitude': -46.655,  # ou None se não foi possível localizar com confiança
        }

    O endereço vem da ViaCEP. As coordenadas vêm, em ordem de prioridade,
    da AwesomeAPI CEP e, por último, da geocodificação (em 2 etapas, com
    bounding box da cidade) via Nominatim/OpenStreetMap. Toda coordenada
    é validada contra a bounding box da UF antes de ser aceita — nunca
    retornamos uma coordenada "torta" que caia em outro estado.

    Lança CepInvalidoError (com mensagem pronta para exibir ao usuário)
    se o CEP for inválido, não existir ou os serviços de consulta
    estiverem indisponíveis.
    """
    cep_limpo = _somente_digitos(cep)
    if len(cep_limpo) != 8:
        raise CepInvalidoError('Informe um CEP válido com 8 dígitos.')

    dados = _consultar_viacep(cep_limpo)
    if dados is None:
        raise CepInvalidoError('CEP não encontrado ou serviço de consulta indisponível no momento. Tente novamente.')

    logradouro = dados.get('logradouro') or ''
    bairro = dados.get('bairro') or ''
    cidade = dados.get('localidade') or ''
    uf = dados.get('uf') or ''

    # 1ª fonte de coordenadas: AwesomeAPI CEP (base IBGE, por CEP).
    latitude, longitude = _consultar_awesomeapi(cep_limpo)
    if not _coordenada_plausivel(latitude, longitude, uf):
        latitude, longitude = None, None

    # 2ª fonte (último recurso): geocodificação do endereço via Nominatim,
    # em duas etapas (cidade -> rua restrita à bounding box da cidade).
    if latitude is None or longitude is None:
        latitude, longitude = _geocodificar_endereco(logradouro, bairro, cidade, uf, cep_limpo)

    return {
        'cep': dados.get('cep') or cep_limpo,
        'logradouro': logradouro,
        'bairro': bairro,
        'cidade': cidade,
        'uf': uf,
        'latitude': latitude,
        'longitude': longitude,
    }


def calcular_distancia_km(lat1, lon1, lat2, lon2):
    """
    Distância aproximada (linha reta) em km entre duas coordenadas,
    usando a fórmula de Haversine. Retorna None se alguma coordenada
    estiver ausente.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None

    raio_terra_km = 6371.0
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(raio_terra_km * c, 1)
