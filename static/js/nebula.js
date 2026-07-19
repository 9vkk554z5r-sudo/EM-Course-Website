// OpenAlex citation network visualization.
document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('nebula-container');
    var form = document.getElementById('nebula-search-form');
    var submit = document.getElementById('nebula-submit');
    var fitButton = document.getElementById('nebula-fit');
    var status = document.getElementById('nebula-status');
    var network = null;

    if (!container) return;

    function setStatus(message, isError) {
        if (!status) return;
        status.textContent = message;
        status.classList.toggle('is-error', Boolean(isError));
    }

    function setBusy(isBusy) {
        if (!submit) return;
        submit.disabled = isBusy;
        submit.classList.toggle('is-loading', isBusy);
        submit.textContent = isBusy ? (submit.dataset.loadingText || '正在生成') : '检索并生成图谱';
    }

    function loadGraph(url) {
        setBusy(true);
        container.innerHTML = '<div class="nebula-loading"><div class="spinner"></div><p>正在从 OpenAlex 加载...</p><span>正在整理文献节点与引用关系</span></div>';
        setStatus('正在检索并核对引用关系...', false);
        fetch(url, {headers: {'Accept': 'application/json'}})
            .then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok) throw new Error(data.error || '请求失败');
                    return data;
                });
            })
            .then(function (data) {
                var graphData = normalizeGraphData(data);
                network = renderNebula(container, graphData, network);
                var sync = data.sync || {};
                var suffix = data.query
                    ? '；新增 ' + (sync.created_nodes || 0) + ' 篇文献、' + (sync.created_edges || 0) + ' 条引用关系'
                    : '';
                if (graphData.isDemo) {
                    setStatus('本地暂无文献，已载入旧版动态星云示例；输入关键词或 DOI 可生成真实图谱', false);
                } else {
                    setStatus('已加载 ' + graphData.nodes.length + ' 篇文献和 ' + graphData.edges.length + ' 条真实引用关系' + suffix, false);
                }
            })
            .catch(function (error) {
                var graphData = sampleNebulaData();
                network = renderNebula(container, graphData, network);
                setStatus('真实数据加载失败，已切换到旧版动态星云示例：' + error.message, true);
            })
            .finally(function () {
                setBusy(false);
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

    if (fitButton) {
        fitButton.addEventListener('click', function () {
            if (network) network.fit({animation: {duration: 420, easingFunction: 'easeInOutQuad'}});
        });
    }

    loadGraph('/api/nebula-data');
});

function topicColor(topic) {
    var palette = ['#22d3ee', '#2ef2c3', '#60a5fa', '#f3c86b', '#a78bfa', '#fb7185', '#34d399'];
    var hash = 0;
    String(topic || '').split('').forEach(function (character) {
        hash = ((hash << 5) - hash) + character.charCodeAt(0);
        hash |= 0;
    });
    return palette[Math.abs(hash) % palette.length];
}

function compactNodeLabel(value) {
    var text = String(value || '未命名文献').replace(/\s+/g, ' ').trim();
    var firstLineLength = 17;
    var maxLength = 34;
    if (text.length <= firstLineLength) return text;
    var clipped = text.length > maxLength ? text.slice(0, maxLength - 1) + '…' : text;
    return clipped.slice(0, firstLineLength) + '\n' + clipped.slice(firstLineLength);
}

