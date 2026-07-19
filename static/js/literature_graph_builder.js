(function () {
    var STOPWORDS = {
        the: true, and: true, for: true, with: true, from: true, this: true, that: true,
        using: true, into: true, are: true, was: true, were: true, study: true, analysis: true,
        method: true, methods: true, paper: true, data: true, based: true, through: true
    };
    var METHOD_TERMS = [
        'single particle analysis', 'electron tomography', 'subtomogram averaging', 'particle picking',
        '2d classification', '3d refinement', 'vitrification', 'sample preparation', 'reconstruction',
        'fsc', 'validation', 'cryo-ET', 'RELION', 'cryoSPARC'
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
        var extracted = Object.keys(counts).sort(function (left, right) {
            return counts[right] - counts[left];
        }).slice(0, 5);
        METHOD_TERMS.forEach(function (term) {
            if (text.toLowerCase().indexOf(term.toLowerCase()) !== -1) extracted.push(term);
        });
        return uniq(explicit.concat(extracted)).slice(0, 8);
    }

    function similarity(left, right) {
        var leftKeywords = keywordList(left).map(function (value) { return value.toLowerCase(); });
        var rightKeywords = keywordList(right).map(function (value) { return value.toLowerCase(); });
        var leftSet = {};
        leftKeywords.forEach(function (value) { leftSet[value] = true; });
        var intersection = rightKeywords.filter(function (value) { return leftSet[value]; }).length;
        var union = uniq(leftKeywords.concat(rightKeywords)).length || 1;
        return intersection / union;
    }

    function analyze(papers, keywordCounts, authorCounts) {
        var missingDoi = papers.filter(function (paper) { return !paper.doi; }).length;
        var topKeywords = Object.keys(keywordCounts).sort(function (left, right) {
            return keywordCounts[right] - keywordCounts[left];
        }).slice(0, 10);
        var topAuthors = Object.keys(authorCounts).sort(function (left, right) {
            return authorCounts[right] - authorCounts[left];
        }).slice(0, 6);
        var topPapers = papers.slice().sort(function (left, right) {
            return (right.citationCount || 0) - (left.citationCount || 0);
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
                topKeywords.length ? '关键词覆盖良好' : '建议补充关键词或摘要'
            ]
        };
    }

    function buildGraph(inputPapers, seed) {
        var papers = (inputPapers || []).slice(0, 80);
        var nodes = [];
        var edges = [];
        var topicLabel = seed || '本地导入文献';
        var topicId = 'topic:' + topicLabel.toLowerCase().replace(/\s+/g, '-');
        var keywordCounts = {};
        var keywordLabels = {};
        var authorCounts = {};
        var methods = {};

        nodes.push({
            id: topicId,
            type: 'Topic',
            label: topicLabel,
            title: topicLabel,
            topic: topicLabel,
            relevance: 1,
            abstract: '当前导入文献形成的研究主题中心。'
        });

        papers.forEach(function (paper, index) {
            var paperKeywords = keywordList(paper);
            var paperAuthors = Array.isArray(paper.authors)
                ? paper.authors
                : String(paper.authors || '').split(/[;|]+/).map(function (value) { return value.trim(); }).filter(Boolean);
            var relevance = Math.min(0.98, 0.48 + paperKeywords.length * 0.045 + Math.min(paper.citationCount || 0, 500) / 1600);
            nodes.push({
                id: paper.id,
                type: 'Paper',
                label: paper.title,
                title: paper.title,
                authors: paperAuthors.join('; '),
                year: paper.year,
                doi: paper.doi,
                journal: paper.journal,
                abstract: paper.abstract,
                keywords: paperKeywords,
                citation_count: paper.citationCount || 0,
                relevance: relevance,
                bookmarked: !!paper.favorite,
                status: paper.status,
                source: paper.source,
                topic: topicLabel
            });
            edges.push({from: topicId, to: paper.id, relation: 'similar_work', weight: Math.max(0.35, relevance - index * 0.01)});

            paperKeywords.forEach(function (keyword) {
                var keywordKey = String(keyword || '').trim().toLowerCase();
                if (!keywordKey) return;
                keywordLabels[keywordKey] = keywordLabels[keywordKey] || String(keyword).trim();
                keywordCounts[keywordKey] = (keywordCounts[keywordKey] || 0) + 1;
                edges.push({from: paper.id, to: 'keyword:' + keywordKey, relation: 'shared_keyword', weight: 0.35 + Math.min(0.45, keywordCounts[keywordKey] * 0.05)});
                METHOD_TERMS.forEach(function (term) {
                    if (keywordKey === term.toLowerCase()) methods[term] = true;
                });
            });

            paperAuthors.slice(0, 4).forEach(function (author) {
                authorCounts[author] = (authorCounts[author] || 0) + 1;
                edges.push({from: paper.id, to: 'author:' + author.toLowerCase(), relation: 'same_author', weight: 0.32 + Math.min(0.4, authorCounts[author] * 0.05)});
            });

            (paper.references || []).forEach(function (reference) {
                var target = papers.find(function (candidate) {
                    return candidate.doi && reference.toLowerCase().indexOf(candidate.doi.toLowerCase()) !== -1;
                });
                if (target) edges.push({from: paper.id, to: target.id, relation: 'cites', weight: 0.72});
            });
        });

        Object.keys(keywordCounts).sort(function (left, right) {
            return keywordCounts[right] - keywordCounts[left];
        }).slice(0, 18).forEach(function (keywordKey) {
            var keyword = keywordLabels[keywordKey] || keywordKey;
            nodes.push({
                id: 'keyword:' + keywordKey,
                type: 'Keyword',
                label: keyword,
                title: keyword,
                topic: topicLabel,
                relevance: Math.min(1, 0.35 + keywordCounts[keywordKey] / Math.max(1, papers.length)),
                abstract: '在导入文献中出现 ' + keywordCounts[keywordKey] + ' 次的关键词。'
            });
        });

        Object.keys(authorCounts).sort(function (left, right) {
            return authorCounts[right] - authorCounts[left];
        }).slice(0, 12).forEach(function (author) {
            nodes.push({
                id: 'author:' + author.toLowerCase(),
                type: 'Author',
                label: author,
                title: author,
                topic: topicLabel,
                relevance: Math.min(0.95, 0.35 + authorCounts[author] / Math.max(1, papers.length)),
                abstract: '在导入文献中出现 ' + authorCounts[author] + ' 次的作者或研究团队。'
            });
        });

        Object.keys(methods).slice(0, 8).forEach(function (method) {
            var methodId = 'method:' + method.toLowerCase();
            nodes.push({
                id: methodId,
                type: 'Method',
                label: method,
                title: method,
                topic: topicLabel,
                relevance: 0.7,
                abstract: '从标题、摘要或关键词中识别到的方法节点。'
            });
            edges.push({from: topicId, to: methodId, relation: 'method_dependency', weight: 0.58});
        });

        for (var leftIndex = 0; leftIndex < papers.length; leftIndex += 1) {
            for (var rightIndex = leftIndex + 1; rightIndex < papers.length; rightIndex += 1) {
                var score = similarity(papers[leftIndex], papers[rightIndex]);
                if (score >= 0.16) {
                    edges.push({
                        from: papers[leftIndex].id,
                        to: papers[rightIndex].id,
                        relation: 'similar_work',
                        weight: Math.min(0.9, score + 0.25)
                    });
                }
            }
        }

        var finalNodes = nodes.slice(0, 60);
        var finalIds = {};
        finalNodes.forEach(function (node) { finalIds[String(node.id)] = true; });
        var finalEdges = edges.filter(function (edge) {
            return finalIds[String(edge.from)] && finalIds[String(edge.to)];
        }).slice(0, 120);

        return {
            nodes: finalNodes,
            edges: finalEdges,
            seed: finalNodes[0],
            source: papers.length ? '本地导入' : '空文献库',
            meta: {source: papers.length ? 'local-import' : 'empty', query: topicLabel, paperCount: papers.length},
            analysis: analyze(papers, keywordCounts, authorCounts)
        };
    }

    window.LiteratureGraphBuilder = {
        buildGraph: buildGraph,
        keywordList: keywordList
    };
})();
