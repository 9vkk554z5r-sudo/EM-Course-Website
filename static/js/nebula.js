// Nebula Graph — Citation Network Visualization with SVG fallback
(function () {
    document.addEventListener('DOMContentLoaded', function() {
        var container = document.getElementById('nebula-container');
        if (!container) return;

        fetch('/api/nebula-data')
            .then(function(resp) { return resp.json(); })
            .then(function(data) {
                renderNebula(container, data || {});
            })
            .catch(function(err) {
                console.error('Failed to load nebula data:', err);
                renderNebulaFallback(container, sampleNebulaData(), true);
            });
    });

    function sampleNebulaData() {
        return {
            nodes: [
                { id: 'topic', label: 'cryo-EM', title: 'cryo-EM', topic: 'cryo-EM', citation_count: 80 },
                { id: 'paper-a', label: 'Single particle', title: 'Single particle analysis', topic: 'cryo-EM', citation_count: 54 },
                { id: 'paper-b', label: 'Tomography', title: 'Electron tomography', topic: 'electron microscopy', citation_count: 38 },
                { id: 'method', label: '3D reconstruction', title: '3D reconstruction', topic: 'cryo-EM', citation_count: 42 },
                { id: 'author', label: 'Author cluster', title: 'Author cluster', topic: 'electron microscopy', citation_count: 24 },
                { id: 'keyword', label: 'Protocol', title: 'Protocol extraction', topic: 'cryo-EM', citation_count: 28 }
            ],
            edges: [
                { source: 'topic', target: 'paper-a', weight: .9 },
                { source: 'topic', target: 'paper-b', weight: .7 },
                { source: 'topic', target: 'method', weight: .85 },
                { source: 'paper-a', target: 'keyword', weight: .6 },
                { source: 'paper-b', target: 'author', weight: .48 },
                { source: 'method', target: 'keyword', weight: .72 }
            ]
        };
    }

    function normalizeData(data) {
        var nodes = data.nodes || [];
        var edges = data.edges || [];
        if (!nodes.length) return sampleNebulaData();
        return { nodes: nodes, edges: edges };
    }

    function renderNebula(container, data) {
        var normalized = normalizeData(data);
        updateStats(normalized.nodes, normalized.edges);

        if (window.vis && window.vis.DataSet && window.vis.Network) {
            renderVisNebula(container, normalized.nodes, normalized.edges);
            return;
        }
        renderNebulaFallback(container, normalized, false);
    }

    function renderVisNebula(container, nodes, edges) {
        var colorMap = {
            'electron microscopy': '#4f8cff',
            'cryo-EM': '#2ef2c3',
            'semiconductor characterization': '#f3c86b'
        };
        var defaultColor = '#00e5ff';

        var visNodes = new vis.DataSet(nodes.map(function(n) {
            var color = colorMap[n.topic] || defaultColor;
            return {
                id: n.id,
                label: n.label,
                title: '<div style="max-width:300px;padding:8px;">' +
                    '<strong>' + (n.title || n.label || '') + '</strong><br>' +
                    '<span style="font-size:0.8rem;color:#a9b8c8;">' + (n.authors || '') + '</span><br>' +
                    '<span style="font-size:0.75rem;color:#7f91a4;">' + (n.journal || '') + ' (' + (n.year || '') + ')</span>' +
                    '<br><span style="font-size:0.75rem;">Citations: ' + (n.citation_count || 0) + '</span></div>',
                color: {
                    background: color,
                    border: color,
                    highlight: { background: '#f3faff', border: color }
                },
                borderWidth: 1,
                size: Math.max(9, Math.min(30, (n.citation_count || 0) / 5 + 9)),
                font: { color: '#dffcff', size: 10, face: 'Inter, Noto Sans SC, sans-serif' }
            };
        }));

        var visEdges = new vis.DataSet(edges.map(function(e) {
            return {
                from: e.source,
                to: e.target,
                width: Math.max(0.6, Math.min(3, (e.weight || 0.5) * 1.4)),
                color: { color: 'rgba(0,229,255,0.22)', highlight: 'rgba(46,242,195,0.62)', hover: 'rgba(46,242,195,0.62)' },
                smooth: { type: 'continuous' }
            };
        }));

        container.innerHTML = '';
        new vis.Network(container, { nodes: visNodes, edges: visEdges }, {
            nodes: { shape: 'dot', scaling: { label: { enabled: true, min: 8, max: 13 } } },
            edges: { smooth: true, arrows: { to: { enabled: true, scaleFactor: 0.35 } } },
            physics: {
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {
                    gravitationalConstant: -38,
                    centralGravity: 0.006,
                    springLength: 156,
                    springConstant: 0.022,
                    damping: 0.43
                },
                stabilization: { iterations: 100 },
                maxVelocity: 38,
                minVelocity: 0.1
            },
            interaction: { hover: true, tooltipDelay: 180, navigationButtons: true, keyboard: true },
            layout: { improvedLayout: true },
            height: '100%',
            width: '100%'
        });
    }

    function renderNebulaFallback(container, data, showError) {
        var nodes = data.nodes || [];
        var edges = data.edges || [];
        var width = 920;
        var height = 520;
        var cx = width / 2;
        var cy = height / 2;
        var positions = {};
        nodes.forEach(function(node, i) {
            var t = nodes.length <= 1 ? 0 : i / nodes.length;
            var radius = 80 + (i % 4) * 42 + t * 120;
            var angle = t * Math.PI * 2 + radius * 0.012;
            positions[node.id] = {
                x: cx + Math.cos(angle) * radius,
                y: cy + Math.sin(angle) * radius * 0.58
            };
        });
        var edgeMarkup = edges.map(function(edge) {
            var a = positions[edge.source];
            var b = positions[edge.target];
            if (!a || !b) return '';
            return '<line class="nebula-edge" x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" />';
        }).join('');
        var nodeMarkup = nodes.map(function(node, i) {
            var p = positions[node.id];
            var size = Math.max(8, Math.min(24, (node.citation_count || 0) / 5 + 8));
            var hueClass = i % 3 === 0 ? 'mint' : (i % 3 === 1 ? 'cyan' : 'blue');
            return '<g class="nebula-node ' + hueClass + '">' +
                '<circle cx="' + p.x + '" cy="' + p.y + '" r="' + size + '" />' +
                '<text x="' + (p.x + size + 8) + '" y="' + (p.y + 4) + '">' + escapeText(node.label || node.title || 'Node') + '</text>' +
                '</g>';
        }).join('');
        container.innerHTML =
            '<svg class="nebula-fallback-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="文献星云关系网络">' +
            '<defs><radialGradient id="nebulaGlow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#2ef2c3" stop-opacity=".35"/><stop offset="100%" stop-color="#00e5ff" stop-opacity="0"/></radialGradient></defs>' +
            '<rect width="100%" height="100%" fill="url(#nebulaGlow)" opacity=".55" />' + edgeMarkup + nodeMarkup + '</svg>' +
            (showError ? '<div class="nebula-note">已使用本地示例星云展示，真实数据加载失败。</div>' : '');
    }

    function updateStats(nodes, edges) {
        var topics = new Set(nodes.map(function(n) { return n.topic || 'Topic'; }));
        var nodeCount = document.getElementById('node-count');
        var edgeCount = document.getElementById('edge-count');
        var topicCount = document.getElementById('topic-count');
        if (nodeCount) nodeCount.textContent = nodes.length;
        if (edgeCount) edgeCount.textContent = edges.length;
        if (topicCount) topicCount.textContent = topics.size;
    }

    function escapeText(value) {
        return String(value).replace(/[&<>"']/g, function(ch) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch];
        });
    }
})();
