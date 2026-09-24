// Adiciona o botão "olhinho" de mostrar/ocultar senha em TODOS os
// campos de senha do site (login, cadastro, redefinição de senha etc.),
// sem precisar alterar cada template individualmente. Carregado tanto no
// layout completo (base.html) quanto no layout mínimo de autenticação
// (base_auth.html).
document.addEventListener('DOMContentLoaded', function () {
    var eyeOpenIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
    var eyeClosedIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a20.3 20.3 0 0 1 5.06-6.06M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a20.3 20.3 0 0 1-3.22 4.44"></path><path d="M14.12 14.12A3 3 0 1 1 9.88 9.88"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';

    document.querySelectorAll('input[type="password"]').forEach(function (input) {
        var wrapper = document.createElement('div');
        wrapper.className = 'password-field-wrapper';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        var toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'password-toggle-btn';
        toggleBtn.setAttribute('aria-label', 'Mostrar senha');
        toggleBtn.innerHTML = eyeOpenIcon;
        wrapper.appendChild(toggleBtn);

        toggleBtn.addEventListener('click', function () {
            var estaOculta = input.type === 'password';
            input.type = estaOculta ? 'text' : 'password';
            toggleBtn.innerHTML = estaOculta ? eyeClosedIcon : eyeOpenIcon;
            toggleBtn.setAttribute('aria-label', estaOculta ? 'Ocultar senha' : 'Mostrar senha');
        });
    });
});
