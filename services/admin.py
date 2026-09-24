from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import Truncator

from .models import (
    CategoriaServico,
    Servico,
    SolicitacaoServico,
    AnexoSolicitacao,
    Notificacao,
    Pagamento,
    PropostaReagendamento,
    Orcamento,
    DiaVisitaOrcamento,
    MensagemSolicitacao,
    Avaliacao,
)


def link_excluir(app_label, model_name, obj):
    """Botão vermelho de exclusão rápida direto na listagem, sem precisar
    abrir o registro - usado nos models que o admin mais precisa moderar
    (avaliações e mensagens)."""
    url = reverse(f'admin:{app_label}_{model_name}_delete', args=[obj.pk])
    return format_html('<a class="button" style="background:#ba2121;color:#fff;" href="{}">Excluir</a>', url)


@admin.register(CategoriaServico)
class CategoriaServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'icone', 'slug')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'subservico', 'categoria', 'profissional', 'preco_min', 'preco_max', 'duracao_minutos', 'criado_em', 'acao_excluir')
    list_display_links = ('nome', 'subservico')
    list_filter = ('categoria',)
    search_fields = ('nome', 'subservico', 'descricao', 'profissional__username', 'profissional__first_name', 'profissional__last_name')
    list_select_related = ('categoria', 'profissional')
    date_hierarchy = 'criado_em'
    autocomplete_fields = ('profissional',)

    @admin.display(description='')
    def acao_excluir(self, obj):
        return link_excluir('services', 'servico', obj)


class AvaliacaoInline(admin.StackedInline):
    """Mostra a avaliação (nota + comentário) direto na página da
    solicitação, sem precisar procurá-la em outra tela."""
    model = Avaliacao
    extra = 0
    max_num = 1
    fields = ('estrelas', 'comentario')
    fk_name = 'solicitacao'


class MensagemSolicitacaoInline(admin.TabularInline):
    """Mostra a conversa inteira direto na página da solicitação e deixa
    uma linha em branco pronta - o admin escolhe quem "fala" (cliente ou
    profissional) em Autor e escreve o texto, sem precisar sair daqui
    para mandar uma mensagem."""
    model = MensagemSolicitacao
    extra = 1
    fields = ('autor', 'texto', 'lida', 'criada_em')
    readonly_fields = ('criada_em',)
    autocomplete_fields = ('autor',)


class AnexoSolicitacaoInline(admin.TabularInline):
    model = AnexoSolicitacao
    extra = 0
    readonly_fields = ('criado_em',)


@admin.register(SolicitacaoServico)
class SolicitacaoServicoAdmin(admin.ModelAdmin):
    list_display = ('servico', 'usuario', 'data_visita', 'turno', 'urgente', 'status', 'nota_avaliacao', 'criado_em', 'acao_excluir')
    list_filter = ('status', 'urgente', 'turno', 'servico__categoria')
    search_fields = (
        'servico__nome', 'usuario__username', 'usuario__first_name',
        'servico__profissional__username', 'servico__profissional__first_name',
    )
    list_select_related = ('servico', 'usuario', 'servico__profissional')
    date_hierarchy = 'criado_em'
    autocomplete_fields = ('usuario', 'servico')
    inlines = [AnexoSolicitacaoInline, AvaliacaoInline, MensagemSolicitacaoInline]

    @admin.display(description='Avaliação')
    def nota_avaliacao(self, obj):
        avaliacao = getattr(obj, 'avaliacao', None)
        if not avaliacao:
            return '—'
        return format_html('<span style="color:#d4af37;">{}</span>', avaliacao.get_estrelas_display())

    @admin.display(description='')
    def acao_excluir(self, obj):
        return link_excluir('services', 'solicitacaoservico', obj)


class DiaVisitaOrcamentoInline(admin.TabularInline):
    model = DiaVisitaOrcamento
    extra = 1


@admin.register(Orcamento)
class OrcamentoAdmin(admin.ModelAdmin):
    list_display = ('solicitacao', 'valor', 'visualizado_pelo_cliente', 'criado_em', 'atualizado_em', 'acao_excluir')
    list_filter = ('visualizado_pelo_cliente',)
    search_fields = (
        'solicitacao__servico__nome', 'solicitacao__usuario__username',
        'solicitacao__servico__profissional__username',
    )
    list_select_related = ('solicitacao', 'solicitacao__servico', 'solicitacao__usuario')
    date_hierarchy = 'criado_em'
    autocomplete_fields = ('solicitacao',)
    inlines = [DiaVisitaOrcamentoInline]

    @admin.display(description='')
    def acao_excluir(self, obj):
        return link_excluir('services', 'orcamento', obj)


