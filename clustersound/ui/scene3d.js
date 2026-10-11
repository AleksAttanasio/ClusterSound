// 3D point cloud of the library: one point per sample, coloured by class.
import * as THREE from './vendor/three.module.min.js';
import { OrbitControls } from './vendor/OrbitControls.js';

const VERT = `
  attribute vec3 aColor;
  attribute float aSize;
  attribute float aAlpha;
  uniform float uScale;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    vColor = aColor;
    vAlpha = aAlpha;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * uScale / max(-mv.z, 1.0);
    gl_Position = projectionMatrix * mv;
  }`;

const FRAG = `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    if (d > 0.5) discard;
    float edge = smoothstep(0.5, 0.40, d);
    // soft rim so overlapping points stay readable
    vec3 col = mix(vColor * 0.55, vColor, smoothstep(0.5, 0.30, d));
    gl_FragColor = vec4(col, vAlpha * edge);
  }`;

const RING_FRAG = `
  uniform vec3 uColor;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float ring = smoothstep(0.50, 0.44, d) * smoothstep(0.30, 0.36, d);
    if (ring < 0.02) discard;
    gl_FragColor = vec4(uColor, ring);
  }`;

const RING_VERT = `
  uniform float uScale;
  uniform float uSize;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = max(uSize * uScale / max(-mv.z, 1.0), 14.0);
    gl_Position = projectionMatrix * mv;
  }`;

