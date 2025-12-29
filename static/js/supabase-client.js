// Supabase Client for Tech-Econ
// Handles authentication only - favorites/playlists use localStorage

(function() {
    'use strict';

    // Supabase configuration
    const SUPABASE_URL = 'https://cldrqbswhdatrqednzzm.supabase.co';
    const SUPABASE_ANON_KEY = 'sb_publishable_j4Gs5aivMj69ClKnnOAUiA_EJFxEuXU';

    let supabase = null;
    let currentUser = null;

    // Initialize Supabase client
    function initSupabase() {
        if (window.supabase && window.supabase.createClient) {
            supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

            // Check for existing session
            supabase.auth.getSession().then(({ data: { session } }) => {
                if (session) {
                    currentUser = session.user;
                }
                updateAuthUI();
            });

            // Listen for auth changes
            supabase.auth.onAuthStateChange((event, session) => {
                currentUser = session?.user || null;
                updateAuthUI();
            });
        }
    }

    // Auth functions
    window.TechEconAuth = {
        signUp: async function(email, password) {
            const { data, error } = await supabase.auth.signUp({
                email,
                password,
                options: {
                    emailRedirectTo: 'https://tech-econ.com/favorites/'
                }
            });
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
            updateAuthUI();
        },

        getUser: function() {
            return currentUser;
        },

        isLoggedIn: function() {
            return currentUser !== null;
        }
    };

    // NOTE: Favorites and Playlists are now handled by localStorage-based modules
    // See: favorites-local.js and playlists-local.js
    // No account required - saves directly to browser storage

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
