"""Retrieval fusion: combine vector text chunks + graph triples for LLM context."""

from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class RetrievalContext:
    text_chunks: List[Dict] = field(default_factory=list)
    graph_triples: List[Dict] = field(default_factory=list)
    linked_entities: List[Dict] = field(default_factory=list)
    multi_hop_paths: List[Dict] = field(default_factory=list)


class RetrievalFusion:
    """Orchestrate hybrid retrieval and format context for LLM."""

    def __init__(self, vector_store, graph_retriever):
        self.vector_store = vector_store
        self.graph_retriever = graph_retriever

    def retrieve(
        self,
        question: str,
        vector_k: int = 5,
        graph_hops: int = 2,
        graph_relations: Optional[List[str]] = None,
        department_filter: Optional[str] = None,
    ) -> RetrievalContext:
        """Execute hybrid retrieval and return combined context."""
        ctx = RetrievalContext()

        # 1. Vector search with keyword re-rank for Chinese relevance
        ctx.text_chunks = self.vector_store.search_with_rerank(
            question, k=vector_k, department_filter=department_filter
        )

        # 2. Entity linking
        ctx.linked_entities = self.graph_retriever.link_entities(question)

        # 3. Graph retrieval
        entity_names = [e["name"] for e in ctx.linked_entities]
        if entity_names:
            ctx.graph_triples = self.graph_retriever.retrieve_one_hop(
                entity_names, relation_types=graph_relations
            )
            ctx.multi_hop_paths = self.graph_retriever.retrieve_multi_hop(
                entity_names, hops=graph_hops
            )

        return ctx

    def format_context(self, ctx: RetrievalContext) -> str:
        """Format RetrievalContext into a structured string for the LLM prompt."""
        parts = []

        # Graph triples section
        if ctx.graph_triples:
            parts.append("【医学知识图谱三元组】")
            for t in ctx.graph_triples:
                conf = t.get("confidence", 1.0)
                parts.append(
                    f"- ({t['head']}, {t['relation']}, {t['tail']}) "
                    f"[置信度: {conf:.2f}]"
                )

        # Multi-hop paths
        if ctx.multi_hop_paths:
            parts.append("\n【多跳推理路径】")
            for p in ctx.multi_hop_paths:
                path_str = f"{p['head']} --[{p['relation1']}]--> {p['middle']}"
                if "relation2" in p:
                    path_str += f" --[{p['relation2']}]--> {p['tail']}"
                parts.append(f"- {path_str}")

        # Text chunks
        if ctx.text_chunks:
            parts.append("\n【相关医学问答记录】")
            for i, chunk in enumerate(ctx.text_chunks):
                meta = chunk.get("metadata", {})
                title = meta.get("title", "未知")
                dept = meta.get("department", "")
                text = chunk.get("text", "")[:500]
                parts.append(f"[{i+1}] ({dept}) {title}")
                parts.append(f"    {text}")

        # Linked entities
        if ctx.linked_entities:
            parts.append("\n【识别到的医学实体】")
            entities_str = ", ".join(
                f"{e['name']}({e['type']})" for e in ctx.linked_entities
            )
            parts.append(f"  {entities_str}")

        return "\n".join(parts)
