/**
 * Analytics Dashboard
 * Fetches and renders analytics data from the Worker /stats endpoint
 */
(function() {
  'use strict';

  var pageviewChart = null;
  var hourlyChart = null;

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
  var CACHE_KEY = 'tech-econ-analytics-cache';
  var CACHE_MAX_AGE = 15 * 60 * 1000; // 15 minutes

  function loadAnalytics() {
    // Try to show cached data immediately for instant UX
    var showedCached = false;
    try {
      var cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        var parsed = JSON.parse(cached);
        if (parsed.data && parsed.ts && (Date.now() - parsed.ts < CACHE_MAX_AGE)) {
          renderDashboard(parsed.data, true);
          showedCached = true;
        }
      }
    } catch (e) {
      // localStorage not available or parse error, continue to fetch
    }

    // Fetch fresh data (in background if cache was shown)
    fetch(STATS_ENDPOINT)
      .then(function(response) {
        if (!response.ok) throw new Error('Failed to fetch stats');
        return response.json();
      })
      .then(function(data) {
        // Cache the fresh data
        try {
          localStorage.setItem(CACHE_KEY, JSON.stringify({
            data: data,
            ts: Date.now()
          }));
        } catch (e) {
          // localStorage full or not available
        }
        renderDashboard(data, false);
      })
      .catch(function(err) {
        console.error('Analytics error:', err);
        if (!showedCached) {
          showError('Unable to load analytics data. Please try again later.');
        }
      });
  }

  function showError(message) {
    document.getElementById('analytics-loading').style.display = 'none';
    var errorEl = document.getElementById('analytics-error');
    errorEl.querySelector('p').textContent = message;
    errorEl.style.display = 'block';
  }

  function renderDashboard(data, isCached) {
    document.getElementById('analytics-loading').style.display = 'none';
    document.getElementById('analytics-content').style.display = 'block';

    // Summary metrics
    document.getElementById('metric-pageviews').textContent =
      formatNumber(data.summary?.pageviews || 0);
    document.getElementById('metric-sessions').textContent =
      formatNumber(data.summary?.sessions || 0);

    // Render charts
    renderPageviewsChart(data.dailyPageviews || {});

    // Render lists
    renderList('list-pages', data.topPages || []);

    // Combine all click buckets into one list
    var allClicks = [];
    ['packages', 'datasets', 'learning', 'other'].forEach(function(cat) {
      var bucket = data.topClicks?.[cat];
      if (bucket) {
        if (Array.isArray(bucket)) {
          allClicks = allClicks.concat(bucket);
        } else {
          // Handle object format (other bucket uses object, not array)
          Object.keys(bucket).forEach(function(name) {
            allClicks.push({ name: name, count: bucket[name] });
          });
        }
      }
    });
    allClicks.sort(function(a, b) { return b.count - a.count; });
    renderList('list-clicks', allClicks.slice(0, 10));

    // Render external links
    renderList('list-external', data.externalLinks || []);

    // Render hourly activity chart
    renderHourlyChart(data.hourlyActivity || {});

    // Render performance
    renderVitals(data.performance || {});

    // Render countries
    renderCountries(data.countries || []);

    // Last updated
    var updateText = 'Last updated: ' + new Date(data.updated).toLocaleString();
    if (isCached) {
      updateText += ' (cached)';
    }
    document.getElementById('last-updated').textContent = updateText;
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

  function renderHourlyChart(hourlyData) {
    var ctx = document.getElementById('chart-hourly');
    if (!ctx) return;

    // Create labels for 24 hours
    var labels = [];
    var values = [];
    for (var h = 0; h < 24; h++) {
      labels.push(h + ':00');
      values.push(hourlyData[h] || 0);
    }

    // Destroy existing chart
    if (hourlyChart) {
      hourlyChart.destroy();
    }

    // Get CSS custom properties for theming
    var style = getComputedStyle(document.documentElement);
    var textColor = style.getPropertyValue('--text-muted').trim() || '#6b7280';
    var gridColor = style.getPropertyValue('--border-color').trim() || '#e5e7eb';
    var accentColor = '#10b981'; // Green for hourly

    hourlyChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Activity',
          data: values,
          backgroundColor: accentColor + '80',
          borderColor: accentColor,
          borderWidth: 1
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
            grid: { display: false },
            ticks: {
              color: textColor,
              maxRotation: 0,
              callback: function(val, index) {
                // Show every 3rd hour
                return index % 3 === 0 ? this.getLabelForValue(val) : '';
              }
            }
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
      var path = item.name || '/';
      // Clean up page paths and make them clickable
      if (elementId === 'list-pages') {
        var displayName = path === '/' ? 'Home' : path.replace(/\//g, ' / ').trim();
        return '<li><a href="' + escapeHtml(path) + '" class="name">' + escapeHtml(displayName) + '</a>' +
               '<span class="count">' + formatNumber(item.count) + '</span></li>';
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
