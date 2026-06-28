// Dashboard interactive nebula
document.addEventListener('DOMContentLoaded', function() {
    var canvas = document.getElementById('nebulaCanvas');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var W, H, offsetX = 0, offsetY = 0, scale = 1;
    var isDragging = false, dragStartX, dragStartY, dragStartMX, dragStartMY, wasDragged = false;
    var papers = typeof nebulaPapers !== 'undefined' ? nebulaPapers : [];
    var stars = [];
    var colors = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#ec4899'];
    var collectionUrl = typeof nebulaCollectionUrl !== 'undefined' ? nebulaCollectionUrl : '/literature-collection';

    function resize() {
        var rect = canvas.getBoundingClientRect();
        W = rect.width; H = 400;
        canvas.width = W * 2; canvas.height = H * 2;
        ctx.scale(2, 2);
        W = canvas.width / 2; H = canvas.height / 2;
        draw();
    }

    function draw() {
        ctx.clearRect(0, 0, W, H);
        ctx.save();
        ctx.translate(offsetX, offsetY);
        ctx.scale(scale, scale);

        // Background: dark space
        var grad = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, Math.max(W,H));
        grad.addColorStop(0, '#0a0f24'); grad.addColorStop(1, '#000');
        ctx.fillStyle = grad; ctx.fillRect(-W, -H, W*3, H*3);

        // Tiny background stars (more natural distribution)
        for (var i = 0; i < 250; i++) {
            var sx = (i * 37 + 13) % (W * 2) - W/2;
            var sy = (i * 53 + 7) % (H * 2) - H/2;
            var sr = (i % 3) * 0.3 + 0.2;
            ctx.beginPath(); ctx.arc(sx, sy, sr, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255,255,255,' + (0.1 + (i % 5) * 0.08) + ')';
            ctx.fill();
        }

        // Literature stars + connecting lines
        stars = [];
        var cx = 0, cy = 0, radius = Math.min(W,H) / 3.5;
        papers.forEach(function(p, i) {
            var angle = (i / papers.length) * Math.PI * 2 - Math.PI/2;
            var dist = radius + (i % 5 - 2) * 20;
            var x = cx + Math.cos(angle) * dist;
            var y = cy + Math.sin(angle) * dist;
            var size = Math.max(3, Math.min(10, (p.citation_count || 50) / 15));
            var color = colors[i % colors.length];
            stars.push({x:x, y:y, size:size, color:color, title:p.title, topic:p.topic});

            // Glow
            var g = ctx.createRadialGradient(x, y, 0, x, y, size * 6);
            g.addColorStop(0, color + '88'); g.addColorStop(0.5, color + '44'); g.addColorStop(1, 'transparent');
            ctx.beginPath(); ctx.arc(x, y, size * 4, 0, Math.PI * 2);
            ctx.fillStyle = g; ctx.fill();
            // Star body with 3D effect
            ctx.beginPath(); ctx.arc(x, y, size, 0, Math.PI * 2);
            ctx.fillStyle = '#fff'; ctx.fill();
            ctx.beginPath(); ctx.arc(x, y, size * 0.7, 0, Math.PI * 2);
            ctx.fillStyle = color; ctx.fill();
            // 3D shadow
            var sd = ctx.createRadialGradient(x+size*0.3, y+size*0.3, 0, x+size*0.3, y+size*0.3, size*1.3);
            sd.addColorStop(0,'rgba(0,0,0,0.35)'); sd.addColorStop(1,'transparent');
            ctx.beginPath(); ctx.arc(x+size*0.3, y+size*0.3, size*1.3, 0, Math.PI*2);
            ctx.fillStyle = sd; ctx.fill();
            // 3D highlight
            var hl = ctx.createRadialGradient(x-size*0.2, y-size*0.2, 0, x-size*0.2, y-size*0.2, size*0.9);
            hl.addColorStop(0,'rgba(255,255,255,0.5)'); hl.addColorStop(1,'transparent');
            ctx.beginPath(); ctx.arc(x-size*0.2, y-size*0.2, size*0.9, 0, Math.PI*2);
            ctx.fillStyle = hl; ctx.fill();
            // Label
            ctx.fillStyle = 'rgba(255,255,255,0.6)';
            ctx.font = '9px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(p.title.slice(0, 18) + (p.title.length > 18 ? '..' : ''), x, y + size + 10);
        });

        // Connecting lines
        for (var i = 0; i < stars.length; i++) {
            for (var j = i + 1; j < stars.length; j++) {
                var dx = stars[i].x - stars[j].x;
                var dy = stars[i].y - stars[j].y;
                var d = Math.sqrt(dx * dx + dy * dy);
                if (d < 150 && stars[i].topic === stars[j].topic) {
                    ctx.beginPath(); ctx.moveTo(stars[i].x, stars[i].y);
                    ctx.lineTo(stars[j].x, stars[j].y);
                    ctx.strokeStyle = 'rgba(59,130,246,' + (1 - d / 150) * 0.2 + ')';
                    ctx.stroke();
                }
            }
        }

        ctx.restore();
    }

    // Mouse interactions
    canvas.addEventListener('mousedown', function(e) {
        isDragging = true;
        dragStartX = e.clientX - offsetX;
        dragStartY = e.clientY - offsetY;
        canvas.style.cursor = 'grabbing';
    });
    window.addEventListener('mousemove', function(e) {
        if (isDragging) {
            offsetX = e.clientX - dragStartX;
            offsetY = e.clientY - dragStartY;
            draw();
        }
    });
    window.addEventListener('mouseup', function() {
        isDragging = false;
        canvas.style.cursor = 'grab';
    });
    canvas.addEventListener('wheel', function(e) {
        e.preventDefault();
        var oldScale = scale;
        scale *= e.deltaY > 0 ? 0.9 : 1.1;
        scale = Math.max(0.3, Math.min(3, scale));
        offsetX = e.offsetX - (e.offsetX - offsetX) * (scale / oldScale);
        offsetY = e.offsetY - (e.offsetY - offsetY) * (scale / oldScale);
        draw();
    });

    // Click detection
    canvas.addEventListener('click', function(e) {
        if (wasDragged) return;
        var rect = canvas.getBoundingClientRect();
        var mx = (e.clientX - rect.left - offsetX) / scale;
        var my = (e.clientY - rect.top - offsetY) / scale;
        for (var i = 0; i < stars.length; i++) {
            var dx = mx - stars[i].x, dy = my - stars[i].y;
            if (dx * dx + dy * dy < (stars[i].size + 5) * (stars[i].size + 5)) {
                window.location.href = collectionUrl;
                return;
            }
        }
    });
    canvas.style.cursor = 'grab';

    // Touch support
    var lastTouchDist = 0;
    canvas.addEventListener('touchstart', function(e) {
        if (e.touches.length === 1) {
            isDragging = true;
            dragStartX = e.touches[0].clientX - offsetX;
            dragStartY = e.touches[0].clientY - offsetY;
        } else if (e.touches.length === 2) {
            lastTouchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
        }
    });
    canvas.addEventListener('touchmove', function(e) {
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
    canvas.addEventListener('touchend', function() { isDragging = false; });

    resize();
    window.addEventListener('resize', resize);
});

function sendChat(){var i=document.getElementById("chatInput"),a=document.getElementById("chatArea"),q=i.value.trim();if(!q)return;a.innerHTML+='<div class="chat-msg user">'+q+"</div>";i.value="";a.scrollTop=a.scrollHeight;a.innerHTML+='<div class="chat-msg bot" style="opacity:0.6;">Thinking...</div>';fetch("/api/agent-chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})}).then(function(r){return r.json()}).then(function(d){var m=a.querySelectorAll(".chat-msg.bot"),l=m[m.length-1];if(l&&l.textContent==="Thinking...")l.remove();a.innerHTML+='<div class="chat-msg bot">'+(d.answer||"No response")+"</div>";a.scrollTop=a.scrollHeight}).catch(function(e){a.innerHTML+='<div class="chat-msg bot">Error: '+e+"</div>"})}

function loadChatHistory(){fetch("/api/chat/history").then(function(r){return r.json()}).then(function(msgs){var a=document.getElementById("chatArea");if(!a)return;msgs.forEach(function(m){a.innerHTML+='<div class="chat-msg '+(m.role==="user"?"user":"bot")+'">'+m.message+"</div>"});a.scrollTop=a.scrollHeight})}
function clearChat(){if(!confirm("Clear chat history?"))return;fetch("/api/chat/clear",{method:"POST"}).then(function(){var a=document.getElementById("chatArea");if(a)a.innerHTML='<div class="chat-msg bot">Chat cleared. Start fresh!</div>'})}
function saveChat(role,msg){fetch("/api/chat/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({role:role,message:msg})})}
document.addEventListener("DOMContentLoaded",function(){loadChatHistory()});
