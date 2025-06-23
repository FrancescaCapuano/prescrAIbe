from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import glob
import os


def load_pdf_documents(file_path: str):
    """
    Loads a PDF and returns a list of Document objects (one per page).
    """
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    return pages


def split_documents(docs, chunk_size=500, chunk_overlap=200):
    """
    Splits documents into chunks using RecursiveCharacterTextSplitter.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    return text_splitter.split_documents(docs)


def split_documents_for_drug(drug, raw_dir="data/raw"):
    """
    Loads all PDFs for a single drug in its raw_dir subfolder,
    splits them, and returns a flat list of all document chunks.
    Adds metadata to each chunk.
    """
    drug_dir = os.path.join(raw_dir, drug)
    pdf_files = glob.glob(os.path.join(drug_dir, "*.pdf"))
    drug_splits = []
    for pdf_file in pdf_files:
        print(f"Processing {pdf_file} ...")
        docs = load_pdf_documents(pdf_file)
        splits = split_documents(docs)
        # Add metadata to each split
        for chunk in splits:
            chunk.metadata["drug"] = drug
            chunk.metadata["source_pdf"] = os.path.basename(pdf_file)
        drug_splits.extend(splits)
        print(f"  {len(splits)} splits.")
    return drug_splits


if __name__ == "__main__":
    drugs_to_process = ["CITALOPRAM", "AZITROMICINA"]
    for drug in drugs_to_process:
        print(f"Processing drug: {drug}")
        splits = split_documents_for_drug(drug)
        print(f"Total splits for {drug}: {len(splits)}")
