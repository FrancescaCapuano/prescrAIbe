"""
Script to run an interaction query using a drug name and ICD code.

Usage:
    python scripts/run_interaction_query.py --icd-code 1A40.0 --drug-name CITALOPRAM
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
from src.rag.prompt import create_dynamic_prompt
from src.rag.retrieval import get_retriever
from src.rag.generation import run_interaction_query
from src.ICD.icd11_concatenate import get_icd_description
from langchain.chains import RetrievalQA
from huggingface_hub import login
import torch

HF_TOKEN = os.getenv("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

torch.cuda.empty_cache()


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

    """
    # Get the ICD description
    icd_description = get_icd_description(
        args.icd_code,
        json_file_path="data/ICD-codes/icd11_all_codes_chapter_1_all_digits.json",
    )

    print(f"ICD Description for {args.icd_code}: {icd_description}")
    """
    icd_description = "placeholder"
    # Set up retriever
    retriever = get_retriever(
        persist_dir=args.persist_dir,
        drug_name=args.drug_name,
        collection_name="collection_" + args.drug_name.lower(),
        search_k=2,  # Number of documents to retrieve
    )

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
