"""Trace/debug endpoint for transparency."""

from fastapi import APIRouter, Depends
from ..schemas import ChatRequest, TraceResponse, SourceDocOut
from ..dependencies import get_qa_pipeline
from ...qa.pipeline import QAPipeline

router = APIRouter(prefix="/api", tags=["trace"])


@router.post("/trace", response_model=TraceResponse)
async def trace(request: ChatRequest, pipeline: QAPipeline = Depends(get_qa_pipeline)):
    """Return full retrieval + generation trace for debugging."""
    raw = pipeline.trace(request.question)

    docs_out = [
        SourceDocOut(
            text_preview=d.get("text", "")[:200],
            title=d.get("title", ""),
            department=d.get("department", ""),
            score=d.get("score", 0.0),
        )
        for d in raw.get("retrieved_documents", [])
    ]

    return TraceResponse(
        question=raw["question"],
        linked_entities=raw.get("linked_entities", []),
        retrieved_documents=docs_out,
        graph_triples=raw.get("graph_triples", []),
        multi_hop_paths=raw.get("multi_hop_paths", []),
        full_prompt=raw.get("full_prompt", ""),
        answer=raw.get("answer", ""),
    )