@admin.register(MensagemSolicitacao)
class MensagemSolicitacaoAdmin(admin.ModelAdmin):
    """Registrado para o admin poder moderar a conversa entre cliente e
    profissional - ver o conteúdo das mensagens, apagar alguma se
    necessário, e também mandar uma mensagem nova (escolhendo a
    solicitação e quem é o autor em "Adicionar mensagem da solicitação")."""
    list_display = ('autor', 'solicitacao', 'texto_resumido', 'lida', 'criada_em', 'acao_excluir')
    list_filter = ('lida',)
    search_fields = ('texto', 'autor__username', 'solicitacao__servico__nome')
    list_select_related = ('autor', 'solicitacao', 'solicitacao__servico')
    autocomplete_fields = ('solicitacao', 'autor')
    date_hierarchy = 'criada_em'
    ordering = ('-criada_em',)

    @admin.display(description='Mensagem')
    def texto_resumido(self, obj):
        return Truncator(obj.texto).chars(80)

    @admin.display(description='')
    def acao_excluir(self, obj):
        return link_excluir('services', 'mensagemsolicitacao', obj)


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    """Aqui o admin vê, de forma rápida, todos os comentários e notas que
    os clientes deixaram para os profissionais - e pode excluir qualquer
    um deles com um clique, sem precisar abrir o registro inteiro."""
    list_display = ('estrelas_display', 'profissional', 'usuario', 'comentario_resumido', 'criado_em', 'acao_excluir')
    list_filter = ('estrelas',)
    search_fields = (
        'comentario', 'profissional__username', 'profissional__first_name',
        'usuario__username', 'usuario__first_name',
    )
    list_select_related = ('profissional', 'usuario', 'solicitacao', 'solicitacao__servico')
    autocomplete_fields = ('solicitacao', 'profissional', 'usuario')
    date_hierarchy = 'criado_em'
    ordering = ('-criado_em',)

    @admin.display(description='Nota')
    def estrelas_display(self, obj):
        return format_html('<span style="color:#d4af37;">{}</span>', obj.get_estrelas_display())

    @admin.display(description='Comentário')
    def comentario_resumido(self, obj):
        return Truncator(obj.comentario).chars(80) if obj.comentario else '—'

    @admin.display(description='')
    def acao_excluir(self, obj):
        return link_excluir('services', 'avaliacao', obj)


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'usuario', 'tipo', 'lida', 'criada_em')
    list_filter = ('tipo', 'lida')
    search_fields = ('titulo', 'texto', 'usuario__username')
    autocomplete_fields = ('usuario',)


@admin.register(PropostaReagendamento)
class PropostaReagendamentoAdmin(admin.ModelAdmin):
    list_display = ('solicitacao', 'proposto_por', 'data_anterior', 'nova_data', 'novo_turno', 'status', 'criada_em')
    list_filter = ('status',)
    search_fields = ('solicitacao__servico__nome', 'proposto_por__username')
    autocomplete_fields = ('solicitacao', 'proposto_por')


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('id', 'solicitacao', 'valor_total', 'valor_comissao', 'valor_profissional', 'status', 'provedor', 'criado_em')
    list_filter = ('status', 'provedor')
    search_fields = ('id_externo', 'solicitacao__servico__nome', 'solicitacao__usuario__username')
    readonly_fields = (
        'solicitacao', 'orcamento', 'provedor', 'id_externo', 'valor_total', 'comissao_percentual',
        'valor_comissao', 'valor_profissional', 'pix_copia_cola', 'pago_em', 'liberado_em',
        'reembolsado_em', 'id_repasse', 'criado_em',
    )
    actions = ['liberar_repasse', 'reembolsar_cliente', 'marcar_como_pago_teste']

    @admin.action(description='Liberar repasse ao profissional')
    def liberar_repasse(self, request, queryset):
        from . import pagamentos
        for pagamento in queryset:
            try:
                pagamentos.liberar_pagamento(pagamento)
            except Exception as exc:  # noqa: BLE001 - mostra o motivo ao suporte
                self.message_user(request, f'Pagamento {pagamento.pk}: {exc}', level='error')

    @admin.action(description='Reembolsar o cliente (valor total)')
    def reembolsar_cliente(self, request, queryset):
        from . import pagamentos
        for pagamento in queryset:
            try:
                pagamentos.reembolsar_pagamento(pagamento)
            except Exception as exc:  # noqa: BLE001
                self.message_user(request, f'Pagamento {pagamento.pk}: {exc}', level='error')

    @admin.action(description='Marcar como pago (somente provedor simulado)')
    def marcar_como_pago_teste(self, request, queryset):
        from . import pagamentos
        for pagamento in queryset.filter(provedor='simulado'):
            pagamentos.confirmar_pagamento(pagamento)
