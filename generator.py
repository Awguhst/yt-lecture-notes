from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path

from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GEMINI_MODEL = "gemini-2.5-flash"

_SUBJECTS = ["Math", "Programming", "Chemistry", "Physics", "MachineLearning", "General"]

_BASE_LATEX_RULES = """\
RULES — FOLLOW EXACTLY:
- Output ONLY valid LaTeX source code. No markdown, no code fences, no commentary.
- Start the very first line with \\documentclass{article}.
- End the very last line with \\end{document}.
- Use packages: amsmath, amssymb, enumitem, hyperref, geometry"""

_SUBJECT_EXTRA: dict[str, str] = {
    "Math": """\
, mathtools, amsthm
- Use display math (\\[ \\] or align) for important equations; number them when useful.
- Define theorem-like environments (definition, theorem, lemma, proof) via amsthm.
- Heavy use of proper math mode throughout.""",

    "Programming": """\
, listings, xcolor
- Configure \\lstset with sensible defaults (ttfamily, small, auto-detect language).
- Wrap every code snippet in a lstlisting environment.
- Explain code behaviour with itemize/enumerate.""",

    "Chemistry": """\
, mhchem, chemfig
- Use \\ce{} for all chemical formulas and equations.
- Draw reaction schemes when described.
- Use tables for periodic trends or experimental data.""",

    "Physics": """\
, siunitx, tikz
- Use \\SI{}{} for all quantities with units.
- Use proper vector notation (\\vec, \\hat).
- Include tikz diagrams when the lecture describes a diagram.""",

    "MachineLearning": """\
, algorithm, algpseudocode, listings
- Use math mode for loss functions, gradients, and model equations.
- Wrap described algorithms in algorithm + algorithmic environments.
- Use tikz for neural-network diagrams when described.""",

    "General": "",   # base rules are sufficient
}


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def make_client(api_key: str) -> genai.Client:
    """Return a configured Gemini client.  Create once per job and pass around."""
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Stage 1 — fetch transcript
# ---------------------------------------------------------------------------

