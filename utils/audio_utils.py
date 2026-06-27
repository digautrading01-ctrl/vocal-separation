"""
General audio utility functions:
  - format conversion
  - extract audio from video
  - trim / merge
  - pitch shift
  - waveform data for visualisation
  - file info
"""

from pathlib import Path
import os
import numpy as np
import soundfile as sf


# ---------------------------------------------------------------------------
# Format conversion
# ---------------------------------------------------------------------------

def convert_format(
    input_path: str,
    output_path: str,
    target_format: str = "mp3",
    bitrate: str = "192k",
) -> str:
    from pydub import AudioSegment

    audio = AudioSegment.from_file(input_path)
    params = {}
    if target_format == "mp3":
        params["bitrate"] = bitrate
    audio.export(output_path, format=target_format, **params)
    return output_path


# ---------------------------------------------------------------------------
# Extract audio from video
# ---------------------------------------------------------------------------

def extract_audio_from_video(input_path: str, output_path: str) -> str:
    from pydub import AudioSegment

    audio = AudioSegment.from_file(input_path)
    ext = Path(output_path).suffix.lstrip(".").lower() or "wav"
    audio.export(output_path, format=ext)
    return output_path


# ---------------------------------------------------------------------------
# Trim
# ---------------------------------------------------------------------------

def trim_audio(
    input_path: str,
    output_path: str,
    start_ms: int = 0,
    end_ms: int | None = None,
) -> str:
    from pydub import AudioSegment

    audio = AudioSegment.from_file(input_path)
    trimmed = audio[start_ms:end_ms]
    trimmed.export(output_path, format="wav")
    return output_path


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_audio(
    input_paths: list[str],
    output_path: str,
    crossfade_ms: int = 0,
) -> str:
    from pydub import AudioSegment

    combined = AudioSegment.from_file(input_paths[0])
    for path in input_paths[1:]:
        next_seg = AudioSegment.from_file(path)
        if crossfade_ms > 0:
            combined = combined.append(next_seg, crossfade=crossfade_ms)
        else:
            combined = combined + next_seg
    combined.export(output_path, format="wav")
    return output_path


# ---------------------------------------------------------------------------
# Pitch shift
# ---------------------------------------------------------------------------

def pitch_shift(input_path: str, output_path: str, semitones: float = 0.0) -> str:
    try:
        import librosa
    except ImportError:
        raise RuntimeError("librosa is not installed. Run: pip install librosa")

    y, sr = librosa.load(input_path, mono=False, sr=None)

    if y.ndim == 1:
        y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=semitones)
    else:
        # Multi-channel: shift each channel independently
        y_shifted = np.stack(
            [librosa.effects.pitch_shift(ch, sr=sr, n_steps=semitones) for ch in y]
        )

    # soundfile expects (T, C) for multi-channel
    if y_shifted.ndim == 2:
        sf.write(output_path, y_shifted.T, sr)
    else:
        sf.write(output_path, y_shifted, sr)

    return output_path


# ---------------------------------------------------------------------------
# Waveform data for the browser canvas renderer
# ---------------------------------------------------------------------------

def get_waveform_data(input_path: str, num_points: int = 800) -> dict:
    """
    Return a compact representation of the audio waveform.

    Returns a dict with:
      - peaks : list of floats in [0, 1] (one per pixel column)
      - duration : float (seconds)
      - sample_rate : int
      - channels : int
    """
    data, sr = sf.read(input_path, always_2d=True)  # (T, C)
    duration = data.shape[0] / sr
    channels = data.shape[1]

    # Mix to mono for visualisation
    mono = data.mean(axis=1)

    # Downsample to num_points by taking max absolute value in each block
    block = max(1, len(mono) // num_points)
    peaks = []
    for i in range(num_points):
        start = i * block
        end = start + block
        chunk = mono[start:end]
        if len(chunk) == 0:
            peaks.append(0.0)
        else:
            peaks.append(float(np.max(np.abs(chunk))))

    # Normalise
    max_val = max(peaks) if max(peaks) > 0 else 1.0
    peaks = [p / max_val for p in peaks]

    return {
        "peaks": peaks,
        "duration": round(duration, 3),
        "sample_rate": sr,
        "channels": channels,
    }


# ---------------------------------------------------------------------------
# File info
# ---------------------------------------------------------------------------

def get_audio_info(input_path: str) -> dict:
    """Return basic metadata about an audio/video file."""
    try:
        info = sf.info(input_path)
        return {
            "duration": round(info.duration, 3),
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "format": info.format,
            "subtype": info.subtype,
        }
    except Exception:
        # Fallback via pydub (handles more formats + video containers)
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_path)
        return {
            "duration": round(len(audio) / 1000.0, 3),
            "sample_rate": audio.frame_rate,
            "channels": audio.channels,
            "format": Path(input_path).suffix.lstrip(".").upper(),
            "subtype": "",
        }
