# OpenPTS: An Open API for MODAPTS-Grounded Motion Labeling in Manufacturing Robot Learning

**Siddhit Sanghavi**  
Independent Researcher  
siddhits@gmail.com · https://siddh.it

---

## Abstract

We present OpenPTS, an open-source REST API that exposes MODAPTS (Modular Arrangement of Predetermined Time Standards) motion primitives as a programmatic interface for industrial time study and ergonomic risk assessment. MODAPTS is a practitioner-validated system for decomposing manual assembly tasks into body-region-aware motion elements, each assigned a time value in units of MODs (1 MOD = 0.129 s). Despite five decades of industrial use, MODAPTS has remained locked in proprietary desktop software and manual spreadsheet workflows. OpenPTS formalizes the MODAPTS motion library, time-study calculations, and ergonomic risk scoring as a typed REST API, and adds a geometric rule-based classifier that maps MediaPipe pose-keypoint sequences to MODAPTS codes. We demonstrate the pipeline on a recorded box-handling task (walk → bend → grasp → lift → walk → place) and propose MODAPTS as a structured semantic layer for imitation-learning pipelines: where prior work labels robot demonstrations with low-level trajectories or task-specific annotations, MODAPTS codes provide standardized, body-grounded, temporally bounded motion primitives that transfer across tasks and workers. OpenPTS is released under the MIT License at https://github.com/siddhit/openpts-api.

---

## 1. Introduction

Robot learning from human demonstration (LfD) has advanced substantially in the past decade, yet a persistent challenge is *how to annotate and segment* the demonstration data [1]. Most approaches either operate at the trajectory level (joint angles, end-effector poses) or use task-specific, hand-coded labels that do not generalize across settings [2,3]. What is lacking is a standardized vocabulary of human motion primitives that is (a) validated against real industrial practice, (b) body-region-aware rather than object-centric, (c) carries inherent time information, and (d) is portable across tasks, workers, and environments.

Industrial engineering has had such a vocabulary for fifty years: Predetermined Time Standards (PTS) systems, of which MODAPTS is among the most widely adopted in manufacturing [4]. In MODAPTS, every manual task is decomposed into atomic motion elements — *Walk* (W5, per pace), *Bend and Arise* (B17), *Complex Grasp* (G3), *Move to full-arm extension* (M5), *Approximate Placement* (P2) — each assigned a time value in MODs (1 MOD = 0.129 s). The subscript encodes body region and distance class simultaneously, making MODAPTS codes semantically richer than either a trajectory label or a freeform text annotation.

Yet MODAPTS has never been accessible as a machine-readable API. Practitioners use proprietary tools (Siemens Tecnomatix, Delmia) or paper forms; there is no open endpoint that accepts a motion sequence and returns standard time, ergonomic risk, and a per-element breakdown. This paper makes three contributions:

1. **OpenPTS API** (§3): a typed REST API that exposes the full MODAPTS motion library, time-study calculations with configurable allowances, and an ergonomic risk scoring module.

2. **Video-to-MODAPTS pipeline** (§4): a local extractor that runs MediaPipe Pose [5] on recorded video and applies a geometric rule-based classifier to segment and label each motion element.

3. **A proposal for MODAPTS as a semantic LfD annotation layer** (§5): we argue that MODAPTS codes satisfy the properties required of a universal motion primitive vocabulary for imitation learning in structured manipulation environments, and we sketch how the OpenPTS API can be integrated into existing robot learning pipelines.

---

## 2. Background and Related Work

### 2.1 Predetermined Time Standards

Predetermined Time Standards (PTS) systems assign standard times to basic human motions derived from large observational datasets. Major systems include MTM (Methods-Time Measurement, 1948), MOST (Maynard Operation Sequence Technique, 1980), and MODAPTS (G.C. Heyde, 1966) [4,6]. MODAPTS is distinguished by its body-centric design: the numeric subscript of each code equals its time value in MODs *and* indicates which body segment performs the motion. M1 (finger-length move) through M5 (full-arm extension), for example, form a natural hierarchy of reach distance indexed by body segment. This makes MODAPTS codes self-documenting with respect to the body region engaged, a property not shared by MTM or MOST.

