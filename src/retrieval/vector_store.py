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
               department_filter: Optional[str] = None,
               min_similarity: float = 0.25) -> List[Dict]:
        """Cosine similarity Top-K search with optional department filter.

        Args:
            min_similarity: minimum cosine similarity (1 - distance) threshold.
                Documents below this are considered irrelevant and filtered out.
        """
        query_embedding = self.embedding_service.embed_query(query).tolist()
        where_filter = None
        if department_filter:
            where_filter = {"department": department_filter}

        # Fetch more than k to allow post-filtering by threshold
        fetch_k = max(k * 4, 20)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0.0
                similarity = 1.0 - distance
                if similarity < min_similarity:
                    continue
                docs.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": distance,
                    "score": round(similarity, 4),
                })
                if len(docs) >= k:
                    break
        return docs

    # Common question/noise words that shouldn't drive keyword matching
    _NOISE_PATTERNS = {
        "怎么办", "怎么", "什么", "为什么", "如何", "是否",
        "可以", "应该", "需要", "能否", "会不会", "能不能",
        "怎么治", "如何治", "该怎样", "该怎么办",
    }

    def _extract_keywords(self, query: str) -> set:
        """Extract meaningful Chinese keywords, filtering out noise words."""
        raw = set(re.findall(r'[一-鿿]{2,}', query))
        return {kw for kw in raw if kw not in self._NOISE_PATTERNS}

    def search_with_rerank(self, query: str, k: int = 5, fetch_k: int = 30,
                           department_filter: Optional[str] = None,
                           min_similarity: float = 0.25,
                           min_rerank_score: float = 0.12) -> List[Dict]:
        """Search with keyword-based reranking for better Chinese relevance.

        Fetches fetch_k candidates from vector search (post threshold), then re-ranks
        by keyword overlap. Filters out noise words (怎么办, 怎么 etc) and results
        below min_rerank_score.
        """
        candidates = self.search(query, k=fetch_k, department_filter=department_filter,
                                 min_similarity=min_similarity)
        query_keywords = self._extract_keywords(query)
        if not query_keywords or not candidates:
            # Without meaningful keywords, rely purely on vector score
            candidates.sort(key=lambda d: d.get("score", 1.0 - d.get("distance", 0)), reverse=True)
            filtered = [d for d in candidates if d.get("score", 1.0 - d.get("distance", 0)) >= 0.55]
            return filtered[:k]

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

            vec_score = doc.get("score", 1.0 - doc.get("distance", 0))

            # Balance: title (40%), body (25%), vector (35%)
            doc["score"] = round(0.4 * title_boost + 0.25 * body_score + 0.35 * vec_score, 4)

        candidates.sort(key=lambda d: d.get("score", 0), reverse=True)
        # Filter by min_rerank_score
        filtered = [d for d in candidates if d.get("score", 0) >= min_rerank_score]
        return filtered[:k]

    def count(self) -> int:
        return self.collection.count()

    def clear(self) -> None:
        """Remove all documents from the collection."""
        ids = self.collection.get()["ids"]
        if ids:
            self.collection.delete(ids=ids)
