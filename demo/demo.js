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
// Current MODAPTS sequence — populated by setAnnotations() or analyzeVideoWithMediaPipe()
// ─────────────────────────────────────────────────────────────────────────────
let SEQ        = [];
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
  const total = SEQ.reduce((s, seg) => s + seg.mv * seg.qty, 0);
  const el = document.getElementById('total-mods-label');
  if (el) el.textContent = total || '—';
  console.log('✅ Annotations loaded:', SEQ.length, 'segments,', poseFrames.length, 'pose frames');
};

// ─────────────────────────────────────────────────────────────────────────────
// Sequence feed
// ─────────────────────────────────────────────────────────────────────────────
let activeIdx = -1;

function buildFeed() {
  const feed = document.getElementById('seq-feed');
  if (!feed) return;

  if (!SEQ.length) {
    feed.innerHTML = '<p class="text-[12px] text-faint font-mono p-4 text-center">No sequence loaded</p>';
    return;
  }

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

  document.getElementById('chip-code').textContent  = s.code;
  document.getElementById('chip-label').textContent = s.label;
  document.getElementById('code-chip').classList.remove('hidden');

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
// Processing overlay — shown while MediaPipe runs in browser
// ─────────────────────────────────────────────────────────────────────────────
function showProcessingOverlay(msg, progress) {
  const overlay = document.getElementById('processing-overlay');
  const msgEl   = document.getElementById('processing-msg');
  const bar     = document.getElementById('processing-bar');
  if (!overlay) return;
  overlay.classList.remove('hidden');
  if (msgEl) msgEl.textContent = msg || 'Analyzing…';
  if (bar)   bar.style.width   = ((progress || 0) * 100) + '%';
}

function updateProcessingOverlay(msg, progress) {
  const msgEl = document.getElementById('processing-msg');
  const bar   = document.getElementById('processing-bar');
  if (msgEl) msgEl.textContent = msg;
  if (bar)   bar.style.width   = ((progress || 0) * 100) + '%';
}

function hideProcessingOverlay() {
  const overlay = document.getElementById('processing-overlay');
  if (overlay) overlay.classList.add('hidden');
}

// ─────────────────────────────────────────────────────────────────────────────
// Sample mode — plays the pre-analyzed delivery video
// ─────────────────────────────────────────────────────────────────────────────
function loadSample() {
  resetFeed();
  SEQ = [];
  poseFrames = [];

  document.getElementById('study-card').classList.add('hidden');
  document.getElementById('card-loading').classList.remove('hidden');
  document.getElementById('card-results').classList.add('hidden');
  document.getElementById('drop-zone').classList.add('hidden');
  vidWrap().classList.remove('hidden');

  const seqHeader = document.getElementById('seq-header-task');
  if (seqHeader) seqHeader.textContent = 'Delivery unload · van → ground';

  document.getElementById('sample-credit')?.classList.remove('hidden');

  const v = vid();
  v.src = './sample.mp4';

  // Load pre-computed sample annotations then play
  fetch('./sample_annotations.json')
    .then(r => r.ok ? r.json() : null)
    .then(j => {
      if (j) window.setAnnotations(j);
      v.currentTime = 0;
      v.play().catch(() => {});
    })
    .catch(() => {
      v.play().catch(() => {});
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// MediaPipe landmark names (same order as Python)
// ─────────────────────────────────────────────────────────────────────────────
const LM_NAMES = [
  'nose','left_eye_inner','left_eye','left_eye_outer',
  'right_eye_inner','right_eye','right_eye_outer',
  'left_ear','right_ear','mouth_left','mouth_right',
  'left_shoulder','right_shoulder','left_elbow','right_elbow',
  'left_wrist','right_wrist','left_pinky','right_pinky',
  'left_index','right_index','left_thumb','right_thumb',
  'left_hip','right_hip','left_knee','right_knee',
  'left_ankle','right_ankle','left_heel','right_heel',
  'left_foot_index','right_foot_index',
];

// ─────────────────────────────────────────────────────────────────────────────
// MODAPTS classifier (JS port of classifier.py)
// ─────────────────────────────────────────────────────────────────────────────
function avg(arr) {
  return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
}
function stdDev(arr) {
  if (arr.length < 2) return 0;
  const m = avg(arr);
  return Math.sqrt(arr.reduce((s, v) => s + (v - m) ** 2, 0) / arr.length);
}
function vecDist(a, b) {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}
function arrRange(arr) {
  return arr.length ? Math.max(...arr) - Math.min(...arr) : 0;
}

const RULES = {
  bend_shoulder_drop: 0.12,   // gap closes ≥12% from segment start
  bend_gap_range:     0.10,   // gap varies ≥10% anywhere in segment (catches mid-bend starts)
  sit_hip_drop:       0.15,
  walk_ankle_osc:     0.06,   // IQR threshold — synced with classifier.py
  wrist_M5: 0.22, wrist_M4: 0.14, wrist_M3: 0.08, wrist_M2: 0.04,
  wrist_G3: 0.02, wrist_G1: 0.005,
  wrist_y_range_M5: 0.20,
};

const MIN_VIS = 0.5;  // ignore landmarks with visibility below this — filters occlusion noise

function extractFeatures(frames) {
  if (frames.length < 2) return null;
  // Only include landmark values where MediaPipe reports sufficient visibility
  const col = (lm, axis) =>
    frames
      .filter(f => (f.landmarks[lm]?.visibility ?? 1.0) >= MIN_VIS)
      .map(f => f.landmarks[lm]?.[axis])
      .filter(v => v != null);

  const lsy = col('left_shoulder', 'y'),  rsy = col('right_shoulder', 'y');
  const lhy = col('left_hip', 'y'),       rhy = col('right_hip', 'y');
  const lay = col('left_ankle', 'y'),     ray = col('right_ankle', 'y');
  const lwx = col('left_wrist', 'x'),     lwy = col('left_wrist', 'y');
  const rwx = col('right_wrist', 'x'),    rwy = col('right_wrist', 'y');

  const tail4 = a => a.slice(-Math.min(4, a.length));
  const head4 = a => a.slice(0,  Math.min(4, a.length));

  // Per-frame mean shoulder Y and hip Y → gap array
  const n = Math.min(lsy.length, lhy.length);
  const gaps = [];
  for (let i = 0; i < n; i++) {
    const shoulderY = (lsy[i] != null && rsy[i] != null) ? (lsy[i] + rsy[i]) / 2
                    : (lsy[i] ?? rsy[i] ?? null);
    const hipY      = (lhy[i] != null && rhy[i] != null) ? (lhy[i] + rhy[i]) / 2
                    : (lhy[i] ?? rhy[i] ?? null);
    if (shoulderY != null && hipY != null) gaps.push(hipY - shoulderY);
  }

  let shoulderDrop = 0, gapRange = 0;
  if (gaps.length >= 2) {
    const startGap = gaps[0];
    const minGap   = Math.min(...gaps);
    const maxGap   = Math.max(...gaps);
    shoulderDrop   = Math.max(0, startGap - minGap);  // classic: gap closes from start
    gapRange       = maxGap - minGap;                  // full range regardless of start
  }

  const hipDisp = Math.abs(
    (avg(tail4(lhy)) + avg(tail4(rhy))) / 2 -
    (avg(head4(lhy)) + avg(head4(rhy))) / 2
  );

  // Use IQR (Q75−Q25) for ankle oscillation — resistant to single bad detections
  const allAnkleY = [...lay, ...ray].sort((a, b) => a - b);
  const ankleOscillation = allAnkleY.length > 4
    ? allAnkleY[Math.floor(allAnkleY.length * 0.75)] - allAnkleY[Math.floor(allAnkleY.length * 0.25)]
    : 0;

  const lStart = { x: avg(head4(lwx)), y: avg(head4(lwy)) };
  const lEnd   = { x: avg(tail4(lwx)), y: avg(tail4(lwy)) };
  const rStart = { x: avg(head4(rwx)), y: avg(head4(rwy)) };
  const rEnd   = { x: avg(tail4(rwx)), y: avg(tail4(rwy)) };

  const wristDisp      = Math.max(vecDist(lStart, lEnd), vecDist(rStart, rEnd));
  const wristYRange    = Math.max(arrRange(lwy), arrRange(rwy));
  const effectiveWrist = Math.max(wristDisp, wristYRange * 0.85);

  return { shoulderDrop, gapRange, hipDisp, ankleOscillation, wristDisp, wristYRange, effectiveWrist };
}

function classifySegment(frames) {
  const f = extractFeatures(frames);
  if (!f) return { code: 'G0', cat: 'get', region: 'fingers', mv: 0 };

  // B17: trunk flexion clearly present
  // b17_classic: gap closes from upright start AND hips stay put
  // b17_dominant: gap_range large AND trunk motion dominates hip motion (ratio > 1.3)
  //   — distinguishes B17 from S30 (S30 has low gap_range, whole body descends together)
  //   — no ankle guard needed: walking can't produce gap_range >= 10% with ratio > 1.3
  const gapRatio   = f.gapRange / Math.max(f.hipDisp, 0.01);
  const b17Classic  = f.shoulderDrop > RULES.bend_shoulder_drop && f.hipDisp < RULES.sit_hip_drop;
  const b17Dominant = f.gapRange > RULES.bend_gap_range && gapRatio >= 1.3;
  if (b17Classic || b17Dominant)
    return { code: 'B17', cat: 'bend', region: 'body', mv: 17 };

  if (f.hipDisp > RULES.sit_hip_drop && f.ankleOscillation < RULES.walk_ankle_osc)
    return f.shoulderDrop > 0
      ? { code: 'S30',  cat: 'sit',   region: 'body', mv: 30 }
      : { code: 'ST30', cat: 'stand', region: 'body', mv: 30 };
  if (f.ankleOscillation > RULES.walk_ankle_osc)
    return { code: 'W5', cat: 'walk', region: 'leg', mv: 5 };
  if (f.effectiveWrist >= RULES.wrist_M5 || f.wristYRange >= RULES.wrist_y_range_M5)
    return { code: 'M5', cat: 'move', region: 'full_arm', mv: 5 };
  if (f.effectiveWrist >= RULES.wrist_M4)
    return { code: 'M4', cat: 'move', region: 'arm', mv: 4 };
  if (f.effectiveWrist >= RULES.wrist_M3)
    return { code: 'M3', cat: 'move', region: 'arm', mv: 3 };
  if (f.effectiveWrist >= RULES.wrist_M2)
    return { code: 'M2', cat: 'move', region: 'hand', mv: 2 };
  if (f.effectiveWrist >= RULES.wrist_G3)
    return { code: 'G3', cat: 'get', region: 'hand', mv: 3 };
  if (f.effectiveWrist >= RULES.wrist_G1)
    return { code: 'G1', cat: 'get', region: 'fingers', mv: 1 };
  return { code: 'G0', cat: 'get', region: 'fingers', mv: 0 };
}

// Sliding-window mode segmentation + classification — works for any video.
// Labels each frame with a coarse mode (bend/walk/arm) using a local window,
// then groups consecutive same-mode frames so short walks are not swallowed
// by surrounding bend segments when the person never comes to a full stop.
function detectAndClassify(frames, durationMs) {
  if (frames.length < 3) return [];

  // Window = ~0.8 s centred on each frame
  const HALF = Math.max(3, Math.floor(frames.length * 0.04));

  // Per-frame coarse mode
  const modes = frames.map((_, i) => {
    const w = frames.slice(Math.max(0, i - HALF), i + HALF + 1);
    if (w.length < 2) return 'arm';
    const f = extractFeatures(w);
    if (!f) return 'arm';

    const gapRatio   = f.gapRange / Math.max(f.hipDisp, 0.01);
    const b17Classic = f.shoulderDrop > RULES.bend_shoulder_drop && f.hipDisp < RULES.sit_hip_drop;
    const b17Dominant= f.gapRange > RULES.bend_gap_range && gapRatio >= 1.3;

    if (b17Classic || b17Dominant)              return 'bend';
    if (f.ankleOscillation > RULES.walk_ankle_osc) return 'walk';
    return 'arm';
  });

  // 5-point majority-vote smooth — removes single-frame noise at transitions
  const smoothed = modes.map((_, i) => {
    const w = modes.slice(Math.max(0, i - 2), i + 3);
    const cnt = {};
    w.forEach(m => cnt[m] = (cnt[m] || 0) + 1);
    return Object.entries(cnt).sort((a, b) => b[1] - a[1])[0][0];
  });

  // Minimum segment length: ~4% of total frames (avoids 1-frame jitter)
  const MIN_FRAMES = Math.max(3, Math.floor(frames.length * 0.04));

  // Group consecutive same-mode frames
  const segments = [];
  let i = 0;
  while (i < frames.length) {
    const mode = smoothed[i];
    let j = i + 1;
    while (j < frames.length && smoothed[j] === mode) j++;

    const segFrames = frames.slice(i, j);
    if (segFrames.length >= MIN_FRAMES) {
      segments.push({ mode, frames: segFrames });
    } else if (segments.length > 0) {
      // Absorb tiny noise segment into the previous one
      segments[segments.length - 1].frames.push(...segFrames);
    }
    i = j;
  }

  // Classify each segment and build SEQ
  const seq = [];
  for (const { mode, frames: sf } of segments) {
    const startMs = sf[0].timestamp_ms;
    const endMs   = sf[sf.length - 1].timestamp_ms;

    // For bend/walk use the mode directly; for arm use the fine classifier
    let cls;
    if      (mode === 'bend') cls = { code: 'B17', cat: 'bend', region: 'body',    mv: 17 };
    else if (mode === 'walk') cls = { code: 'W5',  cat: 'walk', region: 'leg',     mv: 5  };
    else                      cls = classifySegment(sf);

    // Merge consecutive W5 steps into one element with qty > 1
    const last = seq[seq.length - 1];
    if (last && last.code === 'W5' && cls.code === 'W5') {
      last.qty++;
      last.end_pct = endMs / durationMs;
    } else {
      seq.push({
        code:      cls.code,
        qty:       1,
        label:     cls.code,
        cat:       cls.cat,
        region:    cls.region,
        mv:        cls.mv,
        start_pct: startMs / durationMs,
        end_pct:   endMs   / durationMs,
      });
    }
  }

  return seq.length ? seq : [{
    code: 'M3', qty: 1, label: 'M3', cat: 'move', region: 'arm', mv: 3,
    start_pct: 0, end_pct: 1,
  }];
}

// ─────────────────────────────────────────────────────────────────────────────
// Browser-side MediaPipe — lazy-loaded on first video upload
// ─────────────────────────────────────────────────────────────────────────────
let poseLandmarker  = null;
let mpLoading       = false;
let analysisRunning = false;

async function loadMediaPipe() {
  if (poseLandmarker) return poseLandmarker;
  if (mpLoading) return null;
  mpLoading = true;

  updateProcessingOverlay('Loading AI model (first time only)…', 0.05);

  try {
    const { PoseLandmarker, FilesetResolver } = await import(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs'
    );

    const vision = await FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
    );

    poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath:
          'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
        delegate: 'CPU',
      },
      runningMode: 'IMAGE',
      numPoses: 1,
      minPoseDetectionConfidence: 0.5,
      minPosePresenceConfidence:  0.5,
      minTrackingConfidence:      0.5,
    });

    mpLoading = false;
    return poseLandmarker;
  } catch (err) {
    mpLoading = false;
    console.error('MediaPipe load error:', err);
    return null;
  }
}

