# Blind Hunter

Audio-driven echolocation stealth game — laptop-only edition. You play almost
entirely blind: the screen stays black except for brief flashes triggered by
your own claps, captured through the built-in mic. Making noise reveals the map
to you *and* reveals you to predators.

See [`context_new.md`](./context_new.md) for the full design doc.

## Status

**Phases 1–3 are functional** (mic capture + clap detection; playable black-screen
loop with clap-to-move and the radial reveal; spatial audio with stereo panning,
distance falloff, and the proximity heartbeat). Phases 4–5 are scaffolded with
stubs so each layer has a home.

| Phase | What | State |
|------|------|-------|
| 1 | Audio input pipeline (capture + onset detection) | ✅ working |
| 2 | Core game loop + radial reveal | ✅ working (`app.py`, `game/loop.py`, `render/`) |
| 3 | Spatial audio + heartbeat | ✅ working (`audio/`) |
| 4 | Prey/predator AI + capture mechanic | 🧱 stubbed (`game/ai/`) |
| 5 | Webcam directional input (Option B) | 🧱 stubbed (`input/direction_resolver.py`) |

## Quick start

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt

# Phase 1 milestone — clap near the mic and watch it detect:
python main.py --mode claptest

# Phase 2 — the playable loop: black screen, clap to move, terrain flashes:
python main.py --mode play
```

### Phase 2 controls

Clap into the mic to step forward (a louder clap = a bigger step) and light a
radial reveal around you. Works without a mic too:

| Input | Action |
|-------|--------|
| clap / **SPACE** | step forward + echolocation reveal |
| **← / →** | turn 90° (stand-in for Option A voice turning) |
| **ESC** | quit |

The screen stays black except for the fading flash each clap triggers. A faint
blue dot marks the player so you can orient (toggle with `PLAYER_DOT_ALWAYS_ON`
in `config.py`). Reach the extraction point after capturing the required prey to
win; a predator reaching you ends the run (AI movement lands in Phase 4).

Expected output:

```
[calibrating ambient noise... speak/clap NOT during this second]
[done, noise floor ~ 0.0021]
listening — clap near the mic (Ctrl+C to quit)
Clap detected: intensity=0.82  (double=False)
```

> Headphones strongly recommended once audio output exists (Phase 3) — avoids
> the speaker→mic feedback loop.

## Architecture

The whole design pivots on one invariant: **every input scheme produces a
`ClapEvent(direction, intensity, timestamp)`** (see `events.py`). The game core,
AI, and audio engine never touch the input layer, so swapping Option A (mic-only)
for Option B (mic + webcam) — or a future hardware mic array — is a drop-in.

```
blind_hunter/
  config.py            # all tunables in one place
  events.py            # ClapEvent / Direction / VoiceCommand  <- the seam
  loader.py            # level JSON -> World
  app.py               # Pygame frontend / playable loop        [Phase 2] OK
  input/
    base.py            # InputSource ABC (thread-safe event queue)
    audio_capture.py   # sounddevice capture thread            [Phase 1] OK
    onset_detection.py # adaptive-noise-floor clap detector     [Phase 1] OK
    direction_resolver.py  # Option A / Option B seam           [Phase 1/5]
    clap_source.py     # assembled Phase 1 pipeline             [Phase 1] OK
  game/
    state.py           # Player / Entity / Map data model
    loop.py            # apply_clap + update_world tick logic    [Phase 2] OK
    noise.py           # noise-event propagation                [Phase 4]
    ai/prey.py         # idle->alert->flee                      [Phase 4]
    ai/predator.py     # patrol->investigate->chase->attack     [Phase 4]
  audio/
    synth.py           # procedural placeholder sounds (numpy)   [Phase 3] OK
    spatial_mixer.py   # stereo pan + distance attenuation        [Phase 3] OK
    heartbeat.py       # predator-proximity tension loop        [Phase 3] OK
  render/
    camera.py          # world <-> screen transform             [Phase 2] OK
    reveal.py          # radial reveal + light-mask compositing  [Phase 2] OK
  data/maps/level1.json
assets/audio/*.wav     # placeholder sounds (generated)
tools/
  clap_test.py         # Phase 1 milestone console app
  gen_assets.py        # (re)generate placeholder audio assets
main.py                # entry point (--mode claptest | play)
```

## Onset detection, briefly

`onset_detection.py` is ML-free by design: it tracks an adaptive noise floor
(EMA of quiet blocks), fires when a block's RMS spikes past
`floor * TRIGGER_FACTOR`, debounces with a refractory window, and normalizes the
peak into a 0..1 intensity. A one-second ambient calibration at startup seeds the
floor to cut false triggers in echoey rooms. Tune it all in `config.py`.

## Spatial audio (Phase 3)

**Use headphones.** Stereo panning is what makes the world legible, and it
avoids the speaker→mic feedback loop.

Each audio-emitting entity gets its own looping voice on a `pygame` mixer
channel. Every tick, `spatial_mixer.py` recomputes a stereo `(left, right)` gain
from the entity's position relative to the player's position and facing, and
pushes it via `Channel.set_volume(left, right)`:

- **Pan** from the angle between facing and the source (dead ahead = centered).
- **Distance falloff** — silent past `MAX_AUDIBLE_DISTANCE`.
- **Back-muffle** — sources behind you are quieter, a cheap front/back cue since
  stereo pan alone can't disambiguate front from back.

`heartbeat.py` retriggers a "lub-dub" whose tempo and volume rise as the nearest
predator closes in — passive tension that needs no ping.

Sounds are **procedural placeholders** generated by `synth.py` (loop-seamless
breath/growl via a sin² envelope). Regenerate them with
`python -m tools.gen_assets`, or drop real recordings into `assets/audio/` using
the same filenames — no code changes needed. Missing files fall back to the
synth at runtime, so the game never crashes on absent assets.

> Phase 3 milestone (the blind playtest): with headphones on, can you locate a
> hidden prey by ear alone and walk to it? The prey at map positions in
> `level1.json` emit a looping breath from their virtual location; pan + falloff
> should let you home in without ever seeing them.
