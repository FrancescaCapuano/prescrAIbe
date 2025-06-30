"""
Script to run the ICD-11 indexing pipeline: load, process, and embed ICD-11 descriptions.

Usage:
    python scripts/run_indexing.py
    python scripts/run_indexing.py --model sentence-transformers/all-MiniLM-L6-v2
"""

import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
from dev.diagnose_cuda import diagnose_cuda
from src.indexing.indexing import (
    plot_description_lengths,
    convert_icd_to_documents,
    split_documents,
    store_embeddings,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run ICD-11 indexing pipeline.")
    parser.add_argument(
        "--model",
        type=str,
        default="sentence-transformers/all-mpnet-base-v2",
        help="HuggingFace embedding model name",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Fixed configuration parameters
    DATA_FILE = "data/ICD-codes/icd11_vectordb_base.json"
    CHUNK_SIZE = 600
    CHUNK_OVERLAP = 100

    # Generate persist directory name based on model
    model_name_clean = args.model.replace("/", "_").replace("-", "_")
    persist_dir = f"data/vector_dbs/vector_db_{model_name_clean}/chroma_langchain_db"

    print(f"\n📊 Configuration:")
    print(f"   Data file: {DATA_FILE} (fixed)")
    print(f"   Persist directory: {persist_dir}")
    print(f"   Model: {args.model}")
    print(f"   Chunk size: {CHUNK_SIZE} (fixed)")
    print(f"   Chunk overlap: {CHUNK_OVERLAP} (fixed)")

    # Load ICD-11 data
    print(f"\n📂 Loading ICD-11 data from: {DATA_FILE}")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        icd_descriptions = json.load(f)
    print(f"✅ Loaded {len(icd_descriptions)} ICD descriptions")

    # Plot description length distribution
    stats = plot_description_lengths(icd_descriptions, "ICD-11 Description Lengths")

    # Decision on chunking
    chunking_recommended = stats["max"] > 800

    # Convert to Document objects
    icd_docs = convert_icd_to_documents(icd_descriptions)

    # Process based on chunking recommendation
    if chunking_recommended:
        print(f"\n📝 Chunking recommended - splitting documents > 800 characters...")
        chunks = split_documents(
            icd_docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        print(f"📄 Created {len(chunks)} chunks from {len(icd_docs)} descriptions")

        # Store embeddings of chunks
        vector_store = store_embeddings(
            chunks, "icd_11", persist_dir, model_name=args.model
        )
    else:
        print(f"\n✅ No chunking needed - descriptions are ≤ 800 characters")
        print(f"📄 Using {len(icd_docs)} documents directly (no chunking)")

        # Store embeddings of full descriptions
        vector_store = store_embeddings(
            icd_docs, "icd_11", persist_dir, model_name=args.model
        )

    print(f"\n✅ ICD-11 embeddings stored successfully!")
    print(f"🔍 Vector store collection: 'collection_icd_11'")
    print(f"📁 Persist directory: {persist_dir}")
    print(f"🤖 Model used: {args.model}")


if __name__ == "__main__":
    main()
