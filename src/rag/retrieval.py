import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


def get_retriever(
    persist_dir: str,
    drug_name: str,
    embeddings_model_name: str = "sentence-transformers/all-mpnet-base-v2",
    collection_name: str = "collection_raw",
    search_k: int = 2,
):
    """
    Loads a Chroma vectorstore and returns a retriever object.

    Args:
        persist_directory (str): Path to the Chroma DB directory.
        embeddings (str): Name of the HuggingFace embedding model.
        search_k (int): Number of documents to retrieve.

    Returns:
        retriever: A retriever object for querying the vectorstore.
    """
    embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)
    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    return vector_store.as_retriever(
        search_kwargs={"k": search_k, "filter": {"drug": drug_name}}
    )


if __name__ == "__main__":
    persist_dir = "models/chroma_langchain_db"
    retriever = get_retriever(persist_dir, collection_name="collection_raw")
