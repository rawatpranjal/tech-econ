// View toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const btnCards = document.getElementById('btn-cards');
    const btnTable = document.getElementById('btn-table');
    const cardsView = document.getElementById('cards-view');
    const tableView = document.getElementById('table-view');

    // Guard clause - exit if required elements missing
    if (!btnCards || !btnTable || !cardsView || !tableView) {
        console.warn('Toggle: Required DOM elements not found');
        return;
    }

    // Load saved preference with fallback
    let savedView = 'cards';
    try {
        savedView = localStorage.getItem('packageView') || 'cards';
    } catch (e) {
        // localStorage unavailable (private browsing)
    }

    function savePreference(view) {
        try {
            localStorage.setItem('packageView', view);
        } catch (e) {
            // Silently fail if localStorage unavailable
        }
    }

    function setView(view) {
        const isCards = view === 'cards';
        cardsView.style.display = isCards ? '' : 'none';
        tableView.style.display = isCards ? 'none' : '';
        btnCards.classList.toggle('active', isCards);
        btnTable.classList.toggle('active', !isCards);
    }

    btnCards.addEventListener('click', function() {
        setView('cards');
        savePreference('cards');
    });

    btnTable.addEventListener('click', function() {
        setView('table');
        savePreference('table');
    });

    // Initialize view based on saved preference
    if (savedView === 'table') {
        setView('table');
    }
});
