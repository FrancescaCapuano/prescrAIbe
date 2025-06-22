import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


def store_embeddings(all_splits, raw_dir):
    """
    Store document embeddings in a local ChromaDB vector database.

    Args:
        all_splits: List of document chunks to be embedded and stored
        raw_dir: Directory path used to create a unique collection name

    Returns:
        vector_store: The ChromaDB vector store instance
    """
    # Define embedding model
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )

    # Create collection name based on raw_dir to avoid conflicts
    collection_name = f"collection_{os.path.basename(raw_dir)}"

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

    # Index chunks from split text
    vector_store.add_documents(documents=all_splits)

    print(
        f"Successfully stored {len(all_splits)} documents in vector database at {persist_dir}"
    )

    return vector_store
