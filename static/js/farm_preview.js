(function () {
    var stage = document.querySelector('[data-farm-preview]');
    if (!stage) return;

    var layer = stage.querySelector('[data-farm-tree-layer]');
    var countEls = document.querySelectorAll('[data-farm-count-display]');
    var tokenCount = stage.querySelector('[data-token-count]');
    var meter = stage.querySelector('[data-token-meter]');
    var decrease = document.querySelector('[data-farm-decrease]');
    var increase = document.querySelector('[data-farm-increase]');
    var max = Number(stage.getAttribute('data-farm-max') || 12);
    var count = Number(stage.getAttribute('data-farm-count') || 0);

    function tree(index) {
        var element = document.createElement('span');
        element.className = 'farm-big-tree tree-slot-' + (index % 6) + ' tree-row-' + Math.floor(index / 6);
        element.setAttribute('aria-hidden', 'true');
        element.appendChild(document.createElement('i'));
        return element;
    }

    function render() {
        layer.innerHTML = '';
        for (var index = 0; index < count; index += 1) layer.appendChild(tree(index));
        countEls.forEach(function (element) { element.textContent = count; });
        if (tokenCount) tokenCount.textContent = count;
        if (meter) meter.style.width = Math.round((count / max) * 100) + '%';
        stage.classList.toggle('is-empty', count === 0);
        stage.setAttribute('data-farm-count', count);
        if (decrease) decrease.disabled = count <= 0;
        if (increase) increase.disabled = count >= max;
    }

    if (decrease) decrease.addEventListener('click', function () {
        count = Math.max(0, count - 1);
        render();
    });
    if (increase) increase.addEventListener('click', function () {
        count = Math.min(max, count + 1);
        render();
    });

    render();
})();