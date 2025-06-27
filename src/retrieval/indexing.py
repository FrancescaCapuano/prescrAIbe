from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import glob
import os
from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np
from langchain_core.documents import Document
import json
import warnings

# Try different CUDA environment fixes
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

# Import torch after setting environment
import torch

# Force CUDA reinitialization
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    torch.cuda.init()


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


def store_embeddings(docs, collection_name):
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

    collection_name = f"collection_{collection_name}"
    persist_dir = os.path.join("data", "vector_db", "chroma_langchain_db")
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

    chunking_recommended = False

    # Decision on chunking
    if stats["max"] > 800:
        print(f"\n📝 Chunking recommended.")
        chunking_recommended = True
    else:
        print(
            f"\n✅ No chunking needed - descriptions are short enough for direct embedding"
        )
    return chunking_recommended


def convert_icd_to_documents(icd_descriptions):
    """
    Convert ICD-11 descriptions to LangChain Document objects.

    Args:
        icd_descriptions: List of dictionaries with "description", "code", "name", "url" fields

    Returns:
        List of Document objects with description as page_content and metadata
    """
    from langchain_core.documents import Document

    icd_docs = [
        Document(
            page_content=item["description"],
            metadata={
                "code": item["code"],
                "name": item["name"],
                "url": item["url"],
                "type": "icd11_condition",
            },
        )
        for item in icd_descriptions
    ]

    print(f"✅ Converted {len(icd_docs)} ICD descriptions to Document objects")
    return icd_docs


# Test usage
if __name__ == "__main__":
    # Diagnose CUDA setup
    import subprocess

    print("🔍 CUDA Diagnostics:")
    try:
        # Check if nvidia-smi works
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ nvidia-smi works - GPU hardware detected")
        else:
            print("❌ nvidia-smi failed")
    except:
        print("❌ nvidia-smi not found")

    # Check PyTorch CUDA
    print(f"PyTorch CUDA available: {torch.cuda.is_available()}")
    print(f"PyTorch CUDA device count: {torch.cuda.device_count()}")

    if torch.cuda.is_available():
        print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
        device = "cuda"
    else:
        print("Using CPU for embeddings")
        device = "cpu"

    with open(
        "../../data/ICD-codes/icd11_vectordb_base.json", "r", encoding="utf-8"
    ) as f:
        icd_descriptions = json.load(f)

    # Plot description length distribution
    chunking_recommended = plot_description_lengths(
        icd_descriptions, "ICD-11 Description Lengths"
    )

    # Convert to Document objects first
    icd_docs = convert_icd_to_documents(icd_descriptions)

    if chunking_recommended:
        print(f"\n📝 Chunking recommended - splitting documents > 800 characters...")

        # Split documents with appropriate chunk size
        chunks = split_documents(icd_docs, chunk_size=600, chunk_overlap=100)
        print(f"📄 Created {len(chunks)} chunks from {len(icd_docs)} descriptions")

        # Store embeddings of chunks
        vector_store = store_embeddings(chunks, "icd_11")

    else:
        print(f"\n✅ No chunking needed - descriptions are ≤ 800 characters")
        print(f"📄 Using {len(icd_docs)} documents directly (no chunking)")

        # Store embeddings of full descriptions
        vector_store = store_embeddings(icd_docs, "icd_11")

    print(f"\n✅ ICD-11 embeddings stored successfully!")
    print(f"🔍 Vector store collection: 'collection_icd_11'")
    print(f"📁 Persist directory: data/vector_db/chroma_langchain_db")
