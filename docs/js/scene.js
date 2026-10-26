/* RailSaathi AI - WebGL complaint galaxy (Three.js). */
import * as THREE from "three";

const COLORS = window.RS_COLORS;
const POINTS = window.RS_GALAXY.points;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const coarse = window.matchMedia("(pointer: coarse)").matches;
const canvas = document.getElementById("scene");
const tooltip = document.getElementById("tooltip");

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
} catch (e) {
  document.getElementById("nogl").hidden = false;
  canvas.style.display = "none";
  throw e;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight, false);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x050912, 0.012);
const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 400);
camera.position.set(0, 6, 34);

const world = new THREE.Group(); // rotated by the user
scene.add(world);

// ------------------------------------------------------------------ helpers --
function glowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, "rgba(255,255,255,1)");
  grd.addColorStop(0.25, "rgba(255,255,255,0.55)");
  grd.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grd;
  g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}
const GLOW = glowTexture();
const hex = (c) => new THREE.Color(c);

// ------------------------------------------------------------- the galaxy ----
const N = POINTS.length;
const pos = new Float32Array(N * 3);
const col = new Float32Array(N * 3);
const size = new Float32Array(N);
const seed = new Float32Array(N);
const active = new Float32Array(N).fill(1);
const activeTarget = new Float32Array(N).fill(1);
const SEV_SIZE = { Critical: 1.7, High: 1.25, Medium: 1.0, Low: 0.85 };
POINTS.forEach((p, i) => {
  pos.set([p.x, p.y, p.z], i * 3);
  const c = hex(COLORS[p.c] || "#ffffff");
  col.set([c.r, c.g, c.b], i * 3);
  size[i] = SEV_SIZE[p.s] || 1;
  seed[i] = Math.random();
});
const geo = new THREE.BufferGeometry();
geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
geo.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
geo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
geo.setAttribute("aActive", new THREE.BufferAttribute(active, 1));

const pointMat = new THREE.ShaderMaterial({
  uniforms: { uTime: { value: 0 }, uPR: { value: renderer.getPixelRatio() }, uDim: { value: 1 }, uHover: { value: -1 } },
  vertexShader: /* glsl */ `
    attribute float aSize; attribute float aSeed; attribute float aActive;
    uniform float uTime; uniform float uPR; uniform float uDim; uniform float uHover;
    varying vec3 vColor; varying float vAlpha;
    void main() {
      vec3 p = position;
      p += 0.08 * vec3(sin(uTime * 0.6 + aSeed * 40.0), cos(uTime * 0.5 + aSeed * 30.0), sin(uTime * 0.4 + aSeed * 20.0));
      vec4 mv = modelViewMatrix * vec4(p, 1.0);
      gl_Position = projectionMatrix * mv;
      float tw = 0.8 + 0.2 * sin(uTime * 2.0 + aSeed * 6.283);
      float hov = (abs(float(gl_VertexID) - uHover) < 0.5) ? 2.4 : 1.0;
      gl_PointSize = aSize * uPR * (52.0 / -mv.z) * (0.35 + 0.65 * aActive) * tw * hov;
      vColor = color;
      vAlpha = (0.06 + 0.94 * aActive) * uDim;
    }`,
  fragmentShader: /* glsl */ `
    varying vec3 vColor; varying float vAlpha;
    void main() {
      float d = length(gl_PointCoord - 0.5);
      if (d > 0.5) discard;
      float core = smoothstep(0.5, 0.0, d);
      float a = pow(core, 1.3);
      gl_FragColor = vec4(vColor * (0.7 + 1.1 * a), min(1.0, a * 1.15) * vAlpha);
    }`,
  vertexColors: true,
  transparent: true,
  depthWrite: false,
  blending: THREE.AdditiveBlending,
});
const galaxy = new THREE.Points(geo, pointMat);
world.add(galaxy);

// category centroids (for labels and new complaints)
const centroids = {};
for (const p of POINTS) {
  const c = (centroids[p.c] = centroids[p.c] || { x: 0, y: 0, z: 0, n: 0 });
  c.x += p.x; c.y += p.y; c.z += p.z; c.n++;
}
for (const k in centroids) {
  const c = centroids[k];
  centroids[k] = new THREE.Vector3(c.x / c.n, c.y / c.n, c.z / c.n);
}

// ---------------------------------------------------------------- starfield --
{
  const n = 1800, s = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const r = 80 + Math.random() * 120, th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
    s.set([r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph), r * Math.sin(ph) * Math.sin(th)], i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(s, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ size: 0.6, color: 0x8fb3ff, transparent: true, opacity: 0.55, depthWrite: false, fog: false })));
}

