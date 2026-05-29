#!/usr/bin/env python3
"""
mediapipe_extract.py — Generate demo/annotations.json from a video file.

Usage:
    python mediapipe_extract.py <video_file>
    python mediapipe_extract.py <video_file> --output demo/annotations.json
    python mediapipe_extract.py <video_file> --skip 2      # process every 2nd frame (faster)
    python mediapipe_extract.py <video_file> --no-skeleton # skip pose keyframes (smaller file)
    python mediapipe_extract.py <video_file> --auto        # velocity-based auto-segmentation (any video)
    python mediapipe_extract.py <video_file> --task task.json  # custom task definition from JSON

What it does:
    1. Runs MediaPipe Pose on every frame to extract 33 body landmarks
    2a. [default] Segments using proportional timing from the built-in box task definition
    2b. [--auto]  Segments using velocity-based onset detection — works for any video
    2c. [--task]  Segments using proportional timing from a custom task JSON file
    3. Runs the OpenPTS rule-based classifier on each detected segment
    4. Writes annotations.json — consumed by demo/index.html

Requirements:
    pip install mediapipe opencv-python
"""

import sys
import json
import argparse
from pathlib import Path

# ── Check dependencies ─────────────────────────────────────────────────────────
try:
    import cv2
except ImportError:
    sys.exit("❌  opencv-python not installed.\n    Run: pip install opencv-python")

try:
    import mediapipe as mp
    from mediapipe.tasks import python  as _mpt
    from mediapipe.tasks.python import vision as _mpv
except ImportError:
    sys.exit("❌  mediapipe not installed.\n    Run: pip install mediapipe")

try:
    from classifier import classify_pose_sequence
    CLASSIFIER_AVAILABLE = True
except ImportError:
    CLASSIFIER_AVAILABLE = False
    print("⚠️  classifier.py not found — predicted codes will use expected values")


# ── MODAPTS code info lookup ───────────────────────────────────────────────────
CODE_INFO = {
    'W5':  dict(cat='walk',  region='leg',      mv=5,  label='Walk (1 pace)'),
    'B17': dict(cat='bend',  region='body',     mv=17, label='Bend and arise'),
    'G3':  dict(cat='get',   region='hand',     mv=3,  label='Complex grasp'),
    'G1':  dict(cat='get',   region='fingers',  mv=1,  label='Simple grasp'),
    'G0':  dict(cat='get',   region='fingers',  mv=0,  label='Contact grasp'),
    'M5':  dict(cat='move',  region='full_arm', mv=5,  label='Move — full arm'),
    'M4':  dict(cat='move',  region='arm',      mv=4,  label='Move — upper arm'),
    'M3':  dict(cat='move',  region='arm',      mv=3,  label='Move — forearm'),
    'M2':  dict(cat='move',  region='hand',     mv=2,  label='Move — hand'),
    'M1':  dict(cat='move',  region='fingers',  mv=1,  label='Move — finger'),
    'P2':  dict(cat='put',   region='hand',     mv=2,  label='Place — approx.'),
    'P0':  dict(cat='put',   region='fingers',  mv=0,  label='Place — loose'),
    'S30': dict(cat='sit',   region='body',     mv=30, label='Sit down'),
    'ST30':dict(cat='stand', region='body',     mv=30, label='Stand up'),
    'E2':  dict(cat='eye_action', region='eyes', mv=2, label='Eye focus'),
}

# ── Task definition ────────────────────────────────────────────────────────────
# Heavy box: floor → chest height → table
# Total: 72 MODs = 9.288 s base time
TASK = [
    dict(code='W5',  qty=4, label='Walk to box',    cat='walk', region='leg',      mv=5,  mods=20,
         start_pct=0.000, end_pct=0.278),
    dict(code='B17', qty=1, label='Bend to floor',  cat='bend', region='body',     mv=17, mods=17,
         start_pct=0.278, end_pct=0.514),
    dict(code='G3',  qty=1, label='Complex grasp',  cat='get',  region='hand',     mv=3,  mods=3,
         start_pct=0.514, end_pct=0.556),
    dict(code='M5',  qty=1, label='Lift to chest',  cat='move', region='full_arm', mv=5,  mods=5,
         start_pct=0.556, end_pct=0.625),
    dict(code='W5',  qty=5, label='Walk to table',  cat='walk', region='leg',      mv=5,  mods=25,
         start_pct=0.625, end_pct=0.972),
    dict(code='P2',  qty=1, label='Place on table', cat='put',  region='hand',     mv=2,  mods=2,
         start_pct=0.972, end_pct=1.000),
]

