/* Sensação de aplicativo no celular: barra de progresso ao trocar de página
   e animação de carregando nos botões de envio (evita toque duplo). */
(function () {
    var barra = document.createElement('div');
    barra.id = 'page-progress';
    barra.setAttribute('aria-hidden', 'true');
    document.body.appendChild(barra);

    function iniciarBarra() {
        barra.className = 'is-running';
    }

    function pararBarra() {
        barra.className = '';
    }

    // Voltar/avançar do navegador restaura a página do cache: limpa o estado.
    window.addEventListener('pageshow', function () {
        pararBarra();
        document.querySelectorAll('.btn.is-loading').forEach(function (b) {
            b.classList.remove('is-loading');
            b.disabled = false;
        });
    });

    document.addEventListener('click', function (evento) {
        var link = evento.target.closest('a[href]');
        if (!link || evento.defaultPrevented || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.button) {
            return;
        }
        var href = link.getAttribute('href');
        if (!href || href.charAt(0) === '#' || link.target === '_blank' || link.hasAttribute('download')
            || link.hasAttribute('data-bs-toggle') || href.indexOf('javascript:') === 0) {
            return;
        }
        if (link.host && link.host !== window.location.host) {
            return;
        }
        iniciarBarra();
    });

    document.addEventListener('submit', function (evento) {
        var form = evento.target;
        if (evento.defaultPrevented || form.hasAttribute('data-no-loading')) {
            return;
        }
        var botao = evento.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
        iniciarBarra();
        if (botao && botao.classList) {
            botao.classList.add('is-loading');
            // Desabilita só depois que o navegador já leu o formulário
            // (botões com name/value, como as respostas rápidas, precisam ir junto).
            setTimeout(function () { botao.disabled = true; }, 0);
        }
    });

    // Se algo cancelar o envio (validação do servidor via fetch, por ex.), libera de novo.
    window.ifixLiberarBotoes = function (form) {
        pararBarra();
        form.querySelectorAll('.btn.is-loading, button.is-loading').forEach(function (b) {
            b.classList.remove('is-loading');
            b.disabled = false;
        });
    };
})();
