# LectureForge

LectureForge is a Flask web app that turns any YouTube lecture into polished, subject-aware LaTeX notes and an optional compiled PDF. Paste a video URL and a Gemini API key, and the pipeline automatically fetches the transcript, refines it into clean prose, classifies the subject (Math, Physics, Programming, Chemistry, Machine Learning, or General), and generates professionally structured LaTeX — all downloadable from a clean browser UI.

## Setup

```bash
<<<<<<< HEAD
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`. A working [pdflatex](https://www.tug.org/texlive/) installation is required for PDF compilation.
=======
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
>>>>>>> dbd2f6cc556af28c219da79b6b62d40611bd839c
