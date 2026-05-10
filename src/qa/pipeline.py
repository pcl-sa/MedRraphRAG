"""Main Q&A pipeline: hybrid retrieval + LLM generation."""

import re
import uuid
from typing import Optional, List, AsyncIterator
from langchain_community.chat_models.tongyi import ChatTongyi
from ..config import get_settings
from ..kg.entity_relation_extractor import MODEL_LIST, _is_token_exhausted
from .prompts import MEDICAL_SYSTEM_PROMPT
from .schemas import AnswerResponse, SourceDoc, GraphVizData, GraphNode, GraphEdge
from .memory_manager import MemoryManager


class QAPipeline:
    """Medical GraphRAG Q&A pipeline with model fallback and streaming support."""

    def __init__(self, retrieval_fusion, model_list: Optional[List[str]] = None,
                 memory_managers: dict | None = None):
        settings = get_settings()
        self.retrieval_fusion = retrieval_fusion
        self._memories: dict = memory_managers if memory_managers is not None else {}
        self._model_list = model_list or MODEL_LIST
        self._model_index = 0
        self._settings = settings
        self._init_llm()

    def _init_llm(self, streaming: bool = False):
        name = self._model_list[self._model_index]
        self.current_model = name
        llm_kwargs = dict(
            model=name,
            dashscope_api_key=self._settings.dashscope_api_key,
            temperature=self._settings.llm_temperature,
            max_tokens=self._settings.llm_max_tokens,
        )
        if streaming:
            llm_kwargs["streaming"] = True
        self.llm = ChatTongyi(**llm_kwargs)

    def update_api_key(self, key: str) -> None:
        """Override the API key and re-init the LLM (for user-provided keys)."""
        if key and key.strip():
            self._settings.dashscope_api_key = key.strip()
            self._init_llm()
            print(f"  QA using user-provided API key: {key[:8]}...")

    def _try_switch_model(self) -> bool:
        if self._model_index + 1 >= len(self._model_list):
            return False
        self._model_index += 1
        self._init_llm()
        print(f"  QA switched to model: {self.current_model}")
        return True

    def _invoke_llm_with_fallback(self, prompt: str) -> str:
        """Invoke LLM with automatic model fallback on token exhaustion."""
        while True:
            try:
                resp = self.llm.invoke(prompt)
                return resp.content if hasattr(resp, 'content') else str(resp)
            except Exception as e:
                if _is_token_exhausted(e):
                    print(f"  QA token exhausted for '{self.current_model}'")
                    if self._try_switch_model():
                        continue
                    return f"抱歉，所有模型token均已耗尽。请稍后再试。错误: {e}"
                raise

    def _get_memory(self, conversation_id: Optional[str]) -> MemoryManager:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        if conversation_id not in self._memories:
            self._memories[conversation_id] = MemoryManager(self.llm)
        return self._memories[conversation_id]

    def answer(
        self,
        question: str,
        conversation_id: Optional[str] = None,
        department_filter: Optional[str] = None,
        graph_hops: int = 2,
    ) -> AnswerResponse:
        """Main Q&A entry point."""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # 1. Retrieve
        ctx = self.retrieval_fusion.retrieve(
            question, department_filter=department_filter, graph_hops=graph_hops,
        )
        context_str = self.retrieval_fusion.format_context(ctx)

        # 2. Build prompt
        memory = self._get_memory(conversation_id)
        history_str = memory.get_history()
        prompt = MEDICAL_SYSTEM_PROMPT.format(
            context=context_str,
            chat_history=history_str,
            question=question,
        )

        # 3. Generate (with model fallback)
        answer_text = self._invoke_llm_with_fallback(prompt)

        # 4. Parse reasoning steps
        steps = self._extract_reasoning_steps(answer_text)

        # 5. Build sources
        sources = [
            SourceDoc(
                text_preview=c.get("text", "")[:200],
                title=c.get("metadata", {}).get("title", ""),
                department=c.get("metadata", {}).get("department", ""),
                score=round(1.0 - c.get("distance", 0), 4),
            )
            for c in ctx.text_chunks
        ]

        # 6. Build graph visualization data
        graph_data = self._build_graph_viz(ctx)

        # 7. Update memory
        memory.add_user_message(question)
        memory.add_ai_message(answer_text)

        return AnswerResponse(
            answer=answer_text,
            reasoning_steps=steps,
            sources=sources,
            graph_data=graph_data,
            conversation_id=conversation_id,
        )

    def build_prompt_and_context(
        self, question: str, conversation_id: Optional[str] = None,
        department_filter: Optional[str] = None, graph_hops: int = 2,
    ) -> tuple[str, str, object]:
        """Build prompt and return (prompt, conversation_id, RetrievalContext)."""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        ctx = self.retrieval_fusion.retrieve(
            question, department_filter=department_filter, graph_hops=graph_hops,
        )
        context_str = self.retrieval_fusion.format_context(ctx)
        memory = self._get_memory(conversation_id)
        history_str = memory.get_history()
        prompt = MEDICAL_SYSTEM_PROMPT.format(
            context=context_str,
            chat_history=history_str,
            question=question,
        )
        return prompt, conversation_id, ctx

    async def answer_stream(
        self, question: str, conversation_id: Optional[str] = None,
        department_filter: Optional[str] = None, graph_hops: int = 2,
    ) -> AsyncIterator[str]:
        """Stream answer tokens via SSE. Yields JSON lines with token/sources/graph."""
        import json as _json

        prompt, conversation_id, ctx = self.build_prompt_and_context(
            question, conversation_id, department_filter, graph_hops,
        )

        # Build non-stream sources/graph for final event
        sources = [
            {"text_preview": c.get("text", "")[:200],
             "title": c.get("metadata", {}).get("title", ""),
             "department": c.get("metadata", {}).get("department", ""),
             "score": c.get("score", round(1.0 - c.get("distance", 0), 4))}
            for c in ctx.text_chunks
        ]
        graph_data = self._build_graph_viz(ctx)

        full_answer = ""

        try:
            # Create streaming LLM
            stream_llm = ChatTongyi(
                model=self.current_model,
                dashscope_api_key=self._settings.dashscope_api_key,
                temperature=self._settings.llm_temperature,
                max_tokens=self._settings.llm_max_tokens,
                streaming=True,
            )
            async for chunk in stream_llm.astream(prompt):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    full_answer += token
                    yield f"data: {_json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        except Exception as e:
            if _is_token_exhausted(e) and self._try_switch_model():
                # Retry with next model
                stream_llm = ChatTongyi(
                    model=self.current_model,
                    dashscope_api_key=self._settings.dashscope_api_key,
                    temperature=self._settings.llm_temperature,
                    max_tokens=self._settings.llm_max_tokens,
                    streaming=True,
                )
                async for chunk in stream_llm.astream(prompt):
                    token = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if token:
                        full_answer += token
                        yield f"data: {_json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                return

        # Send final metadata event
        steps = self._extract_reasoning_steps(full_answer)
        final = {
            "done": True,
            "conversation_id": conversation_id,
            "sources": sources,
            "graph_data": {"nodes": [{"id": n.id, "label": n.label, "type": n.type, "group": n.group}
                                     for n in graph_data.nodes],
                           "edges": [{"source": e.source, "target": e.target, "relation": e.relation,
                                      "confidence": e.confidence} for e in graph_data.edges]},
            "reasoning_steps": steps,
        }
        yield f"data: {_json.dumps(final, ensure_ascii=False)}\n\n"

        # Update memory
        memory = self._get_memory(conversation_id)
        memory.add_user_message(question)
        memory.add_ai_message(full_answer)

    def trace(self, question: str) -> dict:
        """Return full trace for debugging/transparency."""
        ctx = self.retrieval_fusion.retrieve(question)
        context_str = self.retrieval_fusion.format_context(ctx)

        prompt = MEDICAL_SYSTEM_PROMPT.format(
            context=context_str,
            chat_history="（无对话历史）",
            question=question,
        )

        answer_text = self._invoke_llm_with_fallback(prompt)

        return {
            "question": question,
            "linked_entities": [{"name": e["name"], "type": e["type"]} for e in ctx.linked_entities],
            "retrieved_documents": [
                {"text": c.get("text", "")[:300], "title": c.get("metadata", {}).get("title", ""),
                 "department": c.get("metadata", {}).get("department", ""),
                 "score": round(1.0 - c.get("distance", 0), 4)}
                for c in ctx.text_chunks
            ],
            "graph_triples": [
                {"head": t["head"], "relation": t["relation"], "tail": t["tail"]}
                for t in ctx.graph_triples
            ],
            "multi_hop_paths": [
                {"head": p.get("head", ""), "relation1": p.get("relation1", ""),
                 "middle": p.get("middle", ""), "relation2": p.get("relation2", ""),
                 "tail": p.get("tail", "")}
                for p in ctx.multi_hop_paths
            ],
            "full_prompt": prompt,
            "answer": answer_text,
        }

    @staticmethod
    def _extract_reasoning_steps(text: str) -> list[str]:
        """Extract numbered reasoning steps from LLM output."""
        # Try to match numbered steps
        pattern = r"(?:步骤\s*\d+[：:.]|Step\s*\d+[：:.]|\d+[、.)])\s*(.+?)(?=(?:步骤\s*\d+|Step\s*\d+|\d+[、.)]|$))"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return [m.strip() for m in matches if m.strip() and len(m.strip()) > 5]
        # If no steps found and text is long, return empty
        return []

    @staticmethod
    def _build_graph_viz(ctx) -> GraphVizData:
        """Convert retrieval context to graph visualization data."""
        nodes = {}
        edges = []

        entity_colors = {
            "disease": "#e74c3c", "symptom": "#f39c12", "drug": "#3498db",
            "examination": "#2ecc71", "treatment": "#9b59b6", "department": "#1abc9c",
            "body_part": "#e67e22", "risk_factor": "#95a5a6", "cause": "#34495e",
        }

        for t in ctx.graph_triples:
            head = t.get("head", "")
            tail = t.get("tail", "")
            if head and head not in nodes:
                nodes[head] = GraphNode(id=head, label=head, type="", group="disease")
            if tail and tail not in nodes:
                nodes[tail] = GraphNode(id=tail, label=tail, type="", group="disease")
            edges.append(GraphEdge(
                source=head, target=tail,
                relation=t.get("relation", ""),
                confidence=float(t.get("confidence", 1.0)),
            ))

        for e in ctx.linked_entities:
            name = e.get("name", "")
            etype = e.get("type", "disease")
            if name and name not in nodes:
                nodes[name] = GraphNode(id=name, label=name, type=etype, group=etype)

        for n in nodes.values():
            if n.group in entity_colors:
                n.group = entity_colors[n.group]

        return GraphVizData(nodes=list(nodes.values()), edges=edges)
