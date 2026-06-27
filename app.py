import os
import uuid
import threading
import time
import json
import shutil
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["OUTPUT_FOLDER"] = "outputs"

for d in ["uploads", "outputs", "models"]:
    os.makedirs(d, exist_ok=True)

AUDIO_EXTENSIONS = {"mp3", "wav", "flac", "ogg", "m4a", "aac", "wma", "aiff"}
VIDEO_EXTENSIONS = {"mp4", "mkv", "avi", "mov", "wmv", "webm", "flv"}
ALLOWED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

tasks: dict = {}
tasks_lock = threading.Lock()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_video(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in VIDEO_EXTENSIONS


def set_task(task_id: str, **kwargs):
    with tasks_lock:
        if task_id not in tasks:
            tasks[task_id] = {}
        tasks[task_id].update(kwargs)


def get_task(task_id: str) -> dict:
    with tasks_lock:
        return tasks.get(task_id, {}).copy()


def cleanup_old_tasks():
    """Remove tasks and their files that are older than 1 hour."""
    cutoff = time.time() - 3600
    with tasks_lock:
        to_delete = [tid for tid, t in tasks.items() if t.get("created_at", 0) < cutoff]
    for tid in to_delete:
        task = get_task(tid)
        for key in ("input_path", "output_paths"):
            paths = task.get(key)
            if isinstance(paths, str):
                paths = [paths]
            if isinstance(paths, list):
                for p in paths:
                    try:
                        if p and os.path.exists(p):
                            os.remove(p)
                    except OSError:
                        pass
        with tasks_lock:
            tasks.pop(tid, None)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if f.filename == "" or not allowed_file(f.filename):
        return jsonify({"error": "Invalid file type"}), 400

    ext = f.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    f.save(save_path)

    return jsonify(
        {
            "file_id": filename,
            "original_name": secure_filename(f.filename),
            "is_video": is_video(f.filename),
        }
    )


def _run_task(task_id: str, func, *args, **kwargs):
    set_task(task_id, status="processing", created_at=time.time())
    try:
        result = func(*args, **kwargs)
        set_task(task_id, status="done", **result)
    except Exception as exc:
        set_task(task_id, status="error", error=str(exc))


@app.route("/api/separate", methods=["POST"])
def separate():
    """Vocal / stem separation using Demucs."""
    data = request.get_json()
    file_id = data.get("file_id")
    mode = data.get("mode", "vocals")  # vocals | stems | choir

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    task_id = uuid.uuid4().hex
    set_task(task_id, status="queued", created_at=time.time())

    def run():
        from utils.separator import separate_audio
        out_dir = os.path.join(app.config["OUTPUT_FOLDER"], task_id)
        os.makedirs(out_dir, exist_ok=True)
        outputs = separate_audio(input_path, out_dir, mode=mode)
        return {"output_paths": outputs, "output_dir": out_dir}

    threading.Thread(target=_run_task, args=(task_id, run), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/denoise", methods=["POST"])
def denoise():
    """Noise reduction."""
    data = request.get_json()
    file_id = data.get("file_id")
    stationary = data.get("stationary", True)

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    task_id = uuid.uuid4().hex
    set_task(task_id, status="queued", created_at=time.time())

    def run():
        from utils.denoiser import denoise_audio
        out_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{task_id}_denoised.wav")
        denoise_audio(input_path, out_path, stationary=stationary)
        return {"output_paths": [out_path]}

    threading.Thread(target=_run_task, args=(task_id, run), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/speaker-separate", methods=["POST"])
def speaker_separate():
    """Separate multiple speakers."""
    data = request.get_json()
    file_id = data.get("file_id")
    num_speakers = int(data.get("num_speakers", 2))

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    task_id = uuid.uuid4().hex
    set_task(task_id, status="queued", created_at=time.time())

    def run():
        from utils.speaker_sep import separate_speakers
        out_dir = os.path.join(app.config["OUTPUT_FOLDER"], task_id)
        os.makedirs(out_dir, exist_ok=True)
        outputs = separate_speakers(input_path, out_dir, num_speakers=num_speakers)
        return {"output_paths": outputs, "output_dir": out_dir}

    threading.Thread(target=_run_task, args=(task_id, run), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/convert", methods=["POST"])
def convert():
    """Audio format conversion."""
    data = request.get_json()
    file_id = data.get("file_id")
    target_format = data.get("format", "mp3").lower()
    bitrate = data.get("bitrate", "192k")

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    task_id = uuid.uuid4().hex
    set_task(task_id, status="queued", created_at=time.time())

    def run():
        from utils.audio_utils import convert_format
        out_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{task_id}_converted.{target_format}")
        convert_format(input_path, out_path, target_format=target_format, bitrate=bitrate)
        return {"output_paths": [out_path]}

    threading.Thread(target=_run_task, args=(task_id, run), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/extract-audio", methods=["POST"])
def extract_audio():
    """Extract audio track from video."""
    data = request.get_json()
    file_id = data.get("file_id")
    target_format = data.get("format", "wav").lower()

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    task_id = uuid.uuid4().hex
    set_task(task_id, status="queued", created_at=time.time())

    def run():
        from utils.audio_utils import extract_audio_from_video
        out_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{task_id}_audio.{target_format}")
        extract_audio_from_video(input_path, out_path)
        return {"output_paths": [out_path]}

    threading.Thread(target=_run_task, args=(task_id, run), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/trim", methods=["POST"])
def trim():
    """Trim audio file."""
    data = request.get_json()
    file_id = data.get("file_id")
    start_ms = int(data.get("start_ms", 0))
    end_ms = data.get("end_ms")  # None = until end

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    task_id = uuid.uuid4().hex
    set_task(task_id, status="queued", created_at=time.time())

    def run():
        from utils.audio_utils import trim_audio
        out_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{task_id}_trimmed.wav")
        trim_audio(input_path, out_path, start_ms=start_ms, end_ms=end_ms)
        return {"output_paths": [out_path]}

    threading.Thread(target=_run_task, args=(task_id, run), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/merge", methods=["POST"])
def merge():
    """Merge multiple audio files."""
    data = request.get_json()
    file_ids = data.get("file_ids", [])
    crossfade_ms = int(data.get("crossfade_ms", 0))

    if len(file_ids) < 2:
        return jsonify({"error": "At least 2 files required"}), 400

    input_paths = []
    for fid in file_ids:
        p = os.path.join(app.config["UPLOAD_FOLDER"], fid)
        if not os.path.exists(p):
            return jsonify({"error": f"File {fid} not found"}), 404
        input_paths.append(p)

    task_id = uuid.uuid4().hex
    set_task(task_id, status="queued", created_at=time.time())

    def run():
        from utils.audio_utils import merge_audio
        out_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{task_id}_merged.wav")
        merge_audio(input_paths, out_path, crossfade_ms=crossfade_ms)
        return {"output_paths": [out_path]}

    threading.Thread(target=_run_task, args=(task_id, run), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/pitch", methods=["POST"])
def pitch():
    """Pitch shift audio."""
    data = request.get_json()
    file_id = data.get("file_id")
    semitones = float(data.get("semitones", 0))

    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    task_id = uuid.uuid4().hex
    set_task(task_id, status="queued", created_at=time.time())

    def run():
        from utils.audio_utils import pitch_shift
        out_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{task_id}_pitch.wav")
        pitch_shift(input_path, out_path, semitones=semitones)
        return {"output_paths": [out_path]}

    threading.Thread(target=_run_task, args=(task_id, run), daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/task/<task_id>")
def task_status(task_id: str):
    task = get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    response = {"status": task.get("status"), "error": task.get("error")}

    if task.get("status") == "done":
        paths = task.get("output_paths", [])
        response["outputs"] = [
            {
                "filename": os.path.basename(p),
                "label": _stem_label(os.path.basename(p)),
                "download_url": f"/api/download/{task_id}/{os.path.basename(p)}",
            }
            for p in paths
            if os.path.exists(p)
        ]

    return jsonify(response)


def _stem_label(filename: str) -> str:
    name = filename.lower()
    mapping = {
        "vocals": "Vocals",
        "no_vocals": "Accompaniment",
        "drums": "Drums",
        "bass": "Bass",
        "other": "Other",
        "denoised": "Denoised",
        "speaker1": "Speaker 1",
        "speaker2": "Speaker 2",
        "speaker3": "Speaker 3",
        "converted": "Converted",
        "trimmed": "Trimmed",
        "merged": "Merged",
        "audio": "Extracted Audio",
        "pitch": "Pitch Shifted",
    }
    for key, label in mapping.items():
        if key in name:
            return label
    return filename


@app.route("/api/download/<task_id>/<filename>")
def download(task_id: str, filename: str):
    # Security: only allow files that were produced by this task
    task = get_task(task_id)
    if not task:
        abort(404)
    safe_name = secure_filename(filename)
    paths = task.get("output_paths", [])
    for p in paths:
        if os.path.basename(p) == safe_name:
            if os.path.exists(p):
                return send_file(p, as_attachment=True, download_name=safe_name)
    abort(404)


@app.route("/api/waveform/<file_id>")
def waveform(file_id: str):
    """Return downsampled waveform data for visualization."""
    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    try:
        from utils.audio_utils import get_waveform_data
        data = get_waveform_data(input_path, num_points=800)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/info/<file_id>")
def file_info(file_id: str):
    """Return basic audio info (duration, channels, sample rate)."""
    input_path = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
    if not os.path.exists(input_path):
        return jsonify({"error": "File not found"}), 404

    try:
        from utils.audio_utils import get_audio_info
        info = get_audio_info(input_path)
        return jsonify(info)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
