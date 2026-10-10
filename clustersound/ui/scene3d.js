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

export class Scene3D {
  constructor(container, { onHover, onClick }) {
    this.container = container;
    this.onHover = onHover;
    this.onClick = onClick;
    this.n = 0;
    this.visible = null;     // Uint8Array mask
    this.selected = -1;
    this.labelsOn = true;
    this.anim = null;

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
    this.simRings = this._makeRing(0x6ea8fe, 7, 0);

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

  resize() {
    const w = this.container.clientWidth, h = this.container.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = w + 'px';
    this.renderer.domElement.style.height = h + 'px';
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    // point size is specified in pixels at distance 100
    this.material.uniforms.uScale.value = 100 * (this.renderer.getPixelRatio());
  }

  // data: {xyz, cls, conf}, colors: array of THREE.Color-compatible hex per class index
  setData(data, colors) {
    const n = data.cls.length;
    const sameCount = n === this.n;
    const target = new Float32Array(data.xyz);
    if (sameCount && this.geom.getAttribute('position')) {
      // animate from the current layout (e.g. PCA -> t-SNE)
      const from = this.geom.getAttribute('position').array.slice();
      this.anim = { from, to: target, t0: performance.now(), dur: 900 };
    } else {
      this.geom.setAttribute('position', new THREE.BufferAttribute(target.slice(), 3));
      this.anim = null;
    }
    this.n = n;
    this.data = data;
    this.colors = colors.map((c) => new THREE.Color(c));
    this.geom.setAttribute('aColor', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    this.geom.setAttribute('aSize', new THREE.BufferAttribute(new Float32Array(n), 1));
    this.geom.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(n), 1));
    if (!this.visible || this.visible.length !== n) this.visible = new Uint8Array(n).fill(1);
    this.refreshStyle();
    this._updateRings();
  }

  setVisible(mask) {
    this.visible = mask;
    this.refreshStyle();
  }

  refreshStyle() {
    if (!this.n) return;
    const col = this.geom.getAttribute('aColor').array;
    const size = this.geom.getAttribute('aSize').array;
    const alpha = this.geom.getAttribute('aAlpha').array;
    const { cls, conf } = this.data;
    for (let i = 0; i < this.n; i++) {
      const c = this.colors[cls[i]];
      col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
      const vis = this.visible[i];
      size[i] = vis ? 2.6 + 3.4 * conf[i] : 1.6;
      alpha[i] = vis ? 0.92 : 0.05;
    }
    this.geom.getAttribute('aColor').needsUpdate = true;
    this.geom.getAttribute('aSize').needsUpdate = true;
    this.geom.getAttribute('aAlpha').needsUpdate = true;
  }

  setSelected(i) { this.selected = i; this._updateRings(); }
  setSimilar(ids) { this.similar = ids || []; this._updateRings(); }

  _pos(i) {
    const p = this.geom.getAttribute('position').array;
    return [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]];
  }

  _updateRings() {
    const rp = this.ring.geometry.getAttribute('position');
    if (this.selected >= 0 && this.selected < this.n) {
      rp.array.set(this._pos(this.selected));
      this.ring.geometry.setDrawRange(0, 1);
    } else this.ring.geometry.setDrawRange(0, 0);
    rp.needsUpdate = true;
    const ids = (this.similar || []).filter((i) => i < this.n);
    const g = this.simRings.geometry;
    if (g.getAttribute('position').array.length < ids.length * 3) {
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(ids.length * 3), 3));
    }
    const arr = g.getAttribute('position').array;
    ids.forEach((id, k) => arr.set(this._pos(id), k * 3));
    g.setDrawRange(0, ids.length);
    g.getAttribute('position').needsUpdate = true;
  }

  focus(i) {
    const [x, y, z] = this._pos(i);
    const target = new THREE.Vector3(x, y, z);
    const offset = this.camera.position.clone().sub(this.controls.target);
    const dist = Math.min(offset.length(), 70);
    offset.setLength(dist);
    this._fly = { fromT: this.controls.target.clone(), toT: target, fromC: this.camera.position.clone(),
      toC: target.clone().add(offset), t0: performance.now(), dur: 600 };
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
    if (!d || Math.hypot(e.clientX - d[0], e.clientY - d[1]) > 4) return;
    const r = this.renderer.domElement.getBoundingClientRect();
    const i = this.pick(e.clientX - r.left, e.clientY - r.top);
    this.onClick(i);
  }

  // nearest visible point within a few pixels; ties go to the one closer to the camera
  pick(px, py, radius = 9) {
    if (!this.n) return -1;
    const w = this.container.clientWidth, h = this.container.clientHeight;
    const m = new THREE.Matrix4().multiplyMatrices(this.camera.projectionMatrix, this.camera.matrixWorldInverse).elements;
    const p = this.geom.getAttribute('position').array;
    let best = -1, bestScore = Infinity;
    const r2 = radius * radius;
    for (let i = 0; i < this.n; i++) {
      if (!this.visible[i]) continue;
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
      const t = Math.min(1, (now - this.anim.t0) / this.anim.dur);
      const e = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
      const pos = this.geom.getAttribute('position');
      const { from, to } = this.anim;
      for (let k = 0; k < to.length; k++) pos.array[k] = from[k] + (to[k] - from[k]) * e;
      pos.needsUpdate = true;
      this._updateRings();
      if (t >= 1) this.anim = null;
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
