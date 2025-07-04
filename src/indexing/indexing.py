from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.embeddings import Embeddings  # Add this import
import os
from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np
import json
import torch
import subprocess


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


def store_embeddings(
    docs,
    collection_name,
    persist_dir="data/vector_db/chroma_langchain_db",
    model_name="sentence-transformers/all-mpnet-base-v2",
    device="auto",
):
    """
    Store document embeddings in a local ChromaDB vector database.

    Args:
        docs: List of document chunks to be embedded and stored
        collection_name: Name of the collection
        persist_dir: Directory where ChromaDB will persist the database
        model_name: HuggingFace embedding model name
        device: Device to use ('cuda', 'cpu', or 'auto')

    Returns:
        vector_store: The ChromaDB vector store instance
    """
    # Auto-detect device if not specified
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"🤖 Using embedding model: {model_name}")
    print(f"💻 Using device: {device}")

    # Handle Jina embeddings differently
    if model_name == "jinaai/jina-embeddings-v3":
        print("🎯 Detected Jina embeddings model - using custom implementation")
        embeddings = JinaEmbeddingFunction(model_name=model_name, device=device)
    else:
        # Standard HuggingFace embeddings
        embeddings = HuggingFaceEmbeddings(
            model_name=model_name, model_kwargs={"device": device}
        )

    collection_name = f"collection_{collection_name}"
    os.makedirs(persist_dir, exist_ok=True)

    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )

    for doc in tqdm(docs, desc=f"Storing embeddings for {collection_name}"):
        vector_store.add_documents([doc])

    print(
        f"Successfully stored {len(docs)} documents in collection '{collection_name}' at {persist_dir}"
    )

    return vector_store


class JinaEmbeddingFunction(Embeddings):
    """Custom embedding function for Jina embeddings model."""

    def __init__(self, model_name="jinaai/jina-embeddings-v3", device="auto"):
        from sentence_transformers import SentenceTransformer

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = SentenceTransformer(
            model_name, trust_remote_code=True, device=device
        )
        self.task = "retrieval.passage"  # For documents/passages

    def embed_documents(self, texts):
        """Embed a list of documents."""
        embeddings = self.model.encode(
            texts,
            task=self.task,
            prompt_name=self.task,
        )
        return embeddings.tolist()

    def embed_query(self, text):
        """Embed a single query."""
        query_task = "retrieval.query"  # Different task for queries
        embedding = self.model.encode(
            [text],
            task=query_task,
            prompt_name=query_task,
        )
        return embedding[0].tolist()

    def __call__(self, texts):
        """Make the class callable for ChromaDB compatibility."""
        if isinstance(texts, str):
            return self.embed_query(texts)
        else:
            return self.embed_documents(texts)


