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

    def link_entities(self, question: str) -> List[Dict]:
        """Extract medical entities from question and map to KG nodes."""
        linked = []
        seen_names = set()

        # Step 1: jieba POS tagging — use broader tags to catch medical terms
        # Medical terms often tagged as v(verb), a(adjective), vn(gerund) by jieba
        words = pseg.cut(question)
        candidates = [w.word for w in words
                      if w.flag in ("n", "nr", "ns", "nt", "nz", "eng",
                                    "v", "vn", "vd", "a", "an", "ad")
                      and len(w.word) >= 2]

        # Step 2: Also try bigram sliding window as fallback (catch "手脚麻木" etc)
        for i in range(len(question) - 1):
            bigram = question[i:i+2]
            if bigram not in candidates:
                candidates.append(bigram)
        for i in range(len(question) - 2):
            trigram = question[i:i+3]
            if trigram not in candidates:
                candidates.append(trigram)

        # Step 3: For each candidate, query Neo4j with CONTAINS
        for kw in candidates[:15]:  # limit candidates
            rows = self._run(
                """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $kw OR $kw CONTAINS e.name
                RETURN e.name AS name, e.type AS type
                LIMIT 3
                """,
                {"kw": kw},
            )
            for r in rows:
                if r["name"] not in seen_names:
                    seen_names.add(r["name"])
                    linked.append({"name": r["name"], "type": r["type"], "keyword": kw})

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
