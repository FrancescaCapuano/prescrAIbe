import json
import os
from collections import defaultdict
from pathlib import Path


def load_interaction_results(file_path):
    """Load interaction results from a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_codes_for_contraindication(similarity_search):
    """Extract all ICD-11 codes from a contraindication's similarity search results."""
    codes = set()
    for doc in similarity_search.get("similar_documents", []):
        metadata = doc.get("metadata", {})
        code = metadata.get("code")
        if code:
            codes.add(code)
    return codes


def compare_models(results_dir):
    """Compare models by counting overlapping codes for each contraindication."""

    # Load all result files
    model_results = {}
    results_path = Path(results_dir)

    for file_path in results_path.glob("*.json"):
        if "interaction_results" in file_path.name:
            print(f"Loading {file_path.name}...")
            try:
                data = load_interaction_results(file_path)
                # Extract model name from filename or metadata
                if "metadata" in data and "model_name" in data["metadata"]:
                    model_name = data["metadata"]["model_name"]
                else:
                    # Extract from filename
                    model_name = file_path.stem.replace("interaction_results_", "")

                model_results[model_name] = data
            except Exception as e:
                print(f"Error loading {file_path}: {e}")

    print(f"Loaded {len(model_results)} model results")

    # Structure: {aic: {contraindication_id: {model: set_of_codes}}}
    aic_contraindication_codes = defaultdict(lambda: defaultdict(dict))

    # Extract codes for each AIC/contraindication/model combination
    for model_name, results in model_results.items():
        if "aic_results" in results:
            aic_results_key = "aic_results"
        elif "results" in results and "aic_results" in results["results"]:
            aic_results_key = "results"
            results = results["results"]
        else:
            print(f"Warning: No aic_results found for model {model_name}")
            continue

        for aic_result in results["aic_results"]:
            aic = aic_result["aic"]

            for similarity_search in aic_result.get("similarity_searches", []):
                contraindication_id = similarity_search["contraindication_id"]
                codes = extract_codes_for_contraindication(similarity_search)
                aic_contraindication_codes[aic][contraindication_id][model_name] = codes

    # Calculate scores
    model_scores = defaultdict(int)
    detailed_scores = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for aic, contraindications in aic_contraindication_codes.items():
        for contraindication_id, model_codes in contraindications.items():
            # Get all unique codes found by any model for this contraindication
            all_codes = set()
            for codes in model_codes.values():
                all_codes.update(codes)

            # For each model, count how many of its codes were also found by other models
            for model_name, codes in model_codes.items():
                for code in codes:
                    # Count how many OTHER models also found this code
                    other_models_with_code = sum(
                        1
                        for other_model, other_codes in model_codes.items()
                        if other_model != model_name and code in other_codes
                    )

                    if other_models_with_code > 0:
                        # Award 1 point for each other model that also found this code
                        points = other_models_with_code
                        model_scores[model_name] += points
                        detailed_scores[model_name][aic][contraindication_id] += points

    return model_scores, detailed_scores, aic_contraindication_codes


def print_results(model_scores, detailed_scores, aic_contraindication_codes):
    """Print the comparison results."""

    print("\n" + "=" * 80)
    print("MODEL COMPARISON RESULTS")
    print("=" * 80)

    # Overall scores
    print("\nOVERALL SCORES (Total overlap points):")
    print("-" * 40)
    sorted_models = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
    for model, score in sorted_models:
        print(f"{model:<50} {score:>8} points")

    # Detailed breakdown
    print("\nDETAILED BREAKDOWN BY AIC:")
    print("-" * 40)

    for model in model_scores.keys():
        print(f"\n{model}:")
        total_model_score = 0
        for aic in sorted(detailed_scores[model].keys()):
            aic_score = sum(detailed_scores[model][aic].values())
            total_model_score += aic_score
            print(f"  AIC {aic}: {aic_score} points")

            # Show contraindication breakdown for this AIC
            for contraindication_id in sorted(detailed_scores[model][aic].keys()):
                cont_score = detailed_scores[model][aic][contraindication_id]
                if cont_score > 0:
                    print(
                        f"    Contraindication {contraindication_id}: {cont_score} points"
                    )

    # Summary statistics
    print("\nSUMMARY STATISTICS:")
    print("-" * 40)

    total_aics = len(aic_contraindication_codes)
    total_contraindications = sum(
        len(contraindications)
        for contraindications in aic_contraindication_codes.values()
    )

    print(f"Total AICs analyzed: {total_aics}")
    print(f"Total contraindications analyzed: {total_contraindications}")
    print(f"Models compared: {len(model_scores)}")

    # Code overlap statistics
    print("\nCODE OVERLAP ANALYSIS:")
    print("-" * 40)

    for aic, contraindications in aic_contraindication_codes.items():
        print(f"\nAIC {aic}:")
        for contraindication_id, model_codes in contraindications.items():
            all_codes = set()
            for codes in model_codes.values():
                all_codes.update(codes)

            total_unique_codes = len(all_codes)
            models_with_results = len([m for m, codes in model_codes.items() if codes])

            if total_unique_codes > 0:
                print(
                    f"  Contraindication {contraindication_id}: {total_unique_codes} unique codes, {models_with_results} models with results"
                )

                # Show which codes were found by multiple models
                for code in all_codes:
                    models_with_code = [
                        m for m, codes in model_codes.items() if code in codes
                    ]
                    if len(models_with_code) > 1:
                        print(
                            f"    Code {code}: found by {len(models_with_code)} models ({', '.join(models_with_code)})"
                        )


def main():
    # Set the directory containing your interaction results files
    results_directory = "/home/francesca/Desktop/DS Bootcamp/portfolio_project/rxassist-ai/data/interaction_results"

    # Ensure the directory exists
    if not os.path.exists(results_directory):
        print(f"Error: Directory {results_directory} not found!")
        return

    # Compare models
    model_scores, detailed_scores, aic_contraindication_codes = compare_models(
        results_directory
    )

    if not model_scores:
        print("No models found or no valid data to compare!")
        return

    # Print results
    print_results(model_scores, detailed_scores, aic_contraindication_codes)

    # Optionally save results to a file
    output_file = os.path.join(results_directory, "model_comparison_results.json")
    comparison_results = {
        "model_scores": dict(model_scores),
        "detailed_scores": {
            model: {
                aic: dict(contraindications)
                for aic, contraindications in model_data.items()
            }
            for model, model_data in detailed_scores.items()
        },
        "summary": {
            "total_aics": len(aic_contraindication_codes),
            "total_contraindications": sum(
                len(contraindictions)
                for contraindictions in aic_contraindication_codes.values()
            ),
            "models_compared": list(model_scores.keys()),
        },
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
