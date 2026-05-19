(() => {
    const canvas = document.createElement('canvas');
    Object.assign(canvas.style, {
        position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
        zIndex: '-1', pointerEvents: 'none'
    });
    document.body.prepend(canvas);
    const ctx = canvas.getContext('2d');
    const COUNT = 55, MAX_DIST = 155;
    let nodes = [];

    function resize() {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function init() {
        nodes = Array.from({ length: COUNT }, () => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.35,
            vy: (Math.random() - 0.5) * 0.35,
            r: Math.random() * 1.8 + 0.8,
            pulse: Math.random() * Math.PI * 2
        }));
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const t = performance.now() * 0.001;

        for (let i = 0; i < nodes.length; i++) {
            const n = nodes[i];
            n.x += n.vx; n.y += n.vy;
            if (n.x < 0 || n.x > canvas.width)  n.vx *= -1;
            if (n.y < 0 || n.y > canvas.height)  n.vy *= -1;

            for (let j = i + 1; j < nodes.length; j++) {
                const m = nodes[j];
                const dx = n.x - m.x, dy = n.y - m.y;
                const dist = Math.hypot(dx, dy);
                if (dist < MAX_DIST) {
                    const alpha = (1 - dist / MAX_DIST) * 0.28;
                    const grad = ctx.createLinearGradient(n.x, n.y, m.x, m.y);
                    grad.addColorStop(0, `rgba(129,140,248,${alpha})`);
                    grad.addColorStop(1, `rgba(192,132,252,${alpha})`);
                    ctx.beginPath();
                    ctx.moveTo(n.x, n.y);
                    ctx.lineTo(m.x, m.y);
                    ctx.strokeStyle = grad;
                    ctx.lineWidth = 0.7;
                    ctx.stroke();
                }
            }

            const pulse = Math.sin(t * 1.4 + n.pulse) * 0.5 + 0.5;
            const r = n.r + pulse * 1.2;
            ctx.beginPath();
            ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(192,132,252,${0.4 + pulse * 0.35})`;
            ctx.fill();
        }

        requestAnimationFrame(draw);
    }

    resize(); init(); draw();
    window.addEventListener('resize', () => { resize(); init(); });
})();