async function analyzeVideoWithMediaPipe(videoElement) {
  if (analysisRunning) return false;
  analysisRunning = true;

  showProcessingOverlay('Loading AI model…', 0.02);

  const lm = await loadMediaPipe();
  if (!lm) {
    updateProcessingOverlay('Could not load AI model — check your connection', 0);
    analysisRunning = false;
    return false;
  }

  const duration = videoElement.duration;
  if (!duration || duration < 0.5) {
    analysisRunning = false;
    return false;
  }

  const SAMPLE_FPS  = 10; // 10 fps — fast enough for gesture classification
  const totalSteps  = Math.ceil(duration * SAMPLE_FPS);

  // Offscreen canvas at 640×360 — enough for pose detection
  const canvas  = document.createElement('canvas');
  canvas.width  = 640;
  canvas.height = 360;
  const ctx     = canvas.getContext('2d');

  const keyframes = [];

  for (let i = 0; i <= totalSteps; i++) {
    const t = Math.min(i / SAMPLE_FPS, duration - 0.05);
    videoElement.currentTime = t;
    await new Promise(r => videoElement.addEventListener('seeked', r, { once: true }));

    ctx.drawImage(videoElement, 0, 0, 640, 360);
    const result = lm.detect(canvas);

    if (result.landmarks && result.landmarks.length > 0) {
      const landmarks = {};
      result.landmarks[0].forEach((pt, idx) => {
        if (idx < LM_NAMES.length) {
          landmarks[LM_NAMES[idx]] = {
            x: pt.x, y: pt.y, z: pt.z,
            visibility: pt.visibility ?? 1.0,
          };
        }
      });
      keyframes.push({
        frame_index:  i,
        timestamp_ms: Math.round(t * 1000),
        landmarks,
      });
    }

    updateProcessingOverlay(
      `Detecting pose… ${i + 1} / ${totalSteps} frames`,
      0.1 + 0.8 * (i / totalSteps)
    );
  }

  if (keyframes.length < 5) {
    updateProcessingOverlay('No pose detected — make sure a person is clearly visible', 0);
    analysisRunning = false;
    return false;
  }

  updateProcessingOverlay('Classifying motions…', 0.92);

  // Store pose frames for skeleton overlay
  poseFrames = keyframes;

  // Velocity-based segmentation + MODAPTS classification
  const detected = detectAndClassify(keyframes, duration * 1000);
  SEQ = detected;

  const total = SEQ.reduce((s, seg) => s + seg.mv * seg.qty, 0);
  const el = document.getElementById('total-mods-label');
  if (el) el.textContent = total || '—';

  buildFeed();
  hideProcessingOverlay();
  analysisRunning = false;
  return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Real video upload
// ─────────────────────────────────────────────────────────────────────────────
const vid      = () => document.getElementById('vid');
const dropZone = () => document.getElementById('drop-zone');
const vidWrap  = () => document.getElementById('video-wrap');
const canvas   = () => document.getElementById('skeleton-canvas');
const fileInp  = () => document.getElementById('file-input');

async function loadVideoFile(file) {
  if (analysisRunning) return;
  document.getElementById('sample-credit')?.classList.add('hidden');

  resetFeed();
  SEQ = [];
  poseFrames = [];
  buildFeed();

  document.getElementById('study-card').classList.add('hidden');
  document.getElementById('card-loading').classList.remove('hidden');
  document.getElementById('card-results').classList.add('hidden');

  const seqHeader = document.getElementById('seq-header-task');
  if (seqHeader) seqHeader.textContent = file.name;

  const totalEl = document.getElementById('total-mods-label');
  if (totalEl) totalEl.textContent = '—';

  const v = vid();
  v.src = URL.createObjectURL(file);
  dropZone().classList.add('hidden');
  vidWrap().classList.remove('hidden');

  // Wait for metadata before analysing
  await new Promise(r => v.addEventListener('loadedmetadata', r, { once: true }));

  showProcessingOverlay('Loading AI model…', 0.02);

  const ok = await analyzeVideoWithMediaPipe(v);

  if (ok) {
    v.currentTime = 0;
    v.play().catch(() => {});
  } else {
    hideProcessingOverlay();
    // Fallback: let the video play without annotations
    v.currentTime = 0;
    v.play().catch(() => {});
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Canvas sync — keeps buffer size = element size so 1 buffer px = 1 CSS px
// ─────────────────────────────────────────────────────────────────────────────
function syncCanvas() {
  const c = canvas();
  const v = vid();
  if (!c || !v) return;
  // Size the drawing buffer to the element's CSS display size.
  // Using getBoundingClientRect() is exact even with sub-pixel layouts.
  const rect = c.getBoundingClientRect();
  const w = Math.round(rect.width)  || v.offsetWidth  || 640;
  const h = Math.round(rect.height) || v.offsetHeight || 360;
  if (c.width !== w || c.height !== h) {
    c.width  = w;
    c.height = h;
  }
}

function attachVideoHandlers() {
  const v   = vid();
  const c   = canvas();
  const ctx = c.getContext('2d');

  // Sync canvas size whenever video metadata loads or window resizes
  v.addEventListener('loadedmetadata', syncCanvas);
  window.addEventListener('resize', syncCanvas);

  v.addEventListener('timeupdate', () => {
    if (!v.duration || !SEQ.length) return;
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
      syncCanvas();
      const lm = getSkeletonAtTime(v.currentTime * 1000);
      drawSkeleton(ctx, v, lm);
    }
  });

  v.addEventListener('ended', async () => {
    SEQ.forEach((_, i) => completeSeg(i));
    activateSeg(-1);
    document.getElementById('code-chip').classList.add('hidden');
    if (SEQ.length) {
      updateStats(SEQ.reduce((s, seg) => s + seg.mv * seg.qty, 0));
    }
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

// Compute the actual video content rectangle within the element.
// With object-contain, the video is letterboxed/pillarboxed when aspect ratios differ.
// Landmarks must be mapped to this content rect, not the full element.
function videoContentRect(videoEl) {
  const W  = videoEl.offsetWidth;
  const H  = videoEl.offsetHeight;
  const vw = videoEl.videoWidth;
  const vh = videoEl.videoHeight;

  if (!vw || !vh || !W || !H) return { x: 0, y: 0, w: W, h: H };

  const videoAspect = vw / vh;
  const elemAspect  = W  / H;

  if (Math.abs(videoAspect - elemAspect) < 0.01) {
    // Perfect match — no bars
    return { x: 0, y: 0, w: W, h: H };
  } else if (videoAspect > elemAspect) {
    // Video wider than container → letterbox top/bottom
    const h = W / videoAspect;
    return { x: 0, y: (H - h) / 2, w: W, h };
  } else {
    // Video taller than container → pillarbox left/right
    const w = H * videoAspect;
    return { x: (W - w) / 2, y: 0, w, h: H };
  }
}

function drawSkeleton(ctx, videoEl, landmarks) {
  const cw = ctx.canvas.width;
  const ch = ctx.canvas.height;
  ctx.clearRect(0, 0, cw, ch);
  if (!landmarks) return;

  // Map the video content rect from element pixels → canvas buffer pixels.
  // (Canvas buffer is synced to element CSS px via syncCanvas, so scale = 1:1.)
  const r = videoContentRect(videoEl);

  // Convert normalised landmark [0,1] to canvas pixels
  const px = x => r.x + x * r.w;
  const py = y => r.y + y * r.h;

  ctx.strokeStyle = 'rgba(194,65,12,0.9)';
  ctx.lineWidth   = Math.max(1.5, r.w / 320);   // scale with content width
  for (const [a, b] of CONNECTIONS) {
    const pa = landmarks[a], pb = landmarks[b];
    if (pa && pb && pa.visibility > 0.4 && pb.visibility > 0.4) {
      ctx.beginPath();
      ctx.moveTo(px(pa.x), py(pa.y));
      ctx.lineTo(px(pb.x), py(pb.y));
      ctx.stroke();
    }
  }
  ctx.fillStyle = 'rgba(24,24,27,0.95)';
  for (const lm of Object.values(landmarks)) {
    if (lm.visibility > 0.4) {
      ctx.beginPath();
      ctx.arc(px(lm.x), py(lm.y), Math.max(2, r.w / 213), 0, Math.PI * 2);
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
  if (!SEQ.length) return;
  setApiStatus('calling');
  try {
    const res = await fetch(`${API}/api/v1/sequence/analyze`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name:           'Analyzed task',
        description:    'OpenPTS browser analysis',
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
  // Generate a generic recommendation based on the highest-strain segment
  const highestStrain = SEQ.reduce((best, s) => {
    const load = s.mv * s.qty * (STRAIN[s.region] || 1.0);
    return load > best.load ? { s, load } : best;
  }, { s: null, load: -1 });

  const recs = highestStrain.s ? [{
    action:  `Reduce ${highestStrain.s.code} element load`,
    detail:  `The ${highestStrain.s.code} (${highestStrain.s.label || highestStrain.s.code}) element contributes the highest strain load in this sequence. Consider workstation redesign to reduce this motion's frequency or reach distance.`,
    expected_rsi_reduction: +(rsi * 0.3).toFixed(1),
  }] : [];

  return {
    total_mods: totalMods,
    base_time_seconds: base,
    standard_time_seconds: std,
    units_per_hour: std > 0 ? Math.floor(3600 / std) : 0,
    breakdown_by_body_region: breakdown,
    ergonomic_risk: {
      repetitive_strain_index: rsi,
      risk_category: cat,
      recommendations: recs,
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

  document.getElementById('sample-btn').addEventListener('click', loadSample);

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
