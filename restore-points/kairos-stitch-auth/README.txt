Stitch sign-in restore point
============================
The pre-Stitch dashboard page is saved at:
  restore-points/kairos-stitch-auth/index.pre-stitch.html

To revert the Stitch authentication screen while keeping the rest of this working tree:
1. Restore frontend/index.html from that snapshot.
2. Remove frontend/auth-stitch.html, frontend/auth-stitch.css, frontend/auth.js, and frontend/auth.css.

The Three.js dashboard assets and stylesheets were not replaced by the Stitch sign-in page.
