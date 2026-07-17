(function () {
    var root = document.querySelector('.graph-workbench');
    if (!root) return;

    var canvas = root.querySelector('[data-graph-canvas]');
    var detail = root.querySelector('[data-node-detail]');
    var analysisPanel = root.querySelector('[data-analysis-panel]');
    var statusEl = root.querySelector('[data-graph-status]');
    var metaEl = root.querySelector('[data-graph-meta]');
    var titleEl = root.querySelector('[data-graph-title]');
    var searchForm = root.querySelector('[data-graph-search]');
    var viewButtons = root.querySelectorAll('[data-view]');
    var yearFilter = root.querySelector('[data-filter-year]');
    var relevanceFilter = root.querySelector('[data-filter-relevance]');
    var bookmarkedFilter = root.querySelector('[data-filter-bookmarked]');
    var typeContainer = root.querySelector('[data-filter-types]');

    var state = {
        graph: null,
        view: root.getAttribute('data-initial-view') || 'overview',
        selected: null,
        readIds: JSON.parse(localStorage.getItem('lifeScience.graphReadIds.v1') || '[]'),
    };

    var nodeStyles = {
        Topic: { color: '#5eead4', stroke: '#134e4a', shape: 'hex' },
        Paper: { color: '#e5eef5', stroke: '#475569', shape: 'circle' },
        Keyword: { color: '#7dd3c7', stroke: '#115e59', shape: 'pill' },
        Author: { color: '#f3c86b', stroke: '#7c4a03', shape: 'diamond' },
        Method: { color: '#93c5fd', stroke: '#1d4ed8', shape: 'rect' },
    };
    var edgeStyles = {
        cites: { color: '#a8b3bd', dash: '' },
        similar_work: { color: '#2dd4bf', dash: '6 6' },
        shared_keyword: { color: '#5eead4', dash: '3 5' },
        same_author: { color: '#f3c86b', dash: '2 6' },
        method_dependency: { color: '#93c5fd', dash: '8 4' },
    };

    function setStatus(text) {
        if (statusEl) statusEl.textContent = text;
    }

    function activeTypes() {
        if (!typeContainer) return Object.keys(nodeStyles);
        return Array.prototype.slice.call(typeContainer.querySelectorAll('input:checked')).map(function (el) { return el.value; });
    }

    function filters() {
        return {
            year: yearFilter ? yearFilter.value : 'all',
            relevance: relevanceFilter ? parseFloat(relevanceFilter.value || '0') : 0,
            bookmarked: bookmarkedFilter ? bookmarkedFilter.checked : false,
            types: activeTypes(),
        };
    }

    function currentQuery() {
        var input = searchForm ? searchForm.querySelector('input[name="q"]') : null;
        return input && input.value ? input.value : 'cryo-EM';
    }

    function rebuildGraph() {
        var papers = window.LiteratureStore ? LiteratureStore.getAll() : [];
        if (!papers.length && window.LiteratureParsers && root.classList.contains('graph-workbench-compact')) {
            papers = LiteratureParsers.samplePapers().map(function (p) { return LiteratureStore.normalizePaper(p, 'sample'); });
        }
        if (!papers.length) {
            state.graph = { nodes: [], edges: [], analysis: null, meta: { source: 'empty', query: currentQuery(), paperCount: 0 } };
            render();
            renderAnalysis(null);
            setStatus('等待导入文献');
            return;
        }
        state.graph = LiteratureGraphBuilder.buildGraph(papers, currentQuery());
        state.selected = state.graph.seed;
        render();
        renderDetail(state.selected);
        renderAnalysis(state.graph.analysis);
    }

    function visibleGraph() {
        var graph = state.graph || { nodes: [], edges: [] };
        var f = filters();
        var nodes = graph.nodes.filter(function (node) {
            if (f.types.indexOf(node.type) === -1) return false;
            if (f.bookmarked && !node.bookmarked) return false;
            if ((node.relevance || 0) < f.relevance) return false;
            if (f.year !== 'all' && node.year && Number(node.year) < Number(f.year)) return false;
            if (state.view === 'citation' && ['Topic', 'Paper', 'Author'].indexOf(node.type) === -1) return false;
            if (state.view === 'keywords' && ['Topic', 'Paper', 'Keyword', 'Method'].indexOf(node.type) === -1) return false;
            return true;
        }).slice(0, state.view === 'overview' ? 60 : 46);
        var ids = {};
        nodes.forEach(function (node) { ids[node.id] = true; });
        var edges = graph.edges.filter(function (edge) {
            if (!ids[edge.from] || !ids[edge.to]) return false;
            if (state.view === 'citation' && ['cites', 'similar_work', 'same_author'].indexOf(edge.relation) === -1) return false;
            if (state.view === 'keywords' && ['shared_keyword', 'similar_work', 'method_dependency'].indexOf(edge.relation) === -1) return false;
            return true;
        });
        return { nodes: nodes, edges: edges };
    }

    function render() {
        var graph = visibleGraph();
        if (!canvas) return;
        if (!graph.nodes.length) {
            canvas.innerHTML = '<div class="graph-empty"><strong>还没有可展示的图谱</strong><span>先导入文献，或点击“载入示例数据”。</span></div>';
            if (metaEl) metaEl.textContent = '0 nodes · 0 relations';
            return;
        }

        var width = canvas.clientWidth || 760;
        var height = Math.max(canvas.clientHeight || 580, width < 760 ? 520 : 560);
        var layout = layoutNodes(graph.nodes, width, height);
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
        svg.setAttribute('class', 'knowledge-svg');

        graph.edges.forEach(function (edge) {
            var a = layout[edge.from], b = layout[edge.to];
            if (!a || !b) return;
            var style = edgeStyles[edge.relation] || edgeStyles.similar_work;
            var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', a.x);
            line.setAttribute('y1', a.y);
            line.setAttribute('x2', b.x);
            line.setAttribute('y2', b.y);
            line.setAttribute('stroke', style.color);
            line.setAttribute('stroke-width', Math.max(1, (edge.weight || 0.3) * 3));
            line.setAttribute('stroke-opacity', state.selected && (edge.from === state.selected.id || edge.to === state.selected.id) ? '0.85' : '0.28');
            if (style.dash) line.setAttribute('stroke-dasharray', style.dash);
            line.setAttribute('class', 'graph-edge');
            svg.appendChild(line);
        });

        graph.nodes.forEach(function (node) {
            var p = layout[node.id];
            if (!p) return;
            var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('class', 'graph-node ' + node.type.toLowerCase() + (state.selected && state.selected.id === node.id ? ' selected' : ''));
            g.setAttribute('transform', 'translate(' + p.x + ' ' + p.y + ')');
            g.setAttribute('tabindex', '0');
            g.setAttribute('role', 'button');
            g.addEventListener('click', function () {
                state.selected = node;
                render();
                renderDetail(node);
            });
            g.addEventListener('mouseenter', function () { showTooltip(node, p.x, p.y); });
            g.addEventListener('mouseleave', hideTooltip);
            appendNodeShape(g, node, p.r);
            var label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            label.setAttribute('x', 0);
            label.setAttribute('y', p.r + 17);
            label.setAttribute('text-anchor', 'middle');
            label.setAttribute('class', 'node-label');
            label.textContent = trimLabel(node.label || node.title, node.type === 'Paper' ? 22 : 18);
            g.appendChild(label);
            svg.appendChild(g);
        });

        canvas.innerHTML = '';
        canvas.appendChild(svg);
        if (metaEl) metaEl.textContent = graph.nodes.length + ' nodes · ' + graph.edges.length + ' relations';
        if (titleEl) titleEl.textContent = viewTitle(state.view);
        setStatus((state.graph.meta.paperCount || 0) + ' 篇文献 · ' + state.graph.meta.source);
    }

    function layoutNodes(nodes, width, height) {
        if (state.view === 'timeline') return timelineLayout(nodes, width, height);
        var center = { x: width * 0.48, y: height * 0.5 };
        var groups = { Topic: [], Paper: [], Keyword: [], Author: [], Method: [] };
        nodes.forEach(function (node) { (groups[node.type] || groups.Paper).push(node); });
        var positions = {};
        var rings = [
            { types: ['Topic'], radius: 0, start: 0, arc: Math.PI * 2 },
            { types: ['Paper'], radius: Math.min(width, height) * 0.25, start: -Math.PI * 0.92, arc: Math.PI * 1.84 },
            { types: ['Keyword', 'Method'], radius: Math.min(width, height) * 0.39, start: Math.PI * 0.05, arc: Math.PI * 1.38 },
            { types: ['Author'], radius: Math.min(width, height) * 0.43, start: Math.PI * 1.05, arc: Math.PI * 0.84 },
        ];
        rings.forEach(function (ring) {
            var ringNodes = [];
            ring.types.forEach(function (type) { ringNodes = ringNodes.concat(groups[type] || []); });
            ringNodes.forEach(function (node, i) {
                var angle = ring.start + (ring.arc * (i + 0.5) / Math.max(1, ringNodes.length));
                var jitter = ((i % 3) - 1) * 14;
                positions[node.id] = {
                    x: center.x + Math.cos(angle) * (ring.radius + jitter),
                    y: center.y + Math.sin(angle) * (ring.radius + jitter * 0.4),
                    r: nodeRadius(node),
                };
            });
        });
        return positions;
    }

    function timelineLayout(nodes, width, height) {
        var positions = {};
        var sorted = nodes.slice().sort(function (a, b) { return (Number(a.year) || 0) - (Number(b.year) || 0); });
        sorted.forEach(function (node, i) {
            var x = 72 + (width - 144) * (i / Math.max(1, sorted.length - 1));
            var y = node.type === 'Paper' ? height * 0.48 : 100 + (['Topic', 'Keyword', 'Author', 'Method'].indexOf(node.type) + 1) * 76;
            positions[node.id] = { x: x, y: Math.min(height - 70, y), r: nodeRadius(node) };
        });
        return positions;
    }

    function nodeRadius(node) {
        if (node.type === 'Topic') return 29;
        var base = node.type === 'Paper' ? 13 : 11;
        return Math.round(base + Math.min(Math.sqrt(node.citation_count || 0), 22) * 0.35 + (node.relevance || 0.5) * 7);
    }

    function appendNodeShape(g, node, radius) {
        var style = nodeStyles[node.type] || nodeStyles.Paper;
        var shape;
        if (style.shape === 'diamond') {
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            shape.setAttribute('points', '0,' + (-radius) + ' ' + radius + ',0 0,' + radius + ' ' + (-radius) + ',0');
        } else if (style.shape === 'rect') {
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            shape.setAttribute('x', -radius * 1.25);
            shape.setAttribute('y', -radius * 0.82);
            shape.setAttribute('width', radius * 2.5);
            shape.setAttribute('height', radius * 1.64);
            shape.setAttribute('rx', 4);
        } else if (style.shape === 'pill') {
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            shape.setAttribute('x', -radius * 1.55);
            shape.setAttribute('y', -radius * 0.72);
            shape.setAttribute('width', radius * 3.1);
            shape.setAttribute('height', radius * 1.44);
            shape.setAttribute('rx', radius * 0.72);
        } else if (style.shape === 'hex') {
            var pts = [];
            for (var i = 0; i < 6; i += 1) {
                var a = Math.PI / 6 + i * Math.PI / 3;
                pts.push(Math.cos(a) * radius + ',' + Math.sin(a) * radius);
            }
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            shape.setAttribute('points', pts.join(' '));
        } else {
            shape = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            shape.setAttribute('r', radius);
        }
        shape.setAttribute('fill', style.color);
        shape.setAttribute('stroke', style.stroke);
        shape.setAttribute('stroke-width', node.bookmarked ? 3 : 1.5);
        g.appendChild(shape);
        if (state.readIds.indexOf(node.id) !== -1) {
            var read = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            read.setAttribute('cx', radius * 0.72);
            read.setAttribute('cy', -radius * 0.72);
            read.setAttribute('r', 4);
            read.setAttribute('fill', '#22c55e');
            g.appendChild(read);
        }
    }

    function renderDetail(node) {
        if (!node || !detail) return;
        var keywords = (node.keywords || []).map(function (kw) { return '<span class="mini-tag">' + escapeHtml(kw) + '</span>'; }).join('');
        detail.innerHTML = [
            '<p class="section-kicker">' + escapeHtml(node.type) + '</p>',
            '<h2>' + escapeHtml(node.title || node.label) + '</h2>',
            '<div class="detail-meta">',
            node.year ? '<span>' + escapeHtml(node.year) + '</span>' : '',
            node.authors ? '<span>' + escapeHtml(node.authors) + '</span>' : '',
            node.citation_count ? '<span>' + node.citation_count + ' citations</span>' : '',
            '</div>',
            '<div class="keyword-row">' + keywords + '</div>',
            '<p>' + escapeHtml(node.abstract || '暂无摘要。') + '</p>',
            '<div class="score-row"><span>Relevance</span><strong>' + Math.round((node.relevance || 0) * 100) + '%</strong></div>',
            '<div class="detail-actions">',
            '<button class="btn btn-sm btn-outline" type="button" data-action="favorite">加入收藏</button>',
            '<button class="btn btn-sm btn-outline" type="button" data-action="read">标记已读</button>',
            '<button class="btn btn-sm btn-outline" type="button" data-action="note">生成阅读笔记</button>',
            '<button class="btn btn-sm btn-outline" type="button" data-action="trace">追踪相关文献</button>',
            '<a class="btn btn-sm btn-primary" href="/dashboard">询问科研助手</a>',
            '</div>',
        ].join('');
        var favorite = detail.querySelector('[data-action="favorite"]');
        var read = detail.querySelector('[data-action="read"]');
        var note = detail.querySelector('[data-action="note"]');
        var trace = detail.querySelector('[data-action="trace"]');
        if (favorite) favorite.addEventListener('click', function () { toggleFavorite(node, favorite); });
        if (read) read.addEventListener('click', function () { markRead(node); });
        if (note) note.addEventListener('click', function () { note.textContent = '已加入笔记队列'; });
        if (trace) trace.addEventListener('click', function () { switchView('citation'); });
    }

    function renderAnalysis(analysis) {
        if (!analysisPanel) return;
        if (!analysis) {
            analysisPanel.innerHTML = '<p class="section-kicker">Analysis</p><h2>分析摘要</h2><p>导入文献后显示核心主题、关键论文、高频关键词、主要作者和数据质量提示。</p>';
            return;
        }
        analysisPanel.innerHTML = [
            '<p class="section-kicker">Analysis</p>',
            '<h2>分析摘要</h2>',
            listBlock('核心主题 Top 5', analysis.themes),
            listBlock('关键论文 Top 5', analysis.papers.map(function (p) { return p.title; })),
            listBlock('高频关键词 Top 10', analysis.keywords),
            listBlock('主要作者/团队', analysis.authors),
            listBlock('推荐下一步阅读', analysis.recommended.map(function (p) { return p.title; })),
            listBlock('数据质量提示', analysis.quality),
        ].join('');
    }

    function listBlock(title, items) {
        return '<div class="analysis-block"><strong>' + title + '</strong><ol>' + (items || []).map(function (item) {
            return '<li>' + escapeHtml(item) + '</li>';
        }).join('') + '</ol></div>';
    }

    function toggleFavorite(node, button) {
        if (node.type !== 'Paper') {
            button.textContent = '仅论文可收藏';
            return;
        }
        LiteratureStore.update(node.id, { favorite: !node.bookmarked });
        node.bookmarked = !node.bookmarked;
        button.textContent = node.bookmarked ? '已收藏' : '加入收藏';
        rebuildGraph();
    }

    function markRead(node) {
        if (state.readIds.indexOf(node.id) === -1) state.readIds.push(node.id);
        localStorage.setItem('lifeScience.graphReadIds.v1', JSON.stringify(state.readIds));
        if (node.type === 'Paper') LiteratureStore.update(node.id, { status: 'read' });
        render();
        renderDetail(node);
    }

    function switchView(view) {
        state.view = view;
        viewButtons.forEach(function (btn) { btn.classList.toggle('active', btn.getAttribute('data-view') === view); });
        render();
    }

    function viewTitle(view) {
        return {
            overview: 'Overview · 主题总览',
            citation: 'Citation · 引用网络',
            keywords: 'Keywords · 关键词聚类',
            timeline: 'Timeline · 时间线',
        }[view] || '主题总览';
    }

    function trimLabel(text, max) {
        text = String(text || '');
        return text.length > max ? text.slice(0, max - 1) + '…' : text;
    }

    function escapeHtml(text) {
        return String(text || '').replace(/[&<>"']/g, function (c) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
        });
    }

    function showTooltip(node, x, y) {
        hideTooltip();
        var tip = document.createElement('div');
        tip.className = 'graph-tooltip';
        tip.innerHTML = '<strong>' + escapeHtml(trimLabel(node.title || node.label, 70)) + '</strong><span>' + escapeHtml(node.type) + ' · relevance ' + Math.round((node.relevance || 0) * 100) + '%</span>';
        canvas.appendChild(tip);
        tip.style.left = Math.min(canvas.clientWidth - 260, Math.max(12, x + 16)) + 'px';
        tip.style.top = Math.max(12, y + 16) + 'px';
    }

    function hideTooltip() {
        var old = canvas.querySelector('.graph-tooltip');
        if (old) old.remove();
    }

    if (searchForm) {
        searchForm.addEventListener('submit', function (event) {
            event.preventDefault();
            rebuildGraph();
        });
    }
    viewButtons.forEach(function (btn) { btn.addEventListener('click', function () { switchView(btn.getAttribute('data-view')); }); });
    [yearFilter, relevanceFilter, bookmarkedFilter].forEach(function (el) { if (el) el.addEventListener('change', render); });
    if (typeContainer) typeContainer.addEventListener('change', render);
    window.addEventListener('resize', function () { render(); });
    window.addEventListener('literature-library-updated', rebuildGraph);

    rebuildGraph();
})();