// dotted trail: fixed-size round dots, faded by uOpacity
const DOT_VERT = `
  uniform float uPx;
  void main() {
    gl_PointSize = uPx;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;

const DOT_FRAG = `
  uniform vec3 uColor;
  uniform float uOpacity;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    if (d > 0.5) discard;
    gl_FragColor = vec4(uColor, uOpacity * smoothstep(0.5, 0.3, d));
  }`;

const FOCUS_MS = 750;
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const SPOKE = new THREE.Color(0x6ea8fe);
const TRAIL = new THREE.Color(0xffb84d);

export class Scene3D {
  constructor(container, { onHover, onClick, onContext, onDoubleClick }) {
    this.container = container;
    this.onHover = onHover;
    this.onClick = onClick;
    this.onContext = onContext;
    this.onDoubleClick = onDoubleClick;
    this.n = 0;
    this.base = null;        // layout positions; the geometry shows them, or the focus layout
    this.visible = null;     // Uint8Array mask
    this.selected = -1;
    this.labelsOn = true;
    this.anim = null;
    // Similar-samples focus: {center, items: [{id, sim, w}], layout: [[id, [x,y,z]]]}
    this.focus = null;
    this.trail = [];         // centres visited while re-centring, oldest first
    this._ov = null;         // what spokes/trail draw; kept while they fade out after the focus ends
    this._ovOpacity = 0;
    this._grow = false;      // last trail segment is being drawn towards the new centre
    // px covered on the right (detail panel) and at the top (focus bar): the focus view centres on the rest
    this.inset = { right: 0, top: 0 };
    this._insetCur = { right: 0, top: 0 };

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(window.devicePixelRatio || 1);
    this.renderer.setClearColor(0x0f1115, 1);
    container.prepend(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.5, 2000);
    this.camera.position.set(95, 70, 120);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.autoRotateSpeed = 0.6;

    this.geom = new THREE.BufferGeometry();
    this.material = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
      uniforms: { uScale: { value: 300 } },
    });
    this.points = new THREE.Points(this.geom, this.material);
    this.points.frustumCulled = false;
    this.scene.add(this.points);

    this.ring = this._makeRing(0xffffff, 9, 1);
    this.trailRings = this._makeRing(0xffb84d, 8, 0);
    this.spokes = this._makeLines(THREE.LineSegments);
    this.trailLine = this._makeLines(THREE.Line);
    const dg = new THREE.BufferGeometry();
    dg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3), 3));
    dg.setDrawRange(0, 0);
    this.trailDots = new THREE.Points(dg, new THREE.ShaderMaterial({
      vertexShader: DOT_VERT, fragmentShader: DOT_FRAG, transparent: true, depthTest: false, depthWrite: false,
      uniforms: { uColor: { value: TRAIL.clone() }, uOpacity: { value: 0 }, uPx: { value: 4 * (window.devicePixelRatio || 1) } },
    }));
    this.trailDots.frustumCulled = false;
    this.trailDots.renderOrder = 6;
    this.scene.add(this.trailDots);

    // faint reference grid
    const grid = new THREE.GridHelper(120, 12, 0x232833, 0x1a1e27);
    grid.position.y = -55;
    this.scene.add(grid);

    this._pointer = { x: 0, y: 0, down: null, dirty: false, inside: false };
    const el = this.renderer.domElement;
    el.addEventListener('pointermove', (e) => this._move(e));
    el.addEventListener('pointerleave', () => { this._pointer.inside = false; this.onHover(-1); });
    el.addEventListener('pointerdown', (e) => { this._pointer.down = [e.clientX, e.clientY]; });
    el.addEventListener('pointerup', (e) => this._up(e));
    el.addEventListener('dblclick', (e) => {
      const r = el.getBoundingClientRect();
      const i = this.pick(e.clientX - r.left, e.clientY - r.top);
      if (i >= 0 && this.onDoubleClick) this.onDoubleClick(i);
    });
    el.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const i = this.pick(e.clientX - r.left, e.clientY - r.top);
      if (i >= 0 && this.onContext) this.onContext(i, e.clientX, e.clientY);
    });
    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    this._tick = this._tick.bind(this);
    requestAnimationFrame(this._tick);
  }

  _makeRing(color, size, count) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(Math.max(count, 1) * 3), 3));
    g.setDrawRange(0, count);
    const m = new THREE.ShaderMaterial({
      vertexShader: RING_VERT, fragmentShader: RING_FRAG, transparent: true, depthTest: false,
      uniforms: { uColor: { value: new THREE.Color(color) }, uScale: this.material.uniforms.uScale, uSize: { value: size } },
    });
    const p = new THREE.Points(g, m);
    p.frustumCulled = false;
    p.renderOrder = 10;
    this.scene.add(p);
    return p;
  }

  _makeLines(Kind) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(6), 3));
    g.setDrawRange(0, 0);
    const m = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false });
    const l = new Kind(g, m);
    l.frustumCulled = false;
    l.renderOrder = 5;
    this.scene.add(l);
    return l;
  }

  resize() {
    const w = this.container.clientWidth, h = this.container.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = w + 'px';
    this.renderer.domElement.style.height = h + 'px';
    this.camera.aspect = w / h;
    this._applyInset();
    // point size is specified in pixels at distance 100
    this.material.uniforms.uScale.value = 100 * (this.renderer.getPixelRatio());
  }

  // data: {xyz, cls, conf}, colors: array of THREE.Color-compatible hex per class index
  setData(data, colors) {
    const n = data.cls.length;
    const sameCount = n === this.n && !!this.geom.getAttribute('position');
    this.base = new Float32Array(data.xyz);
    this.n = n;
    this.data = data;
    this.colors = colors.map((c) => new THREE.Color(c));
    if (!sameCount) {
      this.focus = null;
      this.trail = [];
      this._ov = null;
      this.anim = null;
      this.geom.setAttribute('position', new THREE.BufferAttribute(this.base.slice(), 3));
      this.geom.setAttribute('aColor', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
      this.geom.setAttribute('aSize', new THREE.BufferAttribute(new Float32Array(n), 1));
      this.geom.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(n), 1));
    } else if (this.focus) {
      this.focus.layout = this._focusLayout(this.focus.center, this.focus.items, this.trail);
    }
    if (!this.visible || this.visible.length !== n) this.visible = new Uint8Array(n).fill(1);
    this._writeColors();
    // animate from the current layout (e.g. PCA -> t-SNE)
    this._retarget(sameCount ? 900 : 0);
  }

  setVisible(mask) {
    this.visible = mask;
    this.refreshStyle();
  }

  refreshStyle() {
    if (!this.n) return;
    this._writeColors();
    this._retarget(0);
  }

  _writeColors() {
    const col = this.geom.getAttribute('aColor');
    const { cls } = this.data;
    for (let i = 0; i < this.n; i++) {
      const c = this.colors[cls[i]];
      col.array[i * 3] = c.r; col.array[i * 3 + 1] = c.g; col.array[i * 3 + 2] = c.b;
    }
    col.needsUpdate = true;
  }

  _targetPositions() {
    const out = this.base.slice();
    if (this.focus) for (const [id, p] of this.focus.layout) out.set(p, id * 3);
    return out;
  }

  _targetStyle() {
    const n = this.n, size = new Float32Array(n), alpha = new Float32Array(n);
    const f = this.focus, { conf } = this.data;
    for (let i = 0; i < n; i++) {
      if (f) { size[i] = 1.4; alpha[i] = 0.035; continue; }
      const vis = this.visible[i];
      size[i] = vis ? 2.6 + 3.4 * conf[i] : 1.6;
      alpha[i] = vis ? 0.92 : 0.05;
    }
    if (f) {
      for (const id of this.trail) { size[id] = 6; alpha[id] = 0.85; }
      for (const it of f.items) { size[it.id] = 6 + 3.5 * it.w; alpha[it.id] = 1; }
      size[f.center] = 12; alpha[f.center] = 1;
    }
    return [size, alpha];
  }

  // Move positions/sizes/alphas towards the current targets, always starting from what is on
  // screen, so a new command halfway through an animation carries on without a jump.
  _retarget(dur = 0) {
    if (!this.n) return;
    const pos = this._targetPositions();
    const [size, alpha] = this._targetStyle();
    const P = this.geom.getAttribute('position'), S = this.geom.getAttribute('aSize'), A = this.geom.getAttribute('aAlpha');
    if (dur > 0) {
      this.anim = { from: P.array.slice(), to: pos, fromS: S.array.slice(), toS: size, fromA: A.array.slice(), toA: alpha,
        t0: performance.now(), dur };
    } else if (this.anim) {
      Object.assign(this.anim, { to: pos, toS: size, toA: alpha });
    } else {
      P.array.set(pos); S.array.set(size); A.array.set(alpha);
      P.needsUpdate = S.needsUpdate = A.needsUpdate = true;
    }
    this._updateOverlays(1);
  }

  setSelected(i) { this.selected = i; this._updateOverlays(1); }

  _pos(i) {
    const p = this.geom.getAttribute('position').array;
    return [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]];
  }

  // current on-screen position of a point (follows the focus animations)
  pos(i) { return i >= 0 && i < this.n ? this._pos(i) : null; }

  // --------------------------------------------------------------- focus
  // Neighbours fan out around the centre: distance grows with dissimilarity, direction is the one
  // they had in the map as seen from the camera (depth flattened, so nothing hides behind
  // something else), then a few relaxation passes push apart the ones that overlap.
  _focusLayout(center, items, trail = []) {
    const b = this.base;
    const c = [b[center * 3], b[center * 3 + 1], b[center * 3 + 2]];
    const q = this.camera.quaternion;
    const R = new THREE.Vector3(1, 0, 0).applyQuaternion(q), U = new THREE.Vector3(0, 1, 0).applyQuaternion(q);
    const F = new THREE.Vector3(0, 0, 1).applyQuaternion(q);
    // keep the neighbours' angular order as seen on screen but spread them evenly around the
    // centre (a sample on the edge of its cluster would otherwise get a one-sided fan)
    const golden = Math.PI * (3 - Math.sqrt(5));
    const raw = items.map((it, k) => {
      const v = new THREE.Vector3(b[it.id * 3] - c[0], b[it.id * 3 + 1] - c[1], b[it.id * 3 + 2] - c[2]);
      let sx = v.dot(R), sy = v.dot(U);
      if (Math.hypot(sx, sy) < 1e-4) { sx = Math.cos(golden * k); sy = Math.sin(golden * k); }
      const sz = v.length() > 1e-4 ? (v.dot(F) / v.length()) * 0.3 : 0;
      return { ang: Math.atan2(sy, sx), sz };
    });
    const order = raw.map((_, k) => k).sort((a, q) => raw[a].ang - raw[q].ang);
    const n = items.length, step = (2 * Math.PI) / Math.max(n, 1);
    let ox = 0, oy = 0; // circular mean of (original - even) keeps the overall orientation
    order.forEach((k, r) => { ox += Math.cos(raw[k].ang - r * step); oy += Math.sin(raw[k].ang - r * step); });
    const rot = Math.atan2(oy, ox);
    const ang = new Array(n);
    order.forEach((k, r) => { ang[k] = rot + r * step; });
    const pts = items.map((it, k) => {
      const dv = R.clone().multiplyScalar(Math.cos(ang[k])).add(U.clone().multiplyScalar(Math.sin(ang[k])))
        .add(F.clone().multiplyScalar(raw[k].sz));
      const d = [dv.x, dv.y, dv.z];
      const len = Math.hypot(...d);
      // half similarity, half rank: gaps in similarity show, yet near-identical neighbours still spread out
      const rank = n > 1 ? k / (n - 1) : 0;
      const rad = 10 + 26 * (0.5 * (1 - it.w) + 0.5 * rank);
      return { id: it.id, rad, p: [c[0] + d[0] / len * rad, c[1] + d[1] / len * rad, c[2] + d[2] / len * rad] };
    });
    const MIN = 6;
    for (let iter = 0; iter < 40; iter++) {
      for (let a = 0; a < pts.length; a++) {
        for (let q = a + 1; q < pts.length; q++) {
          const pa = pts[a].p, pb = pts[q].p;
          const dx = pb[0] - pa[0], dy = pb[1] - pa[1], dz = pb[2] - pa[2];
          const dist = Math.hypot(dx, dy, dz);
          if (dist >= MIN) continue;
          const push = (MIN - dist) / 2 / (dist || 1);
          const ux = dist ? dx * push : (MIN / 2), uy = dist ? dy * push : 0, uz = dist ? dz * push : 0;
          pa[0] -= ux; pa[1] -= uy; pa[2] -= uz;
          pb[0] += ux; pb[1] += uy; pb[2] += uz;
        }
      }
      for (const pt of pts) { // back towards its similarity radius, and towards the camera-facing plane
        const v = [pt.p[0] - c[0], pt.p[1] - c[1], pt.p[2] - c[2]];
        const depth = (v[0] * F.x + v[1] * F.y + v[2] * F.z) * 0.15;
        v[0] -= F.x * depth; v[1] -= F.y * depth; v[2] -= F.z * depth;
        const len = Math.hypot(...v) || 1;
        const r = len + (pt.rad - len) * 0.35;
        pt.p = [c[0] + v[0] / len * r, c[1] + v[1] / len * r, c[2] + v[2] / len * r];
      }
    }
    const out = pts.map((pt) => [pt.id, pt.p]);
    // earlier trail stops that are not neighbours now but sit inside the fan go to an outer ring
    const inFan = new Set([center, ...items.map((it) => it.id)]);
    const OUTER = 40;
    [...new Set(trail)].filter((id) => !inFan.has(id)).forEach((id, k) => {
      const v = new THREE.Vector3(b[id * 3] - c[0], b[id * 3 + 1] - c[1], b[id * 3 + 2] - c[2]);
      if (v.length() >= OUTER) return;
      let sx = v.dot(R), sy = v.dot(U);
      if (Math.hypot(sx, sy) < 1e-3) { sx = Math.cos(golden * k + 0.5); sy = Math.sin(golden * k + 0.5); }
      const d = R.clone().multiplyScalar(sx).add(U.clone().multiplyScalar(sy)).setLength(OUTER);
      out.push([id, [c[0] + d.x, c[1] + d.y, c[2] + d.z]]);
    });
    return out;
  }

  // items: [{id, sim}]; trail: visited centres, ending with `center`
  setFocus(center, items, trail = [center]) {
    if (center < 0 || center >= this.n) return;
    const list = items.filter((it) => it.id >= 0 && it.id < this.n && it.id !== center).sort((a, b) => b.sim - a.sim);
    const sims = list.map((it) => it.sim);
    const lo = Math.min(...sims), hi = Math.max(...sims);
    const norm = list.map((it) => ({ id: it.id, sim: it.sim, w: hi - lo > 1e-6 ? (it.sim - lo) / (hi - lo) : 1 }));
    if (!this.focus) this._savedView = { pos: this.camera.position.clone(), target: this.controls.target.clone() };
    const newTrail = trail.filter((i) => i >= 0 && i < this.n);
    this._grow = newTrail.length > this.trail.length && newTrail.length > 1;
    this.trail = newTrail;
    this.focus = { center, items: norm, layout: this._focusLayout(center, norm, newTrail) };
    this._ov = { center, items: norm, trail: newTrail };
    this._retarget(FOCUS_MS);
    const c = this.base.subarray(center * 3, center * 3 + 3);
    let R = 6;
    for (const [, p] of this.focus.layout) R = Math.max(R, Math.hypot(p[0] - c[0], p[1] - c[1], p[2] - c[2]));
    this._flyTo(new THREE.Vector3(c[0], c[1], c[2]), this._fitDist(R + 3));
  }

  clearFocus(restoreView = true) {
    if (!this.focus) return;
    this.focus = null;
    this.trail = [];
    this._grow = false;
    this._retarget(FOCUS_MS);
    if (restoreView && this._savedView) {
      this._fly = { fromT: this.controls.target.clone(), toT: this._savedView.target, fromC: this.camera.position.clone(),
        toC: this._savedView.pos, t0: performance.now(), dur: FOCUS_MS };
    }
    this._savedView = null;
  }

  // Frame the whole trail plus the current neighbourhood.
  frameTrail() {
    if (!this.focus) return;
    const to = this._targetPositions();
    const ids = [this.focus.center, ...this.trail, ...this.focus.items.map((it) => it.id)];
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const i of ids) for (let a = 0; a < 3; a++) { lo[a] = Math.min(lo[a], to[i * 3 + a]); hi[a] = Math.max(hi[a], to[i * 3 + a]); }
    const c = new THREE.Vector3((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2);
    let R = 6;
    for (const i of ids) R = Math.max(R, c.distanceTo(new THREE.Vector3(to[i * 3], to[i * 3 + 1], to[i * 3 + 2])));
    this._flyTo(c, this._fitDist(R + 3));
  }

  setInset(right, top) { this.inset = { right, top }; }

  // Shift the projection so the scene centre sits in the middle of the uncovered area.
  _applyInset() {
    const w = this.container.clientWidth, h = this.container.clientHeight;
    const { right, top } = this._insetCur;
    if ((right > 0.5 || top > 0.5) && w && h) this.camera.setViewOffset(w, h, right / 2, -top / 2, w, h);
    else this.camera.clearViewOffset();
    this.camera.updateProjectionMatrix();
  }

  _fitDist(R) {
    const w = this.container.clientWidth || 1, hh = this.container.clientHeight || 1;
    const fx = Math.max(0.3, (w - this.inset.right) / w), fy = Math.max(0.3, (hh - this.inset.top) / hh);
    const t = Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2);
    const half = Math.min(Math.atan(t * fy), Math.atan(t * this.camera.aspect * fx));
    return Math.max((R / Math.sin(half)) * 1.05, 12);
  }

  _flyTo(target, dist, dur = FOCUS_MS) {
    const off = this.camera.position.clone().sub(this.controls.target);
    if (off.lengthSq() < 1e-6) off.set(0.6, 0.4, 0.7);
    off.setLength(dist);
    this._fly = { fromT: this.controls.target.clone(), toT: target, fromC: this.camera.position.clone(),
      toC: target.clone().add(off), t0: performance.now(), dur };
  }

  _pickable() {
    if (!this.focus) return null;
    return [this.focus.center, ...this.focus.items.map((it) => it.id), ...this.trail];
  }

  // Selection ring, trail rings, spokes and trail line follow the points on screen.
  // `e` is the progress of the current animation (draws the newest trail segment).
  _updateOverlays(e) {
    if (!this.n) return;
    const size = this.geom.getAttribute('aSize').array;
    const rp = this.ring.geometry.getAttribute('position');
    if (this.selected >= 0 && this.selected < this.n) {
      rp.array.set(this._pos(this.selected));
      this.ring.material.uniforms.uSize.value = Math.max(9, size[this.selected] + 3);
      this.ring.geometry.setDrawRange(0, 1);
    } else this.ring.geometry.setDrawRange(0, 0);
    rp.needsUpdate = true;

    const stops = this.focus ? this.trail.filter((i) => i !== this.focus.center) : [];
    this._fillPoints(this.trailRings.geometry, stops);

    const ov = this._ov;
    if (!ov) {
      for (const o of [this.spokes, this.trailLine, this.trailDots]) o.geometry.setDrawRange(0, 0);
      return;
    }
    const cp = this._pos(ov.center);
    const segs = [], cols = [];
    for (const it of ov.items) {
      const k = 0.18 + 0.6 * it.w;
      segs.push(cp, this._pos(it.id));
      cols.push([SPOKE.r * k * 0.5, SPOKE.g * k * 0.5, SPOKE.b * k * 0.5], [SPOKE.r * k, SPOKE.g * k, SPOKE.b * k]);
    }
    this._fillLines(this.spokes.geometry, segs, cols);

    const tr = ov.trail;
    if (tr.length > 1) {
      const pts = tr.map((i) => this._pos(i));
      if (this._grow && e < 1) {
        const a = pts[pts.length - 2], b = pts[pts.length - 1];
        pts[pts.length - 1] = a.map((v, k) => v + (b[k] - v) * e);
      }
      const tcols = tr.map((_, k) => { const f = 0.3 + 0.7 * (k / (tr.length - 1)); return [TRAIL.r * f, TRAIL.g * f, TRAIL.b * f]; });
      this._fillLines(this.trailLine.geometry, pts, tcols);
      const dots = [];
      for (let k = 1; k < pts.length; k++) {
        const a = pts[k - 1], b = pts[k];
        const steps = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) / 1.6));
        for (let j = 0; j < steps; j++) dots.push(a.map((v, m) => v + (b[m] - v) * (j / steps)));
      }
      this._fillPointsXYZ(this.trailDots.geometry, dots);
    } else {
      this.trailLine.geometry.setDrawRange(0, 0);
      this.trailDots.geometry.setDrawRange(0, 0);
    }
  }

  _fillPoints(g, ids) {
    if (g.getAttribute('position').array.length < ids.length * 3) {
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(ids.length * 3), 3));
    }
    const arr = g.getAttribute('position').array;
    ids.forEach((id, k) => arr.set(this._pos(id), k * 3));
    g.setDrawRange(0, ids.length);
    g.getAttribute('position').needsUpdate = true;
  }

  _fillPointsXYZ(g, pts) {
    if (g.getAttribute('position').array.length < pts.length * 3) {
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(Math.ceil(pts.length * 1.5) * 3), 3));
    }
    const P = g.getAttribute('position');
    pts.forEach((p, k) => P.array.set(p, k * 3));
    g.setDrawRange(0, pts.length);
    P.needsUpdate = true;
  }

  _fillLines(g, pts, cols) {
    if (g.getAttribute('position').array.length < pts.length * 3) {
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pts.length * 3), 3));
      g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(pts.length * 3), 3));
    }
    const P = g.getAttribute('position'), C = g.getAttribute('color');
    pts.forEach((p, k) => { P.array.set(p, k * 3); C.array.set(cols[k], k * 3); });
    g.setDrawRange(0, pts.length);
    P.needsUpdate = C.needsUpdate = true;
  }

  resetView() {
    this._fly = { fromT: this.controls.target.clone(), toT: new THREE.Vector3(),
      fromC: this.camera.position.clone(), toC: new THREE.Vector3(95, 70, 120), t0: performance.now(), dur: 600 };
  }

  setAutoRotate(on) { this.controls.autoRotate = on; }

  // ---------------------------------------------------------------- picking
  _move(e) {
    const r = this.renderer.domElement.getBoundingClientRect();
    this._pointer.x = e.clientX - r.left;
    this._pointer.y = e.clientY - r.top;
    this._pointer.inside = true;
    this._pointer.dirty = true;
  }

  _up(e) {
    const d = this._pointer.down;
    this._pointer.down = null;
    if (!d || e.button !== 0 || Math.hypot(e.clientX - d[0], e.clientY - d[1]) > 4) return;
    const r = this.renderer.domElement.getBoundingClientRect();
    const i = this.pick(e.clientX - r.left, e.clientY - r.top);
    this.onClick(i);
  }

  // nearest visible point within a few pixels; ties go to the one closer to the camera
  pick(px, py, radius) {
    if (!this.n) return -1;
    const only = this._pickable();
    radius ??= only ? 14 : 9;
    const w = this.container.clientWidth, h = this.container.clientHeight;
    const m = new THREE.Matrix4().multiplyMatrices(this.camera.projectionMatrix, this.camera.matrixWorldInverse).elements;
    const p = this.geom.getAttribute('position').array;
    let best = -1, bestScore = Infinity;
    const r2 = radius * radius;
    const count = only ? only.length : this.n;
    for (let k = 0; k < count; k++) {
      const i = only ? only[k] : k;
      if (!only && !this.visible[i]) continue;
      const x = p[i * 3], y = p[i * 3 + 1], z = p[i * 3 + 2];
      const cw = m[3] * x + m[7] * y + m[11] * z + m[15];
      if (cw <= 0) continue;
      const sx = ((m[0] * x + m[4] * y + m[8] * z + m[12]) / cw * 0.5 + 0.5) * w;
      const sy = (1 - ((m[1] * x + m[5] * y + m[9] * z + m[13]) / cw * 0.5 + 0.5)) * h;
      const d2 = (sx - px) ** 2 + (sy - py) ** 2;
      if (d2 > r2) continue;
      const score = d2 + cw * 0.05; // prefer nearer points when overlapping
      if (score < bestScore) { bestScore = score; best = i; }
    }
    return best;
  }

  project(x, y, z) {
    const v = new THREE.Vector3(x, y, z).project(this.camera);
    if (v.z > 1) return null;
    return [(v.x * 0.5 + 0.5) * this.container.clientWidth, (1 - (v.y * 0.5 + 0.5)) * this.container.clientHeight];
  }

  // ------------------------------------------------------------------ loop
  _tick(now) {
    requestAnimationFrame(this._tick);
    if (this.anim) {
      const a = this.anim;
      const t = Math.min(1, (now - a.t0) / a.dur);
      const e = easeInOut(t);
      const P = this.geom.getAttribute('position'), S = this.geom.getAttribute('aSize'), A = this.geom.getAttribute('aAlpha');
      for (let k = 0; k < a.to.length; k++) P.array[k] = a.from[k] + (a.to[k] - a.from[k]) * e;
      for (let k = 0; k < a.toS.length; k++) {
        S.array[k] = a.fromS[k] + (a.toS[k] - a.fromS[k]) * e;
        A.array[k] = a.fromA[k] + (a.toA[k] - a.fromA[k]) * e;
      }
      P.needsUpdate = S.needsUpdate = A.needsUpdate = true;
      this._updateOverlays(e);
      if (t >= 1) { this.anim = null; this._grow = false; }
    }
    let insetMoved = false;
    for (const side of ['right', 'top']) {
      const want = this.focus ? this.inset[side] : 0, cur = this._insetCur[side];
      if (cur === want) continue;
      this._insetCur[side] = Math.abs(want - cur) < 0.5 ? want : cur + (want - cur) * 0.15;
      insetMoved = true;
    }
    if (insetMoved) this._applyInset();
    // spokes and trail fade in with the focus and out after it
    const want = this.focus ? 1 : 0;
    if (this._ov && this._ovOpacity !== want) {
      this._ovOpacity += (want - this._ovOpacity) * 0.12;
      if (Math.abs(want - this._ovOpacity) < 0.01) this._ovOpacity = want;
      this.spokes.material.opacity = this._ovOpacity * 0.9;
      this.trailLine.material.opacity = this._ovOpacity * 0.5;
      this.trailDots.material.uniforms.uOpacity.value = this._ovOpacity * 0.95;
      if (!this.focus && this._ovOpacity === 0) { this._ov = null; this._updateOverlays(1); }
    }
    if (this._fly) {
      const t = Math.min(1, (now - this._fly.t0) / this._fly.dur);
      const e = 1 - (1 - t) ** 3;
      this.controls.target.lerpVectors(this._fly.fromT, this._fly.toT, e);
      this.camera.position.lerpVectors(this._fly.fromC, this._fly.toC, e);
      if (t >= 1) this._fly = null;
    }
    this.controls.update();
    if (this._pointer.dirty && this._pointer.inside && !this._pointer.down) {
      this._pointer.dirty = false;
      this.onHover(this.pick(this._pointer.x, this._pointer.y), this._pointer.x, this._pointer.y);
    }
    this.renderer.render(this.scene, this.camera);
    if (this.onFrame) this.onFrame();
  }

  positions() { return this.geom.getAttribute('position')?.array; }
}
