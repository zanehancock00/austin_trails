// Austin Trails Web App JavaScript

let currentSegments = [];

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    // Set up event listeners
    document.getElementById('applyFilters').addEventListener('click', loadSegments);
    document.getElementById('resetFilters').addEventListener('click', resetFilters);
    document.getElementById('refreshData').addEventListener('click', refreshData);

    // Load segments on page load
    loadSegments();
});

// Load segments with current filter settings
async function loadSegments() {
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const segmentsList = document.getElementById('segmentsList');

    // Show loading
    loading.style.display = 'block';
    error.style.display = 'none';
    segmentsList.innerHTML = '';

    // Get filter values
    const params = new URLSearchParams({
        min_elevation: document.getElementById('minElevation').value,
        max_elevation: document.getElementById('maxElevation').value,
        min_distance: document.getElementById('minDistance').value,
        max_distance: document.getElementById('maxDistance').value,
        max_distance_from_cedar: document.getElementById('maxDistanceFromCedar').value,
        sort_by: document.getElementById('sortBy').value
    });

    try {
        const response = await fetch(`/api/segments?${params}`);
        const data = await response.json();

        loading.style.display = 'none';

        if (data.error) {
            error.textContent = data.error;
            error.style.display = 'block';
            return;
        }

        currentSegments = data.segments;
        displaySegments(data.segments);
        updateResultsCount(data.total);

    } catch (err) {
        loading.style.display = 'none';
        error.textContent = `Error loading segments: ${err.message}`;
        error.style.display = 'block';
    }
}

// Display segments in the UI
function displaySegments(segments) {
    const segmentsList = document.getElementById('segmentsList');

    if (segments.length === 0) {
        segmentsList.innerHTML = '<div class="loading">No segments match your filters. Try adjusting the criteria.</div>';
        return;
    }

    segmentsList.innerHTML = segments.map(seg => createSegmentCard(seg)).join('');

    // Add click listeners to cards
    document.querySelectorAll('.segment-card').forEach(card => {
        card.addEventListener('click', function() {
            const url = this.dataset.url;
            window.open(url, '_blank');
        });
    });
}

// Create HTML for a segment card
function createSegmentCard(segment) {
    const name = segment.name || 'Unnamed Segment';
    const elevation = segment.elev_difference || 0;
    const distance = segment.distance_km || 0;
    const grade = segment.avg_grade || 0;
    const elevationPerKm = segment.elevation_per_km || 0;
    const distanceFromCedar = segment.distance_from_cedar_park;
    const category = segment.climb_category_desc || 'N/A';
    const city = segment.city || 'Unknown';
    const state = segment.state || '';
    const url = segment.strava_url;

    // Determine grade indicator
    let gradeClass = '';
    if (Math.abs(grade) > 8) gradeClass = 'warning';
    else if (Math.abs(grade) > 5) gradeClass = 'highlight';

    return `
        <div class="segment-card" data-url="${url}">
            <div class="segment-header">
                <div class="segment-name">${escapeHtml(name)}</div>
                <div class="segment-category">${category}</div>
            </div>

            <div class="segment-stats">
                <div class="stat">
                    <div class="stat-label">Elevation Gain</div>
                    <div class="stat-value highlight">${elevation.toFixed(0)} m</div>
                </div>

                <div class="stat">
                    <div class="stat-label">Distance</div>
                    <div class="stat-value">${distance.toFixed(2)} km</div>
                </div>

                <div class="stat">
                    <div class="stat-label">Average Grade</div>
                    <div class="stat-value ${gradeClass}">${grade.toFixed(1)}%</div>
                </div>

                <div class="stat">
                    <div class="stat-label">Intensity</div>
                    <div class="stat-value">${elevationPerKm.toFixed(0)} m/km</div>
                </div>

                ${distanceFromCedar !== null ? `
                <div class="stat">
                    <div class="stat-label">From Cedar Park</div>
                    <div class="stat-value">${distanceFromCedar.toFixed(1)} km</div>
                </div>
                ` : ''}
            </div>

            <div class="segment-location">
                📍 ${escapeHtml(city)}${state ? ', ' + state : ''}
            </div>

            <a href="${url}" target="_blank" class="segment-link" onclick="event.stopPropagation()">
                View on Strava →
            </a>
        </div>
    `;
}

// Update results count
function updateResultsCount(count) {
    const resultsCount = document.getElementById('resultsCount');
    resultsCount.textContent = `${count} segment${count !== 1 ? 's' : ''} found`;
}

// Reset filters to defaults
function resetFilters() {
    document.getElementById('minElevation').value = 30;
    document.getElementById('maxElevation').value = 300;
    document.getElementById('minDistance').value = 0;
    document.getElementById('maxDistance').value = 15;
    document.getElementById('maxDistanceFromCedar').value = 30;
    document.getElementById('sortBy').value = 'elevation';

    loadSegments();
}

// Refresh data from Strava
async function refreshData() {
    const btn = document.getElementById('refreshData');
    const originalText = btn.textContent;

    btn.textContent = 'Refreshing...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/refresh');
        const data = await response.json();

        if (data.status === 'refreshed') {
            loadSegments();
        }
    } catch (err) {
        alert('Error refreshing data: ' + err.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
