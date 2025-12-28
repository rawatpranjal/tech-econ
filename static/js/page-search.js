// Generic Page Search Module - Fuse.js fuzzy search with relevance ordering
// Works with any section page (career, learning, talks, community, etc.)
(function() {
    'use strict';

    // Comprehensive synonym mappings for domain terms
    var SYNONYMS = {
        // Causal Inference
        'did': ['DiD', 'difference-in-differences', 'diff-in-diff', 'staggered DiD'],
        'diff': ['DiD', 'difference-in-differences', 'diff-in-diff'],
        'sc': ['synthetic control', 'Abadie', 'synth'],
        'synthetic': ['synthetic control', 'SC'],
        'rdd': ['regression discontinuity', 'sharp RDD', 'fuzzy RDD'],
        'iv': ['instrumental variable', 'instrumental variables', '2SLS'],
        'instrumental': ['IV', 'instrumental variable', '2SLS'],
        '2sls': ['two-stage least squares', 'IV'],
        // Treatment Effects
        'ate': ['average treatment effect', 'ATE', 'treatment effect'],
        'att': ['average treatment effect on treated', 'ATT'],
        'cate': ['conditional average treatment effect', 'CATE', 'heterogeneous'],
        'hte': ['heterogeneous treatment effects', 'HTE', 'CATE'],
        'treatment': ['treatment effect', 'causal effect', 'ATE'],
        // Matching & Propensity
        'psm': ['propensity score matching', 'PSM', 'matching'],
        'propensity': ['propensity score', 'PSM', 'matching', 'IPW'],
        'matching': ['propensity score matching', 'PSM', 'CEM'],
        'ipw': ['inverse probability weighting', 'IPW', 'propensity'],
        'aipw': ['augmented IPW', 'doubly robust', 'AIPW'],
        // Double/Debiased ML
        'dml': ['double machine learning', 'DML', 'debiased ML'],
        'double': ['double machine learning', 'DML', 'debiased'],
        // A/B Testing
        'ab': ['A/B testing', 'A/B test', 'experimentation'],
        'experiment': ['A/B testing', 'experimentation', 'RCT'],
        'rct': ['randomized controlled trial', 'RCT', 'experiment'],
        'cuped': ['CUPED', 'variance reduction', 'covariate adjustment'],
        'variance': ['variance reduction', 'CUPED', 'precision'],
        // Bandits
        'bandit': ['multi-armed bandit', 'bandits', 'MAB', 'contextual bandit'],
        'mab': ['multi-armed bandit', 'MAB', 'bandits'],
        'thompson': ['Thompson sampling', 'Bayesian bandit'],
        'ucb': ['upper confidence bound', 'UCB'],
        // Uplift
        'uplift': ['uplift modeling', 'incremental', 'CATE'],
        'incremental': ['incrementality', 'uplift', 'lift'],
        // Panel & Fixed Effects
        'panel': ['panel data', 'fixed effects', 'longitudinal'],
        'fe': ['fixed effects', 'FE', 'panel'],
        'twfe': ['two-way fixed effects', 'TWFE', 'panel'],
        // Demand & Pricing
        'blp': ['Berry-Levinsohn-Pakes', 'BLP', 'demand estimation'],
        'demand': ['demand estimation', 'BLP', 'elasticity', 'pricing'],
        'pricing': ['dynamic pricing', 'price optimization', 'demand'],
        // Marketing
        'mmm': ['marketing mix model', 'MMM', 'attribution'],
        'marketing': ['marketing mix', 'MMM', 'attribution', 'CLV'],
        'clv': ['customer lifetime value', 'CLV', 'LTV'],
        'ltv': ['lifetime value', 'LTV', 'CLV'],
        // Geo
        'geo': ['geo-experiment', 'geo-lift', 'regional'],
        'geolift': ['GeoLift', 'geo-experiment'],
        // Time Series
        'arima': ['ARIMA', 'time series', 'forecasting'],
        'forecast': ['forecasting', 'prediction', 'time series'],
        'prophet': ['Prophet', 'Facebook', 'forecasting'],
        'timeseries': ['time series', 'forecasting', 'ARIMA'],
        // Bayesian
        'bayes': ['Bayesian', 'bayesian inference', 'posterior'],
        'bayesian': ['Bayesian', 'MCMC', 'posterior'],
        'mcmc': ['MCMC', 'Markov chain Monte Carlo', 'sampling'],
        'pymc': ['PyMC', 'Bayesian', 'probabilistic programming'],
        'stan': ['Stan', 'Bayesian', 'MCMC'],
        // ML
        'ml': ['machine learning', 'ML', 'prediction'],
        'xgboost': ['XGBoost', 'gradient boosting', 'ensemble'],
        'lightgbm': ['LightGBM', 'gradient boosting', 'ensemble'],
        'forest': ['random forest', 'causal forest', 'trees'],
        'neural': ['neural network', 'deep learning', 'NN'],
        'deep': ['deep learning', 'neural network', 'DNN'],
        // NLP
        'nlp': ['NLP', 'natural language processing', 'text'],
        'text': ['text analysis', 'NLP', 'sentiment'],
        'llm': ['LLM', 'large language model', 'GPT'],
        // General
        'python': ['Python', 'py', 'package'],
        'r': ['R', 'rstats', 'R package'],
        'econometrics': ['econometrics', 'economics', 'causal'],
        'causal': ['causal inference', 'causality', 'treatment effect']
    };

    // Generate bidirectional synonym mappings
    (function() {
        var reverseMap = {};
        Object.keys(SYNONYMS).forEach(function(key) {
            SYNONYMS[key].forEach(function(syn) {
                var synLower = syn.toLowerCase();
                if (!reverseMap[synLower]) reverseMap[synLower] = [];
                if (reverseMap[synLower].indexOf(key) === -1) reverseMap[synLower].push(key);
            });
        });
        Object.keys(reverseMap).forEach(function(key) {
            if (!SYNONYMS[key]) {
                SYNONYMS[key] = reverseMap[key];
            } else {
                reverseMap[key].forEach(function(val) {
                    if (SYNONYMS[key].indexOf(val) === -1) SYNONYMS[key].push(val);
                });
            }
        });
    })();

    // Expand query with synonyms
    function expandQuery(query) {
        var words = query.toLowerCase().split(/\s+/);
        var expanded = [query];
        words.forEach(function(word) {
            if (SYNONYMS[word]) {
                SYNONYMS[word].forEach(function(syn) {
                    if (expanded.indexOf(syn) === -1) expanded.push(syn);
                });
            }
        });
        return expanded;
    }

    // Escape regex special characters
    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // Boost exact matches (lower score = better in Fuse.js)
    function boostExactMatches(results, query) {
        var queryLower = query.toLowerCase().trim();
        var synonymsToBoost = SYNONYMS[queryLower] || [];

        return results.map(function(result) {
            var item = result.item;
            var nameLower = (item.name || '').toLowerCase();
            var boost = 0;

            // Exact name match
            if (nameLower === queryLower) boost = 0.6;
            else if (nameLower.startsWith(queryLower)) boost = 0.4;
            else if (new RegExp('\\b' + escapeRegex(queryLower) + '\\b', 'i').test(nameLower)) boost = 0.3;

            // Check tags
            if (Array.isArray(item.tags)) {
                var exactTagMatch = item.tags.some(function(tag) {
                    return tag.toLowerCase() === queryLower;
                });
                if (exactTagMatch) boost = Math.max(boost, 0.35);

                var synonymTagMatch = item.tags.some(function(tag) {
                    var tagLower = tag.toLowerCase();
                    return synonymsToBoost.some(function(syn) {
                        return tagLower === syn.toLowerCase();
                    });
                });
                if (synonymTagMatch) boost = Math.max(boost, 0.25);
            }

            // Check category
            if (new RegExp('\\b' + escapeRegex(query) + '\\b', 'i').test(item.category || '')) {
                boost = Math.max(boost, 0.3);
            }

            return {
                item: result.item,
                score: Math.max(0, (result.score || 0) - boost),
                refIndex: result.refIndex,
                matches: result.matches
            };
        }).sort(function(a, b) { return a.score - b.score; });
    }

    function PageSearch(config) {
        // Merge config with defaults
        this.config = Object.assign({
            searchInputId: 'page-search',
            clearBtnId: 'clear-search',
            searchDataId: 'search-data',
            resultCountId: 'result-count',
            categorySelectId: 'category-select',
            viewContainerId: null,
            cardSelector: '.resource-card',
            sectionSelector: '.category-section',
            tableRowSelector: null,  // e.g., '#talks-table tbody tr'
            itemLabel: 'items',
            fuseKeys: [
                { name: 'name', weight: 2 },
                { name: 'description', weight: 1 },
                { name: 'category', weight: 0.8 }
            ],
            fuseThreshold: 0.35,
            extraFilters: []  // e.g., [{ selectId: 'format-select', dataKey: 'type' }]
        }, config);

        // DOM elements
        this.searchInput = null;
        this.clearBtn = null;
        this.resultCount = null;
        this.categorySelect = null;
        this.viewContainer = null;
        this.cards = null;
        this.sections = null;
        this.tableRows = null;

        // State
        this.fuse = null;
        this.data = [];
        this.originalOrder = [];
        this.flatContainer = null;
        this.currentCategory = 'all';
        this.currentSearch = '';
        this.debounceTimer = null;
        this.totalItems = 0;
        this.extraFilterValues = {};  // Store values for extra filters

        this.init();
    }

    PageSearch.prototype.init = function() {
        var self = this;

        // Get DOM elements
        this.searchInput = document.getElementById(this.config.searchInputId);
        this.clearBtn = document.getElementById(this.config.clearBtnId);
        this.resultCount = document.getElementById(this.config.resultCountId);
        this.categorySelect = document.getElementById(this.config.categorySelectId);

        if (!this.searchInput) {
            console.warn('PageSearch: search input not found:', this.config.searchInputId);
            return;
        }

        // Get view container
        if (this.config.viewContainerId) {
            this.viewContainer = document.getElementById(this.config.viewContainerId);
        }
        if (!this.viewContainer) {
            // Find first parent that contains the cards
            this.viewContainer = this.searchInput.closest('.container');
        }

        // Get cards and sections
        this.cards = document.querySelectorAll(this.config.cardSelector);
        this.sections = document.querySelectorAll(this.config.sectionSelector);
        this.totalItems = this.cards.length;

        // Get table rows if configured
        if (this.config.tableRowSelector) {
            this.tableRows = document.querySelectorAll(this.config.tableRowSelector);
        }

        // Store original order
        this.originalOrder = Array.from(this.cards);

        // Create flat container for search results
        this.createFlatContainer();

        // Initialize Fuse.js
        this.initFuse();

        // Event listeners
        this.searchInput.addEventListener('input', function(e) {
            clearTimeout(self.debounceTimer);
            self.debounceTimer = setTimeout(function() {
                self.currentSearch = e.target.value.trim();
                self.filterItems();
                self.toggleClearButton();
            }, 150);
        });

        if (this.clearBtn) {
            this.clearBtn.addEventListener('click', function() {
                self.clearSearch();
            });
        }

        if (this.categorySelect) {
            this.categorySelect.addEventListener('change', function() {
                self.currentCategory = this.value;
                self.filterItems();
            });
        }

        // Setup extra filters
        this.config.extraFilters.forEach(function(filter) {
            var selectEl = document.getElementById(filter.selectId);
            if (selectEl) {
                self.extraFilterValues[filter.dataKey] = 'all';
                selectEl.addEventListener('change', function() {
                    self.extraFilterValues[filter.dataKey] = this.value;
                    self.filterItems();
                });
            }
        });

        // Initial state
        this.toggleClearButton();
        this.updateResultCount(this.totalItems);
    };

    PageSearch.prototype.createFlatContainer = function() {
        // Find the first category section's parent to insert flat container
        var firstSection = this.sections[0];
        if (!firstSection) return;

        this.flatContainer = document.createElement('div');
        this.flatContainer.className = 'cards-row flat-results';
        this.flatContainer.style.display = 'none';
        firstSection.parentNode.insertBefore(this.flatContainer, firstSection);
    };

    PageSearch.prototype.initFuse = function() {
        var searchDataEl = document.getElementById(this.config.searchDataId);
        if (searchDataEl) {
            try {
                this.data = JSON.parse(searchDataEl.textContent);
                console.log('PageSearch [' + this.config.searchInputId + ']: Loaded', this.data.length, 'items');
            } catch (e) {
                console.error('PageSearch: Failed to parse search data:', e);
                this.data = [];
            }
        } else {
            console.warn('PageSearch: No search data element found:', this.config.searchDataId);
        }

        if (typeof Fuse !== 'undefined' && this.data.length > 0) {
            this.fuse = new Fuse(this.data, {
                keys: this.config.fuseKeys,
                threshold: this.config.fuseThreshold,
                ignoreLocation: true,
                includeScore: true,
                minMatchCharLength: 2
            });
            console.log('PageSearch [' + this.config.searchInputId + ']: Fuse initialized');
        } else {
            console.warn('PageSearch: Fuse NOT initialized. Fuse defined:', typeof Fuse !== 'undefined', 'Data length:', this.data.length);
        }
    };

    PageSearch.prototype.filterItems = function() {
        if (this.currentSearch && this.fuse) {
            this.showFlatResults();
        } else {
            this.showCategoryLayout();
        }

        // Filter table rows if configured
        if (this.tableRows) {
            this.filterTableRows();
        }

        this.updateResultCount(this.getVisibleCount());
    };

    PageSearch.prototype.matchesExtraFilters = function(element) {
        var self = this;
        var matches = true;
        Object.keys(this.extraFilterValues).forEach(function(dataKey) {
            var filterValue = self.extraFilterValues[dataKey];
            if (filterValue !== 'all') {
                var elementValue = element.dataset[dataKey] || '';
                if (elementValue.toLowerCase() !== filterValue.toLowerCase()) {
                    matches = false;
                }
            }
        });
        return matches;
    };

    PageSearch.prototype.filterTableRows = function() {
        var self = this;
        var scoreMap = new Map();

        if (this.currentSearch && this.fuse) {
            // Adaptive threshold for short queries
            var originalThreshold = this.fuse.options.threshold;
            if (this.currentSearch.length <= 4) {
                this.fuse.options.threshold = 0.2;
            } else if (this.currentSearch.length <= 6) {
                this.fuse.options.threshold = 0.3;
            }

            // Expand query with synonyms and search
            var expandedQueries = expandQuery(this.currentSearch);
            var seen = {};
            var allResults = [];

            expandedQueries.forEach(function(q, queryIndex) {
                var queryResults = self.fuse.search(q);
                queryResults.forEach(function(r) {
                    var key = r.item.name;
                    if (!seen[key]) {
                        seen[key] = true;
                        var penalizedScore = queryIndex > 0 ? Math.min(1, r.score + 0.1) : r.score;
                        allResults.push({
                            item: r.item,
                            score: penalizedScore,
                            refIndex: r.refIndex,
                            matches: r.matches
                        });
                    }
                });
            });

            // Restore original threshold
            this.fuse.options.threshold = originalThreshold;

            // Boost exact matches
            var results = boostExactMatches(allResults, this.currentSearch);
            results.forEach(function(result) {
                scoreMap.set(result.item.name.toLowerCase(), result.score);
            });
        }

        this.tableRows.forEach(function(row) {
            var name = row.dataset.name || '';
            var category = row.dataset.category || '';

            var matchesCategory = self.currentCategory === 'all' || category === self.currentCategory;
            var matchesExtra = self.matchesExtraFilters(row);

            if (matchesCategory && matchesExtra) {
                row.style.display = '';
                // Apply opacity based on search score
                if (self.currentSearch) {
                    var score = scoreMap.get(name);
                    if (score !== undefined && score < 0.3) {
                        row.style.opacity = '1';
                    } else if (score !== undefined && score < 0.5) {
                        row.style.opacity = '0.9';
                    } else {
                        row.style.opacity = '0.7';
                    }
                } else {
                    row.style.opacity = '1';
                }
            } else {
                row.style.display = 'none';
            }
        });
    };

    PageSearch.prototype.showFlatResults = function() {
        var self = this;

        // Safety check - ensure fuse is initialized
        if (!this.fuse) {
            console.warn('PageSearch: Fuse not initialized in showFlatResults');
            return;
        }

        console.log('PageSearch: Searching for "' + this.currentSearch + '"');

        // Hide category sections
        this.sections.forEach(function(section) {
            section.style.display = 'none';
        });

        // Show flat container
        if (this.flatContainer) {
            this.flatContainer.style.display = 'grid';
        }

        // Adaptive threshold for short queries (abbreviations)
        var originalThreshold = this.fuse.options.threshold;
        if (this.currentSearch.length <= 4) {
            this.fuse.options.threshold = 0.2;
        } else if (this.currentSearch.length <= 6) {
            this.fuse.options.threshold = 0.3;
        }

        // Expand query with synonyms and search
        var expandedQueries = expandQuery(this.currentSearch);
        var seen = {};
        var allResults = [];

        expandedQueries.forEach(function(q, queryIndex) {
            var queryResults = self.fuse.search(q);
            queryResults.forEach(function(r) {
                var key = r.item.name;
                if (!seen[key]) {
                    seen[key] = true;
                    // Penalize synonym matches slightly
                    var penalizedScore = queryIndex > 0 ? Math.min(1, r.score + 0.1) : r.score;
                    allResults.push({
                        item: r.item,
                        score: penalizedScore,
                        refIndex: r.refIndex,
                        matches: r.matches
                    });
                }
            });
        });

        // Restore original threshold
        this.fuse.options.threshold = originalThreshold;

        // Boost exact matches
        var results = boostExactMatches(allResults, this.currentSearch);

        var scoreMap = new Map();
        results.forEach(function(result) {
            scoreMap.set(result.item.name.toLowerCase(), result.score);
        });

        // Sort cards by relevance
        var cardsArray = Array.from(this.cards);
        cardsArray.sort(function(a, b) {
            var scoreA = scoreMap.has(a.dataset.name) ? scoreMap.get(a.dataset.name) : 1;
            var scoreB = scoreMap.has(b.dataset.name) ? scoreMap.get(b.dataset.name) : 1;
            return scoreA - scoreB;
        });

        // Filter by category if needed
        if (this.currentCategory !== 'all') {
            cardsArray = cardsArray.filter(function(card) {
                return card.dataset.category === self.currentCategory;
            });
        }

        // Filter by extra filters
        cardsArray = cardsArray.filter(function(card) {
            return self.matchesExtraFilters(card);
        });

        // Hide all cards first
        this.cards.forEach(function(card) {
            card.classList.add('hidden');
            card.classList.remove('visible');
        });

        // Move matching cards to flat container in sorted order
        cardsArray.forEach(function(card) {
            card.classList.remove('hidden');
            card.classList.add('visible');

            // Visual indicator for match quality
            var score = scoreMap.get(card.dataset.name);
            if (score !== undefined && score < 0.3) {
                card.style.opacity = '1';
            } else if (score !== undefined && score < 0.5) {
                card.style.opacity = '0.9';
            } else {
                card.style.opacity = '0.7';
            }

            self.flatContainer.appendChild(card);
        });
    };

    PageSearch.prototype.showCategoryLayout = function() {
        var self = this;

        // Reset section visibility (remove section-hidden from previous filter)
        this.sections.forEach(function(section) {
            section.classList.remove('section-hidden');
            var cat = section.dataset.sectionCategory;
            var shouldShow = self.currentCategory === 'all' || cat === self.currentCategory;
            section.style.display = shouldShow ? '' : 'none';
        });

        // Hide flat container
        if (this.flatContainer) {
            this.flatContainer.style.display = 'none';
        }

        // Restore cards to original positions
        this.originalOrder.forEach(function(card) {
            var cardCategory = card.dataset.category;
            var matchesCategory = self.currentCategory === 'all' || cardCategory === self.currentCategory;
            var matchesExtra = self.matchesExtraFilters(card);

            // Find original parent (cards-row within category section)
            var section = document.querySelector('[data-section-category="' + cardCategory + '"]');
            if (section) {
                var cardsRow = section.querySelector('.cards-row');
                if (cardsRow && card.parentNode !== cardsRow) {
                    cardsRow.appendChild(card);
                }
            }

            if (matchesCategory && matchesExtra) {
                card.classList.remove('hidden');
                card.classList.add('visible');
                card.style.opacity = '1';
            } else {
                card.classList.add('hidden');
                card.classList.remove('visible');
            }
        });

        // Update section visibility based on visible cards
        this.sections.forEach(function(section) {
            var visibleCards = section.querySelectorAll(self.config.cardSelector + ':not(.hidden)');
            if (visibleCards.length === 0) {
                section.classList.add('section-hidden');
            } else {
                section.classList.remove('section-hidden');
            }
        });
    };

    PageSearch.prototype.getVisibleCount = function() {
        var count = 0;
        this.cards.forEach(function(card) {
            if (!card.classList.contains('hidden') && card.offsetParent !== null) {
                count++;
            }
        });
        return count || this.totalItems;
    };

    PageSearch.prototype.updateResultCount = function(count) {
        if (!this.resultCount) return;
        var text = count === 1 ? '1 ' + this.config.itemLabel.replace(/s$/, '') : count + ' ' + this.config.itemLabel;
        if (this.currentSearch) {
            text += ' (sorted by relevance)';
        }
        this.resultCount.textContent = text;
    };

    PageSearch.prototype.toggleClearButton = function() {
        if (!this.clearBtn) return;
        this.clearBtn.style.display = this.searchInput.value ? 'flex' : 'none';
    };

    PageSearch.prototype.clearSearch = function() {
        this.searchInput.value = '';
        this.currentSearch = '';
        this.filterItems();
        this.toggleClearButton();
        this.searchInput.focus();
    };

    // Expose to global
    window.PageSearch = PageSearch;
})();