def get_youtube_transcript(url: str) -> str:
    """Fetch the raw transcript from YouTube.

    Returns:
        Raw joined transcript string.

    Raises:
        ValueError: if the URL is invalid or has no captions.
        RuntimeError: if the API call fails for any other reason.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract a video ID from URL: {url!r}")

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        entries = fetched.to_raw_data()
        raw = " ".join(e["text"] for e in entries).strip()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch transcript for video '{video_id}': {exc}\n"
            "Common causes: no captions, private video, region-restricted, subtitles disabled."
        ) from exc

    if len(raw) < 200:
        raise ValueError(
            "Transcript is too short (< 200 characters). "
            "The video may have no meaningful captions."
        )

    logger.info("Fetched raw transcript (%d chars).", len(raw))
    return raw


# ---------------------------------------------------------------------------
# Stage 2 — refine transcript
# ---------------------------------------------------------------------------

def refine_transcript(raw: str, client: genai.Client) -> str:
    """Turn raw subtitle text into clean academic prose.

    Raises:
        RuntimeError: if the Gemini call fails.
    """
    prompt = (
        "You are an expert academic editor. Rewrite the raw lecture transcript below "
        "into clean, well-structured written prose suitable for high-quality lecture notes.\n\n"
        "Rules:\n"
        "- Remove filler words (um, uh, you know, like, basically, right?, okay, so yeah…)\n"
        "- Eliminate repetitions and false starts\n"
        "- Fix incomplete or run-on sentences\n"
        "- Group related ideas into natural paragraphs\n"
        "- Preserve ALL technical content, equations, and examples exactly\n"
        "- Convert spoken math (\"x squared plus two x\") to symbols (x² + 2x)\n"
        "- Do NOT add new information; do NOT summarise or shorten significantly\n"
        "- Output ONLY the refined transcript text — no headings, no markdown\n\n"
        f"Raw transcript:\n{raw}"
    )

    response = _call_gemini(client, prompt, temperature=0.3)
    refined = _strip_fences(response)

    if not refined:
        logger.warning("Refinement returned empty text; falling back to raw transcript.")
        return raw

    logger.info("Refined transcript (%d → %d chars).", len(raw), len(refined))
    return refined


# ---------------------------------------------------------------------------
# Stage 3 — generate LaTeX
# ---------------------------------------------------------------------------

def generate_latex(transcript: str, client: genai.Client) -> str:
    """Classify the transcript subject and generate subject-appropriate LaTeX.

    Raises:
        RuntimeError: if the Gemini call fails or returns empty content.
    """
    subject = _classify_subject(transcript, client)
    logger.info("Detected subject: %s", subject)

    prompt = _build_latex_prompt(subject, transcript)
    raw_latex = _call_gemini(client, prompt)
    latex = _strip_fences(raw_latex)

    if not latex or "\\documentclass" not in latex:
        raise RuntimeError(
            "Gemini did not return valid LaTeX. "
            f"Response preview: {raw_latex[:300]!r}"
        )

    logger.info("Generated LaTeX (%d chars).", len(latex))
    return latex


# ---------------------------------------------------------------------------
# Stage 4 — compile PDF
# ---------------------------------------------------------------------------

def compile_pdf(
    latex: str,
    filename: str = "lecture_notes",
    output_dir: str | Path = ".",
) -> Path:
    """Compile a LaTeX string to PDF using pdflatex (two passes).

    Args:
        latex:      Full LaTeX source.
        filename:   Base name (without extension) for output files.
        output_dir: Directory in which to write all files.

    Returns:
        Path to the produced PDF.

    Raises:
        FileNotFoundError: if pdflatex is not installed.
        RuntimeError:      if compilation fails (includes log tail for debugging).
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tex_file = output_dir / f"{filename}.tex"
    pdf_file = output_dir / f"{filename}.pdf"
    log_file = output_dir / f"{filename}.log"

    tex_file.write_text(latex, encoding="utf-8")
    logger.info("Wrote %s.", tex_file)

    original_cwd = os.getcwd()
    try:
        os.chdir(output_dir)
        _run_pdflatex(filename)   # pass 1 — build structure
        _run_pdflatex(filename)   # pass 2 — resolve cross-references
    except subprocess.CalledProcessError as exc:
        log_tail = _read_log_tail(log_file)
        raise RuntimeError(
            f"pdflatex failed on pass:\n{log_tail}"
        ) from exc
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "pdflatex not found. Install TeX Live (https://www.tug.org/texlive/) "
            "or MiKTeX (https://miktex.org/)."
        ) from exc
    finally:
        os.chdir(original_cwd)

    if not pdf_file.exists():
        log_tail = _read_log_tail(log_file)
        raise RuntimeError(f"pdflatex ran but produced no PDF.\n{log_tail}")

    _remove_aux_files(output_dir, filename)
    logger.info("PDF ready: %s", pdf_file)
    return pdf_file


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"/embed/([a-zA-Z0-9_-]{11})",
        r"/v/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _call_gemini(
    client: genai.Client,
    prompt: str,
    temperature: float = 1.0,
) -> str:
    """Thin wrapper around Gemini generate_content with unified error handling."""
    try:
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature),
        )
    except Exception as exc:
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    return response.text.strip()


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that the model sometimes wraps output in."""
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
    return "\n".join(lines).strip()


def _classify_subject(transcript: str, client: genai.Client) -> str:
    """Return the best-matching subject category for the transcript."""
    # Only the opening portion is needed for classification.
    sample = transcript[:3500]
    prompt = (
        f"Classify the main subject of this lecture into exactly one of these categories:\n"
        f"{', '.join(_SUBJECTS)}\n\n"
        "Return ONLY the category name — no explanation, no quotes, nothing else.\n\n"
        f"Lecture transcript (opening):\n{sample}"
    )

    try:
        answer = _call_gemini(client, prompt, temperature=0.0)
    except RuntimeError:
        logger.warning("Subject classification failed; defaulting to General.")
        return "General"

    for subject in _SUBJECTS:
        if subject.lower() in answer.lower():
            return subject

    logger.warning("Unexpected classification output %r; defaulting to General.", answer)
    return "General"


def _build_latex_prompt(subject: str, transcript: str) -> str:
    extra = _SUBJECT_EXTRA.get(subject, "")
    package_line = _BASE_LATEX_RULES + extra
    return (
        f"Convert the following {subject} lecture transcript into professional LaTeX notes.\n\n"
        f"{package_line}\n"
        "- Use sections/subsections and itemize/enumerate for structure.\n\n"
        f"Transcript:\n{transcript}"
    )


def _run_pdflatex(filename: str) -> None:
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", f"{filename}.tex"],
        check=True,
        capture_output=True,
        text=True,
    )


def _read_log_tail(log_file: Path, lines: int = 40) -> str:
    """Return the last `lines` lines of the pdflatex log, or a placeholder."""
    if not log_file.exists():
        return "(no log file found)"
    text = log_file.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def _remove_aux_files(directory: Path, stem: str) -> None:
    for ext in (".aux", ".out", ".toc", ".fls", ".fdb_latexmk"):
        f = directory / f"{stem}{ext}"
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass  # non-fatal — leave the file in place