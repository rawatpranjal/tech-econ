// Auth UI for Tech-Econ
// Login/signup modal and user menu

(function() {
    'use strict';

    // Create and inject auth UI elements
    function createAuthUI() {
        // Top-right profile button
        const profileBtn = document.getElementById('profile-btn');
        const profileDropdown = document.getElementById('profile-dropdown');
        const topBar = document.querySelector('.top-bar');

        if (profileBtn) {
            // Click handler - show modal or toggle dropdown
            profileBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                if (window.TechEconAuth && window.TechEconAuth.isLoggedIn()) {
                    topBar.classList.toggle('dropdown-open');
                } else {
                    window.TechEconAuth.showModal();
                }
            });

            // Sign out from dropdown
            const signoutBtn = document.getElementById('profile-signout');
            if (signoutBtn) {
                signoutBtn.addEventListener('click', async function() {
                    try {
                        await window.TechEconAuth.signOut();
                        topBar.classList.remove('dropdown-open');
                        showToast('Signed out successfully');
                    } catch (e) {
                        showToast('Error signing out', 'error');
                    }
                });
            }

            // Close dropdown when clicking outside
            document.addEventListener('click', function(e) {
                if (topBar && !topBar.contains(e.target)) {
                    topBar.classList.remove('dropdown-open');
                }
            });
        }

        // Update profile button state based on auth
        window.updateProfileButton = function(user) {
            const profileIcon = document.querySelector('.profile-icon');
            const profileInitial = document.querySelector('.profile-initial');
            const profileEmail = document.getElementById('profile-email');

            if (user) {
                // Logged in - show initial
                const initial = user.email ? user.email.charAt(0).toUpperCase() : 'U';
                if (profileIcon) profileIcon.style.display = 'none';
                if (profileInitial) {
                    profileInitial.style.display = 'flex';
                    profileInitial.textContent = initial;
                }
                if (profileEmail) profileEmail.textContent = user.email;
                if (profileBtn) profileBtn.classList.add('logged-in');
            } else {
                // Logged out - show icon
                if (profileIcon) profileIcon.style.display = 'block';
                if (profileInitial) profileInitial.style.display = 'none';
                if (profileBtn) profileBtn.classList.remove('logged-in');
                if (topBar) topBar.classList.remove('dropdown-open');
            }
        };

        // Legacy sidebar auth button (keeping for compatibility)
        const sidebarFooter = document.querySelector('.sidebar-footer');
        if (sidebarFooter) {
            // Remove old sidebar auth elements if they exist
            const oldAuthBtn = document.getElementById('auth-btn');
            const oldUserMenu = document.getElementById('user-menu');
            if (oldAuthBtn) oldAuthBtn.remove();
            if (oldUserMenu) oldUserMenu.remove();
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

                <div class="auth-confirmation" id="auth-confirmation" style="display: none;">
                    <div class="auth-confirmation-icon">
                        <svg viewBox="0 0 24 24" width="64" height="64" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                            <polyline points="22 4 12 14.01 9 11.01"></polyline>
                        </svg>
                    </div>
                    <h2 class="auth-confirmation-title">Check your email!</h2>
                    <p class="auth-confirmation-text">We sent a confirmation link to <strong id="auth-confirmation-email"></strong></p>
                    <p class="auth-confirmation-subtext">Click the link in the email to complete your signup.</p>
                    <button class="auth-confirmation-close" id="auth-confirmation-close">Got it</button>
                </div>
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
            if (window.TechEconAuth && TechEconAuth.hideModal) {
                TechEconAuth.hideModal();
            }
        });

        closeBtn.addEventListener('click', function() {
            if (window.TechEconAuth && TechEconAuth.hideModal) {
                TechEconAuth.hideModal();
            }
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.classList.contains('open')) {
                if (window.TechEconAuth && TechEconAuth.hideModal) {
                    TechEconAuth.hideModal();
                }
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
                    TechEconAuth.hideModal();
                    form.reset();
                } else {
                    await TechEconAuth.signUp(email, password);
                    // Show confirmation screen instead of closing
                    showSignupConfirmation(email);
                    form.reset();
                }
            } catch (err) {
                errorEl.textContent = err.message || 'An error occurred';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = currentTab === 'signin' ? 'Sign In' : 'Sign Up';
            }
        });

        // Signup confirmation handlers
        const confirmationEl = document.getElementById('auth-confirmation');
        const confirmationCloseBtn = document.getElementById('auth-confirmation-close');
        const authFormWrapper = modal.querySelector('.auth-form');
        const authTabs = modal.querySelector('.auth-tabs');
        const authTitle = modal.querySelector('.auth-modal-title');
        const authSubtitle = modal.querySelector('.auth-modal-subtitle');
        const authFooter = modal.querySelector('.auth-footer');

        function showSignupConfirmation(email) {
            // Hide form elements
            if (authFormWrapper) authFormWrapper.style.display = 'none';
            if (authTabs) authTabs.style.display = 'none';
            if (authTitle) authTitle.style.display = 'none';
            if (authSubtitle) authSubtitle.style.display = 'none';
            if (authFooter) authFooter.style.display = 'none';

            // Show confirmation
            document.getElementById('auth-confirmation-email').textContent = email;
            confirmationEl.style.display = 'block';
        }

        function hideSignupConfirmation() {
            // Show form elements
            if (authFormWrapper) authFormWrapper.style.display = 'block';
            if (authTabs) authTabs.style.display = 'flex';
            if (authTitle) authTitle.style.display = 'block';
            if (authSubtitle) authSubtitle.style.display = 'block';
            if (authFooter) authFooter.style.display = 'block';

            // Hide confirmation
            confirmationEl.style.display = 'none';
        }

        if (confirmationCloseBtn) {
            confirmationCloseBtn.addEventListener('click', function() {
                if (window.TechEconAuth && TechEconAuth.hideModal) {
                    TechEconAuth.hideModal();
                }
                hideSignupConfirmation();
            });
        }

        // Also hide confirmation when modal is closed
        if (window.TechEconAuth && TechEconAuth.hideModal) {
            const originalHideModal = TechEconAuth.hideModal;
            TechEconAuth.hideModal = function() {
                hideSignupConfirmation();
                modal.classList.remove('open');
                document.body.style.overflow = '';
            };
        }

        // Make showSignupConfirmation available
        window.showSignupConfirmation = showSignupConfirmation;
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
