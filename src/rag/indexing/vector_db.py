import os
from tqdm import tqdm
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


def store_embeddings(all_splits, drug_name):
    """
    Store document embeddings in a local ChromaDB vector database, one collection per drug.

    Args:
        all_splits: List of document chunks to be embedded and stored
        drug_name: Name of the drug (used for collection name)

    Returns:
        vector_store: The ChromaDB vector store instance
    """
    # Define embedding model
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
        # model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    # Use drug_name as the collection name
    collection_name = f"collection_{drug_name.lower()}"

    # Define persist directory relative to the project root
    # Assuming this function is called from src/, go up one level to reach models/
    persist_dir = os.path.join("data", "vector_db", "chroma_langchain_db")

    # Create the directory if it doesn't exist
    os.makedirs(persist_dir, exist_ok=True)

    # Create vector store with embeddings
    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )

    # Use tqdm to show progress
    for chunk in tqdm(all_splits, desc=f"Storing embeddings for {drug_name}"):
        vector_store.add_documents([chunk])

    print(
        f"Successfully stored {len(all_splits)} documents in collection '{collection_name}' at {persist_dir}"
    )

    return vector_store
