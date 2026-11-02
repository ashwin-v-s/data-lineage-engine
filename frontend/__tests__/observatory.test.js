import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

/**
 * Regression guard for the 3D observatory render loop.
 *
 * `animate(now)` computes its frame delta from the timestamp the browser passes
 * in.  Starting the loop with a bare `animate()` leaves `now` undefined, which
 * makes delta (and then `elapsed`) `NaN` for the rest of the session; the bead
 * animation then calls `curve.getPoint(NaN)`, three.js throws inside
 * `distanceToSquared`, and `renderer.render()` is never reached — so the canvas
 * stays black with nodes and edges present in the scene graph.
 */
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(resolve(frontendRoot, 'observatory.js'), 'utf8');

describe('observatory render loop', () => {
  it('starts the loop through requestAnimationFrame so the first frame has a timestamp', () => {
    expect(source).toContain('raf=requestAnimationFrame(animate)');
    // A bare statement call `animate();` on its own line is the bug this guards.
    expect(source).not.toMatch(/^\s*animate\(\);\s*$/m);
  });

  it('ignores frame timestamps that are not finite instead of poisoning the clock', () => {
    expect(source).toContain('Number.isFinite(now)');
  });

  it('never asks three.js for a point on a curve with a non-finite position', () => {
    expect(source).toContain('Number.isFinite(u)');
  });
});
