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

# from src.ICD.icd11_extractor import get_icd_description
from langchain.chains import RetrievalQA
from src.generation.generator import run_interaction_query  # <-- new import
from huggingface_hub import login

HF_TOKEN = os.getenv("HF_TOKEN")  # Or set your token directly here as a string
print(f"HF_TOKEN: {HF_TOKEN}")
if HF_TOKEN:
    login(token=HF_TOKEN)


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
        drug_name=args.drug_name,
        collection_name="collection_" + args.drug_name.lower(),
        search_k=2,  # Number of documents to retrieve
    )

    # Create the dynamic prompt for the interaction query
    # icd_description = get_icd_description(args.icd_code)  # Assuming this function exists
    icd_description = "Diabetes mellito di tipo 2"  # Placeholder for ICD description

    # Run the interaction query (get_llm is called inside this function)
    answer = run_interaction_query(
        retriever=retriever,
        icd_code=args.icd_code,
        icd_description=icd_description,
        drug_name=args.drug_name,
        custom_rag_prompt=create_dynamic_prompt(
            drug_name=args.drug_name,
            icd_code=args.icd_code,
            icd_description=icd_description,
        ),
    )

    print("Answer:", answer)
