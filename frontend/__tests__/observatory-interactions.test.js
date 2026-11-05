import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { beforeEach, describe, expect, it } from 'vitest';

/**
 * Behavioural tests for the 3D observatory pointer and wheel wiring.
 *
 * `observatory.js` is a classic script that talks to a small part of three.js
 * and to the DOM, so the tests hand it a minimal fake of both and then drive the
 * real handlers.  That keeps the orbit maths, the pointer-capture target and the
 * drag/selection suppression under test without needing WebGL.
 */
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(resolve(frontendRoot, 'observatory.js'), 'utf8');
const appSource = readFileSync(resolve(frontendRoot, 'app.js'), 'utf8');

class V3 {
  constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
  set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
  copy(v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
  clone() { return new V3(this.x, this.y, this.z); }
  add(v) { this.x += v.x; this.y += v.y; this.z += v.z; return this; }
  distanceTo(v) { return Math.hypot(this.x - v.x, this.y - v.y, this.z - v.z); }
  distanceToSquared(v) { return this.distanceTo(v) ** 2; }
}

const geometry = (type) => class { constructor() { this.type = type; } dispose() {} };
const material = () => ({
  color: { hex: null, setHex(value) { this.hex = value; } },
  emissive: { hex: null, setHex(value) { this.hex = value; } },
  opacity: 1,
  needsUpdate: false,
  map: null,
  dispose() {},
});

class Node {
  constructor() {
    this.children = [];
    this.userData = {};
    this.position = new V3();
    this.rotation = { x: 0, y: 0, z: 0 };
    this.scale = { x: 1, y: 1, z: 1, setScalar(value) { this.x = this.y = this.z = value; }, set(x, y, z) { this.x = x; this.y = y; this.z = z; } };
    this.geometry = { type: 'Geometry' };
    this.material = material();
    this.visible = true;
  }
  add(child) { this.children.push(child); return this; }
  setFromPoints() { return this; }
  traverse(fn) { fn(this); this.children.forEach((child) => child.traverse?.(fn)); }
  dispose() {}
}

function createFakeThree(state) {
  class Material { constructor() { return material(); } }
  class Mesh extends Node {
    constructor(geo, mat) { super(); this.geometry = geo || { type: 'Geometry' }; this.material = mat || material(); }
  }
  class Raycaster {
    setFromCamera() {}
    intersectObjects() { return Raycaster.hits; }
  }
  Raycaster.hits = [];
  class PerspectiveCamera extends Node {
    constructor() { super(); state.cameras.push(this); this.aspect = 1; this.focus = null; }
    lookAt(target) { this.focus = { x: target.x, y: target.y, z: target.z }; }
    updateProjectionMatrix() {}
  }
  class WebGLRenderer {
    constructor() { this.domElement = state.canvas; this.shadowMap = { enabled: false }; }
    setPixelRatio() {}
    setSize() {}
    render() { state.renders += 1; }
    dispose() {}
  }
  class Group extends Node {}
  class Scene extends Node {}
  class Sprite extends Node {}
  class Light extends Node {
    constructor() { super(); this.shadow = { mapSize: { set() {} }, camera: {}, bias: 0 }; }
  }

  return {
    Scene, PerspectiveCamera, WebGLRenderer, Raycaster, Group, Sprite, Mesh, Light,
    FogExp2: class { constructor() {} },
    Fog: class { constructor() {} },
    Object3D: Node,
    Vector2: class { set() { return this; } },
    Vector3: V3,
    HemisphereLight: Light,
    DirectionalLight: Light,
    PointLight: Light,
    BoxGeometry: geometry('BoxGeometry'),
    TorusGeometry: geometry('TorusGeometry'),
    SphereGeometry: geometry('SphereGeometry'),
    CylinderGeometry: geometry('CylinderGeometry'),
    PlaneGeometry: geometry('PlaneGeometry'),
    OctahedronGeometry: geometry('OctahedronGeometry'),
    TubeGeometry: geometry('TubeGeometry'),
    BufferGeometry: class { setFromPoints() { return this; } dispose() {} },
    CatmullRomCurve3: class { getPoint() { return new V3(); } },
    Line: Node,
    CanvasTexture: class { constructor() { this.colorSpace = null; } dispose() {} },
    MeshPhysicalMaterial: Material,
    MeshStandardMaterial: Material,
    MeshBasicMaterial: Material,
    LineBasicMaterial: Material,
    SpriteMaterial: Material,
    SRGBColorSpace: 'srgb',
    PCFSoftShadowMap: 1,
    ACESFilmicToneMapping: 1,
  };
}

function createCanvas(state) {
  const listeners = {};
  const canvas = {
    width: 0,
    height: 0,
    dataset: {},
    style: {},
    listeners,
    capturedPointer: null,
    addEventListener(type, handler, options) {
      (listeners[type] || (listeners[type] = [])).push({ handler, options });
    },
    removeEventListener(type, handler) {
      listeners[type] = (listeners[type] || []).filter((entry) => entry.handler !== handler);
    },
    setPointerCapture(id) { this.capturedPointer = id; },
    releasePointerCapture() { this.capturedPointer = null; },
    hasPointerCapture() { return this.capturedPointer !== null; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 800, height: 600 }; },
    getContext() {
      return {
        createLinearGradient: () => ({ addColorStop() {} }),
        fillRect() {}, strokeRect() {}, fillText() {},
      };
    },
    fire(type, event) {
      (listeners[type] || []).forEach((entry) => entry.handler(event));
    },
  };
  state.canvas = canvas;
  return canvas;
}

