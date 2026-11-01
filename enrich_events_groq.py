#This script extracts unprocessed drug adverse reaction reports from Snowflake, uses an LLM via the Groq API to analyze and 
#categorize clinical risk, and writes the structured assessments back to Snowflake.

import os #library that interacts with operating systems
import json #library for parsing and formatting json data 
from typing import Literal # restricts a string field to set values 
from pydantic import BaseModel, Field # base model is like a template used to structure data models with expected values - type hints Field adds metadata, constraints and validaiton rules to columns in the data model 
from groq import Groq # library that helps to interact with groq
import snowflake.connector # library for connecting with snowflake 
from cryptography.hazmat.backends import default_backend #this function gives code access to OpenSSL the standard crytographic engine 
from cryptography.hazmat.primitives import serialization #hazmat serves as a warning that incorrect use of these functions can lead to security malfunctions 
# serializati8on is the ability to convert data into a format that can be saved to disk, moved over a netowrk and relaoded later 
# ---------------------------------------------------------
# 1. Pydantic Pharmacovigilance Schema
# ---------------------------------------------------------
# so this desrcibes the 4 columns the llm must create and the values of those columns it is allwoed to return 
class EventEnrichment(BaseModel): # create schema called EventEnrichment, use basemodel template which has predefined data validation and json parsing abilities 
    clinical_severity: Literal["Mild", "Moderate", "Severe", "Critical / Fatal"] = Field(
        description="Assessed clinical severity of the adverse reaction." # model musyt return mild moderate severe or critical/fatal 
    )
    event_category: Literal[
        "Known Side Effect",
        "Medication / Administration Error",
        "Overdose / Toxicity",
        "Drug Interaction",
        "Product Quality / Defect",
        "Other"
    ] = Field(description="Primary clinical category of the safety incident.")
    risk_score: int = Field(
        ge=1, le=5,
        description="Triage risk scale from 1 (minor) to 5 (fatal/life-threatening)."
    )
    summary: str = Field(
        max_length=1000,
        description="A concise 1-2 sentence clinical summary of the drug reaction incident."
    )

# ---------------------------------------------------------
# 2. Snowflake Connection Helper (Key-Pair Auth)
# ---------------------------------------------------------
def get_snowflake_connection():
    with open("rsa_key.p8", "rb") as key_file: #rsa is digital credential, always public key and private key that are linked 
        #public key is given to snowflake, when i set up my snowflake acciunt i ran command ALTER USER GEORGIAMLWEBB SET RSA_PUBLIC_KEY='MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...';
        #private key is on my computer
        key_data = key_file.read()

    #private keys are either PEM or DER, PEM is plain text starting with -----BEGIN PRIVATE KEY-----
    if b"-----BEGIN" in key_data:
        p_key = serialization.load_pem_private_key( #prswes the key 
            key_data,
            password=os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "").encode() or None,#checks if key was encyrpted with a passphrase read from enivronemne varaibles , if no passophrase was set it passes none 
            backend=default_backend()
        )
    else:
        p_key = serialization.load_der_private_key(
            key_data,
            password=None,
            backend=default_backend()
        )

    pkb = p_key.private_bytes(#converts private key into format required by snowlake connector 
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    #connecrt tp snowflake schema 
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT", "DZOKCNJ-VC37479"),
        user=os.getenv("SNOWFLAKE_USER", "GEORGIAMLWEBB"),
        private_key=pkb,
        role="FDA_ROLE",
        warehouse="FDA_WH",
        database="FDA_DB",
        schema="ENRICHED"
    )

# ---------------------------------------------------------
# 3. LLM Enrichment Helper (Groq Free Tier)
# ---------------------------------------------------------
#creates function named enrich_event that takes parameters groq, drugs, reactions , will return a model trhat hasa schema defined byeventenrichment pydantic model 
def enrich_event(client: Groq, drugs: str, reactions: str) -> EventEnrichment:
    # this is text sent to llm, 
    #Medication: Ibuprofen
    #Adverse Reactions: rash

    #Return ONLY a valid JSON object matching this schema:
    #{
    # "clinical_severity": "Mild" | "Moderate" | "Severe" | "Critical / Fatal",
    # "event_category": "Known Side Effect" | "Medication / Administration Error" | "Overdose / Toxicity" | "Drug Interaction" | "Product Quality / Defect" | "Other",
    # "risk_score": <int 1-5>,
    # "summary": "<concise 1-2 sentence clinical summary>"
    #}
    prompt = (
        f"Medication: {drugs}\n"
        f"Adverse Reactions: {reactions}\n\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "clinical_severity": "Mild" | "Moderate" | "Severe" | "Critical / Fatal",\n'
        '  "event_category": "Known Side Effect" | "Medication / Administration Error" | "Overdose / Toxicity" | "Drug Interaction" | "Product Quality / Defect" | "Other",\n'
        '  "risk_score": <int 1-5>,\n'
        '  "summary": "<concise 1-2 sentence clinical summary>"\n'
        "}"
    )

    # api requires oyu to tag every messga eiwht who uis soeaking using a role 
    # role: system means the next set of instructions are very important'
    # role: user means this is the person asking the quesiont, this is the current task the llm is being asked to solve 
    # so systme si like this is what the lm shiould feel, and user is like this is the task you are being asked to do 
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a clinical pharmacovigilance safety officer. Output valid JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        model="llama-3.1-8b-instant",
        response_format={"type": "json_object"},
        temperature=0.1 # lower the number, the more determinsitc, strict, robotic the next word ai generates is, typically 0.0 to 1.0, sometimes up to 2.0 
    )

    #chat_completion is the respons ebudnle returned by the api 
    raw_json = chat_completion.choices[0].message.content # get the text string writtne by ai, message is te metadats sbout the role and the promt, , choices is lst of answers the model geenrated, you cna ask a llm for multiple answers and htenpick, we didnt we jsut asked for 1 chih is hwy it is sety oty thef irst 1 at 0 
    return EventEnrichment.model_validate_json(raw_json) # passes the respobse to my pydantic class whcih is eventenrichement , model vlaidate json says make the text into json data, 

