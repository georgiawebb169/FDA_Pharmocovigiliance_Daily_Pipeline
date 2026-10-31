🧬 End-to-End LLM-Augmented Pharmacovigilance Data PipelineAn automated ELT and AI-enrichment pipeline that extracts adverse drug event reports from the openFDA API, loads structured data into Snowflake using dlt (data load tool), enriches clinical safety records using an LLM via the Groq API with strict Pydantic schema validation, and exposes curated analytics views in Snowflake Data Marts.📌 Architecture Overview┌─────────────────┐       dlt Pipeline        ┌─────────────────────────┐
│   openFDA API   │ ────────────────────────> │ Snowflake: FDA_DB.RAW   │
│  (Adverse Drug  │     (Extract & Load)      │  (ADVERSE_EVENTS Table) │
│     Events)     │                           └────────────┬────────────┘
└─────────────────┘                                        │
                                                           │ Unprocessed Records
                                                           ▼
┌─────────────────┐       Pydantic Schema     ┌─────────────────────────┐
│    Groq API     │ <───────────────────────> │ Python Enrichment Job   │
│  (LLM Inference │     Validated JSON        │ (Key-Pair Authenticated)│
│  Classification)│                           └────────────┬────────────┘
└─────────────────┘                                        │
                                                           │ MERGE UPSERT
                                                           ▼
┌─────────────────────────────────┐           ┌─────────────────────────┐
│     Snowflake Data Marts        │ <──────── │  Snowflake: ENRICHED    │
│  - Pharmacovigilance Summary    │   Views   │ (ADVERSE_EVENTS_        │
│  - Drug Safety Signals          │           │     ENRICHED Table)     │
│  - High-Priority Triage Queue   │           └─────────────────────────┘
└─────────────────────────────────┘
🚀 Pipeline Workflow1. Security & Infrastructure Initialization (generate_keys.py, setup.sql)Generates an unencrypted 2048-bit PKCS#8 RSA key-pair using the Python cryptography library.Provisions Snowflake resources: role-based access control (FDA_ROLE), auto-suspending virtual warehouse (FDA_WH), and layered schemas (RAW, STAGING, ENRICHED, MART).Attaches the RSA public key to the Snowflake user profile for headless service authentication.2. Ingestion & Flattening (fda_pipeline.py)Extracts adverse drug event records from [https://api.fda.gov/drug/event.json](https://api.fda.gov/drug/event.json).Flattens nested JSON payloads into analytical schemas (MedDRA reaction terms, reported medications, seriousness indicators, and demographic fields).Utilizes dlt (data load tool) with a merge disposition on safety_report_id to handle idempotent loads into FDA_DB.RAW.ADVERSE_EVENTS.3. LLM Clinical Enrichment & Triage (enrich_events_groq.py)Queries unprocessed records from RAW that have not yet been evaluated.Connects via snowflake.connector utilizing local PKCS#8 private key parsing.Prompts an LLM (openai/gpt-oss-20b) via Groq's high-throughput inference engine using system-role prompt engineering.Enforces strict response structure using Pydantic (EventEnrichment):clinical_severity: Restricted to Mild, Moderate, Severe, Critical / Fatal.event_category: Categorized into standard safety incident classifications (e.g., Drug Interaction, Overdose / Toxicity).risk_score: Calibrated integer score from 1 (minor) to 5 (fatal/life-threatening).summary: 1–2 sentence clinical synopsis.Merges structured inference back into FDA_DB.ENRICHED.ADVERSE_EVENTS_ENRICHED using atomic MERGE INTO operations.4. Analytical Data Marts (marts.sql)Transforms the enriched dataset into three operational and reporting views:MART_PHARMACOVIGILANCE_SUMMARY: Aggregates incidents by category and severity, computing average risk scores and percentage of high-risk cases.MART_DRUG_SAFETY_SIGNALS: Normalizes comma-separated drug lists via LATERAL SPLIT_TO_TABLE to isolate high-risk active pharmaceutical ingredients and severe incident volume.MART_HIGH_PRIORITY_TRIAGE_QUEUE: Filters records with risk_score >= 4 for clinical safety officer triage.🛠️ Skills & Technologies DemonstratedCategorySkills & Tools AppliedCloud Data WarehousingSnowflake: RBAC (Roles/Grants), Virtual Warehouses, Multi-schema Architecture (RAW, ENRICHED, MART), MERGE INTO Upserts, LATERAL SPLIT_TO_TABLE.Data Engineering & ELTPython, dlt: Declarative resource extraction, automated schema evolution, idempotent state tracking, REST API consumption.Generative AI & LLMOpsGroq API, Prompt Engineering, Structured LLM Outputs, Pydantic schema modeling (BaseModel, Field, Literal), Low-temperature (0.1) deterministic inference.Security & DevOpsCryptography: Asymmetric 2048-bit RSA key generation (PKCS#8/DER/PEM), Key-pair headless Snowflake authentication, Environment variable isolation.Data Modeling & SQLDimensional modeling views, string normalization, CTEs, aggregation metrics, pharmacovigilance domain metrics.📂 Project StructurePlaintext├── generate_keys.py          # Generates RSA public/private key-pair for Snowflake auth
├── fda_pipeline.py           # dlt pipeline pulling OpenFDA data into Snowflake RAW
├── enrich_events_groq.py     # LLM inference script querying RAW, validating via Pydantic, merging into ENRICHED
├── setup.sql                 # Snowflake DDL for Roles, Warehouses, Databases, and Schemas
├── marts.sql                 # SQL views creating reporting and triage data marts
├── rsa_key.p8                # Private key (Ignored in .gitignore)
├── rsa_key.pub               # Public key (Configured on Snowflake user)
└── README.md
⚙️ Setup & Execution1. Prerequisites & Environment VariablesInstall dependencies:Bashpip install dlt requests snowflake-connector-python cryptography groq pydantic
Configure your environment variables:Bashexport GROQ_API_KEY="your-groq-api-key"
export SNOWFLAKE_ACCOUNT="your-account-locator"
export SNOWFLAKE_USER="your-username"
2. Execution OrderGenerate Security Keys:Bashpython generate_keys.py
Configure Snowflake:
Execute setup.sql in the Snowflake Snowsight console, copying your public key into the ALTER USER ... SET RSA_PUBLIC_KEY='...' command.Ingest Raw Data:Bashpython fda_pipeline.py
Run LLM Enrichment:Bashpython enrich_events_groq.py
Build Analytics Marts:
Execute marts.sql in Snowflake to create the reporting views.