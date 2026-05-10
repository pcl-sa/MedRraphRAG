"""FastAPI dependency injection — lazy-initialized singletons."""

from functools import lru_cache
from typing import Dict

from ..config import get_settings, Settings
from ..retrieval.embedding_service import EmbeddingService
from ..retrieval.vector_store import VectorStore
from ..retrieval.graph_retriever import GraphRetriever
from ..retrieval.fusion import RetrievalFusion
from ..qa.pipeline import QAPipeline
from ..qa.memory_manager import MemoryManager


_embedding_service: EmbeddingService | None = None
_vector_store: VectorStore | None = None
_graph_retriever: GraphRetriever | None = None
_retrieval_fusion: RetrievalFusion | None = None
_qa_pipeline: QAPipeline | None = None
_session_memories: Dict[str, MemoryManager] = {}


def get_settings_singleton() -> Settings:
    return get_settings()


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(get_embedding_service())
    return _vector_store


def get_graph_retriever() -> GraphRetriever:
    global _graph_retriever
    if _graph_retriever is None:
        _graph_retriever = GraphRetriever(get_embedding_service())
    return _graph_retriever


def get_retrieval_fusion() -> RetrievalFusion:
    global _retrieval_fusion
    if _retrieval_fusion is None:
        _retrieval_fusion = RetrievalFusion(get_vector_store(), get_graph_retriever())
    return _retrieval_fusion


def get_qa_pipeline() -> QAPipeline:
    global _qa_pipeline
    if _qa_pipeline is None:
        _qa_pipeline = QAPipeline(get_retrieval_fusion(), _session_memories)
    return _qa_pipeline


def get_session_memories() -> Dict[str, MemoryManager]:
    return _session_memories
