# LectureForge

LectureForge is a Flask web app that turns any YouTube lecture into polished, subject-aware LaTeX notes and an optional compiled PDF. Paste a video URL and a Gemini API key, and the pipeline automatically fetches the transcript, refines it into clean prose, classifies the subject (Math, Physics, Programming, Chemistry, Machine Learning, or General), and generates professionally structured LaTeX — all downloadable from a clean browser UI.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`. A working [pdflatex](https://www.tug.org/texlive/) installation is required for PDF compilation.
