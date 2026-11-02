# Frontend Vendor Assets

These are local copies of third-party JavaScript libraries that were previously loaded from CDN.

## Files

- 	hree.min.js - three.js 3D graphics library (0.160.0)
- chart.umd.min.js - chart.js charting library (4.4.4)

## Setup

To download these files into this directory, run:

`ash
# three.js
curl -o frontend/vendors/three.min.js \
  https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js

# chart.js
curl -o frontend/vendors/chart.umd.min.js \
  https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js
`

Or for Windows (PowerShell):

`powershell
Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js" 
  -OutFile "frontend/vendors/three.min.js"

Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js" 
  -OutFile "frontend/vendors/chart.umd.min.js"
`

## Why Vendored?

- **Offline deployments**: No internet required at demo site
- **Performance**: Faster load times (no CDN latency)
- **Reliability**: No dependency on external CDN availability
- **Bundle integrity**: Version-locked, reproducible builds

