#!/usr/bin/env python3
"""
mediapipe_extract.py — Generate demo/annotations.json from a video file.

Usage:
    python mediapipe_extract.py <video_file>
    python mediapipe_extract.py <video_file> --output demo/annotations.json
    python mediapipe_extract.py <video_file> --skip 2   # process every 2nd frame (faster)
    python mediapipe_extract.py <video_file> --no-skeleton  # skip pose keyframes (smaller file)

What it does:
    1. Runs MediaPipe Pose on every frame to extract 33 body landmarks
    2. Segments the video into 6 MODAPTS elements using proportional timing
       based on standard MODAPTS durations (refined when you call --manual)
    3. Runs the OpenPTS rule-based classifier on each segment
    4. Writes annotations.json — consumed by demo/index.html

The proportional timing means segments are split by the % of total video
duration that each MODAPTS element should take (based on 72 total MODs).
This works well when you record ONLY the task with no dead time at start/end.

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
except ImportError:
    sys.exit("❌  mediapipe not installed.\n    Run: pip install mediapipe")

try:
    from classifier import classify_pose_sequence
    CLASSIFIER_AVAILABLE = True
except ImportError:
    CLASSIFIER_AVAILABLE = False
    print("⚠️  classifier.py not found — predicted codes will use expected values")


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


# ── Extraction ─────────────────────────────────────────────────────────────────
def extract(video_path: str, skip: int = 1) -> tuple:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        sys.exit(f"❌  Cannot open: {video_path}")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_ms  = int(total_frames / fps * 1000)

    print(f"\n📹  {Path(video_path).name}")
    print(f"    {total_frames} frames · {fps:.1f} fps · {duration_ms/1000:.1f}s")

    pose_cfg = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    frames, idx = [], 0
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        if idx % max(1, skip) == 0:
            rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose_cfg.process(rgb)
            if results.pose_landmarks:
                lms = {}
                for i, lm in enumerate(results.pose_landmarks.landmark):
                    if i < len(LM_NAMES):
                        lms[LM_NAMES[i]] = dict(
                            x=round(lm.x, 4), y=round(lm.y, 4),
                            z=round(lm.z, 4), visibility=round(lm.visibility, 3),
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
    pose_cfg.close()
    print(f"\r    Extracting: 100% — {len(frames)} frames detected")
    return frames, dict(fps=fps, total_frames=total_frames, duration_ms=duration_ms)


# ── Segmentation ───────────────────────────────────────────────────────────────
def segment(frames: list, duration_ms: int) -> list:
    """Split frames into segments using proportional MODAPTS timing."""
    def nearest(target_ms):
        return min(frames, key=lambda f: abs(f['timestamp_ms'] - target_ms))

    segs = []
    for s in TASK:
        s0 = nearest(int(s['start_pct'] * duration_ms))
        s1 = nearest(int(s['end_pct']   * duration_ms))
        seg_frames = [f for f in frames
                      if s0['timestamp_ms'] <= f['timestamp_ms'] <= s1['timestamp_ms']]
        segs.append(dict(task=s, frames=seg_frames,
                         start_ms=s0['timestamp_ms'], end_ms=s1['timestamp_ms'],
                         start_frame=s0['frame_index'], end_frame=s1['frame_index']))
    return segs


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
    ap.add_argument('video',           help='Path to your recorded video file')
    ap.add_argument('--output',        default='demo/annotations.json',
                    help='Output path (default: demo/annotations.json)')
    ap.add_argument('--skip',          type=int, default=1,
                    help='Process 1 in every N frames — use 2 or 3 to speed things up')
    ap.add_argument('--no-skeleton',   action='store_true',
                    help='Omit pose keyframes from output (smaller file, no skeleton overlay)')
    args = ap.parse_args()

    print("\n🎬  OpenPTS MediaPipe Extractor")
    print("    github.com/siddhit/openpts-api\n")

    # 1. Extract landmarks
    frames, info = extract(args.video, skip=args.skip)
    if not frames:
        sys.exit("❌  No pose landmarks detected — check lighting and camera angle.")

    # 2. Segment
    segs = segment(frames, info['duration_ms'])

    # 3. Classify
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