// ------------------------------------------------------ rail track + train --
const track = new THREE.Group();
track.rotation.set(0.42, 0, 0.12);
world.add(track);
const R = 16;
const railMat = new THREE.MeshBasicMaterial({ color: 0x7dd3fc, transparent: true, opacity: 0.75 });
for (const r of [R - 0.22, R + 0.22]) {
  const m = new THREE.Mesh(new THREE.TorusGeometry(r, 0.03, 6, 240), railMat);
  m.rotation.x = Math.PI / 2;
  track.add(m);
}
{
  const n = 170;
  const sleepers = new THREE.InstancedMesh(new THREE.BoxGeometry(0.75, 0.03, 0.1), new THREE.MeshBasicMaterial({ color: 0x334155 }), n);
  const o = new THREE.Object3D();
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    o.position.set(Math.cos(a) * R, -0.03, Math.sin(a) * R);
    o.rotation.set(0, -a, 0);
    o.updateMatrix();
    sleepers.setMatrixAt(i, o.matrix);
  }
  track.add(sleepers);
}
const train = [];
{
  const bodyMat = new THREE.MeshBasicMaterial({ color: 0x1e3a5f });
  const engineMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b });
  const windowMat = new THREE.MeshBasicMaterial({ color: 0x67e8f9 });
  for (let i = 0; i < 7; i++) {
    const car = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.42, 1.25), i === 0 ? engineMat : bodyMat);
    body.position.y = 0.26;
    car.add(body);
    if (i > 0) {
      for (const side of [-1, 1]) {
        const w = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.1, 1.0), windowMat);
        w.position.set(side * 0.26, 0.33, 0);
        car.add(w);
      }
    } else {
      const lamp = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color: 0xfff1c1, blending: THREE.AdditiveBlending, depthWrite: false }));
      lamp.scale.set(1.6, 1.6, 1);
      lamp.position.set(0, 0.3, 0.7);
      car.add(lamp);
    }
    track.add(car);
    train.push(car);
  }
}
let trainAngle = 0;
function placeTrain(dt) {
  trainAngle += dt * (reduceMotion ? 0.03 : 0.12);
  train.forEach((car, i) => {
    const a = trainAngle - i * 0.085;
    car.position.set(Math.cos(a) * R, 0, Math.sin(a) * R);
    const ahead = a + 0.01;
    car.lookAt(track.localToWorld(new THREE.Vector3(Math.cos(ahead) * R, 0, Math.sin(ahead) * R)));
  });
}

// ------------------------------------------------------------ category labels --
const labelBox = document.getElementById("labels");
const labels = {};
for (const k in centroids) {
  const d = document.createElement("div");
  d.className = "cat-label on";
  d.style.setProperty("--c", COLORS[k]);
  d.textContent = k;
  labelBox.appendChild(d);
  labels[k] = d;
}
const tmpV = new THREE.Vector3();
function placeLabels() {
  const w = window.innerWidth, h = window.innerHeight;
  for (const k in labels) {
    tmpV.copy(centroids[k]).multiplyScalar(1.12).applyMatrix4(world.matrixWorld).project(camera);
    const el = labels[k];
    if (tmpV.z > 1) { el.style.display = "none"; continue; }
    el.style.display = "";
    el.style.left = ((tmpV.x + 1) / 2) * w + "px";
    el.style.top = ((1 - tmpV.y) / 2) * h + "px";
  }
}

// ------------------------------------------------------------ legend & filters --
const hidden = new Set();
const onlyErrors = document.getElementById("toggle-errors");
const onlyCritical = document.getElementById("toggle-critical");
const legend = document.getElementById("legend");
Object.keys(COLORS).forEach((k) => {
  const b = document.createElement("button");
  b.type = "button";
  b.style.setProperty("--c", COLORS[k]);
  b.innerHTML = `<i></i>${k}`;
  b.setAttribute("aria-pressed", "true");
  b.addEventListener("click", () => {
    hidden.has(k) ? hidden.delete(k) : hidden.add(k);
    b.classList.toggle("off", hidden.has(k));
    b.setAttribute("aria-pressed", String(!hidden.has(k)));
    labels[k].classList.toggle("on", !hidden.has(k));
    applyFilters();
  });
  legend.appendChild(b);
});
function applyFilters() {
  let shown = 0, correct = 0;
  POINTS.forEach((p, i) => {
    const on = !hidden.has(p.c) && (!onlyErrors.checked || p.pc !== p.c) && (!onlyCritical.checked || p.s === "Critical");
    activeTarget[i] = on ? 1 : 0;
    if (on) { shown++; if (p.pc === p.c) correct++; }
  });
  document.getElementById("galaxy-stats").textContent =
    `${shown.toLocaleString()} complaints shown · model accuracy on them: ${shown ? ((100 * correct) / shown).toFixed(1) : "0"}%`;
}
onlyErrors.checked = onlyCritical.checked = false; // ignore form state restored by the browser
onlyErrors.addEventListener("change", applyFilters);
onlyCritical.addEventListener("change", applyFilters);
applyFilters();

