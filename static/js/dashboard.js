// Dashboard interactive nebula
(function () {
    document.addEventListener('DOMContentLoaded', function () {
        var canvas = document.getElementById('nebulaCanvas');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var W, H, offsetX = 0, offsetY = 0, scale = 1;
        var isDragging = false, dragStartX, dragStartY, wasDragged = false;
        var papers = typeof nebulaPapers !== 'undefined' ? nebulaPapers : [];
        var stars = [];
        var colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4', '#ec4899'];
        var collectionUrl = typeof nebulaCollectionUrl !== 'undefined' ? nebulaCollectionUrl : '/literature-collection';

        function resize() {
            var rect = canvas.getBoundingClientRect();
            W = rect.width;
            H = 400;
            canvas.width = W * 2;
            canvas.height = H * 2;
            ctx.setTransform(2, 0, 0, 2, 0, 0);
            W = canvas.width / 2;
            H = canvas.height / 2;
            draw();
        }

        function draw() {
            ctx.clearRect(0, 0, W, H);
            ctx.save();
            ctx.translate(offsetX, offsetY);
            ctx.scale(scale, scale);

            var grad = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, Math.max(W, H));
            grad.addColorStop(0, '#0a0f24');
            grad.addColorStop(1, '#000');
            ctx.fillStyle = grad;
            ctx.fillRect(-W, -H, W * 3, H * 3);

            for (var i = 0; i < 250; i += 1) {
                var sx = (i * 37 + 13) % (W * 2) - W / 2;
                var sy = (i * 53 + 7) % (H * 2) - H / 2;
                var sr = (i % 3) * 0.3 + 0.2;
                ctx.beginPath();
                ctx.arc(sx, sy, sr, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(255,255,255,' + (0.1 + (i % 5) * 0.08) + ')';
                ctx.fill();
            }

            stars = [];
            var cx = 0, cy = 0, radius = Math.min(W, H) / 3.5;
            papers.forEach(function (p, i) {
                var angle = (i / Math.max(1, papers.length)) * Math.PI * 2 - Math.PI / 2;
                var dist = radius + (i % 5 - 2) * 20;
                var x = cx + Math.cos(angle) * dist;
                var y = cy + Math.sin(angle) * dist;
                var size = Math.max(3, Math.min(10, (p.citation_count || 50) / 15));
                var color = colors[i % colors.length];
                stars.push({ x: x, y: y, size: size, color: color, title: p.title, topic: p.topic });

                var g = ctx.createRadialGradient(x, y, 0, x, y, size * 6);
                g.addColorStop(0, color + '88');
                g.addColorStop(0.5, color + '44');
                g.addColorStop(1, 'transparent');
                ctx.beginPath();
                ctx.arc(x, y, size * 4, 0, Math.PI * 2);
                ctx.fillStyle = g;
                ctx.fill();

                ctx.beginPath();
                ctx.arc(x, y, size, 0, Math.PI * 2);
                ctx.fillStyle = '#fff';
                ctx.fill();
                ctx.beginPath();
                ctx.arc(x, y, size * 0.7, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.fill();

                var sd = ctx.createRadialGradient(x + size * 0.3, y + size * 0.3, 0, x + size * 0.3, y + size * 0.3, size * 1.3);
                sd.addColorStop(0, 'rgba(0,0,0,0.35)');
                sd.addColorStop(1, 'transparent');
                ctx.beginPath();
                ctx.arc(x + size * 0.3, y + size * 0.3, size * 1.3, 0, Math.PI * 2);
                ctx.fillStyle = sd;
                ctx.fill();

                var hl = ctx.createRadialGradient(x - size * 0.2, y - size * 0.2, 0, x - size * 0.2, y - size * 0.2, size * 0.9);
                hl.addColorStop(0, 'rgba(255,255,255,0.5)');
                hl.addColorStop(1, 'transparent');
                ctx.beginPath();
                ctx.arc(x - size * 0.2, y - size * 0.2, size * 0.9, 0, Math.PI * 2);
                ctx.fillStyle = hl;
                ctx.fill();

                ctx.fillStyle = 'rgba(255,255,255,0.6)';
                ctx.font = '9px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(p.title.slice(0, 18) + (p.title.length > 18 ? '..' : ''), x, y + size + 10);
            });

            for (var a = 0; a < stars.length; a += 1) {
                for (var b = a + 1; b < stars.length; b += 1) {
                    var dx = stars[a].x - stars[b].x;
                    var dy = stars[a].y - stars[b].y;
                    var d = Math.sqrt(dx * dx + dy * dy);
                    if (d < 150 && stars[a].topic === stars[b].topic) {
                        ctx.beginPath();
                        ctx.moveTo(stars[a].x, stars[a].y);
                        ctx.lineTo(stars[b].x, stars[b].y);
                        ctx.strokeStyle = 'rgba(59,130,246,' + (1 - d / 150) * 0.2 + ')';
                        ctx.stroke();
                    }
                }
            }

            ctx.restore();
        }

        canvas.addEventListener('mousedown', function (e) {
            isDragging = true;
            wasDragged = false;
            dragStartX = e.clientX - offsetX;
            dragStartY = e.clientY - offsetY;
            canvas.style.cursor = 'grabbing';
        });
        window.addEventListener('mousemove', function (e) {
            if (!isDragging) return;
            offsetX = e.clientX - dragStartX;
            offsetY = e.clientY - dragStartY;
            wasDragged = true;
            draw();
        });
        window.addEventListener('mouseup', function () {
            isDragging = false;
            canvas.style.cursor = 'grab';
        });
        canvas.addEventListener('wheel', function (e) {
            e.preventDefault();
            var oldScale = scale;
            scale *= e.deltaY > 0 ? 0.9 : 1.1;
            scale = Math.max(0.3, Math.min(3, scale));
            offsetX = e.offsetX - (e.offsetX - offsetX) * (scale / oldScale);
            offsetY = e.offsetY - (e.offsetY - offsetY) * (scale / oldScale);
            draw();
        });
        canvas.addEventListener('click', function (e) {
            if (wasDragged) return;
            var rect = canvas.getBoundingClientRect();
            var mx = (e.clientX - rect.left - offsetX) / scale;
            var my = (e.clientY - rect.top - offsetY) / scale;
            for (var i = 0; i < stars.length; i += 1) {
                var dx = mx - stars[i].x, dy = my - stars[i].y;
                if (dx * dx + dy * dy < (stars[i].size + 5) * (stars[i].size + 5)) {
                    window.location.href = collectionUrl;
                    return;
                }
            }
        });
        canvas.style.cursor = 'grab';

        var lastTouchDist = 0;
        canvas.addEventListener('touchstart', function (e) {
            if (e.touches.length === 1) {
                isDragging = true;
                dragStartX = e.touches[0].clientX - offsetX;
                dragStartY = e.touches[0].clientY - offsetY;
            } else if (e.touches.length === 2) {
                lastTouchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
            }
        });
        canvas.addEventListener('touchmove', function (e) {
            e.preventDefault();
            if (e.touches.length === 1 && isDragging) {
                offsetX = e.touches[0].clientX - dragStartX;
                offsetY = e.touches[0].clientY - dragStartY;
                draw();
            } else if (e.touches.length === 2) {
                var dist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
                scale *= dist / lastTouchDist;
                scale = Math.max(0.3, Math.min(3, scale));
                lastTouchDist = dist;
                draw();
            }
        });
        canvas.addEventListener('touchend', function () { isDragging = false; });

        resize();
        window.addEventListener('resize', resize);
    });
})();

function escapeChatText(text) {
    return String(text || '').replace(/[&<>"']/g, function (c) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
}


(function () {
    var storage = window.localStorage;
    var keys = {
        track: 'lsca.dashboard.trackedTopics',
        imports: 'lsca.importedPapers.count',
        topic: 'lsca.dashboard.currentTopic',
        streak: 'lsca.dashboard.studyDays',
        lastStudyDate: 'lsca.dashboard.lastStudyDate'
    };

    function asInt(value, fallback) {
        var parsed = parseInt(value, 10);
        return Number.isFinite(parsed) ? parsed : (fallback || 0);
    }

    function localDateKey() {
        var now = new Date();
        var y = now.getFullYear();
        var m = String(now.getMonth() + 1).padStart(2, '0');
        var d = String(now.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + d;
    }

    function getMetricsRoot() {
        return document.querySelector('[data-dashboard-metrics]');
    }

    function meaningfulTerms(text) {
        var raw = String(text || '')
            .replace(/[\u3002\uff0c\uff1b\uff1a\uff1f\uff01,.;:?!()\[\]{}]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        var matches = raw.match(/[A-Za-z][A-Za-z0-9+\-\/]{2,}|[\u4e00-\u9fa5]{2,12}/g) || [];
        var stop = {
            '\u5e2e\u6211': true, '\u603b\u7ed3': true, '\u4e00\u7bc7': true, '\u8bba\u6587': true,
            '\u6838\u5fc3\u65b9\u6cd5': true, '\u627e\u51fa': true, '\u5173\u952e\u8bba\u6587': true,
            '\u63d0\u53d6': true, '\u6b65\u9aa4': true, '\u6bd4\u8f83': true, '\u7684': true,
            '\u548c': true, '\u4e0e': true, 'protocol': true
        };
        return matches.filter(function (item) {
            return !stop[item] && !stop[item.toLowerCase()];
        }).slice(0, 3);
    }

    function extractTopic(text, fallback) {
        var terms = meaningfulTerms(text);
        if (!terms.length) return fallback || '';
        return terms.join(' / ');
    }

    function setText(id, value) {
        var node = document.getElementById(id);
        if (node) node.textContent = value;
    }

    function updateTopic(topic) {
        if (!topic) return;
        setText('currentTopicValue', topic);
        setText('topicOrbitCore', topic);
        try { storage.setItem(keys.topic, topic); } catch (e) {}
    }

    function syncImports(initial) {
        var stored = asInt(storage && storage.getItem(keys.imports), initial);
        var value = Math.max(stored, initial || 0);
        setText('importedPaperCount', value);
    }

    function syncStudyDays(initial) {
        if (!storage) {
            setText('studyDayCount', initial || 0);
            return;
        }
        var today = localDateKey();
        var last = storage.getItem(keys.lastStudyDate);
        var stored = asInt(storage.getItem(keys.streak), initial || 0);
        var base = Math.max(stored, initial || 0);
        if (!last) {
            base = Math.max(base, 1);
            storage.setItem(keys.lastStudyDate, today);
            storage.setItem(keys.streak, String(base));
        } else if (last !== today) {
            base += 1;
            storage.setItem(keys.lastStudyDate, today);
            storage.setItem(keys.streak, String(base));
        }
        setText('studyDayCount', base);
    }

    function initWorkbenchMetrics() {
        var root = getMetricsRoot();
        if (!root) return;
        var initialTopic = root.getAttribute('data-initial-topic') || '';
        var initialTrack = asInt(root.getAttribute('data-initial-track'), 0);
        var initialImports = asInt(root.getAttribute('data-initial-imports'), 0);
        var initialStreak = asInt(root.getAttribute('data-initial-streak'), 0);
        var storedTopic = storage && storage.getItem(keys.topic);
        updateTopic(storedTopic || initialTopic);

        var tracked = Math.max(asInt(storage && storage.getItem(keys.track), initialTrack), initialTrack);
        setText('trackedTopicCount', tracked);
        syncImports(initialImports);
        syncStudyDays(initialStreak);

        var input = document.getElementById('chatInput');
        if (input) {
            input.addEventListener('input', function () {
                var topic = extractTopic(input.value, storedTopic || initialTopic);
                updateTopic(topic || initialTopic);
            });
        }

        window.addEventListener('storage', function (event) {
            if (event.key === keys.imports) syncImports(initialImports);
        });
        window.addEventListener('lsca:literature-imported', function () { syncImports(initialImports); });
    }

    function initRobotFace() {
        var robot = document.getElementById('pixelRobot');
        if (!robot) return;
        var faces = ['calm', 'focus', 'spark'];
        var index = 0;
        function setFace() {
            robot.setAttribute('data-face', faces[index % faces.length]);
            index += 1;
        }
        setFace();
        window.setInterval(setFace, 60000);
    }

    window.lscaDashboardTrackQuestion = function (question) {
        var root = getMetricsRoot();
        if (!root) return;
        var initialTrack = asInt(root.getAttribute('data-initial-track'), 0);
        var current = Math.max(asInt(storage && storage.getItem(keys.track), initialTrack), initialTrack) + 1;
        try { storage.setItem(keys.track, String(current)); } catch (e) {}
        setText('trackedTopicCount', current);
        var initialTopic = root.getAttribute('data-initial-topic') || '';
        updateTopic(extractTopic(question, initialTopic));
    };

    document.addEventListener('DOMContentLoaded', function () {
        initWorkbenchMetrics();
        initRobotFace();
    });
})();

function sendChat() {
    var input = document.getElementById('chatInput');
    var area = document.getElementById('chatArea');
    var question = input && input.value ? input.value.trim() : '';
    if (!question || !area) return;
    if (window.lscaDashboardTrackQuestion) window.lscaDashboardTrackQuestion(question);
    saveChat('user', question);
    area.innerHTML += '<div class="chat-msg user">' + escapeChatText(question) + '</div>';
    input.value = '';
    area.scrollTop = area.scrollHeight;
    area.innerHTML += '<div class="chat-msg bot pending">正在分析...</div>';
    fetch('/api/agent-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question })
    }).then(function (response) {
        return response.json();
    }).then(function (data) {
        var messages = area.querySelectorAll('.chat-msg.bot');
        var last = messages[messages.length - 1];
        if (last && last.textContent === '正在分析...') last.remove();
        var answer = data.answer || '暂无回答';
        saveChat('assistant', answer);
        area.innerHTML += '<div class="chat-msg bot">' + escapeChatText(answer) + '</div>';
        area.scrollTop = area.scrollHeight;
    }).catch(function (error) {
        area.innerHTML += '<div class="chat-msg bot">请求失败：' + escapeChatText(error) + '</div>';
    });
}

function quickAsk(text) {
    var input = document.getElementById('chatInput');
    if (!input) return;
    input.value = text;
    sendChat();
}

function loadChatHistory() {
    fetch('/api/chat/history').then(function (response) {
        return response.json();
    }).then(function (messages) {
        var area = document.getElementById('chatArea');
        if (!area) return;
        messages.forEach(function (message) {
            area.innerHTML += '<div class="chat-msg ' + (message.role === 'user' ? 'user' : 'bot') + '">' + escapeChatText(message.message) + '</div>';
        });
        area.scrollTop = area.scrollHeight;
    });
}

function clearChat() {
    if (!confirm('清空聊天记录？')) return;
    fetch('/api/chat/clear', { method: 'POST' }).then(function () {
        var area = document.getElementById('chatArea');
        if (area) area.innerHTML = '<div class="chat-msg bot">聊天记录已清空，可以重新开始。</div>';
    });
}

function saveChat(role, message) {
    fetch('/api/chat/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: role, message: message })
    });
}

function upgradeChatInput() {
    var input = document.getElementById('chatInput');
    if (!input || input.tagName === 'TEXTAREA') return;

    var textarea = document.createElement('textarea');
    textarea.id = input.id;
    textarea.className = input.className;
    textarea.placeholder = input.placeholder;
    textarea.rows = 3;
    textarea.setAttribute('aria-label', input.placeholder || 'Research assistant input');
    textarea.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendChat();
        }
    });
    input.replaceWith(textarea);
}

document.addEventListener('DOMContentLoaded', function () {
    upgradeChatInput();
    loadChatHistory();
});
