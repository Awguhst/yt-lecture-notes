from flask import Flask, request, jsonify, send_file, render_template
from pathlib import Path
from datetime import datetime
import threading
import uuid
import logging

from generator import (
    make_client,
    get_youtube_transcript,
    refine_transcript,
    generate_latex,
    compile_pdf,
)

logging.basicConfig(level=logging.ERROR, format="%(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)
for noisy in ("httpx", "urllib3", "google"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

app = Flask(__name__)

# In-memory job store: job_id -> { status, progress, message, out_dir, files, error }
jobs: dict[str, dict] = {}

OUTPUT_BASE = Path("./outputs")
OUTPUT_BASE.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _output_dir(url: str) -> Path:
    from generator import _extract_video_id  # reuse the private helper
    video_id = _extract_video_id(url)
    name = (
        f"lecture_{video_id}"
        if video_id
        else f"lecture_{datetime.now():%Y%m%d_%H%M%S}"
    )
    out = OUTPUT_BASE / name
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_job(job_id: str, url: str, api_key: str, generate_pdf_flag: bool) -> None:
    """Execute the full generation pipeline in a background thread."""
    job = jobs[job_id]

    def update(progress: int, message: str) -> None:
        job["progress"] = progress
        job["message"]  = message

    def fail(message: str) -> None:
        job["status"]   = "error"
        job["error"]    = message
        job["progress"] = 0

    try:
        client  = make_client(api_key)
        out_dir = _output_dir(url)
        job["out_dir"] = str(out_dir)

        # ── Stage 1: fetch raw transcript ──────────────────────────────────
        update(10, "Fetching transcript from YouTube…")
        raw = get_youtube_transcript(url)

        # ── Stage 2: refine transcript ─────────────────────────────────────
        update(30, "Refining transcript with AI…")
        transcript = refine_transcript(raw, client)
        (out_dir / "transcript.txt").write_text(transcript, encoding="utf-8")

        # ── Stage 3: generate LaTeX ────────────────────────────────────────
        update(55, "Generating LaTeX notes…")
        latex = generate_latex(transcript, client)
        (out_dir / "lecture_notes.tex").write_text(latex, encoding="utf-8")

        files = {
            "transcript": str(out_dir / "transcript.txt"),
            "latex":      str(out_dir / "lecture_notes.tex"),
            "pdf":        None,
        }

        # ── Stage 4: compile PDF (optional) ───────────────────────────────
        if generate_pdf_flag:
            update(78, "Compiling PDF…")
            pdf_path = compile_pdf(latex, "lecture_notes", out_dir)
            files["pdf"] = str(pdf_path)

        job["files"]  = files
        job["status"] = "done"
        update(100, "All done!")

    except FileNotFoundError as exc:   # pdflatex not installed
        fail(str(exc))
    except (ValueError, RuntimeError) as exc:
        fail(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in job %s", job_id)
        fail(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    data         = request.get_json(force=True)
    url          = (data.get("url")     or "").strip()
    api_key      = (data.get("api_key") or "").strip()
    generate_pdf = bool(data.get("generate_pdf", True))

    if not url or not api_key:
        return jsonify({"error": "url and api_key are required"}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status":   "running",
        "progress": 0,
        "message":  "Starting…",
        "out_dir":  None,
        "files":    {},
        "error":    None,
    }

    threading.Thread(
        target=run_job,
        args=(job_id, url, api_key, generate_pdf),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    return jsonify({
        "status":   job["status"],
        "progress": job["progress"],
        "message":  job.get("message", ""),
        "error":    job.get("error"),
        "files":    {k: bool(v) for k, v in job.get("files", {}).items()},
    })


@app.route("/api/download/<job_id>/<file_type>")
def download(job_id: str, file_type: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404

    path_str = job.get("files", {}).get(file_type)
    if not path_str:
        return jsonify({"error": "File not available"}), 404

    path = Path(path_str)
    if not path.exists():
        return jsonify({"error": "File missing on disk"}), 404

    mime_map = {
        "transcript": "text/plain",
        "latex":      "text/x-tex",
        "pdf":        "application/pdf",
    }
    return send_file(
        path,
        mimetype=mime_map.get(file_type, "application/octet-stream"),
        as_attachment=True,
        download_name=path.name,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)