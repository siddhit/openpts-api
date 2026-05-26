'use strict';

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────
const API = 'https://openpts-api.vercel.app';

// MODAPTS category palette — must match Tailwind config in index.html
const CAT_TEXT = {
  walk:       'text-cat-walk',
  bend:       'text-cat-bend',
  get:        'text-cat-get',
  move:       'text-cat-move',
  put:        'text-cat-put',
  sit:        'text-cat-sit',
  stand:      'text-cat-sit',
  eye_action: 'text-cat-eye',
};
const CAT_BG_TINT = {
  walk:       'bg-slate-50',
  bend:       'bg-amber-50',
  get:        'bg-emerald-50',
  move:       'bg-blue-50',
  put:        'bg-violet-50',
  sit:        'bg-yellow-50',
  stand:      'bg-yellow-50',
  eye_action: 'bg-cyan-50',
};

// Body-region strain weights (mirrors ergonomics.py exactly)
const STRAIN = {
  body: 3.5, full_arm: 2.5, arm: 2.0, hand: 1.5,
  leg: 1.2, fingers: 1.0, eyes: 0.5,
};
const RSI_MAX = 150;

// ─────────────────────────────────────────────────────────────────────────────
// Motion code library — mirrors seed_data.py
// ─────────────────────────────────────────────────────────────────────────────
const MOTION_CODES = [
  // MOVE
  { code: 'M1',  cat: 'move',       region: 'fingers',  mods: 1,
    desc: 'Move object — very short distance (finger length)' },
  { code: 'M2',  cat: 'move',       region: 'hand',     mods: 2,
    desc: 'Move object — short distance (hand length)' },
  { code: 'M3',  cat: 'move',       region: 'arm',      mods: 3,
    desc: 'Move object — medium distance (forearm length)' },
  { code: 'M4',  cat: 'move',       region: 'arm',      mods: 4,
    desc: 'Move object — long distance (upper-arm length)' },
  { code: 'M5',  cat: 'move',       region: 'full_arm', mods: 5,
    desc: 'Move object — very long distance (full arm extension)' },

  // GET
  { code: 'G0',  cat: 'get',        region: 'fingers',  mods: 0,
    desc: 'Contact grasp — no finger closure, object touches hand' },
  { code: 'G1',  cat: 'get',        region: 'fingers',  mods: 1,
    desc: 'Simple grasp — fingers close on easy-to-pick object' },
  { code: 'G3',  cat: 'get',        region: 'hand',     mods: 3,
    desc: 'Complex grasp — bulky, nested, or slippery; deliberate finger control' },
  { code: 'R2',  cat: 'get',        region: 'hand',     mods: 2,
    desc: 'Regrasp — adjust grip on already-held object mid-carry' },

  // PUT
  { code: 'P0',  cat: 'put',        region: 'fingers',  mods: 0,
    desc: 'Loose placement — drop or toss, no location control' },
  { code: 'P2',  cat: 'put',        region: 'hand',     mods: 2,
    desc: 'Approximate placement — surface, bin, pallet (±25 mm)' },
  { code: 'P5',  cat: 'put',        region: 'hand',     mods: 5,
    desc: 'Tight-tolerance placement — fixture, hole, mated part (±2 mm)' },
  { code: 'A4',  cat: 'put',        region: 'fingers',  mods: 4,
    desc: 'Apply pressure — sustained force (button press, snap fit, lever)' },

  // WALK
  { code: 'W5',  cat: 'walk',       region: 'leg',      mods: 5,
    desc: 'Walk — one pace (single step). Code once per step.' },
  { code: 'F3',  cat: 'walk',       region: 'leg',      mods: 3,
    desc: 'Foot motion — pedal or foot-switch operation' },

  // BEND
  { code: 'B17', cat: 'bend',       region: 'body',     mods: 17,
    desc: 'Bend and arise — trunk flexion to floor / low level and return upright' },

  // SIT / STAND
  { code: 'S30', cat: 'sit',        region: 'body',     mods: 30,
    desc: 'Sit — lower body from standing to seated position' },
  { code: 'ST30',cat: 'stand',      region: 'body',     mods: 30,
    desc: 'Stand — rise from seated to standing position' },

  // EYE
  { code: 'E2',  cat: 'eye_action', region: 'eyes',     mods: 2,
    desc: 'Eye focus — deliberate shift of gaze to a new target' },
];

