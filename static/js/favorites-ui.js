// Favorites UI for Tech-Econ
// Heart button interactions and favorites page

(function() {
    'use strict';

    // Add favorite buttons to all cards
    function initFavoriteButtons() {
        document.querySelectorAll('.card, .resource-card, .package-card, .dataset-card, .talk-card').forEach(card => {
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

            // Handle click
            btn.addEventListener('click', async function(e) {
                e.preventDefault();
                e.stopPropagation();

                if (!window.TechEconAuth || !window.TechEconAuth.isLoggedIn()) {
                    window.TechEconAuth.showModal();
                    return;
                }

                try {
                    const isFav = await window.TechEconFavorites.toggle(itemType, itemId);
                    btn.classList.toggle('favorited', isFav);
                    btn.setAttribute('aria-pressed', isFav);
                    showToast(isFav ? 'Added to favorites' : 'Removed from favorites');
                } catch (err) {
                    console.error('Favorite error:', err);
                    showToast('Error updating favorite', 'error');
                }
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

        async function loadFavorites() {
            container.innerHTML = '<div class="loading">Loading favorites...</div>';

            if (!window.TechEconAuth || !window.TechEconAuth.isLoggedIn()) {
                container.innerHTML = `
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                        </svg>
                        <h3>Sign in to see your favorites</h3>
                        <p>Create an account to save resources, packages, and datasets</p>
                        <button class="btn btn-primary" onclick="TechEconAuth.showModal()">Sign In</button>
                    </div>
                `;
                return;
            }

            try {
                const favorites = await window.TechEconFavorites.getAll();

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
                    if (!grouped[f.item_type]) grouped[f.item_type] = [];
                    grouped[f.item_type].push(f);
                });

                let html = '';
                const typeLabels = {
                    resource: 'Learning Resources',
                    package: 'Packages',
                    dataset: 'Datasets',
                    talk: 'Talks'
                };

                Object.keys(grouped).forEach(type => {
                    html += `<h3 class="favorites-section-title">${typeLabels[type] || type}</h3>`;
                    html += '<div class="favorites-grid">';
                    grouped[type].forEach(fav => {
                        html += `
                            <div class="favorite-item" data-type="${fav.item_type}" data-id="${fav.item_id}">
                                <span class="favorite-item-name">${fav.item_id}</span>
                                <button class="favorite-remove" onclick="removeFavorite('${fav.item_type}', '${fav.item_id.replace(/'/g, "\\'")}')">
                                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                        <line x1="18" y1="6" x2="6" y2="18"></line>
                                        <line x1="6" y1="6" x2="18" y2="18"></line>
                                    </svg>
                                </button>
                            </div>
                        `;
                    });
                    html += '</div>';
                });

                container.innerHTML = html;
            } catch (err) {
                console.error('Error loading favorites:', err);
                container.innerHTML = '<div class="error">Error loading favorites</div>';
            }
        }

        // Remove favorite function
        window.removeFavorite = async function(type, id) {
            try {
                await window.TechEconFavorites.remove(type, id);
                showToast('Removed from favorites');
                loadFavorites();
            } catch (err) {
                showToast('Error removing favorite', 'error');
            }
        };

        // Load on page load and auth change
        loadFavorites();

        // Re-load when auth state changes
        const checkAuth = setInterval(() => {
            if (window.TechEconAuth) {
                clearInterval(checkAuth);
                // Already loaded above, but will reload on auth change via supabase-client
            }
        }, 100);
    }

    // Initialize when DOM is ready
    function init() {
        // Delay to ensure supabase-client is loaded
        setTimeout(() => {
            initFavoriteButtons();
            initFavoritesPage();
        }, 100);

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
