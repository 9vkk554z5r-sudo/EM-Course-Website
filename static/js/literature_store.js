(function () {
    var KEY = 'lifeScience.importedPapers.v1';

    function safeParse(value, fallback) {
        try { return JSON.parse(value); } catch (err) { return fallback; }
    }

    function normalizeDoi(doi) {
        return String(doi || '').trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, '').toLowerCase();
    }

    function normalizeList(value) {
        if (Array.isArray(value)) return value.map(function (v) { return String(v).trim(); }).filter(Boolean);
        return String(value || '').split(/[;\n|]+|,(?=\s*[A-Z\u4e00-\u9fa5])/).map(function (v) {
            return v.trim();
        }).filter(Boolean);
    }

    function makeId(paper) {
        var doi = normalizeDoi(paper.doi);
        if (doi) return 'doi:' + doi;
        return 'title:' + String(paper.title || 'untitled').toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-').slice(0, 72);
    }

    function normalizePaper(input, source) {
        var paper = input || {};
        var normalized = {
            id: paper.id || '',
            title: String(paper.title || paper.TI || paper.name || '').trim(),
            authors: normalizeList(paper.authors || paper.author || paper.AU),
            year: paper.year ? Number(String(paper.year).match(/\d{4}/)) : null,
            doi: normalizeDoi(paper.doi || paper.DO || ''),
            journal: String(paper.journal || paper.JO || paper.T2 || '').trim(),
            abstract: String(paper.abstract || paper.AB || '').trim(),
            keywords: normalizeList(paper.keywords || paper.KW),
            citationCount: Number(paper.citationCount || paper.citation_count || 0),
            references: normalizeList(paper.references || ''),
            source: source || paper.source || 'manual',
            importedAt: paper.importedAt || new Date().toISOString(),
            tags: normalizeList(paper.tags || ''),
            status: paper.status || 'unread',
            favorite: !!paper.favorite,
        };
        if (!normalized.title && normalized.doi) normalized.title = 'DOI ' + normalized.doi;
        normalized.id = paper.id || makeId(normalized);
        return normalized;
    }

    function getAll() {
        var parsed = safeParse(localStorage.getItem(KEY), []);
        return Array.isArray(parsed) ? parsed : [];
    }

    function saveAll(papers) {
        localStorage.setItem(KEY, JSON.stringify(papers || []));
        window.dispatchEvent(new CustomEvent('literature-library-updated'));
    }

    function upsertMany(items, source) {
        var existing = getAll();
        var byId = {};
        existing.forEach(function (paper) { byId[paper.id] = paper; });
        var added = 0;
        var updated = 0;
        (items || []).map(function (item) { return normalizePaper(item, source); }).forEach(function (paper) {
            if (!paper.title && !paper.doi) return;
            if (byId[paper.id]) {
                byId[paper.id] = Object.assign({}, byId[paper.id], paper, {
                    importedAt: byId[paper.id].importedAt || paper.importedAt,
                });
                updated += 1;
            } else {
                existing.push(paper);
                byId[paper.id] = paper;
                added += 1;
            }
        });
        saveAll(existing);
        return { added: added, updated: updated, total: existing.length };
    }

    function update(id, patch) {
        var papers = getAll().map(function (paper) {
            return paper.id === id ? Object.assign({}, paper, patch || {}) : paper;
        });
        saveAll(papers);
    }

    function clear() {
        saveAll([]);
    }

    window.LiteratureStore = {
        getAll: getAll,
        saveAll: saveAll,
        upsertMany: upsertMany,
        update: update,
        clear: clear,
        normalizePaper: normalizePaper,
        normalizeDoi: normalizeDoi,
    };
})();
