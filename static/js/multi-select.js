(function () {
    var barra = document.getElementById('multi-bar');
    if (!barra) {
        return;
    }
    var MAX = 5;
    var texto = document.getElementById('multi-bar-texto');
    var link = document.getElementById('multi-bar-link');
    var caixas = Array.prototype.slice.call(document.querySelectorAll('.multi-select-input'));

    function atualizar() {
        var marcadas = caixas.filter(function (c) { return c.checked; });
        caixas.forEach(function (c) {
            c.disabled = !c.checked && marcadas.length >= MAX;
        });
        barra.hidden = marcadas.length < 2;
        if (marcadas.length >= 2) {
            texto.textContent = marcadas.length + ' profissionais escolhidos (máx. ' + MAX + ')';
            link.href = barra.dataset.url + '?' + marcadas.map(function (c) { return 's=' + encodeURIComponent(c.value); }).join('&');
        }
    }
    caixas.forEach(function (c) { c.addEventListener('change', atualizar); });
    atualizar();
})();
