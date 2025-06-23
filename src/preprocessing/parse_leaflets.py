import pymupdf4llm
import pathlib
import os
from typing import List


def convert_pdf_to_markdown(pdf_path: str, output_md_path: str) -> str:
    """
    Converts a PDF to markdown using pymupdf4llm and writes it to a file.
    """
    md_text = pymupdf4llm.to_markdown(pdf_path)
    pathlib.Path(output_md_path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(output_md_path).write_bytes(md_text.encode("utf-8"))
    print(f"Markdown written to {output_md_path}")
    return md_text


def process_pdf_directory(input_dir: str, output_dir: str) -> None:
    """
    Processes all PDF files in the input directory and saves their markdown versions in the output directory.
    """
    for file_name in os.listdir(input_dir):
        if file_name.lower().endswith(".pdf"):
            input_path = os.path.join(input_dir, file_name)
            output_path = os.path.join(output_dir, file_name.replace(".pdf", ".md"))
            convert_pdf_to_markdown(input_path, output_path)


def convert_pdfs_to_markdown_for_drugs(
    drugs: List[str], raw_dir: str = "data/raw", processed_dir: str = "data/interim"
) -> None:
    """
    Iterates over a list of drugs and processes their corresponding PDF files,
    converting them to markdown. Allows custom raw and processed directories.
    """
    for drug in drugs:
        drug_raw_dir = os.path.join(raw_dir, drug)
        drug_processed_dir = os.path.join(processed_dir, drug)
        process_pdf_directory(drug_raw_dir, drug_processed_dir)
