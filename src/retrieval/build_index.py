"""Build ChromaDB vector index from cleaned medical Q&A data.

Usage:
    python -m src.retrieval.build_index
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import get_settings
from src.retrieval.embedding_service import EmbeddingService
from src.retrieval.vector_store import VectorStore
import pandas as pd


def main():
    settings = get_settings()
    cleaned_path = Path(settings.processed_data_dir) / "sample_cleaned.csv"

    if not cleaned_path.exists():
        print(f"Cleaned data not found at {cleaned_path}")
        print("Run src/kg/build_graph.py first to generate cleaned data.")
        return

    df = pd.read_csv(cleaned_path, encoding="utf-8-sig")
    print(f"Loaded {len(df)} cleaned records")

    print("Loading embedding model...")
    emb_service = EmbeddingService()
    print(f"  Model loaded, dimension={emb_service.dimension}")

    # Create a combined search text: title + ask (more similar to user queries than answer)
    df["search_text"] = df["title"].astype(str) + " " + df["ask"].astype(str)

    print("Building vector index...")
    store = VectorStore(emb_service)
    store.ingest_dataframe(df, text_col="search_text")
    print(f"Index built. {store.count()} documents in ChromaDB.")

    # Quick verification
    print("\nVerification query: '高血压怎么治疗'")
    results = store.search("高血压怎么治疗", k=3)
    for i, r in enumerate(results):
        print(f"  [{i+1}] distance={r['distance']:.4f} | {r['metadata'].get('title', '')}")


if __name__ == "__main__":
    main()
