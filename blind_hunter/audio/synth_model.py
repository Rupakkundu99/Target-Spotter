"""PyTorch CNN Model Definition and Spectrogram Features.

This file defines the SoundClassifierCNN network and the feature extraction
function. Features are computed in pure NumPy (STFT spectrogram) to avoid
external dependency overhead (like librosa/scipy) and ensure identical, 
high-speed execution on both laptops and the Jetson Nano.
"""

from __future__ import annotations

import numpy as np

# PyTorch is imported lazily inside the classes/methods that need it,
# so the game can still import this file even if PyTorch isn't fully installed.

def compute_spectrogram(audio: np.ndarray) -> np.ndarray:
    """Convert 0.5s of float32 raw audio at 44.1kHz to a 129x56 spectrogram.

    Args:
        audio: 1D numpy array of float32 samples.
        
    Returns:
        Sxx: 2D numpy array of shape (129, 56) containing log-magnitude STFT.
    """
    # Downsample from 44.1kHz to 14.7kHz (take every 3rd sample)
    if len(audio) == 22050:
        audio = audio[::3]
        
    # Ensure size is exactly 7350 samples (0.5s at 14.7kHz)
    target_len = 7350
    if len(audio) < target_len:
        audio = np.pad(audio, (0, target_len - len(audio)))
    elif len(audio) > target_len:
        audio = audio[:target_len]

    # STFT parameters
    nperseg = 256
    noverlap = 128
    step = nperseg - noverlap

    # Hamming window
    window = np.hamming(nperseg)

    # Calculate number of segments
    num_segments = (len(audio) - noverlap) // step  # (7350 - 128) // 128 = 56

    spectrogram_list = []
    for i in range(num_segments):
        start = i * step
        end = start + nperseg
        segment = audio[start:end] * window
        # Compute real FFT magnitude
        fft_vals = np.abs(np.fft.rfft(segment))  # Output size is 129 for nperseg=256
        # Log scale compression to normalize dynamic range
        spectrogram_list.append(np.log1p(fft_vals))

    # Stack to shape (129, 56)
    Sxx = np.stack(spectrogram_list, axis=1)
    return Sxx


def get_torch_model(num_classes: int = 4):
    """Factory function to instantiate and return the PyTorch CNN model."""
    import torch
    import torch.nn as nn

    class SoundClassifierCNN(nn.Module):
        def __init__(self, num_classes: int = 4):
            super().__init__()
            # Input shape: (Batch, 1, 129, 56)
            self.conv1 = nn.Conv2d(1, 8, kernel_size=3, padding=1)
            self.conv2 = nn.Conv2d(8, 16, kernel_size=3, padding=1)
            self.conv3 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
            
            self.pool = nn.MaxPool2d(2, 2)
            self.relu = nn.ReLU()
            
            # Feature size calculations:
            # Input: (129, 56)
            # Pool 1: (64, 28)
            # Pool 2: (32, 14)
            # Pool 3: (16, 7)
            # Flattened: 32 * 16 * 7 = 3584
            self.fc1 = nn.Linear(32 * 16 * 7, 64)
            self.fc2 = nn.Linear(64, num_classes)
            
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = self.pool(self.relu(self.conv1(x)))
            x = self.pool(self.relu(self.conv2(x)))
            x = self.pool(self.relu(self.conv3(x)))
            x = x.view(x.size(0), -1)  # Flatten
            x = self.relu(self.fc1(x))
            x = self.fc2(x)
            return x

    return SoundClassifierCNN(num_classes)
