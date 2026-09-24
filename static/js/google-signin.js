/* Desenha o botão real do "Entrar com Google" (Google Identity Services)
   dentro de #google-signin-btn, só quando esse elemento existe na página
   (ele só existe quando GOOGLE_OAUTH_CLIENT_ID está configurado - ver
   accounts/_google_button.html). O clique devolve um token que é
   confirmado no servidor antes de logar (accounts/services.py). */
(function () {
    var alvo = document.getElementById('google-signin-btn');
    if (!alvo) {
        return;
    }

    function pegarCookie(nome) {
        var encontrado = document.cookie.split('; ').find(function (linha) {
            return linha.indexOf(nome + '=') === 0;
        });
        return encontrado ? decodeURIComponent(encontrado.split('=')[1]) : '';
    }

    function enviarParaOServidor(credential) {
        var form = document.createElement('form');
        form.method = 'POST';
        form.action = '/conta/google/';
        form.style.display = 'none';

        var csrf = document.createElement('input');
        csrf.name = 'csrfmiddlewaretoken';
        csrf.value = pegarCookie('csrftoken');
        form.appendChild(csrf);

        var token = document.createElement('input');
        token.name = 'credential';
        token.value = credential;
        form.appendChild(token);

        var next = document.createElement('input');
        next.name = 'next';
        next.value = alvo.dataset.next || '';
        form.appendChild(next);

        document.body.appendChild(form);
        form.submit();
    }

    // Cookies (LGPD): o script do Google só é carregado com o consentimento
    // guardado pelo aviso de cookies (localStorage 'ifix_cookies' = 'todos').
    function consentimento() {
        try { return localStorage.getItem('ifix_cookies') === 'todos'; } catch (e) { return false; }
    }

    function carregarGoogle() {
        var script = document.createElement('script');
        script.src = 'https://accounts.google.com/gsi/client';
        script.async = true;
        script.defer = true;
        script.onload = function () {
            if (!window.google || !window.google.accounts || !window.google.accounts.id) {
                return;
            }
            window.google.accounts.id.initialize({
                client_id: alvo.dataset.clientId,
                callback: function (resposta) { enviarParaOServidor(resposta.credential); },
            });
            window.google.accounts.id.renderButton(alvo, {
                theme: 'outline', size: 'large', width: alvo.offsetWidth || 320, text: 'continue_with',
            });
        };
        document.head.appendChild(script);
    }

    if (consentimento()) {
        carregarGoogle();
        return;
    }

    var botao = document.createElement('button');
    botao.type = 'button';
    botao.className = 'auth-social-btn';
    botao.innerHTML = '<span class="auth-social-icon">G</span> Continuar com Google';
    botao.title = 'Ao continuar você permite cookies do Google (ver Política de Privacidade)';
    botao.addEventListener('click', function () {
        try { localStorage.setItem('ifix_cookies', 'todos'); } catch (e) {}
        var aviso = document.getElementById('cookie-banner');
        if (aviso) { aviso.hidden = true; }
        botao.remove();
        carregarGoogle();
    });
    alvo.appendChild(botao);
})();
