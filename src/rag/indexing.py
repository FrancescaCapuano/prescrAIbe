from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import glob
import os
from tqdm import tqdm


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
    splits = []
    for pdf_file in pdf_files:
        print(f"Processing {pdf_file} ...")
        docs = load_pdf_documents(pdf_file)
        chunks = split_documents(docs)
        # Add metadata to each chunk
        for chunk in chunks:
            chunk.metadata["drug"] = drug
            chunk.metadata["source_pdf"] = os.path.basename(pdf_file)
        splits.extend(chunks)
        print(f"  {len(chunks)} splits.")
    return splits


def store_embeddings(splits, drug_name):
    """
    Store document embeddings in a local ChromaDB vector database, one collection per drug.

    Args:
        splits: List of document chunks to be embedded and stored
        drug_name: Name of the drug (used for collection name)

    Returns:
        vector_store: The ChromaDB vector store instance
    """
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )

    collection_name = f"collection_{drug_name.lower()}"
    persist_dir = os.path.join("data", "vector_db", "chroma_langchain_db")
    os.makedirs(persist_dir, exist_ok=True)

    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )

    for chunk in tqdm(splits, desc=f"Storing embeddings for {drug_name}"):
        vector_store.add_documents([chunk])

    print(
        f"Successfully stored {len(splits)} documents in collection '{collection_name}' at {persist_dir}"
    )

    return vector_store
