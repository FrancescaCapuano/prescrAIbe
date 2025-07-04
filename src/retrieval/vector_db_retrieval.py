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

    def _distance_to_similarity(self, distance: float) -> float:
        """Convert distance score to similarity score (0-1 range, higher = more similar)."""
        # For cosine distance: similarity = 1 - distance
        # Clamp to [0, 1] range to handle numerical precision issues
        return max(0.0, min(1.0, 1.0 - distance))

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

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            where={"code_prefix": {"$nin": ["M", "N", "P", "Q", "R", "V", "X"]}},
        )

        # Check if results exist and have valid data
        if (
            not results
            or not results.get("ids")
            or not results["ids"]
            or not results["ids"][0]
            or not results.get("documents")
            or not results["documents"]
            or not results["documents"][0]
            or not results.get("distances")
            or not results["distances"]
            or not results["distances"][0]
        ):
            return []

        # Format results (ChromaDB returns distance scores - lower = more similar)
        formatted_results = []
        for i in range(len(results["ids"][0])):
            # Safely get metadata
            metadata = {}
            if (
                results.get("metadatas")
                and results["metadatas"]
                and len(results["metadatas"]) > 0
                and len(results["metadatas"][0]) > i
                and isinstance(results["metadatas"][0][i], dict)
            ):
                metadata = results["metadatas"][0][i]

            formatted_results.append(
                {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": metadata,
                    "distance": results["distances"][0][
                        i
                    ],  # Lower distance = higher similarity
                    "similarity": self._distance_to_similarity(
                        results["distances"][0][i]
                    ),  # Converted to 0-1 scale
                }
            )

        # Apply statistical filtering if requested
        if use_statistical_filter and len(formatted_results) > 1:
            distances = np.array([r["distance"] for r in formatted_results])
            median = np.median(distances)
            mad = median_abs_deviation(distances)
            robust_z_scores = (distances - median) / mad
            # Keep results with LOW distances (high similarity) - z < -devs means much lower than median
            formatted_results = [
                r for r, z in zip(formatted_results, robust_z_scores) if z < -devs
            ]

        # Sort by distance (ascending = most similar first) and deduplicate by unique ICD-11 codes
        formatted_results.sort(
            key=lambda x: x["distance"]
        )  # Lower distance = higher similarity
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
        filepath = self.results_path / "interaction_results.json"

        print("💾 Saving final results to file...")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"✅ All results saved to: {filepath}")
        return str(filepath)


