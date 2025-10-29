import git
import random
from pathlib import Path
import re
import os

REPO_URL = "https://github.com/jenkinsci/jenkins.io.git"
LOCAL_REPO_PATH = Path("./jenkins_docs_repo")
OUTPUT_DIR = Path("./benchmark_data/source_files")
NUM_FILES_TO_SELECT = 19

MIN_FILE_SIZE_KB = 5

PREFERRED_DIRECTORIES = [
    "_docs/user",
    "_docs/developer",
    "_docs/book",
    "blog/_posts",
    "solutions",
]

ADOC_HEADER_RE = re.compile(r"^(?:= .*|:.*:.*)\n", re.MULTILINE)

def parse_adoc_file(file_path: Path) -> str:
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    cleaned_content = ADOC_HEADER_RE.sub("", content)
    parts = cleaned_content.split("\n\n", 1)
    return parts[1] if len(parts) > 1 else cleaned_content

def main():
    if not LOCAL_REPO_PATH.exists():
        git.Repo.clone_from(REPO_URL, LOCAL_REPO_PATH, branch="master", depth=1)

    all_adoc_files = list(LOCAL_REPO_PATH.rglob("*.adoc"))
    candidate_files = [
        p for p in all_adoc_files if (p.stat().st_size / 1024) > MIN_FILE_SIZE_KB
    ]

    preferred_files = []
    other_files = []
    for f in candidate_files:
        if any(preferred_dir in str(f) for preferred_dir in PREFERRED_DIRECTORIES):
            preferred_files.append(f)
        else:
            other_files.append(f)

    selected_files = []
    num_from_preferred = min(len(preferred_files), int(NUM_FILES_TO_SELECT * 0.8))
    selected_files.extend(random.sample(preferred_files, num_from_preferred))

    remaining_needed = NUM_FILES_TO_SELECT - len(selected_files)
    if remaining_needed > 0 and other_files:
        num_from_other = min(len(other_files), remaining_needed)
        selected_files.extend(random.sample(other_files, num_from_other))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUTPUT_DIR.glob('*'):
        os.remove(f)

    for i, file_path in enumerate(selected_files):
        try:
            cleaned_content = parse_adoc_file(file_path)
            output_filename = f"doc_{i + 1:02d}_{file_path.name.replace('.adoc', '.txt')}"
            (OUTPUT_DIR / output_filename).write_text(cleaned_content, encoding="utf-8")
        except:
            pass

if __name__ == "__main__":
    main()
