# Blind Hunter — Audio-Driven Echolocation Stealth Game
### Laptop-Only Edition — Full Context & Technical Plan
*(No external hardware required — runs entirely on a laptop's built-in mic, webcam, and speakers/headphones)*

---

## 1. Concept Overview

**Blind Hunter** is a stealth/hunting game where the player operates almost entirely blind. The screen stays black except for brief, sound-triggered flashes of visibility. All movement, exploration, and hunting is driven by real-world audio input (claps, stomps, voice) captured through the laptop's built-in microphone, and all feedback to the player comes through spatial (stereo-panned) audio.

The player is both **hunter** (tracking prey by sound) and **hunted** (avoiding predators who react to the player's own noise). The core tension is: *making noise helps you see and locate things, but also gives away your position.*

This edition is designed to run **entirely on a laptop** — no Jetson Nano, no mic array HAT, no extra sensors. Just the built-in microphone, optionally the webcam, and headphones/speakers.

### Elevator Pitch
A physical-audio hybrid of *Papa Sangre* (audio-only navigation) and *Perception* (echolocation horror), where your real claps and voice are the controller, and the world only reveals itself in flashes triggered by your own sound — built with zero extra hardware.

---

## 2. Core Pillars

1. **Sound is the only input.** No joystick/keyboard for movement — claps, stomps, and voice volume/timing drive the player.
2. **Sound is the only output that matters.** Visuals are minimal and reactive, not primary.
3. **Every action has a risk/reward tradeoff.** Making noise reveals the map to you AND reveals you to threats.
4. **Tension over reflexes.** This is a slow-burn stealth/horror experience, not a twitch shooter.
5. **Zero hardware barrier to entry.** Anyone can play with just a laptop and headphones — no purchases, no setup beyond installing dependencies.

---

## 3. Input Design — Two Options (No External Hardware)

A laptop's built-in microphone is typically mono or a close-set dual-mic array optimized for noise cancellation, **not** spatial triangulation — so true direction-of-arrival (DOA) detection like a 4-mic array would give isn't available. Two approaches replace it:

### Option A — Intensity-Only Movement (Simplest, Audio-Only) — **Recommended MVP**
- Clap = step forward. Loud clap = big step, soft clap = small/cautious step.
- Turning handled by short voice keywords ("left", "right", "turn") via lightweight keyword spotting.
- Double-clap in quick succession = alternate action (e.g., "capture" attempt on nearby prey).
- Fully mic-only. No webcam needed. Fastest to prototype and most reliable across different laptops/rooms.

### Option B — Mic + Webcam Hybrid for Pseudo-Direction (More Immersive, Still Zero Extra Hardware)
- Webcam + OpenCV hand-tracking (e.g., MediaPipe Hands) detects **where** your hand is in frame (left / center / right, and near/far from camera) at the moment you clap.
- Microphone detects **that** a clap happened (onset detection) and its **loudness/intensity**.
- Combine the two signals: webcam gives direction, mic gives timing + intensity. This effectively reconstructs directional input without needing a physical mic array at all.
- Slightly more setup complexity (lighting-dependent hand tracking) but meaningfully more immersive — the player can gesture-clap toward where they think a sound came from.

**Development approach:** Build Option A first as the MVP (fully playable, mic-only). Layer in Option B as an enhancement once the core loop is validated — the game architecture below is designed so this swap is a clean drop-in (both options ultimately just produce a `ClapEvent(direction, intensity, timestamp)`).

---

## 4. Game Mechanics

### 4.1 Movement — "Clap to Step"
- Player claps (or stomps/shouts) into the laptop mic.
- Onset detection identifies a discrete "sound event"; volume maps to step size.
- **Option A:** direction is either fixed-forward or set via the last voice-command turn.
- **Option B:** direction comes from webcam hand position at the moment of the clap.
- No sound = no movement. Silence is a valid stealth tactic when a predator is near.

### 4.2 Facing / Orientation
- **Option A:** orientation changes only via voice command ("left"/"right" = rotate 90°), keeping movement itself a simple forward-step-on-clap model. Recommended for MVP — much simpler state machine.
- **Option B:** orientation can be continuously informed by hand-gesture direction at clap time, removing the need for separate turn commands.

### 4.3 Echolocation Ping ("Reveal")
- Every clap also acts as a **sonar ping**:
  - Triggers a short reverberant audio decay whose length/pitch subtly encodes distance to the nearest wall/obstacle (closer = shorter, higher-pitched return).
  - Triggers a **radial light reveal** on screen (~0.4–0.6 sec fade) showing terrain within a radius around the player's position.
- This is the player's *only* way to see the map. No persistent visibility.

### 4.4 Hunting Prey
- Prey entities emit ambient audio cues (footsteps, breathing, rustling) from their virtual map position, rendered to the player via stereo panning + distance-based volume attenuation.
- Player must triangulate direction/distance purely by ear, move toward the source, and perform a "capture" action (double-clap or sustained shout within close range) to hunt successfully.
- Prey AI: simple state machine — `idle → alert → flee`. Prey becomes alert if player noise exceeds a threshold within its hearing radius; flees away from noise source.

### 4.5 Being Hunted (Predator Layer)
- One or more predator entities patrol the map with their own AI (`patrol → investigate → chase → attack`).
- Predators are drawn toward player noise (each clap adds a "noise event" at the player's position with a decay radius over time).
- A **heartbeat audio cue** increases in tempo/volume as a predator's distance to the player decreases — passive tension feedback that doesn't require an active ping.
- If a predator reaches the player's position while "chasing," the run ends (jump-scare + game over state, restart from checkpoint).

### 4.6 Win / Loss Conditions
- **Win:** Hunt the required number of prey (or a specific "objective" prey) and reach an extraction point, all before a predator catches you.
- **Loss:** Predator catch, OR (optional) a noise/dread meter maxes out from excessive careless clapping.

### 4.7 Difficulty / Progression
- Later levels reduce the ping reveal radius, increase predator hearing sensitivity, or add multiple predators.
- Optional meta-progression: unlock alternate "echolocation types" (e.g., whistle vs clap vs stomp) with different reveal radius/noise tradeoffs.

---

## 5. Output Mechanism — Spatial Audio & Visual Reveal

### 5.1 Positional Audio Engine
- All game entities (prey, predators, ambient world sounds) have a virtual (x, y) position on the map.
- Player has a virtual position + facing.
- For each audio-emitting entity, compute:
  - **Relative angle** to player facing → stereo pan value.
  - **Distance** → volume attenuation (inverse-square-ish falloff) + optional low-pass filtering to simulate muffling at distance.
- Implementation: `pygame.mixer` with per-channel panning, or a custom mixer on a raw `sounddevice`/`pyaudio` output stream if finer control is needed.
- **Headphones strongly recommended** over laptop speakers — stereo panning is far more legible and immersive with headphones, and it avoids feedback loops between output audio and the input mic.

### 5.2 Visual Reveal System
- Base state: near-black screen (maybe a very faint vignette or noise texture for atmosphere).
- On ping event: render a radial gradient "flashlight from below" reveal centered on player position, radius scaled by clap intensity, fading out over ~0.5s.
- Rendered in **Pygame** (2D top-down or simple first-person layered sprites) — runs easily on any laptop.

### 5.3 Heartbeat / Tension Audio
- Continuous low-volume heartbeat loop, tempo and volume driven by nearest predator distance (updated per game tick).
- This is the main "passive" feedback channel that doesn't require the player to ping.

---

## 6. System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                          Laptop                                  │
│                                                                    │
│  ┌───────────────┐         ┌─────────────────────┐               │
│  │ Built-in Mic   │────────▶│  Audio Input Thread  │               │
│  └───────────────┘         │  (sounddevice/pyaudio)│               │
│                             └──────────┬───────────┘               │
│  ┌───────────────┐                    │                            │
│  │ Webcam         │──(Option B only)──┤                            │
│  │ (OpenCV/       │                    │                            │
│  │  MediaPipe)    │                    │                            │
│  └───────────────┘                    ▼                            │
│                       ┌─────────────────────────┐                  │
│                       │ Onset Detection +        │                 │
│                       │ Direction Resolver        │                 │
│                       │ (voice cmd OR hand pos)   │                 │
│                       └──────────┬──────────────┘                  │
│                                  │  ClapEvent(direction, intensity)  │
│                                  ▼                                  │
│                       ┌─────────────────────────┐                  │
│                       │      Game Core Loop      │                  │
│                       │  (state machine, tick-   │                  │
│                       │   based, ~30–60Hz)        │                  │
│                       │                           │                  │
│                       │  - Player state           │                  │
│                       │  - Prey AI (state machine)│                  │
│                       │  - Predator AI            │                  │
│                       │  - Noise event propagation│                  │
│                       │  - Map / collision data   │                  │
│                       └───────┬──────────┬────────┘                  │
│                               │          │                            │
│                 ┌─────────────▼┐      ┌──▼─────────────────┐          │
│                 │ Visual Reveal │      │ Spatial Audio Mixer │         │
│                 │ Renderer      │      │ (pygame.mixer with   │        │
│                 │ (Pygame)      │      │  per-channel pan +   │        │
│                 │               │      │  heartbeat loop)      │        │
│                 └───────┬───────┘      └──────────┬──────────┘          │
│                         │                          │                     │
└─────────────────────────┼──────────────────────────┼─────────────────────┘
                           ▼                          ▼
                   Laptop screen              Headphones (recommended)
```

### 6.1 Threading Model
- **Audio Capture Thread**: continuous, low-latency, feeds a ring buffer.
- **(Optional) Webcam Thread**: runs hand-tracking at a lower frame rate (~15–20fps is plenty), writes latest hand position to shared state.
- **Event Processing Thread**: consumes audio buffer chunks, runs onset detection, resolves direction (voice command lookup or latest hand position), emits `ClapEvent`s to a thread-safe queue.
- **Main Game Loop (Pygame)**: runs at fixed tick rate, consumes events from the queue each frame, updates game state, triggers rendering and audio mixer updates.
- **Audio Output**: handled via `pygame.mixer` channels, updated each tick based on entity positions relative to the player.

### 6.2 Data Model (simplified)
```
Player {
  position: (x, y)
  facing: angle
  noise_history: [(timestamp, position, intensity), ...]
}

Entity (Prey | Predator) {
  id, type
  position: (x, y)
  state: enum (idle, alert, flee, patrol, investigate, chase, attack)
  hearing_radius: float
  audio_profile: { idle_sound, alert_sound, move_sound }
}

Map {
  grid / nav-mesh for collision & pathfinding
  spawn_points: { prey: [...], predator: [...], player_start, extraction }
}
```

---

## 7. Tech Stack (Laptop-Only)

| Layer | Tool / Library | Notes |
|---|---|---|
| Mic capture | `sounddevice` (preferred) or `pyaudio` | Cross-platform, works with built-in laptop mic |
| Onset/clap detection | `numpy` + simple energy-threshold/attack-time heuristic | No ML model needed |
| Direction (Option A) | Keyword spotting — Porcupine (Picovoice) or a small custom command classifier | For "left"/"right"/"turn" voice commands |
| Direction (Option B) | `opencv-python` + `mediapipe` (Hands) | Webcam hand-position tracking, runs fine on CPU |
| Game loop / rendering | `pygame` | Lightweight, cross-platform (Mac/Windows/Linux) |
| Spatial audio mixer | `pygame.mixer` (multi-channel, per-channel volume/pan) | Sufficient for MVP; can be swapped for a custom `sounddevice` mixer later if needed |
| AI (prey/predator) | Plain Python state machines | Deterministic, no ML required |
| Data/config | JSON or YAML for map layout, entity configs | Easy to iterate on level design without code changes |

**No GPU, no CUDA, no embedded hardware required.** This runs as a normal Python application on any reasonably modern laptop (Mac, Windows, or Linux).

---

## 8. Build Plan / Milestones

### Phase 1 — Audio Input Pipeline (Days 1–3)
- Set up mic capture via `sounddevice`, verify buffer stream is stable.
- Implement onset/clap detection (energy threshold + attack-time heuristic).
- **Milestone:** Console app that prints `Clap detected: intensity=0.8` reliably when you clap near the laptop.

### Phase 2 — Core Game Loop (Days 3–6)
- Build minimal Pygame loop: black screen, player position, single prey entity with idle sound.
- Wire clap events → player movement (Option A: intensity-only forward step + voice-command turning).
- Implement radial reveal effect on ping.
- **Milestone:** Player can clap to move around a blank map and see brief terrain flashes.

### Phase 3 — Spatial Audio (Days 6–9)
- Implement panning/distance-attenuation via `pygame.mixer` channels.
- Add ambient prey sound looping from a virtual position, confirm player can localize it by ear with headphones.
- **Milestone:** Blind playtest — can a tester locate a hidden sound source using only audio?

### Phase 4 — AI & Stealth Loop (Days 9–13)
- Implement prey state machine (idle/alert/flee) reacting to noise events.
- Implement predator state machine (patrol/investigate/chase) + heartbeat audio feedback.
- Implement capture mechanic (double-clap/sustained shout at close range).
- **Milestone:** Full loop playable — hunt prey while avoiding a predator, win/loss states functional.

### Phase 5 — Webcam Direction Upgrade (Optional, Days 13–16)
- Add `mediapipe` hand-tracking thread.
- Fuse hand-position direction with clap timing/intensity into `ClapEvent(direction, intensity)`.
- **Milestone:** Player can clap toward a direction and have the game register it correctly (validate against known hand positions).

### Phase 6 — Polish & Content (Days 16–21)
- Level/map authoring (JSON-configured layouts, 2–3 levels).
- Difficulty tuning (reveal radius, predator sensitivity).
- Audio asset polish (footsteps, growls, ambient drones, capture stinger).
- **Milestone:** Polished vertical slice — 2–3 levels, full stealth loop, ready to demo on just a laptop + headphones.

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Built-in mic picks up ambient room noise / echo, causing false clap triggers | Tune energy threshold + attack-time heuristic per environment; add a brief "noise floor calibration" step at game start |
| No true directional audio input without a mic array | Use Option A (voice-command turning) for MVP; Option B (webcam hand-tracking) as a good-enough directional substitute |
| Webcam hand-tracking unreliable in poor lighting | Keep Option B optional/secondary; always ship Option A as the reliable fallback |
| Audio latency between clap and game response feels laggy | Keep buffer sizes small; profile end-to-end latency early, target <150ms |
| Speaker feedback loop (output audio picked up by input mic) | Strongly recommend headphones; if speakers must be used, add a brief mic-mute window right after triggering output audio |
| Scope creep (too many mechanics) | Lock MVP to: Option A movement + single prey + single predator + one level; expand only after MVP is fun |

---

## 10. Stretch Goals (Post-MVP)
- Full Option B directional movement as the primary control scheme once validated.
- Multiple echolocation "tools" (whistle = long-range/quiet ping, stomp = short-range/loud ping) using pitch/spectral classification of the clap sound.
- Multiplayer co-op: one hunter, one "spotter" whispering directions via a second input device (e.g., phone mic over local network).
- Procedurally generated maps for replayability.
- Later port to Jetson Nano or a Raspberry Pi as a standalone physical installation, once the game loop is fully validated on laptop (the architecture above is designed so the input layer is swappable without touching game logic).

---

## 11. Requirements List (Laptop-Only, No Purchases Needed)

- A laptop (Mac, Windows, or Linux) with a working built-in or external microphone
- Headphones (wired preferred for lowest latency; any pair works)
- Webcam (built-in laptop camera is fine) — only needed if building Option B
- Python 3.9+ environment with: `sounddevice` or `pyaudio`, `numpy`, `pygame`, and optionally `opencv-python` + `mediapipe` for Option B, and `pvporcupine` (Picovoice) if using voice-command turning in Option A

---

## 12. Summary

This laptop-only edition strips away all custom hardware while preserving the core novelty of the concept: real-world claps driving movement in a game you navigate almost entirely blind, with the map only revealed in sound-triggered flashes. Option A (intensity-only clap + voice-command turning) gets a fully playable prototype running fast with zero extra gear beyond headphones. Option B (webcam hand-position + mic) adds a genuinely clever directional-input layer using hardware every laptop already has, without needing a physical mic array. The architecture is deliberately built so the input layer is swappable — meaning if this later gets ported to a Jetson Nano or another embedded device, the game logic, AI, and audio engine carry over unchanged.
