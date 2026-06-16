import json
from pathlib import Path
from neo4j import GraphDatabase
from typing import List, Dict
from ..config import get_settings


class Neo4jImporter:
    """Import medical triples into Neo4j with constraints and indexes."""

    def __init__(self):
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )

    def close(self):
        self.driver.close()

    def _run(self, query: str, params: dict | None = None) -> list:
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    def create_constraints(self) -> None:
        """Create unique constraints and indexes for efficient queries."""
        constraints = [
            "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX disease_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
        ]
        for stmt in constraints:
            try:
                self._run(stmt)
            except Exception as e:
                print(f"  Constraint/index skipped: {e}")

    def clear_all(self) -> None:
        """Delete all nodes and relationships (development reset)."""
        self._run("MATCH (n) DETACH DELETE n")
        print("  Cleared all nodes and relationships")

    def import_triples(self, triples: List[dict]) -> Dict[str, int]:
        """Bulk import triples using UNWIND for efficiency."""
        if not triples:
            return {"nodes": 0, "edges": 0}

        print(f"  Importing {len(triples)} triples...")

        query = """
        UNWIND $triples AS t
        MERGE (h:Entity {name: t.head_entity})
          ON CREATE SET h.type = t.head_type
        MERGE (t2:Entity {name: t.tail_entity})
          ON CREATE SET t2.type = t.tail_type
        MERGE (h)-[r:RELATION {type: t.relation}]->(t2)
          ON CREATE SET r.confidence = t.confidence, r.evidence = t.evidence
        """

        batch_size = 200
        total = 0
        for i in range(0, len(triples), batch_size):
            batch = triples[i:i + batch_size]
            self._run(query, {"triples": batch})
            total += len(batch)

        counts = self.get_stats()
        print(f"  Import complete: {counts['nodes']} nodes, {counts['edges']} edges")
        return counts

    def import_from_json(self, json_path: str, clear_first: bool = False) -> Dict[str, int]:
        """Import knowledge graph from a JSON file (knowledge_graph.json format).

        JSON format: {"entities": [{"name":..., "type":...}], "triples": [{"head":..., "relation":..., "tail":..., "confidence":..., "evidence":...}]}

        Args:
            json_path: path to the JSON file
            clear_first: if True, delete all existing nodes/edges before import
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entities_data = data.get("entities", [])
        triples_data = data.get("triples", [])
        meta = data.get("meta", {})

        print(f"Loading {path.name}: {len(entities_data)} entities, {len(triples_data)} triples")
        if meta:
            print(f"  Meta: {meta.get('entity_count', '?')} entities, {meta.get('triple_count', '?')} triples")

        # Build entity name → type lookup
        entity_types: Dict[str, str] = {}
        for e in entities_data:
            if e.get("name"):
                entity_types[e["name"]] = e.get("type", "unknown")

        # Also extract entity types from triples (head/tail may have implicit types)
        def infer_type(name: str) -> str:
            return entity_types.get(name, "unknown")

        # Convert to import_triples format
        formatted: List[dict] = []
        for t in triples_data:
            head = t.get("head", "")
            tail = t.get("tail", "")
            if not head or not tail:
                continue
            formatted.append({
                "head_entity": head,
                "head_type": infer_type(head),
                "tail_entity": tail,
                "tail_type": infer_type(tail),
                "relation": t.get("relation", "related_to"),
                "confidence": float(t.get("confidence", 0.5)),
                "evidence": t.get("evidence", ""),
            })

        if not formatted:
            print("  No valid triples to import.")
            return self.get_stats()

        if clear_first:
            self.clear_all()

        self.create_constraints()
        return self.import_triples(formatted)

    def get_stats(self) -> Dict[str, int]:
        """Return node and relationship counts."""
        try:
            nodes = self._run("MATCH (n) RETURN count(n) AS cnt")
            edges = self._run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            return {
                "nodes": nodes[0]["cnt"] if nodes else 0,
                "edges": edges[0]["cnt"] if edges else 0,
            }
        except Exception:
            return {"nodes": 0, "edges": 0}

    def get_entity_types(self) -> Dict[str, int]:
        """Return counts per entity type."""
        rows = self._run(
            "MATCH (e:Entity) RETURN e.type AS type, count(e) AS cnt ORDER BY cnt DESC"
        )
        return {r["type"]: r["cnt"] for r in rows}


if __name__ == "__main__":
    import sys
    importer = Neo4jImporter()
    try:
        if len(sys.argv) < 2:
            print("Usage: python -m src.kg.neo4j_importer <knowledge_graph.json> [--clear]")
            print("  --clear  Delete all existing nodes/edges before import")
        else:
            json_path = sys.argv[1]
            clear = "--clear" in sys.argv
            importer.import_from_json(json_path, clear_first=clear)
    finally:
        importer.close()
