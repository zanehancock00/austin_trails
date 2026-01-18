// Austin Trails Web App JavaScript

let currentSegments = [];

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    // Set up event listeners
    document.getElementById('applyFilters').addEventListener('click', loadSegments);
    document.getElementById('resetFilters').addEventListener('click', resetFilters);
    document.getElementById('refreshData').addEventListener('click', refreshData);
    document.getElementById('dataSource').addEventListener('change', loadSegments);

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

    const dataSource = document.getElementById('dataSource').value;

    // Get filter values (convert from imperial to metric for API)
    const minElevationFeet = parseFloat(document.getElementById('minElevation').value);
    const maxElevationFeet = parseFloat(document.getElementById('maxElevation').value);
    const minDistanceMiles = parseFloat(document.getElementById('minDistance').value);
    const maxDistanceMiles = parseFloat(document.getElementById('maxDistance').value);
    const maxDistanceFromCedarMiles = parseFloat(document.getElementById('maxDistanceFromCedar').value);

    const params = new URLSearchParams({
        min_elevation: (minElevationFeet / 3.28084).toFixed(2),
        max_elevation: (maxElevationFeet / 3.28084).toFixed(2),
        min_distance: (minDistanceMiles / 0.621371).toFixed(2),
        max_distance: (maxDistanceMiles / 0.621371).toFixed(2),
        max_distance_from_cedar: (maxDistanceFromCedarMiles / 0.621371).toFixed(2),
        sort_by: document.getElementById('sortBy').value
    });

    try {
        let allItems = [];

        // Fetch segments if needed
        if (dataSource === 'segments' || dataSource === 'both') {
            const segmentResponse = await fetch(`/api/segments?${params}`);
            const segmentData = await segmentResponse.json();

            if (segmentData.error) {
                error.textContent = segmentData.error;
                error.style.display = 'block';
            } else {
                allItems = allItems.concat(segmentData.segments.map(s => ({...s, is_route: false})));
            }
        }

        // Fetch routes if needed
        if (dataSource === 'routes' || dataSource === 'both') {
            const routeResponse = await fetch('/api/routes');
            const routeData = await routeResponse.json();

            if (routeData.error) {
                console.warn('Route error:', routeData.error);
                if (dataSource === 'routes') {
                    error.textContent = routeData.error;
                    error.style.display = 'block';
                }
            } else {
                // Filter routes client-side
                const filteredRoutes = routeData.routes.filter(route => {
                    const elev = route.elev_difference || 0;
                    const dist = route.distance_km || 0;
                    const minElev = minElevationFeet / 3.28084;
                    const maxElev = maxElevationFeet / 3.28084;
                    const minDist = minDistanceMiles / 0.621371;
                    const maxDist = maxDistanceMiles / 0.621371;

                    return elev >= minElev && elev <= maxElev &&
                           dist >= minDist && dist <= maxDist;
                });
                allItems = allItems.concat(filteredRoutes.map(r => ({...r, is_route: true})));
            }
        }

        // Sort combined results
        const sortBy = document.getElementById('sortBy').value;
        sortItems(allItems, sortBy);

        loading.style.display = 'none';
        currentSegments = allItems;
        displaySegments(allItems);
        updateResultsCount(allItems.length);

    } catch (err) {
        loading.style.display = 'none';
        error.textContent = `Error loading data: ${err.message}`;
        error.style.display = 'block';
    }
}

