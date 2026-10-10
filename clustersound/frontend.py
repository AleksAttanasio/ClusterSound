"""YAMNet log-mel frontend reimplemented in numpy (mirrors yamnet/features.py)."""
import numpy as np

SR = 16000
WIN = 400          # 25 ms
HOP = 160          # 10 ms
NFFT = 512
MEL_BANDS = 64
MEL_MIN, MEL_MAX = 125.0, 7500.0
LOG_OFFSET = 0.001
PATCH_FRAMES = 96  # 0.96 s
PATCH_HOP = 48     # 0.48 s


def _hz_to_mel(hz):
    return 1127.0 * np.log1p(np.asarray(hz, dtype=np.float64) / 700.0)


def _mel_matrix() -> np.ndarray:
    """Equivalent of tf.signal.linear_to_mel_weight_matrix (HTK mel, DC bin zeroed)."""
    n_bins = NFFT // 2 + 1
    freqs = np.linspace(0.0, SR / 2.0, n_bins)[1:]
    spec_mel = _hz_to_mel(freqs)[:, None]
    edges = np.linspace(_hz_to_mel(MEL_MIN), _hz_to_mel(MEL_MAX), MEL_BANDS + 2)
    lower, center, upper = edges[:-2], edges[1:-1], edges[2:]
    lo = (spec_mel - lower) / (center - lower)
    up = (upper - spec_mel) / (upper - center)
    w = np.maximum(0.0, np.minimum(lo, up))
    return np.vstack([np.zeros((1, MEL_BANDS)), w]).astype(np.float32)


_MEL = _mel_matrix()
_WINDOW = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(WIN) / WIN)).astype(np.float32)  # periodic hann


def pad_waveform(x: np.ndarray) -> np.ndarray:
    """Pad so there's at least one full patch and an integral number of hops (yamnet pad_waveform)."""
    min_len = PATCH_FRAMES * HOP + WIN - HOP
    n = max(len(x), min_len)
    extra = n - WIN
    n = WIN + int(np.ceil(extra / HOP)) * HOP
    if n > len(x):
        x = np.pad(x, (0, n - len(x)))
    return x


def log_mel(x16k: np.ndarray) -> np.ndarray:
    """[frames, 64] log-mel spectrogram of a 16 kHz waveform (already padded)."""
    n_frames = 1 + (len(x16k) - WIN) // HOP
    if n_frames <= 0:
        return np.zeros((0, MEL_BANDS), np.float32)
    idx = np.arange(WIN)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = x16k[idx] * _WINDOW
    mag = np.abs(np.fft.rfft(frames, n=NFFT, axis=1)).astype(np.float32)
    return np.log(mag @ _MEL + LOG_OFFSET).astype(np.float32)


def patches(mel: np.ndarray) -> np.ndarray:
    """Frame the log-mel into [N, 96, 64] patches with 0.48 s hop."""
    if mel.shape[0] < PATCH_FRAMES:
        return np.zeros((0, PATCH_FRAMES, MEL_BANDS), np.float32)
    n = 1 + (mel.shape[0] - PATCH_FRAMES) // PATCH_HOP
    idx = np.arange(PATCH_FRAMES)[None, :] + PATCH_HOP * np.arange(n)[:, None]
    return np.ascontiguousarray(mel[idx], dtype=np.float32)


def waveform_to_patches(x16k: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mel = log_mel(pad_waveform(x16k.astype(np.float32)))
    return mel, patches(mel)
