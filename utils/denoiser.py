"""
Noise reduction using the noisereduce library (spectral gating).

No model file is required — this is a signal-processing algorithm.
"""

import numpy as np
import soundfile as sf


def denoise_audio(
    input_path: str,
    output_path: str,
    stationary: bool = True,
    prop_decrease: float = 0.75,
) -> str:
    """
    Reduce background noise from an audio file.

    Parameters
    ----------
    input_path : str
        Path to the input audio file.
    output_path : str
        Path where the denoised audio will be saved (WAV).
    stationary : bool
        If True, assumes a stationary noise floor (fan hum, AC noise).
        If False, uses adaptive estimation (better for variable noise).
    prop_decrease : float
        Proportion by which the noise is decreased (0.0–1.0).

    Returns
    -------
    str
        Path to the output file.
    """
    try:
        import noisereduce as nr
    except ImportError:
        raise RuntimeError(
            "noisereduce is not installed. Run: pip install noisereduce"
        )

    data, rate = sf.read(input_path, always_2d=True)  # shape: (T, C)
    data = data.astype(np.float32)

    channels = data.shape[1]
    reduced_channels = []

    for c in range(channels):
        channel_data = data[:, c]
        reduced = nr.reduce_noise(
            y=channel_data,
            sr=rate,
            stationary=stationary,
            prop_decrease=prop_decrease,
        )
        reduced_channels.append(reduced)

    reduced_audio = np.stack(reduced_channels, axis=1)  # (T, C)

    # If mono, write as 1-D
    if channels == 1:
        reduced_audio = reduced_audio[:, 0]

    sf.write(output_path, reduced_audio, rate)
    return output_path
