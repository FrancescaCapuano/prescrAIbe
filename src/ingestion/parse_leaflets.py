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


def convert_pdfs_to_markdown_for_drugs(drugs: List[str]) -> None:
    """
    Iterates over a list of drugs and processes their corresponding PDF files,
    converting them to markdown.
    """
    for drug in drugs:
        raw_dir = f"data/raw/{drug}"
        interim_dir = f"data/interim/{drug}"
        process_pdf_directory(raw_dir, interim_dir)


def load_llama_documents(pdf_path: str) -> List[any]:
    """
    Loads LlamaIndex-compatible documents from a PDF.

    Args:
        pdf_path (str): Path to the input PDF.

    Returns:
        List[Any]: A list of LlamaIndexDocument objects.
    """
    md_read = pymupdf4llm.LlamaMarkdownReader()
    return md_read.load_data(pdf_path)


if __name__ == "__main__":
    drugs_to_process = ["CITALOPRAM", "AZITROMICINA"]
    convert_pdfs_to_markdown_for_drugs(drugs_to_process)
