// View toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const btnCards = document.getElementById('btn-cards');
    const btnTable = document.getElementById('btn-table');
    const cardsView = document.getElementById('cards-view');
    const tableView = document.getElementById('table-view');

    // Load saved preference
    const savedView = localStorage.getItem('packageView') || 'cards';
    if (savedView === 'table') {
        showTable();
    }

    btnCards.addEventListener('click', function() {
        showCards();
        localStorage.setItem('packageView', 'cards');
    });

    btnTable.addEventListener('click', function() {
        showTable();
        localStorage.setItem('packageView', 'table');
    });

    function showCards() {
        cardsView.style.display = 'flex';
        tableView.style.display = 'none';
        btnCards.classList.add('active');
        btnTable.classList.remove('active');
    }

    function showTable() {
        cardsView.style.display = 'none';
        tableView.style.display = 'block';
        btnCards.classList.remove('active');
        btnTable.classList.add('active');
    }
});
