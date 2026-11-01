import dlt
import requests
from datetime import datetime, timedelta

FDA_API_URL = "https://api.fda.gov/drug/event.json"

def get_latest_fda_update_date() -> str:
    """Fetches the last date the openFDA database was updated."""
    resp = requests.get(f"{FDA_API_URL}?limit=1", timeout=15)
    resp.raise_for_status()
    meta = resp.json().get("meta", {})
    # meta['last_updated'] format is typically "YYYY-MM-DD"
    return meta.get("last_updated", "2024-06-01")

def get_fda_events(limit: int = 100):
    """
    Fetches adverse events from the most recent 3-month window of the latest FDA release.
    """
    latest_update_str = get_latest_fda_update_date()
    end_dt = datetime.strptime(latest_update_str, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=90)

    start_date = start_dt.strftime("%Y%m%d")
    end_date = end_dt.strftime("%Y%m%d")

    params = {
        "search": f"receiptdate:[{start_date} TO {end_date}]",
        "sort": "receiptdate:desc",
        "limit": limit
    }

    print(f"Database last refreshed: {latest_update_str}")
    print(f"Fetching up to {limit} records received between {start_date} and {end_date}...")

    response = requests.get(FDA_API_URL, params=params, timeout=30)
    if response.status_code == 404:
        print("No records found for this date window.")
        return

    response.raise_for_status()
    data = response.json()
    results = data.get("results") or []
    print(f"Successfully retrieved {len(results)} records. Loading into Snowflake...")

    for event in results:
        patient = event.get("patient") or {}
        primary_source = event.get("primarysource") or {}

        reaction_list = patient.get("reaction") or []
        drug_list = patient.get("drug") or []

        reactions = [
            rx.get("reactionmeddrapt")
            for rx in reaction_list
            if isinstance(rx, dict) and rx.get("reactionmeddrapt")
        ]

        drugs = [
            d.get("medicinalproduct")
            for d in drug_list
            if isinstance(d, dict) and d.get("medicinalproduct")
        ]

        yield {
            "safety_report_id": str(event.get("safetyreportid")),
            "receipt_date": event.get("receiptdate"),
            "transmission_date": event.get("transmissiondate"),
            "qualification": primary_source.get("qualification"),
            "reporter_country": event.get("primarysourcecountry"),
            "patient_age": patient.get("patientonsetage"),
            "patient_sex": patient.get("patientsex"),
            "reported_drugs": ", ".join(drugs) if drugs else None,
            "adverse_reactions": "; ".join(reactions) if reactions else None,
            "is_serious": str(event.get("serious")) == "1",
            "caused_hospitalization": str(event.get("seriousnesshospitalization")) == "1",
            "caused_death": str(event.get("seriousnessdeath")) == "1",
            "life_threatening": str(event.get("seriousnesslifethreatening")) == "1",
            "raw_reactions_json": str(reactions),
            "raw_drugs_json": str(drugs),
        }

if __name__ == "__main__":
    pipeline = dlt.pipeline(
        pipeline_name="fda_dlt_pipeline",
        destination="snowflake",
        dataset_name="RAW",
    )

    load_info = pipeline.run(get_fda_events(limit=100))
    print(load_info)
