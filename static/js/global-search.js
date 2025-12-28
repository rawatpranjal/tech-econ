// Global Search Module
(function() {
  'use strict';

  // Configuration
  var CONFIG = {
    fuseOptions: {
      keys: [
        { name: 'name', weight: 2 },
        { name: 'tags', weight: 1.5 },
        { name: 'best_for', weight: 1.2 },
        { name: 'description', weight: 1 },
        { name: 'category', weight: 0.8 }
      ],
      threshold: 0.4,
      ignoreLocation: true,
      includeScore: true,
      includeMatches: true,
      minMatchCharLength: 2
    },
    debounceMs: 150,
    maxResultsPerType: 5,
    maxTotalResults: 20,
    recentSearchesKey: 'global-recent-searches',
    maxRecentSearches: 5,
    suggestions: ['causal inference', 'experimentation', 'pricing', 'machine learning', 'A/B testing'],
    useVectorSearch: true,  // Enable semantic search
    vectorSearchFallback: true  // Fall back to Fuse.js if vector search fails
  };

  // Comprehensive synonym mappings for search (200+ terms across 25+ domains)
  var SYNONYMS = {
    // DIFFERENCE-IN-DIFFERENCES (DiD)
    'diff': ['DiD', 'difference-in-differences', 'diff-in-diff', 'staggered DiD'],
    'did': ['DiD', 'difference-in-differences', 'diff-in-diff', 'staggered DiD'],
    'difference': ['DiD', 'diff-in-diff', 'difference-in-differences'],
    'staggered': ['staggered DiD', 'Callaway-Sant\'Anna', 'Sun-Abraham'],
    'callaway': ['Callaway-Sant\'Anna', 'staggered DiD'],

    // SYNTHETIC CONTROL (SC)
    'sc': ['synthetic control', 'Abadie', 'synth'],
    'synthetic': ['synthetic control', 'SC', 'Abadie-Hainmueller'],
    'synth': ['synthetic control', 'SC'],
    'abadie': ['synthetic control', 'Abadie-Hainmueller'],

    // REGRESSION DISCONTINUITY (RDD)
    'rdd': ['regression discontinuity', 'discontinuity design', 'sharp RDD', 'fuzzy RDD'],
    'discontinuity': ['RDD', 'regression discontinuity'],
    'sharp': ['sharp RDD', 'regression discontinuity'],
    'fuzzy': ['fuzzy RDD', 'regression discontinuity'],

    // INSTRUMENTAL VARIABLES (IV)
    'iv': ['instrumental variable', 'instrumental variables', '2SLS', 'two-stage'],
    'instrumental': ['IV', 'instrumental variable', '2SLS'],
    '2sls': ['two-stage least squares', 'IV', 'instrumental variables'],
    'gmm': ['generalized method of moments', 'GMM', 'moment conditions'],

    // TREATMENT EFFECTS
    'ate': ['average treatment effect', 'ATE', 'treatment effect'],
    'att': ['average treatment effect on treated', 'ATT'],
    'late': ['local average treatment effect', 'LATE', 'complier'],
    'cate': ['conditional average treatment effect', 'CATE', 'heterogeneous'],
    'hte': ['heterogeneous treatment effects', 'HTE', 'CATE'],
    'ite': ['individual treatment effect', 'ITE', 'personalized'],
    'treatment': ['treatment effect', 'causal effect', 'ATE'],
    'heterogeneous': ['HTE', 'CATE', 'heterogeneous treatment effects'],

    // MATCHING & PROPENSITY
    'psm': ['propensity score matching', 'PSM', 'matching'],
    'propensity': ['propensity score', 'PSM', 'matching', 'IPW'],
    'matching': ['propensity score matching', 'PSM', 'CEM', 'nearest neighbor'],
    'cem': ['coarsened exact matching', 'CEM', 'matching'],
    'ipw': ['inverse probability weighting', 'IPW', 'propensity'],
    'aipw': ['augmented IPW', 'doubly robust', 'AIPW'],

    // DOUBLE/DEBIASED ML
    'dml': ['double machine learning', 'DML', 'debiased ML', 'Chernozhukov'],
    'double': ['double machine learning', 'DML', 'debiased'],
    'debiased': ['debiased ML', 'DML', 'double ML'],
    'chernozhukov': ['DML', 'double machine learning'],
    'orthogonal': ['Neyman orthogonal', 'DML', 'debiased'],

    // CAUSAL DISCOVERY & GRAPHS
    'dag': ['directed acyclic graph', 'DAG', 'causal graph'],
    'causal': ['causal inference', 'causality', 'treatment effect'],
    'graph': ['causal graph', 'DAG', 'Bayesian network'],
    'discovery': ['causal discovery', 'structure learning', 'PC algorithm'],
    'pc': ['PC algorithm', 'causal discovery', 'constraint-based'],
    'ges': ['GES algorithm', 'score-based', 'causal discovery'],
    'fci': ['FCI algorithm', 'latent confounders', 'causal discovery'],
    'notears': ['NOTEARS', 'gradient-based discovery', 'DAG learning'],
    'lingam': ['LiNGAM', 'non-Gaussian', 'causal discovery'],
    'tetrad': ['Tetrad', 'causal discovery', 'CMU'],

    // A/B TESTING & EXPERIMENTATION
    'ab': ['A/B testing', 'A/B test', 'experimentation', 'online experiment'],
    'experiment': ['A/B testing', 'experimentation', 'RCT', 'randomized'],
    'rct': ['randomized controlled trial', 'RCT', 'experiment'],
    'randomized': ['RCT', 'randomized experiment', 'A/B testing'],
    'testing': ['A/B testing', 'hypothesis testing', 'experimentation'],
    'online': ['online experiment', 'A/B testing', 'web experiment'],

    // VARIANCE REDUCTION
    'cuped': ['CUPED', 'variance reduction', 'covariate adjustment'],
    'variance': ['variance reduction', 'CUPED', 'precision'],
    'covariate': ['covariate adjustment', 'CUPED', 'regression adjustment'],

    // BANDITS & ADAPTIVE
    'bandit': ['multi-armed bandit', 'bandits', 'MAB', 'contextual bandit'],
    'mab': ['multi-armed bandit', 'MAB', 'bandits'],
    'contextual': ['contextual bandit', 'personalization', 'MAB'],
    'thompson': ['Thompson sampling', 'Bayesian bandit', 'posterior sampling'],
    'ucb': ['upper confidence bound', 'UCB', 'optimism'],
    'adaptive': ['adaptive experiment', 'bandits', 'sequential'],

    // UPLIFT MODELING
    'uplift': ['uplift modeling', 'incremental', 'CATE'],
    'incremental': ['incrementality', 'uplift', 'lift'],
    'lift': ['uplift', 'incrementality', 'treatment effect'],
    'qini': ['Qini curve', 'uplift metrics', 'AUUC'],
    'auuc': ['area under uplift curve', 'AUUC', 'Qini'],
    'learner': ['meta-learner', 'S-learner', 'T-learner', 'X-learner'],

    // PANEL DATA & FIXED EFFECTS
    'panel': ['panel data', 'fixed effects', 'longitudinal'],
    'fe': ['fixed effects', 'FE', 'panel'],
    'fixed': ['fixed effects', 'FE', 'panel data'],
    'reghdfe': ['high-dimensional FE', 'reghdfe', 'multi-way FE'],
    'twoway': ['two-way fixed effects', 'TWFE', 'panel'],
    'twfe': ['two-way fixed effects', 'TWFE', 'panel'],
    'arellano': ['Arellano-Bond', 'dynamic panel', 'GMM'],
    'blundell': ['Blundell-Bond', 'system GMM', 'dynamic panel'],

    // DISCRETE CHOICE & DEMAND
    'logit': ['logit', 'multinomial logit', 'discrete choice'],
    'multinomial': ['multinomial logit', 'MNL', 'discrete choice'],
    'mixed': ['mixed logit', 'random coefficients', 'discrete choice'],
    'nested': ['nested logit', 'discrete choice', 'hierarchical'],
    'blp': ['Berry-Levinsohn-Pakes', 'BLP', 'demand estimation'],
    'demand': ['demand estimation', 'BLP', 'elasticity', 'pricing'],
    'elasticity': ['price elasticity', 'demand', 'sensitivity'],
    'choice': ['discrete choice', 'logit', 'demand'],

    // PRICING & ECONOMICS
    'pricing': ['dynamic pricing', 'price optimization', 'demand'],
    'dynamic': ['dynamic pricing', 'dynamic programming'],
    'auction': ['auction', 'mechanism design', 'bidding'],
    'mechanism': ['mechanism design', 'auction', 'incentive'],

    // MARKETING MIX & BUSINESS
    'mmm': ['marketing mix model', 'MMM', 'attribution'],
    'marketing': ['marketing mix', 'MMM', 'attribution', 'CLV'],
    'attribution': ['attribution', 'MMM', 'marketing mix'],
    'clv': ['customer lifetime value', 'CLV', 'LTV'],
    'ltv': ['lifetime value', 'LTV', 'CLV'],
    'lifetime': ['lifetime value', 'CLV', 'LTV'],
    'roi': ['return on investment', 'ROI', 'incrementality'],

    // GEO-EXPERIMENTS
    'geo': ['geo-experiment', 'geo-lift', 'regional'],
    'geolift': ['GeoLift', 'geo-experiment', 'Meta'],
    'trimmed': ['trimmed match', 'geo-experiment', 'Google'],

    // TIME SERIES & FORECASTING
    'arima': ['ARIMA', 'time series', 'forecasting'],
    'garch': ['GARCH', 'volatility', 'ARCH'],
    'arch': ['ARCH', 'volatility', 'GARCH'],
    'var': ['VAR', 'vector autoregression', 'impulse response'],
    'forecast': ['forecasting', 'prediction', 'time series'],
    'prophet': ['Prophet', 'Facebook', 'forecasting'],
    'seasonality': ['seasonal', 'Prophet', 'decomposition'],
    'timeseries': ['time series', 'forecasting', 'ARIMA'],

    // BAYESIAN METHODS
    'bayes': ['Bayesian', 'bayesian inference', 'posterior'],
    'bayesian': ['Bayesian', 'MCMC', 'posterior'],
    'mcmc': ['MCMC', 'Markov chain Monte Carlo', 'sampling'],
    'nuts': ['NUTS', 'No-U-Turn Sampler', 'HMC'],
    'hmc': ['Hamiltonian Monte Carlo', 'HMC', 'NUTS'],
    'pymc': ['PyMC', 'Bayesian', 'probabilistic programming'],
    'stan': ['Stan', 'Bayesian', 'MCMC'],
    'posterior': ['posterior', 'Bayesian', 'inference'],
    'prior': ['prior', 'Bayesian', 'beliefs'],

    // STATISTICAL METHODS
    'ols': ['ordinary least squares', 'OLS', 'regression'],
    'regression': ['regression', 'OLS', 'linear model'],
    'linear': ['linear regression', 'OLS', 'GLM'],
    'glm': ['generalized linear model', 'GLM', 'logistic'],
    'quantile': ['quantile regression', 'distributional', 'percentile'],
    'bootstrap': ['bootstrap', 'resampling', 'confidence interval'],
    'cluster': ['cluster-robust', 'clustered SE', 'wild bootstrap'],
    'robust': ['robust standard errors', 'heteroskedasticity', 'cluster'],
    'anova': ['ANOVA', 'analysis of variance', 'F-test'],
    'hypothesis': ['hypothesis testing', 'p-value', 'significance'],

    // SPATIAL ECONOMETRICS
    'spatial': ['spatial econometrics', 'spatial lag', 'geographic'],
    'geographic': ['geographic', 'spatial', 'location'],

    // MARKET DESIGN & MATCHING MARKETS
    'market': ['market design', 'matching market', 'mechanism'],
    'gale': ['Gale-Shapley', 'stable matching', 'deferred acceptance'],
    'stable': ['stable matching', 'Gale-Shapley', 'two-sided'],
    'kidney': ['kidney exchange', 'matching', 'allocation'],
    'residency': ['residency match', 'NRMP', 'matching'],

    // GAME THEORY
    'game': ['game theory', 'Nash equilibrium', 'strategic'],
    'nash': ['Nash equilibrium', 'game theory', 'equilibrium'],
    'equilibrium': ['equilibrium', 'Nash', 'game theory'],

    // MACHINE LEARNING
    'ml': ['machine learning', 'ML', 'prediction'],
    'machine': ['machine learning', 'ML', 'AI'],
    'xgboost': ['XGBoost', 'gradient boosting', 'ensemble'],
    'lightgbm': ['LightGBM', 'gradient boosting', 'ensemble'],
    'catboost': ['CatBoost', 'gradient boosting', 'categorical'],
    'randomforest': ['random forest', 'RF', 'ensemble'],
    'forest': ['random forest', 'causal forest', 'trees'],
    'tree': ['decision tree', 'random forest', 'ensemble'],
    'ensemble': ['ensemble', 'boosting', 'bagging'],
    'boosting': ['gradient boosting', 'XGBoost', 'LightGBM'],
    'neural': ['neural network', 'deep learning', 'NN'],
    'deep': ['deep learning', 'neural network', 'DNN'],

    // UNCERTAINTY & CONFORMAL
    'conformal': ['conformal prediction', 'prediction intervals', 'coverage'],
    'uncertainty': ['uncertainty quantification', 'confidence', 'intervals'],
    'interval': ['prediction interval', 'confidence interval', 'bounds'],
    'calibration': ['calibration', 'probability', 'reliability'],

    // INTERFERENCE & SPILLOVERS
    'spillover': ['spillover effects', 'interference', 'network'],
    'interference': ['interference', 'spillover', 'SUTVA violation'],
    'network': ['network effects', 'spillover', 'social'],
    'sutva': ['SUTVA', 'no interference', 'stable unit'],

    // STRUCTURAL ECONOMETRICS
    'dsge': ['DSGE', 'dynamic stochastic', 'macro'],
    'structural': ['structural estimation', 'DSGE', 'dynamic'],
    'olg': ['OLG', 'overlapping generations', 'lifecycle'],
    'hank': ['HANK', 'heterogeneous agent', 'New Keynesian'],
    'dynare': ['Dynare', 'DSGE', 'macro'],

    // NLP & TEXT
    'nlp': ['NLP', 'natural language processing', 'text'],
    'text': ['text analysis', 'NLP', 'sentiment'],
    'lda': ['LDA', 'topic modeling', 'Latent Dirichlet'],
    'topic': ['topic modeling', 'LDA', 'text'],
    'sentiment': ['sentiment analysis', 'NLP', 'opinion'],
    'transformer': ['transformer', 'BERT', 'attention'],
    'bert': ['BERT', 'transformer', 'embeddings'],
    'llm': ['LLM', 'large language model', 'GPT'],

    // SURVIVAL & DURATION
    'survival': ['survival analysis', 'duration', 'hazard'],
    'hazard': ['hazard rate', 'survival', 'Cox'],
    'cox': ['Cox regression', 'proportional hazards', 'survival'],
    'duration': ['duration model', 'survival', 'time-to-event'],

    // MISSING DATA
    'imputation': ['imputation', 'missing data', 'MICE'],
    'mice': ['MICE', 'multiple imputation', 'missing data'],
    'missing': ['missing data', 'imputation', 'incomplete'],

    // POWER & DESIGN
    'power': ['power analysis', 'sample size', 'design'],
    'sample': ['sample size', 'power', 'design'],
    'design': ['experimental design', 'DOE', 'factorial'],
    'factorial': ['factorial design', 'DOE', 'experiment'],
    'sequential': ['sequential testing', 'always valid', 'anytime'],

    // DIMENSIONALITY
    'pca': ['PCA', 'principal component', 'dimensionality'],
    'dimensionality': ['dimensionality reduction', 'PCA', 'embedding'],
    'tsne': ['t-SNE', 'visualization', 'embedding'],
    'umap': ['UMAP', 'embedding', 'visualization'],
    'factor': ['factor analysis', 'EFA', 'CFA'],
    'efa': ['exploratory factor analysis', 'EFA', 'latent'],
    'cfa': ['confirmatory factor analysis', 'CFA', 'SEM'],

    // GENERAL & TOOLS
    'python': ['Python', 'py', 'package'],
    'r': ['R', 'rstats', 'R package'],
    'package': ['package', 'library', 'tool'],
    'library': ['library', 'package', 'module'],
    'sklearn': ['scikit-learn', 'sklearn', 'machine learning'],
    'statsmodels': ['statsmodels', 'statistics', 'econometrics'],
    'econometrics': ['econometrics', 'economics', 'causal'],
    'optimization': ['optimization', 'solver', 'numerical'],
    'gpu': ['GPU', 'CUDA', 'acceleration'],
    'jax': ['JAX', 'autodiff', 'GPU'],

    // DATASETS & DOMAINS
    'ecommerce': ['e-commerce', 'retail', 'shopping'],
    'retail': ['retail', 'e-commerce', 'shopping'],
    'advertising': ['advertising', 'ads', 'marketing'],
    'ads': ['ads', 'advertising', 'marketing'],
    'education': ['education', 'learning', 'EdTech'],
    'healthcare': ['healthcare', 'medical', 'health'],
    'finance': ['finance', 'financial', 'trading']
  };

  // Type display configuration
  var TYPE_CONFIG = {
    package: { label: 'Package', icon: 'pkg', color: '#0066cc', href: '/packages/' },
    dataset: { label: 'Dataset', icon: 'data', color: '#2e7d32', href: '/datasets/' },
    resource: { label: 'Resource', icon: 'book', color: '#7b1fa2', href: '/resources/' },
    talk: { label: 'Talk', icon: 'mic', color: '#e65100', href: '/talks/' },
    career: { label: 'Career', icon: 'job', color: '#c2185b', href: '/career/' },
    community: { label: 'Community', icon: 'people', color: '#00796b', href: '/community/' },
    roadmap: { label: 'Roadmap', icon: 'map', color: '#1565c0', href: '/start/' }
  };

  // State
  var fuse = null;
  var searchIndex = [];
  var isOpen = false;
  var selectedIndex = -1;
  var currentResults = [];
  var flatResults = [];

  // DOM Elements (cached after init)
  var modal, backdrop, input, resultsContainer, emptyState, hint, triggers;

  // Initialize
  function init() {
    modal = document.getElementById('global-search-modal');
    if (!modal) return;

    backdrop = modal.querySelector('.global-search-backdrop');
    input = document.getElementById('global-search-input');
    resultsContainer = document.getElementById('global-search-results');
    emptyState = document.getElementById('global-search-empty');
    hint = document.getElementById('global-search-hint');
    triggers = document.querySelectorAll('.global-search-trigger');

    loadSearchIndex();
    bindEvents();
  }

  function loadSearchIndex() {
    var dataEl = document.getElementById('global-search-data');
    if (dataEl) {
      try {
        searchIndex = JSON.parse(dataEl.textContent);
        initFuse();

        // Load vector embeddings asynchronously for semantic search
        if (CONFIG.useVectorSearch && typeof VectorSearch !== 'undefined') {
          VectorSearch.loadEmbeddings().then(function(loaded) {
            if (loaded) {
              console.log('[GlobalSearch] Vector search enabled');
            }
          });
        }
      } catch (e) {
        console.error('Failed to parse search index:', e);
      }
    }
  }

  function initFuse() {
    if (typeof Fuse !== 'undefined' && searchIndex.length > 0) {
      fuse = new Fuse(searchIndex, CONFIG.fuseOptions);
    }
  }

  function bindEvents() {
    // Keyboard shortcut (Cmd/Ctrl + K)
    document.addEventListener('keydown', function(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggleModal();
      }
      if (e.key === 'Escape' && isOpen) {
        closeModal();
      }
    });

    // Trigger buttons
    triggers.forEach(function(trigger) {
      trigger.addEventListener('click', function(e) {
        e.preventDefault();
        openModal();
      });
    });

    // Backdrop click
    if (backdrop) {
      backdrop.addEventListener('click', closeModal);
    }

    // Search input
    if (input) {
      var debounceTimer;
      input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(performSearch, CONFIG.debounceMs);
      });

      // Keyboard navigation
      input.addEventListener('keydown', handleKeyNavigation);
    }

    // Result clicks (event delegation)
    if (resultsContainer) {
      resultsContainer.addEventListener('click', handleResultClick);
    }
  }

  function toggleModal() {
    isOpen ? closeModal() : openModal();
  }

  function openModal() {
    if (!modal) return;
    modal.style.display = 'flex';
    isOpen = true;
    selectedIndex = -1;
    flatResults = [];
    input.value = '';
    setTimeout(function() { input.focus(); }, 50);
    showHint();
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    if (!modal) return;
    modal.style.display = 'none';
    isOpen = false;
    document.body.style.overflow = '';
  }

  function performSearch() {
    var query = input.value.trim();

    if (!query || query.length < 2) {
      showHint();
      currentResults = [];
      flatResults = [];
      return;
    }

    if (!fuse) return;

    // Save to recent searches
    addRecentSearch(query);

    var results;

    // Expand query with synonyms
    var expandedQueries = expandQuery(query);

    // Try vector search first if available
    if (CONFIG.useVectorSearch && typeof VectorSearch !== 'undefined' && VectorSearch.isLoaded) {
      // Use expanded queries for better vector search seeding
      results = VectorSearch.search(query, fuse, CONFIG.maxTotalResults);

      // If vector search returns few results, also try expanded Fuse.js
      if (results.length < 5 && expandedQueries.length > 1) {
        var fuseExpanded = searchWithExpansion(expandedQueries, CONFIG.maxTotalResults);
        // Merge results, avoiding duplicates
        var seen = {};
        results.forEach(function(r) { seen[r.item.name + r.item.type] = true; });
        fuseExpanded.forEach(function(r) {
          var key = r.item.name + r.item.type;
          if (!seen[key]) {
            seen[key] = true;
            results.push(r);
          }
        });
      }
    } else {
      // Fall back to Fuse.js with synonym expansion
      results = searchWithExpansion(expandedQueries, CONFIG.maxTotalResults * 2);
    }

    currentResults = results.slice(0, CONFIG.maxTotalResults);

    // Always try to show results
    if (currentResults.length === 0) {
      showEmpty();
      flatResults = [];
    } else {
      renderResults(currentResults, query);
    }
  }

  function highlightText(text, query) {
    if (!text || !query) return escapeHtml(text);
    var escaped = escapeHtml(text);
    var regex = new RegExp('(' + escapeRegex(query) + ')', 'gi');
    return escaped.replace(regex, '<mark>$1</mark>');
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function renderResults(results, query) {
    hint.style.display = 'none';
    emptyState.style.display = 'none';

    // Group by type
    var grouped = {};
    results.forEach(function(result) {
      var type = result.item.type;
      if (!grouped[type]) grouped[type] = [];
      if (grouped[type].length < CONFIG.maxResultsPerType) {
        grouped[type].push(result);
      }
    });

    var html = '';
    flatResults = [];
    var globalIndex = 0;

    // Order of types
    var typeOrder = ['package', 'dataset', 'resource', 'talk', 'career', 'community', 'roadmap'];

    typeOrder.forEach(function(type) {
      if (!grouped[type]) return;

      var typeConfig = TYPE_CONFIG[type] || { label: type, icon: 'file', color: '#666' };

      html += '<div class="result-group">';
      html += '<div class="result-group-header">';
      html += '<span class="result-type-label">' + typeConfig.label + 's</span>';
      html += '</div>';

      grouped[type].forEach(function(result) {
        var item = result.item;
        var isSelected = globalIndex === selectedIndex;
        flatResults.push(item);

        html += '<a href="' + escapeHtml(item.url) + '" ';
        html += 'class="result-item' + (isSelected ? ' selected' : '') + '" ';
        html += 'data-index="' + globalIndex + '" ';
        html += 'target="_blank" rel="noopener">';
        html += '<div class="result-content">';
        html += '<span class="result-name">' + highlightText(item.name, query) + '</span>';
        html += '<span class="result-description">' + highlightText(truncate(item.description, 80), query) + '</span>';
        html += '</div>';
        html += '<span class="result-category">' + escapeHtml(item.category) + '</span>';
        html += '</a>';

        globalIndex++;
      });

      html += '</div>';
    });

    resultsContainer.innerHTML = html;
    selectedIndex = 0;
    updateSelection();
  }

  function showHint() {
    emptyState.style.display = 'none';
    hint.style.display = 'none';

    var recent = getRecentSearches();
    var html = '';

    if (recent.length > 0) {
      html += '<div class="global-suggestions-section">';
      html += '<div class="global-suggestions-header"><span>Recent searches</span><button class="clear-recent-global">Clear</button></div>';
      html += '<div class="global-suggestion-chips">';
      recent.forEach(function(s) {
        html += '<button class="global-suggestion-chip" data-query="' + escapeHtml(s) + '">' + escapeHtml(s) + '</button>';
      });
      html += '</div></div>';
    }

    html += '<div class="global-suggestions-section">';
    html += '<div class="global-suggestions-header"><span>Try searching</span></div>';
    html += '<div class="global-suggestion-chips">';
    CONFIG.suggestions.forEach(function(s) {
      html += '<button class="global-suggestion-chip" data-query="' + escapeHtml(s) + '">' + escapeHtml(s) + '</button>';
    });
    html += '</div></div>';

    resultsContainer.innerHTML = html;

    // Bind click events
    resultsContainer.querySelectorAll('.global-suggestion-chip').forEach(function(chip) {
      chip.addEventListener('click', function() {
        var query = this.dataset.query;
        input.value = query;
        addRecentSearch(query);
        performSearch();
      });
    });

    var clearBtn = resultsContainer.querySelector('.clear-recent-global');
    if (clearBtn) {
      clearBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        clearRecentSearches();
        showHint();
      });
    }
  }

  // Recent searches helpers
  function getRecentSearches() {
    try {
      return JSON.parse(localStorage.getItem(CONFIG.recentSearchesKey)) || [];
    } catch (e) {
      return [];
    }
  }

  function addRecentSearch(query) {
    if (!query || query.length < 2) return;
    var recent = getRecentSearches();
    recent = recent.filter(function(s) { return s.toLowerCase() !== query.toLowerCase(); });
    recent.unshift(query);
    recent = recent.slice(0, CONFIG.maxRecentSearches);
    try {
      localStorage.setItem(CONFIG.recentSearchesKey, JSON.stringify(recent));
    } catch (e) {}
  }

  function clearRecentSearches() {
    try {
      localStorage.removeItem(CONFIG.recentSearchesKey);
    } catch (e) {}
  }

  function showEmpty() {
    resultsContainer.innerHTML = '';
    hint.style.display = 'none';
    emptyState.style.display = 'flex';
  }

  function handleKeyNavigation(e) {
    if (flatResults.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, flatResults.length - 1);
      updateSelection();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      updateSelection();
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault();
      var selected = resultsContainer.querySelector('.result-item.selected');
      if (selected) {
        window.open(selected.href, '_blank');
        closeModal();
      }
    }
  }

  function updateSelection() {
    var items = resultsContainer.querySelectorAll('.result-item');
    items.forEach(function(item, i) {
      if (i === selectedIndex) {
        item.classList.add('selected');
        item.scrollIntoView({ block: 'nearest' });
      } else {
        item.classList.remove('selected');
      }
    });
  }

  function handleResultClick(e) {
    var item = e.target.closest('.result-item');
    if (item) {
      closeModal();
    }
  }

  // Expand query with synonyms
  function expandQuery(query) {
    var words = query.toLowerCase().split(/\s+/);
    var expanded = [query];
    words.forEach(function(word) {
      if (SYNONYMS[word]) {
        SYNONYMS[word].forEach(function(syn) {
          if (expanded.indexOf(syn) === -1) {
            expanded.push(syn);
          }
        });
      }
    });
    return expanded;
  }

  // Search with multiple queries and combine results
  function searchWithExpansion(queries, maxResults) {
    var seen = {};
    var combined = [];

    queries.forEach(function(q) {
      var results = fuse.search(q);
      results.forEach(function(r) {
        var key = r.item.name + r.item.type;
        if (!seen[key]) {
          seen[key] = true;
          combined.push(r);
        }
      });
    });

    // Sort by score (lower is better in Fuse.js)
    combined.sort(function(a, b) { return a.score - b.score; });
    return combined.slice(0, maxResults);
  }

  // Utility functions
  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