Despite extensive industrial deployment — MODAPTS is used in automotive assembly, electronics manufacturing, and healthcare logistics — no open-source library or API existed prior to this work.

### 2.2 Learning from Demonstration

Robot LfD has been approached through behavioral cloning [7], inverse reinforcement learning [8], and more recently through large-scale imitation learning from video [9,10]. Annotation pipelines vary: MIME [11] and RoboTurk [12] rely on teleoperation; Something-Something [13] uses freeform action labels; recent foundation model work (RT-2 [14], OpenVLA [15]) uses natural-language task descriptions. None of these systems provides a structured, time-calibrated motion primitive vocabulary grounded in industrial human factors.

The closest related concept is *motion primitive* or *option* decomposition in hierarchical reinforcement learning [16], but these are typically task-specific and must be re-learned per environment. MODAPTS codes, by contrast, are defined body-kinematically and apply identically whether a human or robot performs the motion.

### 2.3 Pose-Based Action Recognition in Manufacturing

MediaPipe Pose [5] and related 2D/3D pose estimators have been applied to ergonomic assessment (RULA, REBA scoring) [17,18] and action recognition in industrial settings [19]. Existing ergonomic pipelines typically produce a continuous risk score without motion-element segmentation. OpenPTS is the first system, to our knowledge, to connect pose estimation output to MODAPTS motion codes and standard-time calculation.

---

## 3. The OpenPTS API

OpenPTS is implemented in Python 3.11 using FastAPI, SQLAlchemy, and a PostgreSQL backend (Neon, serverless), deployed on Vercel. The API is publicly accessible at `https://openpts-api.vercel.app` with full OpenAPI 3.0 documentation at `/docs`.

### 3.1 Motion Library

The motion library seeds 17 MODAPTS codes across 7 families (Table 1). Each code record stores: `code` (e.g. `B17`), `category` (`bend`), `body_region` (`body`), `mod_value` (17), and `time_seconds` (2.193). The endpoint `GET /api/v1/motions` returns the full library, filterable by `body_region` and `category`.

**Table 1.** MODAPTS motion codes implemented in OpenPTS v0.2.0.

| Family | Codes | Body region | MODs |
|--------|-------|-------------|------|
| Move | M1, M2, M3, M4, M5 | fingers → full arm | 1–5 |
| Get | G0, G1, G3, R2 | fingers, hand | 0–3 |
| Put | P0, P2, P5, A4 | fingers, hand | 0–5 |
| Walk | W5, F3 | leg | 3, 5 |
| Bend | B17 | body (trunk) | 17 |
| Sit/Stand | S30, ST30 | body | 30 |
| Eye | E2 | eyes | 2 |

### 3.2 Sequence Analysis

The primary endpoint `POST /api/v1/sequence/analyze` accepts an ordered list of motion codes with quantities, an optional task name and description, and an allowances percentage (default 15%, per automotive industry standard). It returns:

- **Base time**: sum of (mod_value × quantity × 0.129 s) across all elements
- **Standard time**: base_time × (1 + allowances_pct / 100)
- **Units per hour**: ⌊3600 / standard_time⌋
- **Per-element breakdown**: subtotal MODs, seconds, category, body region
- **Aggregate breakdowns**: by body region and by category
- **Ergonomic risk profile** (§3.3)

### 3.3 Ergonomic Risk Scoring

We introduce a Repetitive Strain Index (RSI) that quantifies the cumulative musculoskeletal load of a motion sequence on a 0–10 scale. For each element *i* with MOD value *m_i*, quantity *q_i*, and body-region strain weight *w_i*:

```
RSI_raw = Σ_i (m_i × q_i × w_i)
RSI     = min(10,  RSI_raw / RSI_MAX × 10)
```

