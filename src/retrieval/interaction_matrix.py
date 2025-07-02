import json
from pathlib import Path
from typing import Dict, Tuple, Any, List
from datetime import datetime


class InteractionMatrixBuilder:
    """Build interaction matrix from ContraindicationRetriever results."""

    def __init__(self, output_dir: str = "data/interaction_matrix"):
        """Initialize the interaction matrix builder."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_matrix = None  # Cache for loaded matrix

    def build_interaction_matrix(
        self, results: Dict[str, Any]
    ) -> Dict[Tuple[str, str], List[Dict]]:
        """Build interaction matrix from retrieval results."""
        matrix = {}
        total_pairs = 0

        # Handle both single and multi-AIC formats
        if "aic_results" in results:
            aic_results = results["aic_results"]
        else:
            # Convert single format to multi format
            aic_results = [
                {
                    "aic": results.get("metadata", {}).get("aic", ""),
                    "aic_url": results.get("metadata", {}).get("url", ""),
                    "similarity_searches": results.get("similarity_searches", []),
                }
            ]

        for aic_result in aic_results:
            aic = aic_result["aic"]
            aic_url = aic_result["aic_url"]

            for search in aic_result.get("similarity_searches", []):
                warning = search.get("original_warning", {}).get("italian", "")

                for doc in search.get("similar_documents", []):
                    metadata = doc.get("metadata", {})
                    icd_code = metadata.get("ICD11_code") or metadata.get("code", "")

                    if icd_code and warning:
                        total_pairs += 1
                        key = (aic, icd_code)

                        entry = {
                            "aic_url": aic_url,
                            "aic_name": self._get_aic_name(aic),
                            "warning": warning,
                            "icd_name": metadata.get("name", ""),
                            "icd_url": metadata.get("url", ""),
                        }

                        if key not in matrix:
                            matrix[key] = []

                        # Avoid duplicates
                        if not any(e["warning"] == warning for e in matrix[key]):
                            matrix[key].append(entry)

        print(
            f"✅ Built matrix: {len(matrix)} unique pairs from {total_pairs} total pairs"
        )
        return matrix

    def save_interaction_matrix(self, matrix: Dict[Tuple[str, str], List[Dict]]) -> str:
        """Save matrix to JSON file."""
        output_path = self.output_dir / "interaction_matrix.json"

        # Convert tuple keys to strings
        serializable = {f"{aic}|{icd}": data for (aic, icd), data in matrix.items()}

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved to: {output_path}")
        return str(output_path)

    def get_matrix_statistics(
        self, matrix: Dict[Tuple[str, str], List[Dict]]
    ) -> Dict[str, Any]:
        """Get matrix statistics."""
        aics = set(key[0] for key in matrix.keys())
        icds = set(key[1] for key in matrix.keys())
        total_interactions = sum(len(interactions) for interactions in matrix.values())

        possible_combinations = len(aics) * len(icds)
        actual_combinations = len(matrix)

        return {
            "unique_aics": len(aics),
            "unique_icds": len(icds),
            "total_possible_combinations": possible_combinations,
            "actual_unique_combinations": actual_combinations,
            "total_contraindications": total_interactions,
            "avg_contraindications_per_pair": (
                total_interactions / actual_combinations if actual_combinations else 0
            ),
            "coverage_percentage": (
                actual_combinations / possible_combinations * 100
                if possible_combinations
                else 0
            ),
            "matrix_density": (
                actual_combinations / possible_combinations
                if possible_combinations
                else 0
            ),
        }

    def _get_aic_name(self, aic: str) -> str:
        """Get AIC name from code."""
        try:
            import pandas as pd

            df = pd.read_excel("data/leaflets/estrazione_farmaci.xlsx")
            match = df[df["code"].astype(str).str.zfill(9) == str(aic).zfill(9)]
            if not match.empty:
                return match.iloc[0]["name"]
        except:
            pass
        return f"Unknown AIC {aic}"

    def load_matrix(self, matrix_file: str = None) -> Dict[str, List[Dict]]:
        """
        Load interaction matrix from JSON file for efficient querying.

        Args:
            matrix_file: Path to matrix file, uses default if None

        Returns:
            Loaded matrix with string keys for O(1) lookup
        """
        if matrix_file is None:
            matrix_file = self.output_dir / "interaction_matrix.json"

        if self._loaded_matrix is None:
            print(f"📂 Loading matrix from: {matrix_file}")
            with open(matrix_file, "r", encoding="utf-8") as f:
                self._loaded_matrix = json.load(f)
            print(f"✅ Loaded {len(self._loaded_matrix)} AIC-ICD pairs")

        return self._loaded_matrix

    def get_interactions(
        self, aic: str, icd: str, matrix_file: str = None
    ) -> List[Dict[str, str]]:
        """
        Get interactions for specific AIC-ICD pair - O(1) lookup.

        Args:
            aic: AIC code
            icd: ICD code
            matrix_file: Optional path to matrix file

        Returns:
            List of interaction dictionaries, empty if no interactions found
        """
        matrix = self.load_matrix(matrix_file)
        key = f"{aic}|{icd}"
        interactions = matrix.get(key, [])
        if not interactions:
            print(f"No interactions found for AIC {aic} and ICD {icd}.")
        else:
            print(
                f"Found {len(interactions)} interactions for AIC {aic} and ICD {icd}."
            )
        return interactions

    def has_interaction(self, aic: str, icd: str, matrix_file: str = None) -> bool:
        """
        Check if AIC-ICD pair has any interactions - O(1) lookup.

        Args:
            aic: AIC code
            icd: ICD code
            matrix_file: Optional path to matrix file

        Returns:
            True if interactions exist, False otherwise
        """
        matrix = self.load_matrix(matrix_file)
        key = f"{aic}|{icd}"
        return key in matrix and len(matrix[key]) > 0


if __name__ == "__main__":

    # Load matrix from file
    matrix_builder = InteractionMatrixBuilder()
    matrix_file = "data/interaction_matrix/interaction_matrix.json"
    matrix = matrix_builder.load_matrix(matrix_file)

    # Example usage
    aic_code = "030705026"
    icd_code = "3B64.Z"
    interactions = matrix_builder.get_interactions(aic_code, icd_code, matrix_file)
    print(interactions)
