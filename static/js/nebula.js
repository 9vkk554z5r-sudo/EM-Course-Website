// Nebula Graph — Citation Network Visualization
document.addEventListener('DOMContentLoaded', function() {
    var container = document.getElementById('nebula-container');
    if (!container) return;

    fetch('/api/nebula-data')
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            renderNebula(container, data);
        })
        .catch(function(err) {
            console.error('Failed to load nebula data:', err);
            container.innerHTML = '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:rgba(255,255,255,0.3);text-align:center;"><p style="font-size:1.1rem;">Failed to load</p><p style="font-size:0.83rem;">Ensure literature data exists</p></div>';
        });
});

function renderNebula(container, data) {
    var nodes = data.nodes || [];
    var edges = data.edges || [];

    if (nodes.length === 0) {
        container.innerHTML = '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:rgba(255,255,255,0.3);text-align:center;"><p style="font-size:1.2rem;">No literature data</p><p style="font-size:0.83rem;">Subscribe to topics and refresh literature first</p></div>';
        return;
    }

    var colorMap = {
        'electron microscopy': '#3b82f6',
        'cryo-EM': '#10b981',
        'semiconductor characterization': '#f59e0b'
    };
    var defaultColor = '#8b5cf6';

    var visNodes = new vis.DataSet(nodes.map(function(n) {
        var color = colorMap[n.topic] || defaultColor;
        return {
            id: n.id,
            label: n.label,
            title: '<div style="max-width:300px;padding:8px;">' +
                '<strong>' + n.title + '</strong><br>' +
                '<span style="font-size:0.8rem;color:#94a3b8;">' + (n.authors || '') + '</span><br>' +
                '<span style="font-size:0.75rem;color:#64748b;">' + (n.journal || '') + ' (' + (n.year || '') + ')</span>' +
                '<br><span style="font-size:0.75rem;">Citations: ' + (n.citation_count || 0) + '</span></div>',
            color: {
                background: color,
                border: color,
                highlight: { background: '#ffffff', border: color }
            },
            borderWidth: 0,
            size: Math.max(8, Math.min(28, (n.citation_count || 0) / 5 + 8)),
            font: { color: '#94a3b8', size: 9, face: 'Inter, Noto Sans SC, sans-serif' }
        };
    }));

    var visEdges = new vis.DataSet(edges.map(function(e) {
        return {
            from: e.source,
            to: e.target,
            width: Math.max(0.3, Math.min(3, (e.weight || 0.5) * 1.2)),
            color: { color: 'rgba(59,130,246,0.2)', highlight: 'rgba(59,130,246,0.5)', hover: 'rgba(59,130,246,0.5)' },
            smooth: { type: 'continuous' }
        };
    }));

    var options = {
        nodes: { shape: 'dot', scaling: { label: { enabled: true, min: 8, max: 13 } } },
        edges: { smooth: true, arrows: { to: { enabled: true, scaleFactor: 0.4 } } },
        physics: {
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -35,
                centralGravity: 0.005,
                springLength: 160,
                springConstant: 0.02,
                damping: 0.4
            },
            stabilization: { iterations: 100 },
            maxVelocity: 40,
            minVelocity: 0.1
        },
        interaction: { hover: true, tooltipDelay: 200, navigationButtons: true, keyboard: true },
        layout: { improvedLayout: true },
        height: '100%',
        width: '100%'
    };

    var network = new vis.Network(container, { nodes: visNodes, edges: visEdges }, options);

    // Update stats
    var topics = new Set(nodes.map(function(n) { return n.topic; }));
    var nodeCount = document.getElementById('node-count');
    var edgeCount = document.getElementById('edge-count');
    var topicCount = document.getElementById('topic-count');
    if (nodeCount) nodeCount.textContent = nodes.length;
    if (edgeCount) edgeCount.textContent = edges.length;
    if (topicCount) topicCount.textContent = topics.size;

    var loading = container.querySelector('.nebula-loading');
    if (loading) loading.remove();
}
