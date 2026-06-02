(() => {
  const canvas = document.getElementById("home-wave-canvas");
  const home = document.querySelector(".sct-home");
  if (!canvas || !home) return;

  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  let width = 0;
  let height = 0;
  let rafId = 0;
  const tabs = document.querySelector(".md-tabs");

  const layers = [
    { height: 24, speed: 0.0009, offset: 0.28, color: "rgba(112, 245, 255, 0.9)" },
    { height: 18, speed: 0.0012, offset: 0.46, color: "rgba(126, 190, 255, 0.75)" },
    { height: 14, speed: 0.0016, offset: 0.64, color: "rgba(174, 150, 255, 0.6)" },
  ];

  const resize = () => {
    if (tabs) {
      home.style.setProperty("--sct-tabs-offset", `${tabs.getBoundingClientRect().height}px`);
    }
    width = home.clientWidth;
    height = home.clientHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  const drawWave = (t, layer, phaseShift) => {
    const segments = 80;
    ctx.beginPath();
    for (let i = 0; i <= segments; i += 1) {
      const ratio = i / segments;
      const x = ratio * width;
      const envelope = 0.5 + 0.5 * Math.sin((ratio - 0.5) * Math.PI);
      const y =
        height * layer.offset +
        Math.sin(ratio * 9.4 + t * layer.speed + phaseShift) * layer.height * envelope +
        Math.cos(ratio * 4.8 + t * layer.speed * 0.6 - phaseShift) * (layer.height * 0.4);
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.strokeStyle = layer.color;
    ctx.lineWidth = 2;
    ctx.shadowColor = layer.color;
    ctx.shadowBlur = 14;
    ctx.stroke();
    ctx.shadowBlur = 0;
  };

  const draw = (t) => {
    ctx.clearRect(0, 0, width, height);

    const glow = ctx.createRadialGradient(width * 0.52, height * 0.44, 80, width * 0.52, height * 0.44, Math.max(width, height) * 0.66);
    glow.addColorStop(0, "rgba(65, 210, 255, 0.16)");
    glow.addColorStop(1, "rgba(6, 12, 30, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, width, height);

    const phase = t * 0.0003;
    for (let i = 0; i < layers.length; i += 1) {
      drawWave(t, layers[i], phase + i * 1.8);
    }

    rafId = window.requestAnimationFrame(draw);
  };

  const handlePointer = (event) => {
    const rect = home.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    home.style.setProperty("--pointer-x", `${x.toFixed(2)}%`);
    home.style.setProperty("--pointer-y", `${y.toFixed(2)}%`);
    const moveX = (x - 50) * 0.18;
    const moveY = (y - 50) * 0.22;
    const leftGlow = home.querySelector(".sct-home__glow--left");
    const rightGlow = home.querySelector(".sct-home__glow--right");
    if (leftGlow) leftGlow.style.transform = `translate(${moveX * -0.18}px, ${moveY * -0.15}px)`;
    if (rightGlow) rightGlow.style.transform = `translate(${moveX * 0.12}px, ${moveY * 0.1}px)`;
  };

  resize();
  window.addEventListener("resize", resize, { passive: true });
  home.addEventListener("pointermove", handlePointer, { passive: true });

  if (reduceMotion) {
    draw(0);
  } else {
    rafId = window.requestAnimationFrame(draw);
  }

  window.addEventListener("pagehide", () => {
    if (rafId) {
      window.cancelAnimationFrame(rafId);
    }
  });
})();
