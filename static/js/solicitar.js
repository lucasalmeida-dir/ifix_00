(function () {
    var form = document.getElementById('form-solicitar-visita');
    if (!form) {
        return;
    }

    var hoje = form.dataset.hoje;
    var maxAnexos = parseInt(form.dataset.maxAnexos, 10) || 5;
    var inputData = form.querySelector('#id_data_visita');
    var inputUrgente = form.querySelector('#id_urgente');
    var botaoUrgente = document.getElementById('btn-urgente');
    var botaoConfirmar = document.getElementById('btn-confirmar-visita');
    var textoSelecionado = document.getElementById('data-visita-selecionada');

    /* ---------- Calendário: troca de mês sem recarregar ---------- */
    var meses = Array.prototype.slice.call(form.querySelectorAll('.visit-calendar-month'));
    var titulo = document.getElementById('cal-titulo');
    var prev = document.getElementById('cal-prev');
    var next = document.getElementById('cal-next');
    var mesAtual = 0;

    function mostrarMes(indice) {
        mesAtual = Math.max(0, Math.min(meses.length - 1, indice));
        meses.forEach(function (el, i) { el.hidden = i !== mesAtual; });
        titulo.textContent = meses[mesAtual].dataset.titulo;
        prev.disabled = mesAtual === 0;
        prev.classList.toggle('visit-calendar-nav-disabled', mesAtual === 0);
        next.disabled = mesAtual === meses.length - 1;
        next.classList.toggle('visit-calendar-nav-disabled', mesAtual === meses.length - 1);
    }
    prev.addEventListener('click', function () { mostrarMes(mesAtual - 1); });
    next.addEventListener('click', function () { mostrarMes(mesAtual + 1); });
    mostrarMes(0);

    /* ---------- Dia escolhido e urgência ---------- */
    function atualizarResumo() {
        document.querySelectorAll('.visit-calendar-day.is-selected').forEach(function (el) {
            el.classList.remove('is-selected');
        });
        if (inputData.value) {
            var alvo = document.querySelector('.visit-calendar-day[data-data="' + inputData.value + '"]');
            if (alvo) {
                alvo.classList.add('is-selected');
            }
            var p = inputData.value.split('-');
            textoSelecionado.textContent = p[2] + '/' + p[1] + '/' + p[0] + (inputUrgente.checked ? ' (urgente)' : '');
        } else {
            textoSelecionado.textContent = 'nenhum';
        }
        botaoUrgente.classList.toggle('is-on', inputUrgente.checked);
        botaoUrgente.setAttribute('aria-pressed', inputUrgente.checked ? 'true' : 'false');
        botaoConfirmar.disabled = !inputData.value;
    }

    document.querySelectorAll('.visit-calendar-day:not([disabled])').forEach(function (botao) {
        botao.addEventListener('click', function () {
            inputData.value = botao.dataset.data;
            if (inputUrgente.checked && inputData.value !== hoje) {
                inputUrgente.checked = false;
            }
            atualizarResumo();
        });
    });

    botaoUrgente.addEventListener('click', function () {
        inputUrgente.checked = !inputUrgente.checked;
        if (inputUrgente.checked) {
            inputData.value = hoje;
            mostrarMes(0);
        }
        atualizarResumo();
    });
    atualizarResumo();

    /* ---------- Localização do celular (GPS) ---------- */
    var botaoGps = document.getElementById('btn-gps');
    var statusGps = document.getElementById('gps-status');
    var inputLat = form.querySelector('#id_latitude');
    var inputLng = form.querySelector('#id_longitude');

    botaoGps.addEventListener('click', function () {
        if (!navigator.geolocation) {
            statusGps.textContent = 'Seu navegador não permite usar a localização.';
            return;
        }
        botaoGps.disabled = true;
        statusGps.textContent = 'Buscando sua localização...';
        navigator.geolocation.getCurrentPosition(function (pos) {
            inputLat.value = pos.coords.latitude.toFixed(6);
            inputLng.value = pos.coords.longitude.toFixed(6);
            statusGps.textContent = '✔ Localização anexada (precisão de cerca de ' + Math.round(pos.coords.accuracy) + ' m).';
            botaoGps.disabled = false;
            botaoGps.textContent = '📍 Atualizar minha localização';
        }, function (erro) {
            statusGps.textContent = erro.code === 1
                ? 'Permissão negada. Ative a localização do navegador ou informe o endereço abaixo.'
                : 'Não consegui pegar sua localização agora. Informe o endereço abaixo.';
            botaoGps.disabled = false;
        }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 });
    });

    /* ---------- Fotos e vídeo ---------- */
    var inputArquivos = form.querySelector('#id_anexos');
    var areaPrevias = document.getElementById('attach-previews');
    var areaErro = document.getElementById('attach-erro');
    var arquivos = [];

    function sincronizarInput() {
        var dt = new DataTransfer();
        arquivos.forEach(function (f) { dt.items.add(f); });
        inputArquivos.files = dt.files;
    }

    function desenharPrevias() {
        areaPrevias.innerHTML = '';
        arquivos.forEach(function (arquivo, indice) {
            var item = document.createElement('div');
            item.className = 'attach-item';
            var url = URL.createObjectURL(arquivo);
            var midia;
            if (arquivo.type.indexOf('video/') === 0) {
                midia = document.createElement('video');
                midia.src = url;
                midia.muted = true;
                midia.playsInline = true;
            } else {
                midia = document.createElement('img');
                midia.src = url;
                midia.alt = arquivo.name;
            }
            var remover = document.createElement('button');
            remover.type = 'button';
            remover.className = 'attach-remove';
            remover.setAttribute('aria-label', 'Remover ' + arquivo.name);
            remover.textContent = '×';
            remover.addEventListener('click', function () {
                arquivos.splice(indice, 1);
                sincronizarInput();
                desenharPrevias();
            });
            item.appendChild(midia);
            item.appendChild(remover);
            areaPrevias.appendChild(item);
        });
    }

    inputArquivos.addEventListener('change', function () {
        areaErro.textContent = '';
        Array.prototype.forEach.call(inputArquivos.files, function (f) {
            var ehVideo = f.type.indexOf('video/') === 0;
            var ehFoto = f.type.indexOf('image/') === 0;
            if (!ehVideo && !ehFoto) {
                areaErro.textContent = '"' + f.name + '" não é foto nem vídeo.';
            } else if (f.size > (ehVideo ? 30 : 8) * 1024 * 1024) {
                areaErro.textContent = '"' + f.name + '" passa de ' + (ehVideo ? 30 : 8) + ' MB.';
            } else if (arquivos.length >= maxAnexos) {
                areaErro.textContent = 'Máximo de ' + maxAnexos + ' arquivos.';
            } else {
                arquivos.push(f);
            }
        });
        sincronizarInput();
        desenharPrevias();
    });
})();
