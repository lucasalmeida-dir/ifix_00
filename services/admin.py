from django.contrib import admin

from .models import CategoriaServico, Servico, SolicitacaoServico


@admin.register(CategoriaServico)
class CategoriaServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'subservico', 'categoria', 'profissional', 'preco_min', 'preco_max', 'duracao_minutos', 'disponivel', 'criado_em')
    list_filter = ('categoria', 'disponivel')
    search_fields = ('nome', 'subservico', 'descricao', 'profissional__username')


@admin.register(SolicitacaoServico)
class SolicitacaoServicoAdmin(admin.ModelAdmin):
    list_display = ('servico', 'usuario', 'status', 'criado_em')
    list_filter = ('status',)
    search_fields = ('servico__nome', 'usuario__username')