Strain weights *w_i* are calibrated to reflect the relative contribution of each body region to upper-extremity musculoskeletal disorder (WMSD) risk, drawing on RULA [20] and NIOSH lifting guidelines [21] (Table 2). RSI_MAX = 150 normalizes the score such that a task exclusively composed of full-body bending (B17) reaches the maximum. Risk categories follow: LOW (< 2.5), MODERATE (2.5–5.0), HIGH (5.0–7.5), VERY HIGH (≥ 7.5).

**Table 2.** Body-region strain weights used in RSI calculation.

| Body region | Weight (*w*) | Rationale |
|-------------|-------------|-----------|
| body (trunk) | 3.5 | Highest WMSD risk; lumbar load in NIOSH equation |
| full_arm | 2.5 | Full kinetic chain engagement |
| arm | 2.0 | Shoulder/elbow loading |
| hand | 1.5 | Wrist and grip force |
| leg | 1.2 | Lower-body fatigue |
| fingers | 1.0 | Pinch/precision force |
| eyes | 0.5 | Cognitive load, minimal physical strain |

The API returns per-element RSI contributions, overall risk category, identified WMSD targets (e.g. "lumbar flexion — B17"), and prioritized engineering recommendations with estimated RSI reduction (e.g. "install 600 mm lift table → −3.2 RSI").

**Note:** RSI is an engineering screening tool inspired by RULA, REBA, and NIOSH literature and is not a clinical diagnosis instrument. Thresholds are intended for relative comparison across task variants, not for medical decision-making.

### 3.4 Motion Classification Endpoint

`POST /api/v1/classify` accepts a sequence of MediaPipe-format pose frames (minimum 2 frames, recommended 20–90 frames at 30 fps for one motion element) and returns a predicted MODAPTS code, confidence score (0–1), extracted geometric features, alternative candidates with reasoning, and a downstream code suggestion.

---

## 4. Video-to-MODAPTS Pipeline

### 4.1 Pose Extraction

The local script `mediapipe_extract.py` processes a recorded video using the MediaPipe PoseLandmarker Tasks API (v0.10+, `pose_landmarker_full.task` model, 33 keypoints). For each detected frame, it stores normalized (x, y, z) coordinates and visibility for each landmark. The `--skip N` flag processes every N-th frame to trade accuracy for speed.

### 4.2 Temporal Segmentation

Given the total video duration and a predefined task structure, the extractor segments frames into motion elements using proportional timing derived from MODAPTS standard times. For a task with elements *e₁ … eₙ* having MOD values *m₁ … mₙ* and total *M = Σmᵢ*, element *i* spans the video interval:

```
start_pct_i = Σ_{j<i} m_j / M
end_pct_i   = Σ_{j≤i} m_j / M
```

This proportional segmentation is correct when the worker performs the task at MODAPTS standard pace. It degrades gracefully when pace deviates — the resulting annotation remains a useful first approximation that a MODAPTS practitioner can review and correct, analogous to the human-in-the-loop correction step in active learning.

### 4.3 Geometric Rule-Based Classifier

The classifier (`classifier.py`) applies an ordered set of geometric rules to the pose frames of each segment. Feature extraction computes: (1) shoulder-to-hip Y-gap closure (bend signature), (2) hip vertical displacement (sit/stand), (3) ankle vertical oscillation (walk), (4) wrist centroid displacement from segment start (move/grasp), and (5) wrist vertical range (floor-to-chest lift). Classification rules apply in priority order:

1. **B17**: shoulder Y drop ≥ 0.12 normalized frame height AND returns to start position (|Δ shoulder_y| < 0.08 at segment end)
2. **S30/ST30**: hip displacement ≥ 0.15 AND ankle oscillation < 0.04 (guards against walking gait)
3. **W5**: ankle oscillation ≥ 0.04 (bilateral alternating pattern)
4. **M5/M4/M3/M2/G1/G0**: effective wrist displacement thresholds (0.22 / 0.14 / 0.08 / 0.04), where effective displacement = max(point-to-point, 0.85 × vertical range)

