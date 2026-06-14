// LocalStorage-based Playlists for Tech-Econ
// No login required - saves directly to browser

(function() {
    'use strict';

    const STORAGE_KEY = 'techEconPlaylists';

    // Get all playlists from localStorage
    function getPlaylists() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        } catch (e) {
            console.error('Error reading playlists:', e);
            return [];
        }
    }

    // Save playlists to localStorage
    function savePlaylists(playlists) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(playlists));
        } catch (e) {
            console.error('Error saving playlists:', e);
        }
    }

    // Create a new playlist
    function createPlaylist(name) {
        const playlists = getPlaylists();
        const newPlaylist = {
            id: 'playlist-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7),
            name: name || 'Untitled Playlist',
            createdAt: Date.now(),
            items: []
        };
        playlists.push(newPlaylist);
        savePlaylists(playlists);
        updatePlaylistsCount();
        return newPlaylist.id;
    }

    // Delete a playlist
    function deletePlaylist(id) {
        const playlists = getPlaylists().filter(p => p.id !== id);
        savePlaylists(playlists);
        updatePlaylistsCount();
    }

    // Rename a playlist
    function renamePlaylist(id, newName) {
        const playlists = getPlaylists();
        const playlist = playlists.find(p => p.id === id);
        if (playlist) {
            playlist.name = newName;
            savePlaylists(playlists);
        }
    }

    // Get a single playlist by ID
    function getPlaylist(id) {
        return getPlaylists().find(p => p.id === id) || null;
    }

    // Add item to a playlist
    function addItem(playlistId, itemType, itemId, itemData) {
        const playlists = getPlaylists();
        const playlist = playlists.find(p => p.id === playlistId);
        if (!playlist) return false;

        // Check if item already exists
        if (playlist.items.some(item => item.type === itemType && item.id === itemId)) {
            return false; // Already exists
        }

        playlist.items.push({
            type: itemType,
            id: itemId,
            data: itemData || {},
            addedAt: Date.now()
        });
        savePlaylists(playlists);
        return true;
    }

    // Remove item from a playlist
    function removeItem(playlistId, itemType, itemId) {
        const playlists = getPlaylists();
        const playlist = playlists.find(p => p.id === playlistId);
        if (!playlist) return;

        playlist.items = playlist.items.filter(item =>
            !(item.type === itemType && item.id === itemId)
        );
        savePlaylists(playlists);
    }

    // Get playlists count
    function getCount() {
        return getPlaylists().length;
    }

    // Update playlists count badge in nav
    function updatePlaylistsCount() {
        const count = getCount();
        const badges = document.querySelectorAll('.playlists-count');
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

    // Export a playlist as CSV
    function exportCSV(playlistId) {
        const playlist = getPlaylist(playlistId);
        if (!playlist) {
            alert('Playlist not found');
            return;
        }

        if (playlist.items.length === 0) {
            alert('Playlist is empty');
            return;
        }

        // CSV header with playlist name
        let csv = 'Playlist: ' + playlist.name + '\n';
        csv += 'Type,Name,URL,Category,Added Date\n';

        // CSV rows
        playlist.items.forEach(item => {
            const name = (item.data?.name || item.id || '').replace(/"/g, '""');
            const url = (item.data?.url || '').replace(/"/g, '""');
            const category = (item.data?.category || item.type || '').replace(/"/g, '""');
            const date = item.addedAt ? new Date(item.addedAt).toISOString().split('T')[0] : '';
            csv += `"${item.type}","${name}","${url}","${category}","${date}"\n`;
        });

        const filename = playlist.name.toLowerCase().replace(/[^a-z0-9]+/g, '-') + '.csv';
        downloadFile(csv, filename, 'text/csv');
    }

    // Import a playlist from CSV file
    function importCSV(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = function(e) {
                try {
                    const content = e.target.result;
                    const lines = content.split('\n').filter(line => line.trim());

                    if (lines.length < 2) {
                        reject(new Error('CSV file is empty or invalid'));
                        return;
                    }

                    // Parse playlist name from first line
                    let playlistName = 'Imported Playlist';
                    let startLine = 0;

                    if (lines[0].toLowerCase().startsWith('playlist:')) {
                        playlistName = lines[0].substring(9).trim();
                        startLine = 1;
                    }

                    // Skip header row if present
                    if (lines[startLine] && lines[startLine].toLowerCase().includes('type,')) {
                        startLine++;
                    }

                    // Create new playlist
                    const playlistId = createPlaylist(playlistName);
                    let importedCount = 0;

                    // Parse items
                    for (let i = startLine; i < lines.length; i++) {
                        const line = lines[i].trim();
                        if (!line) continue;

                        // Parse CSV line (handling quoted values)
                        const values = parseCSVLine(line);
                        if (values.length >= 3) {
                            const type = values[0] || 'resource';
                            const name = values[1];
                            const url = values[2];
                            const category = values[3] || type;

                            if (name || url) {
                                addItem(playlistId, type, name, {
                                    name: name,
                                    url: url,
                                    category: category
                                });
                                importedCount++;
                            }
                        }
                    }

                    resolve({
                        playlistId: playlistId,
                        playlistName: playlistName,
                        itemCount: importedCount
                    });
                } catch (err) {
                    reject(err);
                }
            };

            reader.onerror = function() {
                reject(new Error('Failed to read file'));
            };

            reader.readAsText(file);
        });
    }

    // Parse a CSV line handling quoted values
    function parseCSVLine(line) {
        const values = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const char = line[i];

            if (char === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    current += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                values.push(current.trim());
                current = '';
            } else {
                current += char;
            }
        }
        values.push(current.trim());

        return values;
    }

    // Initialize count on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updatePlaylistsCount);
    } else {
        updatePlaylistsCount();
    }

    // Expose API globally
    window.TechEconPlaylists = {
        getAll: getPlaylists,
        create: createPlaylist,
        delete: deletePlaylist,
        rename: renamePlaylist,
        get: getPlaylist,
        addItem: addItem,
        removeItem: removeItem,
        exportCSV: exportCSV,
        importCSV: importCSV,
        count: getCount,
        updateCount: updatePlaylistsCount
    };

})();
