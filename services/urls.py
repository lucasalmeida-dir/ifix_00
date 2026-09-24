from django.urls import path

from . import views, views_chat, views_fluxo

app_name = 'services'

urlpatterns = [
    # --- Área do Usuário (U3 Opções de serviços) ---
    path('', views.servico_list, name='servico_list'),  # U4 + U5 + U6
    path('mapa/', views.mapa_profissionais, name='mapa_profissionais'),
    path('favoritos/', views.favoritos_lista, name='favoritos_lista'),
    path('categoria/<slug:slug>/', views.servico_list, name='servico_categoria'),  # página de categoria (SEO)
    path(
        'categoria/<slug:slug>/em/<slug:cidade_slug>/',
        views.servico_list, name='servico_categoria_cidade',
    ),  # página categoria+cidade (SEO, ex.: "Eletricista em Campinas")
    path('perfil/<int:pk>/', views.perfil_profissional, name='perfil_profissional'),  # página pública do profissional
    path('<int:pk>/solicitar/', views.servico_solicitar, name='servico_solicitar'),  # U8
    path('<int:pk>/favoritar/', views.favorito_toggle, name='favorito_toggle'),
    path('solicitar-varios/', views.solicitar_varios, name='solicitar_varios'),
    path('pedido/<uuid:grupo>/comparar/', views.comparar_pedido, name='comparar_pedido'),
    path('solicitacao/<int:pk>/escolher/', views.escolher_profissional_pedido, name='escolher_profissional_pedido'),
    path('minhas-solicitacoes/', views.minhas_solicitacoes, name='minhas_solicitacoes'),
    path('mensagens/', views.mensagens, name='mensagens'),

    # --- Área do Profissional (O Opções de serviços -> P3..P9) ---
    path('profissional/meus-servicos/', views.meus_servicos, name='meus_servicos'),
    path('profissional/adicionar/', views.servico_criar, name='servico_criar'),  # P3-P8
    path('profissional/adicionar-em-lote/', views.servico_criar_em_lote, name='servico_criar_em_lote'),
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
    path('avaliacao/<int:pk>/responder/', views.avaliacao_responder, name='avaliacao_responder'),

    # --- Orçamentos (valor real do serviço + dias de visita) ---
    path('solicitacao/<int:pk>/visita-concluida/', views.marcar_visita_concluida, name='marcar_visita_concluida'),
    path('orcamentos/', views.orcamentos_lista, name='orcamentos_lista'),
    path('solicitacao/<int:pk>/orcamento/responder/<str:acao>/', views_fluxo.orcamento_responder, name='orcamento_responder'),

    # --- Combinar e fechar: a caminho, cancelar, reagendar ---
    path('solicitacao/<int:pk>/a-caminho/<str:chave>/', views_fluxo.estou_a_caminho, name='estou_a_caminho'),
    path('solicitacao/<int:pk>/cancelar/', views_fluxo.cancelar_solicitacao, name='cancelar_solicitacao'),
    path('solicitacao/<int:pk>/reagendar/', views_fluxo.reagendar, name='reagendar'),
    path('reagendamento/<int:pk>/<str:acao>/', views_fluxo.responder_reagendamento, name='responder_reagendamento'),

    # --- Tempo real (o navegador consulta a cada poucos segundos) ---
    path('api/pulso/', views_chat.pulso, name='pulso'),
    path('api/sino/', views_chat.sino_menu, name='sino_menu'),
    path('api/conversas/', views_chat.conversas_resumo, name='conversas_resumo'),
    path('solicitacao/<int:pk>/mensagens/novas/', views_chat.mensagens_novas, name='mensagens_novas'),

    # --- Notificações ---
    path('notificacoes/<int:pk>/abrir/', views_fluxo.notificacao_abrir, name='notificacao_abrir'),
    path('notificacoes/lidas/', views_fluxo.notificacoes_lidas, name='notificacoes_lidas'),

    # --- Pagamento por Pix (desligado até haver conta em um provedor) ---
    path('solicitacao/<int:pk>/pagamento/', views_fluxo.pagamento_detalhe, name='pagamento_detalhe'),
    path('solicitacao/<int:pk>/pagamento/iniciar/', views_fluxo.pagamento_iniciar, name='pagamento_iniciar'),
    path('solicitacao/<int:pk>/pagamento/simular/', views_fluxo.pagamento_simular, name='pagamento_simular'),
    path('solicitacao/<int:pk>/pagamento/status/', views_fluxo.pagamento_status, name='pagamento_status'),
    path('webhooks/pix/<slug:provedor>/', views_fluxo.webhook_pix, name='webhook_pix'),
    path('solicitacao/<int:pk>/orcamento/', views.orcamento_detalhe, name='orcamento_detalhe'),
    path('solicitacao/<int:pk>/orcamento/editar/', views.orcamento_editar, name='orcamento_editar'),

    # --- Página do serviço (URL legível, ex.: eletricista-joao-silva-12/) ---
    # Fica por ÚLTIMO de propósito: casa com qualquer segmento único não
    # reconhecido pelas rotas acima, então precisa ser sempre a última
    # tentativa, senão "sequestraria" caminhos como /servicos/mensagens/.
    path('<slug:slug>/', views.servico_detail, name='servico_detail'),  # U7
]
