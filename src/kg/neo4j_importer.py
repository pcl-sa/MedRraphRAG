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
        CREATE (h)-[r:RELATION {
          type: t.relation,
          confidence: t.confidence,
          evidence: t.evidence
        }]->(t2)
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
