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
        rotationX: -0.2,
        rotationY: 0,
        dragging: false,
        dragDistance: 0,
        pointerX: 0,
        pointerY: 0,
        animationFrame: null,
        renderModel: null,
        lastFrameTime: 0,
        reduceMotion: window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
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
        var usingSample = false;
        if (!papers.length && window.LiteratureParsers && window.LiteratureStore) {
            papers = LiteratureParsers.samplePapers().map(function (p) { return LiteratureStore.normalizePaper(p, 'sample'); });
            usingSample = true;
        }
        if (!papers.length) {
            state.graph = { nodes: [], edges: [], analysis: null, meta: { source: 'empty', query: currentQuery(), paperCount: 0 } };
            render();
            renderAnalysis(null);
            setStatus('等待导入文献');
            return;
        }
        state.graph = LiteratureGraphBuilder.buildGraph(papers, currentQuery());
        if (usingSample) state.graph.meta.source = '\u52a8\u6001\u793a\u4f8b\u661f\u7403';
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
        }).slice(0, state.view === 'overview' ? 44 : 38);
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
        if (state.animationFrame) cancelAnimationFrame(state.animationFrame);
        state.animationFrame = null;
        state.renderModel = null;

        if (!graph.nodes.length) {
            canvas.innerHTML = '<div class="graph-empty"><strong>还没有可展示的图谱</strong><span>先导入文献，或点击“载入示例数据”</span></div>';
            if (metaEl) metaEl.textContent = '0 nodes · 0 relations';
            return;
        }

        var width = canvas.clientWidth || 760;
        var height = Math.max(canvas.clientHeight || 580, width < 760 ? 520 : 560);
        var sphereMode = state.view !== 'timeline';
        var layout = layoutNodes(graph.nodes, width, height);
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
        svg.setAttribute('class', 'knowledge-svg');
        svg.setAttribute('aria-label', sphereMode ? '可拖动并自动旋转的三维文献星球' : '文献时间线');

        var edgeLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        var nodeLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        var edgeElements = [];
        if (sphereMode) appendPlanetBackdrop(svg, width, height);

        graph.edges.forEach(function (edge) {
            var a = layout[edge.from], b = layout[edge.to];
            if (!a || !b) return;
            var style = edgeStyles[edge.relation] || edgeStyles.similar_work;
            var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('stroke', style.color);
            line.setAttribute('stroke-width', Math.max(1, (edge.weight || 0.3) * 2.6));
            if (style.dash) line.setAttribute('stroke-dasharray', style.dash);
            line.setAttribute('class', 'graph-edge');
            line._edgeData = edge;
            edgeElements.push(line);
            edgeLayer.appendChild(line);
        });

        graph.nodes.forEach(function (node) {
            var p = layout[node.id];
            if (!p) return;
            var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('class', 'graph-node ' + node.type.toLowerCase() + (state.selected && state.selected.id === node.id ? ' selected' : ''));
            g.setAttribute('tabindex', '0');
            g.setAttribute('role', 'button');
            g.setAttribute('aria-label', node.title || node.label || node.type);
            g.addEventListener('click', function () {
                if (state.dragDistance > 5) return;
                state.selected = node;
                render();
                renderDetail(node);
            });
            g.addEventListener('keydown', function (event) {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                state.selected = node;
                render();
                renderDetail(node);
            });
            g.addEventListener('mouseenter', function () { showTooltip(node, p.screenX || p.x, p.screenY || p.y); });
            g.addEventListener('mouseleave', hideTooltip);
            appendNodeShape(g, node, p.r);
            var label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            label.setAttribute('x', 0);
            label.setAttribute('y', p.r + 17);
            label.setAttribute('text-anchor', 'middle');
            label.setAttribute('class', 'node-label');
            label.textContent = trimLabel(node.label || node.title, node.type === 'Paper' ? 22 : 18);
            g.appendChild(label);
            p.element = g;
            p.labelElement = label;
            nodeLayer.appendChild(g);
        });

        svg.appendChild(edgeLayer);
        svg.appendChild(nodeLayer);
        canvas.innerHTML = '';
        canvas.appendChild(svg);

        if (sphereMode) {
            var hint = document.createElement('div');
            hint.className = 'graph-planet-hint';
            hint.textContent = '自动旋转 · 按住拖动可查看星球背面';
            canvas.appendChild(hint);
            state.renderModel = {
                graph: graph,
                layout: layout,
                edges: edgeElements,
                width: width,
                height: height,
                radius: Math.min(width * 0.36, height * 0.39),
            };
            updateSphereProjection();
            startSphereAnimation();
        } else {
            graph.nodes.forEach(function (node) {
                var point = layout[node.id];
                if (point && point.element) point.element.setAttribute('transform', 'translate(' + point.x + ' ' + point.y + ')');
            });
            edgeElements.forEach(function (line) {
                var edge = line._edgeData;
                var a = layout[edge.from], b = layout[edge.to];
                line.setAttribute('x1', a.x);
                line.setAttribute('y1', a.y);
                line.setAttribute('x2', b.x);
                line.setAttribute('y2', b.y);
                line.setAttribute('stroke-opacity', state.selected && (edge.from === state.selected.id || edge.to === state.selected.id) ? '0.85' : '0.28');
            });
        }

        if (metaEl) metaEl.textContent = graph.nodes.length + ' nodes · ' + graph.edges.length + ' relations';
        if (titleEl) titleEl.textContent = viewTitle(state.view);
        setStatus((state.graph.meta.paperCount || 0) + ' 篇文献 · ' + state.graph.meta.source);
    }

    function appendPlanetBackdrop(svg, width, height) {
        var centerX = width * 0.5;
        var centerY = height * 0.5;
        var radius = Math.min(width * 0.36, height * 0.39);
        var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        var gradient = document.createElementNS('http://www.w3.org/2000/svg', 'radialGradient');
        gradient.setAttribute('id', 'literatureSphereFill');
        gradient.setAttribute('cx', '34%');
        gradient.setAttribute('cy', '28%');
        [['0%', '#164e63', '.52'], ['52%', '#082f49', '.34'], ['100%', '#020914', '.78']].forEach(function (entry) {
            var stop = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            stop.setAttribute('offset', entry[0]);
            stop.setAttribute('stop-color', entry[1]);
            stop.setAttribute('stop-opacity', entry[2]);
            gradient.appendChild(stop);
        });
        defs.appendChild(gradient);
        svg.appendChild(defs);

        var halo = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        halo.setAttribute('cx', centerX);
        halo.setAttribute('cy', centerY);
        halo.setAttribute('r', radius + 9);
        halo.setAttribute('class', 'literature-sphere-halo');
        svg.appendChild(halo);

        var globe = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        globe.setAttribute('cx', centerX);
        globe.setAttribute('cy', centerY);
        globe.setAttribute('r', radius);
        globe.setAttribute('class', 'literature-sphere-globe');
        svg.appendChild(globe);

        [-0.54, 0, 0.54].forEach(function (offset) {
            var latitude = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
            latitude.setAttribute('cx', centerX);
            latitude.setAttribute('cy', centerY + radius * offset);
            latitude.setAttribute('rx', radius * Math.sqrt(1 - offset * offset));
            latitude.setAttribute('ry', radius * 0.16);
            latitude.setAttribute('class', 'literature-sphere-latitude');
            svg.appendChild(latitude);
        });
        [-54, 0, 54].forEach(function (angle) {
            var longitude = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
            longitude.setAttribute('cx', centerX);
            longitude.setAttribute('cy', centerY);
            longitude.setAttribute('rx', radius * 0.34);
            longitude.setAttribute('ry', radius);
            longitude.setAttribute('transform', 'rotate(' + angle + ' ' + centerX + ' ' + centerY + ')');
            longitude.setAttribute('class', 'literature-sphere-longitude');
            svg.appendChild(longitude);
        });
    }

    function layoutNodes(nodes, width, height) {
        if (state.view === 'timeline') return timelineLayout(nodes, width, height);
        var positions = {};
        var count = Math.max(1, nodes.length);
        var goldenAngle = Math.PI * (3 - Math.sqrt(5));
        nodes.forEach(function (node, index) {
            var vertical = 1 - (2 * (index + 0.5) / count);
            var ringRadius = Math.sqrt(Math.max(0, 1 - vertical * vertical));
            var angle = index * goldenAngle + (node.type === 'Topic' ? 0.45 : 0);
            positions[node.id] = {
                x: Math.cos(angle) * ringRadius,
                y: vertical,
                z: Math.sin(angle) * ringRadius,
                r: nodeRadius(node),
            };
        });
        return positions;
    }

    function updateSphereProjection() {
        var model = state.renderModel;
        if (!model) return;
        var sinY = Math.sin(state.rotationY);
        var cosY = Math.cos(state.rotationY);
        var sinX = Math.sin(state.rotationX);
        var cosX = Math.cos(state.rotationX);
        var centerX = model.width * 0.5;
        var centerY = model.height * 0.5;
        var nodeById = {};
        model.graph.nodes.forEach(function (node) { nodeById[node.id] = node; });

        Object.keys(model.layout).forEach(function (id) {
            var point = model.layout[id];
            var x1 = point.x * cosY + point.z * sinY;
            var z1 = -point.x * sinY + point.z * cosY;
            var y2 = point.y * cosX - z1 * sinX;
            var z2 = point.y * sinX + z1 * cosX;
            var perspective = 1 + z2 * 0.12;
            var scale = 0.72 + (z2 + 1) * 0.18;
            point.screenX = centerX + x1 * model.radius * perspective;
            point.screenY = centerY + y2 * model.radius * perspective;
            point.depth = z2;
            if (!point.element) return;
            point.element.setAttribute('transform', 'translate(' + point.screenX.toFixed(2) + ' ' + point.screenY.toFixed(2) + ') scale(' + scale.toFixed(3) + ')');
            point.element.style.opacity = String(Math.max(.28, .58 + z2 * .4));
            point.element.style.pointerEvents = z2 < -.58 ? 'none' : 'auto';
            if (point.labelElement) {
                var node = nodeById[id];
                var keepLabel = node && (node.type === 'Topic' || (state.selected && state.selected.id === id));
                point.labelElement.style.opacity = keepLabel || z2 > .16 ? '1' : '0';
            }
        });

        model.edges.forEach(function (line) {
            var edge = line._edgeData;
            var a = model.layout[edge.from], b = model.layout[edge.to];
            if (!a || !b) return;
            line.setAttribute('x1', a.screenX.toFixed(2));
            line.setAttribute('y1', a.screenY.toFixed(2));
            line.setAttribute('x2', b.screenX.toFixed(2));
            line.setAttribute('y2', b.screenY.toFixed(2));
            var depth = (a.depth + b.depth) * .5;
            var selectedEdge = state.selected && (edge.from === state.selected.id || edge.to === state.selected.id);
            line.setAttribute('stroke-opacity', selectedEdge ? Math.max(.38, .78 + depth * .16) : Math.max(.05, .16 + depth * .13));
        });
    }

    function startSphereAnimation() {
        if (!state.renderModel) return;
        state.lastFrameTime = performance.now();
        if (state.reduceMotion) return;
        function tick(timestamp) {
            if (!state.renderModel) return;
            var delta = Math.min(34, Math.max(0, timestamp - state.lastFrameTime));
            state.lastFrameTime = timestamp;
            if (!state.dragging) state.rotationY += delta * 0.00022;
            updateSphereProjection();
            state.animationFrame = requestAnimationFrame(tick);
        }
        state.animationFrame = requestAnimationFrame(tick);
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
            node.citation_count ? '<span>' + node.citation_count + ' 次被引</span>' : '',
            '</div>',
            '<div class="keyword-row">' + keywords + '</div>',
            '<p>' + escapeHtml(node.abstract || '暂无摘要') + '</p>',
            '<div class="score-row"><span>相关度</span><strong>' + Math.round((node.relevance || 0) * 100) + '%</strong></div>',
            '<div class="detail-actions">',
            '<button class="btn btn-sm btn-outline" type="button" data-action="favorite">加入收藏</button>',
            '<button class="btn btn-sm btn-outline" type="button" data-action="read">标记已读</button>',
            '<button class="btn btn-sm btn-outline" type="button" data-action="note">生成笔记</button>',
            '<button class="btn btn-sm btn-outline" type="button" data-action="trace">追踪星链</button>',
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
            analysisPanel.innerHTML = '<p class="section-kicker">图谱洞察</p><h2>图谱洞察</h2><p>导入文献后显示核心主题、关键论文、高频关键词、主要作者和数据质量提示</p>';
            return;
        }
        analysisPanel.innerHTML = [
            '<p class="section-kicker">图谱洞察</p>',
            '<h2>图谱洞察</h2>',
            listBlock('核心主题 Top 5', analysis.themes),
            listBlock('关键论文 Top 5', analysis.papers.map(function (p) { return p.title; })),
            listBlock('高频关键词 Top 10', analysis.keywords),
            listBlock('主要作者/团队', analysis.authors),
            listBlock('下一步阅读信号', analysis.recommended.map(function (p) { return p.title; })),
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
            overview: '动态文献星球',
            citation: '引用星球',
            keywords: '关键词星球',
            timeline: '时间线',
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

    if (canvas) {
        canvas.addEventListener('pointerdown', function (event) {
            if (!state.renderModel) return;
            state.dragging = true;
            state.dragDistance = 0;
            state.pointerX = event.clientX;
            state.pointerY = event.clientY;
            canvas.classList.add('is-dragging');
            if (canvas.setPointerCapture) canvas.setPointerCapture(event.pointerId);
        });
        canvas.addEventListener('pointermove', function (event) {
            if (!state.dragging || !state.renderModel) return;
            var dx = event.clientX - state.pointerX;
            var dy = event.clientY - state.pointerY;
            state.dragDistance += Math.abs(dx) + Math.abs(dy);
            state.pointerX = event.clientX;
            state.pointerY = event.clientY;
            state.rotationY += dx * 0.008;
            state.rotationX = Math.max(-1.05, Math.min(1.05, state.rotationX - dy * 0.006));
            updateSphereProjection();
        });
        function endPlanetDrag(event) {
            if (!state.dragging) return;
            state.dragging = false;
            canvas.classList.remove('is-dragging');
            if (canvas.releasePointerCapture && canvas.hasPointerCapture && canvas.hasPointerCapture(event.pointerId)) {
                canvas.releasePointerCapture(event.pointerId);
            }
            window.setTimeout(function () { state.dragDistance = 0; }, 0);
        }
        canvas.addEventListener('pointerup', endPlanetDrag);
        canvas.addEventListener('pointercancel', endPlanetDrag);
        canvas.addEventListener('pointerleave', function (event) {
            if (state.dragging && event.buttons === 0) endPlanetDrag(event);
        });
    }

    window.addEventListener('resize', function () { render(); });
    window.addEventListener('literature-library-updated', rebuildGraph);
    window.addEventListener('beforeunload', function () {
        if (state.animationFrame) cancelAnimationFrame(state.animationFrame);
    });

    rebuildGraph();
})();