function sampleNebulaData() {
    return {
        isDemo: true,
        source: '动态星云示例',
        nodes: [
            {id: 'topic', label: 'cryo-EM', title: 'cryo-EM', topic: 'cryo-EM', citation_count: 80},
            {id: 'paper-a', label: 'Single particle', title: 'Single particle analysis', topic: 'cryo-EM', citation_count: 54},
            {id: 'paper-b', label: 'Tomography', title: 'Electron tomography', topic: 'electron microscopy', citation_count: 38},
            {id: 'method', label: '3D reconstruction', title: '3D reconstruction', topic: 'cryo-EM', citation_count: 42},
            {id: 'author', label: 'Author cluster', title: 'Author cluster', topic: 'electron microscopy', citation_count: 24},
            {id: 'keyword', label: 'Protocol', title: 'Protocol extraction', topic: 'cryo-EM', citation_count: 28}
        ],
        edges: [
            {source: 'topic', target: 'paper-a', weight: .9},
            {source: 'topic', target: 'paper-b', weight: .7},
            {source: 'topic', target: 'method', weight: .85},
            {source: 'paper-a', target: 'keyword', weight: .6},
            {source: 'paper-b', target: 'author', weight: .48},
            {source: 'method', target: 'keyword', weight: .72}
        ]
    };
}

function normalizeGraphData(data) {
    var graphData = data || {};
    if (!Array.isArray(graphData.nodes) || graphData.nodes.length === 0) return sampleNebulaData();
    return graphData;
}
function renderNebula(container, data, oldNetwork) {
    var nodes = data.nodes || [];
    var edges = data.edges || [];
    if (oldNetwork) oldNetwork.destroy();

    if (nodes.length === 0) {
        container.innerHTML = '<div class="nebula-empty"><strong>暂无可展示文献</strong><span>请在上方输入关键词或 DOI 生成图谱</span></div>';
        updateStats(nodes, edges, data.source);
        return null;
    }

    if (typeof vis === 'undefined' || !vis.DataSet || !vis.Network) {
        renderNebulaFallback(container, data);
        updateStats(nodes, edges, data.source);
        return null;
    }
    container.innerHTML = '';

    var visNodes = new vis.DataSet(nodes.map(function (node) {
        var color = topicColor(node.topic);
        var citations = Number(node.citation_count || 0);
        var fullTitle = node.title || node.label || '未命名文献';
        return {
            id: node.id,
            label: compactNodeLabel(fullTitle),
            title: [fullTitle, node.authors, (node.journal || '') + (node.year ? ' (' + node.year + ')' : ''), '被引次数：' + citations].filter(Boolean).join('\n'),
            url: node.url || (node.doi ? 'https://doi.org/' + node.doi : ''),
            color: {
                background: color,
                border: 'rgba(235, 252, 255, .92)',
                highlight: {background: '#f5ffff', border: color},
                hover: {background: color, border: '#ffffff'}
            },
            borderWidth: 1,
            borderWidthSelected: 3,
            size: Math.max(11, Math.min(31, 11 + Math.log10(citations + 1) * 7)),
            shadow: {enabled: true, color: color, size: 16, x: 0, y: 0},
            font: {
                color: '#e8f6fb',
                size: 11,
                face: 'Inter, Noto Sans SC, sans-serif',
                strokeWidth: 5,
                strokeColor: 'rgba(3, 10, 22, .82)',
                vadjust: 4,
                multi: false
            }
        };
    }));

    var visEdges = new vis.DataSet(edges.map(function (edge, index) {
        return {
            id: index,
            from: edge.source || edge.from,
            to: edge.target || edge.to,
            width: Math.max(0.6, Math.min(1.8, Number(edge.weight || 1))),
            title: '引用关系',
            color: {
                color: 'rgba(110, 211, 230, .22)',
                highlight: 'rgba(46, 242, 195, .82)',
                hover: 'rgba(0, 229, 255, .68)',
                inherit: false
            },
            smooth: {enabled: true, type: 'continuous', roundness: 0.28}
        };
    }));

    var options = {
        autoResize: true,
        nodes: {
            shape: 'dot',
            chosen: true,
            scaling: {min: 11, max: 31, label: {enabled: false}}
        },
        edges: {
            arrows: {to: {enabled: true, scaleFactor: 0.42}},
            selectionWidth: 1.5,
            hoverWidth: 0.6
        },
        physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -72,
                centralGravity: 0.006,
                springLength: 190,
                springConstant: 0.018,
                damping: 0.58,
                avoidOverlap: 0.72
            },
            stabilization: {enabled: true, iterations: 220, updateInterval: 25, fit: true},
            maxVelocity: 28,
            minVelocity: 0.12
        },
        interaction: {
            hover: true,
            hoverConnectedEdges: true,
            tooltipDelay: 240,
            navigationButtons: false,
            keyboard: {enabled: true, bindToWindow: false},
            multiselect: false
        },
        layout: {improvedLayout: true, randomSeed: 18},
        height: '100%',
        width: '100%'
    };

    var network = new vis.Network(container, {nodes: visNodes, edges: visEdges}, options);
    network.once('stabilizationIterationsDone', function () {
        network.fit({animation: {duration: 360, easingFunction: 'easeInOutQuad'}});
    });
    network.on('doubleClick', function (params) {
        if (!params.nodes.length) return;
        var node = visNodes.get(params.nodes[0]);
        if (node && node.url) window.open(node.url, '_blank', 'noopener');
    });
    updateStats(nodes, edges, data.source);
    return network;
}

