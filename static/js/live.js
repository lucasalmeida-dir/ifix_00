/* Atualização em tempo real dos balões (menu, barra de baixo, sino e título da
   aba) sem recarregar a página. Consulta o servidor a cada poucos segundos
   enquanto a aba está visível. */
(function () {
    var tituloBase = document.title.replace(/^\(\d+\)\s*/, '');
    var INTERVALO = 12000;
    var timer = null;
    var assinaturaSino = null;
    var pulsoUrl = '/servicos/api/pulso/';

    var sino = document.querySelector('[data-sino-url]');
    if (sino) {
        assinaturaSino = sino.dataset.sinoAssinatura;
    }

    function pintar(nome, valor) {
        document.querySelectorAll('[data-live="' + nome + '"]').forEach(function (el) {
            el.textContent = valor;
            el.hidden = !valor;
        });
    }

    function atualizarSino(assinatura) {
        if (!sino || assinatura === assinaturaSino) {
            return;
        }
        assinaturaSino = assinatura;
        var aberto = sino.querySelector('.dropdown-menu.show');
        if (aberto) {
            return; // não troca a lista enquanto a pessoa está mexendo nela
        }
        fetch(sino.dataset.sinoUrl + '?pagina=' + encodeURIComponent(location.pathname + location.search), { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (dados) {
                var menu = sino.querySelector('.sino-menu');
                if (menu) {
                    menu.innerHTML = dados.html;
                }
            })
            .catch(function () {});
    }

    window.ifixAtualizarPulso = function (p) {
        if (!p) {
            return;
        }
        pintar('mensagens', p.mensagens);
        pintar('orcamentos', p.orcamentos);
        pintar('solicitacoes', p.solicitacoes);
        pintar('sino', p.sino);
        pintar('toggler', (p.mensagens || 0) + (p.orcamentos || 0) + (p.solicitacoes || 0));
        var total = (p.mensagens || 0) + (p.sino || 0);
        document.title = (total ? '(' + total + ') ' : '') + tituloBase;
        atualizarSino(p.sino_assinatura);
    };

    function consultar() {
        if (document.hidden) {
            return;
        }
        fetch(pulsoUrl, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (p) { window.ifixAtualizarPulso(p); })
            .catch(function () {});
    }

    function agendar() {
        clearInterval(timer);
        timer = setInterval(consultar, INTERVALO);
    }

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            consultar();
        }
    });

    agendar();
})();
