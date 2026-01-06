/**
 * Explore Page - Netflix-style topic browsing
 * Features:
 * - Horizontal scrolling rows per cluster
 * - MMR-based diversity selection (pre-computed at build time)
 * - Hero content prioritization (talks > tutorials > papers)
 * - Lazy loading of rows as user scrolls
 * - Shuffle button for cluster order variety
 * - Keyboard and touch navigation
 */

(function() {
    'use strict';

    // Configuration
    const ROWS_PER_BATCH = 5;       // Load 5 rows at a time (faster first paint)
    const ITEMS_PER_ROW = 15;       // Show max 15 items per row
    const MIN_CLUSTER_SIZE = 3;     // Hide clusters with < 3 items (more granular)

    // Curation: Labels to deprioritize (generic/career-heavy)
    const DEPRIORITIZED_LABELS = [
        'career portal', 'job search', 'marketplace', 'recruitment',
        'job board', 'hiring', 'employment', 'resume'
    ];

    // Curation: Labels to prioritize (technical/interesting)
    const PRIORITIZED_LABELS = [
        'causal', 'inference', 'bayesian', 'machine learning', 'neural',
        'statistical', 'regression', 'time series', 'experimental',
        'econometric', 'optimization', 'algorithm', 'deep learning'
    ];

    let clusterData = null;
    let narrativeCarousels = null;
    let allItemsData = null;
    let itemLookup = {};
    let shuffledClusters = [];
    let loadedRowCount = 0;
    let isLoading = false;

    // Initialize on DOM load
    document.addEventListener('DOMContentLoaded', init);

    async function init() {
        // Show loading state
        const loader = document.getElementById('explore-loader');
        loader.classList.add('visible');

        try {
            // Fetch data files in parallel for speed
            const urls = window.DISCOVER_DATA_URLS;
            const [narrativeRes, clustersRes, packagesRes, resourcesRes, datasetsRes, talksRes, careerRes, communityRes, booksRes, papersRes] = await Promise.all([
                fetch(urls.narrativeCarousels).catch(() => null),
                fetch(urls.clusters),
                fetch(urls.packages),
                fetch(urls.resources),
                fetch(urls.datasets),
                fetch(urls.talks),
                fetch(urls.career),
                fetch(urls.community),
                fetch(urls.books),
                fetch(urls.papers)
            ]);

            // Load narrative carousels (optional - may not exist)
            if (narrativeRes && narrativeRes.ok) {
                narrativeCarousels = await narrativeRes.json();
                console.log(`[Discover] Loaded ${narrativeCarousels.carousels?.length || 0} narrative carousels`);
            }

            clusterData = await clustersRes.json();
            allItemsData = {
                packages: await packagesRes.json(),
                resources: await resourcesRes.json(),
                datasets: await datasetsRes.json(),
                talks: await talksRes.json(),
                career: await careerRes.json(),
                community: await communityRes.json(),
                books: await booksRes.json(),
                papers: await papersRes.json()
            };
        } catch (e) {
            console.error('[Discover] Failed to load explore data:', e);
            loader.classList.remove('visible');
            document.getElementById('explore-rows').innerHTML = '<p style="padding: 2rem; text-align: center;">Failed to load data. Please refresh.</p>';
            return;
        }

        // Build item lookup by ID
        buildItemLookup();

        // Initial shuffle and load
        shuffleAndLoad();

        // Setup lazy loading on scroll
        setupLazyLoad();

        // Setup shuffle button
        document.getElementById('shuffle-btn').addEventListener('click', function() {
            shuffleAndLoad();
        });
    }

    function buildItemLookup() {
        // Map item IDs to full item data
        // IDs are in format: "type-slugified-name" (e.g., "package-dowhy")

        const typeMap = {
            'package': allItemsData.packages,
            'resource': allItemsData.resources,
            'dataset': allItemsData.datasets,
            'talk': allItemsData.talks,
            'career': allItemsData.career,
            'community': allItemsData.community,
            'book': allItemsData.books,
            'paper': allItemsData.papers
        };

        for (const [type, items] of Object.entries(typeMap)) {
            if (!items) continue;
            items.forEach(item => {
                const slug = slugify(item.name || item.title || '');
                const id = `${type}-${slug}`;
                itemLookup[id] = { ...item, _type: type };
            });
        }
    }

    function slugify(text) {
        return text.toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
    }

    function shuffleArray(array) {
        const arr = [...array];
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    // Score cluster for curation (higher = show first)
    function scoreCluster(cluster) {
        const label = cluster.label.toLowerCase();
        let score = 0;

        // Deprioritize generic/career labels
        for (const term of DEPRIORITIZED_LABELS) {
            if (label.includes(term)) {
                score -= 50;
                break;
            }
        }

        // Prioritize technical/interesting labels
        for (const term of PRIORITIZED_LABELS) {
            if (label.includes(term)) {
                score += 30;
                break;
            }
        }

        // Prefer medium-sized clusters (10-50 items) over very large ones
        if (cluster.item_count >= 10 && cluster.item_count <= 50) {
            score += 10;
        } else if (cluster.item_count > 100) {
            score -= 5; // Very large clusters might be too generic
        }

        // Penalize homogeneous clusters (all items same type)
        const itemIds = getClusterItems(cluster.id);
        const sampleItems = itemIds.slice(0, 20).map(id => itemLookup[id]).filter(Boolean);
        if (sampleItems.length > 0) {
            const types = new Set(sampleItems.map(i => i._type));
            if (types.size === 1) {
                score -= 20; // Single-type clusters are less interesting
            }
        }

        // Boost clusters with high-engagement items (use model_score)
        const topScores = sampleItems
            .map(item => item.model_score || 0)
            .sort((a, b) => b - a)
            .slice(0, 5);
        const engagementBonus = topScores.reduce((sum, s) => sum + s * 50, 0);
        score += engagementBonus;

        // Add randomness to keep it fresh each load
        score += Math.random() * 20;

        return score;
    }

    function curatedSort(clusters) {
        // Score all clusters
        const scored = clusters.map(c => ({ cluster: c, score: scoreCluster(c) }));

        // Sort by score descending
        scored.sort((a, b) => b.score - a.score);

        // Interleave for variety: take from top, middle, bottom
        const result = [];
        const sorted = scored.map(s => s.cluster);
        const third = Math.floor(sorted.length / 3);

        let top = 0, mid = third, bot = third * 2;
        let pickFrom = 'top';

        while (result.length < sorted.length) {
            if (pickFrom === 'top' && top < third) {
                result.push(sorted[top++]);
                pickFrom = 'mid';
            } else if (pickFrom === 'mid' && mid < third * 2) {
                result.push(sorted[mid++]);
                pickFrom = 'bot';
            } else if (pickFrom === 'bot' && bot < sorted.length) {
                result.push(sorted[bot++]);
                pickFrom = 'top';
            } else {
                // Fallback: add remaining from any bucket
                if (top < third) result.push(sorted[top++]);
                else if (mid < third * 2) result.push(sorted[mid++]);
                else if (bot < sorted.length) result.push(sorted[bot++]);
            }
        }

        return result;
    }

    // Task 1.3: Store narrative carousels for interspersion
    let narrativeQueue = [];
    let narrativePositionCounter = 0;
    let totalRowsRendered = 0;
    const NARRATIVE_INTERVAL = 4; // Insert narrative every 4 regular rows (3-4 range)

    function shuffleAndLoad() {
        const container = document.getElementById('explore-rows');
        container.innerHTML = '';
        loadedRowCount = 0;
        narrativePositionCounter = 0;
        totalRowsRendered = 0; // Reset for interspersion

        // Task 1.3: Prepare narrative carousels for interspersion (every 3-4 rows)
        narrativeQueue = [];
        if (narrativeCarousels && narrativeCarousels.carousels) {
            narrativeQueue = shuffleArray(narrativeCarousels.carousels);
        }

        // Filter and sort semantic clusters
        const filtered = clusterData.clusters.filter(c => c.item_count >= MIN_CLUSTER_SIZE);
        shuffledClusters = curatedSort(filtered);

        // Load rows with interspersed narratives
        loadMoreRows();
    }

    // Task 1.2: Get daily seed for hero rotation (same hero all day)
    function getDailyHeroSeed() {
        const today = new Date();
        return today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate();
    }

    // Task 1.2: Select hero based on daily rotation
    function selectDailyHero(items, carouselId) {
        if (!items || items.length === 0) return null;
        const seed = getDailyHeroSeed();
        // Use carousel ID + date to get consistent but different hero per carousel per day
        const hash = (seed + carouselId.split('').reduce((a, c) => a + c.charCodeAt(0), 0)) % items.length;
        return items[hash];
    }

    function createNarrativeRow(carousel, position = 0) {
        const row = document.createElement('div');
        row.className = 'explore-row narrative-row';
        row.dataset.carouselId = carousel.id;
        row.dataset.template = carousel.template;
        // Task 1.3: Position-based gradient styling (cycles through 6 colors)
        row.dataset.position = String(position % 6);

        // Header (template badge hidden via CSS - Task 1.3)
        const header = document.createElement('div');
        header.className = 'explore-row-header';
        const templateBadge = carousel.template ? `<span class="template-badge template-${carousel.template}">${carousel.template}</span>` : '';
        header.innerHTML = `
            <h2 class="explore-row-title">${escapeHtml(carousel.name)}</h2>
            ${templateBadge}
        `;
        row.appendChild(header);

        // Description if available
        if (carousel.description) {
            const desc = document.createElement('p');
            desc.className = 'explore-row-description';
            desc.textContent = carousel.description;
            row.appendChild(desc);
        }

        // Scroller wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'explore-scroller-wrapper';

        const scroller = document.createElement('div');
        scroller.className = 'explore-scroller';

        // Task 1.2: Build list of all items for daily hero rotation
        const allItems = [];
        if (carousel.hero) {
            const heroItem = itemLookup[carousel.hero.id] || carousel.hero;
            if (heroItem) {
                allItems.push({ item: {...heroItem, _type: carousel.hero.type}, isOriginalHero: true });
            }
        }
        if (carousel.items) {
            carousel.items.forEach(item => {
                const fullItem = itemLookup[item.id] || item;
                if (fullItem) {
                    allItems.push({ item: {...fullItem, _type: item.type}, isOriginalHero: false });
                }
            });
        }

        // Task 1.2: Select daily hero (rotates based on date seed)
        const dailyHeroIndex = allItems.length > 0 ? (getDailyHeroSeed() + carousel.id.split('').reduce((a, c) => a + c.charCodeAt(0), 0)) % allItems.length : 0;

        // Add cards with hero first
        allItems.forEach((entry, idx) => {
            const isHero = idx === dailyHeroIndex;
            const card = createExploreCard(entry.item, false, isHero, isHero);
            if (isHero) {
                // Insert hero at the beginning
                scroller.insertBefore(card, scroller.firstChild);
            } else {
                scroller.appendChild(card);
            }
        });

        wrapper.appendChild(scroller);

        // Navigation arrows
        const prevBtn = document.createElement('button');
        prevBtn.className = 'scroller-nav prev';
        prevBtn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg>';
        prevBtn.addEventListener('click', () => scrollRow(scroller, -1));

        const nextBtn = document.createElement('button');
        nextBtn.className = 'scroller-nav next';
        nextBtn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>';
        nextBtn.addEventListener('click', () => scrollRow(scroller, 1));

        wrapper.appendChild(prevBtn);
        wrapper.appendChild(nextBtn);
        row.appendChild(wrapper);

        // Mobile scroll indicator
        const scrollIndicator = document.createElement('div');
        scrollIndicator.className = 'scroll-indicator';
        scrollIndicator.innerHTML = '← Swipe →';
        row.appendChild(scrollIndicator);

        // Update nav button states on scroll
        scroller.addEventListener('scroll', () => updateNavButtons(scroller, prevBtn, nextBtn));
        setTimeout(() => updateNavButtons(scroller, prevBtn, nextBtn), 0);

        return row;
    }

    function loadMoreRows() {
        if (isLoading) return;

        const remaining = shuffledClusters.length - loadedRowCount;
        const hasNarratives = narrativeQueue.length > 0;

        if (remaining <= 0 && !hasNarratives) {
            document.getElementById('explore-loader').classList.remove('visible');
            return;
        }

        isLoading = true;
        document.getElementById('explore-loader').classList.add('visible');

        const container = document.getElementById('explore-rows');
        const toLoad = Math.min(ROWS_PER_BATCH, remaining);

        // Use requestAnimationFrame for smooth rendering
        requestAnimationFrame(() => {
            const fragment = document.createDocumentFragment();

            for (let i = 0; i < toLoad; i++) {
                // Task 1.3: Insert narrative carousel every 4 regular rows
                if (narrativeQueue.length > 0 && totalRowsRendered > 0 && totalRowsRendered % NARRATIVE_INTERVAL === 0) {
                    const narrative = narrativeQueue.shift();
                    const narrativeRow = createNarrativeRow(narrative, narrativePositionCounter);
                    narrativePositionCounter++;
                    fragment.appendChild(narrativeRow);
                }

                const cluster = shuffledClusters[loadedRowCount + i];
                const rowEl = createClusterRow(cluster);
                fragment.appendChild(rowEl);
                totalRowsRendered++;
            }

            // Task 1.3: Append any remaining narratives at the end
            if (loadedRowCount + toLoad >= shuffledClusters.length) {
                while (narrativeQueue.length > 0) {
                    const narrative = narrativeQueue.shift();
                    const narrativeRow = createNarrativeRow(narrative, narrativePositionCounter);
                    narrativePositionCounter++;
                    fragment.appendChild(narrativeRow);
                }
            }

            container.appendChild(fragment);
            loadedRowCount += toLoad;
            isLoading = false;

            // Hide loader if all loaded
            if (loadedRowCount >= shuffledClusters.length && narrativeQueue.length === 0) {
                document.getElementById('explore-loader').classList.remove('visible');
            }
        });
    }

    function createClusterRow(cluster) {
        const row = document.createElement('div');
        row.className = 'explore-row';
        row.dataset.clusterId = cluster.id;

        // Header - use creative_name if available, fallback to label
        const displayName = cluster.creative_name || cluster.label;
        const header = document.createElement('div');
        header.className = 'explore-row-header';
        header.innerHTML = `
            <h2 class="explore-row-title">${escapeHtml(displayName)}</h2>
            <span class="explore-row-count">${cluster.item_count} items</span>
        `;
        row.appendChild(header);

        // Scroller wrapper (for nav arrows)
        const wrapper = document.createElement('div');
        wrapper.className = 'explore-scroller-wrapper';

        // Scroller
        const scroller = document.createElement('div');
        scroller.className = 'explore-scroller';

        // Use pre-computed diverse selection if available (MMR-based)
        let displayItemIds;
        if (cluster.carousel_items && cluster.carousel_items.length > 0) {
            // Use MMR-computed diverse selection from build time
            displayItemIds = cluster.carousel_items.slice(0, ITEMS_PER_ROW);
        } else {
            // Fallback: legacy shuffle behavior for backwards compatibility
            const itemIds = getClusterItems(cluster.id);
            displayItemIds = shuffleArray(itemIds).slice(0, ITEMS_PER_ROW);
        }

        // Check if row is homogeneous (all same type) - hide badges if so
        const items = displayItemIds.map(id => itemLookup[id]).filter(Boolean);
        const types = new Set(items.map(i => i._type));
        const isHomogeneous = types.size === 1;

        // Sort items by model_score (highest engagement first)
        items.sort((a, b) => (b.model_score || 0) - (a.model_score || 0));

        // First item with high score becomes hero
        const hasHero = items.length > 0 && (items[0].model_score || 0) > 0.1;

        items.forEach((item, idx) => {
            const isHero = hasHero && idx === 0;
            const card = createExploreCard(item, isHomogeneous, isHero);
            scroller.appendChild(card);
        });

        wrapper.appendChild(scroller);

        // Navigation arrows
        const prevBtn = document.createElement('button');
        prevBtn.className = 'scroller-nav prev';
        prevBtn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg>';
        prevBtn.addEventListener('click', () => scrollRow(scroller, -1));

        const nextBtn = document.createElement('button');
        nextBtn.className = 'scroller-nav next';
        nextBtn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>';
        nextBtn.addEventListener('click', () => scrollRow(scroller, 1));

        wrapper.appendChild(prevBtn);
        wrapper.appendChild(nextBtn);

        row.appendChild(wrapper);

        // Mobile scroll indicator
        const scrollIndicator = document.createElement('div');
        scrollIndicator.className = 'scroll-indicator';
        scrollIndicator.innerHTML = '← Swipe →';
        row.appendChild(scrollIndicator);

        // Update nav button states on scroll
        scroller.addEventListener('scroll', () => updateNavButtons(scroller, prevBtn, nextBtn));
        // Initial state check after render
        setTimeout(() => updateNavButtons(scroller, prevBtn, nextBtn), 0);

        return row;
    }

    function getClusterItems(clusterId) {
        // Get all item IDs belonging to this cluster
        const items = [];
        for (const [itemId, cid] of Object.entries(clusterData.item_to_cluster)) {
            if (cid === clusterId) {
                items.push(itemId);
            }
        }
        return items;
    }

    // Task 1.1: Check if item is "New" (date_added within last 5 days)
    function isNewItem(item) {
        if (!item.date_added) return false;
        const dateAdded = new Date(item.date_added);
        const fiveDaysAgo = new Date();
        fiveDaysAgo.setDate(fiveDaysAgo.getDate() - 5);
        return dateAdded >= fiveDaysAgo;
    }

    // Task 1.1: Check if item is "Popular" (model_score > 0.7)
    function isPopularItem(item) {
        return (item.model_score || 0) > 0.7;
    }

    // Task 1.1: Get engagement badge HTML (New takes priority over Popular)
    function getEngagementBadge(item) {
        if (isNewItem(item)) {
            return '<span class="engagement-badge badge-new">New</span>';
        }
        if (isPopularItem(item)) {
            return '<span class="engagement-badge badge-popular">Popular</span>';
        }
        return '';
    }

    function createExploreCard(item, hideTypeBadge = false, isHero = false, isNarrativeHero = false) {
        const card = document.createElement('div');
        card.className = 'explore-card' + (isHero ? ' hero-card' : '');

        const type = item._type || 'resource';
        const name = item.name || item.title || 'Untitled';
        const url = item.url || '#';

        // Build description from best available source
        let description = '';
        if (item.summary && item.summary.length > 20) {
            description = item.summary;
        } else if (item.description && item.description.length > 10 &&
                   !item.description.toLowerCase().includes('career portal')) {
            description = item.description;
        } else if (item.category) {
            // For career items, show category instead of "Career portal"
            description = item.category;
        } else if (item.description) {
            description = item.description;
        }

        // Handle tags - could be array or comma-separated string
        let tags = [];
        if (item.topic_tags) {
            tags = typeof item.topic_tags === 'string'
                ? item.topic_tags.split(',').map(t => t.trim()).filter(t => t)
                : item.topic_tags;
        } else if (item.tags) {
            tags = Array.isArray(item.tags) ? item.tags : [];
        }

        // Format type label nicely
        const typeLabel = type.charAt(0).toUpperCase() + type.slice(1);

        // Task 1.1: Get engagement badge
        const badgeHtml = getEngagementBadge(item);

        // Task 1.2: Hero indicator for narrative carousels only
        const heroIndicatorHtml = isNarrativeHero ? '<div class="hero-indicator">★</div>' : '';

        // Task 1.2: Extra metadata for narrative heroes
        let heroMetadataHtml = '';
        if (isNarrativeHero && isHero) {
            const metadataRows = [];
            if (item.prerequisites) {
                metadataRows.push(`<div class="metadata-row"><span class="metadata-label">Prerequisites:</span> ${escapeHtml(truncate(item.prerequisites, 50))}</div>`);
            }
            if (item.best_for) {
                metadataRows.push(`<div class="metadata-row"><span class="metadata-label">Best for:</span> ${escapeHtml(truncate(item.best_for, 50))}</div>`);
            }
            if (item.related && Array.isArray(item.related) && item.related.length > 0) {
                metadataRows.push(`<div class="metadata-row"><span class="metadata-label">Related:</span> ${escapeHtml(item.related.slice(0, 2).join(', '))}</div>`);
            }
            if (metadataRows.length > 0) {
                heroMetadataHtml = `<div class="hero-metadata">${metadataRows.join('')}</div>`;
            }
        }

        // Adjust description length for narrative hero (show more)
        const descLength = isNarrativeHero && isHero ? 220 : 140;

        card.innerHTML = `
            ${badgeHtml}
            ${heroIndicatorHtml}
            ${!hideTypeBadge ? `<span class="explore-card-type type-${type}">${typeLabel}</span>` : ''}
            <h3 class="explore-card-title">
                <a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(name)}</a>
            </h3>
            <p class="explore-card-desc">${escapeHtml(truncate(description, descLength))}</p>
            ${tags.length > 0 && !heroMetadataHtml ? `
                <div class="explore-card-tags">
                    ${tags.slice(0, 3).map(t => `<span class="explore-card-tag">${escapeHtml(t)}</span>`).join('')}
                </div>
            ` : ''}
            ${heroMetadataHtml}
        `;

        // Make entire card clickable
        card.addEventListener('click', (e) => {
            if (e.target.tagName !== 'A') {
                window.open(url, '_blank');
            }
        });

        return card;
    }

    function truncate(str, len) {
        if (!str) return '';
        if (str.length <= len) return str;
        return str.slice(0, len).trim() + '...';
    }

    function scrollRow(scroller, direction) {
        const scrollAmount = 300 * direction;
        scroller.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }

    function updateNavButtons(scroller, prevBtn, nextBtn) {
        const atStart = scroller.scrollLeft <= 0;
        const atEnd = scroller.scrollLeft >= scroller.scrollWidth - scroller.clientWidth - 10;

        prevBtn.classList.toggle('disabled', atStart);
        nextBtn.classList.toggle('disabled', atEnd);
    }

    function setupLazyLoad() {
        // Intersection Observer for infinite scroll
        const loader = document.getElementById('explore-loader');
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !isLoading) {
                loadMoreRows();
            }
        }, { rootMargin: '300px' });

        observer.observe(loader);
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
})();
