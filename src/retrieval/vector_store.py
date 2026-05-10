import uuid
import re
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from ..config import get_settings


class VectorStore:
    """ChromaDB-backed vector store for medical Q&A text chunks."""

    def __init__(self, embedding_service):
        settings = get_settings()
        self.embedding_service = embedding_service
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def ingest_dataframe(self, df, text_col: str = "answer", title_col: str = "title",
                         dept_col: str = "department") -> int:
        """Ingest cleaned DataFrame into ChromaDB. Returns count of added docs."""
        texts = df[text_col].astype(str).tolist()
        titles = df[title_col].astype(str).tolist() if title_col in df.columns else [""] * len(texts)
        depts = df[dept_col].astype(str).tolist() if dept_col in df.columns else [""] * len(texts)

        ids = [str(uuid.uuid4()) for _ in texts]
        embeddings = []

        batch_size = 64
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            emb = self.embedding_service.embed(batch)
            embeddings.extend(emb.tolist())

        metadatas = [
            {"title": t, "department": d, "text_preview": txt[:200]}
            for t, d, txt in zip(titles, depts, texts)
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        print(f"  VectorStore: ingested {len(ids)} documents")
        return len(ids)

    def search(self, query: str, k: int = 5,
               department_filter: Optional[str] = None) -> List[Dict]:
        """Cosine similarity Top-K search with optional department filter."""
        query_embedding = self.embedding_service.embed_query(query).tolist()
        where_filter = None
        if department_filter:
            where_filter = {"department": department_filter}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                docs.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })
        return docs

    def search_with_rerank(self, query: str, k: int = 5, fetch_k: int = 30,
                           department_filter: Optional[str] = None) -> List[Dict]:
        """Search with keyword-based reranking for better Chinese relevance.

        Fetches fetch_k candidates from vector search, then re-ranks by keyword
        overlap with heavy title boost (titles contain disease names).
        """
        candidates = self.search(query, k=fetch_k, department_filter=department_filter)
        query_keywords = set(re.findall(r'[一-鿿]{2,}', query))
        if not query_keywords:
            return candidates[:k]

        for doc in candidates:
            text = doc.get("text", "")
            meta = doc.get("metadata", {})
            title = meta.get("title", "")

            # Title match: each keyword hit in title = strong relevance signal
            title_hits = sum(1 for kw in query_keywords if kw in title)
            title_boost = min(title_hits / max(len(query_keywords), 1), 1.0)

            # Body match: keyword hits in full text
            body_hits = sum(1 for kw in query_keywords if kw in text)
            body_score = min(body_hits / max(len(query_keywords), 1), 1.0)

            vec_score = 1.0 - doc.get("distance", 0)

            # Heavily favor title match (70%) over vector similarity (30%)
            doc["score"] = round(0.7 * title_boost + 0.2 * body_score + 0.1 * vec_score, 4)

        candidates.sort(key=lambda d: d.get("score", 0), reverse=True)
        return candidates[:k]

    def count(self) -> int:
        return self.collection.count()

    def clear(self) -> None:
        """Remove all documents from the collection."""
        ids = self.collection.get()["ids"]
        if ids:
            self.collection.delete(ids=ids)
