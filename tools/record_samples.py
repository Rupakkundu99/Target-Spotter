"""Interactive audio data collection tool.

Prompts the user to:
1. Choose their Ping sound (Whistle or Tongue Click).
2. Record 10 seconds of background room noise (silence, breathing, speaking).
3. Record 30 claps.
4. Record 30 finger snaps.
5. Record 30 pings (whistles or clicks).

Automatically detects when a sound occurs using the OnsetDetector,
extracts a clean 0.5s window around it, and saves it as a WAV file.
"""

from __future__ import annotations

import sys
import time
import wave
from pathlib import Path
import numpy as np

# Add project root to sys.path to allow running directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

from blind_hunter import config
from blind_hunter.input.audio_capture import AudioCapture
from blind_hunter.input.onset_detection import OnsetDetector


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"


def save_wav(path: Path, samples: np.ndarray, sample_rate: int = config.SAMPLE_RATE) -> None:
    """Save a float32 array as a 16-bit PCM mono WAV file."""
    peak = np.max(np.abs(samples))
    if peak > 0:
        normalized = samples / peak * 0.9  # Scale to peak of 0.9 to avoid clipping
    else:
        normalized = samples
    int_data = (normalized * 32767).astype(np.int16)
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(int_data.tobytes())


def record_background(capture: AudioCapture) -> None:
    print("\n--- Phase 1: Recording Background Noise ---")
    print("Please sit quietly for 10 seconds. Do not clap or snap.")
    print("Normal room noise, mouse clicks, keyboard taps, or breathing are fine.")
    input("Press ENTER when ready to start...")
    
    # Empty queue
    while capture.read(timeout=0.01) is not None:
        pass
        
    duration = 10.0
    samples_needed = int(config.SAMPLE_RATE * duration)
    recorded = []
    
    start_time = time.time()
    while time.time() - start_time < duration:
        block = capture.read(timeout=0.5)
        if block is not None:
            recorded.append(block)
            
    all_samples = np.concatenate(recorded)
    
    # Split into 0.5s slices and save
    slice_len = int(config.SAMPLE_RATE * 0.5)  # 22050 samples
    num_slices = len(all_samples) // slice_len
    
    for i in range(num_slices):
        chunk = all_samples[i * slice_len : (i + 1) * slice_len]
        save_wav(DATA_DIR / "background" / f"bg_{i:02d}.wav", chunk)
        
    print(f"Recorded {num_slices} background samples successfully.")


def record_class(capture: AudioCapture, detector: OnsetDetector, class_name: str, display_name: str) -> None:
    print(f"\n--- Phase: Recording {display_name} ---")
    print(f"We need to record 30 separate instances of your {display_name.lower()}.")
    print("Make the sound near your laptop mic. Wait for the confirmation before doing the next one.")
    input("Press ENTER when ready to start...")
    
    # Empty queue
    while capture.read(timeout=0.01) is not None:
        pass

    history_blocks = []
    max_history = 3  # ~70ms history buffer at 44.1kHz
    
    count = 0
    while count < 30:
        block = capture.read(timeout=0.5)
        if block is None:
            continue
            
        history_blocks.append(block)
        if len(history_blocks) > max_history:
            history_blocks.pop(0)
            
        now = time.monotonic()
        onset = detector.process(block, now)
        if onset is not None:
            # Sound spike detected! Collect the remainder of the 0.5s window.
            # 0.5s is 22050 samples (~22 blocks). We have history + onset block (~4 blocks).
            # We need to collect 19 more blocks to cover the tail.
            tail_blocks = []
            for _ in range(19):
                b = capture.read(timeout=0.5)
                if b is not None:
                    tail_blocks.append(b)
                    
            if len(tail_blocks) < 19:
                # Capture timed out or was interrupted, skip
                history_blocks.clear()
                continue
                
            # Concatenate history + onset + tail
            all_blocks = history_blocks + [block] + tail_blocks
            audio_segment = np.concatenate(all_blocks)
            
            # Find the onset index
            # The onset block starts after history_blocks
            onset_idx = len(history_blocks) * config.BLOCK_SIZE
            
            # Extract 0.5s segment centered around onset (50ms pre-onset to 450ms post-onset)
            pre_samples = int(config.SAMPLE_RATE * 0.05)  # 2205 samples
            start_idx = max(0, onset_idx - pre_samples)
            end_idx = start_idx + int(config.SAMPLE_RATE * 0.5)
            
            segment = audio_segment[start_idx:end_idx]
            
            count += 1
            filename = f"{class_name}_{count:02d}.wav"
            save_wav(DATA_DIR / class_name / filename, segment)
            print(f"[{count}/30] Recorded {display_name} (intensity={onset.intensity:.2f}) -> {filename}")
            
            # Clear history and sleep briefly to let the sound decay
            history_blocks.clear()
            time.sleep(0.5)
            
            # Flush any blocks captured during the sleep
            while capture.read(timeout=0.01) is not None:
                pass


def main() -> int:
    print("====================================================")
    print("       Blind Hunter Sound Classifier Recorder       ")
    print("====================================================")
    print("This script will record audio samples to train the CNN.")
    print("Please connect your headphones/mic before proceeding.")
    
    # 1. Choose Ping Sound
    print("\nWhich 'Ping' sound would you like to use for directional reveal?")
    print("1. Whistle (High pitch, clean frequency)")
    print("2. Tongue Click / Mouth Pop (Easy to do, sharp sound)")
    choice = ""
    while choice not in ("1", "2"):
        choice = input("Enter 1 or 2: ").strip()
        
    ping_display = "Whistle" if choice == "1" else "Tongue Click"
    
    # Init capture & calibration
    capture = AudioCapture()
    detector = OnsetDetector()
    
    print("\n[calibrating noise floor... please stay silent]")
    capture.start()
    
    # Sample ambient for calibration
    ambient = []
    start_cal = time.time()
    while time.time() - start_cal < 1.0:
        b = capture.read(timeout=0.1)
        if b is not None:
            ambient.append(b)
    detector.calibrate(ambient)
    print(f"Calibration done (noise floor ~ {detector.noise_floor:.4f}).")
    
    try:
        # Record classes
        record_background(capture)
        record_class(capture, detector, "clap", "Clap")
        record_class(capture, detector, "snap", "Finger Snap")
        record_class(capture, detector, "ping", ping_display)
        
        print("\n====================================================")
        print("          All audio recording completed!            ")
        print("====================================================")
        print("Your recorded audio is saved in 'data/samples/'.")
        print("Next step: Run the training script to build the model:")
        print("    python -m tools.train_classifier")
        
    except KeyboardInterrupt:
        print("\nRecording canceled.")
    finally:
        capture.stop()
        
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
