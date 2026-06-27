"""
Multi-speaker voice separation using SpeechBrain SepFormer.

Model setup
-----------
On first run (requires internet), SpeechBrain will download the model to:
    models/sepformer-whamr/

To use fully offline, manually download all files from:
    https://huggingface.co/speechbrain/sepformer-whamr
and place them under:
    models/sepformer-whamr/

Note: SepFormer expects 8 kHz mono input. This module handles resampling
automatically.
"""

from pathlib import Path
import os
import numpy as np
import soundfile as sf

_MODEL_DIR = "models/sepformer-whamr"
_MODEL_SOURCE = "speechbrain/sepformer-whamr"
_sep_model = None


def _get_model():
    global _sep_model
    if _sep_model is not None:
        return _sep_model

    try:
        from speechbrain.pretrained import SepformerSeparation
    except ImportError:
        raise RuntimeError(
            "SpeechBrain is not installed. Run: pip install speechbrain"
        )

    os.makedirs(_MODEL_DIR, exist_ok=True)
    _sep_model = SepformerSeparation.from_hparams(
        source=_MODEL_SOURCE,
        savedir=_MODEL_DIR,
        run_opts={"device": "cpu"},
    )
    return _sep_model


def separate_speakers(
    input_path: str,
    out_dir: str,
    num_speakers: int = 2,
) -> list[str]:
    """
    Separate overlapping speakers in an audio file.

    Parameters
    ----------
    input_path : str
        Path to the input audio file (any format/sample rate).
    out_dir : str
        Directory where separated speaker files will be saved.
    num_speakers : int
        Number of speakers expected (currently 2 is best supported).

    Returns
    -------
    list[str]
        Paths to the per-speaker WAV files.
    """
    import torch
    import torchaudio

    model = _get_model()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load and resample to 8 kHz mono (SepFormer requirement)
    waveform, sr = torchaudio.load(input_path)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)  # stereo → mono

    target_sr = 8000
    if sr != target_sr:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sr)
        waveform = resampler(waveform)

    # Save a temporary 8 kHz mono WAV for the model
    tmp_path = str(out_dir / "_tmp_input.wav")
    torchaudio.save(tmp_path, waveform, target_sr)

    # Run separation
    est_sources = model.separate_file(path=tmp_path)  # (1, T, num_speakers)

    output_files: list[str] = []
    n = min(num_speakers, est_sources.shape[-1])

    for i in range(n):
        speaker_audio = est_sources[:, :, i].detach().cpu()  # (1, T)
        speaker_path = str(out_dir / f"speaker{i + 1}.wav")
        torchaudio.save(speaker_path, speaker_audio, target_sr)
        output_files.append(speaker_path)

    # Clean up temp file
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    return output_files