# MediaPipe landmark index → name
LM_NAMES = [
    'nose','left_eye_inner','left_eye','left_eye_outer',
    'right_eye_inner','right_eye','right_eye_outer',
    'left_ear','right_ear','mouth_left','mouth_right',
    'left_shoulder','right_shoulder','left_elbow','right_elbow',
    'left_wrist','right_wrist','left_pinky','right_pinky',
    'left_index','right_index','left_thumb','right_thumb',
    'left_hip','right_hip','left_knee','right_knee',
    'left_ankle','right_ankle','left_heel','right_heel',
    'left_foot_index','right_foot_index',
]

# Landmarks to keep in the skeleton output (smaller JSON, faster demo load)
SKELETON_LM = {
    'left_shoulder','right_shoulder','left_elbow','right_elbow',
    'left_wrist','right_wrist','left_hip','right_hip',
    'left_knee','right_knee','left_ankle','right_ankle',
}


# ── Model download ─────────────────────────────────────────────────────────────
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task"
)
MODEL_PATH = Path(__file__).parent / "pose_landmarker_full.task"

def ensure_model():
    if MODEL_PATH.exists():
        return
    import urllib.request
    print(f"⬇️   Downloading MediaPipe pose model (~30 MB, one-time)…")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print(f"    Saved → {MODEL_PATH.name}")


