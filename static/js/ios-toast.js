document.addEventListener('DOMContentLoaded', function () {
    var toasts = document.querySelectorAll('.ios-toast');

    toasts.forEach(function (toast, index) {
        var deAcao = toast.classList.contains('ios-toast-action');

        function fechar() {
            if (toast.classList.contains('is-leaving')) {
                return;
            }
            toast.classList.add('is-leaving');
            setTimeout(function () { toast.remove(); }, 400);
        }

        toast.addEventListener('click', function (evento) {
            // Cliques nos botões (Aceitar / Recusar) não fecham o aviso.
            if (evento.target.closest('button, a, form')) {
                return;
            }
            fechar();
        });
        setTimeout(fechar, (deAcao ? 20000 : 5000) + index * 400);
    });
});
