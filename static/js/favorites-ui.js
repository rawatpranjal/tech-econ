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

    // Current item being added to collection
    let currentCollectionItem = null;

    // Show "Add to Collection" modal
    function showAddToCollectionModal(itemType, itemId, itemData) {
        if (!window.TechEconPlaylists) {
            showToast('Collections not available', 'error');
            return;
        }

        currentCollectionItem = { type: itemType, id: itemId, data: itemData };

        const modal = document.getElementById('add-to-collection-modal');
        const optionsContainer = document.getElementById('collection-options');

        if (!modal || !optionsContainer) {
            // Modal not on this page, create it dynamically
            createAddToCollectionModal();
            return showAddToCollectionModal(itemType, itemId, itemData);
        }

        const collections = window.TechEconPlaylists.getAll();

        if (collections.length === 0) {
            optionsContainer.innerHTML = `
                <div class="empty-state-small">
                    <p>No collections yet</p>
                    <p class="text-muted">Create one to get started</p>
                </div>
            `;
        } else {
            let html = '';
            collections.forEach(collection => {
                const hasItem = collection.items.some(item =>
                    item.type === itemType && item.id === itemId
                );
                html += `
                    <div class="collection-option ${hasItem ? 'already-added' : ''}"
                         data-collection-id="${collection.id}">
                        <span class="collection-option-name">${escapeHtml(collection.name)}</span>
                        <span class="collection-option-count">${collection.items.length} items</span>
                        ${hasItem ? '<span class="collection-option-check">✓</span>' : ''}
                    </div>
                `;
            });
            optionsContainer.innerHTML = html;

            // Add click handlers
            optionsContainer.querySelectorAll('.collection-option:not(.already-added)').forEach(opt => {
                opt.addEventListener('click', function() {
                    const collectionId = this.dataset.collectionId;
                    if (currentCollectionItem) {
                        window.TechEconPlaylists.addItem(
                            collectionId,
                            currentCollectionItem.type,
                            currentCollectionItem.id,
                            currentCollectionItem.data
                        );
                        showToast('Added to collection');
                        hideAddToCollectionModal();
                    }
                });
            });
        }

        modal.style.display = 'flex';
    }

    // Hide "Add to Collection" modal
    function hideAddToCollectionModal() {
        const modal = document.getElementById('add-to-collection-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        currentCollectionItem = null;
    }

    // Create modal dynamically for pages that don't have it
    function createAddToCollectionModal() {
        if (document.getElementById('add-to-collection-modal')) return;

        const modal = document.createElement('div');
        modal.id = 'add-to-collection-modal';
        modal.className = 'modal';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="modal-backdrop"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Add to Collection</h3>
                    <button class="modal-close" id="close-add-collection-modal">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
                <div id="collection-options" class="collection-options-list"></div>
                <div class="modal-actions">
                    <button class="btn btn-outline" id="create-and-add-btn">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="12" y1="5" x2="12" y2="19"></line>
                            <line x1="5" y1="12" x2="19" y2="12"></line>
                        </svg>
                        Create New Collection
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        initAddToCollectionModal();
    }

    // Initialize modal event handlers
    function initAddToCollectionModal() {
        const modal = document.getElementById('add-to-collection-modal');
        if (!modal) return;

        const backdrop = modal.querySelector('.modal-backdrop');
        const closeBtn = document.getElementById('close-add-collection-modal');
        const createBtn = document.getElementById('create-and-add-btn');

        if (backdrop) backdrop.addEventListener('click', hideAddToCollectionModal);
        if (closeBtn) closeBtn.addEventListener('click', hideAddToCollectionModal);

        if (createBtn) {
            createBtn.addEventListener('click', function() {
                // Store pending item to add after collection creation
                window._pendingCollectionItem = currentCollectionItem;
                hideAddToCollectionModal();
                // Show the proper create collection modal
                if (window.showCreateCollectionModal) {
                    window.showCreateCollectionModal();
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
    window.showAddToCollectionModal = showAddToCollectionModal;

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

            // Long press to add to collection (mouse)
            btn.addEventListener('mousedown', function(e) {
                pressTimer = setTimeout(() => {
                    longPressed = true;
                    showAddToCollectionModal(itemType, itemId, itemData);
                }, 500);
            });
            btn.addEventListener('mouseup', () => clearTimeout(pressTimer));
            btn.addEventListener('mouseleave', () => clearTimeout(pressTimer));

            // Long press to add to collection (touch)
            btn.addEventListener('touchstart', function(e) {
                pressTimer = setTimeout(() => {
                    longPressed = true;
                    e.preventDefault();
                    showAddToCollectionModal(itemType, itemId, itemData);
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

        // Note: We use fav.data stored in localStorage instead of looking up in all-data
        // This avoids embedding 1MB+ of JSON in the page which caused issues on GitHub Pages

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

        // Render a single favorite card with move-to-collection option
        function renderCollectionCard(fav, collectionId) {
            const name = fav.data?.name || fav.id;
            const desc = fav.data?.description || '';
            const url = fav.data?.url || '#';
            const category = fav.data?.category || fav.type;
            const favicon = getFavicon(url);
            const escapedId = fav.id.replace(/'/g, "\\'").replace(/"/g, '&quot;');
            const escapedCollectionId = collectionId ? collectionId.replace(/'/g, "\\'") : '';

            return `
                <div class="favorite-card" data-type="${fav.type}" data-id="${fav.id}" data-collection="${collectionId || ''}">
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
                            <button class="move-to-collection-btn" title="Move to collection" data-type="${fav.type}" data-id="${escapedId}" data-current-collection="${escapedCollectionId}">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M5 12h14M12 5l7 7-7 7"/>
                                </svg>
                            </button>
                            <button class="favorite-remove" onclick="removeFromCollection('${fav.type}', '${escapedId}', '${escapedCollectionId}')">
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
        function renderCollectionRow(fav, collectionId) {
            const name = fav.data?.name || fav.id;
            const url = fav.data?.url || '#';
            const category = fav.data?.category || fav.type;
            const favicon = getFavicon(url);
            const escapedId = fav.id.replace(/'/g, "\\'").replace(/"/g, '&quot;');
            const escapedCollectionId = collectionId ? collectionId.replace(/'/g, "\\'") : '';

            return `
                <tr class="collection-row" data-type="${fav.type}" data-id="${fav.id}">
                    <td class="col-name">
                        ${favicon ? `<img class="resource-favicon-sm" src="${favicon}" alt="" loading="lazy" onerror="this.style.display='none'">` : ''}
                        <a href="${url}" target="_blank" rel="noopener">${name}</a>
                    </td>
                    <td class="col-type"><span class="type-badge type-${fav.type}">${fav.type}</span></td>
                    <td class="col-category">${category}</td>
                    <td class="col-actions">
                        <button class="btn-icon-sm move-to-collection-btn" title="Move to collection" data-type="${fav.type}" data-id="${escapedId}" data-current-collection="${escapedCollectionId}">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M5 12h14M12 5l7 7-7 7"/>
                            </svg>
                        </button>
                        <button class="btn-icon-sm btn-danger" onclick="removeFromCollection('${fav.type}', '${escapedId}', '${escapedCollectionId}')" title="Remove">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"></line>
                                <line x1="6" y1="6" x2="18" y2="18"></line>
                            </svg>
                        </button>
                    </td>
                </tr>
            `;
        }

        // Render a collection section
        function renderCollectionSection(collection, items, isExpanded, viewMode) {
            const itemCount = items.length;
            const escapedId = collection.id.replace(/'/g, "\\'");

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
                        itemsHtml += renderCollectionRow(fav, collection.id);
                    });
                    itemsHtml += '</tbody></table>';
                }
            } else {
                // Card view (default)
                items.forEach(item => {
                    const fav = { type: item.type, id: item.id, data: item.data };
                    itemsHtml += renderCollectionCard(fav, collection.id);
                });
            }

            const contentClass = viewMode === 'table' ? 'table-view' : 'favorites-grid';
            const isUncategorized = collection.id === '__uncategorized__';

            return `
                <div class="collection-section ${isExpanded ? 'expanded' : ''}" data-collection-id="${collection.id}">
                    <div class="collection-section-header" onclick="toggleCollectionSection('${escapedId}')">
                        <div class="collection-section-info">
                            <svg class="collection-chevron" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="9 18 15 12 9 6"></polyline>
                            </svg>
                            <span class="collection-section-name">${escapeHtml(collection.name)}</span>
                            <span class="collection-section-count">${itemCount} item${itemCount !== 1 ? 's' : ''}</span>
                        </div>
                        <div class="collection-section-actions">
                            <button class="btn-icon" onclick="event.stopPropagation(); renameCollection('${escapedId}')" title="${isUncategorized ? 'Create collection from these items' : 'Rename'}">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    ${isUncategorized ?
                                        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>' :
                                        '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
                                    }
                                </svg>
                            </button>
                            ${isUncategorized ? '' : `<button class="btn-icon btn-danger" onclick="event.stopPropagation(); deleteCollection('${escapedId}')" title="Delete collection">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3 6 5 6 21 6"></polyline>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                </svg>
                            </button>`}
                        </div>
                    </div>
                    <div class="collection-section-content">
                        <div class="${contentClass}">
                            ${itemsHtml || '<p class="empty-collection">No items in this collection</p>'}
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
                            <button class="btn btn-primary btn-sm" onclick="showCreateCollectionModal()">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="12" y1="5" x2="12" y2="19"></line>
                                    <line x1="5" y1="12" x2="19" y2="12"></line>
                                </svg>
                                New Collection
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

                // Render each collection as a collapsible section
                playlists.forEach((collection, index) => {
                    html += renderCollectionSection(collection, collection.items, index === 0, currentView);
                });

                // Render uncategorized section
                if (uncategorized.length > 0) {
                    const uncategorizedCollection = {
                        id: '__uncategorized__',
                        name: 'Uncategorized',
                        items: uncategorized.map(f => ({ type: f.type, id: f.id, data: f.data }))
                    };
                    html += renderCollectionSection(uncategorizedCollection, uncategorizedCollection.items, playlists.length === 0, currentView);
                }

                container.innerHTML = html;

                // Add event listeners for move-to-collection buttons
                container.querySelectorAll('.move-to-collection-btn').forEach(btn => {
                    btn.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        const type = this.dataset.type;
                        const id = this.dataset.id;
                        const currentCollection = this.dataset.currentCollection;
                        const card = this.closest('.favorite-card');
                        const name = card?.querySelector('.card-title a')?.textContent || id;
                        const url = card?.querySelector('.card-title a')?.href || '';
                        showMoveToCollectionModal(type, id, { name, url, category: type }, currentCollection);
                    });
                });

                console.log('[Collection] Rendered successfully');
            } catch (e) {
                console.error('[Collection] Error:', e);
                container.innerHTML = '<div class="error">Error loading collection: ' + e.message + '</div>';
            }
        }

        // Toggle collection section expand/collapse
        window.toggleCollectionSection = function(collectionId) {
            const section = container.querySelector(`.collection-section[data-collection-id="${collectionId}"]`);
            if (section) {
                section.classList.toggle('expanded');
            }
        };

        // Set collection view (cards or table)
        window.setCollectionView = function(viewMode) {
            localStorage.setItem('collectionView', viewMode);
            loadCollection();
        };

        // Show create collection modal
        window.showCreateCollectionModal = function() {
            const modal = document.getElementById('create-collection-modal');
            if (modal) {
                modal.style.display = 'flex';
                document.getElementById('collection-name-input').focus();
            }
        };

        // Rename collection - show modal
        window.renameCollection = function(collectionId) {
            const isUncategorized = collectionId === '__uncategorized__';
            const collection = isUncategorized ? { name: '' } : window.TechEconPlaylists.get(collectionId);
            if (!collection) return;

            const modal = document.getElementById('rename-collection-modal');
            const input = document.getElementById('rename-collection-input');
            const idInput = document.getElementById('rename-collection-id');
            const modalTitle = modal?.querySelector('h3');
            const confirmBtn = document.getElementById('confirm-rename-btn');

            if (modal && input && idInput) {
                input.value = collection.name;
                idInput.value = collectionId;
                if (modalTitle) modalTitle.textContent = isUncategorized ? 'Create Collection' : 'Rename Collection';
                if (confirmBtn) confirmBtn.textContent = isUncategorized ? 'Create' : 'Rename';
                input.placeholder = isUncategorized ? 'Collection name' : '';
                modal.style.display = 'flex';
                input.focus();
                input.select();
            }
        };

        // Delete collection
        window.deleteCollection = function(collectionId) {
            if (confirm('Delete this collection? Items will move to Uncategorized.')) {
                window.TechEconPlaylists.delete(collectionId);
                showToast('Collection deleted');
                loadCollection();
            }
        };

        // Remove from collection
        window.removeFromCollection = function(type, id, collectionId) {
            if (collectionId && collectionId !== '__uncategorized__') {
                // Remove from collection
                window.TechEconPlaylists.removeItem(collectionId, type, id);
                showToast('Removed from collection');
            } else {
                // Remove from favorites entirely
                window.TechEconFavorites.remove(type, id);
                showToast('Removed from favorites');
            }
            loadCollection();
        };

        // Show move to collection modal
        window.showMoveToCollectionModal = function(itemType, itemId, itemData, currentCollectionId) {
            if (!window.TechEconPlaylists) {
                showToast('Collections not available', 'error');
                return;
            }

            currentCollectionItem = { type: itemType, id: itemId, data: itemData, currentCollection: currentCollectionId };

            const modal = document.getElementById('add-to-collection-modal');
            const optionsContainer = document.getElementById('collection-options');

            if (!modal || !optionsContainer) return;

            const collections = window.TechEconPlaylists.getAll();

            let html = '';

            // Add "Uncategorized" option if item is in a collection
            if (currentCollectionId && currentCollectionId !== '__uncategorized__') {
                html += `
                    <div class="collection-option" data-collection-id="__uncategorized__">
                        <span class="collection-option-name">Uncategorized</span>
                        <span class="collection-option-count">Remove from collection</span>
                    </div>
                `;
            }

            collections.forEach(collection => {
                const isCurrentCollection = collection.id === currentCollectionId;
                html += `
                    <div class="collection-option ${isCurrentCollection ? 'already-added' : ''}"
                         data-collection-id="${collection.id}">
                        <span class="collection-option-name">${escapeHtml(collection.name)}</span>
                        <span class="collection-option-count">${collection.items.length} items</span>
                        ${isCurrentCollection ? '<span class="collection-option-check">✓ Current</span>' : ''}
                    </div>
                `;
            });

            if (collections.length === 0 && (!currentCollectionId || currentCollectionId === '__uncategorized__')) {
                html = `
                    <div class="empty-state-small">
                        <p>No collections yet</p>
                        <p class="text-muted">Create one to organize your favorites</p>
                    </div>
                `;
            }

            optionsContainer.innerHTML = html;

            // Add click handlers
            optionsContainer.querySelectorAll('.collection-option:not(.already-added)').forEach(opt => {
                opt.addEventListener('click', function() {
                    const targetCollectionId = this.dataset.collectionId;
                    if (currentCollectionItem) {
                        // Remove from current collection if exists
                        if (currentCollectionItem.currentCollection && currentCollectionItem.currentCollection !== '__uncategorized__') {
                            window.TechEconPlaylists.removeItem(
                                currentCollectionItem.currentCollection,
                                currentCollectionItem.type,
                                currentCollectionItem.id
                            );
                        }

                        // Add to new collection (unless moving to uncategorized)
                        if (targetCollectionId !== '__uncategorized__') {
                            window.TechEconPlaylists.addItem(
                                targetCollectionId,
                                currentCollectionItem.type,
                                currentCollectionItem.id,
                                currentCollectionItem.data
                            );
                            showToast('Moved to collection');
                        } else {
                            showToast('Moved to Uncategorized');
                        }

                        hideAddToCollectionModal();
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
        initAddToCollectionModal();
        initCreateCollectionModal();
        initRenameCollectionModal();
    }

    // Initialize create collection modal
    function initCreateCollectionModal() {
        const modal = document.getElementById('create-collection-modal');
        const input = document.getElementById('collection-name-input');
        const cancelBtn = document.getElementById('cancel-collection-btn');
        const createBtn = document.getElementById('create-collection-btn');

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
                    const collectionId = window.TechEconPlaylists.create(name);

                    // Check if there's a pending item to add
                    if (window._pendingCollectionItem) {
                        const item = window._pendingCollectionItem;
                        window.TechEconPlaylists.addItem(collectionId, item.type, item.id, item.data);
                        showToast('Created collection and added item');
                        window._pendingCollectionItem = null;
                    } else {
                        showToast('Collection created');
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

    // Initialize rename collection modal
    function initRenameCollectionModal() {
        const modal = document.getElementById('rename-collection-modal');
        const input = document.getElementById('rename-collection-input');
        const idInput = document.getElementById('rename-collection-id');
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
                const collectionId = idInput.value;
                if (newName && collectionId) {
                    if (collectionId === '__uncategorized__') {
                        // Create new collection from uncategorized items
                        const newCollectionId = window.TechEconPlaylists.create(newName);
                        if (newCollectionId) {
                            // Get all uncategorized favorites
                            const favorites = window.TechEconFavorites.get();
                            const playlists = window.TechEconPlaylists.getAll();
                            const favoritesInPlaylists = new Set();
                            playlists.forEach(p => {
                                p.items.forEach(item => favoritesInPlaylists.add(`${item.type}:${item.id}`));
                            });
                            const uncategorized = favorites.filter(fav =>
                                !favoritesInPlaylists.has(`${fav.type}:${fav.id}`)
                            );
                            // Add all uncategorized items to new collection
                            uncategorized.forEach(fav => {
                                window.TechEconPlaylists.addItem(newCollectionId, fav.type, fav.id, fav.data);
                            });
                            showToast(`Created "${newName}" with ${uncategorized.length} items`);
                        }
                    } else {
                        window.TechEconPlaylists.rename(collectionId, newName);
                        showToast('Collection renamed');
                    }
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

        // Note: We use item.data stored in localStorage instead of looking up in all-data

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
                    const name = item.data?.name || item.id;
                    const url = item.data?.url || '#';
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
