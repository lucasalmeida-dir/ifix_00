from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from . import seguranca
from .models import Bloqueio, Denuncia, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'foto_preview', 'user', 'tipo', 'selo_verificacao', 'telefone', 'cep',
        'especialidades_lista', 'termos_aceitos', 'criado_em',
    )
    list_filter = ('tipo', 'verificacao_status', 'termos_aceitos', 'especialidades')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'especialidades__nome', 'cep')
    list_select_related = ('user',)
    filter_horizontal = ('especialidades',)
    # O arquivo bruto não é editável aqui: quem ENVIA é o profissional (área
    # dele); a equipe só confere as prévias abaixo e decide.
    readonly_fields = (
        'previa_documento', 'previa_foto_verificacao', 'verificacao_enviada_em',
        'verificado_em', 'verificado_por',
    )
    actions = ['aprovar_verificacao', 'recusar_verificacao']
    # A verificação vem PRIMEIRO na página: documento e foto enviados, e logo
    # abaixo a situação (escolha "Verificado" e salve para conceder o selo).
    fieldsets = (
        ('Verificação de identidade (selo "Profissional verificado")', {
            'description': 'Confira o documento e a foto abaixo. Para conceder o selo, mude a situação '
                           'para "Verificado" e clique em Salvar. Para negar, escolha "Recusado" e '
                           'escreva o motivo (o profissional recebe um aviso).',
            'fields': (
                'previa_documento', 'previa_foto_verificacao', 'verificacao_status',
                'verificacao_motivo_recusa', 'verificacao_enviada_em', 'verificado_em', 'verificado_por',
            ),
        }),
        ('Conta', {'fields': ('user', 'tipo', 'termos_aceitos', 'termos_aceitos_em')}),
        ('Contato e endereço', {
            'fields': ('telefone', 'cep', 'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'latitude', 'longitude'),
        }),
        ('Perfil', {'fields': ('foto', 'especialidades', 'site_url', 'chave_pix')}),
    )

    @admin.display(description='Especialidades')
    def especialidades_lista(self, obj):
        return obj.especialidades_texto or '—'

    @admin.display(description='Verificação')
    def selo_verificacao(self, obj):
        if not obj.is_profissional:
            return '—'
        cores = {
            Profile.VERIF_VERIFICADO: '#157347',
            Profile.VERIF_PENDENTE: '#b58105',
            Profile.VERIF_RECUSADO: '#b02a37',
            Profile.VERIF_NAO_ENVIADO: '#6c757d',
        }
        return format_html(
            '<b style="color:{}">{}</b>', cores.get(obj.verificacao_status, '#6c757d'),
            obj.get_verificacao_status_display(),
        )

    @admin.display(description='Foto')
    def foto_preview(self, obj):
        if not obj.foto:
            return format_html(
                '<span style="display:inline-flex;align-items:center;justify-content:center;'
                'width:32px;height:32px;border-radius:50%;background:#14315c;color:#fff;'
                'font-weight:700;">{}</span>',
                obj.user.username[:1].upper(),
            )
        return format_html(
            '<img src="{}" style="width:32px;height:32px;border-radius:50%;object-fit:cover;'
            'border:1px solid #d4af37;">',
            obj.foto.url,
        )

    def _previa(self, obj, campo, campo_url):
        arquivo = getattr(obj, campo)
        if not arquivo or not arquivo.name:
            return 'Nada enviado.'
        url = reverse('accounts:arquivo_verificacao', args=[obj.pk, campo_url])
        if arquivo.name.lower().endswith('.pdf'):
            return format_html('<a href="{}" target="_blank" rel="noopener">Abrir PDF do documento</a>', url)
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener"><img src="{0}" '
            'style="max-width:360px;max-height:360px;border:1px solid #ccc;border-radius:6px;"></a>',
            url,
        )

    @admin.display(description='Documento enviado (só a equipe vê)')
    def previa_documento(self, obj):
        return self._previa(obj, 'documento', 'documento')

    @admin.display(description='Foto do rosto enviada (só a equipe vê)')
    def previa_foto_verificacao(self, obj):
        return self._previa(obj, 'foto_verificacao', 'foto')

    def save_model(self, request, obj, form, change):
        """Quem muda a situação pelo formulário também fica registrado
        (quem e quando), como nas ações em lote."""
        if 'verificacao_status' in form.changed_data:
            if obj.verificacao_status == Profile.VERIF_VERIFICADO:
                obj.verificado_em = timezone.now()
                obj.verificado_por = request.user
                obj.verificacao_motivo_recusa = ''
            else:
                obj.verificado_em = None
                obj.verificado_por = None
        super().save_model(request, obj, form, change)
        if 'verificacao_status' in form.changed_data:
            seguranca.avisar_verificacao(obj)

    @admin.action(description='✔ Aprovar verificação (conceder selo)', permissions=['change'])
    def aprovar_verificacao(self, request, queryset):
        total = 0
        for perfil in queryset.filter(tipo=Profile.TIPO_PROFISSIONAL).exclude(verificacao_status=Profile.VERIF_NAO_ENVIADO):
            seguranca.aprovar_verificacao(perfil, request.user)
            total += 1
        ignorados = queryset.count() - total
        if ignorados:
            self.message_user(
                request,
                f'{ignorados} perfil(is) ignorado(s): só profissionais que já enviaram documento e foto '
                'podem ser verificados (situação "Não enviado" não conta).',
                messages.WARNING,
            )
        self.message_user(request, f'{total} profissional(is) verificado(s).', messages.SUCCESS if total else messages.WARNING)

    @admin.action(description='✖ Recusar verificação (usa o motivo preenchido, se houver)', permissions=['change'])
    def recusar_verificacao(self, request, queryset):
        total = 0
        for perfil in queryset.filter(tipo=Profile.TIPO_PROFISSIONAL).exclude(verificacao_status=Profile.VERIF_NAO_ENVIADO):
            seguranca.recusar_verificacao(perfil)
            total += 1
        self.message_user(request, f'{total} verificação(ões) recusada(s).', messages.WARNING)