def plot_description_lengths(
    descriptions, title="ICD-11 Description Length Distribution"
):
    """
    Plot the distribution of description lengths to help decide on chunking strategy.

    Args:
        descriptions: List of ICD-11 description strings
        title: Plot title
    """
    # Extract description strings for length analysis
    description_texts = [item["description"] for item in descriptions]

    # Calculate lengths
    lengths = [len(desc) for desc in description_texts]

    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # Histogram
    ax1.hist(lengths, bins=20, alpha=0.7, color="skyblue", edgecolor="black")
    ax1.set_xlabel("Description Length (characters)")
    ax1.set_ylabel("Frequency")
    ax1.set_title("Histogram of Description Lengths")
    ax1.grid(True, alpha=0.3)

    # Add statistics to histogram
    mean_length = np.mean(lengths)
    median_length = np.median(lengths)
    ax1.axvline(
        mean_length, color="red", linestyle="--", label=f"Mean: {mean_length:.0f}"
    )
    ax1.axvline(
        median_length,
        color="orange",
        linestyle="--",
        label=f"Median: {median_length:.0f}",
    )
    ax1.legend()

    # Box plot
    ax2.boxplot(lengths, vert=True)
    ax2.set_ylabel("Description Length (characters)")
    ax2.set_title("Box Plot of Description Lengths")
    ax2.grid(True, alpha=0.3)

    # Overall title
    fig.suptitle(title, fontsize=16, fontweight="bold")

    # Print statistics
    print(f"📊 Description Length Statistics:")
    print(f"   Total descriptions: {len(descriptions)}")
    print(f"   Mean length: {mean_length:.1f} characters")
    print(f"   Median length: {median_length:.1f} characters")
    print(f"   Min length: {min(lengths)} characters")
    print(f"   Max length: {max(lengths)} characters")
    print(f"   Standard deviation: {np.std(lengths):.1f} characters")

    # Chunking recommendations
    print(f"\n🔧 Chunking Recommendations:")
    if max(lengths) > 1000:
        print(f"   ⚠️  Some descriptions are very long (max: {max(lengths)})")
        print(f"   Consider chunking with overlap for descriptions > 800 chars")
    elif max(lengths) > 500:
        print(f"   📝 Moderate length descriptions (max: {max(lengths)})")
        print(f"   Consider chunking for descriptions > 400 chars")
    else:
        print(f"   ✅ All descriptions are relatively short (max: {max(lengths)})")
        print(f"   Chunking may not be necessary")

    plt.tight_layout()
    plt.show()

    return {
        "lengths": lengths,
        "mean": mean_length,
        "median": median_length,
        "min": min(lengths),
        "max": max(lengths),
        "std": np.std(lengths),
    }


def convert_icd_to_documents(icd_descriptions):
    """
    Convert ICD-11 descriptions to LangChain Document objects.

    Args:
        icd_descriptions: List of dictionaries with "description", "code", "name", "url" fields

    Returns:
        List of Document objects with description as page_content and metadata
    """
    from langchain_core.documents import Document

    icd_docs = []
    for item in icd_descriptions:
        code = item.get("code", "")
        code_prefix = (
            code[0] if code else ""
        )  # Get first letter, empty string if no code

        doc = Document(
            page_content=item["description"],
            metadata={
                "code": code,
                "code_prefix": code_prefix,
                "name": item["name"],
                "url": item["url"],
                "type": "icd11_condition",
            },
        )
        icd_docs.append(doc)

    print(f"✅ Converted {len(icd_docs)} ICD descriptions to Document objects")
    return icd_docs


def convert_leaflets_to_documents(leaflet_data):
    """
    Convert a list of drug leaflet data dictionaries to LangChain Document objects.

    Args:
        leaflet_data: List of dictionaries with 'aic', 'aic_url', 'description' keys

    Returns:
        List of LangChain Document objects with drug-specific metadata
    """
    from langchain.schema import Document

    documents = []
    for item in leaflet_data:
        metadata = {
            "aic": item.get("aic"),
            "aic_url": item.get("aic_url"),
        }

        doc = Document(
            page_content=item["description"],
            metadata=metadata,
        )
        documents.append(doc)

    return documents


def load_section_files(data_dir):
    """
    Load all markdown files from a section directory and convert to a format
    suitable for indexing.
    """
    from pathlib import Path
    from src.llm_extraction.extraction import (
        extract_aic_from_filename,
        extract_sis_from_filename,
        generate_url,
    )

    section_data = []
    data_path = Path(data_dir)

    if not data_path.exists():
        raise FileNotFoundError(f"Directory not found: {data_dir}")

    for md_file in data_path.glob("*.md"):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if content:  # Only add non-empty files
            # Extract metadata
            aic = extract_aic_from_filename(md_file.name)
            aic6 = aic[:6] if aic and len(aic) >= 6 else None
            codice_sis = extract_sis_from_filename(md_file.name)
            url = generate_url(aic6, codice_sis)

            section_data.append(
                {
                    "aic": aic,
                    "aic_url": url,
                    "description": content,
                }
            )

    return section_data
