/**
 * Analytics Dashboard
 * Fetches and renders analytics data from the Worker /stats endpoint
 */
(function() {
  'use strict';

  var pageviewChart = null;

  // Country flag emoji mapping
  var countryFlags = {
    'US': '\u{1F1FA}\u{1F1F8}', 'GB': '\u{1F1EC}\u{1F1E7}', 'DE': '\u{1F1E9}\u{1F1EA}',
    'FR': '\u{1F1EB}\u{1F1F7}', 'IN': '\u{1F1EE}\u{1F1F3}', 'CN': '\u{1F1E8}\u{1F1F3}',
    'JP': '\u{1F1EF}\u{1F1F5}', 'CA': '\u{1F1E8}\u{1F1E6}', 'AU': '\u{1F1E6}\u{1F1FA}',
    'BR': '\u{1F1E7}\u{1F1F7}', 'IT': '\u{1F1EE}\u{1F1F9}', 'ES': '\u{1F1EA}\u{1F1F8}',
    'NL': '\u{1F1F3}\u{1F1F1}', 'SE': '\u{1F1F8}\u{1F1EA}', 'CH': '\u{1F1E8}\u{1F1ED}',
    'SG': '\u{1F1F8}\u{1F1EC}', 'KR': '\u{1F1F0}\u{1F1F7}', 'MX': '\u{1F1F2}\u{1F1FD}',
    'RU': '\u{1F1F7}\u{1F1FA}', 'PL': '\u{1F1F5}\u{1F1F1}'
  };

  function init() {
    loadAnalytics();
  }

  // Stats endpoint URL
  var STATS_ENDPOINT = 'https://tech-econ-analytics.rawat-pranjal010.workers.dev/stats';

  function loadAnalytics() {
    fetch(STATS_ENDPOINT)
      .then(function(response) {
        if (!response.ok) throw new Error('Failed to fetch stats');
        return response.json();
      })
      .then(function(data) {
        renderDashboard(data);
      })
      .catch(function(err) {
        console.error('Analytics error:', err);
        showError('Unable to load analytics data. Please try again later.');
      });
  }

  function showError(message) {
    document.getElementById('analytics-loading').style.display = 'none';
    var errorEl = document.getElementById('analytics-error');
    errorEl.querySelector('p').textContent = message;
    errorEl.style.display = 'block';
  }

  function renderDashboard(data) {
    document.getElementById('analytics-loading').style.display = 'none';
    document.getElementById('analytics-content').style.display = 'block';

    // Summary metrics
    document.getElementById('metric-pageviews').textContent =
      formatNumber(data.summary?.pageviews || 0);
    document.getElementById('metric-sessions').textContent =
      formatNumber(data.summary?.sessions || 0);
    document.getElementById('metric-time').textContent =
      formatTime(data.summary?.avgTimeOnPage || 0);

    // Top search
    var topSearch = data.topSearches && data.topSearches[0];
    document.getElementById('metric-top-search').textContent =
      topSearch ? '"' + topSearch.name + '"' : '-';

    // Render charts
    renderPageviewsChart(data.dailyPageviews || {});

    // Render lists
    renderList('list-searches', data.topSearches || []);
    renderList('list-pages', data.topPages || []);
    renderList('list-packages', (data.topClicks?.packages || []).slice(0, 5));
    renderList('list-datasets', (data.topClicks?.datasets || []).slice(0, 5));
    renderList('list-learning', (data.topClicks?.learning || []).slice(0, 5));

    // Render performance
    renderVitals(data.performance || {});

    // Render countries
    renderCountries(data.countries || []);

    // Last updated
    document.getElementById('last-updated').textContent =
      'Last updated: ' + new Date(data.updated).toLocaleString();
  }

  function renderPageviewsChart(dailyData) {
    var ctx = document.getElementById('chart-pageviews');
    if (!ctx) return;

    var labels = Object.keys(dailyData).map(function(date) {
      return new Date(date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    });
    var values = Object.values(dailyData);

    // Destroy existing chart
    if (pageviewChart) {
      pageviewChart.destroy();
    }

    // Get CSS custom properties for theming
    var style = getComputedStyle(document.documentElement);
    var textColor = style.getPropertyValue('--text-muted').trim() || '#6b7280';
    var gridColor = style.getPropertyValue('--border-color').trim() || '#e5e7eb';
    var accentColor = '#3b82f6';

    pageviewChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Page Views',
          data: values,
          borderColor: accentColor,
          backgroundColor: accentColor + '20',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { color: gridColor },
            ticks: { color: textColor }
          },
          y: {
            beginAtZero: true,
            grid: { color: gridColor },
            ticks: { color: textColor }
          }
        }
      }
    });
  }

  function renderList(elementId, items) {
    var list = document.getElementById(elementId);
    if (!list) return;

    if (!items || items.length === 0) {
      list.innerHTML = '<li class="placeholder">No data yet</li>';
      return;
    }

    list.innerHTML = items.map(function(item) {
      var name = item.name || '-';
      // Clean up page paths
      if (elementId === 'list-pages') {
        name = name === '/' ? 'Home' : name.replace(/\//g, ' / ').trim();
      }
      return '<li><span class="name">' + escapeHtml(name) + '</span>' +
             '<span class="count">' + formatNumber(item.count) + '</span></li>';
    }).join('');
  }

  function renderVitals(performance) {
    renderVital('vital-lcp', performance.lcp, 'ms', [2500, 4000]);
    renderVital('vital-fid', performance.fid, 'ms', [100, 300]);
    renderVital('vital-cls', performance.cls, '', [0.1, 0.25]);
  }

  function renderVital(elementId, data, unit, thresholds) {
    var card = document.getElementById(elementId);
    if (!card) return;

    var valueEl = card.querySelector('.vital-value');
    if (!data || data.avg === null) {
      valueEl.textContent = '-';
      card.className = 'vital-card';
      return;
    }

    var value = data.avg;
    var displayValue = unit === 'ms' ? (value >= 1000 ? (value / 1000).toFixed(1) + 's' : value + 'ms') : value.toFixed(2);
    valueEl.textContent = displayValue;

    // Set rating class
    var rating = value < thresholds[0] ? 'good' : value < thresholds[1] ? 'needs-improvement' : 'poor';
    card.className = 'vital-card ' + rating;
  }

  function renderCountries(countries) {
    var container = document.getElementById('countries-list');
    if (!container) return;

    if (!countries || countries.length === 0) {
      container.innerHTML = '<span class="placeholder">No data yet</span>';
      return;
    }

    container.innerHTML = countries.map(function(item) {
      var flag = countryFlags[item.name] || '';
      return '<span class="country-badge">' +
             '<span class="flag">' + flag + '</span>' +
             '<span class="code">' + item.name + '</span>' +
             '<span class="count">(' + formatNumber(item.count) + ')</span>' +
             '</span>';
    }).join('');
  }

  // Utilities
  function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
  }

  function formatTime(seconds) {
    if (seconds < 60) return seconds + 's';
    var mins = Math.floor(seconds / 60);
    var secs = seconds % 60;
    return mins + 'm ' + secs + 's';
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Global refresh function
  window.refreshAnalytics = function() {
    document.getElementById('analytics-content').style.display = 'none';
    document.getElementById('analytics-error').style.display = 'none';
    document.getElementById('analytics-loading').style.display = 'block';
    loadAnalytics();
  };

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
