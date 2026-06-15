"""Graph-based retrieval from Neo4j knowledge graph."""

import jieba
import jieba.posseg as pseg
from typing import List, Dict, Optional
from neo4j import GraphDatabase
from ..config import get_settings


class GraphRetriever:
    """Entity linking + Cypher multi-hop queries on Neo4j medical KG."""

    def __init__(self, embedding_service=None):
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        self.embedding_service = embedding_service

    def close(self):
        self.driver.close()

    def _run(self, query: str, params: dict | None = None) -> list:
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    # ── Entity Linking ──

    # Common non-medical words that jieba extracts — don't use as entity keywords
    _STOP_WORDS = {
        "一会", "之后", "结果", "怎么办", "什么", "怎么", "可以", "应该",
        "这个", "那个", "一下", "有点", "还是", "因为", "所以", "但是",
        "而且", "不过", "如果", "就是", "休息", "猛地", "力气", "平时",
        "开始", "已经", "以前", "以后", "现在", "可能", "感觉", "情况",
        "发现", "进行", "使用", "需要", "没有", "知道", "觉得", "出来",
        "问题", "一下", "起来", "下来", "上来", "过来", "回去", "回来",
        "有时", "一直", "经常", "忽然", "突然", "正在", "总是", "立刻",
    }

    # Entity types that are likely real medical concepts (not noise)
    _MEDICAL_TYPES = {"disease", "symptom", "drug", "examination", "treatment",
                      "body_part", "department", "cause", "complication"}

    def link_entities(self, question: str) -> List[Dict]:
        """Extract medical entities from question and map to KG nodes.

        Quality controls:
        - Filter out common non-medical words
        - Skip entities that look like full sentences (>12 chars)
        - Prefer short keyword ↔ short entity matching
        - Prioritize real medical entity types
        """
        linked = []
        seen_names = set()

        # Step 1: jieba POS tagging
        words = pseg.cut(question)
        candidates = [w.word for w in words
                      if w.flag in ("n", "nr", "ns", "nt", "nz", "eng",
                                    "v", "vn", "vd", "a", "an", "ad")
                      and len(w.word) >= 2
                      and w.word not in self._STOP_WORDS]

        # Step 2: bigram/trigram sliding window for compound terms (skip stop words)
        for i in range(len(question) - 1):
            bigram = question[i:i+2]
            if bigram not in candidates and bigram not in self._STOP_WORDS:
                candidates.append(bigram)
        for i in range(len(question) - 2):
            trigram = question[i:i+3]
            if trigram not in candidates and trigram not in self._STOP_WORDS:
                candidates.append(trigram)

        # Step 3: Query Neo4j with quality filtering
        for kw in candidates[:15]:
            rows = self._run(
                """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $kw OR $kw CONTAINS e.name
                RETURN e.name AS name, e.type AS type
                LIMIT 5
                """,
                {"kw": kw},
            )
            for r in rows:
                name = r["name"]
                if name in seen_names:
                    continue
                # Filter: skip sentence-like entities (too long)
                if len(name) > 12:
                    continue
                # Filter: when keyword is short, matched entity should be reasonably short
                if len(kw) <= 3 and len(name) > 8:
                    continue
                seen_names.add(name)
                linked.append({"name": name, "type": r["type"], "keyword": kw})

        # Sort: prefer medical-type entities, then shorter names
        linked.sort(key=lambda e: (
            0 if e["type"] in self._MEDICAL_TYPES else 1,
            len(e["name"]),
        ))
        return linked

    # ── One-hop Retrieval ──

    def retrieve_one_hop(
        self,
        entity_names: List[str],
        relation_types: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Retrieve direct neighbors of given entities."""
        if not entity_names:
            return []

        if relation_types:
            query = """
            MATCH (h:Entity)-[r:RELATION]->(t:Entity)
            WHERE h.name IN $names AND r.type IN $rel_types
            RETURN h.name AS head, r.type AS relation, t.name AS tail,
                   r.confidence AS confidence, r.evidence AS evidence
            LIMIT $limit
            """
            rows = self._run(query, {"names": entity_names, "rel_types": relation_types, "limit": limit})
        else:
            query = """
            MATCH (h:Entity)-[r:RELATION]->(t:Entity)
            WHERE h.name IN $names
            RETURN h.name AS head, r.type AS relation, t.name AS tail,
                   r.confidence AS confidence, r.evidence AS evidence
            LIMIT $limit
            """
            rows = self._run(query, {"names": entity_names, "limit": limit})

        return rows

    # ── Multi-hop Retrieval ──

    def retrieve_multi_hop(
        self,
        entity_names: List[str],
        hops: int = 2,
        limit: int = 50,
    ) -> List[Dict]:
        """Retrieve multi-hop paths from KG starting from given entities."""
        if not entity_names:
            return []

        if hops == 1:
            return self.retrieve_one_hop(entity_names, limit=limit)

        query = """
        MATCH path = (h:Entity)-[r1:RELATION]->(m:Entity)-[r2:RELATION]->(t:Entity)
        WHERE h.name IN $names
        RETURN h.name AS head, r1.type AS relation1, m.name AS middle, m.type AS middle_type,
               r2.type AS relation2, t.name AS tail, t.type AS tail_type,
               r1.confidence AS conf1, r2.confidence AS conf2
        LIMIT $limit
        """
        return self._run(query, {"names": entity_names, "limit": limit})

    # ── Specialized: diabetes + numbness -> examination ──

    def retrieve_examination_path(self, disease: str, symptom: str) -> List[Dict]:
        """Multi-hop: disease -> symptom -> examination (for required test case)."""
        query = """
        MATCH (d:Entity {name: $disease})-[r1:RELATION]->(s:Entity)-[r2:RELATION]->(e:Entity)
        WHERE s.name CONTAINS $symptom
        RETURN d.name AS disease, r1.type AS rel_to_symptom, s.name AS symptom,
               r2.type AS rel_to_exam, e.name AS examination, e.type AS exam_type,
               r1.confidence AS conf1, r2.confidence AS conf2
        LIMIT 20
        """
        return self._run(query, {"disease": disease, "symptom": symptom})
