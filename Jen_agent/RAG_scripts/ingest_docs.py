import asyncio
import json
import re
import signal
import shutil
from pathlib import Path
from typing import List, Set, Tuple
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import git
from tqdm import tqdm
from tempfile import NamedTemporaryFile
from tools.knowledge_base import CoreLightRAGManager
from models.google.client import GoogleProvider

load_dotenv()

CONFIG = {
    "repo_url": "https://github.com/jenkinsci/jenkins.io.git",
    "local_repo_path": Path("./jenkins_docs_repo"),
    "rag_dir": Path("./agent_workspace/knowledge_base/"),
    "provider_name": "google",
    "embedding_model_id": "text-embedding-004",
    "llm_model_id": "gemini-2.0-flash",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "batch_size": 4,
    "max_concurrent_inserts": 4,
    "valid_extensions": {".adoc", ".md", ".txt"},
    "checkpoint_file": "processed_files.log",
    "metadata_file": "metadata.json",
}

stop_requested = False


def handle_sigint(sig, frame):
    global stop_requested
    print("\n🛑 Stop signal received — finishing current batch gracefully...")
    stop_requested = True


signal.signal(signal.SIGINT, handle_sigint)
ADOC_HEADER_RE = re.compile(r"^(?:= .*|:.*:.*)\n", re.MULTILINE)


def clone_repo():
    if CONFIG["local_repo_path"].exists():
        print(f"Repository already exists at '{CONFIG['local_repo_path']}'. Skipping clone.")
    else:
        print(f"Cloning repository from '{CONFIG['repo_url']}'...")
        try:
            git.Repo.clone_from(CONFIG["repo_url"], CONFIG["local_repo_path"], branch="master", depth=1)
            print("Repository cloned successfully.")
        except Exception as e:
            print(f"Error cloning repository: {e}")
            import sys
            sys.exit(1)


def load_checkpoints() -> Set[str]:
    path = CONFIG["rag_dir"] / CONFIG["checkpoint_file"]
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)


def safe_write_checkpoint(processed_set: Set[str]):
    path = CONFIG["rag_dir"] / CONFIG["checkpoint_file"]
    tmp_path = None
    try:
        with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=path.parent) as tmp:
            tmp_path = tmp.name
            sorted_lines = sorted(list(processed_set))
            tmp.write("\n".join(sorted_lines) + "\n")
        shutil.move(tmp_path, path)
    except Exception as e:
        print(f"Error writing checkpoint: {e}")
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def read_file(fp: Path) -> str:
    try:
        text = await asyncio.to_thread(fp.read_text, encoding="utf-8", errors="ignore")
        if fp.suffix.lower() == ".adoc":
            cleaned = ADOC_HEADER_RE.sub("", text)
            parts = cleaned.split("\n\n", 1)
            return parts[1] if len(parts) > 1 else cleaned
        return text
    except Exception as e:
        print(f"[{fp.name}] read error: {e}")
        return ""


def get_all_valid_files() -> List[Path]:
    return [
        p
        for p in CONFIG["local_repo_path"].rglob("*")
        if p.is_file() and p.suffix.lower() in CONFIG["valid_extensions"]
    ]


async def process_batch(rag_manager, batch: List[Tuple[str, str]], processed_set: Set[str], pbar):
    contents = [item[0] for item in batch]
    doc_ids = [item[1] for item in batch]

    try:
        await rag_manager.rag_instance.ainsert(input=contents, ids=doc_ids)
        for doc_id in doc_ids:
            processed_set.add(doc_id)
        pbar.update(len(batch))
        return True
    except Exception as e:
        print(f"Error inserting batch of {len(batch)} documents: {e}")
        pbar.update(len(batch))
        return False


async def main():
    print("\n--- Starting Jenkins Docs Ingestion ---")
    print(f"Embedding: {CONFIG['embedding_model_id']} | LLM: {CONFIG['llm_model_id']}")
    print(f"Output Dir: {CONFIG['rag_dir']}\n")

    CONFIG["rag_dir"].mkdir(parents=True, exist_ok=True)
    clone_repo()

    processed_set = load_checkpoints()
    all_files = get_all_valid_files()
    files_to_process = [
        f for f in all_files if str(f.relative_to(CONFIG["local_repo_path"])) not in processed_set
    ]

    if not files_to_process:
        print("✅ Knowledge base already up-to-date.")
        return

    print(
        f"Found {len(all_files)} total files. "
        f"{len(processed_set)} processed. "
        f"Processing {len(files_to_process)} new files.\n"
    )

    try:
        llm_provider = GoogleProvider(api_key=os.getenv("GOOGLE_API_KEY"))
        embedding_func = llm_provider.get_embedding_function(model_id=CONFIG["embedding_model_id"])
        llm_func = llm_provider.get_llm_model_func(model_id=CONFIG["llm_model_id"])


    except Exception as e:
        print(f"Failed to initialize providers: {e}")
        return
    try :
        rag_manager = CoreLightRAGManager(
            working_dir=str(CONFIG["rag_dir"]),
            embedding_func=embedding_func,
            llm_func=llm_func,
        )
        await rag_manager.initialize()
    except Exception as e:
        raise e

    pbar = tqdm(total=len(files_to_process), desc="Ingesting Documents")

    batch = []
    for fp in files_to_process:
        if stop_requested:
            print("\n🛑 Graceful stop requested. Exiting loop...")
            break

        content = await read_file(fp)
        if not content.strip():
            pbar.update(1)
            continue

        doc_id = str(fp.relative_to(CONFIG["local_repo_path"]))
        batch.append((content, doc_id))

        if len(batch) >= CONFIG["batch_size"]:
            success = await process_batch(rag_manager, batch, processed_set, pbar)
            if success:
                safe_write_checkpoint(processed_set)
            batch = []

    if batch and not stop_requested:
        print(f"\nProcessing the final batch of {len(batch)} documents...")
        success = await process_batch(rag_manager, batch, processed_set, pbar)
        if success:
            safe_write_checkpoint(processed_set)

    pbar.close()

    metadata = {
        "embedding_provider": CONFIG["provider_name"],
        "embedding_model_id": CONFIG["embedding_model_id"],
        "llm_model_id": CONFIG["llm_model_id"],
        "last_updated_utc": datetime.now(timezone.utc).isoformat(),
        "total_documents_processed": len(processed_set),
        "chunk_size": CONFIG["chunk_size"],
        "chunk_overlap": CONFIG["chunk_overlap"],
    }

    with open(CONFIG["rag_dir"] / CONFIG["metadata_file"], "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\n✅ Ingestion complete (or safely stopped).")
    print(f"Vector store: {CONFIG['rag_dir']}")
    print(f"Metadata:     {CONFIG['rag_dir'] / CONFIG['metadata_file']}")


if __name__ == "__main__":
    asyncio.run(main())
