// Supabase Client for Tech-Econ
// Handles authentication and favorites/playlists data

(function() {
    'use strict';

    // Supabase configuration
    const SUPABASE_URL = 'https://cldrqbswhdatrqednzzm.supabase.co';
    const SUPABASE_ANON_KEY = 'sb_publishable_j4Gs5aivMj69ClKnnOAUiA_EJFxEuXU';

    let supabase = null;
    let currentUser = null;
    let userFavorites = new Set();

    // Initialize Supabase client
    function initSupabase() {
        if (window.supabase && window.supabase.createClient) {
            supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

            // Check for existing session
            supabase.auth.getSession().then(({ data: { session } }) => {
                if (session) {
                    currentUser = session.user;
                    loadUserFavorites();
                }
                updateAuthUI();
            });

            // Listen for auth changes
            supabase.auth.onAuthStateChange((event, session) => {
                currentUser = session?.user || null;
                if (currentUser) {
                    loadUserFavorites();
                } else {
                    userFavorites.clear();
                }
                updateAuthUI();
                updateFavoriteButtons();
            });
        }
    }

    // Auth functions
    window.TechEconAuth = {
        signUp: async function(email, password) {
            const { data, error } = await supabase.auth.signUp({ email, password });
            if (error) throw error;
            return data;
        },

        signIn: async function(email, password) {
            const { data, error } = await supabase.auth.signInWithPassword({ email, password });
            if (error) throw error;
            return data;
        },

        signOut: async function() {
            const { error } = await supabase.auth.signOut();
            if (error) throw error;
            currentUser = null;
            userFavorites.clear();
            updateAuthUI();
            updateFavoriteButtons();
        },

        getUser: function() {
            return currentUser;
        },

        isLoggedIn: function() {
            return currentUser !== null;
        }
    };

    // Favorites functions
    window.TechEconFavorites = {
        add: async function(itemType, itemId) {
            if (!currentUser) {
                showAuthModal();
                return false;
            }
            const { error } = await supabase
                .from('favorites')
                .insert({ user_id: currentUser.id, item_type: itemType, item_id: itemId });
            if (error && error.code !== '23505') throw error; // Ignore duplicate
            userFavorites.add(`${itemType}:${itemId}`);
            return true;
        },

        remove: async function(itemType, itemId) {
            if (!currentUser) return false;
            const { error } = await supabase
                .from('favorites')
                .delete()
                .eq('user_id', currentUser.id)
                .eq('item_type', itemType)
                .eq('item_id', itemId);
            if (error) throw error;
            userFavorites.delete(`${itemType}:${itemId}`);
            return true;
        },

        toggle: async function(itemType, itemId) {
            const key = `${itemType}:${itemId}`;
            if (userFavorites.has(key)) {
                await this.remove(itemType, itemId);
                return false;
            } else {
                await this.add(itemType, itemId);
                return true;
            }
        },

        isFavorited: function(itemType, itemId) {
            return userFavorites.has(`${itemType}:${itemId}`);
        },

        getAll: async function() {
            if (!currentUser) return [];
            const { data, error } = await supabase
                .from('favorites')
                .select('*')
                .eq('user_id', currentUser.id)
                .order('created_at', { ascending: false });
            if (error) throw error;
            return data || [];
        }
    };

    // Playlists functions
    window.TechEconPlaylists = {
        create: async function(name, description = '') {
            if (!currentUser) {
                showAuthModal();
                return null;
            }
            const { data, error } = await supabase
                .from('playlists')
                .insert({ user_id: currentUser.id, name, description })
                .select()
                .single();
            if (error) throw error;
            return data;
        },

        getAll: async function() {
            if (!currentUser) return [];
            const { data, error } = await supabase
                .from('playlists')
                .select('*')
                .eq('user_id', currentUser.id)
                .order('created_at', { ascending: false });
            if (error) throw error;
            return data || [];
        },

        delete: async function(playlistId) {
            if (!currentUser) return false;
            const { error } = await supabase
                .from('playlists')
                .delete()
                .eq('id', playlistId)
                .eq('user_id', currentUser.id);
            if (error) throw error;
            return true;
        },

        addItem: async function(playlistId, itemType, itemId) {
            const { error } = await supabase
                .from('playlist_items')
                .insert({ playlist_id: playlistId, item_type: itemType, item_id: itemId });
            if (error && error.code !== '23505') throw error;
            return true;
        },

        removeItem: async function(playlistId, itemType, itemId) {
            const { error } = await supabase
                .from('playlist_items')
                .delete()
                .eq('playlist_id', playlistId)
                .eq('item_type', itemType)
                .eq('item_id', itemId);
            if (error) throw error;
            return true;
        },

        getItems: async function(playlistId) {
            const { data, error } = await supabase
                .from('playlist_items')
                .select('*')
                .eq('playlist_id', playlistId)
                .order('position', { ascending: true });
            if (error) throw error;
            return data || [];
        }
    };

    // Load user's favorites into memory
    async function loadUserFavorites() {
        if (!currentUser) return;
        try {
            const { data } = await supabase
                .from('favorites')
                .select('item_type, item_id')
                .eq('user_id', currentUser.id);
            userFavorites.clear();
            (data || []).forEach(f => userFavorites.add(`${f.item_type}:${f.item_id}`));
            updateFavoriteButtons();
        } catch (e) {
            console.error('Failed to load favorites:', e);
        }
    }

    // Update auth UI elements
    function updateAuthUI() {
        const authBtn = document.getElementById('auth-btn');
        const userMenu = document.getElementById('user-menu');
        const userEmail = document.getElementById('user-email');

        if (currentUser) {
            if (authBtn) authBtn.style.display = 'none';
            if (userMenu) userMenu.style.display = 'flex';
            if (userEmail) userEmail.textContent = currentUser.email;
        } else {
            if (authBtn) authBtn.style.display = 'flex';
            if (userMenu) userMenu.style.display = 'none';
        }

        // Update top-right profile button
        if (window.updateProfileButton) {
            window.updateProfileButton(currentUser);
        }
    }

    // Update all favorite buttons on page
    function updateFavoriteButtons() {
        document.querySelectorAll('[data-favorite-btn]').forEach(btn => {
            const itemType = btn.dataset.itemType;
            const itemId = btn.dataset.itemId;
            const isFav = userFavorites.has(`${itemType}:${itemId}`);
            btn.classList.toggle('favorited', isFav);
            btn.setAttribute('aria-pressed', isFav);
        });
    }

    // Show auth modal
    function showAuthModal() {
        const modal = document.getElementById('auth-modal');
        if (modal) {
            modal.classList.add('open');
            document.body.style.overflow = 'hidden';
        }
    }

    // Hide auth modal
    function hideAuthModal() {
        const modal = document.getElementById('auth-modal');
        if (modal) {
            modal.classList.remove('open');
            document.body.style.overflow = '';
        }
    }

    // Expose modal functions
    window.TechEconAuth.showModal = showAuthModal;
    window.TechEconAuth.hideModal = hideAuthModal;

    // Initialize when Supabase script loads
    function waitForSupabase() {
        if (window.supabase && window.supabase.createClient) {
            initSupabase();
        } else {
            setTimeout(waitForSupabase, 50);
        }
    }

    // Start initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', waitForSupabase);
    } else {
        waitForSupabase();
    }
})();
