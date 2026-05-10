"""End-to-end knowledge graph construction script.

Usage:
    python -m src.kg.build_graph           # full pipeline
    python -m src.kg.build_graph --sample 800   # custom sample size
    python -m src.kg.build_graph --skip-extract  # reuse saved triples
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path for direct invocation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import get_settings
from src.kg.data_loader import DataLoader
from src.kg.data_cleaner import DataCleaner
from src.kg.entity_relation_extractor import EntityRelationExtractor
from src.kg.neo4j_importer import Neo4jImporter


def main():
    parser = argparse.ArgumentParser(description="Build Medical Knowledge Graph")
    parser.add_argument("--sample", type=int, default=500, help="Number of records to sample")
    parser.add_argument("--skip-extract", action="store_true", help="Skip LLM extraction (use saved triples)")
    parser.add_argument("--output", type=str, default=None, help="Output path for triples JSON")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between LLM calls (seconds)")
    parser.add_argument("--clear", action="store_true", help="Clear all existing data in Neo4j before import")
    args = parser.parse_args()

    settings = get_settings()
    processed_dir = Path(settings.processed_data_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Load stratified sample ──
    print("=" * 60)
    print("STEP 1: Loading data sample...")
    print("=" * 60)
    loader = DataLoader(Path(settings.original_data_dir))
    sample = loader.stratified_sample(n=args.sample)
    sample_path = processed_dir / "sample.csv"
    loader.save_sample(sample, sample_path)

    # ── 2. Clean ──
    print("\n" + "=" * 60)
    print("STEP 2: Cleaning text...")
    print("=" * 60)
    cleaner = DataCleaner()
    cleaned = cleaner.process(sample)
    cleaned_path = processed_dir / "sample_cleaned.csv"
    cleaned.to_csv(cleaned_path, index=False, encoding="utf-8-sig")
    print(f"  Cleaned data saved to {cleaned_path}")

    # ── 3. Extract entities & relations ──
    triples_path = args.output or str(processed_dir / "triples.json")

    if args.skip_extract and Path(triples_path).exists():
        print("\n" + "=" * 60)
        print("STEP 3: Skipping extraction (using saved triples)...")
        print("=" * 60)
        with open(triples_path, "r", encoding="utf-8") as f:
            all_triples = json.load(f)
        print(f"  Loaded {len(all_triples)} triples from {triples_path}")
    else:
        print("\n" + "=" * 60)
        print(f"STEP 3: Extracting entities & relations via LLM ({settings.llm_model_name})...")
        print("=" * 60)

        checkpoint_path = str(processed_dir / "extraction_checkpoint.json")
        extractor = EntityRelationExtractor(temperature=0.3)
        all_triples = extractor.extract_from_dataframe(
            cleaned, text_col="answer", dept_col="department", delay=args.delay,
            checkpoint_path=checkpoint_path,
        )
        print(f"  Extracted {len(all_triples)} triples")

        # Deduplicate exact matches
        seen = set()
        deduped = []
        for t in all_triples:
            key = (t["head_entity"], t["relation"], t["tail_entity"])
            if key not in seen:
                seen.add(key)
                deduped.append(t)
        print(f"  After dedup: {len(deduped)} unique triples")
        all_triples = deduped

        # Save triples
        with open(triples_path, "w", encoding="utf-8") as f:
            json.dump(all_triples, f, ensure_ascii=False, indent=2)
        print(f"  Triples saved to {triples_path}")

    # ── 4. Import into Neo4j ──
    print("\n" + "=" * 60)
    print("STEP 4: Importing into Neo4j...")
    print("=" * 60)
    importer = Neo4jImporter()
    try:
        if args.clear:
            importer.clear_all()
        importer.create_constraints()
        counts = importer.import_triples(all_triples)
        print(f"\n  KG Stats: {counts['nodes']} nodes, {counts['edges']} edges")
        entity_types = importer.get_entity_types()
        if entity_types:
            print("  Entity types:")
            for etype, cnt in sorted(entity_types.items(), key=lambda x: -x[1]):
                print(f"    {etype}: {cnt}")
    finally:
        importer.close()

    print("\n" + "=" * 60)
    print("KG Construction Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
