// Favorites UI for Tech-Econ
// Heart button interactions, favorites page, and playlists - LocalStorage based

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
        console.log('[Favorites] initFavoritesPage called');
        const container = document.getElementById('favorites-list');
        console.log('[Favorites] Container found:', !!container);
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
        function renderFavoriteCard(fav, item) {
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
            console.log('[Favorites] loadFavorites called');
            try {
                if (!window.TechEconFavorites) {
                    container.innerHTML = '<div class="error">Favorites module not loaded</div>';
                    return;
                }

                const favorites = window.TechEconFavorites.get();
                console.log('[Favorites] Got', favorites.length, 'favorites');

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
                    <span class="favorites-count-label">${favorites.length} saved items</span>
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
                    html += renderFavoriteCard(fav, item);
                });
                html += '</div>';
            });

                container.innerHTML = html;
                console.log('[Favorites] Rendered successfully');
            } catch (e) {
                console.error('[Favorites] Error:', e);
                container.innerHTML = '<div class="error">Error loading favorites: ' + e.message + '</div>';
            }
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

        // Load immediately
        loadFavorites();

        // Initialize tabs if present
        initTabs(loadFavorites);
    }

    // Tab switching functionality
    function initTabs(reloadFavorites) {
        const tabBtns = document.querySelectorAll('.tab-btn');
        const favoritesTab = document.getElementById('favorites-tab');
        const playlistsTab = document.getElementById('playlists-tab');

        if (!tabBtns.length || !favoritesTab || !playlistsTab) return;

        tabBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const tab = this.dataset.tab;

                // Update active states
                tabBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');

                // Show/hide tabs
                if (tab === 'favorites') {
                    favoritesTab.style.display = 'block';
                    playlistsTab.style.display = 'none';
                    reloadFavorites();
                } else {
                    favoritesTab.style.display = 'none';
                    playlistsTab.style.display = 'block';
                    loadPlaylists();
                }
            });
        });

        // Initialize playlists UI
        initPlaylistsUI();
    }

    // Playlists functionality
    function initPlaylistsUI() {
        const container = document.getElementById('playlists-list');
        if (!container) return;

        let currentPlaylistId = null;

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

        // Render playlists grid
        window.loadPlaylists = function() {
            if (!window.TechEconPlaylists) {
                container.innerHTML = '<div class="error">Playlists module not loaded</div>';
                return;
            }

            const playlists = window.TechEconPlaylists.getAll();

            // Action bar
            let html = `
                <div class="playlists-actions">
                    <div class="action-buttons">
                        <button class="btn btn-primary" id="create-playlist-trigger">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="12" y1="5" x2="12" y2="19"></line>
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                            </svg>
                            Create Playlist
                        </button>
                        <button class="btn btn-outline" id="import-playlist-trigger">
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                <polyline points="17 8 12 3 7 8"/>
                                <line x1="12" y1="3" x2="12" y2="15"/>
                            </svg>
                            Import CSV
                        </button>
                    </div>
                </div>
            `;

            if (playlists.length === 0) {
                html += `
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                            <line x1="8" y1="6" x2="21" y2="6"></line>
                            <line x1="8" y1="12" x2="21" y2="12"></line>
                            <line x1="8" y1="18" x2="21" y2="18"></line>
                            <line x1="3" y1="6" x2="3.01" y2="6"></line>
                            <line x1="3" y1="12" x2="3.01" y2="12"></line>
                            <line x1="3" y1="18" x2="3.01" y2="18"></line>
                        </svg>
                        <h3>No playlists yet</h3>
                        <p>Create a playlist to organize your favorite resources</p>
                    </div>
                `;
            } else {
                html += '<div class="playlists-grid">';
                playlists.forEach(playlist => {
                    const date = new Date(playlist.createdAt).toLocaleDateString();
                    html += `
                        <div class="playlist-card" data-playlist-id="${playlist.id}">
                            <div class="playlist-card-header">
                                <h3 class="playlist-name">${escapeHtml(playlist.name)}</h3>
                                <span class="playlist-count">${playlist.items.length} items</span>
                            </div>
                            <div class="playlist-card-meta">
                                Created ${date}
                            </div>
                            <div class="playlist-card-actions">
                                <button class="btn btn-sm btn-outline playlist-view" data-id="${playlist.id}">
                                    View
                                </button>
                                <button class="btn btn-sm btn-outline playlist-export" data-id="${playlist.id}">
                                    Export
                                </button>
                                <button class="btn btn-sm btn-outline playlist-delete" data-id="${playlist.id}">
                                    Delete
                                </button>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            }

            container.innerHTML = html;

            // Attach event listeners
            attachPlaylistListeners();
        };

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function attachPlaylistListeners() {
            // Create playlist trigger
            const createTrigger = document.getElementById('create-playlist-trigger');
            if (createTrigger) {
                createTrigger.addEventListener('click', showCreateModal);
            }

            // Import trigger
            const importTrigger = document.getElementById('import-playlist-trigger');
            if (importTrigger) {
                importTrigger.addEventListener('click', function() {
                    document.getElementById('csv-import-input').click();
                });
            }

            // View buttons
            document.querySelectorAll('.playlist-view').forEach(btn => {
                btn.addEventListener('click', function() {
                    showPlaylistDetail(this.dataset.id);
                });
            });

            // Export buttons
            document.querySelectorAll('.playlist-export').forEach(btn => {
                btn.addEventListener('click', function() {
                    window.TechEconPlaylists.exportCSV(this.dataset.id);
                    showToast('Playlist exported');
                });
            });

            // Delete buttons
            document.querySelectorAll('.playlist-delete').forEach(btn => {
                btn.addEventListener('click', function() {
                    if (confirm('Delete this playlist?')) {
                        window.TechEconPlaylists.delete(this.dataset.id);
                        showToast('Playlist deleted');
                        loadPlaylists();
                    }
                });
            });
        }

        // Create playlist modal
        function showCreateModal() {
            const modal = document.getElementById('create-playlist-modal');
            const input = document.getElementById('playlist-name-input');
            modal.style.display = 'flex';
            input.value = '';
            input.focus();
        }

        function hideCreateModal() {
            document.getElementById('create-playlist-modal').style.display = 'none';
        }

        // Create modal event listeners
        const createModal = document.getElementById('create-playlist-modal');
        if (createModal) {
            const backdrop = createModal.querySelector('.modal-backdrop');
            const cancelBtn = document.getElementById('cancel-playlist-btn');
            const createBtn = document.getElementById('create-playlist-btn');
            const input = document.getElementById('playlist-name-input');

            backdrop.addEventListener('click', hideCreateModal);
            cancelBtn.addEventListener('click', hideCreateModal);

            createBtn.addEventListener('click', function() {
                const name = input.value.trim();
                if (name) {
                    window.TechEconPlaylists.create(name);
                    showToast('Playlist created');
                    hideCreateModal();
                    loadPlaylists();
                }
            });

            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    createBtn.click();
                }
            });
        }

        // Playlist detail modal
        function showPlaylistDetail(playlistId) {
            currentPlaylistId = playlistId;
            const modal = document.getElementById('playlist-detail-modal');
            const playlist = window.TechEconPlaylists.get(playlistId);

            if (!playlist) return;

            document.getElementById('playlist-detail-title').textContent = playlist.name;

            const itemsContainer = document.getElementById('playlist-detail-items');

            if (playlist.items.length === 0) {
                itemsContainer.innerHTML = `
                    <div class="empty-state-small">
                        <p>This playlist is empty</p>
                        <p class="text-muted">Add items from your favorites or import a CSV</p>
                    </div>
                `;
            } else {
                let html = '<div class="playlist-items-list">';
                playlist.items.forEach(item => {
                    const dbItem = findItem(item.type, item.id);
                    const name = dbItem?.name || dbItem?.title || item.data?.name || item.id;
                    const url = dbItem?.url || dbItem?.link || item.data?.url || '#';
                    const favicon = getFavicon(url);

                    html += `
                        <div class="playlist-item">
                            ${favicon ? `<img class="resource-favicon" src="${favicon}" alt="" loading="lazy" onerror="this.style.display='none'">` : ''}
                            <div class="playlist-item-info">
                                <a href="${url}" target="_blank" rel="noopener">${escapeHtml(name)}</a>
                                <span class="type-badge type-${item.type}">${item.type}</span>
                            </div>
                            <button class="playlist-item-remove" data-type="${item.type}" data-id="${escapeHtml(item.id)}">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            </button>
                        </div>
                    `;
                });
                html += '</div>';
                itemsContainer.innerHTML = html;

                // Attach remove listeners
                itemsContainer.querySelectorAll('.playlist-item-remove').forEach(btn => {
                    btn.addEventListener('click', function() {
                        window.TechEconPlaylists.removeItem(currentPlaylistId, this.dataset.type, this.dataset.id);
                        showPlaylistDetail(currentPlaylistId);
                        showToast('Item removed from playlist');
                    });
                });
            }

            modal.style.display = 'flex';
        }

        function hideDetailModal() {
            document.getElementById('playlist-detail-modal').style.display = 'none';
            currentPlaylistId = null;
        }

        // Detail modal event listeners
        const detailModal = document.getElementById('playlist-detail-modal');
        if (detailModal) {
            const backdrop = detailModal.querySelector('.modal-backdrop');
            const closeBtn = document.getElementById('close-playlist-detail');
            const exportBtn = document.getElementById('export-playlist-btn');

            backdrop.addEventListener('click', hideDetailModal);
            closeBtn.addEventListener('click', hideDetailModal);

            exportBtn.addEventListener('click', function() {
                if (currentPlaylistId) {
                    window.TechEconPlaylists.exportCSV(currentPlaylistId);
                    showToast('Playlist exported');
                }
            });
        }

        // CSV import handler
        const importInput = document.getElementById('csv-import-input');
        if (importInput) {
            importInput.addEventListener('change', async function(e) {
                const file = e.target.files[0];
                if (!file) return;

                try {
                    const result = await window.TechEconPlaylists.importCSV(file);
                    showToast(`Imported "${result.playlistName}" with ${result.itemCount} items`);
                    loadPlaylists();
                } catch (err) {
                    showToast('Error importing CSV: ' + err.message, 'error');
                }

                // Reset input
                importInput.value = '';
            });
        }
    }

    // Initialize when DOM is ready
    function init() {
        console.log('[Favorites] init() called');
        let retryCount = 0;
        const maxRetries = 30; // 3 seconds max wait

        function tryInit() {
            console.log('[Favorites] tryInit() attempt', retryCount, 'TechEconFavorites:', !!window.TechEconFavorites);
            // Only require favorites module - playlists is optional
            if (!window.TechEconFavorites) {
                retryCount++;
                if (retryCount < maxRetries) {
                    setTimeout(tryInit, 100);
                } else {
                    console.error('[Favorites] Module failed to load after timeout');
                    const container = document.getElementById('favorites-list');
                    if (container) {
                        container.innerHTML = '<div class="error">Failed to load favorites. Please refresh the page.</div>';
                    }
                }
                return;
            }

            console.log('[Favorites] Calling initFavoriteButtons and initFavoritesPage');
            initFavoriteButtons();
            initFavoritesPage();

            // Re-run when new content is added (for infinite scroll, etc)
            const observer = new MutationObserver(() => {
                initFavoriteButtons();
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }

        tryInit();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
