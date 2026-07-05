"""Central tunables for Blind Hunter.

Everything a level designer or playtester might want to tweak lives here so the
rest of the codebase reads config rather than hard-coding magic numbers.
"""

# ---------------------------------------------------------------------------
# Audio capture
# ---------------------------------------------------------------------------
SAMPLE_RATE = 44100          # Hz — standard, well supported by built-in mics
BLOCK_SIZE = 1024            # frames per capture block (~23ms at 44.1kHz)
CHANNELS = 1                 # built-in mics are effectively mono for our needs
RING_BUFFER_BLOCKS = 64      # how many blocks the capture ring buffer holds

# ---------------------------------------------------------------------------
# Onset / clap detection
# ---------------------------------------------------------------------------
# A clap is a sharp energy spike above the ambient noise floor. We track an
# adaptive floor and fire when the block energy exceeds it by TRIGGER_FACTOR.
CALIBRATION_SECONDS = 1.0        # ambient sampling window at startup
NOISE_FLOOR_ALPHA = 0.995        # EMA smoothing for the adaptive floor (per block)
TRIGGER_FACTOR = 6.0             # energy must exceed floor * this to count
MIN_TRIGGER_RMS = 0.01           # absolute floor so dead-silent rooms don't false-fire
REFRACTORY_SECONDS = 0.18        # debounce: ignore new claps within this window
DOUBLE_CLAP_WINDOW = 0.45        # two claps inside this = a "double clap" action

# Intensity mapping: peak RMS is normalized against this to produce 0..1.
INTENSITY_REFERENCE_RMS = 0.35   # RMS considered a "full strength" clap

# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------
TICK_RATE = 60               # game logic / render ticks per second

# ---------------------------------------------------------------------------
# Player / movement
# ---------------------------------------------------------------------------
STEP_MIN = 0.4               # world units for a soft clap
STEP_MAX = 1.6               # world units for a full-strength clap
TURN_DEGREES = 90            # voice-command turn increment (Option A)

# ---------------------------------------------------------------------------
# Echolocation reveal
# ---------------------------------------------------------------------------
REVEAL_RADIUS_MIN = 60       # pixels, soft clap
REVEAL_RADIUS_MAX = 220      # pixels, full clap
REVEAL_FADE_SECONDS = 0.5

# ---------------------------------------------------------------------------
# Rendering / window (Phase 2)
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800
VIEWPORT_MARGIN = 40         # px padding between the map and the window edge

# Base darkness. The screen sits at this level except where reveals light it.
# 0 = pure black; a small value adds a faint atmospheric floor. Kept at 0 to
# honor the "navigate blind" pillar — orientation comes from the player dot.
AMBIENT_LIGHT = 0

REVEAL_FALLOFF_POWER = 1.6   # gradient softness; higher = tighter bright core

# Colors (R, G, B). Scene colors are drawn at full brightness and then gated by
# the reveal light mask, so they only *appear* when lit.
COLOR_BACKGROUND = (4, 4, 6)
COLOR_WALL = (90, 90, 105)
COLOR_FLOOR_GRID = (24, 24, 32)
COLOR_EXTRACTION = (70, 200, 120)
COLOR_PREY = (210, 180, 70)
COLOR_PREDATOR = (200, 60, 60)
COLOR_PLAYER = (120, 200, 255)

# The player marker stays faintly visible even in darkness so you can orient.
# Set to 0 for a fully blind experience.
PLAYER_DOT_ALWAYS_ON = True
PLAYER_DOT_DIM = (30, 55, 75)
PLAYER_RADIUS_PX = 6
FACING_INDICATOR_PX = 22

DRAW_FLOOR_GRID = True       # faint grid inside reveals, helps read the space

# Debug clap intensity fired by the SPACE key (play without a mic).
DEBUG_CLAP_INTENSITY = 0.85

# ---------------------------------------------------------------------------
# Audio Classifier & Sound Actions (Phase 4 CNN)
# ---------------------------------------------------------------------------
MODEL_PATH = "blind_hunter/data/sound_classifier.pt"
CLASSIFIER_HISTORY_SECONDS = 1.0     # keep 1 second of audio in the rolling buffer
CLASSIFIER_WINDOW_SECONDS = 0.5      # segment size to classify
CLASSIFIER_WINDOW_PRE_ONSET = 0.05   # include 50ms before the onset to capture the attack

# Snap (stealth action) scales
SNAP_STEP_SCALE = 0.4                # soft small step
SNAP_NOISE_SCALE = 0.2               # very quiet footprint
SNAP_REVEAL_RADIUS_SCALE = 0.4       # small dim reveal

# Ping (whistle / tongue click) scales
PING_REVEAL_RADIUS_SCALE = 1.8       # long-range reveal
PING_CONE_ANGLE = 45                 # degrees (width of visual cone)
PING_NOISE_SCALE = 1.2               # loud, alerts predators

# ---------------------------------------------------------------------------
# Audio output / spatialization
# ---------------------------------------------------------------------------
MIXER_CHANNELS = 16
DISTANCE_FALLOFF = 1.0       # higher = faster volume drop with distance
MAX_AUDIBLE_DISTANCE = 25.0  # world units past which entities are silent

MASTER_VOLUME = 0.85         # global scale applied to every voice
BACK_MUFFLE = 0.55           # volume multiplier when a source is behind the player
                             # (cheap front/back cue — stereo pan alone can't
                             #  disambiguate front from back)
AUDIO_BUFFER = 512           # mixer buffer size; smaller = lower latency

# Heartbeat tension loop
HEARTBEAT_VOLUME = 0.7       # peak volume when a predator is adjacent
HEARTBEAT_TEMPO_MIN = 0.6    # beats/sec at the edge of audible range
HEARTBEAT_TEMPO_MAX = 3.0    # beats/sec when a predator is on top of you

# ---------------------------------------------------------------------------
# AI & stealth loop (Phase 4)
# ---------------------------------------------------------------------------
# Noise events decay over NOISE_DECAY_SECONDS (see game/noise.py). Their
# effective loudness fades across that window so entities lose interest smoothly
# instead of snapping between "heard" and "silent".

# Prey: how long a prey lingers in ALERT before breaking into a FLEE. Gives the
# escalation a readable beat instead of flipping states in a single tick.
PREY_ALERT_TO_FLEE_SECONDS = 0.35
# How far ahead (world units) a fleeing prey aims its escape target.
PREY_FLEE_LOOKAHEAD = 5.0

# Predator: a loud noise this close (world units) with at least this decayed
# intensity yanks the predator straight into CHASE, even beyond CHASE_RANGE.
PREDATOR_CHASE_NOISE_RANGE = 7.0
PREDATOR_CHASE_NOISE_INTENSITY = 0.55
# Patrol movement is slower and more casual than an active chase.
PREDATOR_PATROL_SPEED_FACTOR = 0.55

# How close (world units) an entity must get to a target cell to count as
# "arrived" — used for patrol waypoints and finishing an investigation.
AI_ARRIVE_DISTANCE = 0.6

# Double-clap capture: a prey within this range of the player is caught.
CAPTURE_RANGE = 1.5
# Reaching within this range of the extraction point (with the prey quota met)
# wins the run.
EXTRACTION_RANGE = 1.5
