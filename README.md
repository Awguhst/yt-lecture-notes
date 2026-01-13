# YT Lecture Notes Generator

Command-line tool that downloads YouTube lecture transcripts, refines them with Gemini AI, classifies the subject, and generates beautiful, subject-specific LaTeX lecture notes (with optional PDF compilation).

## Features

- Fetches full transcript using YouTube Transcript API
- Cleans & refines spoken transcript into proper written prose (Gemini 2.5 Flash)
- Automatically detects lecture subject (Math, Physics, Programming, Chemistry, ML, General...)
- Generates professional LaTeX notes tailored to each subject
- Compiles LaTeX → PDF (using pdflatex)
- Creates separate folder per video (named by video ID)

## Usage
python cli.py --help

### Most common usage:
python cli.py VIDEO_URL -k YOUR_API_KEY

### Useful flags:
  -k, --api-key       Your Gemini API key (required)
  -o, --output-dir    Custom output directory (default: creates lecture_{video_id}/)
      --no-pdf        Generate only .tex file (skip PDF compilation)
      --quiet         Show only final paths and errors
      --debug         Very verbose output