// Family display data
const FAMILIES = [
  { id: 'move',  letter: 'M',      name: 'Move',           cat: 'move',
    blurb: 'Object held and transported. Subscript = distance class (which body part moves).' },
  { id: 'get',   letter: 'G / R',  name: 'Get & regrasp',  cat: 'get',
    blurb: 'Secure control of an object. Subscript = complexity of grasp.' },
  { id: 'put',   letter: 'P / A',  name: 'Put & apply',    cat: 'put',
    blurb: 'Release at a target. Subscript = precision. Apply = sustained force.' },
  { id: 'walk',  letter: 'W / F',  name: 'Walk & foot',    cat: 'walk',
    blurb: 'Walking paces (per step) and foot-pedal operation.' },
  { id: 'bend',  letter: 'B',      name: 'Bend & arise',   cat: 'bend',
    blurb: 'Trunk flexion to a low level and return to upright — the highest single-element load.' },
  { id: 'sit',   letter: 'S / ST', name: 'Sit & stand',    cat: 'sit',
    blurb: 'Sit-down and stand-up transitions. Includes hip and knee load.' },
  { id: 'eye',   letter: 'E',      name: 'Eye action',     cat: 'eye_action',
    blurb: 'Deliberate gaze shifts to a new visual target. Not blinking or incidental gaze.' },
];

const FAMILY_OF_CAT = {
  move: 'move', get: 'get', put: 'put',
  walk: 'walk', bend: 'bend',
  sit: 'sit', stand: 'sit',
  eye_action: 'eye',
};

// ─────────────────────────────────────────────────────────────────────────────
// Build motion-code library grid
// ─────────────────────────────────────────────────────────────────────────────
function buildCodesGrid() {
  const grid = document.getElementById('codes-grid');
  if (!grid) return;

  grid.innerHTML = FAMILIES.map(fam => {
    const codes   = MOTION_CODES.filter(m => FAMILY_OF_CAT[m.cat] === fam.id);
    const catText = CAT_TEXT[fam.cat];
    const tint    = CAT_BG_TINT[fam.cat];

    return `
      <div class="grid md:grid-cols-12 gap-6 items-start">
        <!-- Family header -->
        <div class="md:col-span-3">
          <div class="${tint} border hairline rounded-lg p-5 sticky top-20">
            <div class="flex items-baseline gap-3 mb-2">
              <span class="font-mono font-bold text-[28px] ${catText} leading-none">${fam.letter}</span>
              <span class="text-[11px] font-mono text-faint">${codes.length} code${codes.length === 1 ? '' : 's'}</span>
            </div>
            <p class="font-semibold text-[15px] text-ink">${fam.name}</p>
            <p class="text-[12.5px] text-dim mt-2 leading-[1.55]">${fam.blurb}</p>
          </div>
        </div>

        <!-- Codes -->
        <div class="md:col-span-9 grid sm:grid-cols-2 gap-px bg-rule border hairline rounded-lg overflow-hidden">
          ${codes.map(m => `
            <div class="bg-panel p-4 hover:bg-paper transition-colors">
              <div class="flex items-baseline justify-between mb-1.5">
                <span class="font-mono font-bold text-[20px] ${catText}">${m.code}</span>
                <span class="font-mono text-[11px] text-faint">${m.region.replace('_', ' ')}</span>
              </div>
              <p class="text-[12.5px] text-dim leading-[1.55]">${m.desc}</p>
              <div class="flex items-center gap-4 mt-3 pt-3 border-t hairline text-[11px] font-mono">
                <span class="text-ink"><span class="text-faint">MODs</span> ${m.mods}</span>
                <span class="text-ink"><span class="text-faint">time</span> ${(m.mods * 0.129).toFixed(3)}s</span>
                <span class="text-ink"><span class="text-faint">cat</span> ${m.cat.replace('_', ' ')}</span>
              </div>
            </div>
          `).join('')}
          ${codes.length % 2 ? '<div class="bg-paper"></div>' : ''}
        </div>
      </div>
    `;
  }).join('');
}

