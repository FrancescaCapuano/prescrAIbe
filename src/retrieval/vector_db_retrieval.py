import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import torch
from tqdm import tqdm


class ContraindicationRetriever:
    """Similarity search for contraindications against ICD-11 vector database."""

    def __init__(self, vectordb_path: str, results_path: str):
        self.vectordb_path = Path(vectordb_path)
        self.results_path = Path(results_path)
        self.results_path.mkdir(parents=True, exist_ok=True)

        # Checkpoint file path
        self.checkpoint_file = self.results_path / "checkpoint.json"

        # Initialize embedding model (same as indexing)
        print("🔧 Initializing embedding model...")
        self.embedding_function = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="sentence-transformers/all-mpnet-base-v2",
                device="cuda" if torch.cuda.is_available() else "cpu",
            )
        )

        # Initialize ChromaDB
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
        std_devs: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """Perform similarity search with optional statistical filtering."""

        # Determine number of results to fetch
        n_results = min(
            5000 if use_statistical_filter else max_results, self.collection.count()
        )

        # Generate embedding and search
        query_embedding = self.embedding_function([query])
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"][0]:
            return []

        # Format results
        formatted_results = []
        for i in range(len(results["ids"][0])):
            formatted_results.append(
                {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] or {},
                    "distance": results["distances"][0][i],
                }
            )

        # Apply statistical filtering if requested
        if use_statistical_filter and len(formatted_results) > 1:
            distances = [r["distance"] for r in formatted_results]
            mean_dist = np.mean(distances)
            std_dist = np.std(distances)
            cutoff = mean_dist - (std_devs * std_dist)

            filtered_results = [r for r in formatted_results if r["distance"] <= cutoff]

            # Sort and limit to max_results
            filtered_results.sort(key=lambda x: x["distance"])
            final_results = filtered_results[:max_results]

            return final_results
        else:
            # Sort and limit for non-statistical filtering
            formatted_results.sort(key=lambda x: x["distance"])
            return formatted_results[:max_results]

    def save_checkpoint(self, results: Dict[str, Any], current_aic_index: int):
        """Save current progress to checkpoint file."""
        checkpoint_data = {
            "results": results,
            "current_aic_index": current_aic_index,
            "timestamp": datetime.now().isoformat(),
        }

        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

    def load_checkpoint(self):
        """Load checkpoint if it exists."""
        if self.checkpoint_file.exists():
            print(f"📄 Found checkpoint file: {self.checkpoint_file}")
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)

                results = checkpoint_data["results"]
                current_aic_index = checkpoint_data["current_aic_index"]
                timestamp = checkpoint_data["timestamp"]

                print(f"✅ Loaded checkpoint from {timestamp}")
                print(f"🔄 Resuming from AIC index {current_aic_index}")
                print(f"📊 Already processed {len(results['aic_results'])} AICs")

                return results, current_aic_index
            except Exception as e:
                print(f"❌ Error loading checkpoint: {e}")
                print("🔄 Starting fresh...")
                return None, 0
        else:
            print("📄 No checkpoint found, starting fresh...")
            return None, 0

    def clear_checkpoint(self):
        """Clear checkpoint file after successful completion."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            print("🗑️ Checkpoint file cleared")

    def process_all_contraindications_file(
        self,
        contraindications_data: Any,
        max_results: int = 100,
        use_statistical_filter: bool = False,
        std_devs: float = 2.0,
        save_checkpoint_every: int = 5,  # Save checkpoint every N AICs
    ) -> Dict[str, Any]:
        """Process ALL AICs from the contraindications file with checkpoint support."""

        # Handle the full JSON structure - it's a list of AIC objects
        if not isinstance(contraindications_data, list):
            raise ValueError("Expected a list of AIC objects")

        # Try to load existing checkpoint
        checkpoint_results, start_index = self.load_checkpoint()

        if checkpoint_results:
            # Resume from checkpoint
            all_results = checkpoint_results
        else:
            # Start fresh
            all_results = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_aics": len(contraindications_data),
                    "max_results_per_query": max_results,
                    "use_statistical_filter": use_statistical_filter,
                    "std_devs": std_devs if use_statistical_filter else None,
                },
                "aic_results": [],
            }

        print(f"🚀 Processing {len(contraindications_data)} AICs from the entire file")

        if start_index > 0:
            print(
                f"🔄 Resuming from AIC {start_index + 1}/{len(contraindications_data)}"
            )

        # Main progress bar for AICs (start from checkpoint)
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

                # Process contraindications with nested progress bar
                contraindication_pbar = tqdm(
                    contraindications,
                    desc=f"  {aic}",
                    unit="contraindications",
                    leave=False,
                    colour="blue",
                )

                for contraindication in contraindication_pbar:
                    contraindication_id = contraindication.get("id", "unknown")
                    query = contraindication.get("context_eng", "")

                    contraindication_pbar.set_postfix({"ID": contraindication_id})

                    if not query.strip():
                        tqdm.write(
                            f"  ⚠️ Empty query for contraindication {contraindication_id}"
                        )
                        continue

                    search_results = self.search(
                        query, max_results, use_statistical_filter, std_devs
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
                    else:
                        tqdm.write(
                            f"    ⚠️ No results for contraindication {contraindication_id}"
                        )

                all_results["aic_results"].append(aic_results)

                # Save checkpoint every N AICs
                if (actual_index + 1) % save_checkpoint_every == 0:
                    self.save_checkpoint(all_results, actual_index + 1)
                    tqdm.write(f"💾 Checkpoint saved after AIC {actual_index + 1}")

        except KeyboardInterrupt:
            print(f"\n⚠️ Process interrupted! Saving checkpoint...")
            self.save_checkpoint(all_results, start_index + relative_index)
            print(f"💾 Progress saved. Resume by running the script again.")
            raise
        except Exception as e:
            print(f"\n❌ Error occurred: {e}")
            self.save_checkpoint(all_results, start_index + relative_index)
            print(f"💾 Progress saved. Resume by running the script again.")
            raise

        # Clear checkpoint on successful completion
        self.clear_checkpoint()
        return all_results

    def save_all_results(self, results: Dict[str, Any]) -> str:
        """Save results for all AICs to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"similarity_results_final_{timestamp}.json"
        filepath = self.results_path / filename

        print("💾 Saving final results to file...")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"✅ All results saved to: {filepath}")
        return str(filepath)


