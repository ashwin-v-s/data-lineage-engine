# Temporal UI Integration Notes

## Status: ✅ Ready for Integration

The temporal UI files (`temporal-ui.js` and `temporal-ui.css`) are complete standalone modules that need to be integrated into the main application.

## Files Created
- `frontend/temporal-ui.js` - Time travel controls with T_v/T_k pickers
- `frontend/temporal-ui.css` - Complete styling for temporal interface

## Integration Required

### 1. HTML Integration
Add to `frontend/index.html` (or relevant layout):

```html
<!-- In <head> section -->
<link href="/temporal-ui.css?v=1" rel="stylesheet" />

<!-- Before </body> -->
<script type="module" src="/temporal-ui.js"></script>
```

### 2. Container Placeholder
The temporal UI expects a container with ID `time-travel-controls`. Add this to the lineage view:

```html
<div id="time-travel-controls"></div>
```

### 3. View Router Integration
Update the view router in `app.js` to handle the "history" view:

```javascript
case 'history':
    // Render lineage page with temporal controls visible
    window.TimeTravelUI.init();
    break;
```

### 4. Lineage Graph Integration
The temporal UI calls these functions (ensure they exist):
- `getCurrentAssetId()` - Should return the currently selected asset ID
- `getAuthToken()` - Should return the Supabase auth token
- `renderLineageGraph(nodes, edges, container)` - Existing graph renderer

### 5. Global State Integration
The temporal UI sets `window.currentAssetId` - ensure your main app syncs this:

```javascript
// When user selects an asset
window.currentAssetId = selectedAssetId;
```

## API Endpoints Used
- `GET /api/v1/lineage/{id}/both?as_of=<iso>&recorded_as_of=<iso>`
- Expects response: `{ nodes: [], edges: [], undated_edges: [] }`

## Features
- ✅ Separate T_v (valid time) and T_k (recorded time) pickers
- ✅ Historical banner when viewing past lineage
- ✅ Undated rows disclosure
- ✅ Reset to current functionality
- ✅ Pan/zoom support (integrated with existing graph)

## Browser Compatibility
- Modern browsers with datetime-local input support
- Falls back gracefully on older browsers

## Testing Checklist
- [ ] Load temporal-ui.css in HTML
- [ ] Load temporal-ui.js in HTML  
- [ ] Add `#time-travel-controls` container
- [ ] Test "Time travel" nav item (`data-view="history"`)
- [ ] Verify auth token is accessible
- [ ] Test with real lineage API endpoint

## Notes
- The module is self-contained and doesn't depend on React
- Uses vanilla JavaScript for maximum compatibility
- Integrates with existing app.js state management pattern
- No build step required (plain ES6 modules)
