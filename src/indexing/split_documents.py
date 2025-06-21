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


def split_documents(docs, chunk_size=1000, chunk_overlap=200):
    """
    Splits documents into chunks using RecursiveCharacterTextSplitter.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    return text_splitter.split_documents(docs)


def split_documents_for_drugs(drugs_to_process, raw_dir="data/raw", flatten=False):
    """
    For each drug in drugs_to_process, loads all PDFs in its raw_dir subfolder,
    splits them, and returns:
      - a dict: {drug: {pdf_file: splits}} if flatten=False (default)
      - a flat list of all splits if flatten=True
    """
    results = {}
    for drug in drugs_to_process:
        drug_dir = os.path.join(raw_dir, drug)
        pdf_files = glob.glob(os.path.join(drug_dir, "*.pdf"))
        drug_results = {}
        for pdf_file in pdf_files:
            print(f"Processing {pdf_file} ...")
            docs = load_pdf_documents(pdf_file)
            splits = split_documents(docs)
            drug_results[os.path.basename(pdf_file)] = splits
            print(f"  {len(splits)} splits.")
        results[drug] = drug_results
    return [doc for drug in results.values() for pdf in drug.values() for doc in pdf]


if __name__ == "__main__":
    drugs_to_process = ["CITALOPRAM", "AZITROMICINA"]
    all_splits = split_documents_for_drugs(drugs_to_process, flatten=True)