class Section1Retriever:
    """Retriever for comparing drug leaflet section 1 content."""

    def __init__(self, vectordb_path, results_path, model_name):
        self.vectordb_path = Path(vectordb_path)
        self.results_path = Path(results_path)
        self.results_path.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.checkpoint_file = self.results_path / "section1_checkpoint.json"

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
        self.collection = self.client.get_collection("collection_section_1")
        print(f"✅ Connected to collection with {self.collection.count():,} documents")

    def _distance_to_similarity(self, distance: float) -> float:
        """Convert distance score to similarity score (0-1 range, higher = more similar)."""
        return max(0.0, min(1.0, 1.0 - distance))

    def get_all_documents(self):
        """Get all documents from the vector database."""
        try:
            all_data = self.collection.get(
                include=["documents", "metadatas", "embeddings"]
            )

            documents = []
            for i in range(len(all_data["ids"])):
                # Safe access to embeddings - check if embeddings exist and handle numpy arrays
                embedding = None
                if (
                    all_data.get("embeddings") is not None
                    and len(all_data["embeddings"]) > i
                ):
                    embedding = all_data["embeddings"][i]

                # Safe access to metadata
                metadata = {}
                if (
                    all_data.get("metadatas") is not None
                    and len(all_data["metadatas"]) > i
                ):
                    metadata = all_data["metadatas"][i] or {}

                documents.append(
                    {
                        "id": all_data["ids"][i],
                        "document": all_data["documents"][i],
                        "metadata": metadata,
                        "embedding": embedding,
                    }
                )

            print(f"✅ Successfully retrieved {len(documents)} documents")
            return documents

        except Exception as e:
            print(f"❌ Error retrieving documents: {e}")
            import traceback

            traceback.print_exc()  # This will show the full error trace
            return []

    def search_similar_drugs(
        self,
        query_document: str,
        max_results: int = 10,
        use_statistical_filter: bool = False,
        devs: float = 2.0,
        exclude_id: str = None,
    ) -> List[Dict[str, Any]]:
        """Find similar drugs using the same logic as contraindication search."""

        # Use more results for statistical filtering
        n_results = min(
            5000 if use_statistical_filter else max_results * 3, self.collection.count()
        )

        # Generate embedding and search
        query_embedding = self.embedding_function([query_document])

        # Search with optional exclusion of self
        where_clause = {}
        if exclude_id:
            where_clause = {"id": {"$ne": exclude_id}}

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            where=where_clause if where_clause else None,
        )

        # Check if results exist and have valid data
        if (
            not results
            or not results.get("ids")
            or not results["ids"]
            or not results["ids"][0]
        ):
            return []

        # Format results
        formatted_results = []
        for i in range(len(results["ids"][0])):
            metadata = {}
            if (
                results.get("metadatas")
                and results["metadatas"]
                and len(results["metadatas"]) > 0
                and len(results["metadatas"][0]) > i
                and isinstance(results["metadatas"][0][i], dict)
            ):
                metadata = results["metadatas"][0][i]

            formatted_results.append(
                {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": metadata,
                    "distance": results["distances"][0][i],
                    "similarity": self._distance_to_similarity(
                        results["distances"][0][i]
                    ),
                }
            )

        # Apply statistical filtering if requested (same as ContraindicationRetriever)
        if use_statistical_filter and len(formatted_results) > 1:
            distances = np.array([r["distance"] for r in formatted_results])
            median = np.median(distances)
            mad = median_abs_deviation(distances)
            robust_z_scores = (distances - median) / mad
            # Keep results with LOW distances (high similarity)
            formatted_results = [
                r for r, z in zip(formatted_results, robust_z_scores) if z < -devs
            ]

        # Sort by distance (ascending = most similar first)
        formatted_results.sort(key=lambda x: x["distance"])

        # Return top max_results
        return formatted_results[:max_results]

    def compare_all_vs_all(
        self,
        max_results=10,
        use_statistical_filter=False,
        devs=2.0,
        save_checkpoint_every=10,
    ):
        """Compare every document against all others with statistical filtering."""

        documents = self.get_all_documents()
        if not documents:
            print("❌ No documents found in the vector database.")
            return {}

        print(f"🎯 Starting all-vs-all comparison for {len(documents)} drugs")
        print(f"📊 Configuration:")
        print(f"   Max results per query: {max_results}")
        print(
            f"   Statistical filtering: {'enabled' if use_statistical_filter else 'disabled'}"
        )
        if use_statistical_filter:
            print(f"   Deviation threshold: {devs}")

        # Load checkpoint or start fresh
        save_checkpoint, load_checkpoint, clear_checkpoint = (
            self._checkpoint_operations()
        )
        checkpoint_results, start_index = load_checkpoint()

        all_results = checkpoint_results or {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_drugs": len(documents),
                "max_results_per_query": max_results,
                "use_statistical_filter": use_statistical_filter,
                "devs": devs if use_statistical_filter else None,
                "model_name": self.model_name,
            },
            "drug_results": [],
        }

        drug_pbar = tqdm(
            documents[start_index:],
            desc="Processing drugs",
            unit="drugs",
            colour="blue",
            initial=start_index,
            total=len(documents),
        )

        try:
            for relative_index, query_doc in enumerate(drug_pbar):
                actual_index = start_index + relative_index
                query_id = query_doc["id"]
                query_content = query_doc["document"]

                drug_pbar.set_postfix(
                    {
                        "Current Drug": (
                            query_id[:20] + "..." if len(query_id) > 20 else query_id
                        ),
                        "Index": f"{actual_index + 1}/{len(documents)}",
                    }
                )

                # Find similar drugs (exclude self)
                similar_drugs = self.search_similar_drugs(
                    query_content,
                    max_results=max_results,
                    use_statistical_filter=use_statistical_filter,
                    devs=devs,
                    exclude_id=query_id,
                )

                drug_result = {
                    "query_drug": {
                        "id": query_id,
                        "metadata": query_doc.get("metadata", {}),
                        "content_preview": (
                            query_content[:200] + "..."
                            if len(query_content) > 200
                            else query_content
                        ),
                    },
                    "similar_drugs": similar_drugs,
                    "similarity_count": len(similar_drugs),
                }

                all_results["drug_results"].append(drug_result)

                # Save checkpoint periodically
                if (actual_index + 1) % save_checkpoint_every == 0:
                    save_checkpoint(all_results, actual_index + 1)
                    tqdm.write(f"💾 Checkpoint saved after drug {actual_index + 1}")

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

    def _checkpoint_operations(self):
        """Checkpoint management methods (same as ContraindicationRetriever)."""

        def save_checkpoint(results: Dict[str, Any], current_drug_index: int):
            checkpoint_data = {
                "results": results,
                "current_drug_index": current_drug_index,
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
                current_drug_index = checkpoint_data["current_drug_index"]
                print(f"✅ Loaded checkpoint from {checkpoint_data['timestamp']}")
                print(f"🔄 Resuming from drug index {current_drug_index}")
                return results, current_drug_index
            except Exception as e:
                print(f"❌ Error loading checkpoint: {e}")
                return None, 0

        def clear_checkpoint():
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                print("🗑️ Checkpoint file cleared")

        return save_checkpoint, load_checkpoint, clear_checkpoint

    def save_all_results(self, results):
        """Save the similarity results to file."""
        filepath = self.results_path / "section1_similarity_results.json"

        print("💾 Saving final results to file...")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"✅ All results saved to: {filepath}")
        return str(filepath)

    def create_similarity_matrix(self, results):
        """Create a similarity matrix from results."""
        import pandas as pd

        # Extract all drug IDs
        drug_ids = [
            drug_result["query_drug"]["id"] for drug_result in results["drug_results"]
        ]

        # Create similarity matrix
        matrix = np.zeros((len(drug_ids), len(drug_ids)))

        for i, drug_result in enumerate(results["drug_results"]):
            for similar_drug in drug_result["similar_drugs"]:
                j = (
                    drug_ids.index(similar_drug["id"])
                    if similar_drug["id"] in drug_ids
                    else -1
                )
                if j >= 0:
                    matrix[i][j] = similar_drug["similarity"]

        # Save as CSV
        df = pd.DataFrame(matrix, index=drug_ids, columns=drug_ids)
        matrix_path = self.results_path / "similarity_matrix.csv"
        df.to_csv(matrix_path)

        print(f"📊 Similarity matrix saved to: {matrix_path}")
        return str(matrix_path)


def filter_contraindications_by_category(contraindications_data, category):
    """Filter contraindications by category."""
    filtered_data = []
    for aic_data in contraindications_data:
        filtered_contraindications = [
            ci
            for ci in aic_data.get("contraindications", [])
            if ci.get("category") == category
        ]
        if filtered_contraindications:
            filtered_aic_data = aic_data.copy()
            filtered_aic_data["contraindications"] = filtered_contraindications
            filtered_data.append(filtered_aic_data)

    print(f"🔍 Filtered to {len(filtered_data)} AICs with category '{category}'")
    return filtered_data


def filter_contraindications_by_aic(contraindications_data, aic_codes):
    """Filter contraindications by AIC codes."""
    if not aic_codes:
        return contraindications_data

    aic_codes_set = set(aic_codes)
    filtered_data = [
        aic_data
        for aic_data in contraindications_data
        if aic_data.get("aic") in aic_codes_set
    ]

    print(f"🔍 Filtered to {len(filtered_data)} AICs from provided AIC codes")
    return filtered_data