// ─────────────────────────────────────────────────────────────────────────────
// Sequence (sample task: heavy box, floor → table)
// ─────────────────────────────────────────────────────────────────────────────
const DEFAULT_SEQUENCE = [
  { code:'W5',  qty:4, label:'Walk to box',    cat:'walk', region:'leg',      mv:5,  start_pct:0.000, end_pct:0.278 },
  { code:'B17', qty:1, label:'Bend to floor',  cat:'bend', region:'body',     mv:17, start_pct:0.278, end_pct:0.514 },
  { code:'G3',  qty:1, label:'Complex grasp',  cat:'get',  region:'hand',     mv:3,  start_pct:0.514, end_pct:0.556 },
  { code:'M5',  qty:1, label:'Lift to chest',  cat:'move', region:'full_arm', mv:5,  start_pct:0.556, end_pct:0.625 },
  { code:'W5',  qty:5, label:'Walk to table',  cat:'walk', region:'leg',      mv:5,  start_pct:0.625, end_pct:0.972 },
  { code:'P2',  qty:1, label:'Place on table', cat:'put',  region:'hand',     mv:2,  start_pct:0.972, end_pct:1.000 },
];
let SEQ = DEFAULT_SEQUENCE.map(s => ({ ...s }));

// ─────────────────────────────────────────────────────────────────────────────
// Annotations — loaded from annotations.json when available.
// window.setAnnotations(json) may also be called from the browser console
// or programmatically after loading the demo with a known video.
// ─────────────────────────────────────────────────────────────────────────────
let poseFrames = [];

window.setAnnotations = function(json) {
  if (json.motion_segments && json.motion_segments.length) {
    SEQ = json.motion_segments.map(s => ({
      code:      s.code,
      qty:       s.quantity,
      label:     s.label || s.code,
      cat:       s.category || 'move',
      region:    s.body_region || s.region || 'arm',
      mv:        s.mod_value,
      start_pct: s.start_pct,
      end_pct:   s.end_pct,
    }));
  }
  if (json.pose_keyframes) {
    poseFrames = json.pose_keyframes;
  }
  buildFeed();
  console.log('✅ Annotations loaded:', SEQ.length, 'segments,', poseFrames.length, 'pose frames');
};

// Auto-fetch annotations.json from the same directory (works on Vercel, not file://)
fetch('./annotations.json')
  .then(r => r.ok ? r.json() : null)
  .then(j => { if (j) window.setAnnotations(j); })
  .catch(() => {}); // silent fail — annotations are optional

// ─────────────────────────────────────────────────────────────────────────────
// Sequence feed
// ─────────────────────────────────────────────────────────────────────────────
let activeIdx = -1;

function buildFeed() {
  const feed = document.getElementById('seq-feed');
  if (!feed) return;

  feed.innerHTML = SEQ.map((s, i) => {
    const catText = CAT_TEXT[s.cat] || 'text-cat-walk';
    const mods    = s.mv * s.qty;
    const t       = (mods * 0.129).toFixed(2);
    const codeStr = s.qty > 1
      ? `${s.code} <span class="text-faint">×${s.qty}</span>`
      : s.code;
    return `
      <div id="seg${i}"
           class="flex items-center gap-3 px-3 py-2.5 rounded-md border hairline bg-panel
                  transition-all duration-300 opacity-55"
           data-i="${i}">
        <div id="seg${i}-icon" class="w-4 h-4 flex items-center justify-center flex-shrink-0">
          <div class="w-1.5 h-1.5 rounded-full bg-zinc-300"></div>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-baseline gap-2">
            <span class="font-mono font-bold text-[13px] ${catText}">${codeStr}</span>
            <span class="text-[12px] text-ink truncate">${s.label}</span>
          </div>
          <div class="text-[11px] text-faint mt-0.5 capitalize font-mono">
            ${s.region.replace('_', ' ')} · ${mods} MODs · ${t}s
          </div>
        </div>
        <div class="text-[11px] font-mono text-faint flex-shrink-0 tab-nums">${mods}</div>
      </div>`;
  }).join('');
}

