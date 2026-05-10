"""Chat and health endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_community.chat_models.tongyi import ChatTongyi
from ..schemas import ChatRequest, ChatResponse, SourceDocOut, GraphVizOut, GraphNodeOut, GraphEdgeOut
from ..dependencies import get_qa_pipeline, get_graph_retriever, get_vector_store
from ...qa.pipeline import QAPipeline
from ...config import get_settings

router = APIRouter(prefix="/api", tags=["chat"])


def _apply_api_key(request: ChatRequest, pipeline: QAPipeline) -> None:
    """Apply user API key or reset to .env default. Validates key immediately."""
    settings = get_settings()
    if request.api_key and request.api_key.strip():
        new_key = request.api_key.strip()
        # Skip if already using this key
        if settings.dashscope_api_key == new_key:
            return
        # Fast validation: ping DashScope with a minimal call
        try:
            test_llm = ChatTongyi(
                model=settings.llm_model_name,
                dashscope_api_key=new_key,
                temperature=0,
                max_tokens=1,
            )
            test_llm.invoke("OK")
        except Exception as e:
            msg = str(e).lower()
            if any(kw in msg for kw in ("401", "403", "invalid", "unauthorized", "apikey", "api-key")):
                raise HTTPException(status_code=401, detail=f"API Key 无效: {str(e)[:200]}")
            # Non-auth error (e.g. network) — still apply the key but warn
            print(f"  API key validation warning: {str(e)[:100]}")
        # Key valid — apply it
        settings.update_api_key(new_key)
        pipeline.update_api_key(new_key)
    else:
        # No valid user key — always restore .env default
        if settings.dashscope_api_key != settings._default_api_key:
            settings.dashscope_api_key = settings._default_api_key
            pipeline.update_api_key(settings._default_api_key)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, pipeline: QAPipeline = Depends(get_qa_pipeline)):
    """Main medical Q&A endpoint."""
    _apply_api_key(request, pipeline)
    conv_id = None if request.new_conversation else request.conversation_id

    try:
        result = pipeline.answer(
            question=request.question,
            conversation_id=conv_id,
            department_filter=request.department_filter,
            graph_hops=request.graph_hops,
        )
    except Exception as e:
        msg = str(e)
        if "401" in msg or "403" in msg or "invalid" in msg.lower() or "unauthorized" in msg.lower():
            raise HTTPException(status_code=401, detail=f"API Key 无效或无权访问: {msg[:200]}")
        raise HTTPException(status_code=500, detail=f"LLM 调用失败: {msg[:200]}")

    # Convert internal models to API response models
    sources_out = [
        SourceDocOut(
            text_preview=s.text_preview,
            title=s.title,
            department=s.department,
            score=s.score,
        )
        for s in result.sources
    ]

    graph_out = GraphVizOut(
        nodes=[
            GraphNodeOut(id=n.id, label=n.label, type=n.type, group=n.group)
            for n in result.graph_data.nodes
        ],
        edges=[
            GraphEdgeOut(source=e.source, target=e.target, relation=e.relation, confidence=e.confidence)
            for e in result.graph_data.edges
        ],
    )

    return ChatResponse(
        answer=result.answer,
        conversation_id=result.conversation_id,
        sources=sources_out,
        graph_data=graph_out,
        reasoning_steps=result.reasoning_steps,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, pipeline: QAPipeline = Depends(get_qa_pipeline)):
    """Streaming medical Q&A endpoint (SSE)."""
    _apply_api_key(request, pipeline)
    conv_id = None if request.new_conversation else request.conversation_id

    async def event_stream():
        async for sse_chunk in pipeline.answer_stream(
            question=request.question,
            conversation_id=conv_id,
            department_filter=request.department_filter,
            graph_hops=request.graph_hops,
        ):
            yield sse_chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
async def health():
    """Health check with component status."""
    from ..schemas import HealthResponse

    neo4j_ok = False
    kg_nodes = 0
    kg_edges = 0
    try:
        gr = get_graph_retriever()
        stats = gr._run("MATCH (n) RETURN count(n) AS cnt")
        kg_nodes = stats[0]["cnt"] if stats else 0
        edge_stats = gr._run("MATCH ()-[r]->() RETURN count(r) AS cnt")
        kg_edges = edge_stats[0]["cnt"] if edge_stats else 0
        neo4j_ok = True
    except Exception:
        pass

    chroma_count = 0
    try:
        vs = get_vector_store()
        chroma_count = vs.count()
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        neo4j_connected=neo4j_ok,
        chroma_doc_count=chroma_count,
        kg_node_count=kg_nodes,
        kg_edge_count=kg_edges,
    )
