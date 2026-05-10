"""QA-specific Pydantic models."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SourceDoc(BaseModel):
    text_preview: str = ""
    title: str = ""
    department: str = ""
    score: float = 0.0


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    group: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    confidence: float = 1.0


class GraphVizData(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class AnswerResponse(BaseModel):
    answer: str
    reasoning_steps: List[str] = Field(default_factory=list)
    sources: List[SourceDoc] = Field(default_factory=list)
    graph_data: GraphVizData = Field(default_factory=GraphVizData)
    conversation_id: str = ""


class TraceResponse(BaseModel):
    question: str
    linked_entities: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_documents: List[SourceDoc] = Field(default_factory=list)
    graph_triples: List[Dict[str, Any]] = Field(default_factory=list)
    multi_hop_paths: List[Dict[str, Any]] = Field(default_factory=list)
    full_prompt: str = ""
    answer: str = ""
