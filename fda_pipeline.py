#gets data from fda api, transforms and flattend the json dats, and laods into into raw schem ain snowflake 
import dlt
import requests

FDA_API_URL = "https://api.fda.gov/drug/event.json"


@dlt.resource(fda_pipeline.py: 
    name="adverse_events",
    write_disposition="merge",
    primary_key="safety_report_id"
)
def get_fda_events(limit: int = 50):
    """
    Fetches official adverse drug event reports directly from OpenFDA
    and formats them for Snowflake ingestion.
    """
    params = {
        "limit": limit
    }

    print(f"Fetching {limit} adverse event records from OpenFDA...")
    response = requests.get(FDA_API_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    results = data.get("results", [])
    print(f"Successfully retrieved {len(results)} records. Transforming for Snowflake...")

    for event in results:
        patient = event.get("patient", {})

        # Extract reaction terms into a clean string and list
        reactions = [
            rx.get("reactionmeddrapt")
            for rx in patient.get("reaction", [])
            if rx.get("reactionmeddrapt")
        ]

        # Extract reported medications
        drugs = [
            d.get("medicinalproduct")
            for d in patient.get("drug", [])
            if d.get("medicinalproduct")
        ]

        # Seriousness flags
        is_serious = event.get("serious") == "1"
        caused_hospitalization = event.get("seriousnesshospitalization") == "1"
        caused_death = event.get("seriousnessdeath") == "1"
        life_threatening = event.get("seriousnesslifethreatening") == "1"

        yield {
            "safety_report_id": str(event.get("safetyreportid")),
            "receipt_date": event.get("receiptdate"),
            "transmission_date": event.get("transmissiondate"),
            "qualification": event.get("primarysource", {}).get("qualification"),
            "reporter_country": event.get("primarysourcecountry"),
            "patient_age": patient.get("patientonsetage"),
            "patient_sex": patient.get("patientsex"),
            "reported_drugs": ", ".join(drugs) if drugs else None,
            "adverse_reactions": "; ".join(reactions) if reactions else None,
            "is_serious": is_serious,
            "caused_hospitalization": caused_hospitalization,
            "caused_death": caused_death,
            "life_threatening": life_threatening,
            "raw_reactions_json": str(reactions),
            "raw_drugs_json": str(drugs),
        }


if __name__ == "__main__":
    pipeline = dlt.pipeline(
        pipeline_name="fda_dlt_pipeline",
        destination="snowflake",
        dataset_name="RAW",
    )

    load_info = pipeline.run(get_fda_events(limit=50))
    print("\n--- Pipeline Load Summary ---")
    print(load_info)