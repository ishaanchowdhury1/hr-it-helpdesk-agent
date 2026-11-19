"""
RAG over the company policy documents.

- Splits each Markdown policy in data/policies/ into one chunk per "## " section.
- Stores the chunks in a local ChromaDB vector database (folder: chroma_db/).
- search() returns the best matching sections with their source file and section
  name, so the agent can cite where every answer came from.

Embeddings: ChromaDB's built-in all-MiniLM-L6-v2 (runs locally, no API key needed).

Build or rebuild the index:  python rag.py --rebuild
Try a search:                python rag.py "how many sick days do I get"
"""

import hashlib
import re
import sys
from pathlib import Path

import chromadb

BASE_DIR = Path(__file__).resolve().parent
POLICY_DIR = BASE_DIR / "data" / "policies"
DB_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "hr_it_policies"

# Cosine distance: 0 = identical, 2 = opposite. Chunks further away than this
# are treated as "not relevant", which lets the agent say "I don't know".
MAX_DISTANCE = 0.65


def _split_markdown(path: Path) -> list[dict]:
    """Split one policy file into chunks, one per '## ' section."""
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^# (.+)$", text, flags=re.MULTILINE)
    doc_title = title_match.group(1).strip() if title_match else path.stem

    chunks = []
    for part in re.split(r"(?m)^## ", text)[1:]:
        heading, _, body = part.partition("\n")
        heading, body = heading.strip(), body.strip()
        if not body:
            continue
        chunks.append(
            {
                # Put the title and heading into the text so the embedding knows the context
                "text": f"{doc_title} - {heading}\n{body}",
                "source": path.name,
                "document": doc_title,
                "section": heading,
            }
        )
    return chunks


def _policy_fingerprint() -> str:
    """Hash of all policy files, so the index rebuilds itself when a policy changes."""
    h = hashlib.sha256()
    for path in sorted(POLICY_DIR.glob("*.md")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def get_collection(rebuild: bool = False):
    """Return the Chroma collection, building it if it is missing or out of date."""
    client = chromadb.PersistentClient(path=str(DB_DIR))
    fingerprint = _policy_fingerprint()

    if not rebuild:
        try:
            collection = client.get_collection(COLLECTION_NAME)
            if (collection.metadata or {}).get("fingerprint") == fingerprint:
                return collection
        except Exception:
            pass  # collection does not exist yet

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "fingerprint": fingerprint},
    )

    chunks = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        chunks.extend(_split_markdown(path))

    collection.add(
        ids=[f"{c['source']}::{i}" for i, c in enumerate(chunks)],
        documents=[c["text"] for c in chunks],
        metadatas=[
            {"source": c["source"], "document": c["document"], "section": c["section"]}
            for c in chunks
        ],
    )
    print(f"[rag] Indexed {len(chunks)} sections from {POLICY_DIR}", file=sys.stderr)
    return collection


def search(query: str, k: int = 3) -> list[dict]:
    """Return up to k relevant policy sections for the query.

    Each result: {"text", "source", "document", "section", "distance"}.
    Returns an empty list if nothing is close enough to the question.
    """
    collection = get_collection()
    res = collection.query(query_texts=[query], n_results=k)

    results = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        if dist <= MAX_DISTANCE:
            results.append({"text": text, **meta, "distance": round(dist, 3)})
    return results


def format_results(results: list[dict]) -> str:
    """Turn search results into a text block the LLM can read and cite."""
    if not results:
        return "NO_RELEVANT_POLICY_FOUND"
    blocks = []
    for r in results:
        blocks.append(f"[Source: {r['source']} > {r['section']}]\n{r['text']}")
    return "\n\n".join(blocks)


if __name__ == "__main__":
    if "--rebuild" in sys.argv:
        get_collection(rebuild=True)
        sys.argv.remove("--rebuild")
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        results = search(question)
        for r in results:
            print(f"{r['distance']:.3f}  {r['source']} > {r['section']}")
        if not results:
            print("No relevant policy found.")