# ── Extraction ─────────────────────────────────────────────────────────────────
def extract(video_path: str, skip: int = 1) -> tuple:
    ensure_model()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        sys.exit(f"❌  Cannot open: {video_path}")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_ms  = int(total_frames / fps * 1000)

    print(f"\n📹  {Path(video_path).name}")
    print(f"    {total_frames} frames · {fps:.1f} fps · {duration_ms/1000:.1f}s")

    # MediaPipe 0.10+ Tasks API
    options = _mpv.PoseLandmarkerOptions(
        base_options=_mpt.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=_mpv.RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    frames, idx = [], 0
    with _mpv.PoseLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            if idx % max(1, skip) == 0:
                rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result   = landmarker.detect(mp_image)

                if result.pose_landmarks:
                    lms = {}
                    for i, lm in enumerate(result.pose_landmarks[0]):
                        if i < len(LM_NAMES):
                            lms[LM_NAMES[i]] = dict(
                                x=round(lm.x, 4),
                                y=round(lm.y, 4),
                                z=round(lm.z, 4),
                                visibility=round(getattr(lm, 'visibility', 1.0) or 1.0, 3),
                            )
                    frames.append(dict(
                        frame_index=idx,
                        timestamp_ms=int(idx / fps * 1000),
                        landmarks=lms,
                    ))
            idx += 1
            if idx % 30 == 0:
                print(f"\r    Extracting: {idx/total_frames*100:.0f}%", end='', flush=True)

    cap.release()
    print(f"\r    Extracting: 100% — {len(frames)} frames detected")
    return frames, dict(fps=fps, total_frames=total_frames, duration_ms=duration_ms)


# ── Segmentation ───────────────────────────────────────────────────────────────
def segment(frames: list, duration_ms: int, task_override: list = None) -> list:
    """Split frames into segments using proportional MODAPTS timing."""
    task_def = task_override if task_override is not None else TASK

    def nearest(target_ms):
        return min(frames, key=lambda f: abs(f['timestamp_ms'] - target_ms))

    segs = []
    for s in task_def:
        s0 = nearest(int(s['start_pct'] * duration_ms))
        s1 = nearest(int(s['end_pct']   * duration_ms))
        seg_frames = [f for f in frames
                      if s0['timestamp_ms'] <= f['timestamp_ms'] <= s1['timestamp_ms']]
        segs.append(dict(task=s, frames=seg_frames,
                         start_ms=s0['timestamp_ms'], end_ms=s1['timestamp_ms'],
                         start_frame=s0['frame_index'], end_frame=s1['frame_index']))
    return segs


# ── Auto-segmentation (velocity-based onset detection) ─────────────────────────
def auto_segment(frames: list, fps: float, min_seg_sec: float = 0.7) -> list:
    """
    Detect motion boundaries from wrist/ankle velocity valleys.
    Returns a list of frame-lists, one per detected segment.
    Works for any video without knowing the task sequence in advance.
    """
    if len(frames) < 10:
        return [frames]

    tracking_lms = ['left_wrist', 'right_wrist', 'left_ankle', 'right_ankle']

    # Compute per-frame max velocity across tracked landmarks
    vels = [0.0]
    for i in range(1, len(frames)):
        a, b = frames[i - 1]['landmarks'], frames[i]['landmarks']
        v = 0.0
        for lm in tracking_lms:
            if lm in a and lm in b:
                dx = b[lm]['x'] - a[lm]['x']
                dy = b[lm]['y'] - a[lm]['y']
                v = max(v, (dx * dx + dy * dy) ** 0.5)
        vels.append(v)

    # 5-point median smooth
    def smooth(arr, w=5):
        out = []
        for i in range(len(arr)):
            chunk = sorted(arr[max(0, i - w // 2): i + w // 2 + 1])
            out.append(chunk[len(chunk) // 2])
        return out

    s = smooth(vels)
    mean_v = sum(s) / len(s) if s else 0
    threshold = mean_v * 0.35
    min_gap   = max(6, int(fps * min_seg_sec))

    # Valley = local minimum below threshold
    cuts = [0]
    for i in range(2, len(s) - 2):
        if (s[i] < threshold and
                s[i] <= s[i - 1] and s[i] <= s[i + 1] and
                i - cuts[-1] >= min_gap):
            cuts.append(i)
    cuts.append(len(frames) - 1)

    segs = []
    for i in range(len(cuts) - 1):
        sf = frames[cuts[i]: cuts[i + 1] + 1]
        if len(sf) >= 4:
            segs.append(sf)

    return segs if segs else [frames]


def classify_auto(seg_frame_lists: list, duration_ms: int) -> list:
    """Classify auto-detected segments."""
    print("\n🤖  Auto-classifying detected segments:")
    results = []
    for seg_frames in seg_frame_lists:
        if CLASSIFIER_AVAILABLE and len(seg_frames) >= 2:
            r    = classify_pose_sequence(seg_frames)
            code = r.get('predicted_code', 'M3')
            conf = r.get('confidence', 0.0)
        else:
            code, conf = 'M3', 0.5

        start_ms = seg_frames[0]['timestamp_ms']
        end_ms   = seg_frames[-1]['timestamp_ms']
        info     = CODE_INFO.get(code, dict(cat='move', region='arm', mv=3, label=code))

        print(f"    {start_ms/1000:.1f}s–{end_ms/1000:.1f}s  →  {code}  (conf={conf:.2f})")

        results.append(dict(
            code=code, quantity=1, label=info.get('label', code),
            category=info['cat'], body_region=info['region'],
            mod_value=info['mv'], subtotal_mods=info['mv'],
            start_ms=start_ms, end_ms=end_ms,
            start_pct=round(start_ms / duration_ms, 4) if duration_ms else 0,
            end_pct  =round(end_ms   / duration_ms, 4) if duration_ms else 1,
            confidence=round(conf, 2),
        ))

    # Merge consecutive W5 walk segments into one element with qty > 1
    merged = []
    for seg in results:
        if merged and merged[-1]['code'] == 'W5' and seg['code'] == 'W5':
            merged[-1]['quantity'] += 1
            merged[-1]['end_ms']   = seg['end_ms']
            merged[-1]['end_pct']  = seg['end_pct']
            merged[-1]['subtotal_mods'] += seg['subtotal_mods']
        else:
            merged.append(seg)
    return merged


# ── Task-file based segmentation ───────────────────────────────────────────────
def load_task_file(path: str) -> list:
    """
    Load a task definition from a JSON file and compute proportional start/end.
    JSON format: [{"code":"B17","qty":1,"label":"...","cat":"bend","region":"body","mv":17,"mods":17}, ...]
    """
    import json as _json
    with open(path) as f:
        raw = _json.load(f)
    total_mods = sum(t['mods'] for t in raw)
    if total_mods == 0:
        raise ValueError("Task file has zero total MODs")
    cumulative = 0
    task = []
    for t in raw:
        start = cumulative / total_mods
        end   = (cumulative + t['mods']) / total_mods
        task.append(dict(
            code=t['code'], qty=t.get('qty', 1), label=t.get('label', t['code']),
            cat=t['cat'], region=t['region'], mv=t['mv'], mods=t['mods'],
            start_pct=round(start, 4), end_pct=round(end, 4),
        ))
        cumulative += t['mods']
    return task


# ── Classification ─────────────────────────────────────────────────────────────
def classify(segs: list, duration_ms: int) -> list:
    print("\n🤖  Classifying segments:")
    results = []
    for seg in segs:
        t = seg['task']
        expected = t['code']

        if CLASSIFIER_AVAILABLE and len(seg['frames']) >= 2:
            r    = classify_pose_sequence(seg['frames'])
            code = r.get('predicted_code', expected)
            conf = r.get('confidence', 0.0)
        else:
            code, conf = expected, 1.0

        match = '✓' if code == expected else f'→ expected {expected}'
        print(f"    {t['label']:20s}  predicted={code:<4}  conf={conf:.2f}  {match}")

        start_pct = seg['start_ms'] / duration_ms if duration_ms else t['start_pct']
        end_pct   = seg['end_ms']   / duration_ms if duration_ms else t['end_pct']

        results.append(dict(
            code=code, quantity=t['qty'], label=t['label'],
            category=t['cat'], body_region=t['region'],
            mod_value=t['mv'], subtotal_mods=t['mods'],
            start_frame=seg['start_frame'], end_frame=seg['end_frame'],
            start_ms=seg['start_ms'],       end_ms=seg['end_ms'],
            start_pct=round(start_pct, 4),  end_pct=round(end_pct, 4),
            confidence=round(conf, 2),
        ))
    return results


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='Generate OpenPTS demo annotations from video')
    ap.add_argument('video',             help='Path to your recorded video file')
    ap.add_argument('--output',          default='demo/annotations.json',
                    help='Output path (default: demo/annotations.json)')
    ap.add_argument('--skip',            type=int, default=1,
                    help='Process 1 in every N frames — use 2 or 3 to speed things up')
    ap.add_argument('--no-skeleton',     action='store_true',
                    help='Omit pose keyframes from output (smaller file, no skeleton overlay)')
    ap.add_argument('--auto',            action='store_true',
                    help='Use velocity-based auto-segmentation instead of the built-in box task. '
                         'Works for any video; accuracy depends on the clarity of motion transitions.')
    ap.add_argument('--task',            metavar='TASK_JSON',
                    help='Path to a custom task definition JSON file. '
                         'Overrides the built-in box task for proportional segmentation.')
    args = ap.parse_args()

    print("\n🎬  OpenPTS MediaPipe Extractor")
    print("    github.com/siddhit/openpts-api\n")

    # 1. Extract landmarks
    frames, info = extract(args.video, skip=args.skip)
    if not frames:
        sys.exit("❌  No pose landmarks detected — check lighting and camera angle.")

    # 2 & 3. Segment + Classify
    if args.auto:
        print("🔍  Auto-segmentation mode (velocity-based onset detection)")
        seg_lists = auto_segment(frames, info['fps'])
        print(f"    Found {len(seg_lists)} candidate segments")
        motion_segments = classify_auto(seg_lists, info['duration_ms'])
    elif args.task:
        print(f"📋  Custom task mode: {args.task}")
        task_override = load_task_file(args.task)
        segs = segment(frames, info['duration_ms'], task_override=task_override)
        motion_segments = classify(segs, info['duration_ms'])
    else:
        segs = segment(frames, info['duration_ms'])
        motion_segments = classify(segs, info['duration_ms'])

    # 4. Build output
    out = dict(
        video=Path(args.video).name,
        fps=info['fps'],
        total_frames=info['total_frames'],
        duration_ms=info['duration_ms'],
        motion_segments=motion_segments,
    )

    if not args.no_skeleton:
        out['pose_keyframes'] = [
            dict(
                frame_index=f['frame_index'],
                timestamp_ms=f['timestamp_ms'],
                landmarks={k: v for k, v in f['landmarks'].items() if k in SKELETON_LM},
            )
            for f in frames
        ]
        print(f"\n🦴  Skeleton: {len(out['pose_keyframes'])} keyframes included")

    # 5. Write
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(out, f, indent=2)

    total_mods = sum(s['subtotal_mods'] for s in motion_segments)
    std_time   = round(total_mods * 0.129 * 1.15, 2)
    print(f"\n✅  Done!")
    print(f"    {len(motion_segments)} segments · {total_mods} MODs · {std_time}s standard time")
    print(f"    Saved → {args.output}")
    print(f"\n    Next: open demo/index.html in your browser")


if __name__ == '__main__':
    main()
