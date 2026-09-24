"""Regras de bloqueio entre usuários e exclusão de conta (LGPD)."""
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import ProtectedError, Q

from django.urls import reverse
from django.utils import timezone

from .models import Bloqueio, Profile


def ids_com_bloqueio(user):
    """IDs de quem tem bloqueio com `user`, nos dois sentidos (quem ele
    bloqueou e quem o bloqueou): nenhum dos dois enxerga ou contrata o outro."""
    if not getattr(user, 'is_authenticated', False):
        return set()
    ids = set()
    pares = Bloqueio.objects.filter(Q(bloqueador=user) | Q(bloqueado=user)).values_list('bloqueador_id', 'bloqueado_id')
    for bloqueador_id, bloqueado_id in pares:
        ids.add(bloqueado_id if bloqueador_id == user.id else bloqueador_id)
    return ids


def existe_bloqueio(a, b):
    return Bloqueio.objects.filter(
        Q(bloqueador=a, bloqueado=b) | Q(bloqueador=b, bloqueado=a),
    ).exists()


def bloquear(bloqueador, bloqueado):
    """Cria o bloqueio e cancela os pedidos ainda pendentes entre os dois
    (os já confirmados continuam, mas sem conversa - ver views)."""
    from services.models import SolicitacaoServico

    Bloqueio.objects.get_or_create(bloqueador=bloqueador, bloqueado=bloqueado)
    SolicitacaoServico.objects.filter(
        Q(usuario=bloqueador, servico__profissional=bloqueado)
        | Q(usuario=bloqueado, servico__profissional=bloqueador),
        status=SolicitacaoServico.STATUS_PENDENTE,
    ).update(status=SolicitacaoServico.STATUS_CANCELADO)


def excluir_conta(user):
    """Exclui a conta e os dados pessoais (LGPD, art. 18, VI).

    Tenta apagar tudo de verdade. Se houver registros que a lei manda
    guardar (ex.: pagamentos), a conta é ANONIMIZADA: perde nome, e-mail,
    telefone, endereço, fotos e documentos, e não consegue mais entrar.
    Retorna 'excluida' ou 'anonimizada'.
    """
    perfil = getattr(user, 'profile', None)
    arquivos = []
    if perfil is not None:
        arquivos = [perfil.foto, perfil.documento, perfil.foto_verificacao]
        arquivos = [(a.storage, a.name) for a in arquivos if a and a.name]

    try:
        with transaction.atomic():
            user.delete()
        resultado = 'excluida'
    except ProtectedError:
        with transaction.atomic():
            user = User.objects.get(pk=user.pk)
            user.username = f'excluido-{user.pk}'
            user.first_name = ''
            user.last_name = ''
            user.email = ''
            user.is_active = False
            user.set_unusable_password()
            user.save()
            perfil = getattr(user, 'profile', None)
            if perfil is not None:
                perfil.telefone = ''
                perfil.cep = ''
                perfil.latitude = None
                perfil.longitude = None
                perfil.endereco = ''
                perfil.numero = ''
                perfil.complemento = ''
                perfil.bairro = ''
                perfil.cidade = ''
                perfil.uf = ''
                perfil.chave_pix = ''
                perfil.site_url = ''
                perfil.foto = ''
                perfil.documento = ''
                perfil.foto_verificacao = ''
                perfil.verificacao_status = perfil.VERIF_NAO_ENVIADO
                perfil.especialidades.clear()
                perfil.save()
        resultado = 'anonimizada'

    for storage, nome in arquivos:
        try:
            storage.delete(nome)
        except Exception:  # noqa: BLE001
            pass
    return resultado


# ---------------------------------------------------------------------------
# Selo "Profissional verificado": decisão da equipe (admin ou página do site)
# ---------------------------------------------------------------------------

def avisar_verificacao(perfil):
    """Avisa o profissional (sino + e-mail) do resultado da análise."""
    from services.notificacoes import notificar

    if perfil.verificacao_status == Profile.VERIF_VERIFICADO:
        notificar(
            perfil.user, 'Você agora é um profissional verificado!',
            'A equipe do IFIX conferiu seus documentos. O selo já aparece no seu perfil.',
            url=reverse('accounts:verificacao'), tipo='verificacao',
            chave=f'verificacao-ok-{perfil.pk}-{perfil.verificado_em:%Y%m%d%H%M%S}',
        )
    elif perfil.verificacao_status == Profile.VERIF_RECUSADO:
        notificar(
            perfil.user, 'Verificação não aprovada',
            perfil.verificacao_motivo_recusa or 'Não foi possível confirmar sua identidade. Envie novamente.',
            url=reverse('accounts:verificacao'), tipo='verificacao',
            chave=f'verificacao-recusa-{perfil.pk}-{timezone.now():%Y%m%d%H%M%S}',
        )


def aprovar_verificacao(perfil, por):
    perfil.verificacao_status = Profile.VERIF_VERIFICADO
    perfil.verificado_em = timezone.now()
    perfil.verificado_por = por
    perfil.verificacao_motivo_recusa = ''
    perfil.save()
    avisar_verificacao(perfil)


def recusar_verificacao(perfil, motivo=''):
    perfil.verificacao_status = Profile.VERIF_RECUSADO
    perfil.verificado_em = None
    perfil.verificado_por = None
    perfil.verificacao_motivo_recusa = (motivo or perfil.verificacao_motivo_recusa or
                                        'Não foi possível conferir o documento/foto enviados. Envie arquivos nítidos.')
    perfil.save()
    avisar_verificacao(perfil)
