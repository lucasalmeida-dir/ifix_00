"""Regras de cancelamento e reagendamento do IFIX.

Todos os limites vêm de `settings` (ver IFIX/settings.py), então mudar uma
regra é trocar um número - e os textos mostrados aos usuários são gerados
daqui, para nunca ficarem diferentes do que o sistema realmente aplica.
"""
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .models import DiaVisitaOrcamento, Orcamento, SolicitacaoServico

# Hora em que cada turno começa (usada para contar "faltam X horas").
INICIO_DO_TURNO = {
    SolicitacaoServico.TURNO_MANHA: time(8, 0),
    SolicitacaoServico.TURNO_TARDE: time(12, 0),
    SolicitacaoServico.TURNO_NOITE: time(18, 0),
    SolicitacaoServico.TURNO_QUALQUER: time(8, 0),
}


def antecedencia_cancelamento_horas():
    return getattr(settings, 'IFIX_CANCELAMENTO_ANTECEDENCIA_HORAS', 24)


def antecedencia_reagendamento_horas():
    return getattr(settings, 'IFIX_REAGENDAMENTO_ANTECEDENCIA_HORAS', 12)


def max_reagendamentos():
    return getattr(settings, 'IFIX_REAGENDAMENTO_MAX', 2)


def inicio_da_visita(data, turno):
    hora = INICIO_DO_TURNO.get(turno, time(8, 0))
    return timezone.make_aware(datetime.combine(data, hora))


def horas_ate(momento):
    return (momento - timezone.now()).total_seconds() / 3600


@dataclass
class Visita:
    """Uma visita agendada: a primeira (dia pedido na solicitação) ou uma
    das visitas seguintes previstas no orçamento aprovado."""

    tipo: str  # 'principal' | 'dia'
    obj: object
    solicitacao: SolicitacaoServico
    data: object
    turno: str
    a_caminho_em: Optional[datetime]
    reagendamentos: int

    @property
    def chave(self):
        return f'{self.tipo}-{self.obj.pk}'

    @property
    def inicio(self):
        return inicio_da_visita(self.data, self.turno)

    @property
    def turno_curto(self):
        return SolicitacaoServico.TURNOS_CURTOS.get(self.turno, '')

    @property
    def rotulo(self):
        base = 'Primeira visita' if self.tipo == 'principal' else 'Visita'
        return f'{base} - {self.data:%d/%m/%Y} ({self.turno_curto})'


def visitas_da_solicitacao(solicitacao, apenas_futuras=True):
    """Visitas ainda por acontecer de uma solicitação ativa."""
    visitas = []
    if solicitacao.status != SolicitacaoServico.STATUS_CONFIRMADO:
        return visitas
    hoje = timezone.localdate()

    if not solicitacao.visita_concluida_em and solicitacao.data_visita:
        if not apenas_futuras or solicitacao.data_visita >= hoje:
            visitas.append(Visita(
                'principal', solicitacao, solicitacao, solicitacao.data_visita, solicitacao.turno,
                solicitacao.a_caminho_em, solicitacao.reagendamentos,
            ))

    orcamento = getattr(solicitacao, 'orcamento', None)
    if orcamento and orcamento.status == Orcamento.STATUS_APROVADO:
        for dia in orcamento.dias_visita.filter(status=DiaVisitaOrcamento.STATUS_AGENDADA):
            if not apenas_futuras or dia.data >= hoje:
                visitas.append(Visita(
                    'dia', dia, solicitacao, dia.data, dia.turno, dia.a_caminho_em, dia.reagendamentos,
                ))
    visitas.sort(key=lambda v: v.inicio)
    return visitas


def visita_por_chave(solicitacao, chave):
    for visita in visitas_da_solicitacao(solicitacao):
        if visita.chave == chave:
            return visita
    return None


