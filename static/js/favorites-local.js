// LocalStorage-based Favorites for Tech-Econ
// No login required - saves directly to browser

(function() {
    'use strict';

    const STORAGE_KEY = 'techEconFavorites';

    // Get all favorites from localStorage
    function getFavorites() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        } catch (e) {
            console.error('Error reading favorites:', e);
            return [];
        }
    }

    // Save favorites to localStorage
    function saveFavorites(favs) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(favs));
        } catch (e) {
            console.error('Error saving favorites:', e);
        }
    }

    // Add a favorite
    function addFavorite(itemType, itemId, itemData) {
        const favs = getFavorites();
        // Check if already exists
        if (favs.some(f => f.type === itemType && f.id === itemId)) {
            return false; // Already exists
        }
        favs.push({
            type: itemType,
            id: itemId,
            data: itemData || {},
            addedAt: Date.now()
        });
        saveFavorites(favs);
        updateFavoritesCount();
        return true;
    }

    // Remove a favorite
    function removeFavorite(itemType, itemId) {
        const favs = getFavorites().filter(f => !(f.type === itemType && f.id === itemId));
        saveFavorites(favs);
        updateFavoritesCount();
    }

    // Toggle favorite state
    function toggleFavorite(itemType, itemId, itemData) {
        if (isFavorited(itemType, itemId)) {
            removeFavorite(itemType, itemId);
            return false;
        } else {
            addFavorite(itemType, itemId, itemData);
            return true;
        }
    }

    // Check if item is favorited
    function isFavorited(itemType, itemId) {
        return getFavorites().some(f => f.type === itemType && f.id === itemId);
    }

    // Get favorites count
    function getCount() {
        return getFavorites().length;
    }

    // Update favorites count badge in nav
    function updateFavoritesCount() {
        const count = getCount();
        const badges = document.querySelectorAll('.favorites-count');
        badges.forEach(badge => {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'inline-flex' : 'none';
        });
    }

    // Download helper
    function downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // Export as JSON
    function exportJSON() {
        const favs = getFavorites();
        const data = JSON.stringify(favs, null, 2);
        downloadFile(data, 'my-favorites.json', 'application/json');
    }

    // Export as CSV
    function exportCSV() {
        const favs = getFavorites();
        if (favs.length === 0) {
            alert('No favorites to export');
            return;
        }

        // CSV header
        let csv = 'Type,Name,Category,URL,Added Date\n';

        // CSV rows
        favs.forEach(f => {
            const name = (f.data?.name || f.data?.title || f.id || '').replace(/"/g, '""');
            const category = (f.data?.category || f.type || '').replace(/"/g, '""');
            const url = (f.data?.url || f.data?.link || '').replace(/"/g, '""');
            const date = f.addedAt ? new Date(f.addedAt).toISOString().split('T')[0] : '';
            csv += `"${f.type}","${name}","${category}","${url}","${date}"\n`;
        });

        downloadFile(csv, 'my-favorites.csv', 'text/csv');
    }

    // Clear all favorites
    function clearAll() {
        if (confirm('Are you sure you want to remove all favorites?')) {
            saveFavorites([]);
            updateFavoritesCount();
            return true;
        }
        return false;
    }

    // Initialize count on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateFavoritesCount);
    } else {
        updateFavoritesCount();
    }

    // Expose API globally
    window.TechEconFavorites = {
        get: getFavorites,
        add: addFavorite,
        remove: removeFavorite,
        toggle: toggleFavorite,
        isFavorited: isFavorited,
        count: getCount,
        exportJSON: exportJSON,
        exportCSV: exportCSV,
        clearAll: clearAll,
        updateCount: updateFavoritesCount
    };

})();
