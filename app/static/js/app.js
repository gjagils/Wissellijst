// API Base URL
const API_BASE = window.location.origin;

// Tab management
function showTab(tabName) {
    // Hide all content
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));

    // Remove active state from all tabs
    document.querySelectorAll('.tab-button').forEach(el => {
        el.classList.remove('border-indigo-500', 'text-indigo-600');
        el.classList.add('border-transparent', 'text-gray-500');
    });

    // Show selected content
    document.getElementById(`content-${tabName}`).classList.remove('hidden');

    // Add active state to selected tab
    const tabButton = document.getElementById(`tab-${tabName}`);
    tabButton.classList.remove('border-transparent', 'text-gray-500');
    tabButton.classList.add('border-indigo-500', 'text-indigo-600');

    // Load data for the tab
    if (tabName === 'dashboard') loadDashboard();
    if (tabName === 'playlists') loadPlaylists();
    if (tabName === 'scheduler') loadSchedulerJobs();
}

// Load dashboard stats
async function loadDashboard() {
    try {
        // Load playlists count
        const playlistsResp = await fetch(`${API_BASE}/playlists`);
        const playlists = await playlistsResp.json();
        document.getElementById('stat-playlists').textContent = playlists.length;

        // Load scheduler jobs count
        const jobsResp = await fetch(`${API_BASE}/scheduler/jobs`);
        const jobs = await jobsResp.json();
        document.getElementById('stat-jobs').textContent = jobs.total || 0;

        // Load recent runs (from first playlist)
        if (playlists.length > 0) {
            const runsResp = await fetch(`${API_BASE}/playlists/${playlists[0].key}/runs?limit=5`);
            const runs = await runsResp.json();

            const pendingCount = runs.runs.filter(r => r.status === 'preview').length;
            document.getElementById('stat-pending').textContent = pendingCount;

            displayRecentRuns(runs.runs);
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function displayRecentRuns(runs) {
    const container = document.getElementById('recent-runs');

    if (runs.length === 0) {
        container.innerHTML = '<p class="text-gray-500">No recent runs</p>';
        return;
    }

    container.innerHTML = runs.map(run => `
        <div class="border-l-4 ${getStatusColor(run.status)} pl-4 py-2">
            <div class="flex justify-between items-start">
                <div>
                    <div class="font-medium">Run #${run.id}</div>
                    <div class="text-sm text-gray-500">
                        ${new Date(run.created_at).toLocaleString()}
                    </div>
                </div>
                <span class="px-2 py-1 text-xs rounded-full ${getStatusBadge(run.status)}">
                    ${run.status}
                </span>
            </div>
        </div>
    `).join('');
}

// Load playlists
async function loadPlaylists() {
    try {
        const response = await fetch(`${API_BASE}/playlists`);
        const playlists = await response.json();

        const container = document.getElementById('playlists-list');
        const select = document.getElementById('run-playlist-select');

        if (playlists.length === 0) {
            container.innerHTML = '<p class="px-6 py-4 text-gray-500">No playlists found</p>';
            return;
        }

        // Update select dropdown
        select.innerHTML = '<option value="">-- Select Playlist --</option>' +
            playlists.map(p => `<option value="${p.key}">${p.name || p.key}</option>`).join('');

        // Display playlists
        container.innerHTML = playlists.map(playlist => `
            <div class="px-6 py-4">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <h3 class="text-lg font-medium text-gray-900">${playlist.name || playlist.key}</h3>
                        <p class="text-sm text-gray-500 mt-1">${playlist.vibe || 'Geen beschrijving'}</p>
                        <p class="text-xs text-gray-400 mt-1">
                            Schedule: ${playlist.refresh_schedule || 'Handmatig'} |
                            Auto-commit: ${playlist.is_auto_commit ? 'Ja' : 'Nee'}
                        </p>
                        <div class="mt-3 flex flex-wrap gap-2">
                            <button onclick="triggerRefresh('${playlist.key}', false)" class="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">
                                Preview Run
                            </button>
                            <button onclick="triggerRefresh('${playlist.key}', true)" class="text-sm bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700">
                                Auto-commit Run
                            </button>
                            <button onclick="showEditRulesModal('${playlist.key}', '${(playlist.name || playlist.key).replace(/'/g, "\\'")}')" class="text-sm bg-gray-600 text-white px-3 py-1 rounded hover:bg-gray-700">
                                Regels
                            </button>
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="text-xs text-gray-400">Key: ${playlist.key}</span>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading playlists:', error);
        document.getElementById('playlists-list').innerHTML =
            '<p class="px-6 py-4 text-red-500">Error loading playlists</p>';
    }
}

// Trigger manual refresh
async function triggerRefresh(playlistKey, autoCommit) {
    if (!confirm(`Trigger refresh for "${playlistKey}"${autoCommit ? ' with auto-commit' : ''}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/scheduler/refresh/${playlistKey}?auto_commit=${autoCommit}`, {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            alert(`Refresh triggered! Run ID: ${result.run_id}\nStatus: ${result.status}`);
            loadDashboard();
        } else {
            alert(`Error: ${result.message}`);
        }
    } catch (error) {
        alert(`Error triggering refresh: ${error.message}`);
    }
}

// Load playlist runs
async function loadPlaylistRuns() {
    const select = document.getElementById('run-playlist-select');
    const playlistKey = select.value;

    if (!playlistKey) {
        document.getElementById('runs-list').innerHTML =
            '<p class="px-6 py-4 text-gray-500">Select a playlist to view runs</p>';
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/playlists/${playlistKey}/runs?limit=20`);
        const data = await response.json();

        const container = document.getElementById('runs-list');

        if (data.runs.length === 0) {
            container.innerHTML = '<p class="px-6 py-4 text-gray-500">No runs found</p>';
            return;
        }

        container.innerHTML = data.runs.map(run => `
            <div class="px-6 py-4 hover:bg-gray-50 cursor-pointer" onclick="viewRunDetails(${run.id})">
                <div class="flex justify-between items-center">
                    <div>
                        <div class="font-medium">Run #${run.id}</div>
                        <div class="text-sm text-gray-500">
                            ${new Date(run.created_at).toLocaleString()}
                        </div>
                    </div>
                    <span class="px-2 py-1 text-xs rounded-full ${getStatusBadge(run.status)}">
                        ${run.status}
                    </span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading runs:', error);
    }
}

// View run details
async function viewRunDetails(runId) {
    try {
        const response = await fetch(`${API_BASE}/runs/${runId}/changes`);
        const data = await response.json();

        const container = document.getElementById('run-content');
        const detailsDiv = document.getElementById('run-details');

        detailsDiv.classList.remove('hidden');

        container.innerHTML = `
            <div class="space-y-6">
                <div>
                    <h3 class="text-lg font-medium mb-3">Removes (${data.removes.length})</h3>
                    <div class="space-y-2">
                        ${data.removes.map(change => `
                            <div class="border rounded p-3">
                                <div class="font-medium">${change.artist} - ${change.title}</div>
                                <div class="text-sm text-gray-500">Block ${change.block_index}, Position ${change.position_in_block}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div>
                    <h3 class="text-lg font-medium mb-3">Adds (${data.adds.length})</h3>
                    <div class="space-y-2">
                        ${data.adds.map(change => `
                            <div class="border rounded p-3 ${change.is_approved ? 'bg-green-50' : 'bg-yellow-50'}">
                                <div class="flex justify-between items-start">
                                    <div class="flex-1">
                                        <div class="font-medium">${change.artist} - ${change.title}</div>
                                        <div class="text-sm text-gray-600 mt-1">${change.suggested_reason || 'AI suggested'}</div>
                                        <div class="text-sm text-gray-500 mt-1">
                                            ${change.year || '?'} | ${change.decade || '?'}s | ${change.language || '?'}
                                        </div>
                                    </div>
                                    <div class="ml-4">
                                        ${change.is_approved ?
                                            '<span class="text-green-600">✓ Approved</span>' :
                                            `<button onclick="approveChange(${change.id}, true)" class="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700">Approve</button>`
                                        }
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="flex gap-3">
                    <button onclick="commitRun(${runId})" class="bg-indigo-600 text-white px-6 py-2 rounded-md hover:bg-indigo-700">
                        Commit Run
                    </button>
                    <button onclick="cancelRun(${runId})" class="bg-red-600 text-white px-6 py-2 rounded-md hover:bg-red-700">
                        Cancel Run
                    </button>
                </div>
            </div>
        `;

        container.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error loading run details:', error);
        alert('Error loading run details');
    }
}

// Approve change
async function approveChange(changeId, isApproved) {
    try {
        const response = await fetch(`${API_BASE}/runs/0/changes/${changeId}/approve`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_approved: isApproved })
        });

        if (response.ok) {
            // Reload current run details
            const runId = parseInt(document.getElementById('run-content').querySelector('[onclick*="commitRun"]').getAttribute('onclick').match(/\d+/)[0]);
            viewRunDetails(runId);
        } else {
            alert('Error approving change');
        }
    } catch (error) {
        console.error('Error approving change:', error);
        alert('Error approving change');
    }
}

// Commit run
async function commitRun(runId) {
    if (!confirm(`Commit run #${runId}? This will update the Spotify playlist.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/runs/${runId}/commit`, {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            alert(`Run committed successfully!\n\nRemoved ${result.removed_tracks.length} tracks\nAdded ${result.added_tracks.length} tracks`);
            loadPlaylistRuns();
            document.getElementById('run-details').classList.add('hidden');
        } else {
            alert(`Error: ${result.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error committing run:', error);
        alert('Error committing run');
    }
}

// Cancel run
async function cancelRun(runId) {
    if (!confirm(`Cancel run #${runId}?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/runs/${runId}`, {
            method: 'DELETE'
        });
        const result = await response.json();

        if (result.success) {
            alert('Run cancelled');
            loadPlaylistRuns();
            document.getElementById('run-details').classList.add('hidden');
        } else {
            alert('Error cancelling run');
        }
    } catch (error) {
        console.error('Error cancelling run:', error);
        alert('Error cancelling run');
    }
}

// Load scheduler jobs
async function loadSchedulerJobs() {
    try {
        const response = await fetch(`${API_BASE}/scheduler/jobs`);
        const data = await response.json();

        const container = document.getElementById('scheduler-jobs');

        if (data.total === 0) {
            container.innerHTML = '<p class="text-gray-500">No scheduled jobs</p>';
            return;
        }

        container.innerHTML = data.jobs.map(job => `
            <div class="border rounded-lg p-4">
                <div class="flex justify-between items-start">
                    <div>
                        <div class="font-medium">${job.name}</div>
                        <div class="text-sm text-gray-500 mt-1">${job.trigger}</div>
                    </div>
                    <div class="text-right">
                        <div class="text-sm font-medium">Next Run</div>
                        <div class="text-sm text-gray-600">
                            ${job.next_run ? new Date(job.next_run).toLocaleString() : 'N/A'}
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading scheduler jobs:', error);
        document.getElementById('scheduler-jobs').innerHTML =
            '<p class="text-red-500">Error loading scheduler jobs</p>';
    }
}

// Reload scheduler
async function reloadScheduler() {
    try {
        const response = await fetch(`${API_BASE}/scheduler/reload`, {
            method: 'POST'
        });
        const result = await response.json();

        alert(`Scheduler reloaded: ${result.message}`);
        loadSchedulerJobs();
    } catch (error) {
        console.error('Error reloading scheduler:', error);
        alert('Error reloading scheduler');
    }
}

// Helper functions
function getStatusColor(status) {
    switch(status) {
        case 'preview': return 'border-yellow-500';
        case 'committed': return 'border-green-500';
        case 'cancelled': return 'border-red-500';
        default: return 'border-gray-500';
    }
}

function getStatusBadge(status) {
    switch(status) {
        case 'preview': return 'bg-yellow-100 text-yellow-800';
        case 'committed': return 'bg-green-100 text-green-800';
        case 'cancelled': return 'bg-red-100 text-red-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}

// ============================================================
// Add Playlist Modal
// ============================================================

async function showAddPlaylistModal() {
    document.getElementById('add-playlist-modal').classList.remove('hidden');

    // Load Spotify playlists
    const select = document.getElementById('spotify-playlist-select');
    select.innerHTML = '<option value="">Laden...</option>';

    try {
        const response = await fetch(`${API_BASE}/spotify/playlists`);
        const playlists = await response.json();

        select.innerHTML = '<option value="">-- Selecteer een Spotify playlist --</option>' +
            playlists.map(p => `<option value="${p.id}" data-name="${p.name}">${p.name} (${p.tracks_total} tracks)</option>`).join('');

        // Auto-fill name when selecting
        select.onchange = function() {
            const option = this.options[this.selectedIndex];
            if (option.value) {
                document.getElementById('playlist-name').value = option.dataset.name || '';
                document.getElementById('playlist-key').value = (option.dataset.name || '')
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, '-')
                    .replace(/^-|-$/g, '');
            }
        };
    } catch (error) {
        console.error('Error loading Spotify playlists:', error);
        select.innerHTML = '<option value="">Fout bij laden playlists</option>';
    }
}

function hideAddPlaylistModal() {
    document.getElementById('add-playlist-modal').classList.add('hidden');
    document.getElementById('add-playlist-form').reset();
}

async function submitAddPlaylist(event) {
    event.preventDefault();

    const spotifyPlaylistId = document.getElementById('spotify-playlist-select').value;
    const name = document.getElementById('playlist-name').value;
    const key = document.getElementById('playlist-key').value;
    const vibe = document.getElementById('playlist-vibe').value;
    const schedule = document.getElementById('playlist-schedule').value || null;
    const autoCommit = document.getElementById('playlist-autocommit').checked;

    // Rules
    const blockSize = parseInt(document.getElementById('rule-block-size').value);
    const blockCount = parseInt(document.getElementById('rule-block-count').value);
    const maxArtist = parseInt(document.getElementById('rule-max-artist').value);
    const noRepeat = document.getElementById('rule-no-repeat').checked;

    // Decade distribution
    const decadeDistribution = {
        1980: parseInt(document.getElementById('decade-80').value),
        1990: parseInt(document.getElementById('decade-90').value),
        2000: parseInt(document.getElementById('decade-00').value),
        2010: parseInt(document.getElementById('decade-10').value),
        2020: parseInt(document.getElementById('decade-20').value),
    };

    try {
        // Create playlist
        const playlistResponse = await fetch(`${API_BASE}/playlists`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                key: key,
                name: name,
                spotify_playlist_id: spotifyPlaylistId,
                vibe: vibe,
                refresh_schedule: schedule,
                is_auto_commit: autoCommit,
            }),
        });

        if (!playlistResponse.ok) {
            const error = await playlistResponse.json();
            throw new Error(error.detail || 'Fout bij aanmaken playlist');
        }

        // Update rules
        const rulesResponse = await fetch(`${API_BASE}/playlists/${key}/rules`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                block_size: blockSize,
                block_count: blockCount,
                max_tracks_per_artist: maxArtist,
                no_repeat_ever: noRepeat,
                candidate_policies: {
                    decade_distribution: decadeDistribution,
                },
            }),
        });

        if (!rulesResponse.ok) {
            console.warn('Failed to update rules, using defaults');
        }

        hideAddPlaylistModal();
        loadPlaylists();
        alert(`Playlist "${name}" succesvol aangemaakt!`);

    } catch (error) {
        console.error('Error creating playlist:', error);
        alert(`Fout: ${error.message}`);
    }
}

// ============================================================
// Edit Rules Modal
// ============================================================

async function showEditRulesModal(playlistKey, playlistName) {
    document.getElementById('edit-rules-modal').classList.remove('hidden');
    document.getElementById('edit-rules-playlist-key').value = playlistKey;
    document.getElementById('edit-rules-playlist-name').textContent = playlistName;

    try {
        const response = await fetch(`${API_BASE}/playlists/${playlistKey}/rules`);
        const rules = await response.json();

        document.getElementById('edit-block-size').value = rules.block_size || 5;
        document.getElementById('edit-block-count').value = rules.block_count || 10;
        document.getElementById('edit-max-artist').value = rules.max_tracks_per_artist || 1;
        document.getElementById('edit-no-repeat').checked = rules.no_repeat_ever !== false;

        const decades = rules.candidate_policies?.decade_distribution || {};
        document.getElementById('edit-decade-80').value = decades[1980] || 1;
        document.getElementById('edit-decade-90').value = decades[1990] || 1;
        document.getElementById('edit-decade-00').value = decades[2000] || 1;
        document.getElementById('edit-decade-10').value = decades[2010] || 1;
        document.getElementById('edit-decade-20').value = decades[2020] || 1;

    } catch (error) {
        console.error('Error loading rules:', error);
    }
}

function hideEditRulesModal() {
    document.getElementById('edit-rules-modal').classList.add('hidden');
}

async function submitEditRules(event) {
    event.preventDefault();

    const playlistKey = document.getElementById('edit-rules-playlist-key').value;

    const decadeDistribution = {
        1980: parseInt(document.getElementById('edit-decade-80').value),
        1990: parseInt(document.getElementById('edit-decade-90').value),
        2000: parseInt(document.getElementById('edit-decade-00').value),
        2010: parseInt(document.getElementById('edit-decade-10').value),
        2020: parseInt(document.getElementById('edit-decade-20').value),
    };

    try {
        const response = await fetch(`${API_BASE}/playlists/${playlistKey}/rules`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                block_size: parseInt(document.getElementById('edit-block-size').value),
                block_count: parseInt(document.getElementById('edit-block-count').value),
                max_tracks_per_artist: parseInt(document.getElementById('edit-max-artist').value),
                no_repeat_ever: document.getElementById('edit-no-repeat').checked,
                candidate_policies: {
                    decade_distribution: decadeDistribution,
                },
            }),
        });

        if (!response.ok) {
            throw new Error('Fout bij opslaan regels');
        }

        hideEditRulesModal();
        alert('Regels opgeslagen!');

    } catch (error) {
        console.error('Error saving rules:', error);
        alert(`Fout: ${error.message}`);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});
