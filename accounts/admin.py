from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'tipo', 'telefone', 'cep', 'latitude', 'longitude', 'especialidade', 'criado_em')
    list_filter = ('tipo',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'especialidade', 'cep')
