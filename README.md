# YT Lecture Notes Generator

Command-line tool that downloads YouTube lecture transcripts, refines them with Gemini AI, classifies the subject, and generates subject-specific LaTeX lecture notes (with optional PDF compilation).

## Features

- Fetches full transcript using YouTube Transcript API
- Cleans & refines spoken transcript into structured text
- Automatically detects lecture subject (Math, Physics, Programming, Chemistry, ML, General...)
- Generates professional LaTeX notes tailored to each subject
- Compiles LaTeX → PDF 
- Creates separate folder per video (named by video ID)

## Usage
```bash
# Generate LaTeX + PDF lecture notes from a YouTube video
python main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -k YOUR_API_KEY

# Specify a custom output directory
python main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -k YOUR_API_KEY -o ./my_notes

# Generate only LaTeX (skip PDF)
python main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -k YOUR_API_KEY --no-pdf

# Show progress messages (verbose)
python main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -k YOUR_API_KEY -v

# Show detailed debug output
python main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -k YOUR_API_KEY --debug
