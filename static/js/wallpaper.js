(() => {
  const canvas = document.getElementById('snow-canvas');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (!canvas || reduceMotion) return;

  const context = canvas.getContext('2d');
  if (!context) return;

  let width = 0;
  let height = 0;
  let flakes = [];
  let previousFrame = 0;

  function resizeCanvas() {
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * pixelRatio);
    canvas.height = Math.floor(height * pixelRatio);
    
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

    const count = Math.min(70, Math.floor(width / 15));

    flakes = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      radius: Math.random() * 2.5 + 0.5,
      speed: Math.random() * 0.6 + 0.2, // Медленное парение
      drift: (Math.random() - 0.5) * 0.3,
      opacity: Math.random() * 0.6 + 0.2,
      // Голубые, фиолетовые или белые частицы
      color: Math.random() > 0.5 ? '100, 200, 255' : (Math.random() > 0.5 ? '180, 150, 255' : '255, 255, 255')
    }));
  }

  function drawParticles(timestamp) {
    requestAnimationFrame(drawParticles);

    // Ограничиваем FPS ~30 кадрами
    if (timestamp - previousFrame < 33 || document.hidden) return;
    previousFrame = timestamp;

    context.clearRect(0, 0, width, height);

    for (const flake of flakes) {
      context.beginPath();
      context.arc(flake.x, flake.y, flake.radius, 0, Math.PI * 2);
      context.fillStyle = `rgba(${flake.color}, ${flake.opacity})`;
      
      // Добавляем эффект неонового свечения
      context.shadowBlur = 8;
      context.shadowColor = `rgba(${flake.color}, 0.8)`;
      context.fill();

      flake.y += flake.speed;
      flake.x += flake.drift;

      // Возврат частиц на экран
      if (flake.y > height + flake.radius) {
        flake.y = -flake.radius;
        flake.x = Math.random() * width;
      }
      if (flake.x < -5) flake.x = width + 5;
      if (flake.x > width + 5) flake.x = -5;
    }
    
    // Сбрасываем тень (важно для производительности)
    context.shadowBlur = 0;
  }

  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();
  requestAnimationFrame(drawParticles);
})();