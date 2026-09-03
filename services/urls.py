from django.urls import path

from . import views

app_name = 'services'

urlpatterns = [
    # --- Área do Usuário (U3 Opções de serviços) ---
    path('', views.servico_list, name='servico_list'),  # U4 + U5 + U6
    path('<int:pk>/', views.servico_detail, name='servico_detail'),  # U7
    path('<int:pk>/solicitar/', views.servico_solicitar, name='servico_solicitar'),  # U8
    path('minhas-solicitacoes/', views.minhas_solicitacoes, name='minhas_solicitacoes'),
    path('mensagens/', views.mensagens, name='mensagens'),

    # --- Área do Profissional (O Opções de serviços -> P3..P9) ---
    path('profissional/meus-servicos/', views.meus_servicos, name='meus_servicos'),
    path('profissional/adicionar/', views.servico_criar, name='servico_criar'),  # P3-P8
    path('profissional/<int:pk>/editar/', views.servico_editar, name='servico_editar'),
    path('profissional/<int:pk>/excluir/', views.servico_excluir, name='servico_excluir'),
    path('profissional/solicitacoes/', views.solicitacoes_recebidas, name='solicitacoes_recebidas'),
    path(
        'profissional/solicitacoes/<int:pk>/<str:acao>/',
        views.atualizar_status_solicitacao,
        name='atualizar_status_solicitacao',
    ),
    path('solicitacao/<int:pk>/conversa/', views.conversa_solicitacao, name='conversa_solicitacao'),
    path('solicitacao/<int:pk>/concluir/', views.concluir_solicitacao, name='concluir_solicitacao'),
    path('solicitacao/<int:pk>/avaliar/', views.avaliar_solicitacao, name='avaliar_solicitacao'),
]
