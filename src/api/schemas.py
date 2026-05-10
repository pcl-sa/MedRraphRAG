"""API request/response models."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="User's medical question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for multi-turn")
    new_conversation: bool = Field(False, description="Start a new conversation")
    department_filter: Optional[str] = Field(None, description="Filter by medical department")
    graph_hops: int = Field(2, ge=1, le=3, description="Number of graph hops (1-3)")
    api_key: Optional[str] = Field(None, description="User's own DashScope API key (overrides .env)")


class SourceDocOut(BaseModel):
    text_preview: str
    title: str
    department: str
    score: float


class GraphNodeOut(BaseModel):
    id: str
    label: str
    type: str
    group: str = ""


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    relation: str
    confidence: float = 1.0


class GraphVizOut(BaseModel):
    nodes: List[GraphNodeOut] = Field(default_factory=list)
    edges: List[GraphEdgeOut] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: List[SourceDocOut] = Field(default_factory=list)
    graph_data: GraphVizOut = Field(default_factory=GraphVizOut)
    reasoning_steps: List[str] = Field(default_factory=list)


class TraceResponse(BaseModel):
    question: str
    linked_entities: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_documents: List[SourceDocOut] = Field(default_factory=list)
    graph_triples: List[Dict[str, Any]] = Field(default_factory=list)
    multi_hop_paths: List[Dict[str, Any]] = Field(default_factory=list)
    full_prompt: str = ""
    answer: str = ""


class HealthResponse(BaseModel):
    status: str = "ok"
    neo4j_connected: bool = False
    chroma_doc_count: int = 0
    kg_node_count: int = 0
    kg_edge_count: int = 0