function activateSeg(i) {
  if (activeIdx >= 0) deactivateSeg(activeIdx);
  activeIdx = i;
  if (i < 0) return;
  const el = document.getElementById(`seg${i}`);
  if (!el) return;
  const s = SEQ[i];

  el.classList.remove('opacity-55', 'bg-panel');
  el.classList.add('opacity-100', 'bg-accenttint', 'border-accent', 'seg-active');

  // Update both chips (real video + sample stage)
  document.getElementById('chip-code').textContent  = s.code;
  document.getElementById('chip-label').textContent = s.label;
  document.getElementById('code-chip').classList.remove('hidden');

  document.getElementById('sample-chip-code').textContent  = s.code;
  document.getElementById('sample-chip-label').textContent = s.label;
  document.getElementById('sample-chip').classList.remove('hidden');

  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function deactivateSeg(i) {
  const el = document.getElementById(`seg${i}`);
  if (!el) return;
  el.classList.remove('opacity-100', 'bg-accenttint', 'border-accent', 'seg-active');
  el.classList.add('opacity-55', 'bg-panel');
}

function completeSeg(i) {
  const el   = document.getElementById(`seg${i}`);
  const icon = document.getElementById(`seg${i}-icon`);
  if (!el) return;
  el.classList.remove('seg-active', 'border-accent', 'bg-accenttint', 'opacity-100');
  el.classList.add('bg-panel', 'opacity-70');
  if (icon) icon.innerHTML = `
    <svg class="w-3.5 h-3.5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
    </svg>`;
}

function resetFeed() {
  activeIdx = -1;
  buildFeed();
}

// ─────────────────────────────────────────────────────────────────────────────
// Running stats
// ─────────────────────────────────────────────────────────────────────────────
const sMods  = () => document.getElementById('s-mods');
const sTime  = () => document.getElementById('s-time');
const sRsi   = () => document.getElementById('s-rsi');
const rsiBar = () => document.getElementById('rsi-bar');
const rsiCat = () => document.getElementById('rsi-cat');

function updateStats(elapsedMods) {
  const time = (elapsedMods * 0.129).toFixed(2);
  let raw = 0, consumed = 0;
  for (const s of SEQ) {
    const segMods  = s.mv * s.qty;
    const contrib  = Math.min(segMods, Math.max(0, elapsedMods - consumed));
    raw      += contrib * (STRAIN[s.region] || 1.0);
    consumed += segMods;
    if (consumed >= elapsedMods) break;
  }
  const rsi = Math.min(10, (raw / RSI_MAX) * 10);

  sMods().textContent = Math.round(elapsedMods);
  sTime().textContent = time;
  sRsi().textContent  = rsi.toFixed(1);

  const pct = rsi / 10 * 100;
  rsiBar().style.width = pct + '%';

  let bg, catLabel, catColor;
  if      (rsi >= 7.5) { bg = '#dc2626'; catLabel = 'VERY HIGH'; catColor = 'text-red-600'; }
  else if (rsi >= 5.0) { bg = '#ea580c'; catLabel = 'HIGH';      catColor = 'text-accent';  }
  else if (rsi >= 2.5) { bg = '#ca8a04'; catLabel = 'MODERATE';  catColor = 'text-yellow-700'; }
  else                 { bg = '#059669'; catLabel = 'LOW';        catColor = 'text-emerald-600'; }

  rsiBar().style.background = bg;
  const cat = rsiCat();
  cat.textContent = catLabel;
  cat.className   = `text-[11px] font-mono font-semibold ${catColor}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sample mode — simulated playback (no video file required)
// ─────────────────────────────────────────────────────────────────────────────
let sampleRunning = false;
let sampleStart   = 0;
const SAMPLE_DURATION_MS = 9500;

function startSample() {
  if (sampleRunning) return;
  sampleRunning = true;

  resetFeed();
  document.getElementById('study-card').classList.add('hidden');
  document.getElementById('card-loading').classList.remove('hidden');
  document.getElementById('card-results').classList.add('hidden');

  document.getElementById('drop-zone').classList.add('hidden');
  document.getElementById('video-wrap').classList.add('hidden');
  document.getElementById('sample-stage').classList.remove('hidden');

  document.getElementById('sample-box').style.left    = '12%';
  document.getElementById('sample-box').style.bottom  = '22%';
  document.getElementById('sample-box').style.opacity = '1';
  positionFigure(0);

  sampleStart = performance.now();
  requestAnimationFrame(stepSample);
}

function positionFigure(progress) {
  const fig   = document.getElementById('sample-figure');
  const torso = document.getElementById('sf-torso');
  const head  = document.getElementById('sf-head');
  const arml  = document.getElementById('sf-arml');
  const armr  = document.getElementById('sf-armr');
  const legl  = document.getElementById('sf-legl');
  const legr  = document.getElementById('sf-legr');
  const box   = document.getElementById('sample-box');

  const seg = SEQ.findIndex(s => progress >= s.start_pct && progress < s.end_pct);
  const idx  = Math.max(0, seg);
  const s    = SEQ[idx] || SEQ[SEQ.length - 1];
  const local = (progress - s.start_pct) / Math.max(0.0001, s.end_pct - s.start_pct);

  let figLeft    = 5;
  let bend       = 0;
  let armReach   = 0;
  let boxLeft    = 12;
  let boxBottom  = 22;
  let boxOpacity = 1;

  if (s.code === 'W5' && s.label === 'Walk to box') {
    figLeft = 5 + local * 5;
    const phase = (progress * 40) % (Math.PI * 2);
    legl.setAttribute('x2', 18 + Math.sin(phase) * 6);
    legr.setAttribute('x2', 42 - Math.sin(phase) * 6);
    arml.setAttribute('x2', 14 - Math.sin(phase) * 4);
    armr.setAttribute('x2', 46 + Math.sin(phase) * 4);
  } else if (s.code === 'B17') {
    figLeft  = 10;
    bend     = local * 36;
    armReach = local;
  } else if (s.code === 'G3') {
    figLeft    = 10;
    bend       = 36;
    armReach   = 1;
    boxOpacity = 1 - local * 0.5;
  } else if (s.code === 'M5') {
    figLeft   = 10;
    bend      = 36 * (1 - local);
    armReach  = 1 - local;
    boxLeft   = 12;
    boxBottom = 22 + local * 14;
  } else if (s.code === 'W5' && s.label === 'Walk to table') {
    figLeft   = 10 + local * 60;
    boxLeft   = 12 + local * 60;
    boxBottom = 36;
    const phase = (progress * 40) % (Math.PI * 2);
    legl.setAttribute('x2', 18 + Math.sin(phase) * 6);
    legr.setAttribute('x2', 42 - Math.sin(phase) * 6);
    arml.setAttribute('x2', 18 + Math.sin(phase) * 2);
    armr.setAttribute('x2', 42 - Math.sin(phase) * 2);
  } else if (s.code === 'P2') {
    figLeft   = 70;
    boxLeft   = 75;
    boxBottom = 28;
  }

  fig.style.left   = figLeft + '%';
  fig.style.bottom = '22%';
  torso.setAttribute('y2', 65 + bend);
  legl.setAttribute('y1', 65 + bend);
  legr.setAttribute('y1', 65 + bend);
  head.setAttribute('cy', 14 + bend * 0.4);

  if (bend > 0) {
    torso.setAttribute('x2', 30 + bend * 0.3);
    head.setAttribute('cx', 30 + bend * 0.45);
    arml.setAttribute('x1', 30 + bend * 0.18);
    armr.setAttribute('x1', 30 + bend * 0.18);
    arml.setAttribute('y1', 35 + bend * 0.4);
    armr.setAttribute('y1', 35 + bend * 0.4);
    arml.setAttribute('x2', 14 + bend * 0.4);
    armr.setAttribute('x2', 46 + bend * 0.4);
    arml.setAttribute('y2', 55 + bend * 0.6);
    armr.setAttribute('y2', 55 + bend * 0.6);
  } else {
    torso.setAttribute('x2', 30);
    head.setAttribute('cx', 30);
    arml.setAttribute('x1', 30);
    armr.setAttribute('x1', 30);
    arml.setAttribute('y1', 35);
    armr.setAttribute('y1', 35);
    if (armReach > 0) {
      arml.setAttribute('x2', 18);
      arml.setAttribute('y2', 55 - armReach * 18);
      armr.setAttribute('x2', 42);
      armr.setAttribute('y2', 55 - armReach * 18);
    }
  }

  box.style.left    = boxLeft   + '%';
  box.style.bottom  = boxBottom + '%';
  box.style.opacity = boxOpacity;
}

function stepSample(now) {
  if (!sampleRunning) return;
  const elapsed = now - sampleStart;
  const t = Math.min(1, elapsed / SAMPLE_DURATION_MS);

  document.getElementById('sample-progress').style.width = (t * 100) + '%';

  const newIdx = SEQ.findIndex(s => t >= s.start_pct && t < s.end_pct);
  if (newIdx !== activeIdx && t < 1) {
    if (activeIdx >= 0 && newIdx > activeIdx) completeSeg(activeIdx);
    activateSeg(newIdx);
  }

  let elapsedMods = 0;
  for (let i = 0; i < SEQ.length; i++) {
    const s = SEQ[i], sm = s.mv * s.qty;
    if      (t >= s.end_pct)   { elapsedMods += sm; }
    else if (t >= s.start_pct) {
      const segProg = (t - s.start_pct) / (s.end_pct - s.start_pct);
      elapsedMods += sm * segProg;
      break;
    }
  }
  updateStats(elapsedMods);
  positionFigure(t);

  if (t < 1) {
    requestAnimationFrame(stepSample);
  } else {
    SEQ.forEach((_, i) => completeSeg(i));
    activateSeg(-1);
    document.getElementById('sample-chip').classList.add('hidden');
    document.getElementById('code-chip').classList.add('hidden');
    updateStats(SEQ.reduce((s, seg) => s + seg.mv * seg.qty, 0));
    document.getElementById('sample-progress').style.width = '100%';
    document.getElementById('study-card').classList.remove('hidden');
    callAPI();
    sampleRunning = false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Real video upload
// ─────────────────────────────────────────────────────────────────────────────
const vid      = () => document.getElementById('vid');
const dropZone = () => document.getElementById('drop-zone');
const vidWrap  = () => document.getElementById('video-wrap');
const canvas   = () => document.getElementById('skeleton-canvas');
const fileInp  = () => document.getElementById('file-input');

function loadVideoFile(file) {
  resetFeed();
  document.getElementById('study-card').classList.add('hidden');
  document.getElementById('card-loading').classList.remove('hidden');
  document.getElementById('card-results').classList.add('hidden');

  const v = vid();
  v.src = URL.createObjectURL(file);
  dropZone().classList.add('hidden');
  document.getElementById('sample-stage').classList.add('hidden');
  vidWrap().classList.remove('hidden');
  v.play().catch(() => {});
}

function attachVideoHandlers() {
  const v   = vid();
  const c   = canvas();
  const ctx = c.getContext('2d');

  v.addEventListener('loadedmetadata', () => {
    c.width  = v.videoWidth  || v.offsetWidth;
    c.height = v.videoHeight || v.offsetHeight;
  });

  v.addEventListener('timeupdate', () => {
    if (!v.duration) return;
    const progress = v.currentTime / v.duration;
    document.getElementById('progress-bar').style.width = (progress * 100) + '%';

    const newIdx = SEQ.findIndex(s => progress >= s.start_pct && progress < s.end_pct);
    if (newIdx !== activeIdx) {
      if (activeIdx >= 0 && newIdx > activeIdx) completeSeg(activeIdx);
      activateSeg(newIdx);
    }

    let elapsed = 0;
    for (let i = 0; i < SEQ.length; i++) {
      const s = SEQ[i], sm = s.mv * s.qty;
      if      (i < newIdx)  { elapsed += sm; }
      else if (i === newIdx) {
        const segProg = (progress - s.start_pct) / Math.max(0.001, s.end_pct - s.start_pct);
        elapsed += sm * Math.min(1, Math.max(0, segProg));
        break;
      }
    }
    updateStats(elapsed);

    if (poseFrames.length) {
      const lm = getSkeletonAtTime(v.currentTime * 1000);
      drawSkeleton(ctx, c.width, c.height, lm);
    }
  });

  v.addEventListener('ended', async () => {
    SEQ.forEach((_, i) => completeSeg(i));
    activateSeg(-1);
    document.getElementById('code-chip').classList.add('hidden');
    updateStats(SEQ.reduce((s, seg) => s + seg.mv * seg.qty, 0));
    document.getElementById('progress-bar').style.width = '100%';
    document.getElementById('study-card').classList.remove('hidden');
    await callAPI();
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Skeleton overlay
// ─────────────────────────────────────────────────────────────────────────────
const CONNECTIONS = [
  ['left_shoulder',  'right_shoulder'],
  ['left_shoulder',  'left_elbow'],  ['left_elbow',  'left_wrist'],
  ['right_shoulder', 'right_elbow'], ['right_elbow', 'right_wrist'],
  ['left_shoulder',  'left_hip'],    ['right_shoulder', 'right_hip'],
  ['left_hip',       'right_hip'],
  ['left_hip',       'left_knee'],   ['left_knee',  'left_ankle'],
  ['right_hip',      'right_knee'],  ['right_knee', 'right_ankle'],
];

function drawSkeleton(ctx, W, H, landmarks) {
  ctx.clearRect(0, 0, W, H);
  if (!landmarks) return;
  ctx.strokeStyle = 'rgba(194,65,12,0.9)';
  ctx.lineWidth   = 2.5;
  for (const [a, b] of CONNECTIONS) {
    const pa = landmarks[a], pb = landmarks[b];
    if (pa && pb && pa.visibility > 0.4 && pb.visibility > 0.4) {
      ctx.beginPath();
      ctx.moveTo(pa.x * W, pa.y * H);
      ctx.lineTo(pb.x * W, pb.y * H);
      ctx.stroke();
    }
  }
  ctx.fillStyle = 'rgba(24,24,27,0.95)';
  for (const lm of Object.values(landmarks)) {
    if (lm.visibility > 0.4) {
      ctx.beginPath();
      ctx.arc(lm.x * W, lm.y * H, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function getSkeletonAtTime(ms) {
  if (!poseFrames.length) return null;
  let closest = poseFrames[0];
  for (const f of poseFrames) {
    if (Math.abs(f.timestamp_ms - ms) < Math.abs(closest.timestamp_ms - ms)) closest = f;
  }
  return closest.landmarks;
}

// ─────────────────────────────────────────────────────────────────────────────
// API call + result render
// ─────────────────────────────────────────────────────────────────────────────
async function callAPI() {
  setApiStatus('calling');
  try {
    const res = await fetch(`${API}/api/v1/sequence/analyze`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name:           'Heavy Box Floor to Table',
        description:    'Worker picks up heavy box from floor, walks to table, places it down',
        allowances_pct: 15,
        motions: SEQ.map(s => ({ code: s.code, quantity: s.qty })),
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    setApiStatus('ok');
    renderCard(data);
  } catch (err) {
    setApiStatus('error');
    renderCard(fallbackResult(err));
  }
}

function fallbackResult(err) {
  const totalMods = SEQ.reduce((s, x) => s + x.mv * x.qty, 0);
  const base = +(totalMods * 0.129).toFixed(4);
  const std  = +(base * 1.15).toFixed(4);
  let raw = 0;
  const regionTotals = {};
  for (const s of SEQ) {
    const m = s.mv * s.qty;
    raw += m * (STRAIN[s.region] || 1.0);
    regionTotals[s.region] = (regionTotals[s.region] || 0) + m;
  }
  const rsi = +Math.min(10, (raw / RSI_MAX) * 10).toFixed(1);
  const cat = rsi >= 7.5 ? 'VERY HIGH' : rsi >= 5 ? 'HIGH' : rsi >= 2.5 ? 'MODERATE' : 'LOW';
  const breakdown = {};
  for (const [r, m] of Object.entries(regionTotals)) {
    breakdown[r] = { total_mods: m, pct_of_task: +(m / totalMods * 100).toFixed(1) };
  }
  return {
    total_mods: totalMods,
    base_time_seconds: base,
    standard_time_seconds: std,
    units_per_hour: Math.floor(3600 / std),
    breakdown_by_body_region: breakdown,
    ergonomic_risk: {
      repetitive_strain_index: rsi,
      risk_category: cat,
      recommendations: [{
        action:  'Replace floor-level bending with a powered lift table',
        detail:  'B17 contributes ~40% of the trunk load. A 600 mm lift table eliminates the bend cycle, removing the highest single-element WMSD risk.',
        expected_rsi_reduction: 3.2,
      }, {
        action:  'Reduce walking distance with adjacent staging',
        detail:  'Bring the box origin within 1 step of the placement table to drop W5×9 to W5×2.',
        expected_rsi_reduction: 1.1,
      }],
      _fallback: !!err,
      _error: err ? String(err.message) : null,
    },
  };
}

function setApiStatus(state) {
  const dot  = document.getElementById('api-dot');
  const text = document.getElementById('api-status');
  if (!dot || !text) return;
  const map = {
    calling: ['bg-amber-500 animate-pulse', 'Calling API…'],
    ok:      ['bg-emerald-500', 'Response received'],
    error:   ['bg-red-500',     'Using fallback'],
  };
  const [cls, label] = map[state] || ['bg-emerald-500', 'API ready'];
  dot.className    = `w-1.5 h-1.5 rounded-full ${cls}`;
  text.textContent = label;
}

function renderCard(d) {
  document.getElementById('card-loading').classList.add('hidden');
  const res = document.getElementById('card-results');
  res.classList.remove('hidden');

  document.getElementById('r-std').textContent  = d.standard_time_seconds.toFixed(2) + 's';
  document.getElementById('r-uph').textContent  = d.units_per_hour.toLocaleString();
  document.getElementById('r-mods').textContent = d.total_mods;

  const cat   = d.ergonomic_risk.risk_category;
  const rsi   = d.ergonomic_risk.repetitive_strain_index;
  const catEl = document.getElementById('r-cat');
  catEl.textContent = cat;
  catEl.className   = `text-[24px] font-bold leading-none ${
    cat === 'VERY HIGH' ? 'text-red-600'    :
    cat === 'HIGH'      ? 'text-accent'     :
    cat === 'MODERATE'  ? 'text-yellow-700' : 'text-emerald-600'
  }`;
  document.getElementById('r-rsi').textContent = `RSI ${rsi}/10`;

  // Region breakdown bars
  document.getElementById('r-regions').innerHTML =
    Object.entries(d.breakdown_by_body_region).map(([region, info]) => `
      <div>
        <div class="flex justify-between text-[12px] mb-1.5 font-mono">
          <span class="text-ink capitalize">${region.replace('_', ' ')}</span>
          <span class="text-faint">${info.total_mods} MODs · ${info.pct_of_task}%</span>
        </div>
        <div class="h-1.5 bg-paper border hairline rounded-full overflow-hidden">
          <div class="h-full bg-ink rounded-full transition-all duration-700"
               style="width:${info.pct_of_task}%"></div>
        </div>
      </div>`).join('');

  // Top recommendation
  const recs = d.ergonomic_risk.recommendations || [];
  const r1   = recs[0];
  document.getElementById('r-rec').innerHTML = r1 ? `
    <div class="flex gap-3">
      <span class="text-accent text-[16px] mt-0.5 flex-shrink-0">▲</span>
      <div>
        <p class="text-[14px] font-semibold text-ink leading-snug">${r1.action}</p>
        <p class="text-[12.5px] text-dim mt-2 leading-[1.6]">${r1.detail}</p>
        <p class="text-[11.5px] text-emerald-700 mt-2.5 font-mono">
          Expected RSI reduction: −${r1.expected_rsi_reduction}
        </p>
      </div>
    </div>` : '<p class="text-[13px] text-faint">No critical recommendations.</p>';

  // All recs
  document.getElementById('all-recs').innerHTML = recs.map((r, i) => `
    <div class="bg-paper border hairline rounded-md p-3">
      <div class="flex items-start gap-3">
        <span class="text-[11px] text-faint font-mono mt-0.5 tab-nums">${String(i + 1).padStart(2, '0')}</span>
        <div class="flex-1">
          <p class="text-[12.5px] font-semibold text-ink leading-snug">${r.action}</p>
          <p class="text-[12px] text-dim mt-1 leading-[1.55]">${r.detail}</p>
        </div>
        <span class="text-[11px] text-emerald-700 flex-shrink-0 font-mono">−${r.expected_rsi_reduction}</span>
      </div>
    </div>`).join('');

  // Raw JSON
  document.getElementById('raw-json').textContent = JSON.stringify(d, null, 2);
}

function toggleSection(id) {
  document.getElementById(id).classList.toggle('hidden');
}
window.toggleSection = toggleSection;

// ─────────────────────────────────────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────────────────────────────────────
function init() {
  buildCodesGrid();
  buildFeed();
  attachVideoHandlers();

  document.getElementById('sample-btn').addEventListener('click', startSample);

  fileInp().addEventListener('change', e => {
    if (e.target.files[0]) loadVideoFile(e.target.files[0]);
  });

  const dz = dropZone();
  ['dragover', 'dragenter'].forEach(ev =>
    dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('drag-over'); })
  );
  ['dragleave', 'dragend'].forEach(ev =>
    dz.addEventListener(ev, () => dz.classList.remove('drag-over'))
  );
  dz.addEventListener('drop', e => {
    e.preventDefault();
    dz.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('video/')) loadVideoFile(f);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