On the box-handling demonstration video (467 frames, 29.99 fps, 15.6 s), the classifier correctly predicted Walk (W5, conf. 0.96), Walk-to-table (W5, conf. 0.96), and Place (P2, conf. 1.00) — 3/6 segments. Bend (B17), Grasp (G3), and Lift (M5) required practitioner correction, primarily because the proportional timing placed segment boundaries before the actual motion onset in this particular recording. This is the expected failure mode for proportional segmentation when the worker's pace differs from MODAPTS standard; it is correctable with motion-onset detection or manual boundary adjustment.

### 4.4 Output Format

The extractor writes `demo/annotations.json` containing: video metadata, motion segments with MODAPTS codes, proportional timing, confidence scores, and (optionally) 370 skeletal keyframes for canvas overlay in the demo. The demo site (`demo/index.html`) renders this file without a backend, animating the sequence feed in sync with the video and calling the OpenPTS API on completion.

---

## 5. MODAPTS as a Semantic Layer for Robot Learning

### 5.1 The Annotation Problem in Robot LfD

Modern imitation learning pipelines consume demonstrations in one of three forms: (a) raw sensorimotor trajectories (joint angles, end-effector poses, force/torque), (b) keyframe sequences with object-centric state labels (e.g. "grasped," "placed"), or (c) natural-language task descriptions used to condition foundation models. Each representation has a distinct failure mode. Raw trajectories are high-dimensional and overfit to specific morphologies. Object-centric labels require per-task ontology design and do not transfer to new objects. Natural-language descriptions are underspecified with respect to the *manner* of motion, making it impossible to distinguish a power grasp (G3) from a pinch grasp (G1), or a full-arm swing (M5) from a wrist flick (M2).

### 5.2 Properties of a Universal Motion Vocabulary

We argue that a useful universal motion vocabulary for LfD must be: **body-grounded** (tied to which body segment moves, not which object), **temporally calibrated** (carrying an inherent time budget), **hierarchically composable** (elements chain into sequences that chain into tasks), and **validated on human workers** (grounded in observable, repeatable human behavior rather than theoretical constructs).

MODAPTS codes satisfy all four properties. Body-grounding is explicit in the code structure: M5 describes full-arm extension regardless of what the arm carries. Temporal calibration is intrinsic: 1 MOD = 0.129 s, so a sequence of codes immediately implies a standard cycle time. Codes compose naturally into sequences (Table 3). And the code system has been validated across millions of industrial observations over five decades.

### 5.3 Integration with Robot Learning Pipelines

We propose a three-stage integration:

**Stage 1 — Demonstration labeling**: Record human demonstrations of manufacturing tasks. Run `mediapipe_extract.py` to produce MODAPTS-annotated video segments. A MODAPTS practitioner reviews and corrects classifier predictions (expected correction rate: 30–50% of elements for the current geometric classifier; target < 10% with a supervised model trained on labeled video). This produces a dataset of (video segment, MODAPTS code) pairs.

**Stage 2 — Policy conditioning**: Use MODAPTS codes as structured goal specifications for hierarchical or option-based policies. Each code defines a sub-goal (body region, direction, and implied distance class), which is more constrained than a natural-language instruction and more semantic than a trajectory waypoint. For example, conditioning a policy on (B17, G3, M5) specifies the complete manipulation strategy for a floor-level pickup.

**Stage 3 — Standard time as reward signal**: MODAPTS standard time provides a natural efficiency signal. A robot policy that completes a W5 pace in fewer than 0.645 s is operating above standard pace; one that takes more is below. This allows reward shaping without task-specific instrumentation.

**Table 3.** Example: Heavy box floor-to-table task decomposed into six MODAPTS elements. Standard time with 15% allowance = 10.68 s; RSI = 8.9/10 (VERY HIGH), flagging B17 as the primary WMSD intervention target.