function mountObservatory({ selected = 'a1' } = {}) {
  const state = { cameras: [], renders: 0 };
  const canvas = createCanvas(state);
  const THREE = createFakeThree(state);
  const groups = [];

  class TrackingGroup extends THREE.Group {
    constructor() { super(); groups.push(this); }
  }
  THREE.Group = TrackingGroup;

  const hostCaptureCalls = [];
  const host = {
    clientWidth: 800,
    clientHeight: 600,
    isConnected: true,
    children: [],
    prepend(child) { this.children.unshift(child); },
    querySelectorAll() { return []; },
    querySelector() { return null; },
    addEventListener() {},
    removeEventListener() {},
    setPointerCapture(id) { hostCaptureCalls.push(id); },
  };

  const selections = [];
  const win = {
    THREE,
    devicePixelRatio: 1,
    matchMedia: () => ({ matches: false }),
    addEventListener() {},
    removeEventListener() {},
    localStorage: { getItem: () => null, setItem() {} },
  };
  const doc = {
    createElement: () => createCanvas({}),
    querySelector: () => null,
  };
  const raf = () => 1;

  const factory = new Function(
    'window', 'document', 'localStorage', 'requestAnimationFrame', 'cancelAnimationFrame', 'performance',
    `${source}\nreturn window.KairosObservatory.mount;`,
  );
  const mount = factory(win, doc, win.localStorage, raf, raf, { now: () => 0 });

  mount({
    host,
    assets: [
      { id: 'a1', name: 'orders', schema: 'warehouse.raw', kind: 'source', path: 'warehouse.raw.orders', type: 'Dataset' },
      { id: 'a2', name: 'orders_model', schema: 'analytics', kind: 'transform', path: 'analytics.orders_model', type: 'Model' },
    ],
    edges: [['a1', 'a2']],
    selected,
    mode: 'overview',
    filter: 'all',
    onSelect: (id) => selections.push(id),
  });

  return {
    canvas,
    host,
    hostCaptureCalls,
    selections,
    groups,
    camera: state.cameras[state.cameras.length - 1],
    THREE,
    groupFor(id) {
      return groups.find((group) => group.userData.asset && group.userData.asset.id === id);
    },
    haloFor(id) {
      const group = groups.find((item) => item.userData.asset && item.userData.asset.id === id);
      return group && group.children.find((child) => child.geometry && child.geometry.type === 'TorusGeometry');
    },
  };
}

let app;
beforeEach(() => {
  app = mountObservatory();
});

describe('observatory orbit', () => {
  it('captures the pointer on the canvas and rotates the camera while dragging', () => {
    const before = { x: app.camera.position.x, y: app.camera.position.y };

    app.canvas.fire('pointerdown', { clientX: 100, clientY: 100, pointerId: 7 });
    expect(app.canvas.capturedPointer).toBe(7);
    expect(app.hostCaptureCalls).toEqual([]);

    app.canvas.fire('pointermove', { clientX: 160, clientY: 120, pointerId: 7 });

    expect(app.camera.position.x).not.toBeCloseTo(before.x, 3);
    expect(app.camera.position.y).not.toBeCloseTo(before.y, 3);
  });

  it('resets drag state on pointerup, pointercancel and lostpointercapture', () => {
    for (const releaseEvent of ['pointerup', 'pointercancel', 'lostpointercapture']) {
      app.canvas.fire('pointerdown', { clientX: 100, clientY: 100, pointerId: 3 });
      app.canvas.fire('pointermove', { clientX: 200, clientY: 100, pointerId: 3 });
      const afterDrag = { x: app.camera.position.x, y: app.camera.position.y };

      app.canvas.fire(releaseEvent, { pointerId: 3 });
      // Without a button held, movement is hover only and must not move the camera.
      app.canvas.fire('pointermove', { clientX: 320, clientY: 240, pointerId: 3 });

      expect(app.camera.position.x).toBeCloseTo(afterDrag.x, 6);
      expect(app.camera.position.y).toBeCloseTo(afterDrag.y, 6);
    }
  });

  it('keeps the orbit limits and never scrolls the page on wheel zoom', () => {
    const wheelBindings = app.canvas.listeners.wheel || [];
    expect(wheelBindings.length).toBe(1);
    expect(wheelBindings[0].options).toMatchObject({ passive: false });

    const before = app.camera.position.clone();
    let prevented = 0;

    for (let i = 0; i < 40; i += 1) {
      app.canvas.fire('wheel', { deltaY: -100, preventDefault: () => { prevented += 1; } });
    }
    expect(prevented).toBe(40);
    // Zoom in moves the camera closer to the target, and the 1.75 cap holds.
    const after = app.camera.position.clone();
    expect(after.distanceTo({ x: 0, y: 0, z: 0 })).toBeLessThan(before.distanceTo({ x: 0, y: 0, z: 0 }));
    const capped = after.clone();
    app.canvas.fire('wheel', { deltaY: -100, preventDefault: () => {} });
    expect(app.camera.position.distanceTo(capped)).toBeLessThan(1e-9);
  });
});

