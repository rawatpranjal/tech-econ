/**
 * Search Synonyms Module
 *
 * Comprehensive synonym mappings for domain terms (200+ terms across 25+ domains).
 * Single source of truth - used by both search-worker.js and unified-search.js.
 */
(function(global) {
  'use strict';

  // Comprehensive synonym mappings for search
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

  // Generate bidirectional synonym mappings
  // So "difference-in-differences" also finds DiD packages
  (function() {
    var reverseMap = {};
    Object.keys(SYNONYMS).forEach(function(key) {
      SYNONYMS[key].forEach(function(syn) {
        var synLower = syn.toLowerCase();
        if (!reverseMap[synLower]) {
          reverseMap[synLower] = [];
        }
        if (reverseMap[synLower].indexOf(key) === -1) {
          reverseMap[synLower].push(key);
        }
      });
    });
    // Merge reverse mappings into SYNONYMS
    Object.keys(reverseMap).forEach(function(key) {
      if (!SYNONYMS[key]) {
        SYNONYMS[key] = reverseMap[key];
      } else {
        reverseMap[key].forEach(function(val) {
          if (SYNONYMS[key].indexOf(val) === -1) {
            SYNONYMS[key].push(val);
          }
        });
      }
    });
  })();

  /**
   * Expand query with synonyms
   * @param {string} query - Search query
   * @returns {string[]} - Array of expanded queries
   */
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

  /**
   * Get synonyms for a term
   * @param {string} term - Search term
   * @returns {string[]} - Array of synonyms
   */
  function getSynonyms(term) {
    return SYNONYMS[term.toLowerCase()] || [];
  }

  // Export
  var SearchSynonyms = {
    SYNONYMS: SYNONYMS,
    expandQuery: expandQuery,
    getSynonyms: getSynonyms
  };

  // AMD/CommonJS/Global export
  if (typeof define === 'function' && define.amd) {
    define(function() { return SearchSynonyms; });
  } else if (typeof module === 'object' && module.exports) {
    module.exports = SearchSynonyms;
  } else {
    global.SearchSynonyms = SearchSynonyms;
  }

})(typeof window !== 'undefined' ? window : typeof self !== 'undefined' ? self : this);