| Element | Code | Qty | MODs | Body region | Time (s) |
|---------|------|-----|------|-------------|----------|
| Walk to box | W5 | 4 | 20 | leg | 2.580 |
| Bend to floor | B17 | 1 | 17 | body | 2.193 |
| Complex grasp | G3 | 1 | 3 | hand | 0.387 |
| Lift to chest | M5 | 1 | 5 | full arm | 0.645 |
| Walk to table | W5 | 5 | 25 | leg | 3.225 |
| Place on table | P2 | 1 | 2 | hand | 0.258 |
| **Total** | | | **72** | | **9.288 s** |

### 5.4 Ergonomics as a Robot Substitution Priority Signal

A direct practical application: the RSI score identifies which elements in a human task create the highest musculoskeletal load and are therefore the highest-priority candidates for robotic substitution. In Table 3, B17 contributes 40% of the trunk load (RSI contribution ≈ 3.95/10) — a VERY HIGH signal for automation. W5 walking steps contribute the next largest share. This gives a principled, quantified prioritization for robot deployment that is grounded in worker health rather than throughput alone.

---

## 6. Discussion

### 6.1 Current Limitations

The geometric rule-based classifier is a heuristic starting point. Its primary failure modes are: (1) proportional timing mismatch when the worker's pace deviates from MODAPTS standard, causing segment boundaries to misalign with actual motion onsets; (2) sensitivity to camera angle and worker morphology (all thresholds are calibrated for a full-body view at ~2 m distance); and (3) inability to distinguish codes that share a body region but differ in load (e.g. G1 vs. G3 both involve the hand but at different object complexity levels). A supervised classifier trained on labeled video data would resolve (1) and (2); (3) requires additional modalities (force sensing, object recognition).

### 6.2 Scope of the RSI Model

The RSI score is an engineering screening tool, not a clinical instrument. Body-region strain weights are calibrated to reflect relative WMSD risk literature but are not derived from epidemiological regression. Users should not use RSI values for medical or regulatory compliance decisions; for those purposes, formal RULA or REBA assessments by a certified ergonomist are required.

### 6.3 MODAPTS Trademark

MODAPTS® is a registered trademark of the International MODAPTS Association. OpenPTS is an independent open-source implementation of publicly documented MODAPTS principles and is not affiliated with or endorsed by the International MODAPTS Association. The mathematical relationships underlying MODAPTS (1 MOD = 0.129 s, body-region code structure) appear in the peer-reviewed literature cited below.

### 6.4 Future Work

Immediate priorities: (a) a supervised pose-sequence classifier trained on labeled manufacturing video, (b) motion-onset detection to replace proportional timing segmentation, (c) expansion to 30+ MODAPTS codes including combined elements and MTM-1 cross-reference, and (d) structured output suitable for direct consumption by hierarchical policy frameworks (e.g. as option definitions in the options framework [16]).

Longer-term: integration with digital twin platforms (Siemens NX, Dassault DELMIA) as an open alternative to proprietary PTS plugins; adaptation to the MOST and MTM systems under a unified `OpenPTS` umbrella; and a labeled dataset of manufacturing demonstrations annotated with MODAPTS codes for training supervised classifiers.

---

## 7. Conclusion

We have presented OpenPTS, the first open-source REST API for MODAPTS-grounded industrial time study. By formalizing fifty years of predetermined time standards as a typed API with ergonomic risk scoring and a pose-sequence classifier, OpenPTS lowers the barrier to entry for researchers and practitioners who wish to (a) digitize existing time studies, (b) annotate robot learning demonstrations with structured motion primitives, or (c) identify high-load operations for robotic substitution. The live API, demo site, and all source code are available under the MIT License.

We invite the robot learning community to evaluate MODAPTS codes as demonstration annotation primitives and to contribute labeled video data, additional motion codes, and supervised classifier implementations via the GitHub repository.

---

## References

[1] Ravichandar, H., Polydoros, A. S., Chernova, S., & Billard, A. (2020). Recent advances in robot learning from demonstration. *Annual Review of Control, Robotics, and Autonomous Systems*, 3, 297–330.