function renderNebulaFallback(container, data) {
    var nodes = data.nodes || [];
    var edges = data.edges || [];
    var width = 920;
    var height = 520;
    var centerX = width / 2;
    var centerY = height / 2;
    var positions = {};

    nodes.forEach(function (node, index) {
        var progress = nodes.length <= 1 ? 0 : index / nodes.length;
        var radius = 80 + (index % 4) * 42 + progress * 120;
        var angle = progress * Math.PI * 2 + radius * .012;
        positions[node.id] = {
            x: centerX + Math.cos(angle) * radius,
            y: centerY + Math.sin(angle) * radius * .58
        };
    });

    var edgeMarkup = edges.map(function (edge) {
        var start = positions[edge.source || edge.from];
        var end = positions[edge.target || edge.to];
        if (!start || !end) return '';
        return '<line class="nebula-edge" x1="' + start.x + '" y1="' + start.y + '" x2="' + end.x + '" y2="' + end.y + '" />';
    }).join('');

    var nodeMarkup = nodes.map(function (node, index) {
        var position = positions[node.id];
        var size = Math.max(8, Math.min(24, Number(node.citation_count || 0) / 5 + 8));
        var hueClass = index % 3 === 0 ? 'mint' : (index % 3 === 1 ? 'cyan' : 'blue');
        return '<g class="nebula-node ' + hueClass + '">' +
            '<circle cx="' + position.x + '" cy="' + position.y + '" r="' + size + '" />' +
            '<text x="' + (position.x + size + 8) + '" y="' + (position.y + 4) + '">' + escapeNebulaText(node.label || node.title || 'Node') + '</text>' +
            '</g>';
    }).join('');

    container.innerHTML =
        '<svg class="nebula-fallback-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="NEXUS 引用星链关系网络">' +
        '<defs><radialGradient id="nebulaGlow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#2ef2c3" stop-opacity=".35"/><stop offset="100%" stop-color="#00e5ff" stop-opacity="0"/></radialGradient></defs>' +
        '<rect width="100%" height="100%" fill="url(#nebulaGlow)" opacity=".55" />' + edgeMarkup + nodeMarkup + '</svg>' +
        '<div class="nebula-note">交互组件未加载，当前显示基础星云图</div>';
}

function escapeNebulaText(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
        return ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[character];
    });
}
function updateStats(nodes, edges, source) {
    var topics = new Set(nodes.map(function (node) { return node.topic || '未分类'; }));
    var nodeCount = document.getElementById('node-count');
    var edgeCount = document.getElementById('edge-count');
    var topicCount = document.getElementById('topic-count');
    var sourceLabel = document.getElementById('nebula-source');
    if (nodeCount) nodeCount.textContent = nodes.length;
    if (edgeCount) edgeCount.textContent = edges.length;
    if (topicCount) topicCount.textContent = topics.size;
    if (sourceLabel) sourceLabel.textContent = source || 'OpenAlex';
}