describe('observatory selection', () => {
  it('selects the clicked asset, highlights it and focuses the camera', () => {
    app.THREE.Raycaster.hits = [{ object: app.groupFor('a2') }];

    app.canvas.fire('pointerdown', { clientX: 200, clientY: 200, pointerId: 1 });
    app.canvas.fire('pointerup', { pointerId: 1 });
    app.canvas.fire('click', { clientX: 200, clientY: 200 });

    expect(app.selections).toEqual(['a2']);
    expect(app.haloFor('a2').material.color.hex).toBe(0xffffff);
    // a2 sits on the left of the room; the camera target follows the selection.
    expect(app.camera.focus.x).toBeCloseTo(app.groupFor('a2').position.x, 6);
    expect(app.camera.focus.z).toBeCloseTo(app.groupFor('a2').position.z, 6);
  });

  it('does not select an asset when the press turned into a drag', () => {
    app.THREE.Raycaster.hits = [{ object: app.groupFor('a2') }];

    // Fast drag.
    app.canvas.fire('pointerdown', { clientX: 100, clientY: 100, pointerId: 2 });
    app.canvas.fire('pointermove', { clientX: 180, clientY: 100, pointerId: 2 });
    app.canvas.fire('pointerup', { pointerId: 2 });
    app.canvas.fire('click', { clientX: 180, clientY: 100 });
    expect(app.selections).toEqual([]);

    // Slow drag made of many 1px steps must be treated as a drag too.
    app.canvas.fire('pointerdown', { clientX: 100, clientY: 100, pointerId: 5 });
    for (let x = 101; x <= 110; x += 1) {
      app.canvas.fire('pointermove', { clientX: x, clientY: 100, pointerId: 5 });
    }
    app.canvas.fire('pointerup', { pointerId: 5 });
    app.canvas.fire('click', { clientX: 110, clientY: 100 });
    expect(app.selections).toEqual([]);
  });
});

describe('observatory asset selector', () => {
  it('opens the scene focused on the initially selected asset', () => {
    const focused = mountObservatory({ selected: 'a2' });
    expect(focused.camera.focus.x).toBeCloseTo(focused.groupFor('a2').position.x, 6);
    expect(focused.camera.focus.z).toBeCloseTo(focused.groupFor('a2').position.z, 6);
    expect(focused.haloFor('a2').material.color.hex).toBe(0xffffff);
  });

  it('refreshes the detail panel when the dropdown changes the selection', () => {
    const handler = appSource.slice(
      appSource.indexOf("e.target.id==='observatoryAssetSelect'"),
      appSource.indexOf("e.target.id==='dataModeSelect'"),
    );

    expect(handler).toContain('S.selected=a.id');
    expect(handler).toContain("$('#observatoryDetail')");
    expect(handler).toContain('detail(a)');
    expect(handler).toContain('three()');
  });
});

describe('observatory pointer wiring contract', () => {
  it('never captures the pointer on the parent stage', () => {
    expect(source).not.toContain('host.setPointerCapture');
    expect(source).toContain('renderer.domElement.setPointerCapture');
  });

  it('registers pointerup, pointercancel and lostpointercapture on the canvas', () => {
    for (const eventName of ['pointerup', 'pointercancel', 'lostpointercapture']) {
      expect(source).toContain(`addEventListener('${eventName}',pointerUp)`);
      expect(source).toContain(`removeEventListener('${eventName}',pointerUp)`);
    }
  });
});
