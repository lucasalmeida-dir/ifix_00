from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = 'accounts'

urlpatterns = [
    # --- Autenticação (B) ---
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='accounts/login.html'),
        name='login',
    ),  # B1 - Login
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),  # B2 - Logout

    # B3 - Recuperação de senha
    path(
        'senha/recuperar/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset.html',
            email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'senha/recuperar/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'senha/redefinir/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'senha/redefinida/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),

    # --- Área do Usuário (U) ---
    path('cadastro/usuario/', views.register_user, name='register_user'),  # U1
    # --- Área do Profissional (P) ---
    path('cadastro/profissional/', views.register_professional, name='register_professional'),  # P1

    # Comum às duas áreas
    path('perfil/editar/', views.profile_edit, name='profile_edit'),  # U2 / P2
]
