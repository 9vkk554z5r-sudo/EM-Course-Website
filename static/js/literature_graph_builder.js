(function () {
    var STOPWORDS = {
        the: true, and: true, for: true, with: true, from: true, this: true, that: true,
        using: true, into: true, are: true, was: true, were: true, study: true, analysis: true,
        method: true, methods: true, paper: true, data: true, based: true, through: true,
    };
    var METHOD_TERMS = [
        'single particle analysis', 'electron tomography', 'subtomogram averaging', 'particle picking',
        '2d classification', '3d refinement', 'vitrification', 'sample preparation', 'reconstruction',
        'fsc', 'validation', 'cryo-ET', 'RELION', 'cryoSPARC',
    ];

    function words(text) {
        return String(text || '').toLowerCase().match(/[a-z][a-z0-9-]{2,}|[\u4e00-\u9fa5]{2,}/g) || [];
    }

    function uniq(list) {
        var seen = {};
        return list.filter(function (item) {
            var key = String(item || '').toLowerCase();
            if (!key || seen[key]) return false;
            seen[key] = true;
            return true;
        });
    }

    function keywordList(paper) {
        var explicit = Array.isArray(paper.keywords) ? paper.keywords : [];
        var text = [paper.title, paper.abstract].join(' ');
        var tokens = words(text).filter(function (token) { return !STOPWORDS[token] && token.length > 3; });
        var counts = {};
        tokens.forEach(function (token) { counts[token] = (counts[token] || 0) + 1; });
        var extracted = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; }).slice(0, 5);
        METHOD_TERMS.forEach(function (term) {
            if (text.toLowerCase().indexOf(term.toLowerCase()) !== -1) extracted.push(term);
        });
        return uniq(explicit.concat(extracted)).slice(0, 8);
    }

    function similarity(a, b) {
        var ak = keywordList(a).map(function (x) { return x.toLowerCase(); });
        var bk = keywordList(b).map(function (x) { return x.toLowerCase(); });
        var setA = {};
        ak.forEach(function (x) { setA[x] = true; });
        var inter = bk.filter(function (x) { return setA[x]; }).length;
        var union = uniq(ak.concat(bk)).length || 1;
        return inter / union;
    }

    function buildGraph(papers, seed) {
        papers = (papers || []).slice(0, 80);
        var nodes = [];
        var edges = [];
        var topicId = 'topic:' + (seed || 'imported-literature').toLowerCase().replace(/\s+/g, '-');
        var keywordCounts = {};
        var authorCounts = {};
        var methods = {};

        nodes.push({
            id: topicId,
            type: 'Topic',
            label: seed || 'Imported literature',
            title: seed || 'Imported literature',
            relevance: 1,
            abstract: '当前导入文献形成的研究主题中心。',
        });

        papers.forEach(function (paper, index) {
            var pKeywords = keywordList(paper);
            var relevance = Math.min(0.98, 0.48 + pKeywords.length * 0.045 + Math.min(paper.citationCount || 0, 500) / 1600);
            nodes.push({
                id: paper.id,
                type: 'Paper',
                label: paper.title,
                title: paper.title,
                authors: (paper.authors || []).join('; '),
                year: paper.year,
                doi: paper.doi,
                journal: paper.journal,
                abstract: paper.abstract,
                keywords: pKeywords,
                citation_count: paper.citationCount || 0,
                relevance: relevance,
                bookmarked: !!paper.favorite,
                status: paper.status,
                source: paper.source,
            });
            edges.push({ from: topicId, to: paper.id, relation: 'similar_work', weight: Math.max(0.35, relevance - index * 0.01) });

            pKeywords.forEach(function (kw) {
                keywordCounts[kw] = (keywordCounts[kw] || 0) + 1;
                edges.push({ from: paper.id, to: 'keyword:' + kw.toLowerCase(), relation: 'shared_keyword', weight: 0.35 + Math.min(0.45, keywordCounts[kw] * 0.05) });
                METHOD_TERMS.forEach(function (term) {
                    if (kw.toLowerCase() === term.toLowerCase()) methods[term] = true;
                });
            });
            (paper.authors || []).slice(0, 4).forEach(function (author) {
                authorCounts[author] = (authorCounts[author] || 0) + 1;
                edges.push({ from: paper.id, to: 'author:' + author.toLowerCase(), relation: 'same_author', weight: 0.32 + Math.min(0.4, authorCounts[author] * 0.05) });
            });
            (paper.references || []).forEach(function (ref) {
                var target = papers.find(function (candidate) {
                    return candidate.doi && ref.toLowerCase().indexOf(candidate.doi.toLowerCase()) !== -1;
                });
                if (target) edges.push({ from: paper.id, to: target.id, relation: 'cites', weight: 0.72 });
            });
        });

        Object.keys(keywordCounts).sort(function (a, b) { return keywordCounts[b] - keywordCounts[a]; }).slice(0, 18).forEach(function (kw) {
            nodes.push({
                id: 'keyword:' + kw.toLowerCase(),
                type: 'Keyword',
                label: kw,
                title: kw,
                relevance: Math.min(1, 0.35 + keywordCounts[kw] / Math.max(1, papers.length)),
                abstract: '在导入文献中出现 ' + keywordCounts[kw] + ' 次的关键词。',
            });
        });

        Object.keys(authorCounts).sort(function (a, b) { return authorCounts[b] - authorCounts[a]; }).slice(0, 12).forEach(function (author) {
            nodes.push({
                id: 'author:' + author.toLowerCase(),
                type: 'Author',
                label: author,
                title: author,
                relevance: Math.min(0.95, 0.35 + authorCounts[author] / Math.max(1, papers.length)),
                abstract: '在导入文献中出现 ' + authorCounts[author] + ' 次的作者或团队。',
            });
        });

        Object.keys(methods).slice(0, 8).forEach(function (method) {
            var id = 'method:' + method.toLowerCase();
            nodes.push({ id: id, type: 'Method', label: method, title: method, relevance: 0.7, abstract: '从标题、摘要或关键词中识别到的方法节点。' });
            edges.push({ from: topicId, to: id, relation: 'method_dependency', weight: 0.58 });
        });

        for (var i = 0; i < papers.length; i += 1) {
            for (var j = i + 1; j < papers.length; j += 1) {
                var sim = similarity(papers[i], papers[j]);
                if (sim >= 0.16) edges.push({ from: papers[i].id, to: papers[j].id, relation: 'similar_work', weight: Math.min(0.9, sim + 0.25) });
            }
        }

        return {
            nodes: nodes.slice(0, 60),
            edges: edges.filter(function (edge) {
                return nodes.some(function (n) { return n.id === edge.from; }) && nodes.some(function (n) { return n.id === edge.to; });
            }).slice(0, 120),
            seed: nodes[0],
            meta: { source: papers.length ? 'local-import' : 'empty', query: seed || 'Imported literature', paperCount: papers.length },
            analysis: analyze(papers, keywordCounts, authorCounts),
        };
    }

    function analyze(papers, keywordCounts, authorCounts) {
        var missingDoi = papers.filter(function (paper) { return !paper.doi; }).length;
        var topKeywords = Object.keys(keywordCounts).sort(function (a, b) { return keywordCounts[b] - keywordCounts[a]; }).slice(0, 10);
        var topAuthors = Object.keys(authorCounts).sort(function (a, b) { return authorCounts[b] - authorCounts[a]; }).slice(0, 6);
        var topPapers = papers.slice().sort(function (a, b) {
            return (b.citationCount || 0) - (a.citationCount || 0);
        }).slice(0, 5);
        return {
            themes: topKeywords.slice(0, 5),
            keywords: topKeywords,
            authors: topAuthors,
            papers: topPapers,
            recommended: topPapers.slice(0, 3),
            quality: [
                papers.length + ' 篇文献已导入',
                missingDoi + ' 篇文献缺少 DOI',
                topKeywords.length ? '关键词覆盖良好' : '建议补充关键词或摘要',
            ],
        };
    }

    window.LiteratureGraphBuilder = {
        buildGraph: buildGraph,
        keywordList: keywordList,
    };
})();
