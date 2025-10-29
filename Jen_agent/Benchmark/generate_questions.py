import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os
from tqdm import tqdm

from models.google.client import GoogleProvider


SOURCE_FILES_DIR = Path("./benchmark_data/source_files")
OUTPUT_FILE = Path("./benchmark_data/questions.json")
QUESTION_GENERATOR_MODEL = "gemini-pro-latest"

PROMPT_TEMPLATE = """
You are an expert in creating evaluation questions for a Retrieval-Augmented Generation (RAG) system.
Your task is to read the following document about Jenkins and generate a single, high-quality question.

**CRITICAL INSTRUCTIONS:**
1.  The question MUST be answerable **only** from the information within the provided document text.
2.  The question should be complex and require reasoning or the extraction of specific, detailed information. It should NOT be a generic question that could be answered by general knowledge.
3.  Do NOT ask for a summary of the document.
4.  The question should be phrased as if a user is asking for help or information.
5.  Good examples include questions that ask "how to achieve a specific outcome...", "what is the purpose of the following configuration...", or "explain the steps to resolve a particular error mentioned...".

---DOCUMENT TEXT---
{context_text}
---END DOCUMENT TEXT---

Based on the text, generate only the question. Do not add any preamble.
QUESTION:
"""


async def main():
    print("--- Starting Benchmark Question Generation ---")
    load_dotenv()

    if not os.getenv("GOOGLE_API_KEY"):
        print("\n[ERROR] GOOGLE_API_KEY not found in .env file.")
        exit(1)

    try:
        provider = GoogleProvider()
        llm_func = provider.get_llm_model_func(model_id=QUESTION_GENERATOR_MODEL)
    except Exception as e:
        print(f"Failed to initialize Google Provider: {e}")
        exit(1)

    source_files = sorted(list(SOURCE_FILES_DIR.glob("*.txt")))
    if not source_files:
        print(f"[ERROR] No source files found in '{SOURCE_FILES_DIR}'.")
        exit(1)

    print(f"Found {len(source_files)} source documents to generate questions from.")

    benchmark_questions = []

    for i, file_path in enumerate(tqdm(source_files, desc="Generating Questions")):
        try:
            ground_truth_context = file_path.read_text(encoding="utf-8")
            prompt = PROMPT_TEMPLATE.format(context_text=ground_truth_context)
            generated_question = await llm_func(prompt=prompt)
            cleaned_question = generated_question.strip().replace("QUESTION:", "").strip()

            benchmark_item = {
                "question_id": f"doc_{i + 1:02d}",
                "source_file": str(file_path),
                "question": cleaned_question,
                "ground_truth_context": ground_truth_context,
            }
            benchmark_questions.append(benchmark_item)

        except Exception as e:
            print(f"\nWarning: Failed to generate question for {file_path.name}. Error: {e}")

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(benchmark_questions, f, indent=2)

    print(f"\n✅ Question generation complete!")
    print(f"Saved {len(benchmark_questions)} questions to: '{OUTPUT_FILE}'")


if __name__ == "__main__":
    asyncio.run(main())