// ---------------------------------------------------------------- camera story --
const PRESETS = {
  hero: { pos: [0, 5, 33], off: [7, 0, 0], dim: 1 },
  explore: { pos: [0, 3, 25], off: [6, 0, 0], dim: 1 },
  demo: { pos: [0, 2, 23], off: [7, 0, 0], dim: 1 },
  pipeline: { pos: [0, 16, 42], off: [0, -2, 0], dim: 0.45 },
  results: { pos: [0, 24, 52], off: [0, 0, 0], dim: 0.3 },
};
let preset = PRESETS.hero;
const camTarget = new THREE.Vector3(...preset.pos);
const offTarget = new THREE.Vector3(...preset.off);
const offset = new THREE.Vector3(...preset.off);
function narrow() { return window.innerWidth < 900; }
function setPreset(name) {
  preset = PRESETS[name] || PRESETS.hero;
  document.body.className = document.body.className.replace(/\bcam-\w+/g, "").trim() + " cam-" + name;
  camTarget.set(...preset.pos);
  if (narrow()) {
    camTarget.multiplyScalar(1.25);
    offTarget.set(0, name === "explore" || name === "demo" ? 4 : 2, 0);
  } else offTarget.set(...preset.off);
}
const sectionIO = new IntersectionObserver((ents) => {
  ents.forEach((en) => { if (en.isIntersecting) setPreset(en.target.dataset.cam); });
}, { threshold: 0.35 });
document.querySelectorAll("[data-cam]").forEach((s) => sectionIO.observe(s));
setPreset("hero");

// ------------------------------------------------------------ drag / hover --
let yaw = 0, pitch = 0.15, vYaw = 0, vPitch = 0;
let dragging = false, lastX = 0, lastY = 0, downX = 0, downY = 0;
const mouse = new THREE.Vector2(9, 9);
const parallax = new THREE.Vector2();
canvas.addEventListener("pointerdown", (e) => {
  dragging = true; lastX = downX = e.clientX; lastY = downY = e.clientY;
  canvas.classList.add("dragging");
});
window.addEventListener("pointerup", (e) => {
  if (dragging && Math.hypot(e.clientX - downX, e.clientY - downY) < 6 && e.target === canvas) pick(e.clientX, e.clientY, true);
  dragging = false;
  canvas.classList.remove("dragging");
});
canvas.addEventListener("pointercancel", () => { dragging = false; canvas.classList.remove("dragging"); });
window.addEventListener("pointermove", (e) => {
  parallax.set(e.clientX / window.innerWidth - 0.5, e.clientY / window.innerHeight - 0.5);
  if (dragging) {
    vYaw = (e.clientX - lastX) * 0.005;
    vPitch = (e.clientY - lastY) * 0.003;
    yaw += vYaw; pitch = THREE.MathUtils.clamp(pitch + vPitch, -0.9, 0.9);
    lastX = e.clientX; lastY = e.clientY;
    hideTip();
  } else if (!coarse && e.target === canvas) {
    pick(e.clientX, e.clientY, false);
  } else if (e.target !== canvas) hideTip();
});

