import argparse               
from pathlib import Path      
import os                      
import sys                     
import logging            
from generator import (
    extract_video_id,
    refine_transcript_for_notes,
    get_youtube_transcript,
    classify_transcript_subject,
    get_subject_prompt,
    generate_latex_notes,
    compile_latex_to_pdf,
)
        
        
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Argument parser
def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate beautiful lecture notes (LaTeX + PDF) from YouTube lectures",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""\
Examples:
  yt-lecture-notes "https://youtu.be/dQw4w9WgXcQ" -k YOUR_API_KEY_HERE
  yt-lecture-notes -u https://youtube.com/watch?v=abc123 --api-key YOUR_KEY --no-pdf
  yt-lecture-notes https://youtu.be/VIDEO_ID -o ./my_notes --debug
        """
    )

    # URL 
    parser.add_argument(
        "url", nargs="?", metavar="URL",
        help="YouTube video URL"
    )
    parser.add_argument(
        "-u", "--url", dest="url_flag",
        help="YouTube video URL (alternative to positional)"
    )

    # Required API key
    parser.add_argument(
        "-k", "--api-key", "--key",
        required=True,
        help="Your YouTube Data API v3 key (REQUIRED - no default)"
    )

    # Output control
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="where to save files (default: current directory)"
    )
    parser.add_argument(
        "--no-pdf", action="store_true",
        help="generate only .tex file (skip PDF compilation)"
    )

    # Verbosity
    parser.add_argument(
        "--quiet", action="store_true",
        help="show only errors and final file paths"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="very verbose output (for troubleshooting)"
    )

    args = parser.parse_args()

    # Resolve URL
    final_url = args.url or args.url_flag
    if not final_url:
        parser.error("You must provide a YouTube URL (either positional or --url)")

    args.url = final_url

    # Verbosity levels
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    return args


def main():
    args = parse_arguments()

    base_output = args.output_dir.resolve()

    # If user didn't specify custom folder → create one based on video ID
    if base_output == Path.cwd():
        video_id = extract_video_id(args.url)  
        if video_id:
            folder_name = f"lecture_{video_id}"
        else:
            # fallback if we can't parse ID
            from datetime import datetime
            folder_name = f"lecture_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        output_dir = base_output / folder_name
    else:
        # User specified folder
        output_dir = base_output

    output_dir.mkdir(parents=True, exist_ok=True)

    # File paths
    base_name = "lecture_notes"
    transcript_path = output_dir / "transcript.txt"
    tex_path       = output_dir / f"{base_name}.tex"
    pdf_path       = output_dir / f"{base_name}.pdf"

    try:
        print()
        logger.info("Starting YouTube Lecture Notes Generator")
        logger.debug(f"Video URL:     {args.url}")
        logger.info (f"Output folder: {output_dir}")

        # Fetch transcript
        logger.info("Fetching transcript...")
        transcript = get_youtube_transcript(args.url, args.api_key)

        if len(transcript.strip()) < 200:
            raise ValueError("Transcript is too short or empty")  # ← changed to ValueError

        logger.debug(f"Transcript length: {len(transcript):,} chars")

        transcript_path.write_text(transcript, encoding="utf-8")
        logger.info(f"Saved raw transcript → {transcript_path}")

        # Generate LaTeX notes
        logger.info("Generating formatted lecture notes...")
        latex_content = generate_latex_notes(transcript, args.api_key)

        tex_path.write_text(latex_content, encoding="utf-8")
        logger.info(f"LaTeX file created → {tex_path}")

        # Compile PDF 
        if not args.no_pdf:
            logger.info("Compiling PDF (this may take a few seconds)...")

            # Important: change to the target directory before compilation
            original_cwd = os.getcwd()
            try:
                os.chdir(output_dir)
                compile_latex_to_pdf(latex_content, base_name) 
            finally:
                os.chdir(original_cwd)  

            if pdf_path.is_file():
                logger.info(f"PDF successfully created → {pdf_path}")
            else:
                logger.warning("PDF compilation finished but output file not found")

        print("\n" + "═" * 72)
        print("               FINISHED SUCCESSFULLY                  ".center(72))
        print("═" * 72)
        print(f"  Folder:       {output_dir}")
        print(f"  Transcript:   {transcript_path.name}")
        print(f"  LaTeX source: {tex_path.name}")
        if pdf_path.is_file():
            print(f"  Final PDF:    {pdf_path.name}")
        print("═" * 72 + "\n")

    except Exception as e:  
        logger.exception("Error occurred:")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n\nInterrupted. Exiting...\n")
        sys.exit(130)


if __name__ == "__main__":
    main()