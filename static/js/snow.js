(function() {
  const container = document.getElementById('snow-container');
  const toggle = document.getElementById('snow-toggle');
  const SNOW_KEY = 'snow-preference';
  const FLAKE_COUNT = 50;

  function createSnowflakes() {
    container.innerHTML = '';
    for (let i = 0; i < FLAKE_COUNT; i++) {
      const flake = document.createElement('div');
      flake.className = 'snowflake';
      flake.textContent = '\u2744';
      flake.style.left = Math.random() * 100 + '%';
      flake.style.fontSize = (Math.random() * 10 + 10) + 'px';
      flake.style.opacity = Math.random() * 0.6 + 0.4;
      flake.style.animationDuration = (Math.random() * 8 + 8) + 's, ' + (Math.random() * 3 + 2) + 's';
      flake.style.animationDelay = Math.random() * 10 + 's';
      container.appendChild(flake);
    }
  }

  function isSnowEnabled() {
    const pref = localStorage.getItem(SNOW_KEY);
    return pref === null ? true : pref === 'true'; // Default ON
  }

  function updateSnow() {
    const enabled = isSnowEnabled();
    if (enabled) {
      container.classList.remove('hidden');
      toggle?.classList.add('active');
      if (!container.hasChildNodes()) createSnowflakes();
    } else {
      container.classList.add('hidden');
      toggle?.classList.remove('active');
    }
  }

  toggle?.addEventListener('click', () => {
    const newState = !isSnowEnabled();
    localStorage.setItem(SNOW_KEY, newState);
    updateSnow();
  });

  createSnowflakes();
  updateSnow();
})();
