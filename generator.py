from youtube_transcript_api import YouTubeTranscriptApi
import re
from google import genai
from google.genai import types
import subprocess
import os
from pathlib import Path

def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats"""
    import re
    patterns = [
        r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'/embed/([a-zA-Z0-9_-]{11})',
        r'/v/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_youtube_transcript(youtube_url: str, api_key: str) -> str:
    video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", youtube_url)
    if not video_id_match:
        return "Invalid YouTube URL"
    
    video_id = video_id_match.group(1)

    try:
        ytt_api = YouTubeTranscriptApi()
        fetched_transcript = ytt_api.fetch(video_id)          
        transcript_list = fetched_transcript.to_raw_data()    
        
        raw_transcript = " ".join([entry['text'] for entry in transcript_list])
        
        refined_transcript = refine_transcript_for_notes(raw_transcript, api_key)
        
        return refined_transcript

    except Exception as e:
        return f"Error fetching transcript: {str(e)} (Common causes: no captions, private video, region-restricted, subtitles disabled)"

def refine_transcript_for_notes(raw_transcript: str, api_key: str) -> str:
    client = genai.Client(api_key=api_key)
    
    model_id = 'gemini-2.5-flash' 

    refine_prompt = """
You are an expert academic editor. Your task is to take a raw transcript of a spoken lecture (from YouTube subtitles) and rewrite it into clean, concise, well-structured written prose suitable for creating high-quality lecture notes.

Follow these rules strictly:
- Remove all filler words (um, uh, you know, like, basically, right?, okay, so yeah, etc.)
- Eliminate repetitions and false starts (e.g., "let's let's begin" → "let's begin")
- Fix incomplete or run-on sentences into proper grammar
- Improve flow and logical structure: group related ideas, create natural paragraphs
- Keep all technical content, equations, examples, and explanations 100% accurate and intact
- Convert informal spoken style into clear academic written style
- Do NOT add new information or explanations — only rephrase and organize what's already said
- Do NOT summarize or shorten drastically — preserve detail and length, just make it read smoothly
- If code is mentioned, preserve it accurately
- If math/equations are spoken (e.g., "x squared plus two x plus one"), write them naturally (e.g., "x² + 2x + 1")

Output ONLY the refined transcript text. No introductions, no explanations, no markdown.

Raw transcript:
""" + raw_transcript
    
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=refine_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            )
        )
        
        if not response.text:
            print("Warning: Empty response. Falling back to raw.")
            return raw_transcript
        
        refined = response.text.strip()
    
        refined = refined.replace('```', '').strip()
        
        return refined
        
    except Exception as e:
        print(f"Refinement failed: {e}. Falling back to raw transcript.")
        return raw_transcript

def classify_transcript_subject(transcript: str, api_key: str) -> str:
    client = genai.Client(api_key=api_key)
    model_id = 'gemini-2.5-flash'

    categories = ["Math", "Programming", "Chemistry", "Physics", "MachineLearning", "General"]

    prompt = f"""Classify the main subject of this lecture into **exactly one** of these categories.
Return **ONLY** the category name — nothing else, no explanation, no quotes, no prefix.

Categories: {', '.join(categories)}

Lecture transcript (beginning):
{transcript[:3500]}

Your answer must look exactly like this example:
Physics
""".strip()

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="text/plain", 
                temperature=0.0, 
            )
        )

        text = response.text.strip()
        for cat in categories:
            if cat.lower() in text.lower():
                print(f"Detected subject: {cat}")
                return cat

        print(f"Unexpected output: {text!r} → fallback to General")
        return "General"

    except Exception as e:
        print(f"Error: {e}")
        return "General"

    except Exception as e:
        print(f"Classification failed: {e}. Falling back to General.")
        return "General"

def get_subject_prompt(subject: str) -> str:
    base_packages = "amsmath, amssymb, enumitem, hyperref, geometry"

    prompts = {
        "Math": f"""
Convert the following lecture transcript into clean, professional LaTeX lecture notes focused on mathematics.
RULES - FOLLOW EXACTLY:
- Output ONLY the LaTeX code.
- Do NOT use markdown or code blocks.
- Start directly with \\documentclass{{article}}
- End with \\end{{document}}
- Use packages: {base_packages}, mathtools, cancel, tikz (if diagrams needed)
- Use display math ($$ or \\[ \\]) for important equations, align/environment for multi-line
- Use theorem-like environments (definition, theorem, lemma, proof) via amsthm if useful
- Number equations when appropriate
- Make heavy use of proper math mode
- Structure with sections, subsections, itemize/enumerate
Transcript:
""",

        "Programming": f"""
