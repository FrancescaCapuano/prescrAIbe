import json
import os
from pathlib import Path
from typing import Dict, Tuple, Any, List
from datetime import datetime


class InteractionMatrixBuilder:
    """Build interaction matrix from ContraindicationRetriever results."""

    def __init__(self, output_dir: str = "data/interaction_matrix"):
        """Initialize the interaction matrix builder."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_interaction_matrix(
        self, retrieval_results: Dict[str, Any]
    ) -> Dict[Tuple[str, str], List[Dict[str, str]]]:
        """
        Build interaction matrix from ContraindicationRetriever results.
        Supports both single-AIC and multi-AIC formats.
        """
        interaction_matrix = {}
        total_raw_pairs = 0
        total_duplicates_avoided = 0

        # Check if this is the new multi-AIC format
        if "aic_results" in retrieval_results:
            # New multi-AIC format
            aic_results = retrieval_results.get("aic_results", [])
            print(f"🔍 Processing {len(aic_results)} AICs from multi-AIC format")

            for aic_result in aic_results:
                aic = aic_result.get("aic", "")
                aic_url = aic_result.get("aic_url", "")
                similarity_searches = aic_result.get("similarity_searches", [])

                print(
                    f"  📋 Processing AIC: {aic} with {len(similarity_searches)} contraindications"
                )

                # Process this AIC's similarity searches
                pairs, duplicates = self._process_aic_searches(
                    aic, aic_url, similarity_searches, interaction_matrix
                )
                total_raw_pairs += pairs
                total_duplicates_avoided += duplicates

        else:
            # Old single-AIC format
            metadata = retrieval_results.get("metadata", {})
            aic = metadata.get("aic", "")
            aic_url = metadata.get("url", "")
            similarity_searches = retrieval_results.get("similarity_searches", [])

            print(f"🔍 Processing single AIC: {aic}")

            pairs, duplicates = self._process_aic_searches(
                aic, aic_url, similarity_searches, interaction_matrix
            )
            total_raw_pairs += pairs
            total_duplicates_avoided += duplicates

        # Calculate statistics
        total_contraindications = sum(
            len(contraindications) for contraindications in interaction_matrix.values()
        )
        unique_pairs = len(interaction_matrix)

        print(f"✅ Built interaction matrix:")
        print(f"   📊 Raw (AIC, ICD) pairs found: {total_raw_pairs}")
        print(f"   🔑 Unique (AIC, ICD) combinations: {unique_pairs}")
        print(f"   📋 Total unique contraindication entries: {total_contraindications}")
        print(f"   🚫 Duplicate entries avoided: {total_duplicates_avoided}")

        if unique_pairs > 0:
            print(
                f"   📈 Avg contraindications per pair: {total_contraindications/unique_pairs:.2f}"
            )
            print(
                f"   🔄 Deduplication rate: {(1 - unique_pairs/total_raw_pairs)*100:.1f}%"
            )
        else:
            print("   ⚠️ No valid interactions found!")

        return interaction_matrix

    def _process_aic_searches(
        self,
        aic: str,
        aic_url: str,
        similarity_searches: List[Dict],
        interaction_matrix: Dict,
    ) -> Tuple[int, int]:
        """Process similarity searches for a single AIC."""
        raw_pairs = 0
        duplicates_avoided = 0

        for search_entry in similarity_searches:
            contraindication_id = search_entry.get("contraindication_id", "")
            original_warning = search_entry.get("original_warning", {})
            warning_ita = original_warning.get("italian", "")
            similar_documents = search_entry.get("similar_documents", [])

            # Process each similar document (ICD-11 conditions)
            for doc in similar_documents:
                doc_metadata = doc.get("metadata", {})

                # Handle different metadata key formats
                icd_code = doc_metadata.get("ICD11_code") or doc_metadata.get(
                    "code", ""
                )
                icd_name = doc_metadata.get("name", "")
                icd_url = doc_metadata.get("url", "")

                if (
                    icd_code and warning_ita
                ):  # Only add if we have both AIC and ICD data
                    raw_pairs += 1

                    # Create unique key (aic, icd_code)
                    key = (aic, icd_code)

                    # Create interaction entry
                    interaction_entry = {
                        "aic_url": aic_url,
                        "warning": warning_ita,
                        "icd_name": icd_name,
                        "icd_url": icd_url,
                    }

                    # Initialize list if this (AIC, ICD) combination is new
                    if key not in interaction_matrix:
                        interaction_matrix[key] = []

                    # Check if this exact entry already exists to avoid duplicates
                    entry_exists = any(
                        existing_entry["warning"] == interaction_entry["warning"]
                        for existing_entry in interaction_matrix[key]
                    )

                    if not entry_exists:
                        interaction_matrix[key].append(interaction_entry)
                    else:
                        duplicates_avoided += 1

        return raw_pairs, duplicates_avoided

    def save_interaction_matrix(
        self,
        interaction_matrix: Dict[Tuple[str, str], List[Dict[str, str]]],
        filename: str = None,
    ) -> str:
        """
        Save interaction matrix to JSON file.

        Args:
            interaction_matrix: The interaction matrix to save
            filename: Optional custom filename

        Returns:
            Path to saved file
        """
        output_path = self.output_dir / "interaction_matrix.json"

        # Convert tuple keys to strings for JSON serialization
        serializable_matrix = {}
        for (aic, icd_code), data in interaction_matrix.items():
            key_str = f"{aic}|{icd_code}"  # Use pipe separator
            serializable_matrix[key_str] = data

        # Save to JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable_matrix, f, indent=2, ensure_ascii=False)

        print(f"💾 Interaction matrix saved to: {output_path}")
        return str(output_path)

    def load_interaction_matrix(
        self, filepath: str
    ) -> Dict[Tuple[str, str], List[Dict[str, str]]]:
        """
        Load interaction matrix from JSON file.

        Args:
            filepath: Path to the JSON file

        Returns:
            Interaction matrix with tuple keys
        """
        with open(filepath, "r", encoding="utf-8") as f:
            serializable_matrix = json.load(f)

        # Convert string keys back to tuples
        interaction_matrix = {}
        for key_str, data in serializable_matrix.items():
            aic, icd_code = key_str.split("|", 1)  # Split on first pipe only
            key = (aic, icd_code)
            interaction_matrix[key] = data

        return interaction_matrix

    def get_matrix_statistics(
        self, interaction_matrix: Dict[Tuple[str, str], List[Dict[str, str]]]
    ) -> Dict[str, Any]:
        """Get statistics about the interaction matrix."""
        unique_aics = set(key[0] for key in interaction_matrix.keys())
        unique_icds = set(key[1] for key in interaction_matrix.keys())

        # Calculate contraindication statistics
        contraindication_counts = [
            len(contraindications) for contraindications in interaction_matrix.values()
        ]
        total_contraindications = sum(contraindication_counts)

        # Calculate total possible combinations vs actual unique combinations
        total_possible_combinations = len(unique_aics) * len(unique_icds)
        actual_unique_combinations = len(interaction_matrix)

        stats = {
            "total_interactions": len(interaction_matrix),
            "unique_aics": len(unique_aics),
            "unique_icds": len(unique_icds),
            "total_possible_combinations": total_possible_combinations,
            "actual_unique_combinations": actual_unique_combinations,
            "total_contraindications": total_contraindications,  # Add this
            "avg_contraindications_per_pair": (
                total_contraindications / actual_unique_combinations
                if actual_unique_combinations > 0
                else 0
            ),
            "matrix_density": (
                actual_unique_combinations / total_possible_combinations
                if total_possible_combinations > 0
                else 0
            ),
            "coverage_percentage": (
                (actual_unique_combinations / total_possible_combinations) * 100
                if total_possible_combinations > 0
                else 0
            ),
            "sample_aics": list(unique_aics)[:5],
            "sample_icds": list(unique_icds)[:5],
        }

        return stats


def process_retrieval_results_to_matrix(
    results_file: str, output_dir: str = "data/interaction_matrix"
) -> str:
    """
    Convenience function to process a single retrieval results file.

    Args:
        results_file: Path to the retrieval results JSON file
        output_dir: Directory to save the interaction matrix

    Returns:
        Path to saved interaction matrix file
    """
    # Load results
    with open(results_file, "r", encoding="utf-8") as f:
        results = json.load(f)

    # Build matrix
    builder = InteractionMatrixBuilder(output_dir)
    interaction_matrix = builder.build_interaction_matrix(results)

    # Save matrix
    matrix_file = builder.save_interaction_matrix(interaction_matrix)

    # Print statistics
    stats = builder.get_matrix_statistics(interaction_matrix)
    print(f"\n📊 INTERACTION MATRIX STATISTICS:")
    print(f"  Unique AIC codes: {stats['unique_aics']}")
    print(f"  Unique ICD codes: {stats['unique_icds']}")
    print(f"  🔢 Total possible combinations: {stats['total_possible_combinations']:,}")
    print(f"  ✅ Actual unique combinations: {stats['actual_unique_combinations']:,}")
    print(
        f"  📋 Total interaction entries: {stats['total_contraindications']:,}"
    )  # Add this line
    print(
        f"  📈 Avg entries per combination: {stats['avg_contraindications_per_pair']:.2f}"
    )  # Add this line
    print(f"  📈 Coverage: {stats['coverage_percentage']:.2f}%")
    print(f"  📊 Matrix density: {stats['matrix_density']:.6f}")

    return matrix_file


def process_multiple_retrieval_results(
    results_dir: str, output_dir: str = "data/interaction_matrix"
) -> str:
    """
    Process multiple retrieval result files and combine into one interaction matrix.

    Args:
        results_dir: Directory containing retrieval result JSON files
        output_dir: Directory to save the combined interaction matrix

    Returns:
        Path to saved combined interaction matrix file
    """
    results_path = Path(results_dir)
    builder = InteractionMatrixBuilder(output_dir)

    combined_matrix = {}
    processed_files = 0

    # Process all JSON files in the results directory
    for json_file in results_path.glob("*.json"):
        print(f"🔍 Processing: {json_file.name}")

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                results = json.load(f)

            # Build matrix for this file
            file_matrix = builder.build_interaction_matrix(results)

            # Merge into combined matrix
            combined_matrix.update(file_matrix)
            processed_files += 1

        except Exception as e:
            print(f"❌ Error processing {json_file.name}: {e}")

    # Save combined matrix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"combined_interaction_matrix_{processed_files}_files_{timestamp}.json"
    matrix_file = builder.save_interaction_matrix(combined_matrix, filename)

    # Print statistics
    stats = builder.get_matrix_statistics(combined_matrix)
    print(f"\n📊 COMBINED INTERACTION MATRIX STATISTICS:")
    print(f"  Files processed: {processed_files}")
    print(f"  Unique AIC codes: {stats['unique_aics']}")
    print(f"  Unique ICD codes: {stats['unique_icds']}")
    print(f"  🔢 Total possible combinations: {stats['total_possible_combinations']:,}")
    print(f"  ✅ Actual unique combinations: {stats['actual_unique_combinations']:,}")
    print(
        f"  📋 Total interaction entries: {stats['total_contraindications']:,}"
    )  # Add this line
    print(
        f"  📈 Avg entries per combination: {stats['avg_contraindications_per_pair']:.2f}"
    )  # Add this line
    print(f"  📈 Coverage: {stats['coverage_percentage']:.2f}%")
    print(f"  📊 Matrix density: {stats['matrix_density']:.6f}")

    return matrix_file


def main():
    """Demo/test function."""
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python interaction_matrix.py <results_file.json>")
        print("  python interaction_matrix.py --dir <results_directory>")
        return

    if sys.argv[1] == "--dir":
        if len(sys.argv) < 3:
            print("Please specify results directory")
            return
        results_dir = sys.argv[2]
        matrix_file = process_multiple_retrieval_results(results_dir)
    else:
        results_file = sys.argv[1]
        matrix_file = process_retrieval_results_to_matrix(results_file)

    print(f"\n✅ Interaction matrix saved to: {matrix_file}")


if __name__ == "__main__":
    main()
