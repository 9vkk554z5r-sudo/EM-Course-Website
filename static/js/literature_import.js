(function () {
    var root = document.querySelector('[data-import-console]');
    if (!root || !window.LiteratureStore || !window.LiteratureParsers) return;

    var status = root.querySelector('[data-import-status]');
    var countEl = root.querySelector('[data-paper-count]');

    function setMessage(text, tone) {
        if (!status) return;
        status.setAttribute('data-tone', tone || 'neutral');
        var old = status.querySelector('.import-message');
        if (old) old.remove();
        var message = document.createElement('span');
        message.className = 'import-message';
        message.textContent = text;
        status.appendChild(message);
    }

    function syncDashboardImportMetric(added) {
        var delta = Math.max(0, parseInt(added, 10) || 0);
        if (!delta) return;
        try {
            var key = 'lsca.importedPapers.count';
            var current = parseInt(window.localStorage.getItem(key), 10) || 0;
            window.localStorage.setItem(key, String(current + delta));
            window.dispatchEvent(new CustomEvent('lsca:literature-imported', {detail: {added: delta}}));
        } catch (error) {}
    }

    function refreshCount() {
        var count = LiteratureStore.getAll().length;
        if (countEl) countEl.textContent = count + ' 篇文献';
    }

    function fileText(input) {
        return new Promise(function (resolve, reject) {
            var file = input && input.files && input.files[0];
            if (!file) return resolve('');
            var reader = new FileReader();
            reader.onload = function () { resolve(String(reader.result || '')); };
            reader.onerror = function () { reject(reader.error); };
            reader.readAsText(file, 'utf-8');
        });
    }

    function handleResult(papers, source) {
        if (!papers.length) {
            setMessage('没有解析到可用文献，请检查输入格式。', 'error');
            return;
        }
        var result = LiteratureStore.upsertMany(papers, source);
        refreshCount();
        syncDashboardImportMetric(result.added);
        setMessage('导入完成：新增 ' + result.added + ' 篇，更新 ' + result.updated + ' 篇。', 'success');
    }

    root.querySelectorAll('[data-import-tab]').forEach(function (tab) {
        tab.addEventListener('click', function () {
            var name = tab.getAttribute('data-import-tab');
            root.querySelectorAll('[data-import-tab]').forEach(function (item) {
                item.classList.toggle('active', item === tab);
            });
            root.querySelectorAll('[data-import-panel]').forEach(function (panel) {
                panel.classList.toggle('active', panel.getAttribute('data-import-panel') === name);
            });
        });
    });

    var doiForm = root.querySelector('[data-import-panel="doi"]');
    if (doiForm) doiForm.addEventListener('submit', function (event) {
        event.preventDefault();
        handleResult(LiteratureParsers.parseDoiText(event.currentTarget.doiText.value), 'doi');
    });

    var bibtexForm = root.querySelector('[data-import-panel="bibtex"]');
    if (bibtexForm) bibtexForm.addEventListener('submit', function (event) {
        event.preventDefault();
        var form = event.currentTarget;
        fileText(form.bibFile).then(function (text) {
            handleResult(LiteratureParsers.parseBibTeX(text || form.bibText.value), 'bibtex');
        }).catch(function () { setMessage('BibTeX 文件读取失败。', 'error'); });
    });

    var risForm = root.querySelector('[data-import-panel="ris"]');
    if (risForm) risForm.addEventListener('submit', function (event) {
        event.preventDefault();
        var form = event.currentTarget;
        fileText(form.risFile).then(function (text) {
            handleResult(LiteratureParsers.parseRIS(text || form.risText.value), 'ris');
        }).catch(function () { setMessage('RIS 文件读取失败。', 'error'); });
    });

    var csvForm = root.querySelector('[data-import-panel="csv"]');
    if (csvForm) csvForm.addEventListener('submit', function (event) {
        event.preventDefault();
        var form = event.currentTarget;
        fileText(form.csvFile).then(function (text) {
            handleResult(LiteratureParsers.parseCSV(text || form.csvText.value), 'csv');
        }).catch(function () { setMessage('CSV 文件读取失败。', 'error'); });
    });

    var manualForm = root.querySelector('[data-import-panel="manual"]');
    if (manualForm) manualForm.addEventListener('submit', function (event) {
        event.preventDefault();
        var form = event.currentTarget;
        handleResult([{
            title: form.title.value,
            authors: form.authors.value,
            year: form.year.value,
            doi: form.doi.value,
            journal: form.journal.value,
            keywords: form.keywords.value,
            abstract: form.abstract.value
        }], 'manual');
        form.reset();
    });

    var sampleButton = root.querySelector('[data-load-sample]');
    if (sampleButton) sampleButton.addEventListener('click', function () {
        handleResult(LiteratureParsers.samplePapers(), 'sample');
    });

    var clearButton = root.querySelector('[data-clear-library]');
    if (clearButton) clearButton.addEventListener('click', function () {
        LiteratureStore.clear();
        try { window.localStorage.setItem('lsca.importedPapers.count', '0'); } catch (error) {}
        refreshCount();
        setMessage('本地导入已清空。', 'neutral');
    });

    refreshCount();
})();