// Sort items based on selected criteria
function sortItems(items, sortBy) {
    if (sortBy === 'elevation_desc') {
        items.sort((a, b) => (b.elev_difference || 0) - (a.elev_difference || 0));
    } else if (sortBy === 'elevation_asc') {
        items.sort((a, b) => (a.elev_difference || 0) - (b.elev_difference || 0));
    } else if (sortBy === 'distance_desc') {
        items.sort((a, b) => (b.distance_km || 0) - (a.distance_km || 0));
    } else if (sortBy === 'distance_asc') {
        items.sort((a, b) => (a.distance_km || 0) - (b.distance_km || 0));
    } else if (sortBy === 'elevation_per_km') {
        items.sort((a, b) => (b.elevation_per_km || 0) - (a.elevation_per_km || 0));
    } else if (sortBy === 'distance_from_cedar') {
        items.sort((a, b) => (a.distance_from_cedar_park || 999) - (b.distance_from_cedar_park || 999));
    } else if (sortBy === 'grade') {
        items.sort((a, b) => Math.abs(b.avg_grade || 0) - Math.abs(a.avg_grade || 0));
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
    const isRoute = segment.is_route || false;
    const name = segment.name || (isRoute ? 'Unnamed Route' : 'Unnamed Segment');
    const elevationFeet = segment.elev_difference_feet || 0;
    const distanceMiles = segment.distance_miles || 0;
    const grade = segment.avg_grade || 0;
    const elevationPerMile = segment.elevation_per_mile || 0;
    const distanceFromCedarMiles = segment.distance_from_cedar_park_miles;
    const category = segment.climb_category_desc || (isRoute ? 'Route' : 'N/A');
    const city = segment.city || 'Unknown';
    const state = segment.state || '';
    const url = segment.strava_url;
    const typeLabel = isRoute ? '🗺️ Route' : '📊 Segment';

    // Determine grade indicator
    let gradeClass = '';
    if (Math.abs(grade) > 8) gradeClass = 'warning';
    else if (Math.abs(grade) > 5) gradeClass = 'highlight';

    return `
        <div class="segment-card" data-url="${url}">
            <div class="segment-header">
                <div class="segment-name">${typeLabel} ${escapeHtml(name)}</div>
                <div class="segment-category">${category}</div>
            </div>

            <div class="segment-stats">
                <div class="stat">
                    <div class="stat-label">Elevation Gain</div>
                    <div class="stat-value highlight">${elevationFeet.toFixed(0)} ft</div>
                </div>

                <div class="stat">
                    <div class="stat-label">Distance</div>
                    <div class="stat-value">${distanceMiles.toFixed(2)} mi</div>
                </div>

                <div class="stat">
                    <div class="stat-label">Average Grade</div>
                    <div class="stat-value ${gradeClass}">${grade.toFixed(1)}%</div>
                </div>

                <div class="stat">
                    <div class="stat-label">Intensity</div>
                    <div class="stat-value">${elevationPerMile.toFixed(0)} ft/mi</div>
                </div>

                ${distanceFromCedarMiles !== null && distanceFromCedarMiles !== undefined ? `
                <div class="stat">
                    <div class="stat-label">From Cedar Park</div>
                    <div class="stat-value">${distanceFromCedarMiles.toFixed(1)} mi</div>
                </div>
                ` : ''}
            </div>

            ${!isRoute && city !== 'Unknown' ? `
            <div class="segment-location">
                📍 ${escapeHtml(city)}${state ? ', ' + state : ''}
            </div>
            ` : ''}

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
    document.getElementById('minElevation').value = 0;
    document.getElementById('maxElevation').value = 5000;
    document.getElementById('minDistance').value = 0;
    document.getElementById('maxDistance').value = 50;
    document.getElementById('maxDistanceFromCedar').value = 50;
    document.getElementById('sortBy').value = 'elevation_desc';

    loadSegments();
}

// Refresh data from Strava
async function refreshData() {
    const btn = document.getElementById('refreshData');
    const originalText = btn.textContent;

    btn.textContent = 'Searching grid (this may take 10-15 seconds)...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/refresh');
        const data = await response.json();

        if (data.status === 'refreshed') {
            btn.textContent = `Found ${data.total} segments! Loading...`;
            loadSegments();
        }
    } catch (err) {
        alert('Error refreshing data: ' + err.message);
    } finally {
        setTimeout(() => {
            btn.textContent = originalText;
            btn.disabled = false;
        }, 1000);
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
