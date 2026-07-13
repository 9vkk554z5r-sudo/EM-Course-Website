document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.flash-message').forEach(function (flash) {
        setTimeout(function () {
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            flash.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
            setTimeout(function () {
                if (flash.parentNode) flash.remove();
            }, 260);
        }, 5000);
    });

    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            var button = form.querySelector('button[type="submit"][data-loading-text]');
            if (!button) return;
            button.dataset.originalText = button.textContent;
            button.textContent = button.getAttribute('data-loading-text');
            button.classList.add('is-loading');
        });
    });
});

// Galaxy UI interactions: visual only, keeps original routes/forms intact.
document.addEventListener('DOMContentLoaded', function () {
    var toast = document.querySelector('.galaxy-toast');
    function showGalaxyToast(message) {
        if (!toast) return;
        toast.textContent = message || '该星系即将开放';
        toast.classList.add('is-visible');
        clearTimeout(showGalaxyToast.timer);
        showGalaxyToast.timer = setTimeout(function () {
            toast.classList.remove('is-visible');
        }, 2200);
    }

    document.querySelectorAll('.galaxy-link[aria-disabled="true"]').forEach(function (link) {
        link.addEventListener('click', function (event) {
            event.preventDefault();
            showGalaxyToast(link.getAttribute('data-soon-message') || '该学科星系即将开放');
        });
    });

    document.querySelectorAll('.galaxy-link[data-enter-galaxy="true"]').forEach(function (link) {
        link.addEventListener('click', function (event) {
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            var href = link.getAttribute('href');
            if (!href || href === '#') return;
            event.preventDefault();
            document.body.classList.add('galaxy-warping');
            setTimeout(function () {
                window.location.href = href;
            }, 420);
        });
    });

    document.querySelectorAll('.galaxy-login-form').forEach(function (form) {
        form.addEventListener('submit', function () {
            document.body.classList.add('galaxy-auth-warping');
        });
    });
});
