🧬 OpenFDA Adverse Events Pipeline with LLM Triage

An automated ELT pipeline that extracts adverse drug event reports from the openFDA API, loads normalized records into Snowflake using dlt, enriches clinical risk with an LLM via Groq using Pydantic validation, and builds dimensional analytics views.

⚡ Architecture Flow

openFDA API ──(dlt)──> Snowflake RAW ──(Python + Key-Pair Auth)──> Groq LLM (gpt-oss-20b)
                                                                       │
Snowflake Analytics Marts <─── Snowflake ENRICHED <───(Pydantic JSON)──┘


🛠️ Tech Stack & Skills

Data Warehousing & SQL: Snowflake (RBAC, Warehouses, MERGE INTO, LATERAL SPLIT_TO_TABLE, Analytical Marts)

Data Engineering: Python, dlt (declarative ELT, schema evolution, merge disposition), REST APIs

Generative AI / LLMOps: Groq API, structured JSON outputs, Pydantic data validation (BaseModel, Literal, Field)

Security & Cloud Auth: Cryptography (2048-bit RSA key-pair authentication, PKCS#8), environment variable management

📁 Repository Structure

├── generate_keys.py       # Generates 2048-bit RSA key-pair for Snowflake auth
├── fda_pipeline.py        # Extracts OpenFDA data and loads to Snowflake RAW (dlt)
├── enrich_events_groq.py  # LLM classification job writing to Snowflake ENRICHED
├── setup.sql              # Snowflake setup (Roles, DB, Schemas, Warehouses, User key)
├── marts.sql              # Data Mart views (Summary, Signals, Priority Triage)
├── rsa_key.pub            # Public key (Configured on Snowflake user)
└── README.md


🚀 Quickstart

1. Install Dependencies

pip install dlt requests snowflake-connector-python cryptography groq pydantic


2. Set Environment Variables

export GROQ_API_KEY="your_groq_api_key"
export SNOWFLAKE_ACCOUNT="your_snowflake_account_locator"
export SNOWFLAKE_USER="your_snowflake_username"


3. Run Pipeline

# 1. Generate local RSA keys
python generate_keys.py

# 2. Run setup.sql in Snowflake Snowsight (paste rsa_key.pub into ALTER USER)

# 3. Ingest raw FDA events
python fda_pipeline.py

# 4. Run LLM clinical enrichment
python enrich_events_groq.py

# 5. Run marts.sql in Snowflake to create the reporting views


📊 Analytics Data Marts

MART_PHARMACOVIGILANCE_SUMMARY: Aggregated incidents, average risk score, and high-risk case percentages by category.

MART_DRUG_SAFETY_SIGNALS: Normalizes reported medications via LATERAL SPLIT_TO_TABLE to flag high-risk drugs.

MART_HIGH_PRIORITY_TRIAGE_QUEUE: Filtered operational queue prioritizing cases with risk_score >= 4 for clinical review.
