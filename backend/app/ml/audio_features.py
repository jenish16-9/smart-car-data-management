"""Dependency-light WAV decoding and fixed-length acoustic feature extraction."""

import io
import math
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly


@dataclass(frozen=True)
class FeatureConfig:
    sample_rate: int = 16_000
    clip_seconds: float = 3.0
    frame_ms: float = 25.0
    hop_ms: float = 10.0
    n_fft: int = 512
    n_mels: int = 64
    min_hz: float = 50.0
    max_hz: float = 7_600.0

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def _pcm_to_float(raw: bytes, sample_width: int) -> np.ndarray:
    if sample_width == 1:
        return (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if sample_width == 3:
        packed = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        values = (
            packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
        )
        values = np.where(values & 0x800000, values - 0x1000000, values)
        return values.astype(np.float32) / 8388608.0
    if sample_width == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    raise ValueError(f"Unsupported PCM sample width: {sample_width} bytes")


def decode_wav(source: bytes | Path | str, target_sample_rate: int = 16_000) -> np.ndarray:
    """Decode uncompressed PCM WAV to mono float32 and resample if needed."""
    stream = io.BytesIO(source) if isinstance(source, bytes) else str(source)
    try:
        with wave.open(stream, "rb") as reader:
            if reader.getcomptype() != "NONE":
                raise ValueError("Compressed WAV is not supported; convert it to PCM WAV")
            channels = reader.getnchannels()
            source_rate = reader.getframerate()
            sample_width = reader.getsampwidth()
            raw = reader.readframes(reader.getnframes())
    except (EOFError, wave.Error) as exc:
        raise ValueError("Input is not a valid PCM WAV file") from exc

    if channels < 1 or source_rate < 1:
        raise ValueError("WAV must have at least one channel and a positive sample rate")
    waveform = _pcm_to_float(raw, sample_width)
    if waveform.size % channels:
        raise ValueError("WAV sample data is not aligned to its channel count")
    waveform = waveform.reshape(-1, channels).mean(axis=1, dtype=np.float32)
    if source_rate != target_sample_rate:
        divisor = math.gcd(source_rate, target_sample_rate)
        waveform = resample_poly(waveform, target_sample_rate // divisor, source_rate // divisor).astype(np.float32)
    return np.clip(waveform, -1.0, 1.0)


def _hz_to_mel(value: np.ndarray | float) -> np.ndarray | float:
    return 2595.0 * np.log10(1.0 + np.asarray(value) / 700.0)


def _mel_to_hz(value: np.ndarray | float) -> np.ndarray | float:
    return 700.0 * (np.power(10.0, np.asarray(value) / 2595.0) - 1.0)


def _mel_filterbank(config: FeatureConfig) -> np.ndarray:
    frequencies = np.linspace(0, config.sample_rate / 2, config.n_fft // 2 + 1)
    mel_points = np.linspace(_hz_to_mel(config.min_hz), _hz_to_mel(config.max_hz), config.n_mels + 2)
    hz_points = _mel_to_hz(mel_points)
    filters = np.zeros((config.n_mels, frequencies.size), dtype=np.float32)
    for index in range(config.n_mels):
        left, center, right = hz_points[index : index + 3]
        filters[index] = np.maximum(
            0.0,
            np.minimum(
                (frequencies - left) / max(center - left, 1e-9),
                (right - frequencies) / max(right - center, 1e-9),
            ),
        )
    filters /= np.maximum(filters.sum(axis=1, keepdims=True), 1e-12)
    return filters


def extract_features(waveform: np.ndarray, config: FeatureConfig = FeatureConfig()) -> np.ndarray:
    """Create compact log-mel, delta, energy, and spectral summary features."""
    target_length = int(config.sample_rate * config.clip_seconds)
    waveform = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if waveform.size < target_length:
        waveform = np.pad(waveform, (0, target_length - waveform.size))
    else:
        waveform = waveform[:target_length]
    waveform = waveform - waveform.mean()

    frame_length = int(config.sample_rate * config.frame_ms / 1000)
    hop_length = int(config.sample_rate * config.hop_ms / 1000)
    frames = np.lib.stride_tricks.sliding_window_view(waveform, frame_length)[::hop_length]
    windowed = frames * np.hanning(frame_length).astype(np.float32)
    spectrum = np.fft.rfft(windowed, n=config.n_fft, axis=1)
    power = (spectrum.real**2 + spectrum.imag**2).astype(np.float32)
    mel_power = power @ _mel_filterbank(config).T
    log_mel = np.log10(np.maximum(mel_power, 1e-10))
    delta = np.diff(log_mel, axis=0, prepend=log_mel[:1])

    mel_summary = np.concatenate(
        [
            log_mel.mean(axis=0),
            log_mel.std(axis=0),
            np.percentile(log_mel, 10, axis=0),
            np.percentile(log_mel, 90, axis=0),
            log_mel.max(axis=0),
            delta.mean(axis=0),
            delta.std(axis=0),
        ]
    )

    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    zero_crossing = np.mean(np.not_equal(frames[:, 1:] >= 0, frames[:, :-1] >= 0), axis=1)
    frequencies = np.fft.rfftfreq(config.n_fft, 1 / config.sample_rate)
    power_sum = np.maximum(power.sum(axis=1), 1e-12)
    centroid = (power * frequencies).sum(axis=1) / power_sum
    bandwidth = np.sqrt((power * (frequencies - centroid[:, None]) ** 2).sum(axis=1) / power_sum)
    temporal = np.array(
        [
            rms.mean(),
            rms.std(),
            np.percentile(rms, 10),
            np.percentile(rms, 90),
            zero_crossing.mean(),
            zero_crossing.std(),
            centroid.mean() / config.sample_rate,
            centroid.std() / config.sample_rate,
            bandwidth.mean() / config.sample_rate,
            bandwidth.std() / config.sample_rate,
        ],
        dtype=np.float32,
    )
    return np.concatenate([mel_summary.astype(np.float32), temporal])


def features_from_wav(source: bytes | Path | str, config: FeatureConfig = FeatureConfig()) -> np.ndarray:
    return extract_features(decode_wav(source, config.sample_rate), config)
