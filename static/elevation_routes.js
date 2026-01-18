// Elevation Training Routes JavaScript
// Handles map visualization, elevation charts, and route filtering

let map;
let markersLayer;
let currentRoutes = [];
let selectedRoute = null;
let elevationChart = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    setupEventListeners();
    loadRoutes();
});

// Initialize Leaflet map
function initMap() {
    // Default center: Austin, TX
    map = L.map('map').setView([30.2672, -97.7431], 11);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Create layer group for markers
    markersLayer = L.layerGroup().addTo(map);
}

// Set up event listeners
function setupEventListeners() {
    document.getElementById('applyFilters').addEventListener('click', loadRoutes);
    document.getElementById('resetFilters').addEventListener('click', resetFilters);
    document.getElementById('refreshData').addEventListener('click', refreshData);

    // Sort by dropdown change
    document.getElementById('sortBy').addEventListener('change', loadRoutes);
    document.getElementById('surfaceType').addEventListener('change', loadRoutes);

    // Table header sorting
    document.querySelectorAll('.routes-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => handleTableSort(th.dataset.sort));
    });
}

// Load routes from API
async function loadRoutes() {
    const tableLoading = document.getElementById('tableLoading');
    const routesTable = document.getElementById('routesTable');

    tableLoading.style.display = 'block';
    routesTable.style.display = 'none';

    // Get filter values
    const params = new URLSearchParams({
        min_distance: document.getElementById('minDistance').value,
        max_distance: document.getElementById('maxDistance').value,
        min_ft_per_mile: document.getElementById('minFtPerMile').value,
        max_ft_per_mile: document.getElementById('maxFtPerMile').value,
        surface_type: document.getElementById('surfaceType').value,
        sort_by: document.getElementById('sortBy').value
    });

    try {
        const response = await fetch(`/api/elevation-routes?${params}`);
        const data = await response.json();

        if (data.error) {
            tableLoading.textContent = data.error;
            return;
        }

        currentRoutes = data.segments;
        updateResultsCount(data.total);
        displayRoutesOnMap(data.segments, data.center);
        displayRoutesTable(data.segments);

        tableLoading.style.display = 'none';
        routesTable.style.display = 'table';

    } catch (err) {
        tableLoading.textContent = `Error loading routes: ${err.message}`;
    }
}

