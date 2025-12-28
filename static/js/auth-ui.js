// Auth UI for Tech-Econ
// Login/signup modal and user menu

(function() {
    'use strict';

    // Create and inject auth UI elements
    function createAuthUI() {
        // Auth button in sidebar
        const sidebarFooter = document.querySelector('.sidebar-footer');
        if (sidebarFooter) {
            const authBtn = document.createElement('a');
            authBtn.href = '#';
            authBtn.id = 'auth-btn';
            authBtn.className = 'sidebar-footer-link';
            authBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
                Sign In
            `;
            authBtn.addEventListener('click', function(e) {
                e.preventDefault();
                TechEconAuth.showModal();
            });
            sidebarFooter.insertBefore(authBtn, sidebarFooter.firstChild);

            // User menu (hidden by default)
            const userMenu = document.createElement('div');
            userMenu.id = 'user-menu';
            userMenu.className = 'user-menu';
            userMenu.style.display = 'none';
            userMenu.innerHTML = `
                <div class="user-menu-trigger">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                    <span id="user-email" class="user-email"></span>
                </div>
                <div class="user-menu-dropdown">
                    <a href="/favorites/" class="user-menu-item">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                        </svg>
                        My Favorites
                    </a>
                    <a href="/playlists/" class="user-menu-item">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="8" y1="6" x2="21" y2="6"></line>
                            <line x1="8" y1="12" x2="21" y2="12"></line>
                            <line x1="8" y1="18" x2="21" y2="18"></line>
                            <line x1="3" y1="6" x2="3.01" y2="6"></line>
                            <line x1="3" y1="12" x2="3.01" y2="12"></line>
                            <line x1="3" y1="18" x2="3.01" y2="18"></line>
                        </svg>
                        My Playlists
                    </a>
                    <button class="user-menu-item user-menu-signout" id="signout-btn">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                            <polyline points="16 17 21 12 16 7"></polyline>
                            <line x1="21" y1="12" x2="9" y2="12"></line>
                        </svg>
                        Sign Out
                    </button>
                </div>
            `;
            sidebarFooter.insertBefore(userMenu, sidebarFooter.firstChild);

            // Toggle dropdown
            userMenu.querySelector('.user-menu-trigger').addEventListener('click', function() {
                userMenu.classList.toggle('open');
            });

            // Sign out
            document.getElementById('signout-btn').addEventListener('click', async function() {
                try {
                    await TechEconAuth.signOut();
                    showToast('Signed out successfully');
                } catch (e) {
                    showToast('Error signing out', 'error');
                }
            });

            // Close dropdown when clicking outside
            document.addEventListener('click', function(e) {
                if (!userMenu.contains(e.target)) {
                    userMenu.classList.remove('open');
                }
            });
        }

        // Create auth modal
        const modal = document.createElement('div');
        modal.id = 'auth-modal';
        modal.className = 'auth-modal';
        modal.innerHTML = `
            <div class="auth-modal-backdrop"></div>
            <div class="auth-modal-content">
                <button class="auth-modal-close" aria-label="Close">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
                <h2 class="auth-modal-title">Welcome to Tech-Econ</h2>
                <p class="auth-modal-subtitle">Sign in to save favorites and create playlists</p>

                <div class="auth-tabs">
                    <button class="auth-tab active" data-tab="signin">Sign In</button>
                    <button class="auth-tab" data-tab="signup">Sign Up</button>
                </div>

                <form id="auth-form" class="auth-form">
                    <div class="auth-field">
                        <label for="auth-email">Email</label>
                        <input type="email" id="auth-email" required placeholder="you@example.com">
                    </div>
                    <div class="auth-field">
                        <label for="auth-password">Password</label>
                        <input type="password" id="auth-password" required placeholder="Your password" minlength="6">
                    </div>
                    <div class="auth-error" id="auth-error"></div>
                    <button type="submit" class="auth-submit" id="auth-submit">Sign In</button>
                </form>

                <p class="auth-footer">
                    By signing in, you agree to our terms of service.
                </p>
            </div>
        `;
        document.body.appendChild(modal);

        // Modal event handlers
        const backdrop = modal.querySelector('.auth-modal-backdrop');
        const closeBtn = modal.querySelector('.auth-modal-close');
        const tabs = modal.querySelectorAll('.auth-tab');
        const form = document.getElementById('auth-form');
        const submitBtn = document.getElementById('auth-submit');
        const errorEl = document.getElementById('auth-error');

        let currentTab = 'signin';

        backdrop.addEventListener('click', function() {
            TechEconAuth.hideModal();
        });

        closeBtn.addEventListener('click', function() {
            TechEconAuth.hideModal();
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.classList.contains('open')) {
                TechEconAuth.hideModal();
            }
        });

        tabs.forEach(tab => {
            tab.addEventListener('click', function() {
                currentTab = this.dataset.tab;
                tabs.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                submitBtn.textContent = currentTab === 'signin' ? 'Sign In' : 'Sign Up';
                errorEl.textContent = '';
            });
        });

        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            const email = document.getElementById('auth-email').value;
            const password = document.getElementById('auth-password').value;

            submitBtn.disabled = true;
            submitBtn.textContent = 'Loading...';
            errorEl.textContent = '';

            try {
                if (currentTab === 'signin') {
                    await TechEconAuth.signIn(email, password);
                    showToast('Welcome back!');
                } else {
                    await TechEconAuth.signUp(email, password);
                    showToast('Check your email to confirm your account');
                }
                TechEconAuth.hideModal();
                form.reset();
            } catch (err) {
                errorEl.textContent = err.message || 'An error occurred';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = currentTab === 'signin' ? 'Sign In' : 'Sign Up';
            }
        });
    }

    // Toast notification
    function showToast(message, type = 'success') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    window.showToast = showToast;

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createAuthUI);
    } else {
        createAuthUI();
    }
})();
