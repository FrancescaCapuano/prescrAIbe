import json
import os
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import pandas as pd
from datetime import datetime
import torch
import matplotlib.pyplot as plt
import numpy as np


class ContraindicationRetriever:
    """
    Similarity search system for contraindication warnings against vector database.
    """

    def __init__(self, vectordb_path: str, results_path: str):
        self.vectordb_path = Path(vectordb_path)
        self.results_path = Path(results_path)
        self.client = None
        self.collection = None

        # Create results directory if it doesn't exist
        self.results_path.mkdir(parents=True, exist_ok=True)

        # Initialize the same embedding model using ChromaDB's native function
        print("Initializing embedding model...")
        self.embedding_function = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="sentence-transformers/all-mpnet-base-v2",
                device="cuda" if torch.cuda.is_available() else "cpu",
            )
        )
        print(f"Using device: {'cuda' if torch.cuda.is_available() else 'cpu'}")

    def initialize_chroma_client(self):
        """Initialize ChromaDB client and get collection."""
        try:
            # Initialize ChromaDB client with persistent storage
            self.client = chromadb.PersistentClient(
                path=str(self.vectordb_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )

            # First, let's see what collections exist
            collections = self.client.list_collections()
            print(f"Available collections: {[c.name for c in collections]}")

            if not collections:
                raise ValueError("No collections found in the vector database")

            # Try to get the collection - first try without embedding function (for compatibility)
            collection_name = "langchain"  # or use collections[0].name

            try:
                # Try getting collection without embedding function first
                self.collection = self.client.get_collection(name=collection_name)
                print(
                    f"✅ Connected to collection '{collection_name}' without embedding function"
                )
            except chromadb.errors.NotFoundError:
                # If 'langchain' doesn't exist, use the first available collection
                collection_name = collections[0].name
                self.collection = self.client.get_collection(name=collection_name)
                print(f"✅ Connected to collection '{collection_name}' (fallback)")

            # Debug: Check collection contents
            collection_count = self.collection.count()
            print(f"Collection contains {collection_count} documents")

            if collection_count == 0:
                raise ValueError("Collection is empty - no documents to search against")

            # Debug: Show a sample of what's in the collection
            sample = self.collection.peek(limit=3)
            print(f"Sample documents in collection:")
            for i, doc in enumerate(sample["documents"]):
                print(f"  Doc {i+1}: {doc[:100]}...")

            # Test a simple query using the external embedding function
            try:
                # We'll handle embedding manually in the search function
                print("✅ Collection initialized successfully")
            except Exception as test_error:
                print(f"⚠️ WARNING: Collection access issue - {test_error}")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize ChromaDB client: {e}")

    def load_contraindications(self, json_path: str) -> Any:
        """Load contraindications from JSON file."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load contraindications: {e}")

    def perform_similarity_search(
        self, query: str, similarity_threshold: float = None, max_results: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search for a single query with optional threshold and result limit.

        Args:
            query: English warning text to search for
            similarity_threshold: Maximum distance threshold (smaller = more similar). If None, no filtering.
            max_results: Maximum number of results to retrieve (default: 1000)

        Returns:
            List of similarity search results
        """
        try:
            print(f"Searching for: '{query[:80]}...'")
            if similarity_threshold is not None:
                print(f"Using similarity threshold: {similarity_threshold}")

            # Get the total number of documents in the collection
            total_docs = self.collection.count()
            print(f"Total documents in collection: {total_docs}")

            # Use the smaller of max_results or total_docs
            n_results = min(max_results, total_docs)
            print(f"Requesting {n_results} results (limit: {max_results})")

            # Method 1: Try with query_texts (ChromaDB will handle embedding)
            try:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
                print(f"✅ Used query_texts method")
            except Exception as e1:
                print(f"query_texts method failed: {e1}")

                # Method 2: Try with manual embedding
                try:
                    query_embedding = self.embedding_function([query])
                    results = self.collection.query(
                        query_embeddings=query_embedding,
                        n_results=n_results,
                        include=["documents", "metadatas", "distances"],
                    )
                    print(f"✅ Used manual embedding method")
                except Exception as e2:
                    print(f"Manual embedding method also failed: {e2}")
                    return []

            print(f"Raw results structure: {type(results)}")
            print(f"Results keys: {results.keys() if results else 'None'}")

            if not results or not results.get("ids") or not results["ids"][0]:
                print(f"No results returned for query")
                return []

            print(f"Found {len(results['ids'][0])} results")

            # Structure results for better readability - only using distance
            formatted_results = []
            for i in range(len(results["ids"][0])):
                result = {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": (
                        results["metadatas"][0][i] if results["metadatas"][0] else {}
                    ),
                    "distance": results["distances"][0][i],
                }
                formatted_results.append(result)

            print(f"  Processed {len(formatted_results)} results")

            # Apply similarity threshold filtering if specified
            if similarity_threshold is not None:
                filtered_results = [
                    r
                    for r in formatted_results
                    if r["distance"] <= similarity_threshold
                ]
                print(
                    f"  After threshold filtering ({similarity_threshold}): {len(filtered_results)} results"
                )
                return filtered_results

            return formatted_results

        except Exception as e:
            print(f"Error in similarity search for query '{query[:50]}...': {e}")
            print(f"Error type: {type(e)}")
            import traceback

            traceback.print_exc()
            return []

    def create_individual_histogram(
        self, contraindication_id: str, aic: str, distances: List[float]
    ) -> Dict[str, Any]:
        """
        Create a histogram for a single contraindication ID and return histogram data.

        Args:
            contraindication_id: ID of the contraindication
            aic: AIC code identifier
            distances: List of distance values from the search

        Returns:
            Dictionary containing histogram data and statistics
        """
        try:
            # Create histogram data
            hist_counts, hist_bins = np.histogram(distances, bins=50)

            # Create and save the plot
            plt.figure(figsize=(12, 8))
            plt.hist(distances, bins=50, alpha=0.7, color="blue", edgecolor="black")
            plt.title(
                f"Distance Distribution for AIC: {aic}, Contraindication ID: {contraindication_id}\n(Total distances: {len(distances)})"
            )
            plt.xlabel("Distance")
            plt.ylabel("Frequency")
            plt.grid(True, alpha=0.3)

            # Add statistics to the plot
            mean_dist = np.mean(distances)
            median_dist = np.median(distances)
            std_dist = np.std(distances)

            plt.axvline(
                mean_dist,
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"Mean: {mean_dist:.4f}",
            )
            plt.axvline(
                median_dist,
                color="green",
                linestyle="--",
                linewidth=2,
                label=f"Median: {median_dist:.4f}",
            )

            plt.legend()

            # Save histogram
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            histogram_filename = (
                f"histogram_{aic}_id_{contraindication_id}_{timestamp}.png"
            )
            histogram_path = self.results_path / histogram_filename

            plt.tight_layout()
            plt.savefig(histogram_path, dpi=300, bbox_inches="tight")
            plt.close()

            print(f"Individual histogram saved to: {histogram_path}")

            # Create histogram data dictionary
            histogram_data = {
                "contraindication_id": contraindication_id,
                "aic": aic,
                "timestamp": timestamp,
                "statistics": {
                    "total_distances": len(distances),
                    "mean": float(mean_dist),
                    "median": float(median_dist),
                    "std": float(std_dist),
                    "min": float(min(distances)) if distances else 0,
                    "max": float(max(distances)) if distances else 0,
                    "percentile_25": (
                        float(np.percentile(distances, 25)) if distances else 0
                    ),
                    "percentile_75": (
                        float(np.percentile(distances, 75)) if distances else 0
                    ),
                },
                "histogram": {
                    "bins": hist_bins.tolist(),  # Convert numpy array to list for JSON serialization
                    "counts": hist_counts.tolist(),  # Convert numpy array to list for JSON serialization
                    "bin_edges": hist_bins.tolist(),
                },
                "raw_distances": distances,
                "image_path": str(histogram_path),
            }

            return histogram_data

        except Exception as e:
            print(
                f"Error creating individual histogram for ID {contraindication_id}: {e}"
            )
            return {}

    def create_distance_histogram(self, aic: str, all_distances: List[float]) -> str:
        """
        Create a histogram of distances for all queries of a given AIC code.

        Args:
            aic: AIC code identifier
            all_distances: List of all distance values from all searches

        Returns:
            Path to saved histogram image
        """
        try:
            plt.figure(figsize=(12, 8))

            # Create histogram
            plt.hist(all_distances, bins=50, alpha=0.7, color="blue", edgecolor="black")
            plt.title(
                f"Overall Distance Distribution for AIC: {aic}\n(Total queries: {len(all_distances)} distances)"
            )
            plt.xlabel("Distance")
            plt.ylabel("Frequency")
            plt.grid(True, alpha=0.3)

            # Add statistics to the plot
            mean_dist = np.mean(all_distances)
            median_dist = np.median(all_distances)
            std_dist = np.std(all_distances)

            plt.axvline(
                mean_dist,
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"Mean: {mean_dist:.4f}",
            )
            plt.axvline(
                median_dist,
                color="green",
                linestyle="--",
                linewidth=2,
                label=f"Median: {median_dist:.4f}",
            )

            plt.legend()

            # Save histogram
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            histogram_filename = f"overall_distance_histogram_{aic}_{timestamp}.png"
            histogram_path = self.results_path / histogram_filename

            plt.tight_layout()
            plt.savefig(histogram_path, dpi=300, bbox_inches="tight")
            plt.close()

            print(f"Overall histogram saved to: {histogram_path}")

            # Also save statistics as text
            stats_filename = f"overall_distance_statistics_{aic}_{timestamp}.txt"
            stats_path = self.results_path / stats_filename

            with open(stats_path, "w") as f:
                f.write(f"Overall Distance Statistics for AIC: {aic}\n")
                f.write(f"=" * 40 + "\n")
                f.write(f"Total distances: {len(all_distances)}\n")
                f.write(f"Mean: {mean_dist:.6f}\n")
                f.write(f"Median: {median_dist:.6f}\n")
                f.write(f"Standard deviation: {std_dist:.6f}\n")
                f.write(f"Min: {min(all_distances):.6f}\n")
                f.write(f"Max: {max(all_distances):.6f}\n")
                f.write(f"25th percentile: {np.percentile(all_distances, 25):.6f}\n")
                f.write(f"75th percentile: {np.percentile(all_distances, 75):.6f}\n")

            print(f"Overall statistics saved to: {stats_path}")

            return str(histogram_path)

        except Exception as e:
            print(f"Error creating overall histogram: {e}")
            return ""

    def process_all_contraindications(
        self,
        contraindications_data: Any,
        similarity_threshold: float = None,
        max_results: int = 1000,
    ) -> Dict[str, Any]:
        """
        Process all contraindications and perform similarity searches.

        Args:
            contraindications_data: JSON data containing contraindications
            similarity_threshold: Maximum distance threshold for filtering results (smaller = more similar)
            max_results: Maximum number of results to retrieve per query (default: 1000)
        """
        # Handle different JSON structures
        if isinstance(contraindications_data, list):
            if len(contraindications_data) > 0 and isinstance(
                contraindications_data[0], dict
            ):
                # JSON is an array containing objects with contraindications
                if "contraindications" in contraindications_data[0]:
                    # Structure: [{"aic": "...", "url": "...", "contraindications": [...]}]
                    data_obj = contraindications_data[0]
                    contraindications_list = data_obj["contraindications"]
                    aic = data_obj.get("aic", "unknown")
                    url = data_obj.get("url", "unknown")
                else:
                    # Structure: [{"id": 1, "warning_eng": "...", ...}, ...]
                    contraindications_list = contraindications_data
                    aic = "unknown"
                    url = "unknown"
            else:
                # Empty list or other structure
                contraindications_list = contraindications_data
                aic = "unknown"
                url = "unknown"
        else:
            # Original dict format: {"aic": "...", "contraindications": [...]}
            contraindications_list = contraindications_data["contraindications"]
            aic = contraindications_data["aic"]
            url = contraindications_data["url"]

        # List to store all distances for overall histogram
        all_distances = []
        # List to store individual histogram data
        individual_histograms = []

        results = {
            "metadata": {
                "aic": aic,
                "url": url,
                "processing_timestamp": datetime.now().isoformat(),
                "total_contraindications": len(contraindications_list),
                "similarity_threshold": similarity_threshold,
                "max_results_per_query": max_results,
            },
            "similarity_searches": [],
            "individual_histograms": [],
            "distance_statistics": {},
        }

        print(f"Processing AIC: {aic}")
        print(f"Total contraindications to process: {len(contraindications_list)}")
        print(
            f"Similarity threshold: {similarity_threshold if similarity_threshold is not None else 'None (no filtering)'}"
        )
        print(f"Max results per query: {max_results}")

        for contraindication in contraindications_list:
            contraindication_id = str(contraindication["id"])
            print(f"Processing contraindication ID: {contraindication_id}")

            # Use the English warning as the search query
            query = contraindication["warning_eng"]

            # Perform similarity search with threshold and limit
            search_results = self.perform_similarity_search(
                query,
                similarity_threshold=similarity_threshold,
                max_results=max_results,
            )

            if not search_results:
                print(
                    f"⚠️ WARNING: No results returned for contraindication ID {contraindication_id}"
                )
                print(f"Query was: {query[:100]}...")
                continue

            # Extract distances and add to the list for overall histogram
            query_distances = [result["distance"] for result in search_results]
            all_distances.extend(query_distances)

            # Create individual histogram for this contraindication
            individual_histogram_data = self.create_individual_histogram(
                contraindication_id, aic, query_distances
            )

            if individual_histogram_data:
                individual_histograms.append(individual_histogram_data)

                # Save individual histogram data to JSON
                individual_json_filename = f"histogram_data_{aic}_id_{contraindication_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                individual_json_path = self.results_path / individual_json_filename

                try:
                    with open(individual_json_path, "w", encoding="utf-8") as f:
                        json.dump(
                            individual_histogram_data, f, indent=2, ensure_ascii=False
                        )
                    print(f"Individual histogram data saved to: {individual_json_path}")
                except Exception as e:
                    print(f"Error saving individual histogram JSON: {e}")

            # Store results
            search_entry = {
                "contraindication_id": contraindication_id,
                "original_warning": {
                    "italian": contraindication["warning_ita"],
                    "english": contraindication["warning_eng"],
                    "context": contraindication["context"],
                    "pretext": contraindication["pretext"],
                },
                "search_query": query,
                "similar_documents": search_results,
                "results_count": len(search_results),
                "distances": query_distances,  # Store distances separately for analysis
                "individual_histogram_path": (
                    individual_histogram_data.get("image_path", "")
                    if individual_histogram_data
                    else ""
                ),
            }

            results["similarity_searches"].append(search_entry)

        # Add individual histograms to results
        results["individual_histograms"] = individual_histograms

        # Create overall histogram and add statistics to results
        if all_distances:
            overall_histogram_path = self.create_distance_histogram(aic, all_distances)

            results["distance_statistics"] = {
                "total_distances": len(all_distances),
                "mean": float(np.mean(all_distances)),
                "median": float(np.median(all_distances)),
                "std": float(np.std(all_distances)),
                "min": float(min(all_distances)),
                "max": float(max(all_distances)),
                "percentile_25": float(np.percentile(all_distances, 25)),
                "percentile_75": float(np.percentile(all_distances, 75)),
                "overall_histogram_path": overall_histogram_path,
                "all_distances": all_distances,  # Store all distances for further analysis
            }

        return results

    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save results to JSON file."""
        if filename is None:
            aic = results["metadata"]["aic"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"similarity_results_{aic}_{timestamp}.json"

        output_path = self.results_path / filename

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            print(f"Results saved to: {output_path}")
            return output_path

        except Exception as e:
            raise RuntimeError(f"Failed to save results: {e}")

    def create_summary_report(self, results: Dict[str, Any]) -> str:
        """Create a summary report of the similarity search results."""
        summary = []
        summary.append(f"=== Similarity Search Summary ===")
        summary.append(f"AIC: {results['metadata']['aic']}")
        summary.append(
            f"Total Contraindications: {results['metadata']['total_contraindications']}"
        )
        summary.append(
            f"Similarity Threshold: {results['metadata']['similarity_threshold'] if results['metadata']['similarity_threshold'] is not None else 'None (no filtering)'}"
        )
        summary.append(
            f"Max Results Per Query: {results['metadata']['max_results_per_query']}"
        )
        summary.append(
            f"Processing Time: {results['metadata']['processing_timestamp']}"
        )
        summary.append("")

        # Add distance statistics
        if "distance_statistics" in results and results["distance_statistics"]:
            stats = results["distance_statistics"]
            summary.append(f"=== Overall Distance Statistics ===")
            summary.append(f"Total distances analyzed: {stats['total_distances']}")
            summary.append(f"Mean distance: {stats['mean']:.6f}")
            summary.append(f"Median distance: {stats['median']:.6f}")
            summary.append(f"Standard deviation: {stats['std']:.6f}")
            summary.append(f"Min distance: {stats['min']:.6f}")
            summary.append(f"Max distance: {stats['max']:.6f}")
            summary.append(
                f"Overall histogram saved to: {stats['overall_histogram_path']}"
            )
            summary.append("")

        # Add individual histogram summary
        if "individual_histograms" in results and results["individual_histograms"]:
            summary.append(f"=== Individual Histograms ===")
            summary.append(
                f"Created {len(results['individual_histograms'])} individual histograms"
            )
            for hist_data in results["individual_histograms"]:
                summary.append(
                    f"  ID {hist_data['contraindication_id']}: {hist_data['statistics']['total_distances']} distances"
                )
            summary.append("")

        for search in results["similarity_searches"]:
            summary.append(f"Contraindication ID {search['contraindication_id']}:")
            summary.append(f"  Query: {search['search_query'][:100]}...")
            summary.append(f"  Found {search['results_count']} documents")

            if search["similar_documents"]:
                best_match = search["similar_documents"][0]
                summary.append(
                    f"  Best match (distance: {best_match['distance']:.6f}): {best_match['document'][:100]}..."
                )

            summary.append("")

        return "\n".join(summary)


def main():
    """Main execution function."""
    # Get the root directory (two levels up from src/retrieval/)
    root_dir = Path(__file__).parent.parent.parent

    # Configuration with absolute paths from root
    VECTORDB_PATH = root_dir / "data" / "vectordb"
    CONTRAINDICATIONS_PATH = root_dir / "data" / "LLM_output" / "contraindications.json"
    RESULTS_PATH = root_dir / "data" / "results"

    # Verify paths exist
    if not VECTORDB_PATH.exists():
        raise FileNotFoundError(f"Vector database not found at: {VECTORDB_PATH}")
    if not CONTRAINDICATIONS_PATH.exists():
        raise FileNotFoundError(
            f"Contraindications JSON not found at: {CONTRAINDICATIONS_PATH}"
        )

    print(f"Using paths:")
    print(f"  Vector DB: {VECTORDB_PATH}")
    print(f"  JSON file: {CONTRAINDICATIONS_PATH}")
    print(f"  Results: {RESULTS_PATH}")

    try:
        # Initialize retriever
        retriever = ContraindicationRetriever(str(VECTORDB_PATH), str(RESULTS_PATH))
        retriever.initialize_chroma_client()

        # Load contraindications data
        contraindications_data = retriever.load_contraindications(
            str(CONTRAINDICATIONS_PATH)
        )

        # Process all contraindications with configurable threshold and limits
        results = retriever.process_all_contraindications(
            contraindications_data,
            similarity_threshold=None,  # Set to a value like 0.5 to filter by similarity
            max_results=1000,  # Limit to 1000 documents per query
        )

        # Save results
        output_file = retriever.save_results(results)

        # Print summary
        print("\n" + retriever.create_summary_report(results))

        print(f"\n✅ Processing completed successfully!")
        print(f"📁 Results saved to: {output_file}")
        print(f"📊 Individual histograms created for each contraindication ID")
        print(f"📈 Overall histogram created for all distances")

    except Exception as e:
        print(f"❌ Error during processing: {e}")
        raise


if __name__ == "__main__":
    main()
