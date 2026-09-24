(function () {
    var form = document.getElementById('message-form');
    var caixaMensagens = document.getElementById('conversation-messages');

    /* =====================================================================
       ANEXOS E ÁUDIO (só quando o formulário de envio existe)
       ===================================================================== */
    var limparAnexo = function () {};
    if (form) {
        var inputArquivo = form.querySelector('.chat-file-input');
        var caixa = document.getElementById('chat-attach-preview');
        var nome = document.getElementById('chat-attach-nome');
        var player = document.getElementById('chat-attach-audio');
        var remover = document.getElementById('chat-attach-remover');
        var botaoMic = document.getElementById('chat-mic');
        var dicaGravando = document.getElementById('chat-rec-hint');
        var gravador = null;
        var pedacos = [];
        var fluxo = null;

        var mostrarAnexo = function (arquivo) {
            caixa.hidden = false;
            nome.textContent = arquivo.name;
            if (arquivo.type.indexOf('audio/') === 0 || /\.(webm|ogg|m4a|mp4|wav|mp3|aac)$/i.test(arquivo.name)) {
                player.hidden = false;
                player.src = URL.createObjectURL(arquivo);
            } else {
                player.hidden = true;
                player.removeAttribute('src');
            }
        };

        limparAnexo = function () {
            var dt = new DataTransfer();
            inputArquivo.files = dt.files;
            caixa.hidden = true;
            player.hidden = true;
            player.removeAttribute('src');
            nome.textContent = '';
        };

        inputArquivo.addEventListener('change', function () {
            if (inputArquivo.files.length) {
                mostrarAnexo(inputArquivo.files[0]);
            } else {
                limparAnexo();
            }
        });
        remover.addEventListener('click', limparAnexo);

        var extensaoPara = function (tipo) {
            if (tipo.indexOf('webm') !== -1) { return '.webm'; }
            if (tipo.indexOf('ogg') !== -1) { return '.ogg'; }
            if (tipo.indexOf('mp4') !== -1) { return '.m4a'; }
            return '.webm';
        };

        botaoMic.addEventListener('click', function () {
            if (gravador && gravador.state === 'recording') {
                gravador.stop();
                return;
            }
            if (!navigator.mediaDevices || !window.MediaRecorder) {
                alert('Seu navegador não permite gravar áudio aqui. Use um navegador atualizado com HTTPS.');
                return;
            }
            navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
                fluxo = stream;
                pedacos = [];
                gravador = new MediaRecorder(stream);
                gravador.addEventListener('dataavailable', function (e) {
                    if (e.data.size) { pedacos.push(e.data); }
                });
                gravador.addEventListener('stop', function () {
                    fluxo.getTracks().forEach(function (t) { t.stop(); });
                    botaoMic.classList.remove('is-recording');
                    dicaGravando.hidden = true;
                    var tipo = gravador.mimeType || 'audio/webm';
                    var arquivo = new File(pedacos, 'audio' + extensaoPara(tipo), { type: tipo });
                    var dt = new DataTransfer();
                    dt.items.add(arquivo);
                    inputArquivo.files = dt.files;
                    mostrarAnexo(arquivo);
                });
                gravador.start();
                botaoMic.classList.add('is-recording');
                dicaGravando.hidden = false;
            }).catch(function () {
                alert('Não consegui acessar o microfone. Permita o acesso no navegador e tente de novo.');
            });
        });
    }

    if (!caixaMensagens || !caixaMensagens.dataset.novasUrl) {
        return;
    }

    /* =====================================================================
       TEMPO REAL: mensagens novas, "lido" (✓✓) e lista de conversas
       ===================================================================== */
    var urlNovas = caixaMensagens.dataset.novasUrl;
    var urlResumo = caixaMensagens.dataset.resumoUrl;
    var ativa = caixaMensagens.dataset.ativa;
    var lista = document.querySelector('.chat-list');
    var chipNovas = null;
    var atraso = 2500;
    var contador = 0;
    var ocupado = false;

    function linhas() {
        return caixaMensagens.querySelectorAll('.chat-bubble-row[data-id]');
    }

    function ultimoId() {
        var l = linhas();
        return l.length ? l[l.length - 1].dataset.id : 0;
    }

    function ultimaData() {
        var l = linhas();
        return l.length ? l[l.length - 1].dataset.data : '';
    }

    function idsPendentes() {
        var ids = [];
        caixaMensagens.querySelectorAll('.chat-bubble-row[data-mine="1"]').forEach(function (linha) {
            var visto = linha.querySelector('.chat-ticks');
            if (visto && !visto.classList.contains('is-read')) {
                ids.push(linha.dataset.id);
            }
        });
        return ids;
    }

    function pertoDoFim() {
        return caixaMensagens.scrollHeight - caixaMensagens.scrollTop - caixaMensagens.clientHeight < 140;
    }

    function irParaOFim() {
        caixaMensagens.scrollTop = caixaMensagens.scrollHeight;
        if (chipNovas) {
            chipNovas.hidden = true;
        }
    }

    function mostrarChip() {
        if (!chipNovas) {
            chipNovas = document.createElement('button');
            chipNovas.type = 'button';
            chipNovas.className = 'chat-new-chip';
            chipNovas.textContent = 'Novas mensagens ↓';
            chipNovas.addEventListener('click', irParaOFim);
            caixaMensagens.parentNode.insertBefore(chipNovas, caixaMensagens.nextSibling);
        }
        chipNovas.hidden = false;
    }

    caixaMensagens.addEventListener('scroll', function () {
        if (chipNovas && pertoDoFim()) {
            chipNovas.hidden = true;
        }
    });

    function marcarLidas(ids) {
        ids.forEach(function (id) {
            var linha = caixaMensagens.querySelector('.chat-bubble-row[data-id="' + id + '"] .chat-ticks');
            if (linha) {
                linha.classList.add('is-read');
                linha.innerHTML = '&#10003;&#10003;';
                linha.title = 'Lida';
            }
        });
    }

    function atualizarLista() {
        if (!lista || !urlResumo) {
            return Promise.resolve();
        }
        return fetch(urlResumo + '?ativa=' + encodeURIComponent(ativa), { credentials: 'same-origin' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (dados) {
                if (!dados) { return; }
                var holder = document.createElement('div');
                var alvo = lista.querySelectorAll('.chat-list-item');
                var mudou = alvo.length !== dados.conversas.length;
                dados.conversas.forEach(function (c, i) {
                    holder.innerHTML = c.html.trim();
                    var novo = holder.firstElementChild;
                    var atual = lista.querySelector('.chat-list-item[data-conversa="' + c.pk + '"]');
                    if (!atual || atual.outerHTML !== novo.outerHTML) {
                        mudou = true;
                    }
                });
                if (mudou) {
                    lista.innerHTML = dados.conversas.map(function (c) { return c.html; }).join('');
                }
                window.ifixAtualizarPulso && window.ifixAtualizarPulso(dados.pulso);
            });
    }

    function consultar() {
        if (ocupado) {
            return Promise.resolve();
        }
        ocupado = true;
        var url = urlNovas + '?depois=' + ultimoId()
            + '&pendentes=' + idsPendentes().join(',')
            + '&data_ultima=' + encodeURIComponent(ultimaData())
            + '&visivel=' + (document.hidden ? '0' : '1');
        return fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
            .then(function (r) {
                if (!r.ok) { throw new Error('http ' + r.status); }
                return r.json();
            })
            .then(function (dados) {
                atraso = 2500;
                var estavaNoFim = pertoDoFim();
                var chegouDoOutro = false;
                dados.mensagens.forEach(function (m) {
                    var holder = document.createElement('div');
                    holder.innerHTML = m.html.trim();
                    while (holder.firstChild) {
                        caixaMensagens.appendChild(holder.firstChild);
                    }
                    if (!m.minha) { chegouDoOutro = true; }
                });
                if (dados.mensagens.length) {
                    var vazio = caixaMensagens.querySelector('p.text-muted');
                    if (vazio) { vazio.remove(); }
                    if (estavaNoFim || !chegouDoOutro) {
                        irParaOFim();
                    } else {
                        mostrarChip();
                    }
                }
                marcarLidas(dados.lidas);
                window.ifixAtualizarPulso && window.ifixAtualizarPulso(dados.pulso);
                if (dados.status !== 'confirmado' && form) {
                    location.reload(); // conversa foi encerrada: recarrega para refletir
                }
            })
            .catch(function () {
                atraso = Math.min(atraso * 2, 15000);
            })
            .then(function () { ocupado = false; });
    }

    function ciclo() {
        setTimeout(function () {
            if (!document.hidden) {
                contador += 1;
                consultar().then(function () {
                    if (contador % 3 === 0) { return atualizarLista(); }
                }).then(ciclo, ciclo);
            } else {
                ciclo();
            }
        }, atraso);
    }

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            consultar();
            atualizarLista();
        }
    });
    ciclo();

    /* =====================================================================
       ENVIO SEM RECARREGAR A PÁGINA
       ===================================================================== */
    if (form) {
        var areaErro = document.getElementById('chat-envio-erro');
        if (!areaErro) {
            areaErro = document.createElement('div');
            areaErro.id = 'chat-envio-erro';
            areaErro.className = 'chat-send-error';
            areaErro.hidden = true;
            form.insertBefore(areaErro, form.querySelector('.chat-input-bar'));
        }
        var campoTexto = form.querySelector('textarea');

        form.addEventListener('submit', function (evento) {
            if (!window.fetch || !window.FormData) {
                return; // navegador antigo: envio normal
            }
            evento.preventDefault();
            var texto = campoTexto ? campoTexto.value.trim() : '';
            var temArquivo = form.querySelector('.chat-file-input').files.length > 0;
            if (!texto && !temArquivo) {
                return;
            }
            var dados = new FormData(form);
            areaErro.hidden = true;
            var botaoEnviar = form.querySelector('.btn-send');
            botaoEnviar.disabled = true;
            fetch(form.getAttribute('action') || location.href, {
                method: 'POST',
                body: dados,
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'fetch' },
            }).then(function (r) {
                return r.json().catch(function () { return { ok: false, erros: ['Erro ao enviar.'] }; })
                    .then(function (j) { return { ok: r.ok && j.ok, dados: j }; });
            }).then(function (res) {
                if (res.ok) {
                    if (campoTexto) {
                        campoTexto.value = '';
                        campoTexto.style.height = 'auto';
                    }
                    limparAnexo();
                    return consultar().then(function () { irParaOFim(); });
                }
                areaErro.textContent = (res.dados.erros || ['Não foi possível enviar.']).join(' ');
                areaErro.hidden = false;
            }).catch(function () {
                areaErro.textContent = 'Sem conexão. Tente de novo em instantes.';
                areaErro.hidden = false;
            }).then(function () {
                botaoEnviar.disabled = false;
            });
        });
    }
})();
