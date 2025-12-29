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

    // Current item being added to playlist
    let currentPlaylistItem = null;

    // Show "Add to Playlist" modal
    function showAddToPlaylistModal(itemType, itemId, itemData) {
        if (!window.TechEconPlaylists) {
            showToast('Playlists not available', 'error');
            return;
        }

        currentPlaylistItem = { type: itemType, id: itemId, data: itemData };

        const modal = document.getElementById('add-to-playlist-modal');
        const optionsContainer = document.getElementById('playlist-options');

        if (!modal || !optionsContainer) {
            // Modal not on this page, create it dynamically
            createAddToPlaylistModal();
            return showAddToPlaylistModal(itemType, itemId, itemData);
        }

        const playlists = window.TechEconPlaylists.getAll();

        if (playlists.length === 0) {
            optionsContainer.innerHTML = `
                <div class="empty-state-small">
                    <p>No playlists yet</p>
                    <p class="text-muted">Create one to get started</p>
                </div>
            `;
        } else {
            let html = '';
            playlists.forEach(playlist => {
                const hasItem = playlist.items.some(item =>
                    item.type === itemType && item.id === itemId
                );
                html += `
                    <div class="playlist-option ${hasItem ? 'already-added' : ''}"
                         data-playlist-id="${playlist.id}">
                        <span class="playlist-option-name">${escapeHtml(playlist.name)}</span>
                        <span class="playlist-option-count">${playlist.items.length} items</span>
                        ${hasItem ? '<span class="playlist-option-check">✓</span>' : ''}
                    </div>
                `;
            });
            optionsContainer.innerHTML = html;

            // Add click handlers
            optionsContainer.querySelectorAll('.playlist-option:not(.already-added)').forEach(opt => {
                opt.addEventListener('click', function() {
                    const playlistId = this.dataset.playlistId;
                    if (currentPlaylistItem) {
                        window.TechEconPlaylists.addItem(
                            playlistId,
                            currentPlaylistItem.type,
                            currentPlaylistItem.id,
                            currentPlaylistItem.data
                        );
                        showToast('Added to playlist');
                        hideAddToPlaylistModal();
                    }
                });
            });
        }

        modal.style.display = 'flex';
    }

    // Hide "Add to Playlist" modal
    function hideAddToPlaylistModal() {
        const modal = document.getElementById('add-to-playlist-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        currentPlaylistItem = null;
    }

    // Create modal dynamically for pages that don't have it
    function createAddToPlaylistModal() {
        if (document.getElementById('add-to-playlist-modal')) return;

        const modal = document.createElement('div');
        modal.id = 'add-to-playlist-modal';
        modal.className = 'modal';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="modal-backdrop"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Add to Playlist</h3>
                    <button class="modal-close" id="close-add-playlist-modal">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
                <div id="playlist-options" class="playlist-options-list"></div>
                <div class="modal-actions">
                    <button class="btn btn-outline" id="create-and-add-btn">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="12" y1="5" x2="12" y2="19"></line>
                            <line x1="5" y1="12" x2="19" y2="12"></line>
                        </svg>
                        Create New Playlist
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        initAddToPlaylistModal();
    }

    // Initialize modal event handlers
    function initAddToPlaylistModal() {
        const modal = document.getElementById('add-to-playlist-modal');
        if (!modal) return;

        const backdrop = modal.querySelector('.modal-backdrop');
        const closeBtn = document.getElementById('close-add-playlist-modal');
        const createBtn = document.getElementById('create-and-add-btn');

        if (backdrop) backdrop.addEventListener('click', hideAddToPlaylistModal);
        if (closeBtn) closeBtn.addEventListener('click', hideAddToPlaylistModal);

        if (createBtn) {
            createBtn.addEventListener('click', function() {
                // Store pending item to add after playlist creation
                window._pendingPlaylistItem = currentPlaylistItem;
                hideAddToPlaylistModal();
                // Show the proper create playlist modal
                if (window.showCreatePlaylistModal) {
                    window.showCreatePlaylistModal();
                }
            });
        }
    }

    // Helper to escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Expose globally for use from anywhere
    window.showAddToPlaylistModal = showAddToPlaylistModal;

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
            let pressTimer;
            let longPressed = false;

            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                // If long press just happened, don't toggle favorite
                if (longPressed) {
                    longPressed = false;
                    return;
                }

                if (!window.TechEconFavorites) {
                    console.error('Favorites module not loaded');
                    return;
                }

                const isFav = window.TechEconFavorites.toggle(itemType, itemId, itemData);
                btn.classList.toggle('favorited', isFav);
                btn.setAttribute('aria-pressed', isFav);
                showToast(isFav ? 'Added to favorites' : 'Removed from favorites');
            });

            // Long press to add to playlist (mouse)
            btn.addEventListener('mousedown', function(e) {
                pressTimer = setTimeout(() => {
                    longPressed = true;
                    showAddToPlaylistModal(itemType, itemId, itemData);
                }, 500);
            });
            btn.addEventListener('mouseup', () => clearTimeout(pressTimer));
            btn.addEventListener('mouseleave', () => clearTimeout(pressTimer));

            // Long press to add to playlist (touch)
            btn.addEventListener('touchstart', function(e) {
                pressTimer = setTimeout(() => {
                    longPressed = true;
                    e.preventDefault();
                    showAddToPlaylistModal(itemType, itemId, itemData);
                }, 500);
            }, { passive: false });
            btn.addEventListener('touchend', () => clearTimeout(pressTimer));
            btn.addEventListener('touchcancel', () => clearTimeout(pressTimer));

            // Check initial state
            if (window.TechEconFavorites && window.TechEconFavorites.isFavorited(itemType, itemId)) {
                btn.classList.add('favorited');
                btn.setAttribute('aria-pressed', 'true');
            }
        });
    }

    // Initialize collection page (merged favorites + playlists)
    function initCollectionPage() {
        console.log('[Collection] initCollectionPage called');
        const container = document.getElementById('collection-container');
        console.log('[Collection] Container found:', !!container);
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

        // Render a single favorite card with move-to-playlist option
        function renderCollectionCard(fav, item, playlistId) {
            const name = item?.name || item?.title || fav.data?.name || fav.id;
            const desc = item?.description || fav.data?.description || '';
            const url = item?.url || item?.link || fav.data?.url || '#';
            const category = item?.category || item?.type || fav.data?.category || fav.type;
            const favicon = getFavicon(url);
            const escapedId = fav.id.replace(/'/g, "\\'").replace(/"/g, '&quot;');
            const escapedPlaylistId = playlistId ? playlistId.replace(/'/g, "\\'") : '';

            return `
                <div class="favorite-card" data-type="${fav.type}" data-id="${fav.id}" data-playlist="${playlistId || ''}">
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
                        <div class="card-actions">
                            <button class="move-to-playlist-btn" title="Move to playlist" data-type="${fav.type}" data-id="${escapedId}" data-current-playlist="${escapedPlaylistId}">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M5 12h14M12 5l7 7-7 7"/>
                                </svg>
                            </button>
                            <button class="favorite-remove" onclick="removeFromCollection('${fav.type}', '${escapedId}', '${escapedPlaylistId}')">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }

        // Render a table row for an item
        function renderCollectionRow(fav, item, playlistId) {
            const name = item?.name || item?.title || fav.data?.name || fav.id;
            const desc = item?.description || fav.data?.description || '';
            const url = item?.url || item?.link || fav.data?.url || '#';
            const category = item?.category || item?.type || fav.data?.category || fav.type;
            const favicon = getFavicon(url);
            const escapedId = fav.id.replace(/'/g, "\\'").replace(/"/g, '&quot;');
            const escapedPlaylistId = playlistId ? playlistId.replace(/'/g, "\\'") : '';

            return `
                <tr class="collection-row" data-type="${fav.type}" data-id="${fav.id}">
                    <td class="col-name">
                        ${favicon ? `<img class="resource-favicon-sm" src="${favicon}" alt="" loading="lazy" onerror="this.style.display='none'">` : ''}
                        <a href="${url}" target="_blank" rel="noopener">${name}</a>
                    </td>
                    <td class="col-type"><span class="type-badge type-${fav.type}">${fav.type}</span></td>
                    <td class="col-category">${category}</td>
                    <td class="col-actions">
                        <button class="btn-icon-sm move-to-playlist-btn" title="Move to playlist" data-type="${fav.type}" data-id="${escapedId}" data-current-playlist="${escapedPlaylistId}">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M5 12h14M12 5l7 7-7 7"/>
                            </svg>
                        </button>
                        <button class="btn-icon-sm btn-danger" onclick="removeFromCollection('${fav.type}', '${escapedId}', '${escapedPlaylistId}')" title="Remove">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </td>
                </tr>
            `;
        }

        // Render a playlist section
        function renderPlaylistSection(playlist, items, isExpanded, viewMode) {
            const itemCount = items.length;
            const escapedId = playlist.id.replace(/'/g, "\\'");

            let itemsHtml = '';
            if (viewMode === 'table') {
                // Table view
                if (items.length > 0) {
                    itemsHtml = `
                        <table class="collection-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Type</th>
                                    <th>Category</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                    `;
                    items.forEach(item => {
                        const fav = { type: item.type, id: item.id, data: item.data };
                        const fullItem = findItem(item.type, item.id);
                        itemsHtml += renderCollectionRow(fav, fullItem, playlist.id);
                    });
                    itemsHtml += '</tbody></table>';
                }
            } else {
                // Card view (default)
                items.forEach(item => {
                    const fav = { type: item.type, id: item.id, data: item.data };
                    const fullItem = findItem(item.type, item.id);
                    itemsHtml += renderCollectionCard(fav, fullItem, playlist.id);
                });
            }

            const contentClass = viewMode === 'table' ? 'table-view' : 'favorites-grid';

            return `
                <div class="playlist-section ${isExpanded ? 'expanded' : ''}" data-playlist-id="${playlist.id}">
                    <div class="playlist-section-header" onclick="togglePlaylistSection('${escapedId}')">
                        <div class="playlist-section-info">
                            <svg class="playlist-chevron" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="9 18 15 12 9 6"></polyline>
                            </svg>
                            <span class="playlist-section-name">${escapeHtml(playlist.name)}</span>
                            <span class="playlist-section-count">${itemCount} item${itemCount !== 1 ? 's' : ''}</span>
                        </div>
                        <div class="playlist-section-actions">
                            <button class="btn-icon" onclick="event.stopPropagation(); renamePlaylist('${escapedId}')" title="Rename">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </button>
                            <button class="btn-icon btn-danger" onclick="event.stopPropagation(); deletePlaylist('${escapedId}')" title="Delete playlist">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3 6 5 6 21 6"></polyline>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="playlist-section-content">
                        <div class="${contentClass}">
                            ${itemsHtml || '<p class="empty-playlist">No items in this playlist</p>'}
                        </div>
                    </div>
                </div>
            `;
        }

        function loadCollection() {
            console.log('[Collection] loadCollection called');
            try {
                if (!window.TechEconFavorites) {
                    container.innerHTML = '<div class="error">Favorites module not loaded</div>';
                    return;
                }

                const favorites = window.TechEconFavorites.get();
                const playlists = window.TechEconPlaylists ? window.TechEconPlaylists.getAll() : [];

                console.log('[Collection] Got', favorites.length, 'favorites and', playlists.length, 'playlists');

                if (favorites.length === 0 && playlists.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
                                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                            </svg>
                            <h3>Your collection is empty</h3>
                            <p>Click the heart icon on any resource to save it here</p>
                            <a href="/learning/" class="btn btn-primary">Browse Resources</a>
                        </div>
                    `;
                    return;
                }

                // Track which favorites are in playlists
                const favoritesInPlaylists = new Set();
                playlists.forEach(playlist => {
                    playlist.items.forEach(item => {
                        favoritesInPlaylists.add(`${item.type}:${item.id}`);
                    });
                });

                // Find uncategorized favorites (not in any playlist)
                const uncategorized = favorites.filter(fav =>
                    !favoritesInPlaylists.has(`${fav.type}:${fav.id}`)
                );

                // Get current view preference
                const currentView = localStorage.getItem('collectionView') || 'cards';

                // Build HTML
                let html = `
                    <div class="collection-actions">
                        <span class="collection-count-label">${favorites.length} saved item${favorites.length !== 1 ? 's' : ''}</span>
                        <div class="action-buttons">
                            <div class="view-toggle">
                                <button class="view-toggle-btn ${currentView === 'cards' ? 'active' : ''}" onclick="setCollectionView('cards')" title="Card view">
                                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                                        <rect x="3" y="3" width="7" height="7"></rect>
                                        <rect x="14" y="3" width="7" height="7"></rect>
                                        <rect x="3" y="14" width="7" height="7"></rect>
                                        <rect x="14" y="14" width="7" height="7"></rect>
                                    </svg>
                                </button>
                                <button class="view-toggle-btn ${currentView === 'table' ? 'active' : ''}" onclick="setCollectionView('table')" title="Table view">
                                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                                        <line x1="3" y1="6" x2="21" y2="6"></line>
                                        <line x1="3" y1="12" x2="21" y2="12"></line>
                                        <line x1="3" y1="18" x2="21" y2="18"></line>
                                    </svg>
                                </button>
                            </div>
                            <button class="btn btn-primary btn-sm" onclick="showCreatePlaylistModal()">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="12" y1="5" x2="12" y2="19"></line>
                                    <line x1="5" y1="12" x2="19" y2="12"></line>
                                </svg>
                                New Playlist
                            </button>
                            <button class="btn btn-outline btn-sm" onclick="TechEconFavorites.exportJSON()">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="7 10 12 15 17 10"/>
                                    <line x1="12" y1="15" x2="12" y2="3"/>
                                </svg>
                                Export
                            </button>
                        </div>
                    </div>
                `;

                // Render each playlist as a collapsible section
                playlists.forEach((playlist, index) => {
                    html += renderPlaylistSection(playlist, playlist.items, index === 0, currentView);
                });

                // Render uncategorized section
                if (uncategorized.length > 0) {
                    const uncategorizedPlaylist = {
                        id: '__uncategorized__',
                        name: 'Uncategorized',
                        items: uncategorized.map(f => ({ type: f.type, id: f.id, data: f.data }))
                    };
                    html += renderPlaylistSection(uncategorizedPlaylist, uncategorizedPlaylist.items, playlists.length === 0, currentView);
                }

                container.innerHTML = html;

                // Add event listeners for move-to-playlist buttons
                container.querySelectorAll('.move-to-playlist-btn').forEach(btn => {
                    btn.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        const type = this.dataset.type;
                        const id = this.dataset.id;
                        const currentPlaylist = this.dataset.currentPlaylist;
                        const card = this.closest('.favorite-card');
                        const name = card?.querySelector('.card-title a')?.textContent || id;
                        const url = card?.querySelector('.card-title a')?.href || '';
                        showMoveToPlaylistModal(type, id, { name, url, category: type }, currentPlaylist);
                    });
                });

                console.log('[Collection] Rendered successfully');
            } catch (e) {
                console.error('[Collection] Error:', e);
                container.innerHTML = '<div class="error">Error loading collection: ' + e.message + '</div>';
            }
        }

        // Toggle playlist section expand/collapse
        window.togglePlaylistSection = function(playlistId) {
            const section = container.querySelector(`.playlist-section[data-playlist-id="${playlistId}"]`);
            if (section) {
                section.classList.toggle('expanded');
            }
        };

        // Set collection view (cards or table)
        window.setCollectionView = function(viewMode) {
            localStorage.setItem('collectionView', viewMode);
            loadCollection();
        };

        // Show create playlist modal
        window.showCreatePlaylistModal = function() {
            const modal = document.getElementById('create-playlist-modal');
            if (modal) {
                modal.style.display = 'flex';
                document.getElementById('playlist-name-input').focus();
            }
        };

        // Rename playlist - show modal
        window.renamePlaylist = function(playlistId) {
            const playlist = window.TechEconPlaylists.get(playlistId);
            if (!playlist) return;

            const modal = document.getElementById('rename-playlist-modal');
            const input = document.getElementById('rename-playlist-input');
            const idInput = document.getElementById('rename-playlist-id');

            if (modal && input && idInput) {
                input.value = playlist.name;
                idInput.value = playlistId;
                modal.style.display = 'flex';
                input.focus();
                input.select();
            }
        };

        // Delete playlist
        window.deletePlaylist = function(playlistId) {
            if (confirm('Delete this playlist? Items will move to Uncategorized.')) {
                window.TechEconPlaylists.delete(playlistId);
                showToast('Playlist deleted');
                loadCollection();
            }
        };

        // Remove from collection
        window.removeFromCollection = function(type, id, playlistId) {
            if (playlistId && playlistId !== '__uncategorized__') {
                // Remove from playlist
                window.TechEconPlaylists.removeItem(playlistId, type, id);
                showToast('Removed from playlist');
            } else {
                // Remove from favorites entirely
                window.TechEconFavorites.remove(type, id);
                showToast('Removed from favorites');
            }
            loadCollection();
        };

        // Show move to playlist modal
        window.showMoveToPlaylistModal = function(itemType, itemId, itemData, currentPlaylistId) {
            if (!window.TechEconPlaylists) {
                showToast('Playlists not available', 'error');
                return;
            }

            currentPlaylistItem = { type: itemType, id: itemId, data: itemData, currentPlaylist: currentPlaylistId };

            const modal = document.getElementById('add-to-playlist-modal');
            const optionsContainer = document.getElementById('playlist-options');

            if (!modal || !optionsContainer) return;

            const playlists = window.TechEconPlaylists.getAll();

            let html = '';

            // Add "Uncategorized" option if item is in a playlist
            if (currentPlaylistId && currentPlaylistId !== '__uncategorized__') {
                html += `
                    <div class="playlist-option" data-playlist-id="__uncategorized__">
                        <span class="playlist-option-name">Uncategorized</span>
                        <span class="playlist-option-count">Remove from playlist</span>
                    </div>
                `;
            }

            playlists.forEach(playlist => {
                const isCurrentPlaylist = playlist.id === currentPlaylistId;
                html += `
                    <div class="playlist-option ${isCurrentPlaylist ? 'already-added' : ''}"
                         data-playlist-id="${playlist.id}">
                        <span class="playlist-option-name">${escapeHtml(playlist.name)}</span>
                        <span class="playlist-option-count">${playlist.items.length} items</span>
                        ${isCurrentPlaylist ? '<span class="playlist-option-check">✓ Current</span>' : ''}
                    </div>
                `;
            });

            if (playlists.length === 0 && (!currentPlaylistId || currentPlaylistId === '__uncategorized__')) {
                html = `
                    <div class="empty-state-small">
                        <p>No playlists yet</p>
                        <p class="text-muted">Create one to organize your favorites</p>
                    </div>
                `;
            }

            optionsContainer.innerHTML = html;

            // Add click handlers
            optionsContainer.querySelectorAll('.playlist-option:not(.already-added)').forEach(opt => {
                opt.addEventListener('click', function() {
                    const targetPlaylistId = this.dataset.playlistId;
                    if (currentPlaylistItem) {
                        // Remove from current playlist if exists
                        if (currentPlaylistItem.currentPlaylist && currentPlaylistItem.currentPlaylist !== '__uncategorized__') {
                            window.TechEconPlaylists.removeItem(
                                currentPlaylistItem.currentPlaylist,
                                currentPlaylistItem.type,
                                currentPlaylistItem.id
                            );
                        }

                        // Add to new playlist (unless moving to uncategorized)
                        if (targetPlaylistId !== '__uncategorized__') {
                            window.TechEconPlaylists.addItem(
                                targetPlaylistId,
                                currentPlaylistItem.type,
                                currentPlaylistItem.id,
                                currentPlaylistItem.data
                            );
                            showToast('Moved to playlist');
                        } else {
                            showToast('Moved to Uncategorized');
                        }

                        hideAddToPlaylistModal();
                        loadCollection();
                    }
                });
            });

            modal.style.display = 'flex';
        };

        // Expose loadCollection for external trigger
        window.reloadFavoritesPage = loadCollection;

        // Remove favorite function (legacy support)
        window.removeFavorite = function(type, id) {
            if (window.TechEconFavorites) {
                window.TechEconFavorites.remove(type, id);
                showToast('Removed from favorites');
                loadCollection();
            }
        };

        // Load immediately
        loadCollection();

        // Initialize modals
        initAddToPlaylistModal();
        initCreatePlaylistModal();
        initRenamePlaylistModal();
    }

    // Initialize create playlist modal
    function initCreatePlaylistModal() {
        const modal = document.getElementById('create-playlist-modal');
        const input = document.getElementById('playlist-name-input');
        const cancelBtn = document.getElementById('cancel-playlist-btn');
        const createBtn = document.getElementById('create-playlist-btn');

        if (!modal || !input) return;

        function closeModal() {
            modal.style.display = 'none';
            input.value = '';
        }

        if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

        if (createBtn) {
            createBtn.addEventListener('click', function() {
                const name = input.value.trim();
                if (name) {
                    const playlistId = window.TechEconPlaylists.create(name);

                    // Check if there's a pending item to add
                    if (window._pendingPlaylistItem) {
                        const item = window._pendingPlaylistItem;
                        window.TechEconPlaylists.addItem(playlistId, item.type, item.id, item.data);
                        showToast('Created playlist and added item');
                        window._pendingPlaylistItem = null;
                    } else {
                        showToast('Playlist created');
                    }

                    closeModal();
                    if (window.reloadFavoritesPage) window.reloadFavoritesPage();
                }
            });
        }

        // Allow Enter key to create
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                createBtn.click();
            }
        });

        // Close on backdrop click
        modal.querySelector('.modal-backdrop')?.addEventListener('click', closeModal);
    }

    // Initialize rename playlist modal
    function initRenamePlaylistModal() {
        const modal = document.getElementById('rename-playlist-modal');
        const input = document.getElementById('rename-playlist-input');
        const idInput = document.getElementById('rename-playlist-id');
        const cancelBtn = document.getElementById('cancel-rename-btn');
        const confirmBtn = document.getElementById('confirm-rename-btn');

        if (!modal || !input) return;

        function closeModal() {
            modal.style.display = 'none';
            input.value = '';
            idInput.value = '';
        }

        if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

        if (confirmBtn) {
            confirmBtn.addEventListener('click', function() {
                const newName = input.value.trim();
                const playlistId = idInput.value;
                if (newName && playlistId) {
                    window.TechEconPlaylists.rename(playlistId, newName);
                    showToast('Playlist renamed');
                    closeModal();
                    if (window.reloadFavoritesPage) window.reloadFavoritesPage();
                }
            });
        }

        // Allow Enter key
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmBtn.click();
            }
        });

        // Close on backdrop click
        modal.querySelector('.modal-backdrop')?.addEventListener('click', closeModal);
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

            console.log('[Favorites] Calling initFavoriteButtons and initCollectionPage');
            initFavoriteButtons();
            initCollectionPage();

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