const ray = new THREE.Raycaster();
ray.params.Points.threshold = 0.28;
function pick(x, y, isTap) {
  mouse.set((x / window.innerWidth) * 2 - 1, -(y / window.innerHeight) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const hits = ray.intersectObject(galaxy).filter((h) => activeTarget[h.index] > 0.5);
  if (!hits.length) { if (isTap || !coarse) hideTip(); return; }
  const i = hits[0].index, p = POINTS[i];
  pointMat.uniforms.uHover.value = i;
  const ok = p.pc === p.c;
  tooltip.innerHTML = `<div class="tt-cat" style="color:${COLORS[p.c]}">${p.c}</div>
    <div>${escapeHtml(p.t)}</div>
    <div class="tt-meta">${p.s} severity · ${p.m} · train ${p.tn} (${p.tt})<br>
    Model said: <span class="${ok ? "" : "bad"}">${p.pc}${ok ? " ✓" : " ✗"}</span></div>`;
  const tx = Math.min(x + 16, window.innerWidth - 336), ty = Math.min(y + 16, window.innerHeight - 160);
  tooltip.style.left = Math.max(8, tx) + "px";
  tooltip.style.top = Math.max(8, ty) + "px";
  tooltip.classList.add("show");
  canvas.style.cursor = "pointer";
}
function hideTip() {
  tooltip.classList.remove("show");
  pointMat.uniforms.uHover.value = -1;
  canvas.style.cursor = "";
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ------------------------------------------------- new complaint fly-in --
const flights = [];
const userPoints = new THREE.Group();
world.add(userPoints);
window.addEventListener("rs:classified", (ev) => {
  const r = ev.detail;
  const target = centroids[r.category].clone().add(new THREE.Vector3((Math.random() - 0.5) * 1.6, (Math.random() - 0.5) * 1.6, (Math.random() - 0.5) * 1.6));
  // start just in front of the camera, expressed in world-group coordinates
  const start = world.worldToLocal(camera.position.clone().add(new THREE.Vector3(0, -1.5, -6).applyQuaternion(camera.quaternion)));
  const mid = start.clone().lerp(target, 0.5).add(new THREE.Vector3(0, 6, 0));
  const curve = new THREE.QuadraticBezierCurve3(start, mid, target);
  const color = hex(COLORS[r.category]);
  const orb = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  orb.scale.set(2.2, 2.2, 1);
  userPoints.add(orb);
  const trailGeo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(60));
  trailGeo.setDrawRange(0, 0);
  const trail = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.8, blending: THREE.AdditiveBlending }));
  userPoints.add(trail);
  flights.push({ curve, orb, trail, t: reduceMotion ? 1 : 0, cat: r.category, done: false, life: 0 });
  // dim everything except the predicted category for a moment
  POINTS.forEach((p, i) => { activeTarget[i] = p.c === r.category ? 1 : 0.15; });
  clearTimeout(window.__rsRestore);
  window.__rsRestore = setTimeout(applyFilters, 3200);
});
function updateFlights(dt) {
  for (const f of flights) {
    if (!f.done) {
      f.t = Math.min(1, f.t + dt / 1.6);
      const k = 1 - Math.pow(1 - f.t, 3);
      f.orb.position.copy(f.curve.getPoint(k));
      f.trail.geometry.setDrawRange(0, Math.floor(k * 61));
      if (f.t >= 1) {
        f.done = true;
        const el = labels[f.cat];
        el.classList.remove("pulse"); void el.offsetWidth; el.classList.add("pulse");
      }
    } else {
      f.life += dt;
      f.trail.material.opacity = Math.max(0, 0.8 - f.life * 0.4);
      const s = 1.2 + 0.25 * Math.sin(f.life * 4);
      f.orb.scale.set(s, s, 1);
    }
  }
}

// ---------------------------------------------------------------- loop --
let lastW = 0, lastH = 0;
function resize() {
  const w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  setPreset(preset === PRESETS.hero ? "hero" : Object.keys(PRESETS).find((k) => PRESETS[k] === preset));
}
window.addEventListener("resize", resize);

const clock = new THREE.Clock();
const look = new THREE.Vector3();
let running = true;
document.addEventListener("visibilitychange", () => { running = !document.hidden; if (running) { clock.getDelta(); loop(); } });

function loop() {
  if (!running) return;
  // keep the drawing buffer in sync with the canvas (covers viewport changes that fire no resize event)
  if (canvas.clientWidth !== lastW || canvas.clientHeight !== lastH) {
    lastW = canvas.clientWidth; lastH = canvas.clientHeight;
    resize();
  }
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;
  pointMat.uniforms.uTime.value = reduceMotion ? 0 : t;

  if (!dragging) {
    vYaw *= 0.94; vPitch *= 0.9;
    yaw += vYaw + (reduceMotion ? 0 : dt * 0.06);
    pitch = THREE.MathUtils.clamp(pitch + vPitch, -0.9, 0.9);
  }
  world.rotation.set(pitch, yaw, 0);
  offset.lerp(offTarget, 0.04);
  world.position.copy(offset);

  const px = coarse || reduceMotion ? 0 : parallax.x * 2.5, py = coarse || reduceMotion ? 0 : parallax.y * 1.5;
  camera.position.lerp(tmpV.set(camTarget.x + px, camTarget.y - py, camTarget.z), 0.035);
  look.lerp(offset, 0.05);
  camera.lookAt(look);

  pointMat.uniforms.uDim.value += (preset.dim - pointMat.uniforms.uDim.value) * 0.05;
  railMat.opacity = 0.75 * pointMat.uniforms.uDim.value;
  for (let i = 0; i < N; i++) active[i] += (activeTarget[i] - active[i]) * 0.12;
  geo.attributes.aActive.needsUpdate = true;

  placeTrain(dt);
  updateFlights(dt);
  world.updateMatrixWorld();
  placeLabels();
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();
