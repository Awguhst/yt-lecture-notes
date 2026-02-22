import argparse
from pathlib import Path
import os
import sys
import logging
from datetime import datetime

from generator import (
    extract_video_id,
    get_youtube_transcript,
    generate_latex_notes,
    compile_latex_to_pdf,
)

logging.basicConfig(level=logging.ERROR, format="%(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

for noisy in ("httpx", "urllib3", "google"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="yt-lecture-notes",
        description="Generate LaTeX + PDF lecture notes from YouTube video",
        add_help=True,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("-k", "--api-key", required=True, help="API key")

    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="output directory"
    )
    parser.add_argument("--no-pdf", action="store_true", help="skip PDF creation")

    log = parser.add_mutually_exclusive_group()
    log.add_argument("-v", "--verbose", action="store_true", help="show progress")
    log.add_argument("--debug",   action="store_true", help="show debug output")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    return args


def determine_output_dir(base_dir: Path, url: str) -> Path:
    base_dir = base_dir.resolve()
    if base_dir != Path.cwd():
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    video_id = extract_video_id(url)
    name = f"lecture_{video_id}" if video_id else f"lecture_{datetime.now():%Y%m%d_%H%M%S}"
    out = base_dir / name
    out.mkdir(parents=True, exist_ok=True)
    return out


def main() -> None:
    args = parse_arguments()
    out_dir = determine_output_dir(args.output_dir, args.url)

    transcript_path = out_dir / "transcript.txt"
    tex_path       = out_dir / "lecture_notes.tex"
    pdf_path       = out_dir / "lecture_notes.pdf"

    try:
        logger.info(f"Output → {out_dir}")

        logger.info("Fetching transcript...")
        transcript = get_youtube_transcript(args.url, args.api_key)
        transcript_path.write_text(transcript, encoding="utf-8")

        if len(transcript.strip()) < 200:
            raise ValueError("Transcript too short / empty")

        logger.info("Generating LaTeX...")
        latex = generate_latex_notes(transcript, args.api_key)
        tex_path.write_text(latex, encoding="utf-8")

        if not args.no_pdf:
            logger.info("Compiling PDF...")
            original_cwd = os.getcwd()
            try:
                os.chdir(out_dir)
                compile_latex_to_pdf(latex, "lecture_notes")
            finally:
                os.chdir(original_cwd)

        pdf_status = pdf_path.name if pdf_path.exists() and not args.no_pdf else "—"

        print("\n" + "=" * 42)
        print("LECTURE NOTES READY")
        print("-" * 42)
        print(f"Folder     : {out_dir.name}")
        print(f"Transcript : {transcript_path.name}")
        print(f"LaTeX      : {tex_path.name}")
        print(f"PDF        : {pdf_status}")
        print("=" * 42 + "\n")

    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()