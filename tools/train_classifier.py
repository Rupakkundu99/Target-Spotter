"""PyTorch CNN Sound Classifier Training Script.

Loads WAV files from data/samples/, computes spectrograms, splits the data,
trains a lightweight 3-layer CNN, and saves the weights to blind_hunter/data/.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path
import numpy as np

# Add project root to sys.path to allow running directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

# PyTorch is required for this training script
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from blind_hunter import config
from blind_hunter.audio import synth_model


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
MODEL_SAVE_PATH = Path(__file__).resolve().parent.parent / config.MODEL_PATH

CLASSES = ["background", "clap", "snap", "ping"]


def load_wav(path: Path) -> np.ndarray:
    """Load a 16-bit PCM WAV file into a float32 numpy array."""
    with wave.open(str(path), "rb") as w:
        frames = w.readframes(w.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16)
        return samples.astype(np.float32) / 32768.0


def load_dataset() -> tuple[np.ndarray, np.ndarray]:
    """Load all WAV files, compute spectrograms, and return X and y."""
    X_list = []
    y_list = []

    for label_idx, class_name in enumerate(CLASSES):
        class_dir = DATA_DIR / class_name
        if not class_dir.exists():
            print(f"Warning: Directory {class_dir} does not exist. Skipping.")
            continue

        wav_files = list(class_dir.glob("*.wav"))
        print(f"Loading {len(wav_files)} files from class '{class_name}'...")
        
        for f in wav_files:
            try:
                audio = load_wav(f)
                spectrogram = synth_model.compute_spectrogram(audio)  # shape (129, 56)
                X_list.append(spectrogram)
                y_list.append(label_idx)
            except Exception as e:
                print(f"Error loading {f.name}: {e}")

    if not X_list:
        raise ValueError("No training data found in data/samples/! Please run tools/record_samples.py first.")

    X = np.stack(X_list, axis=0)  # Shape: (N, 129, 56)
    # Add a channel dimension for CNN: (N, 1, 129, 56)
    X = np.expand_dims(X, axis=1)
    y = np.array(y_list, dtype=np.int64)

    return X, y


def main() -> int:
    print("====================================================")
    print("        Blind Hunter CNN Classifier Trainer         ")
    print("====================================================")

    try:
        X, y = load_dataset()
    except ValueError as err:
        print(f"Error: {err}")
        return 1

    print(f"\nDataset loaded. Total samples: {X.shape[0]}")
    print(f"Input feature shape: {X.shape[1:]}")

    # Shuffle and split into Train (80%) and Val (20%)
    indices = np.arange(X.shape[0])
    np.random.seed(42)
    np.random.shuffle(indices)

    split_idx = int(len(indices) * 0.8)
    train_indices = indices[:split_idx]
    val_indices = indices[split_idx:]

    X_train, y_train = X[train_indices], y[train_indices]
    X_val, y_val = X[val_indices], y[val_indices]

    # Convert to PyTorch Tensors
    train_dataset = TensorDataset(torch.tensor(X_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.long))
    val_dataset = TensorDataset(torch.tensor(X_val, dtype=torch.float32), torch.tensor(y_val, dtype=torch.long))

    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False)

    # Instantiate model
    model = synth_model.get_torch_model(num_classes=len(CLASSES))
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    print("\nTraining classifier neural network...")
    epochs = 20
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for data, target in train_loader:
            optimizer.zero_grad()
            output = model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * data.size(0)

        train_loss /= len(train_loader.dataset)

        # Validate
        model.eval()
        correct = 0
        val_loss = 0.0
        with torch.no_grad():
            for data, target in val_loader:
                output = model(data)
                loss = criterion(output, target)
                val_loss += loss.item() * data.size(0)
                pred = output.argmax(dim=1, keepdim=True)
                correct += pred.eq(target.view_as(pred)).sum().item()

        val_loss /= len(val_loader.dataset)
        val_acc = correct / len(val_loader.dataset) * 100.0

        print(f"Epoch {epoch:02d}/{epochs} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f} - Val Acc: {val_acc:.1f}%")

    # Evaluate final confusion matrix on validation set
    print("\n--- Final Validation Metrics ---")
    model.eval()
    correct = 0
    predictions = []
    targets = []
    with torch.no_grad():
        for data, target in val_loader:
            output = model(data)
            pred = output.argmax(dim=1)
            predictions.extend(pred.tolist())
            targets.extend(target.tolist())
            correct += pred.eq(target).sum().item()

    accuracy = correct / len(val_loader.dataset) * 100.0
    print(f"Final Validation Accuracy: {accuracy:.2f}%")

    # Print a text confusion matrix
    cm = np.zeros((4, 4), dtype=int)
    for t, p in zip(targets, predictions):
        cm[t, p] += 1

    print("\nConfusion Matrix (Rows=True, Cols=Predicted):")
    print(f"{'':12s} | {'bg':4s} {'clap':4s} {'snap':4s} {'ping':4s}")
    print("-" * 36)
    for idx, class_name in enumerate(CLASSES):
        print(f"{class_name:12s} | {cm[idx, 0]:4d} {cm[idx, 1]:4d} {cm[idx, 2]:4d} {cm[idx, 3]:4d}")

    # Save model weights
    MODEL_SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), str(MODEL_SAVE_PATH))
    print(f"\nModel weights saved successfully to:\n   {MODEL_SAVE_PATH}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
