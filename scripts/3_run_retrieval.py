"""
Script to run the contraindication similarity search pipeline: process pharmaceutical
contraindications and find similar ICD-11 conditions using vector embeddings.

Usage:
    python scripts/3_run_retrieval.py
    python scripts/3_run_retrieval.py --model jinaai/jina-embeddings-v3
    python scripts/3_run_retrieval.py --aic-codes 045034307 --category condition

    python scripts/3_run_retrieval.py --model jinaai/jina-embeddings-v3 --aic-codes 030705026 044077028 041445014 044856060 023779061 034949026 040409017 042342016 008679021 025373073 036906055 041508019 023892033 035077015 028282376 934521384 934521358 038016109 029354192 023309103 --category condition
    python scripts/3_run_retrieval.py --model jinaai/jina-embeddings-v2-base-en --aic-codes 030705026 044077028 041445014 044856060 023779061 034949026 040409017 042342016 008679021 025373073 036906055 041508019 023892033 035077015 028282376 934521384 934521358 038016109 029354192 023309103 --category condition
    python scripts/3_run_retrieval.py --model sentence-transformers/all-mpnet-base-v2 --aic-codes 030705026 044077028 041445014 044856060 023779061 034949026 040409017 042342016 008679021 025373073 036906055 041508019 023892033 035077015 028282376 934521384 934521358 038016109 029354192 023309103 --category condition
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
from src.retrieval.vector_db_retrieval import (
    ContraindicationRetriever,
    filter_contraindications_by_category,
    filter_contraindications_by_aic,
)
from src.retrieval.interaction_matrix import InteractionMatrixBuilder


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run contraindication similarity search"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="sentence-transformers/all-mpnet-base-v2",
        help="Embedding model name",
    )
    parser.add_argument("--category", type=str, default=None, help="Filter by category")
    parser.add_argument(
        "--aic-codes",
        type=str,
        nargs="+",
        default=None,
        help="Filter by AIC codes (space-separated list)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Fixed configuration parameters
    MAX_RESULTS = 50
    USE_STATISTICAL_FILTER = True
    DEVS = 1.25
    CHECKPOINT_FREQUENCY = 3

    # Generate paths based on model
    root_dir = Path(__file__).parent.parent
    model_name_clean = args.model.replace("/", "_").replace("-", "_")

    vectordb_path = (
        root_dir
        / "data"
        / "vector_dbs"
        / f"vector_db_{model_name_clean}"
        / "chroma_langchain_db"
    )
    contraindications_path = (
        root_dir / "data" / "contraindications" / "all_contraindications_verified.json"
    )
    results_path = root_dir / "data" / "interaction_results"

    print(f"\n📊 Configuration:")
    print(f"   Model: {args.model}")
    print(f"   Vector DB path: {vectordb_path}")
    print(f"   Max results per query: {MAX_RESULTS} (fixed)")
    print(
        f"   Statistical filtering: {'enabled' if USE_STATISTICAL_FILTER else 'disabled'} (fixed)"
    )
    print(f"   Checkpoint frequency: every {CHECKPOINT_FREQUENCY} AICs (fixed)")

    if args.category:
        print(f"   Category filter: {args.category}")
    if args.aic_codes:
        print(f"   AIC codes filter: {args.aic_codes}")

    # Validation
    if not vectordb_path.exists():
        print(f"❌ Vector database not found.")
        return

    # Load and filter data
    print(f"\n📂 Loading contraindications...")
    with open(contraindications_path, "r", encoding="utf-8") as f:
        contraindications_data = json.load(f)

    print(f"✅ Loaded {len(contraindications_data)} AICs")

    # Apply filtering
    if args.aic_codes:
        contraindications_data = filter_contraindications_by_aic(
            contraindications_data, args.aic_codes
        )

    if args.category:
        contraindications_data = filter_contraindications_by_category(
            contraindications_data, args.category
        )

    if not contraindications_data:
        print("❌ No data remaining after filtering.")
        return

    # Process
    retriever = ContraindicationRetriever(
        str(vectordb_path), str(results_path), model_name=args.model
    )

    print(f"\n🎯 Processing {len(contraindications_data)} AICs...")
    results = retriever.process_all_contraindications_file(
        contraindications_data,
        max_results=MAX_RESULTS,
        use_statistical_filter=USE_STATISTICAL_FILTER,
        devs=DEVS,
        save_checkpoint_every=CHECKPOINT_FREQUENCY,
    )

    # Save results
    output_file = retriever.save_all_results(results)
    total_contraindications = sum(
        len(aic_result["similarity_searches"]) for aic_result in results["aic_results"]
    )

    print(f"\n✅ Completed! Results: {output_file}")
    print(
        f"📊 Processed {len(results['aic_results'])} AICs, {total_contraindications:,} contraindications"
    )

    # Build and save interaction matrix
    # print(f"\n🔗 Building interaction matrix from results...")
    # matrix_builder = InteractionMatrixBuilder()
    # interaction_matrix = matrix_builder.build_interaction_matrix(results)
    # matrix_file = matrix_builder.save_interaction_matrix(interaction_matrix)

    # # Print matrix statistics
    # stats = matrix_builder.get_matrix_statistics(interaction_matrix)
    # print(f"\n📊 INTERACTION MATRIX STATISTICS:")
    # print(f"  Unique AIC codes: {stats['unique_aics']}")
    # print(f"  Unique ICD codes: {stats['unique_icds']}")
    # print(f"  🔢 Total possible combinations: {stats['total_possible_combinations']:,}")
    # print(f"  ✅ Actual unique combinations: {stats['actual_unique_combinations']:,}")
    # print(f"  📋 Total interaction entries: {stats['total_contraindications']:,}")
    # print(
    #     f"  📈 Avg entries per combination: {stats['avg_contraindications_per_pair']:.2f}"
    # )
    # print(f"  📈 Coverage: {stats['coverage_percentage']:.2f}%")
    # print(f"  📊 Matrix density: {stats['matrix_density']:.6f}")

    # print(f"\n💾 Interaction matrix saved: {matrix_file}")


if __name__ == "__main__":
    main()