# ---------------------------------------------------------
# 4. Main Processing Loop
# ---------------------------------------------------------
#function called main, take no parameters, variable that has groq api key, gives error if no key  
def main():
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("Please set $env:GROQ_API_KEY='your-gsk-key' before running.")

    client = Groq(api_key=groq_api_key)
    conn = get_snowflake_connection() # connection 
    cursor = conn.cursor() # A cursor is a workhorse object spawned from that connection to execute SQL commands and fetch results.

    try:
        # Create target table if missing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fda_DB.ENRICHED.ADVERSE_EVENTS_ENRICHED (
                safety_report_id VARCHAR PRIMARY KEY,
                reported_drugs VARCHAR,
                adverse_reactions VARCHAR,
                clinical_severity VARCHAR,
                event_category VARCHAR,
                risk_score INT,
                summary VARCHAR,
                enriched_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)

        # Pull raw events not yet enriched
        cursor.execute("""
            SELECT 
                r.safety_report_id, 
                r.reported_drugs, 
                r.adverse_reactions
            FROM fda_DB.RAW.ADVERSE_EVENTS r
            LEFT JOIN fda_DB.ENRICHED.ADVERSE_EVENTS_ENRICHED e
                ON r.safety_report_id = e.safety_report_id
            WHERE r.adverse_reactions IS NOT NULL
              AND e.safety_report_id IS NULL
            LIMIT 50
        """)
        records = cursor.fetchall() # get all the records 
        print(f"Found {len(records)} records ready to enrich.")

        insert_sql = """
            MERGE INTO fda_DB.ENRICHED.ADVERSE_EVENTS_ENRICHED target
            USING (SELECT %s AS id) src
            ON target.safety_report_id = src.id
            WHEN MATCHED THEN UPDATE SET
                reported_drugs = %s,
                adverse_reactions = %s,
                clinical_severity = %s,
                event_category = %s,
                risk_score = %s,
                summary = %s,
                enriched_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT 
                (safety_report_id, reported_drugs, adverse_reactions, clinical_severity, event_category, risk_score, summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        #idx is short for index, it is a counter which counts which item you are starting with 1, return 3 variables saety report id, drugs, reactions 
        for idx, (safety_report_id, drugs, reactions) in enumerate(records, 1):
            print(f"[{idx}/{len(records)}] Enriching ID {safety_report_id}...")
            #[1/50] Enriching ID 1001...
            #[2/50] Enriching ID 1002...
            #calls the function we made earlier , enrich_event(client: Groq, drugs: str, reactions: str) -> EventEnrichment:
            enriched = enrich_event(client, drugs or "Unknown", reactions) # this returns 4 columns, clincial severity, event cateogry, risk score, summary 
            #drugs or "Unknown": A safety fallback. If the database record had an empty or None value for the drug name, it passes the string "Unknown" so the prompt doesn't break.
            params = (
                safety_report_id,
                drugs, reactions, enriched.clinical_severity, enriched.event_category, enriched.risk_score, enriched.summary,
                safety_report_id, drugs, reactions, enriched.clinical_severity, enriched.event_category, enriched.risk_score, enriched.summary
            )
            cursor.execute(insert_sql, params) # sends merge query and data to snwoflake 
            conn.commit() # commits the transatioun to the databse immediatly so change is permanent 

        print("\nAll records enriched and merged into fda_DB.ENRICHED.ADVERSE_EVENTS_ENRICHED successfully!")

    finally:# this runs no matter what happens in the try block 
        cursor.close()
        conn.close() # cursor.close(): Releases the cursor memory and frees server-side query resources in Snowflake.

#conn.close(): Closes the active network session and disconnects from Snowflake.

#Why this matters: If a script crashes without closing its connection, it leaves "hanging" or orphaned sessions on Snowflake. That wastes warehouse resources and can keep database locks open.

if __name__ == "__main__":
    main()
#If you run the file directly from your terminal (e.g., python script.py), Python sets __name__ to "__main__". The if condition evaluates to True, and it calls main().