def main():
    """Main execution."""
    root_dir = Path(__file__).parent.parent.parent

    VECTORDB_PATH = root_dir / "data" / "vector_db" / "chroma_langchain_db"
    CONTRAINDICATIONS_PATH = (
        root_dir / "data" / "contraindications" / "all_contraindications_verified.json"
    )
    RESULTS_PATH = root_dir / "data" / "interaction_results"

    # Load data
    print("📂 Loading contraindications file...")
    with open(CONTRAINDICATIONS_PATH, "r", encoding="utf-8") as f:
        contraindications_data = json.load(f)

    print(f"✅ Loaded contraindications file with {len(contraindications_data)} AICs")

    # Initialize retriever and process ALL AICs
    retriever = ContraindicationRetriever(str(VECTORDB_PATH), str(RESULTS_PATH))

    # Process with progress monitoring and checkpoint support
    print("\n🎯 Starting similarity search processing...")
    results = retriever.process_all_contraindications_file(
        contraindications_data,
        max_results=250,
        use_statistical_filter=True,
        std_devs=2.5,
        save_checkpoint_every=3,  # Save every 3 AICs
    )

    # Save and report
    output_file = retriever.save_all_results(results)

    print(f"\n🎉 COMPLETED PROCESSING ALL AICs!")
    print(f"📁 Results: {output_file}")
    print(f"📊 Processed {len(results['aic_results'])} AICs")

    # Summary statistics
    total_contraindications = sum(
        len(aic_result["similarity_searches"]) for aic_result in results["aic_results"]
    )
    print(f"📈 Total contraindications processed: {total_contraindications:,}")

    # Calculate average results per contraindication
    if total_contraindications > 0:
        total_results = sum(
            sum(
                len(search["similar_documents"])
                for search in aic_result["similarity_searches"]
            )
            for aic_result in results["aic_results"]
        )
        avg_results = total_results / total_contraindications
        print(f"📊 Average results per contraindication: {avg_results:.1f}")


if __name__ == "__main__":
    main()