// Display routes on the map
function displayRoutesOnMap(routes, center) {
    // Clear existing markers
    markersLayer.clearLayers();

    if (routes.length === 0) return;

    // Recenter map if center provided
    if (center) {
        map.setView([center.lat, center.lon], 11);
    }

    // Add markers for each route
    const bounds = [];
    routes.forEach(route => {
        if (!route.start_latlng || route.start_latlng.length < 2) return;

        const lat = route.start_latlng[0];
        const lon = route.start_latlng[1];
        bounds.push([lat, lon]);

        // Create custom colored marker based on intensity
        const color = route.intensity_color || '#667eea';
        const marker = L.circleMarker([lat, lon], {
            radius: 8,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        });

        // Create popup content
        const popupContent = `
            <div style="min-width: 200px;">
                <strong style="font-size: 1.1em;">${escapeHtml(route.name || 'Unknown')}</strong>
                <hr style="margin: 8px 0; border: none; border-top: 1px solid #e0e0e0;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; font-size: 0.9em;">
                    <div><strong>Distance:</strong> ${route.distance_miles?.toFixed(2) || '?'} mi</div>
                    <div><strong>Elevation:</strong> ${route.elev_difference_feet?.toFixed(0) || '?'} ft</div>
                    <div><strong>Ft/Mile:</strong> ${route.elevation_per_mile?.toFixed(0) || '?'}</div>
                    <div><strong>Grade:</strong> ${route.avg_grade?.toFixed(1) || '?'}%</div>
                </div>
                <div style="margin-top: 10px;">
                    <span style="background: ${color}; color: white; padding: 3px 10px; border-radius: 10px; font-size: 0.85em;">
                        ${route.intensity_label || 'Unknown'}
                    </span>
                </div>
                <div style="margin-top: 10px;">
                    <a href="${route.strava_url}" target="_blank" style="color: #667eea;">View on Strava</a>
                </div>
            </div>
        `;

        marker.bindPopup(popupContent);

        // Click handler to show elevation profile
        marker.on('click', () => {
            selectRoute(route);
        });

        markersLayer.addLayer(marker);
    });

    // Fit map to show all markers
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Display routes in the table
function displayRoutesTable(routes) {
    const tbody = document.getElementById('routesTableBody');
    tbody.innerHTML = '';

    routes.forEach(route => {
        const tr = document.createElement('tr');
        tr.dataset.segmentId = route.id;

        // Determine intensity class
        let intensityClass = 'intensity-easy';
        const ftPerMile = route.elevation_per_mile || 0;
        if (ftPerMile >= 300) intensityClass = 'intensity-very-steep';
        else if (ftPerMile >= 200) intensityClass = 'intensity-steep';
        else if (ftPerMile >= 100) intensityClass = 'intensity-moderate';

        tr.innerHTML = `
            <td class="route-name-cell" title="${escapeHtml(route.name || 'Unknown')}">
                ${escapeHtml(route.name || 'Unknown')}
            </td>
            <td>${route.distance_miles?.toFixed(2) || '?'} mi</td>
            <td>${route.elev_difference_feet?.toFixed(0) || '?'} ft</td>
            <td><strong>${route.elevation_per_mile?.toFixed(0) || '?'}</strong> ft/mi</td>
            <td>${route.avg_grade?.toFixed(1) || '?'}%</td>
            <td>
                <span class="intensity-badge ${intensityClass}">
                    ${route.intensity_label || 'Unknown'}
                </span>
            </td>
            <td>
                <a href="${route.strava_url}" target="_blank" class="route-link" onclick="event.stopPropagation();">
                    View
                </a>
            </td>
        `;

        tr.addEventListener('click', () => {
            // Highlight selected row
            document.querySelectorAll('.routes-table tr.selected').forEach(r => r.classList.remove('selected'));
            tr.classList.add('selected');

            selectRoute(route);

            // Pan map to marker
            if (route.start_latlng && route.start_latlng.length >= 2) {
                map.setView([route.start_latlng[0], route.start_latlng[1]], 14);
            }
        });

        tbody.appendChild(tr);
    });
}

// Select a route and load its elevation profile
async function selectRoute(route) {
    selectedRoute = route;

    const chartPlaceholder = document.getElementById('chartPlaceholder');
    const chartCanvas = document.getElementById('elevationChart');
    const segmentStats = document.getElementById('segmentStats');

    chartPlaceholder.textContent = 'Loading elevation profile...';
    chartPlaceholder.style.display = 'flex';
    chartCanvas.style.display = 'none';
    segmentStats.style.display = 'none';

    try {
        const response = await fetch(`/api/segment/${route.id}/streams`);
        const data = await response.json();

        if (data.error && !data.distance_miles) {
            chartPlaceholder.textContent = data.error || 'Unable to load elevation profile';
            return;
        }

        // Check if we have stream data
        if (!data.distance_miles || data.distance_miles.length === 0) {
            chartPlaceholder.textContent = data.message || 'Elevation profile data not available for this segment';
            // Still show the stats if available
            if (data.total_elevation_gain_feet) {
                updateSegmentStats(data);
                segmentStats.style.display = 'grid';
            }
            return;
        }

        // Show chart and stats
        chartPlaceholder.style.display = 'none';
        chartCanvas.style.display = 'block';
        segmentStats.style.display = 'grid';

        // Update stats
        updateSegmentStats(data);

        // Create/update chart
        createElevationChart(data);

    } catch (err) {
        chartPlaceholder.textContent = `Error loading profile: ${err.message}`;
    }
}

// Update segment stats display
function updateSegmentStats(data) {
    document.getElementById('statElevGain').textContent =
        `${data.total_elevation_gain_feet?.toFixed(0) || '?'} ft`;
    document.getElementById('statAvgGrade').textContent =
        `${data.avg_grade?.toFixed(1) || '?'}%`;
    document.getElementById('statMaxGrade').textContent =
        `${data.max_grade?.toFixed(1) || '?'}%`;
    document.getElementById('statSteepSections').textContent =
        `${data.steep_sections?.length || 0}`;
}

// Create the elevation profile chart
function createElevationChart(data) {
    const ctx = document.getElementById('elevationChart').getContext('2d');

    // Destroy existing chart if any
    if (elevationChart) {
        elevationChart.destroy();
    }

    // Prepare data for chart
    const labels = data.distance_miles.map(d => d.toFixed(2));
    const elevationData = data.altitude_feet;
    const gradeData = data.grades;

    // Create gradient for elevation line based on grade
    const gradientColors = data.grades.map(g => {
        const absGrade = Math.abs(g);
        if (absGrade > 15) return 'rgba(211, 47, 47, 1)';
        if (absGrade > 8) return 'rgba(245, 124, 0, 1)';
        if (absGrade > 4) return 'rgba(251, 192, 45, 1)';
        return 'rgba(56, 142, 60, 1)';
    });

    // Create background colors for steep sections
    const backgroundColors = data.grades.map(g => {
        const absGrade = Math.abs(g);
        if (absGrade > 8) return 'rgba(211, 47, 47, 0.3)';
        return 'rgba(102, 126, 234, 0.2)';
    });

    elevationChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Elevation (ft)',
                    data: elevationData,
                    borderColor: 'rgb(102, 126, 234)',
                    backgroundColor: 'rgba(102, 126, 234, 0.2)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHitRadius: 10,
                    segment: {
                        borderColor: ctx => {
                            const idx = ctx.p0DataIndex;
                            const grade = Math.abs(gradeData[idx] || 0);
                            if (grade > 15) return 'rgb(211, 47, 47)';
                            if (grade > 8) return 'rgb(245, 124, 0)';
                            if (grade > 4) return 'rgb(251, 192, 45)';
                            return 'rgb(56, 142, 60)';
                        }
                    }
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: data.name || 'Elevation Profile',
                    font: { size: 14, weight: 'bold' }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const idx = context.dataIndex;
                            const elev = elevationData[idx]?.toFixed(0) || '?';
                            const grade = gradeData[idx]?.toFixed(1) || '?';
                            return [
                                `Elevation: ${elev} ft`,
                                `Grade: ${grade}%`
                            ];
                        },
                        title: function(context) {
                            return `Distance: ${context[0].label} mi`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Distance (miles)'
                    },
                    ticks: {
                        maxTicksLimit: 10
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Elevation (ft)'
                    },
                    beginAtZero: false
                }
            }
        }
    });

    // Add steep section annotations
    if (data.steep_sections && data.steep_sections.length > 0) {
        // Could add annotation plugin here for vertical lines at steep sections
        console.log(`Found ${data.steep_sections.length} steep sections (>8% grade)`);
    }
}

