from django.shortcuts import redirect
from django.urls import reverse


class EspecialidadeObrigatoriaMiddleware:
    """Bloqueia o acesso ao site enquanto o profissional não escolher sua
    Especialidade/Área de atuação.

    Essa etapa fica numa tela própria, exibida logo depois que o
    profissional aperta "Cadastrar" no Cadastro profissional - antes
    até do aceite do Termo de Uso (por isso este middleware roda antes
    do TermosAceiteMiddleware). Intercepta qualquer requisição de um
    profissional autenticado nessa situação e o redireciona para a tela
    de escolha, exceto para a própria tela, o logout e as áreas técnicas
    do site (admin, estáticos e mídia).
    """

    ISENTAS_PREFIXOS = ('/admin/', '/static/', '/media/', '/privacidade/', '/termos-de-uso/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.path.startswith(self.ISENTAS_PREFIXOS):
            especialidade_url = reverse('accounts:escolher_especialidade')
            logout_url = reverse('accounts:logout')
            if request.path not in (especialidade_url, logout_url):
                profile = getattr(request.user, 'profile', None)
                if profile is not None and profile.is_profissional and not profile.especialidades.exists():
                    return redirect(especialidade_url)

        return self.get_response(request)


class TermosAceiteMiddleware:
    """Bloqueia o acesso ao site enquanto o Termo de Uso não for aceito.

    Exigido apenas para contas profissionais, depois que já escolheram a
    Especialidade/Área de atuação (por isso só passa a valer depois do
    EspecialidadeObrigatoriaMiddleware: enquanto a especialidade não
    estiver preenchida, aquele middleware já redireciona antes deste
    entrar em ação). Intercepta qualquer requisição de um profissional
    autenticado nessa situação e o redireciona para a tela de aceite,
    exceto para a própria tela de aceite, o logout e as áreas técnicas
    do site (admin, estáticos e mídia).
    """

    ISENTAS_PREFIXOS = ('/admin/', '/static/', '/media/', '/privacidade/', '/termos-de-uso/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.path.startswith(self.ISENTAS_PREFIXOS):
            aceitar_termos_url = reverse('accounts:aceitar_termos')
            logout_url = reverse('accounts:logout')
            if request.path not in (aceitar_termos_url, logout_url):
                profile = getattr(request.user, 'profile', None)
                if (
                    profile is not None
                    and profile.is_profissional
                    and profile.especialidades.exists()
                    and not profile.termos_aceitos
                ):
                    return redirect(aceitar_termos_url)

        return self.get_response(request)
