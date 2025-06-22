"""
Script to run an interaction query using a drug name and ICD code.

Usage:
    python scripts/run_interaction_query.py --icd-code E11 --drug-name CITALOPRAM
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
from src.prompt.prompt import create_dynamic_prompt
from src.retrieval.retriever import get_retriever
from src.ICD-retrieval.icd11_extractor import get_icd_description
from langchain.chains import RetrievalQA
from src.generation.generator import run_interaction_query  # <-- new import


def parse_args():
    parser = argparse.ArgumentParser(description="Run a drug-ICD interaction query.")
    parser.add_argument("--icd-code", required=True, help="ICD code for the condition.")
    parser.add_argument("--drug-name", required=True, help="Drug name.")
    parser.add_argument(
        "--persist-dir",
        type=str,
        default="data/vector_db/chroma_langchain_db",
        help="Path to Chroma DB directory.",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default="collection_raw",
        help="Chroma collection name.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Set up retriever
    retriever = get_retriever(
        persist_dir=args.persist_dir,
        collection_name=args.collection_name,
    )

    # Create the dynamic prompt for the interaction query
    icd_description = get_icd_description(args.icd_code)  # Assuming this function exists

    # Run the interaction query (get_llm is called inside this function)
    answer = run_interaction_query(
        retriever=retriever,
        icd_code=args.icd_code,
        drug_name=args.drug_name,
        custom_rag_prompt=create_dynamic_prompt(
            drug_name=args.drug_name,
            icd_code=args.icd_code,
            icd_description="",
        ),
    )

    print("Answer:", answer)