Convert the following programming lecture transcript into clean LaTeX notes.
RULES - FOLLOW EXACTLY:
- Output ONLY the LaTeX code.
- Start directly with \\documentclass{{article}}
- End with \\end{{document}}
- Use packages: {base_packages}, listings, xcolor
- Use \\lstset for code styling (language=[language if detectable], basicstyle=\\ttfamily\\small, etc.)
- Put code snippets in lstlisting environments
- Explain concepts clearly with itemize/enumerate
- Include comments from speech as explanations
Transcript:
""",

        "Chemistry": f"""
Convert the following chemistry lecture transcript into professional LaTeX notes.
RULES - FOLLOW EXACTLY:
- Output ONLY the LaTeX code.
- Start directly with \\documentclass{{article}}
- End with \\end{{document}}
- Use packages: {base_packages}, mhchem, chemfig (for structures if mentioned)
- Use \\ce{{}} for chemical equations and formulas
- Draw reaction schemes if described
- Use tables for periodic trends, data, etc.
Transcript:
""",

        "Physics": f"""
Convert the following physics lecture transcript into clean LaTeX notes.
RULES - FOLLOW EXACTLY:
- Output ONLY the LaTeX code.
- Start directly with \\documentclass{{article}}
- End with \\end{{document}}
- Use packages: {base_packages}, siunitx, physunits, tikz (for diagrams)
- Use \\si{{}} for units, proper vector notation
- Heavy use of equations in display math
- Include diagrams if described (using tikz if possible)
Transcript:
""",

        "MachineLearning": f"""
Convert the following machine learning/AI lecture transcript into LaTeX notes.
RULES - FOLLOW EXACTLY:
- Output ONLY the LaTeX code.
- Start directly with \\documentclass{{article}}
- End with \\end{{document}}
- Use packages: {base_packages}, algorithm, algorithmicx, algpseudocode, listings
- Use math mode extensively for loss functions, gradients, etc.
- Include pseudocode in algorithm environments when explained
- Use tikz for neural network diagrams if described
Transcript:
""",

        "General": f"""
Convert the following lecture transcript into clean, structured LaTeX notes.
RULES - FOLLOW EXACTLY:
- Output ONLY the LaTeX code.
- Start directly with \\documentclass{{article}}
- End with \\end{{document}}
- Use packages: {base_packages}
- Use sections/subsections, itemize/enumerate, bold/italic
- Use math mode when equations appear ($...$ or \\[ \\])
- Be concise and well-organized
Transcript:
"""
    }

    return prompts.get(subject, prompts["General"])

def generate_latex_notes(transcript: str, api_key: str) -> str:
    client = genai.Client(api_key=api_key)
    model_id = 'gemini-2.5-flash'

    subject = classify_transcript_subject(transcript, api_key)
    
    custom_prompt = get_subject_prompt(subject)
    full_prompt = custom_prompt + transcript
    
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=full_prompt)
       
        if not response.text:
            return "Error: No response from Gemini"
       
        latex_code = response.text.strip()
       
        if "```" in latex_code:
            lines = latex_code.splitlines()
            cleaned_lines = [line for line in lines if not line.strip().startswith('```')]
            latex_code = '\n'.join(cleaned_lines).strip()
       
        return latex_code

    except Exception as e:
        return f"Error during LaTeX generation: {str(e)}"

def compile_latex_to_pdf(
    latex_code: str,
    filename: str = "lecture_notes",
    output_dir: str | Path = "."
):
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tex_file = output_dir / f"{filename}.tex"
    pdf_file = output_dir / f"{filename}.pdf"

    tex_file.write_text(latex_code, encoding="utf-8")
    try:
        original_cwd = os.getcwd()
        os.chdir(output_dir)  

        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", f"{filename}.tex"],
                check=True,
                capture_output=True,
                text=True
            )

        os.chdir(original_cwd)  

        if pdf_file.exists():
            print(f"PDF saved as: {pdf_file}")
            
            for ext in [".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"]:
                path = output_dir / f"{filename}{ext}"
                if path.exists():
                    path.unlink()
        else:
            print("PDF was not created.")

    except subprocess.CalledProcessError as e:
        print("LaTeX compilation failed!")
        print("Last error output:")
        print(e.stderr or e.stdout)
    except FileNotFoundError:
        print("pdflatex not found. Please install LaTeX (TeX Live / MiKTeX / MacTeX)")
        print("Download from: https://www.tug.org/texlive/ or https://miktex.org/")
    except Exception as e:
        print(f"Unexpected error during compilation: {e}")