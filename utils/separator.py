"""
Vocal / stem separation using Demucs (htdemucs model).

Model setup
-----------
Place the pre-downloaded model file at:
    models/demucs/htdemucs.th

Download URL:
    https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/htdemucs.th

If the file is absent the library will attempt to download it automatically
(requires internet access on first use).
"""

from pathlib import Path
import os
import soundfile as sf
import numpy as np


_MODEL_REPO = Path("models/demucs")
_MODEL_NAME = "htdemucs"
_SEP = None  # cached Separator instance


def _get_separator():
    global _SEP
    if _SEP is not None:
        return _SEP

    try:
        import demucs.api as dapi
    except ImportError:
        raise RuntimeError(
            "Demucs is not installed. Run: pip install demucs"
        )

    repo = _MODEL_REPO if (_MODEL_REPO / f"{_MODEL_NAME}.th").exists() else None

    try:
        _SEP = dapi.Separator(model=_MODEL_NAME, repo=repo, device="cpu", jobs=1)
    except Exception:
        # Fallback: let demucs find/download the model itself
        _SEP = dapi.Separator(model=_MODEL_NAME, device="cpu", jobs=1)

    return _SEP


def separate_audio(input_path: str, out_dir: str, mode: str = "vocals") -> list[str]:
    """
    Separate audio using Demucs.

    Parameters
    ----------
    input_path : str
        Path to the input audio file.
    out_dir : str
        Directory where output stems will be saved.
    mode : str
        One of:
          - 'vocals'  → returns [vocals.wav, accompaniment.wav]
          - 'stems'   → returns [vocals.wav, drums.wav, bass.wav, other.wav]
          - 'choir'   → alias for 'vocals' (vocal emphasis)

    Returns
    -------
    list[str]
        Absolute paths to the output files.
    """
    sep = _get_separator()

    origin, separated = sep.separate_audio_file(Path(input_path))
    sr = sep.samplerate

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_files: list[str] = []

    if mode in ("vocals", "choir"):
        # Save vocals
        vocals_path = str(out_dir / "vocals.wav")
        _save_stem(separated["vocals"], vocals_path, sr)
        output_files.append(vocals_path)

        # Accompaniment = drums + bass + other combined
        acc = separated["drums"] + separated["bass"] + separated["other"]
        acc_path = str(out_dir / "no_vocals.wav")
        _save_stem(acc, acc_path, sr)
        output_files.append(acc_path)

    elif mode == "stems":
        for stem_name in ("vocals", "drums", "bass", "other"):
            stem_path = str(out_dir / f"{stem_name}.wav")
            _save_stem(separated[stem_name], stem_path, sr)
            output_files.append(stem_path)

    else:
        raise ValueError(f"Unknown mode: {mode!r}")

    return output_files


def _save_stem(tensor, path: str, sr: int):
    """Save a stem tensor (C, T) as a WAV file."""
    import torch
    audio = tensor.cpu()
    # Convert to numpy: shape (T, C) or (T,)
    np_audio = audio.numpy()
    if np_audio.ndim == 2:
        np_audio = np_audio.T  # (T, C)
    else:
        np_audio = np_audio  # (T,)
    sf.write(path, np_audio, sr)
