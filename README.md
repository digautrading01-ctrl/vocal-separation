# AI Vocal Separator

A fully offline Flask web application for AI-powered audio processing. It provides vocal separation, noise reduction, multi-stem extraction, speaker separation, and common audio utilities — all running locally on your machine.

---

## Features

| Category | Feature | Description |
|----------|---------|-------------|
| **Hot** | Vocal Separation | Extract clean vocals or accompaniment using Demucs htdemucs |
| **Hot** | One-click Noise Reduction | Remove background hiss/hum via spectral gating (no model needed) |
| **Hot** | Audio Track Separation | Separate into 4 stems: vocals, drums, bass, other |
| **Hot** | Speaker Separation | Unmix up to 3 overlapping speakers (SpeechBrain SepFormer) |
| **Hot** | Extract Audio from Video | Pull the audio track from MP4, MKV, AVI, MOV, etc. |
| **Hot** | Format Conversion | Convert between MP3, WAV, FLAC, OGG, AAC |
| **Tools** | Pitch Adjustment | Shift pitch ±12 semitones without changing tempo |
| **Tools** | Audio Trim | Clip any time range from an audio file |
| **Tools** | Audio Merge | Concatenate multiple audio files with optional crossfade |

---

## Requirements

- Python 3.10 or newer
- [FFmpeg](https://ffmpeg.org/download.html) installed and on your `PATH` (required by pydub for non-WAV files)

---

## Installation

```bash
# 1. Clone / download this project
cd ai-vocal-separator

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt
```

### Install FFmpeg

| OS | Command |
|----|---------|
| Windows | Download from https://ffmpeg.org/download.html, add `bin/` folder to PATH |
| macOS | `brew install ffmpeg` |
| Ubuntu | `sudo apt install ffmpeg` |

---

## Model Setup (Offline Use)

All AI models must be placed in the `models/` folder before using the relevant features offline.

### 1. Demucs htdemucs (Vocal & Stem Separation)

Used by: **Vocal Separation**, **Audio Track Separation**

Download the model checkpoint and place it at:

```
models/
└── demucs/
    └── htdemucs.th        ← place downloaded file here
```

**Download URL:**
```
https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/htdemucs.th
```

File size: ~83 MB

> **Note:** If the file is not found in `models/demucs/`, Demucs will attempt to download it automatically on first use (requires internet access).

---

### 2. SpeechBrain SepFormer (Speaker Separation)

Used by: **Speaker Separation**

On **first run** (with internet access), SpeechBrain will automatically download the model to:

```
models/
└── sepformer-whamr/       ← auto-created on first run
    ├── hyperparams.yaml
    ├── custom_interface.py
    ├── encoder.ckpt
    ├── masknet.ckpt
    └── decoder.ckpt
```

For a **fully offline** setup, manually download all files from HuggingFace and place them in `models/sepformer-whamr/`:

```
https://huggingface.co/speechbrain/sepformer-whamr
```

> **Note:** SepFormer processes audio at 8 kHz mono. Input files are resampled automatically.

---

### 3. Noise Reduction

Used by: **One-click Noise Reduction**

No model file is required. This feature uses the `noisereduce` library (spectral gating algorithm) which runs entirely offline.

---

## Running the App

```bash
python app.py
```

Then open your browser at:

```
http://localhost:5000
```

The app listens on all interfaces (`0.0.0.0:5000`) so it is also accessible from other devices on your local network.

---

## Project Structure

```
ai-vocal-separator/
├── app.py                  # Flask application (routes, task management)
├── requirements.txt        # Python dependencies
├── README.md               # This file
│
├── models/                 # Place AI model files here (see above)
│   └── demucs/
│       └── htdemucs.th
│
├── uploads/                # Temporary uploaded files (auto-cleaned after 1 h)
├── outputs/                # Processed output files (auto-cleaned after 1 h)
│
├── utils/
│   ├── separator.py        # Demucs wrapper (vocal / stem separation)
│   ├── denoiser.py         # Noise reduction (noisereduce)
│   ├── speaker_sep.py      # SpeechBrain SepFormer wrapper
│   └── audio_utils.py      # Format conversion, trim, merge, pitch, waveform
│
├── templates/
│   └── index.html          # Single-page UI
│
└── static/
    ├── css/
    │   └── style.css       # Dark-theme styles
    └── js/
        └── main.js         # Frontend logic (upload, waveform, API polling)
```

---

## Usage Guide

### Vocal Separation

1. Click **Vocal Separation** in the sidebar.
2. Drag & drop an audio/video file onto the upload zone, or click **Choose File**.
3. Select a model card:
   - **Vocal Extraction** — optimised Roformer variant for clear vocals.
   - **Choir / Harmony Separation** — for choral or multi-voice recordings.
4. Click **Start Separation**.
5. Download **Vocals** or **Accompaniment** from the results panel.

### Noise Reduction

1. Upload an audio file.
2. Toggle **Stationary noise** on (for constant-spectrum noise like fan hum) or off (for variable noise).
3. Click **Reduce Noise**.

### Audio Track Separation (4 Stems)

1. Upload a music track.
2. Click **Separate Stems**.
3. Download individual stems: **Vocals**, **Drums**, **Bass**, **Other**.

### Speaker Separation

1. Upload a recording with multiple overlapping speakers.
2. Select the number of speakers (2 or 3).
3. Click **Separate Speakers**.
4. Download per-speaker tracks (**Speaker 1**, **Speaker 2**, …).

### Format Conversion

1. Upload any supported audio file.
2. Select target format and bitrate.
3. Click **Convert**.

### Audio Trim

1. Upload an audio file.
2. Enter **Start** and **End** times in seconds.
3. Click **Trim**.

### Audio Merge

1. Click **Add File** to add 2 or more audio files.
2. Optionally set a **Crossfade** duration (in milliseconds).
3. Click **Merge**.

### Pitch Adjustment

1. Upload an audio file.
2. Move the slider (−12 to +12 semitones).
3. Click **Shift Pitch**.

---

## Supported File Formats

| Type | Formats |
|------|---------|
| Audio input | MP3, WAV, FLAC, OGG, M4A, AAC, WMA, AIFF |
| Video input | MP4, MKV, AVI, MOV, WMV, WebM, FLV |
| Audio output | WAV (default), MP3, FLAC, OGG, AAC |

---

## Technical Notes

- **Processing is asynchronous.** Long tasks (especially separation) run in a background thread and are polled by the browser every 1.5 seconds.
- **Uploaded files are automatically deleted** after 1 hour.
- **GPU acceleration:** If a CUDA-compatible GPU is available and PyTorch is installed with CUDA support, you can change `device="cpu"` to `device="cuda"` in `utils/separator.py` and `utils/speaker_sep.py` for faster processing.
- **Max upload size** is set to 500 MB. Adjust `MAX_CONTENT_LENGTH` in `app.py` if needed.
- **No authentication** is required. Do not expose this app directly to the public internet.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ffmpeg not found` | Install FFmpeg and ensure it is on your `PATH` |
| `demucs not found` | Run `pip install demucs` |
| `speechbrain not found` | Run `pip install speechbrain` |
| Separation produces silence | Verify `models/demucs/htdemucs.th` exists and is not corrupted |
| Speaker separation sounds robotic | SepFormer is optimised for clean studio conditions; try shorter clips |
| Waveform not displayed | Upload a WAV or FLAC file; some MP3 encodings may fail the fast-path reader |

---

## License

This project's application code is provided as-is for personal and research use.

Bundled AI models have their own licenses:
- **Demucs** — MIT License (Meta AI)
- **SpeechBrain / SepFormer** — Apache 2.0
- **noisereduce** — MIT License
