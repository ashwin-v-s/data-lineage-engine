/**
 * frontend/temporal-ui.js
 * ───────────────────────
 * Time travel UI for historical lineage queries.
 * Implements separate T_v (valid time) and T_k (recorded time) pickers.
 *
 * Per handout section 8:
 * - API supports ?as_of= and ?recorded_as_of= params
 * - UI needs separate pickers (never one merged control)
 * - Must display historical banner when querying past
 * - Must disclose undated rows instead of implying complete history
 */

(function() {
    'use strict';

    /**
     * Initialize time travel controls
     */
    function initTimeTravelControls() {
        const container = document.getElementById('time-travel-controls');
        if (!container) return;

        container.innerHTML = `
            <div class="time-travel-panel">
                <div class="time-travel-header">
                    <h3>⏱️ Time Travel</h3>
                    <button id="reset-time-travel" class="btn-secondary">Reset to Current</button>
                </div>
                
                <div class="time-picker-group">
                    <div class="time-picker">
                        <label for="valid-time-picker">Valid Time (T_v):</label>
                        <input 
                            type="datetime-local" 
                            id="valid-time-picker" 
                            class="datetime-input"
                            title="Show lineage as it was valid at this time"
                        />
                        <small>When the relationships were actually valid</small>
                    </div>
                    
                    <div class="time-picker">
                        <label for="recorded-time-picker">Recorded Time (T_k):</label>
                        <input 
                            type="datetime-local" 
                            id="recorded-time-picker" 
                            class="datetime-input"
                            title="Show lineage as it was known at this time"
                        />
                        <small>When we learned about the relationships</small>
                    </div>
                </div>

                <button id="apply-time-travel" class="btn-primary">
                    🔍 Query Historical Lineage
                </button>

                <div id="time-travel-banner" class="historical-banner hidden">
                    ⚠️ Viewing historical lineage. Some relationships may have unknown timestamps.
                </div>
            </div>
        `;

        attachTimeTravelEvents();
    }

    /**
     * Attach event handlers to time travel controls
     */
    function attachTimeTravelEvents() {
        const validTimePicker = document.getElementById('valid-time-picker');
        const recordedTimePicker = document.getElementById('recorded-time-picker');
        const applyButton = document.getElementById('apply-time-travel');
        const resetButton = document.getElementById('reset-time-travel');
        const banner = document.getElementById('time-travel-banner');

        applyButton.addEventListener('click', () => {
            const validTime = validTimePicker.value;
            const recordedTime = recordedTimePicker.value;

            if (!validTime && !recordedTime) {
                alert('Please select at least one timestamp');
                return;
            }

            // Show historical banner
            banner.classList.remove('hidden');
            
            // Build query params
            const params = new URLSearchParams();
            if (validTime) {
                params.set('as_of', new Date(validTime).toISOString());
            }
            if (recordedTime) {
                params.set('recorded_as_of', new Date(recordedTime).toISOString());
            }

            // Trigger lineage re-query
            queryHistoricalLineage(params);
        });

        resetButton.addEventListener('click', () => {
            validTimePicker.value = '';
            recordedTimePicker.value = '';
            banner.classList.add('hidden');
            
            // Reset to current lineage
            reloadCurrentLineage();
        });
    }

    /**
     * Query historical lineage from API
     */
    async function queryHistoricalLineage(params) {
        const currentAssetId = getCurrentAssetId();
        if (!currentAssetId) {
            console.error('No asset selected for lineage query');
            return;
        }

        try {
            const url = `/api/v1/lineage/${currentAssetId}/both?${params.toString()}`;
            const response = await fetch(url, {
                headers: {
                    'Authorization': `Bearer ${getAuthToken()}`
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch historical lineage: ${response.status}`);
            }

            const data = await response.json();
            
            // Render historical graph
            renderHistoricalLineage(data, params);
            
            // Show undated rows warning if present
            if (data.undated_edges && data.undated_edges.length > 0) {
                showUndatedWarning(data.undated_edges.length);
            }
            
        } catch (error) {
            console.error('Historical lineage query failed:', error);
            alert('Failed to query historical lineage. See console for details.');
        }
    }

    /**
     * Render historical lineage graph
     */
    function renderHistoricalLineage(data, params) {
        const graphContainer = document.getElementById('lineage-graph');
        if (!graphContainer) return;

        // Clear existing graph
        graphContainer.innerHTML = '';

        // Add historical context header
        const contextHeader = document.createElement('div');
        contextHeader.className = 'historical-context';
        contextHeader.innerHTML = `
            <strong>Historical View:</strong>
            ${params.has('as_of') ? `Valid at: ${new Date(params.get('as_of')).toLocaleString()}` : ''}
            ${params.has('recorded_as_of') ? `Known at: ${new Date(params.get('recorded_as_of')).toLocaleString()}` : ''}
        `;
        graphContainer.appendChild(contextHeader);

        // Render graph (reuse existing graph renderer)
        if (window.renderLineageGraph) {
            window.renderLineageGraph(data.nodes, data.edges, graphContainer);
        } else {
            console.error('Lineage graph renderer not found');
        }
    }

    /**
     * Show warning about undated edges
     */
    function showUndatedWarning(count) {
        const banner = document.getElementById('time-travel-banner');
        banner.innerHTML = `
            ⚠️ Viewing historical lineage. 
            ${count} relationship(s) have unknown timestamps and are excluded from this view.
            <a href="#" id="show-undated-details">View details</a>
        `;
        banner.classList.remove('hidden');

        document.getElementById('show-undated-details')?.addEventListener('click', (e) => {
            e.preventDefault();
            alert('Undated relationships cannot be accurately placed in time and are excluded from historical queries.');
        });
    }

    /**
     * Reset to current (non-historical) lineage
     */
    function reloadCurrentLineage() {
        const currentAssetId = getCurrentAssetId();
        if (!currentAssetId) return;

        // Reload without time params
        const url = `/api/v1/lineage/${currentAssetId}/both`;
        fetch(url, {
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`
            }
        })
        .then(res => res.json())
        .then(data => {
            renderHistoricalLineage(data, new URLSearchParams());
        })
        .catch(err => console.error('Failed to reload current lineage:', err));
    }

    /**
     * Helper: Get current asset ID from page state
     */
    function getCurrentAssetId() {
        // This should integrate with existing app.js state management
        return window.currentAssetId || null;
    }

    /**
     * Helper: Get auth token
     */
    function getAuthToken() {
        // This should integrate with existing auth system
        return localStorage.getItem('supabase.auth.token') || '';
    }

    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTimeTravelControls);
    } else {
        initTimeTravelControls();
    }

    // Export for integration with main app
    window.TimeTravelUI = {
        init: initTimeTravelControls,
        query: queryHistoricalLineage,
        reset: reloadCurrentLineage
    };
})();