// Handle table header sort clicks
function handleTableSort(sortField) {
    const currentSort = document.getElementById('sortBy').value;
    let newSort;

    switch (sortField) {
        case 'name':
            // Toggle alphabetical (not in API, handle client-side)
            currentRoutes.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
            displayRoutesTable(currentRoutes);
            return;
        case 'distance':
            newSort = currentSort === 'distance_desc' ? 'distance_asc' : 'distance_desc';
            break;
        case 'elevation':
            newSort = currentSort === 'elevation_desc' ? 'elevation_asc' : 'elevation_desc';
            break;
        case 'ft_per_mile':
            newSort = currentSort === 'ft_per_mile_desc' ? 'ft_per_mile_asc' : 'ft_per_mile_desc';
            break;
        case 'grade':
            newSort = 'grade_desc';
            break;
        default:
            return;
    }

    document.getElementById('sortBy').value = newSort;
    loadRoutes();

    // Update sort indicators
    document.querySelectorAll('.routes-table th').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
    });
    const sortedTh = document.querySelector(`.routes-table th[data-sort="${sortField}"]`);
    if (sortedTh) {
        sortedTh.classList.add(newSort.endsWith('_asc') ? 'sorted-asc' : 'sorted-desc');
    }
}

// Update results count
function updateResultsCount(count) {
    const resultsCount = document.getElementById('resultsCount');
    resultsCount.textContent = `${count} route${count !== 1 ? 's' : ''} found`;
}

// Reset filters to defaults
function resetFilters() {
    document.getElementById('minDistance').value = 0;
    document.getElementById('maxDistance').value = 10;
    document.getElementById('minFtPerMile').value = 0;
    document.getElementById('maxFtPerMile').value = 1000;
    document.getElementById('surfaceType').value = 'all';
    document.getElementById('sortBy').value = 'ft_per_mile_desc';

    // Clear chart
    const chartPlaceholder = document.getElementById('chartPlaceholder');
    const chartCanvas = document.getElementById('elevationChart');
    const segmentStats = document.getElementById('segmentStats');

    chartPlaceholder.textContent = 'Click on a route to view its elevation profile';
    chartPlaceholder.style.display = 'flex';
    chartCanvas.style.display = 'none';
    segmentStats.style.display = 'none';

    if (elevationChart) {
        elevationChart.destroy();
        elevationChart = null;
    }

    loadRoutes();
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
            btn.textContent = `Found ${data.total} segments!`;
            loadRoutes();
        }
    } catch (err) {
        alert('Error refreshing data: ' + err.message);
    } finally {
        setTimeout(() => {
            btn.textContent = originalText;
            btn.disabled = false;
        }, 1500);
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
