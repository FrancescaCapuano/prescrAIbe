import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import torch
from tqdm import tqdm
from scipy.stats import median_abs_deviation


class JinaEmbeddingFunction:
    """Custom embedding function for Jina embeddings model compatible with ChromaDB."""

    def __init__(self, model_name="jinaai/jina-embeddings-v3", device="auto"):
        from sentence_transformers import SentenceTransformer

        device = "cuda" if device == "auto" and torch.cuda.is_available() else device
        self.model = SentenceTransformer(
            model_name, trust_remote_code=True, device=device
        )

    def __call__(self, texts):
        """ChromaDB expects this method for embedding."""
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(
            texts, task="retrieval.query", prompt_name="retrieval.query"
        ).tolist()


class ContraindicationRetriever:
    """Similarity search for contraindications against ICD-11 vector database."""

    def __init__(
        self,
        vectordb_path: str,
        results_path: str,
        model_name: str = "sentence-transformers/all-mpnet-base-v2",
    ):
        self.vectordb_path = Path(vectordb_path)
        self.results_path = Path(results_path)
        self.results_path.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.checkpoint_file = self.results_path / "checkpoint.json"

        self._init_embedding_model()
        self._init_chromadb()

    def _init_embedding_model(self):
        """Initialize embedding model based on model type."""
        print(f"🔧 Initializing embedding model: {self.model_name}")
        device = "cuda" if torch.cuda.is_available() else "cpu"

        if self.model_name == "jinaai/jina-embeddings-v3":
            print("🎯 Using Jina embeddings")
            self.embedding_function = JinaEmbeddingFunction(self.model_name, device)
        else:
            print("🎯 Using standard SentenceTransformer embeddings")
            self.embedding_function = (
                embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.model_name, device=device
                )
            )

    def _init_chromadb(self):
        """Initialize ChromaDB connection."""
        print("🔧 Connecting to ChromaDB...")
        self.client = chromadb.PersistentClient(
            path=str(self.vectordb_path), settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_collection("collection_icd_11")
        print(f"✅ Connected to collection with {self.collection.count():,} documents")

    def search(
        self,
        query: str,
        max_results: int = 100,
        use_statistical_filter: bool = False,
        devs: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """Perform similarity search with optional statistical filtering."""
        n_results = min(
            5000 if use_statistical_filter else max_results * 3, self.collection.count()
        )

        # Generate embedding and search
        query_embedding = self.embedding_function([query])
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            where={"code_prefix": {"$nin": ["M", "N", "P", "Q", "R", "V", "X"]}},
        )

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        # Format results
        formatted_results = [
            {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": (
                    results["metadatas"][0][i]
                    if results["metadatas"] and results["metadatas"][0]
                    else {}
                ),
                "distance": results["distances"][0][i],
            }
            for i in range(len(results["ids"][0]))
            if isinstance(
                (
                    results["metadatas"][0][i]
                    if results["metadatas"] and results["metadatas"][0]
                    else {}
                ),
                dict,
            )
        ]

        # Apply statistical filtering if requested
        if use_statistical_filter and len(formatted_results) > 1:
            distances = [r["distance"] for r in formatted_results]
            median = np.median(distances)
            mad = median_abs_deviation(distances)
            robust_z_scores = (distances - median) / mad
            formatted_results = [
                r for r, z in zip(formatted_results, robust_z_scores) if z > devs
            ]

        # Sort by distance and deduplicate by unique ICD-11 codes
        formatted_results.sort(key=lambda x: x["distance"])
        seen_codes = set()
        unique_results = []

        for result in formatted_results:
            code = result["metadata"].get("code", "")
            if code and code not in seen_codes:
                seen_codes.add(code)
                unique_results.append(result)
                if len(unique_results) >= max_results:
                    break

        return unique_results

    def _checkpoint_operations(self):
        """Checkpoint management methods."""

        def save_checkpoint(results: Dict[str, Any], current_aic_index: int):
            checkpoint_data = {
                "results": results,
                "current_aic_index": current_aic_index,
                "timestamp": datetime.now().isoformat(),
            }
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

        def load_checkpoint():
            if not self.checkpoint_file.exists():
                print("📄 No checkpoint found, starting fresh...")
                return None, 0

            print(f"📄 Found checkpoint file: {self.checkpoint_file}")
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)
                results = checkpoint_data["results"]
                current_aic_index = checkpoint_data["current_aic_index"]
                print(f"✅ Loaded checkpoint from {checkpoint_data['timestamp']}")
                print(f"🔄 Resuming from AIC index {current_aic_index}")
                return results, current_aic_index
            except Exception as e:
                print(f"❌ Error loading checkpoint: {e}")
                return None, 0

        def clear_checkpoint():
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                print("🗑️ Checkpoint file cleared")

        return save_checkpoint, load_checkpoint, clear_checkpoint

    def process_all_contraindications_file(
        self,
        contraindications_data: List[Dict],
        max_results: int = 100,
        use_statistical_filter: bool = False,
        devs: float = 2.0,
        save_checkpoint_every: int = 5,
    ) -> Dict[str, Any]:
        """Process ALL AICs from the contraindications file with checkpoint support."""
        save_checkpoint, load_checkpoint, clear_checkpoint = (
            self._checkpoint_operations()
        )

        # Load checkpoint or start fresh
        checkpoint_results, start_index = load_checkpoint()
        all_results = checkpoint_results or {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_aics": len(contraindications_data),
                "max_results_per_query": max_results,
                "use_statistical_filter": use_statistical_filter,
                "devs": devs if use_statistical_filter else None,
                "model_name": self.model_name,
            },
            "aic_results": [],
        }

        print(f"🚀 Processing {len(contraindications_data)} AICs")
        if start_index > 0:
            print(
                f"🔄 Resuming from AIC {start_index + 1}/{len(contraindications_data)}"
            )

        aic_pbar = tqdm(
            contraindications_data[start_index:],
            desc="Processing AICs",
            unit="AICs",
            colour="green",
            initial=start_index,
            total=len(contraindications_data),
        )

        try:
            for relative_index, aic_data in enumerate(aic_pbar):
                actual_index = start_index + relative_index
                aic = aic_data.get("aic", "unknown")
                contraindications = aic_data.get("contraindications", [])

                aic_pbar.set_postfix(
                    {
                        "Current AIC": aic,
                        "Contraindications": len(contraindications),
                        "Index": f"{actual_index + 1}/{len(contraindications_data)}",
                    }
                )

                aic_results = {
                    "aic": aic,
                    "aic_url": aic_data.get("url", ""),
                    "contraindications_count": len(contraindications),
                    "similarity_searches": [],
                }

                # Process contraindications
                for contraindication in tqdm(
                    contraindications,
                    desc=f"  {aic}",
                    unit="contraindications",
                    leave=False,
                ):
                    contraindication_id = contraindication.get("id", "unknown")
                    query = contraindication.get("context_eng", "")

                    if not query.strip():
                        continue

                    search_results = self.search(
                        query, max_results, use_statistical_filter, devs
                    )

                    if search_results:
                        aic_results["similarity_searches"].append(
                            {
                                "contraindication_id": contraindication_id,
                                "original_warning": {
                                    "italian": contraindication.get("warning_ita", ""),
                                    "english": contraindication.get("context_eng", ""),
                                    "context": contraindication.get("context", ""),
                                    "pretext": contraindication.get("pretext", ""),
                                },
                                "similar_documents": search_results,
                                "results_count": len(search_results),
                            }
                        )

                all_results["aic_results"].append(aic_results)

                # Save checkpoint periodically
                if (actual_index + 1) % save_checkpoint_every == 0:
                    save_checkpoint(all_results, actual_index + 1)
                    tqdm.write(f"💾 Checkpoint saved after AIC {actual_index + 1}")

        except KeyboardInterrupt:
            print(f"\n⚠️ Process interrupted! Saving checkpoint...")
            save_checkpoint(all_results, start_index + relative_index)
            print(f"💾 Progress saved. Resume by running the script again.")
            raise
        except Exception as e:
            print(f"\n❌ Error occurred: {e}")
            save_checkpoint(all_results, start_index + relative_index)
            print(f"💾 Progress saved. Resume by running the script again.")
            raise

        clear_checkpoint()
        return all_results

    def save_all_results(self, results: Dict[str, Any]) -> str:
        """Save results for all AICs to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name_clean = self.model_name.replace("/", "_").replace("-", "_")
        filename = f"interaction_results_{model_name_clean}_{timestamp}.json"
        filepath = self.results_path / filename

        print("💾 Saving final results to file...")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"✅ All results saved to: {filepath}")
        return str(filepath)


def filter_contraindications_by_category(
    contraindications_data: List[Dict], category: str
) -> List[Dict]:
    """Filter contraindications by category."""
    filtered_aics = []
    total_before = sum(
        len(aic_data.get("contraindications", []))
        for aic_data in contraindications_data
    )
    total_after = 0

    for aic_data in contraindications_data:
        filtered_contraindications = [
            contraindication
            for contraindication in aic_data.get("contraindications", [])
            if contraindication.get("category", "").lower() == category.lower()
        ]

        if filtered_contraindications:
            aic_data_copy = aic_data.copy()
            aic_data_copy["contraindications"] = filtered_contraindications
            filtered_aics.append(aic_data_copy)
            total_after += len(filtered_contraindications)

    print(
        f"📊 Category '{category}': {total_after}/{total_before} contraindications "
        f"({100*total_after/total_before:.1f}%) in {len(filtered_aics)} AICs"
    )
    return filtered_aics


def filter_contraindications_by_aic(
    contraindications_data: List[Dict], aic_codes: List[str]
) -> List[Dict]:
    """Filter contraindications by AIC codes."""
    # Convert to lowercase for case-insensitive matching
    aic_codes_lower = [code.lower().strip() for code in aic_codes]

    filtered_aics = []
    total_before = sum(
        len(aic_data.get("contraindications", []))
        for aic_data in contraindications_data
    )
    total_after = 0

    for aic_data in contraindications_data:
        aic_code = aic_data.get("aic", "").lower().strip()

        # Check if this AIC code is in our filter list
        if aic_code in aic_codes_lower:
            filtered_aics.append(aic_data)
            total_after += len(aic_data.get("contraindications", []))

    print(
        f"📊 AIC filtering: {total_after}/{total_before} contraindications "
        f"({100*total_after/total_before:.1f}%) in {len(filtered_aics)}/{len(contraindications_data)} AICs"
    )
    print(f"🎯 Filtered AICs: {[aic['aic'] for aic in filtered_aics]}")
    return filtered_aics


def show_categories():
    """Show available categories in the contraindications file."""
    root_dir = Path(__file__).parent.parent.parent
    contraindications_path = (
        root_dir / "data" / "contraindications" / "all_contraindications_verified.json"
    )

    with open(contraindications_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    category_counts = {}
    for aic_data in data:
        for contraindication in aic_data.get("contraindications", []):
            category = contraindication.get("category", "").lower()
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1

    print("\n📋 Available categories:")
    for i, (category, count) in enumerate(
        sorted(category_counts.items(), key=lambda x: x[1], reverse=True), 1
    ):
        print(f"   {i:2d}. {category:<25} ({count:,} contraindications)")


def show_aic_codes():
    """Show available AIC codes in the contraindications file."""
    root_dir = Path(__file__).parent.parent.parent
    contraindications_path = (
        root_dir / "data" / "contraindications" / "all_contraindications_verified.json"
    )

    with open(contraindications_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    aic_info = []
    for aic_data in data:
        aic_code = aic_data.get("aic", "")
        contraindications_count = len(aic_data.get("contraindications", []))
        aic_info.append((aic_code, contraindications_count))

    # Sort by contraindications count (descending)
    aic_info.sort(key=lambda x: x[1], reverse=True)

    print(f"\n📋 Available AIC codes ({len(aic_info)} total):")
    for i, (aic_code, count) in enumerate(aic_info, 1):
        print(f"   {i:3d}. {aic_code:<15} ({count:,} contraindications)")


def main():
    """Main execution."""
    import argparse
    import sys

    # Handle special commands
    if len(sys.argv) > 1:
        if sys.argv[1] == "--show-categories":
            show_categories()
            return
        elif sys.argv[1] == "--show-aic-codes":
            show_aic_codes()
            return

    parser = argparse.ArgumentParser(
        description="Run contraindication similarity search"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="sentence-transformers/all-mpnet-base-v2",
        help="Embedding model name",
    )
    parser.add_argument("--category", type=str, default=None, help="Filter by category")
    parser.add_argument(
        "--aic-codes",
        type=str,
        nargs="+",
        default=None,
        help="Filter by AIC codes (space-separated list, e.g., --aic-codes A10BA02 A10BF01)",
    )
    args = parser.parse_args()

    root_dir = Path(__file__).parent.parent.parent
    model_name_clean = args.model.replace("/", "_").replace("-", "_")

    # Paths
    vectordb_path = (
        root_dir
        / "data"
        / "vector_dbs"
        / f"vector_db_{model_name_clean}"
        / "chroma_langchain_db"
    )
    contraindications_path = (
        root_dir / "data" / "contraindications" / "all_contraindications_verified.json"
    )
    results_path = root_dir / "data" / "interaction_results"

    print(f"🤖 Using model: {args.model}")
    print(f"📁 Vector DB path: {vectordb_path}")

    if args.category:
        print(f"🏷️ Filtering by category: {args.category}")
    if args.aic_codes:
        print(f"🏷️ Filtering by AIC codes: {args.aic_codes}")

    if not vectordb_path.exists():
        print(
            f"❌ Vector database not found. Run: python scripts/run_indexing.py --model {args.model}"
        )
        return

    # Load and filter data
    print("📂 Loading contraindications file...")
    with open(contraindications_path, "r", encoding="utf-8") as f:
        contraindications_data = json.load(f)

    # Apply AIC filtering first (if specified)
    if args.aic_codes:
        print(f"🎯 Filtering by {len(args.aic_codes)} AIC codes")
        contraindications_data = filter_contraindications_by_aic(
            contraindications_data, args.aic_codes
        )

    # Apply category filtering (if specified)
    if args.category:
        print(f"🏷️ Filtering by category: {args.category}")
        contraindications_data = filter_contraindications_by_category(
            contraindications_data, args.category
        )

    if not contraindications_data:
        print(
            "❌ No data remaining after filtering. Please check your filter criteria."
        )
        return

    # Process
    retriever = ContraindicationRetriever(
        str(vectordb_path), str(results_path), model_name=args.model
    )

    print("\n🎯 Starting similarity search processing...")
    results = retriever.process_all_contraindications_file(
        contraindications_data,
        max_results=50,
        use_statistical_filter=True,
        devs=1.25,
        save_checkpoint_every=3,
    )

    # Save and report
    output_file = retriever.save_all_results(results)
    total_contraindications = sum(
        len(aic_result["similarity_searches"]) for aic_result in results["aic_results"]
    )

    print(f"\n🎉 COMPLETED! Results: {output_file}")
    print(
        f"📊 Processed {len(results['aic_results'])} AICs, {total_contraindications:,} contraindications"
    )


if __name__ == "__main__":
    main()