def visita_de_hoje(solicitacao):
    hoje = timezone.localdate()
    for visita in visitas_da_solicitacao(solicitacao):
        if visita.data == hoje:
            return visita
    return None


# ------------------------------------------------------------------ cancelamento

@dataclass
class AvaliacaoCancelamento:
    pode: bool
    bloqueio: str = ''
    tardio: bool = False
    horas_restantes: Optional[float] = None
    consequencia: str = ''


def avaliar_cancelamento(solicitacao):
    """Diz se a solicitação pode ser cancelada agora e o que acontece."""
    if solicitacao.status == SolicitacaoServico.STATUS_PENDENTE:
        return AvaliacaoCancelamento(
            True, consequencia='Pedido ainda sem resposta: você pode cancelar quando quiser, sem nenhum registro.',
        )
    if solicitacao.status != SolicitacaoServico.STATUS_CONFIRMADO:
        return AvaliacaoCancelamento(False, 'Este pedido já foi encerrado.')

    orcamento = getattr(solicitacao, 'orcamento', None)
    if orcamento and orcamento.status == Orcamento.STATUS_APROVADO:
        return AvaliacaoCancelamento(
            False,
            'O orçamento já foi aprovado, então o serviço está contratado. Você ainda pode reagendar '
            'as visitas; para desistir (ou pedir reembolso de um Pix já pago), fale com o suporte do IFIX.',
        )

    if solicitacao.visita_concluida_em or not solicitacao.data_visita:
        return AvaliacaoCancelamento(
            True,
            consequencia='A visita já aconteceu e não há orçamento aprovado: o cancelamento não gera nenhuma cobrança.',
        )

    horas = horas_ate(inicio_da_visita(solicitacao.data_visita, solicitacao.turno))
    limite = antecedencia_cancelamento_horas()
    if horas >= limite:
        return AvaliacaoCancelamento(
            True, horas_restantes=horas,
            consequencia=f'Faltam mais de {limite} horas para a visita: cancelamento sem custo e sem registro.',
        )
    return AvaliacaoCancelamento(
        True, tardio=True, horas_restantes=horas,
        consequencia=(
            f'Faltam menos de {limite} horas para a visita, então este é um cancelamento tardio: '
            'ele fica registrado no seu histórico e a outra parte é avisada na hora.'
        ),
    )


# ------------------------------------------------------------------ reagendamento

def avaliar_reagendamento(visita):
    """(pode, motivo_do_bloqueio) para uma visita."""
    if visita.reagendamentos >= max_reagendamentos():
        return False, f'Esta visita já foi reagendada {visita.reagendamentos}x (máximo de {max_reagendamentos()}).'
    horas = horas_ate(visita.inicio)
    if horas < antecedencia_reagendamento_horas():
        return False, (
            f'Só é possível pedir reagendamento com pelo menos {antecedencia_reagendamento_horas()} horas '
            'de antecedência. Combine direto pelo chat.'
        )
    return True, ''


def regras_em_texto():
    """Texto exibido nas telas de cancelar/reagendar."""
    return {
        'cancelamento': [
            'Pedido sem resposta do profissional: cancele quando quiser.',
            f'Visita aceita: cancelamento sem custo até {antecedencia_cancelamento_horas()} horas antes; '
            'depois disso conta como cancelamento tardio e fica registrado.',
            'Orçamento aprovado: o serviço está contratado e não é cancelado pelo app (só reagendado). '
            'Reembolso de Pix pago é tratado pelo suporte.',
            'Cancelamentos do profissional também ficam registrados no histórico dele.',
        ],
        'reagendamento': [
            f'Peça com pelo menos {antecedencia_reagendamento_horas()} horas de antecedência da visita.',
            f'Cada visita pode ser reagendada até {max_reagendamentos()} vezes.',
            'A troca só vale depois que a outra pessoa aceitar; até lá, vale a data combinada antes.',
            'Só uma proposta por vez fica aberta em cada pedido.',
        ],
    }