@admin.register(Denuncia)
class DenunciaAdmin(admin.ModelAdmin):
    list_display = ('id', 'denunciado', 'motivo', 'autor', 'status', 'criada_em')
    list_filter = ('status', 'motivo')
    search_fields = ('denunciado__username', 'autor__username', 'descricao')
    date_hierarchy = 'criada_em'
    readonly_fields = ('autor', 'denunciado', 'solicitacao', 'motivo', 'descricao', 'criada_em', 'resolvida_em')
    fields = readonly_fields + ('status', 'observacao_equipe')
    actions = ['marcar_em_analise', 'marcar_resolvida', 'arquivar', 'bloquear_conta_denunciada', 'reativar_conta_denunciada']

    def has_add_permission(self, request):
        return False

    @admin.action(description='Marcar como em análise')
    def marcar_em_analise(self, request, queryset):
        queryset.update(status=Denuncia.STATUS_ANALISE)

    @admin.action(description='Marcar como resolvida')
    def marcar_resolvida(self, request, queryset):
        queryset.update(status=Denuncia.STATUS_RESOLVIDA, resolvida_em=timezone.now())

    @admin.action(description='Arquivar (sem procedência)')
    def arquivar(self, request, queryset):
        queryset.update(status=Denuncia.STATUS_ARQUIVADA, resolvida_em=timezone.now())

    @admin.action(description='🚫 BLOQUEAR a conta do denunciado (impede login e some do site)', permissions=['change'])
    def bloquear_conta_denunciada(self, request, queryset):
        total = 0
        for denuncia in queryset.select_related('denunciado'):
            alvo = denuncia.denunciado
            if alvo.is_superuser or alvo.is_staff:
                self.message_user(request, f'{alvo.username} é da equipe: bloqueie pelo cadastro de usuários.', messages.ERROR)
                continue
            if alvo.is_active:
                alvo.is_active = False
                alvo.save(update_fields=['is_active'])
                total += 1
            denuncia.status = Denuncia.STATUS_RESOLVIDA
            denuncia.save()
        self.message_user(request, f'{total} conta(s) bloqueada(s).', messages.WARNING)

    @admin.action(description='Reativar a conta do denunciado', permissions=['change'])
    def reativar_conta_denunciada(self, request, queryset):
        total = 0
        for denuncia in queryset.select_related('denunciado'):
            if not denuncia.denunciado.is_active and not denuncia.denunciado.username.startswith('excluido-'):
                denuncia.denunciado.is_active = True
                denuncia.denunciado.save(update_fields=['is_active'])
                total += 1
        self.message_user(request, f'{total} conta(s) reativada(s).', messages.SUCCESS)


@admin.register(Bloqueio)
class BloqueioAdmin(admin.ModelAdmin):
    list_display = ('bloqueador', 'bloqueado', 'criado_em')
    search_fields = ('bloqueador__username', 'bloqueado__username')

    def has_add_permission(self, request):
        return False
