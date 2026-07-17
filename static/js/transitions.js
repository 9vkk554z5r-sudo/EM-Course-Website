(function () {
    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return;

    document.documentElement.classList.add('motion-ready');
    requestAnimationFrame(function () {
        document.documentElement.classList.add('motion-entered');
    });

    document.addEventListener('click', function (event) {
        var link = event.target.closest && event.target.closest('a[href]');
        if (!link) return;
        if (link.target || link.hasAttribute('download') || link.getAttribute('href').charAt(0) === '#') return;
        var url = new URL(link.href, window.location.href);
        if (url.origin !== window.location.origin) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        document.documentElement.classList.add('motion-leaving');
        setTimeout(function () { window.location.href = link.href; }, 130);
    });
})();
