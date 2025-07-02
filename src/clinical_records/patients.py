import requests
import json
import os
import pdb


BASE_URL = "https://r4.smarthealthit.org"


def save_json(data, filename, folder="output"):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved to {filepath}")


def get_patients(count=5):
    url = f"{BASE_URL}/Patient"
    params = {"_count": count}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_resources(resource_type, patient_id, params=None):
    if params is None:
        params = {}
    params["patient"] = patient_id
    url = f"{BASE_URL}/{resource_type}"
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def print_patients(patients_bundle):
    print("Patients:")
    for entry in patients_bundle.get("entry", []):
        patient = entry["resource"]
        name = patient.get("name", [{}])[0]
        full_name = " ".join(name.get("given", [])) + " " + name.get("family", "")
        print(f"- {full_name.strip()} (ID: {patient['id']})")
    print()


def print_conditions(conditions_bundle):
    print("Conditions:")
    for entry in conditions_bundle.get("entry", []):
        c = entry["resource"]
        code = c.get("code", {}).get("coding", [{}])[0]
        print(f"- {code.get('display', 'n/a')} ({code.get('code', 'n/a')})")
    print()


def print_medications(meds_bundle):
    print("Medications:")
    for entry in meds_bundle.get("entry", []):
        m = entry["resource"]
        coding = m.get("medicationCodeableConcept", {}).get("coding", [{}])[0]
        print(f"- {coding.get('display', 'n/a')}")
    print()


def print_allergies(allergy_bundle):
    print("Allergies / Intolerances:")
    for entry in allergy_bundle.get("entry", []):
        a = entry["resource"]
        coding = a.get("code", {}).get("coding", [{}])[0]
        print(f"- {coding.get('display', 'n/a')}")
    print()


def print_observations(obs_bundle):
    print("Observations:")
    for entry in obs_bundle.get("entry", []):
        o = entry["resource"]
        coding = o.get("code", {}).get("coding", [{}])[0]
        val = o.get("valueQuantity")
        if val:
            print(
                f"- {coding.get('display', 'n/a')}: {val.get('value', 'n/a')} {val.get('unit', '')}"
            )
        else:
            print(f"- {coding.get('display', 'n/a')}")
    print()


def main():

    patients_bundle = get_patients(count=5)
    print_patients(patients_bundle)

    for entry in patients_bundle.get("entry", []):
        patient = entry["resource"]
        patient_id = patient["id"]
        name = patient.get("name", [{}])[0]
        full_name = " ".join(name.get("given", [])) + " " + name.get("family", "")
        print("=" * 40)
        print(f"Patient: {full_name.strip()} (ID: {patient_id})\n")

        fields_of_interest = [
            "Condition",
            "AllergyIntolerance",
            "Observation",
            "MedicationRequest",
        ]

        try:
            for field in fields_of_interest:
                resources = get_resources(field, patient_id)
                save_json(
                    resources,
                    f"{field}.json",
                    f"../../data/patients/{full_name.strip()}",
                )

        except requests.HTTPError as e:
            print(f"Error retrieving data for patient {patient_id}: {e}")
        print("\n")


if __name__ == "__main__":
    main()
