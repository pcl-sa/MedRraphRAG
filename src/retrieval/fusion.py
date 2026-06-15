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
        """Execute hybrid retrieval and return combined context.

        Quality gates:
        - If best text score is very low and entity matches are weak, clear results
          to avoid showing irrelevant data.
        """
        ctx = RetrievalContext()

        # 1. Vector search with keyword re-rank for Chinese relevance
        ctx.text_chunks = self.vector_store.search_with_rerank(
            question, k=vector_k, department_filter=department_filter
        )

        # 2. Entity linking
        ctx.linked_entities = self.graph_retriever.link_entities(question)

        # Quality gate: based on combined evidence from text + entities + graph
        best_text_score = max((c.get("score", 0) for c in ctx.text_chunks), default=0)

        # 3. Graph retrieval
        entity_names = [e["name"] for e in ctx.linked_entities]
        if entity_names:
            ctx.graph_triples = self.graph_retriever.retrieve_one_hop(
                entity_names, relation_types=graph_relations
            )
            ctx.multi_hop_paths = self.graph_retriever.retrieve_multi_hop(
                entity_names, hops=graph_hops
            )

        # Quality gate: clear low-confidence results to avoid showing irrelevant data
        strong_entities = [e for e in ctx.linked_entities
                          if e["type"] in ("disease", "symptom", "drug", "body_part")]
        graph_rich = len(ctx.graph_triples) >= 3

        # Gate 1: poor text + few graph triples → not confident, clear all
        if best_text_score < 0.25 and not graph_rich:
            ctx.text_chunks = []
            ctx.graph_triples = []
            ctx.multi_hop_paths = []
            ctx.linked_entities = []
        # Gate 2: very poor text with any entities → clear text, keep graph if rich
        elif best_text_score < 0.18:
            ctx.text_chunks = []
            if not graph_rich:
                ctx.graph_triples = []
                ctx.multi_hop_paths = []
                ctx.linked_entities = []

        return ctx

    def format_context(self, ctx: RetrievalContext) -> str:
        """Format RetrievalContext into a structured string for the LLM prompt."""
        has_graph = bool(ctx.graph_triples or ctx.multi_hop_paths)
        has_text = bool(ctx.text_chunks)
        has_entities = bool(ctx.linked_entities)

        # If nothing found, signal clearly
        if not has_graph and not has_text and not has_entities:
            return (
                "【重要提醒】知识库中未找到与该问题相关的任何医学知识。\n"
                "你必须回复：'抱歉，当前知识库中没有与您问题相关的医学信息。我是医疗助手，只能回答医学健康相关问题。'\n"
                "禁止编造任何医学信息或回答非医学问题。"
            )

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
        elif has_entities:
            parts.append("【注意】知识图谱中有相关实体，但未检索到直接三元组关系。")

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
                score = chunk.get("score", 0)
                parts.append(f"[{i+1}] ({dept}) {title} [相关度: {score:.2f}]")
                parts.append(f"    {text}")
        elif has_graph:
            parts.append("\n【注意】未找到与该问题直接相关的文本问答记录。")

        # Linked entities
        if ctx.linked_entities:
            parts.append("\n【识别到的医学实体】")
            entities_str = ", ".join(
                f"{e['name']}({e['type']})" for e in ctx.linked_entities
            )
            parts.append(f"  {entities_str}")

        return "\n".join(parts)
