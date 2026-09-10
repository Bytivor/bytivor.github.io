(() => {
  const init = () => {
    const videos = [...document.querySelectorAll('.portfolio-vfx-card video:not([data-ready])')];
    if (!videos.length) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const visible = new Set();
    const play = video => {
      if (!reduced.matches && !document.hidden) video.play().catch(() => {});
    };
    const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
      entries.forEach(({ target, isIntersecting }) => {
        if (isIntersecting) { visible.add(target); play(target); }
        else { visible.delete(target); target.pause(); }
      });
    }, { threshold: 0.4 }) : null;
    videos.forEach(video => {
      video.dataset.ready = 'true';
      video.muted = true;
      if (observer) observer.observe(video);
    });
    document.addEventListener('visibilitychange', () => {
      visible.forEach(video => document.hidden ? video.pause() : play(video));
    });
    reduced.addEventListener('change', () => {
      visible.forEach(video => reduced.matches ? video.pause() : play(video));
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
  document.addEventListener('pjax:complete', init);
})();