[2] Schaal, S. (1996). Learning from demonstration. *Advances in Neural Information Processing Systems*, 9.

[3] Argall, B. D., Chernova, S., Veloso, M., & Browning, B. (2009). A survey of robot learning from demonstration. *Robotics and Autonomous Systems*, 57(5), 469–483.

[4] Heyde, G. C. (1966). *Depiction of human motions with modular arrangement of predetermined time standards: MODAPTS*. Sydney: GC Heyde.

[5] Lugaresi, C., Tang, J., Nash, H., McClanahan, C., Uboweja, E., Hays, M., … & Grundmann, M. (2019). MediaPipe: A framework for building perception pipelines. *arXiv preprint arXiv:1906.08172*.

[6] Zandin, K. B. (2003). *MOST Work Measurement Systems* (3rd ed.). Marcel Dekker.

[7] Pomerleau, D. A. (1988). ALVINN: An autonomous land vehicle in a neural network. *Advances in Neural Information Processing Systems*, 1.

[8] Abbeel, P., & Ng, A. Y. (2004). Apprenticeship learning via inverse reinforcement learning. *Proceedings of the 21st ICML*.

[9] Chi, C., Xu, Z., Pan, Z., Cousineau, E., Burchfiel, B., Feng, S., … & Song, S. (2023). Diffusion policy: Visuomotor policy learning via action diffusion. *RSS 2023*.

[10] Zhao, T. Z., Kumar, V., Levine, S., & Finn, C. (2023). Learning fine-grained bimanual manipulation with low-cost hardware. *RSS 2023*.

[11] Sharma, P., Mohan, L., Pinto, L., & Gupta, A. (2018). Multiple interactions made easy (MIME): Large scale demonstrations data for imitation. *CoRL 2018*.

[12] Mandlekar, A., Zhu, Y., Garg, A., Booher, J., Spero, M., Tung, A., … & Fei-Fei, L. (2019). RoboTurk: A crowdsourcing platform for robotic skill learning through imitation. *CoRL 2019*.

[13] Goyal, R., Ebrahimi Kahou, S., Michalski, V., Materzynska, J., Westphal, S., Kim, H., … & Memisevic, R. (2017). The "Something Something" video database for learning and evaluating visual common sense. *ICCV 2017*.

[14] Brohan, A., Brown, N., Carbajal, J., Chebotar, Y., Chen, X., Choromanski, K., … & Hausman, K. (2023). RT-2: Vision-language-action models transfer web knowledge to robotic control. *CoRL 2023*.

[15] Kim, M. J., Pertsch, K., Karamcheti, S., Mees, O., Walke, J., Hejna, D., … & Finn, C. (2024). OpenVLA: An open-source vision-language-action model. *arXiv:2406.09246*.

[16] Sutton, R. S., Precup, D., & Singh, S. (1999). Between MDPs and semi-MDPs: A framework for temporal abstraction in reinforcement learning. *Artificial Intelligence*, 112(1–2), 181–211.

[17] McAtamney, L., & Corlett, E. N. (1993). RULA: A survey method for the investigation of work-related upper limb disorders. *Applied Ergonomics*, 24(2), 91–99.

[18] Hignett, S., & McAtamney, L. (2000). Rapid Entire Body Assessment (REBA). *Applied Ergonomics*, 31(2), 201–205.

[19] Vignais, N., Miezal, M., Bleser, G., Mura, K., Gorecky, D., & Marin, F. (2013). Innovative system for real-time ergonomic feedback in industrial manufacturing. *Applied Ergonomics*, 44(4), 566–574.

[20] McAtamney & Corlett (1993). *ibid.*

[21] Waters, T. R., Putz-Anderson, V., Garg, A., & Fine, L. J. (1993). Revised NIOSH equation for the design and evaluation of manual lifting tasks. *Ergonomics*, 36(7), 749–776.
