// Favorites UI for Tech-Econ
// Heart button interactions and favorites page - LocalStorage based

(function() {
    'use strict';

    // Simple toast notification
    function showToast(message, type) {
        const existing = document.querySelector('.toast-notification');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = 'toast-notification' + (type === 'error' ? ' toast-error' : '');
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 2500);
    }

    // Add favorite buttons to all cards
    function initFavoriteButtons() {
        document.querySelectorAll('.card, .resource-card, .package-card, .dataset-card, .talk-card, .paper-card, .roadmap-card').forEach(card => {
            // Skip if already has button
            if (card.querySelector('[data-favorite-btn]')) return;

            // Determine item type from card class or data attribute
            let itemType = 'resource';
            if (card.classList.contains('package-card') || card.closest('.packages-section')) {
                itemType = 'package';
            } else if (card.classList.contains('dataset-card') || card.closest('.datasets-section')) {
                itemType = 'dataset';
            } else if (card.classList.contains('talk-card') || card.closest('.talks-section')) {
                itemType = 'talk';
            } else if (card.classList.contains('paper-card')) {
                itemType = 'paper';
            } else if (card.classList.contains('roadmap-card')) {
                itemType = 'roadmap';
            }

            // Get item ID from data attribute or link
            let itemId = card.dataset.itemId;
            if (!itemId) {
                const link = card.querySelector('a[href]');
                if (link) {
                    itemId = link.textContent.trim() || link.href;
                }
                const title = card.querySelector('.card-title, h3, h4');
                if (title) {
                    itemId = title.textContent.trim();
                }
            }

            if (!itemId) return;

            // Get item data for storage
            const itemData = {
                name: itemId,
                url: card.querySelector('a[href]')?.href || '',
                category: itemType
            };
            const desc = card.querySelector('.card-desc, .description, p');
            if (desc) itemData.description = desc.textContent.trim().substring(0, 200);

            // Create favorite button
            const btn = document.createElement('button');
            btn.className = 'favorite-btn';
            btn.setAttribute('data-favorite-btn', '');
            btn.setAttribute('data-item-type', itemType);
            btn.setAttribute('data-item-id', itemId);
            btn.setAttribute('aria-label', 'Add to favorites');
            btn.setAttribute('aria-pressed', 'false');
            btn.innerHTML = `
                <svg class="heart-outline" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                </svg>
                <svg class="heart-filled" viewBox="0 0 24 24" width="18" height="18" fill="currentColor" stroke="none">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                </svg>
            `;

            // Position button
            const cardHeader = card.querySelector('.card-header');
            if (cardHeader) {
                cardHeader.style.position = 'relative';
                cardHeader.appendChild(btn);
            } else {
                card.style.position = 'relative';
                card.appendChild(btn);
            }

            // Handle click - no auth needed!
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                if (!window.TechEconFavorites) {
                    console.error('Favorites module not loaded');
                    return;
                }

                const isFav = window.TechEconFavorites.toggle(itemType, itemId, itemData);
                btn.classList.toggle('favorited', isFav);
                btn.setAttribute('aria-pressed', isFav);
                showToast(isFav ? 'Added to favorites' : 'Removed from favorites');
            });

            // Check initial state
            if (window.TechEconFavorites && window.TechEconFavorites.isFavorited(itemType, itemId)) {
                btn.classList.add('favorited');
                btn.setAttribute('aria-pressed', 'true');
            }
        });
    }

    // Initialize favorites page if on that page
    function initFavoritesPage() {
        const container = document.getElementById('favorites-list');
        if (!container) return;

        // Load all data for lookups
        let allData = {};
        const dataScript = document.getElementById('all-data');
        if (dataScript) {
            try {
                allData = JSON.parse(dataScript.textContent);
            } catch (e) {
                console.error('Error parsing all-data:', e);
            }
        }

        // Find item in data by name
        function findItem(type, itemId) {
            // Papers have a nested structure: topics > subtopics > papers
            if (type === 'paper') {
                const topics = allData.paper?.topics || [];
                for (const topic of topics) {
                    for (const subtopic of (topic.subtopics || [])) {
                        const paper = (subtopic.papers || []).find(p => p.title === itemId);
                        if (paper) return paper;
                    }
                }
                return null;
            }
            const items = allData[type] || [];
            return items.find(item => item.name === itemId || item.title === itemId);
        }

        // Get favicon URL from item URL
        function getFavicon(url) {
            if (!url) return '';
            try {
                const domain = new URL(url).hostname;
                return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
            } catch {
                return '';
            }
        }

        // Render a single favorite card
        function renderCard(fav, item) {
            const name = item?.name || item?.title || fav.data?.name || fav.id;
            const desc = item?.description || fav.data?.description || '';
            const url = item?.url || item?.link || fav.data?.url || '#';
            const category = item?.category || item?.type || fav.data?.category || fav.type;
            const favicon = getFavicon(url);
            const escapedId = fav.id.replace(/'/g, "\\'").replace(/"/g, '&quot;');

            return `
                <div class="favorite-card" data-type="${fav.type}" data-id="${fav.id}">
                    <div class="card-header">
                        ${favicon ? `<img class="resource-favicon" src="${favicon}" alt="" loading="lazy" onerror="this.style.display='none'">` : ''}
                        <h3 class="card-title">
                            <a href="${url}" target="_blank" rel="noopener">${name}</a>
                        </h3>
                        <span class="type-badge type-${fav.type}">${fav.type}</span>
                    </div>
                    ${desc ? `<p class="card-desc">${desc}</p>` : ''}
                    <div class="card-footer">
                        <span class="category-badge">${category}</span>
                        <button class="favorite-remove" onclick="removeFavorite('${fav.type}', '${escapedId}')">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
            `;
        }

        function loadFavorites() {
            if (!window.TechEconFavorites) {
                container.innerHTML = '<div class="error">Favorites module not loaded</div>';
                return;
            }

            const favorites = window.TechEconFavorites.get();

            if (favorites.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                        </svg>
                        <h3>No favorites yet</h3>
                        <p>Click the heart icon on any resource to save it here</p>
                        <a href="/learning/" class="btn btn-primary">Browse Resources</a>
                    </div>
                `;
                return;
            }

            // Group by type
            const grouped = {};
            favorites.forEach(f => {
                if (!grouped[f.type]) grouped[f.type] = [];
                grouped[f.type].push(f);
            });

            const typeLabels = {
                resource: 'Learning Resources',
                package: 'Packages',
                dataset: 'Datasets',
                talk: 'Talks',
                book: 'Books',
                career: 'Career Resources',
                community: 'Community',
                paper: 'Papers',
                roadmap: 'Learning Paths'
            };

            // Export buttons
            let html = `
                <div class="favorites-actions">
                    <span class="favorites-count">${favorites.length} saved items</span>
                    <div class="export-buttons">
                        <button class="btn btn-outline btn-sm" onclick="TechEconFavorites.exportJSON()">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            Download JSON
                        </button>
                        <button class="btn btn-outline btn-sm" onclick="TechEconFavorites.exportCSV()">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                            Download CSV
                        </button>
                    </div>
                </div>
            `;

            Object.keys(grouped).forEach(type => {
                html += `<h3 class="favorites-section-title">${typeLabels[type] || type}</h3>`;
                html += '<div class="favorites-grid">';
                grouped[type].forEach(fav => {
                    const item = findItem(type, fav.id);
                    html += renderCard(fav, item);
                });
                html += '</div>';
            });

            container.innerHTML = html;
        }

        // Remove favorite function
        window.removeFavorite = function(type, id) {
            if (window.TechEconFavorites) {
                window.TechEconFavorites.remove(type, id);
                showToast('Removed from favorites');
                loadFavorites();
            }
        };

        // Expose loadFavorites for external trigger
        window.reloadFavoritesPage = loadFavorites;

        // Load immediately - no auth wait needed!
        loadFavorites();
    }

    // Initialize when DOM is ready
    function init() {
        initFavoriteButtons();
        initFavoritesPage();

        // Re-run when new content is added (for infinite scroll, etc)
        const observer = new MutationObserver(() => {
            initFavoriteButtons();
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
