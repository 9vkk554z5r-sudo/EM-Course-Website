// OpenAlex citation network visualization.
document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('nebula-container');
    var form = document.getElementById('nebula-search-form');
    if (!container || typeof vis === 'undefined') return;

    var network = null;
    var status = document.getElementById('nebula-status');

    function setStatus(message, isError) {
        if (!status) return;
        status.textContent = message;
        status.style.color = isError ? '#f87171' : '';
    }

    function loadGraph(url) {
        container.innerHTML = '<div class="nebula-loading"><div class="spinner"></div><p>正在从 OpenAlex 加载...</p></div>';
        setStatus('正在检索并核对引用关系...', false);
        fetch(url, {headers: {'Accept': 'application/json'}})
            .then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok) throw new Error(data.error || '请求失败');
                    return data;
                });
            })
            .then(function (data) {
                network = renderNebula(container, data, network);
                var sync = data.sync || {};
                var suffix = data.query
                    ? '；新增 ' + (sync.created_nodes || 0) + ' 篇文献、' + (sync.created_edges || 0) + ' 条引用边'
                    : '';
                setStatus('已加载 ' + (data.nodes || []).length + ' 篇文献和 ' + (data.edges || []).length + ' 条真实引用关系' + suffix, false);
            })
            .catch(function (error) {
                setStatus('加载失败：' + error.message, true);
                container.innerHTML = '<div class="nebula-empty">无法加载图谱，请检查网络或稍后重试。</div>';
            });
    }

    if (form) {
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var query = document.getElementById('nebula-query').value.trim();
            var type = document.getElementById('nebula-query-type').value;
            if (!query) return;
            loadGraph('/api/nebula-data?q=' + encodeURIComponent(query) + '&type=' + encodeURIComponent(type));
        });
    }

    loadGraph('/api/nebula-data');
});

function topicColor(topic) {
    var palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
    var hash = 0;
    String(topic || '').split('').forEach(function (character) {
        hash = ((hash << 5) - hash) + character.charCodeAt(0);
        hash |= 0;
    });
    return palette[Math.abs(hash) % palette.length];
}

function renderNebula(container, data, oldNetwork) {
    var nodes = data.nodes || [];
    var edges = data.edges || [];
    if (oldNetwork) oldNetwork.destroy();

    if (nodes.length === 0) {
        container.innerHTML = '<div class="nebula-empty">暂无本地文献。请在上方输入关键词或 DOI 生成图谱。</div>';
        updateStats(nodes, edges, data.source);
        return null;
    }
    container.innerHTML = '';

    var visNodes = new vis.DataSet(nodes.map(function (node) {
        var color = topicColor(node.topic);
        var citations = Number(node.citation_count || 0);
        return {
            id: node.id,
            label: node.label || String(node.title || '').slice(0, 55),
            title: [node.title, node.authors, (node.journal || '') + (node.year ? ' (' + node.year + ')' : ''), 'Citations: ' + citations].filter(Boolean).join('\n'),
            url: node.url || (node.doi ? 'https://doi.org/' + node.doi : ''),
            color: {background: color, border: color, highlight: {background: '#ffffff', border: color}},
            borderWidth: 0,
            size: Math.max(9, Math.min(34, 9 + Math.log10(citations + 1) * 8)),
            font: {color: '#cbd5e1', size: 10, face: 'Inter, Noto Sans SC, sans-serif'}
        };
    }));

    var visEdges = new vis.DataSet(edges.map(function (edge, index) {
        return {
            id: index,
            from: edge.source || edge.from,
            to: edge.target || edge.to,
            width: Math.max(0.7, Math.min(2.5, Number(edge.weight || 1))),
            title: 'cites',
            color: {color: 'rgba(96,165,250,0.28)', highlight: 'rgba(34,211,238,0.8)', hover: 'rgba(34,211,238,0.8)'},
            smooth: {type: 'continuous'}
        };
    }));

    var options = {
        nodes: {shape: 'dot', scaling: {label: {enabled: true, min: 9, max: 14}}},
        edges: {arrows: {to: {enabled: true, scaleFactor: 0.45}}, selectionWidth: 2},
        physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {gravitationalConstant: -45, centralGravity: 0.008, springLength: 145, springConstant: 0.025, damping: 0.5},
            stabilization: {iterations: 160, fit: true},
            maxVelocity: 35,
            minVelocity: 0.15
        },
        interaction: {hover: true, tooltipDelay: 180, navigationButtons: true, keyboard: true},
        layout: {improvedLayout: true},
        height: '100%',
        width: '100%'
    };

    var network = new vis.Network(container, {nodes: visNodes, edges: visEdges}, options);
    network.on('doubleClick', function (params) {
        if (!params.nodes.length) return;
        var node = visNodes.get(params.nodes[0]);
        if (node && node.url) window.open(node.url, '_blank', 'noopener');
    });
    updateStats(nodes, edges, data.source);
    return network;
}

function updateStats(nodes, edges, source) {
    var topics = new Set(nodes.map(function (node) { return node.topic || 'Uncategorized'; }));
    var nodeCount = document.getElementById('node-count');
    var edgeCount = document.getElementById('edge-count');
    var topicCount = document.getElementById('topic-count');
    var sourceLabel = document.getElementById('nebula-source');
    if (nodeCount) nodeCount.textContent = nodes.length;
    if (edgeCount) edgeCount.textContent = edges.length;
    if (topicCount) topicCount.textContent = topics.size;
    if (sourceLabel) sourceLabel.textContent = source || 'OpenAlex';
}
