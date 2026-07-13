(function () {
    'use strict';

    var container = null;
    var activeScene = null;
    var graphCache = null;
    var renderTicket = 0;

    var colors = {
        Topic: '#2ef2c3',
        Paper: '#dfeaf2',
        Keyword: '#70e1d1',
        Author: '#f3c86b',
        Method: '#78aefc',
        Protocol: '#b8a2ff'
    };

    document.addEventListener('DOMContentLoaded', function () {
        container = document.getElementById('nebula-container');
        if (!container || typeof THREE === 'undefined') return;

        var searchForm = document.querySelector('[data-graph-search]');
        var controls = document.querySelectorAll('[data-filter-year], [data-filter-relevance], [data-filter-bookmarked], [data-filter-types] input, [data-view]');

        if (searchForm) {
            searchForm.addEventListener('submit', function () {
                window.setTimeout(loadMergedGraph, 0);
            });
        }
        controls.forEach(function (control) {
            control.addEventListener('change', renderFilteredGraph);
            if (control.hasAttribute('data-view')) control.addEventListener('click', function () {
                window.setTimeout(renderFilteredGraph, 0);
            });
        });
        window.addEventListener('literature-library-updated', loadMergedGraph);
        loadMergedGraph();
    });

    function currentQuery() {
        var input = document.querySelector('[data-graph-search] input[name="q"]');
        return input && input.value.trim() ? input.value.trim() : 'cryo-EM';
    }

    function loadMergedGraph() {
        var ticket = ++renderTicket;
        var localGraph = buildLocalGraph();
        fetch('/api/literature-graph?q=' + encodeURIComponent(currentQuery()), { headers: { Accept: 'application/json' } })
            .then(function (response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function (remoteGraph) {
                if (ticket !== renderTicket) return;
                graphCache = mergeGraphs(localGraph, remoteGraph || {});
                renderFilteredGraph();
            })
            .catch(function () {
                if (ticket !== renderTicket) return;
                graphCache = localGraph && localGraph.nodes && localGraph.nodes.length ? localGraph : null;
                if (graphCache) renderFilteredGraph();
            });
    }

    function buildLocalGraph() {
        if (!window.LiteratureStore || !window.LiteratureGraphBuilder) return { nodes: [], edges: [] };
        var papers = LiteratureStore.getAll();
        if (!papers.length && window.LiteratureParsers) {
            papers = LiteratureParsers.samplePapers().map(function (paper) {
                return LiteratureStore.normalizePaper(paper, 'sample');
            });
        }
        return papers.length ? LiteratureGraphBuilder.buildGraph(papers, currentQuery()) : { nodes: [], edges: [] };
    }

    function mergeGraphs(localGraph, remoteGraph) {
        localGraph = localGraph || { nodes: [], edges: [] };
        remoteGraph = remoteGraph || { nodes: [], edges: [] };
        var nodes = [];
        var ids = {};
        var paperTitles = {};
        var aliases = {};

        function addNode(node) {
            if (!node || !node.id) return;
            var titleKey = node.type === 'Paper' ? String(node.title || node.label || '').trim().toLowerCase() : '';
            var existing = ids[node.id] ? node.id : (titleKey ? paperTitles[titleKey] : '');
            if (existing) {
                aliases[node.id] = existing;
                return;
            }
            nodes.push(node);
            ids[node.id] = true;
            if (titleKey) paperTitles[titleKey] = node.id;
        }

        (localGraph.nodes || []).forEach(addNode);
        (remoteGraph.nodes || []).forEach(addNode);

        var edges = [];
        var edgeKeys = {};
        function addEdge(edge) {
            if (!edge) return;
            var from = aliases[edge.from] || aliases[edge.source] || edge.from || edge.source;
            var to = aliases[edge.to] || aliases[edge.target] || edge.to || edge.target;
            if (!ids[from] || !ids[to]) return;
            var relation = edge.relation || 'similar_work';
            var key = from + '|' + to + '|' + relation;
            if (edgeKeys[key]) return;
            edgeKeys[key] = true;
            edges.push({ from: from, to: to, relation: relation, weight: edge.weight || 0.5 });
        }
        (localGraph.edges || []).forEach(addEdge);
        (remoteGraph.edges || []).forEach(addEdge);

        return { nodes: nodes, edges: edges, seed: localGraph.seed || remoteGraph.seed || null };
    }

    function renderFilteredGraph() {
        if (!graphCache || !container) return;
        var yearEl = document.querySelector('[data-filter-year]');
        var relevanceEl = document.querySelector('[data-filter-relevance]');
        var bookmarkedEl = document.querySelector('[data-filter-bookmarked]');
        var checkedTypes = Array.prototype.slice.call(document.querySelectorAll('[data-filter-types] input:checked')).map(function (input) { return input.value; });
        var activeView = document.querySelector('[data-view].active');
        var view = activeView ? activeView.getAttribute('data-view') : 'citation';
        var year = yearEl ? yearEl.value : 'all';
        var relevance = relevanceEl ? parseFloat(relevanceEl.value || '0') : 0;

        var nodes = graphCache.nodes.filter(function (node) {
            if (checkedTypes.length && checkedTypes.indexOf(node.type) === -1 && !(node.type === 'Protocol' && checkedTypes.indexOf('Method') !== -1)) return false;
            if (bookmarkedEl && bookmarkedEl.checked && !node.bookmarked) return false;
            if ((node.relevance || 0) < relevance) return false;
            if (year !== 'all' && node.year && Number(node.year) < Number(year)) return false;
            if (view === 'citation' && ['Topic', 'Paper', 'Author'].indexOf(node.type) === -1) return false;
            if (view === 'keywords' && ['Topic', 'Paper', 'Keyword', 'Method', 'Protocol'].indexOf(node.type) === -1) return false;
            return true;
        }).slice(0, 42);

        var ids = {};
        nodes.forEach(function (node) { ids[node.id] = true; });
        var edges = graphCache.edges.filter(function (edge) {
            return ids[edge.from] && ids[edge.to];
        }).slice(0, 90);

        renderPlanetaryNebula(nodes, edges);
    }

    function renderPlanetaryNebula(nodes, edges) {
        if (!nodes.length) return;
        disposeActiveScene();
        updateStats(nodes, edges);

        var width = Math.max(container.clientWidth, 320);
        var height = Math.max(container.clientHeight, 300);
        var scene = new THREE.Scene();
        var camera = new THREE.PerspectiveCamera(48, width / height, 0.1, 120);
        camera.position.set(0, 3.2, 17);

        var renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.domElement.setAttribute('aria-label', '动态文献行星星云');
        renderer.domElement.style.display = 'block';
        renderer.domElement.style.width = '100%';
        renderer.domElement.style.height = '100%';
        container.innerHTML = '';
        container.appendChild(renderer.domElement);

        scene.add(new THREE.AmbientLight(0x385071, 1.15));
        var keyLight = new THREE.DirectionalLight(0xc7f9ff, 1.4);
        keyLight.position.set(8, 12, 10);
        scene.add(keyLight);
        var rimLight = new THREE.PointLight(0x2ef2c3, 1.2, 32);
        rimLight.position.set(-7, -2, 5);
        scene.add(rimLight);

        addStarField(scene);
        var glow = makeGlowSprite('#2ef2c3');
        glow.scale.set(12, 12, 1);
        scene.add(glow);

        var topic = nodes.find(function (node) { return node.type === 'Topic'; }) || nodes[0];
        var nodeMap = {};
        var orbiters = [];
        var clickableMeshes = [];

        nodes.forEach(function (node, index) {
            var isCenter = node.id === topic.id;
            var baseColor = colors[node.type] || '#5fd7ff';
            var size = isCenter ? 1.05 : nodeSize(node);
            var geometry = new THREE.SphereGeometry(size, isCenter ? 32 : 16, isCenter ? 32 : 16);
            var color = new THREE.Color(baseColor);
            var material = new THREE.MeshPhongMaterial({
                color: color,
                emissive: color,
                emissiveIntensity: isCenter ? 0.62 : 0.24,
                shininess: 72,
                transparent: true,
                opacity: node.type === 'Paper' ? 0.96 : 1
            });
            var mesh = new THREE.Mesh(geometry, material);
            mesh.userData = { node: node, baseScale: 1 };
            scene.add(mesh);
            clickableMeshes.push(mesh);
            nodeMap[node.id] = mesh;

            var label = makeLabel(node.label || node.title || node.type, isCenter);
            scene.add(label);
            mesh.userData.label = label;

            if (isCenter) {
                mesh.position.set(0, 0, 0);
                label.position.set(0, 1.75, 0);
            } else {
                var orbitIndex = orbiters.length;
                var ring = orbitIndex % 5;
                var radius = 2.2 + ring * 1.35 + Math.floor(orbitIndex / 5) * 0.16;
                var angle = (orbitIndex / Math.max(1, nodes.length - 1)) * Math.PI * 2 + ring * 0.56;
                var y = ((orbitIndex % 7) - 3) * 0.23;
                orbiters.push({
                    mesh: mesh,
                    label: label,
                    angle: angle,
                    radius: radius,
                    y: y,
                    speed: 0.055 + (orbitIndex % 6) * 0.008,
                    phase: orbitIndex * 0.7
                });
            }
        });

        addOrbitRings(scene);
        var relationLines = buildRelationLines(scene, edges, nodeMap);
        var interaction = bindInteraction(container, renderer, camera, clickableMeshes);
        var rotationX = -0.12;
        var rotationY = 0;
        var lastTime = 0;
        var frameId = 0;
        var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function animate(time) {
            frameId = requestAnimationFrame(animate);
            var delta = lastTime ? Math.min((time - lastTime) / 1000, 0.05) : 0;
            lastTime = time;
            if (!reducedMotion) {
                rotationY += interaction.dragging ? 0 : delta * 0.08;
                orbiters.forEach(function (item) {
                    item.angle += delta * item.speed;
                    item.mesh.rotation.y += delta * 0.75;
                });
                nodeMap[topic.id].rotation.y += delta * 0.28;
            }

            orbiters.forEach(function (item) {
                var angle = item.angle + rotationY;
                var x = Math.cos(angle) * item.radius;
                var z = Math.sin(angle) * item.radius * 0.62;
                var y = item.y + Math.sin(angle * 1.7 + item.phase) * 0.24;
                var cosX = Math.cos(rotationX);
                var sinX = Math.sin(rotationX);
                item.mesh.position.set(x, y * cosX - z * sinX, y * sinX + z * cosX);
                item.label.position.set(item.mesh.position.x, item.mesh.position.y + 0.62, item.mesh.position.z);
            });
            interaction.applyRotation(function (dx, dy) {
                rotationY += dx;
                rotationX = Math.max(-0.55, Math.min(0.45, rotationX + dy));
            });
            updateRelationLines(relationLines);
            renderer.render(scene, camera);
        }
        frameId = requestAnimationFrame(animate);

        function resize() {
            if (!container || !renderer) return;
            var nextWidth = Math.max(container.clientWidth, 320);
            var nextHeight = Math.max(container.clientHeight, 300);
            camera.aspect = nextWidth / nextHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(nextWidth, nextHeight);
        }
        window.addEventListener('resize', resize);

        activeScene = {
            cancel: function () {
                cancelAnimationFrame(frameId);
                window.removeEventListener('resize', resize);
                interaction.dispose();
                scene.traverse(function (object) {
                    if (object.geometry) object.geometry.dispose();
                    if (object.material) {
                        if (object.material.map) object.material.map.dispose();
                        object.material.dispose();
                    }
                });
                renderer.dispose();
            }
        };
    }

    function addStarField(scene) {
        var geometry = new THREE.BufferGeometry();
        var positions = [];
        for (var i = 0; i < 900; i += 1) {
            var radius = 10 + Math.random() * 32;
            var theta = Math.random() * Math.PI * 2;
            var phi = Math.acos(2 * Math.random() - 1);
            positions.push(
                radius * Math.sin(phi) * Math.cos(theta),
                radius * Math.cos(phi) * 0.42,
                radius * Math.sin(phi) * Math.sin(theta)
            );
        }
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        scene.add(new THREE.Points(geometry, new THREE.PointsMaterial({
            color: 0xc9f5ff,
            size: 0.045,
            transparent: true,
            opacity: 0.48,
            depthWrite: false
        })));
    }

    function addOrbitRings(scene) {
        for (var ring = 0; ring < 5; ring += 1) {
            var radius = 2.2 + ring * 1.35;
            var points = [];
            for (var i = 0; i <= 96; i += 1) {
                var angle = (i / 96) * Math.PI * 2;
                points.push(Math.cos(angle) * radius, 0, Math.sin(angle) * radius * 0.62);
            }
            var geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
            scene.add(new THREE.Line(geometry, new THREE.LineBasicMaterial({
                color: 0x59dce7,
                transparent: true,
                opacity: 0.075
            })));
        }
    }

    function buildRelationLines(scene, edges, nodeMap) {
        var lines = [];
        edges.forEach(function (edge) {
            var from = nodeMap[edge.from];
            var to = nodeMap[edge.to];
            if (!from || !to) return;
            var geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 0, 0, 0], 3));
            var line = new THREE.Line(geometry, new THREE.LineBasicMaterial({
                color: edge.relation === 'cites' ? 0xf3c86b : 0x45d9e8,
                transparent: true,
                opacity: 0.14 + Math.min(0.22, (edge.weight || 0.5) * 0.18)
            }));
            scene.add(line);
            lines.push({ line: line, from: from, to: to });
        });
        return lines;
    }

    function updateRelationLines(lines) {
        lines.forEach(function (item) {
            var position = item.line.geometry.attributes.position;
            position.setXYZ(0, item.from.position.x, item.from.position.y, item.from.position.z);
            position.setXYZ(1, item.to.position.x, item.to.position.y, item.to.position.z);
            position.needsUpdate = true;
        });
    }

    function bindInteraction(host, renderer, camera, meshes) {
        var raycaster = new THREE.Raycaster();
        var pointer = new THREE.Vector2();
        var dragging = false;
        var moved = false;
        var lastX = 0;
        var lastY = 0;
        var pendingX = 0;
        var pendingY = 0;
        var hovered = null;

        function setPointer(event) {
            var rect = renderer.domElement.getBoundingClientRect();
            pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        }
        function pointerDown(event) {
            dragging = true;
            moved = false;
            lastX = event.clientX;
            lastY = event.clientY;
            renderer.domElement.style.cursor = 'grabbing';
        }
        function pointerMove(event) {
            if (dragging) {
                var dx = event.clientX - lastX;
                var dy = event.clientY - lastY;
                pendingX += dx * 0.006;
                pendingY += dy * 0.005;
                moved = moved || Math.abs(dx) + Math.abs(dy) > 2;
                lastX = event.clientX;
                lastY = event.clientY;
                return;
            }
            setPointer(event);
            raycaster.setFromCamera(pointer, camera);
            var hits = raycaster.intersectObjects(meshes);
            if (hovered && (!hits.length || hits[0].object !== hovered)) hovered.scale.setScalar(hovered.userData.baseScale);
            hovered = hits.length ? hits[0].object : null;
            if (hovered) {
                hovered.scale.setScalar(1.28);
                renderer.domElement.style.cursor = 'pointer';
                host.title = hovered.userData.node.title || hovered.userData.node.label || '';
            } else {
                renderer.domElement.style.cursor = 'grab';
                host.removeAttribute('title');
            }
        }
        function pointerUp() {
            dragging = false;
            renderer.domElement.style.cursor = hovered ? 'pointer' : 'grab';
        }
        function click() {
            if (moved || !hovered) return;
            var node = hovered.userData.node;
            if (node.url) window.open(node.url, '_blank', 'noopener');
        }
        function wheel(event) {
            event.preventDefault();
            camera.position.z = Math.max(10, Math.min(28, camera.position.z + event.deltaY * 0.012));
        }

        renderer.domElement.style.cursor = 'grab';
        renderer.domElement.addEventListener('pointerdown', pointerDown);
        renderer.domElement.addEventListener('pointermove', pointerMove);
        window.addEventListener('pointerup', pointerUp);
        renderer.domElement.addEventListener('click', click);
        renderer.domElement.addEventListener('wheel', wheel, { passive: false });

        return {
            get dragging() { return dragging; },
            applyRotation: function (callback) {
                if (!pendingX && !pendingY) return;
                callback(pendingX, pendingY);
                pendingX = 0;
                pendingY = 0;
            },
            dispose: function () {
                renderer.domElement.removeEventListener('pointerdown', pointerDown);
                renderer.domElement.removeEventListener('pointermove', pointerMove);
                window.removeEventListener('pointerup', pointerUp);
                renderer.domElement.removeEventListener('click', click);
                renderer.domElement.removeEventListener('wheel', wheel);
            }
        };
    }

    function makeLabel(text, prominent) {
        var canvas = document.createElement('canvas');
        canvas.width = prominent ? 512 : 320;
        canvas.height = prominent ? 96 : 64;
        var context = canvas.getContext('2d');
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.fillStyle = prominent ? 'rgba(4,14,28,.78)' : 'rgba(4,14,28,.62)';
        context.fillRect(4, 4, canvas.width - 8, canvas.height - 8);
        context.fillStyle = prominent ? '#eafffb' : '#d7f6ff';
        context.font = (prominent ? '700 28px' : '600 18px') + ' Inter, Noto Sans SC, sans-serif';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        var value = String(text || 'Node');
        var limit = prominent ? 28 : 22;
        context.fillText(value.length > limit ? value.slice(0, limit - 1) + '…' : value, canvas.width / 2, canvas.height / 2);
        var texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        var sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false }));
        sprite.scale.set(prominent ? 4.9 : 2.7, prominent ? 0.92 : 0.54, 1);
        return sprite;
    }

    function makeGlowSprite(color) {
        var canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 256;
        var context = canvas.getContext('2d');
        var gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128);
        var c = new THREE.Color(color);
        var rgb = Math.round(c.r * 255) + ',' + Math.round(c.g * 255) + ',' + Math.round(c.b * 255);
        gradient.addColorStop(0, 'rgba(' + rgb + ',.46)');
        gradient.addColorStop(0.35, 'rgba(' + rgb + ',.18)');
        gradient.addColorStop(1, 'rgba(' + rgb + ',0)');
        context.fillStyle = gradient;
        context.fillRect(0, 0, 256, 256);
        var texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        return new THREE.Sprite(new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        }));
    }

    function nodeSize(node) {
        var relevance = Math.max(0, Math.min(1, node.relevance || 0.45));
        var citations = Math.min(1, Math.log((node.citation_count || 0) + 1) / 6);
        return 0.18 + relevance * 0.13 + citations * 0.12;
    }

    function updateStats(nodes, edges) {
        var topics = nodes.filter(function (node) { return node.type === 'Topic'; }).length;
        var nodeCount = document.getElementById('node-count');
        var edgeCount = document.getElementById('edge-count');
        var topicCount = document.getElementById('topic-count');
        if (nodeCount) nodeCount.textContent = nodes.length;
        if (edgeCount) edgeCount.textContent = edges.length;
        if (topicCount) topicCount.textContent = topics || 1;
    }

    function disposeActiveScene() {
        if (activeScene) activeScene.cancel();
        activeScene = null;
    }
})();