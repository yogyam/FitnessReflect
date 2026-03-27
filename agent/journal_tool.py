import subprocess
from pathlib import Path

def log_daily_reflection(date: str, steps: int, calories: int, protein: int, notes: str) -> str:
    """
    Appends the user's daily reflection to the RAG markdown log, then completely 
    re-generates the PDF and re-ingests it into the vector database live!
    """
    log_file = Path("data/fitness-log.md")
    
    # Append the new entry
    new_entry = f"\n## Day X - {date}\nSteps: {steps}. Calories: {calories} kcal. Protein: {protein}g. Reflection: {notes}\n"
    
    with log_file.open("a", encoding="utf-8") as f:
        f.write(new_entry)
        
    # Rebuild the PDF and Vector embeddings using the existing scripts
    try:
        subprocess.run(["python3", "scripts/generate_pdf.py", "data/fitness-log.md", "data/fitness-log.pdf"], check=True)
        subprocess.run(["python3", "scripts/ingest_pdf.py", "data/fitness-log.pdf"], check=True)
        return f"Successfully logged {date} to the fitness journal and updated the RAG vectorstore!"
    except subprocess.CalledProcessError as e:
        return f"Failed to dynamically re-ingest the PDF into the RAG system: {e}"
