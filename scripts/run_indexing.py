"""
Script to run the ICD-11 indexing pipeline: load, process, and embed ICD-11 descriptions.

Usage:
    python scripts/run_indexing.py --data-file data/ICD-codes/icd11_vectordb_base.json
    python scripts/run_indexing.py --chunk-size 600 --chunk-overlap 100
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
        "--data-file",
        type=str,
        default="../../data/ICD-codes/icd11_vectordb_base.json",
        help="Path to ICD-11 descriptions JSON file",
    )
    parser.add_argument(
        "--persist-dir",
        type=str,
        default="../../data/vector_db/chroma_langchain_db",
        help="Directory to persist ChromaDB database",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=600,
        help="Maximum chunk size for text splitting",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Overlap between chunks",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Check if CUDA is available and diagnose setup
    diagnose_cuda()

    # Load ICD-11 data
    print(f"📂 Loading ICD-11 data from: {args.data_file}")
    with open(args.data_file, "r", encoding="utf-8") as f:
        icd_descriptions = json.load(f)
    print(f"✅ Loaded {len(icd_descriptions)} ICD descriptions")

    # Plot description length distribution
    chunking_recommended = plot_description_lengths(
        icd_descriptions, "ICD-11 Description Lengths"
    )

    # Convert to Document objects
    icd_docs = convert_icd_to_documents(icd_descriptions)

    # Process based on chunking recommendation
    if chunking_recommended:
        print(f"\n📝 Chunking recommended - splitting documents > 800 characters...")
        chunks = split_documents(
            icd_docs, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap
        )
        print(f"📄 Created {len(chunks)} chunks from {len(icd_docs)} descriptions")

        # Store embeddings of chunks
        vector_store = store_embeddings(chunks, "icd_11", args.persist_dir)
    else:
        print(f"\n✅ No chunking needed - descriptions are ≤ 800 characters")
        print(f"📄 Using {len(icd_docs)} documents directly (no chunking)")

        # Store embeddings of full descriptions
        vector_store = store_embeddings(icd_docs, "icd_11", args.persist_dir)

    print(f"\n✅ ICD-11 embeddings stored successfully!")
    print(f"🔍 Vector store collection: 'collection_icd_11'")
    print(f"📁 Persist directory: {args.persist_dir}")


if __name__ == "__main__":
    main()
