# Smart Ticket Understanding Engine

An intelligent **Service Desk Management Platform** built with Python and Streamlit. It combines ML classification, semantic search (RAG), and Groq LLM reasoning to route tickets, recommend resolutions, and track SLA compliance.

**Core idea:** ML classifies tickets quickly, RAG retrieves similar historical cases, and Groq synthesizes root cause and resolution steps using that context. If Groq is unavailable or fails, the system falls back to copied RAG recommendations.

---

## Features

| Area | What it does |
|------|----------------|
| **Hybrid ML/LLM classification** | XGBoost + Sentence Transformers; Groq fallback when any field confidence &lt; 65% |
| **RAG knowledge retrieval** | Cosine similarity over resolved tickets in SQLite |
| **Groq resolution engine** | Root cause, numbered steps, escalation, and team recommendation |
| **Priority engine** | ML priority + keyword overrides (e.g. "server down" → High) |
| **Smart routing** | ML department + keyword override rules |
| **SLA tracking** | Timers, breach detection, company-level auto-escalation (≥3 past breaches) |
| **Kanban workflow** | New → In Progress → Escalated → Done |
| **Admin dashboard** | Volume, SLA, department workload, KPI radar charts |
| **Knowledge base** | Aggregates reused root causes and resolutions |
| **Multi-tenant access** | Admin, Department User, and Company User roles |

---

## Intelligence Pipeline

When a ticket is submitted (`execute_ticket_creation_pipeline` in `app.py`):

```
Ticket submitted
      │
      ▼
┌─────────────────────────────────────┐
│ 1. ML Classification (TicketProcessor) │
│    Sentence Transformer → XGBoost   │
│    category, priority, dept, sentiment│
└─────────────────────────────────────┘
      │  Any field confidence < 65%?
      ▼
┌─────────────────────────────────────┐
│ 2. Groq LLM classification fallback │  (optional)
│    classify_ticket_fallback()       │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 3. Priority + Routing engines       │
│    keyword overrides, dept rules    │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 4. RAG retrieval                    │
│    find_similar_tickets() → top 3   │
│    filtered by dept / type / priority│
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 5. Groq resolution (primary)        │
│    generate_resolution()              │
│    Input: ticket + ML fields + RAG  │
│    Output: root cause, steps, esc.  │
└─────────────────────────────────────┘
      │  LLM fails / no API key?
      ▼
┌─────────────────────────────────────┐
│ 6. RAG fallback                     │
│    Copy root cause + resolution     │
│    from top similar historical ticket│
└─────────────────────────────────────┘
      │
      ▼
Save ticket + show Cognitive Analytics Summary
```

### Three separate Groq LLM calls

| Method | When | Purpose |
|--------|------|---------|
| `classify_ticket_fallback()` | ML confidence &lt; 65% on any field | Replace low-confidence ML labels |
| `generate_next_action()` | Every ticket (if Groq available) | Agent guidance shown as **Hybrid Engine Recommendation** |
| `generate_resolution()` | Every ticket (if Groq available) | **Root cause + resolution steps** (uses RAG context) |

> **Important:** RAG always runs first. Groq does **not** replace RAG — it reads similar tickets as context and writes a **new** answer. You only see `[Recommended Resolution (Based on Similar Ticket ID …)]` when Groq failed and the system used pure RAG fallback.

### RAG details

- **Knowledge base:** Resolved tickets in `smart_ticket_engine.db` (`status = 'Done'` or `root_cause IS NOT NULL`)
- **Embeddings:** `all-MiniLM-L6-v2` via Sentence Transformers (local `models/sentence_transformer_model/`)
- **Search:** Cosine similarity; optional filters on department, incident type, priority
- **Cache:** Embeddings cached in RAM after first search (faster subsequent lookups)
- **Outlier flag:** Top similarity &lt; 15% → `failure_case_flag = 1`

---

## User Roles & Portals

### Admin role (`admin` / `admin123`)

Admins have **full system access** across all companies, departments, and tickets. The admin portal has **7 navigation tabs** plus a global **Ticket Resolution Panel**.

**Admin-only privileges:**
- View and manage tickets from **every department** (not scoped to one team)
- Open the resolution panel on **closed (Done)** tickets from Kanban (department users cannot re-open Done tickets from Kanban)
- Access executive dashboards, system-wide audit logs, knowledge base analytics, and AI engine health
- Export the full ticket queue; correct routing/category on any ticket

**Sidebar (all roles, scoped for Admin):**
- Profile card (username, role)
- **Workspace Stats** — total queue, active backlog, closed tickets (system-wide for Admin)
- Logout

---

#### Tab 1: All Support Tickets

Central ticket database for the entire organization.

| Feature | Details |
|---------|---------|
| **Search** | Subject, description, company name |
| **Filters** | Priority (High / Medium / Low), department |
| **Paginated table** | ID, company, employee, subject, category, priority, department, status, engineer, SLA countdown, SLA status, created date |
| **Priority aging** | Tickets near SLA breach show ⬆️ aged priority in the table |
| **Enterprise sorting** | Critical / breached / SLA-remaining order |
| **Pagination** | Previous / Next; page size 50 / 100 / 200 / 500 |
| **Manage ticket** | Select any ticket ID → opens **Ticket Resolution Panel** below |
| **Export** | Download current queue as **CSV** or **JSON** |

---

#### Tab 2: Unified Kanban Board

Visual workflow board across all departments.

| Feature | Details |
|---------|---------|
| **Department filter** | All Departments or one of the 9 support teams |
| **Status columns** | New → In Progress → Escalated → Done (expandable sections) |
| **Ticket cards** | ID, subject, company, priority pill, SLA countdown pill, assigned engineer |
| **Manage button** | Opens Ticket Resolution Panel for any ticket (including Done) |
| **Sorting** | Enterprise priority: breached and high-priority tickets surface first |

---

#### Tab 3: Leadership SLA Dashboard

Executive-level operational dashboard (Plotly charts).

| Feature | Details |
|---------|---------|
| **KPI cards** | Total volume, active backlog, resolved count, SLA met rate %, SLA breaches, average resolution duration |
| **Department workload chart** | Stacked bar — queue status per department (New / In Progress / Escalated / Done) |
| **Incident type pie** | Category distribution across all tickets |
| **Priority pie** | High / Medium / Low split |
| **SLA compliance pie** | Met / Breached / In Progress |
| **Radar KPI index** | SLA met rate, closure rate, routing precision, KB reference coverage, resolution speed |
| **Capacity planner** | Per-department backlog, closed count, avg resolution time, staffing recommendation (e.g. “Additional Staff Recommended”, “Optimally Staffed”) |

---

#### Tab 4: Root Cause Knowledge Base

Browse proven resolutions that feed the RAG engine.

| Feature | Details |
|---------|---------|
| **Filters** | Department, incident type (Network, Hardware, Software, Access, etc.) |
| **Grouped entries** | Root cause + resolution steps from completed tickets |
| **Reuse frequency** | How many times each root-cause / resolution pair appeared in history |
| **Metadata** | Incident category, owning department |

---

#### Tab 5: Audit Logs

System-wide compliance and activity trail.

| Feature | Details |
|---------|---------|
| **Paginated log table** | 200 entries per page; Older / Newer navigation |
| **Per-entry fields** | Log ID, ticket ID, subject, company, user action, timestamp, status change (old → new), SLA remaining at action, SLA status, created/completed dates, resolution time, remarks |
| **Scope** | All tickets and all users across the platform |

---

#### Tab 6: Continuous Learning Loop

Model improvement and anomaly review.

| Feature | Details |
|---------|---------|
| **Outlier review** | Lists active tickets where RAG similarity was &lt; 15% (`failure_case_flag = 1`) — likely new problem types not in the knowledge base |
| **Retraining guidance** | UI retraining is disabled (memory safety); documents offline command `python train_xgboost_model.py` |
| **Engineer corrections** | When admins/engineers correct department or incident type in the Resolution Panel, `failure_case_flag` is set for retraining signal |

---

#### Tab 7: Performance Metrics

Deep operational KPIs and AI health monitoring.

| Feature | Details |
|---------|---------|
| **MTTR** | Mean Time To Resolve (overall) |
| **MTTM** | Mean Time To Mitigate (creation → first non-New status change) |
| **Resolution success rate** | Closed / total tickets % |
| **Avg resolution time** | Across completed tickets |
| **MTTR by incident category** | Horizontal bar chart |
| **MTTR by priority** | Bar chart (High / Medium / Low) |
| **Engineer performance** | Per-engineer: tickets resolved, avg resolution time, SLA met %, breaches; bar charts + table |
| **Monthly trend** | Combined chart — tickets resolved per month + avg resolution time line |
| **AI Engine Status** | Groq API key detected (green) vs missing (yellow fallback to RAG) |
| **AI adoption metric** | % of tickets whose `ai_recommended_resolution` contains LLM-structured `Root Cause:` output |

---

#### Ticket Resolution Panel (Admin + Department Users)

Opens when you click **Manage** on Kanban or **Manage Selected Ticket** in All Support Tickets. Admins can access **any** ticket; department users only their department.

| Section | What you can do |
|---------|-----------------|
| **Ticket details** | Subject, company, employee, description, channel, created date |
| **AI insights** | Incident type, sentiment, root cause, resolution steps, escalation, recommended team |
| **Similar tickets (RAG)** | Live similarity search with expandable historical matches |
| **SLA breach alert** | Warning if the company has past SLA violations |
| **Resolve / Update** | Change status, assign engineer, add remarks |
| **Continuous learning** | Correct department routing and incident type (flags ticket for model feedback) |
| **Per-ticket audit trail** | Full status history with SLA snapshots |

---

### Department User (e.g. `desktop` / `desktop123`)
- **Active Kanban Board** — department queue with status management
- **SLA Dashboard** — department metrics
- **History Audit Trail**
- **Ticket Resolution Panel** — assign engineer, update status, add remarks

### Company User (e.g. `techcorp_user` / `techcorp123`)
- **Submit New Ticket** — form with 10 pre-filled sample tickets for AI testing
- **Company Tickets Archive**
- **Company SLA Insights**
- Instant **Cognitive Analytics Summary** after submission (classification, RAG match %, root cause, resolution)

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| UI | Streamlit |
| Language | Python 3.8+ (tested on 3.13) |
| Database | SQLite (`smart_ticket_engine.db`) |
| ML | XGBoost, scikit-learn, joblib |
| NLP / embeddings | HuggingFace Sentence Transformers (`all-MiniLM-L6-v2`) |
| LLM | **Groq API** (`llama-3.3-70b-versatile` default) via `groq` package |
| RAG search | NumPy + scikit-learn cosine similarity |
| Charts | Plotly |
| Config | `python-dotenv` (`.env`) |

**Legacy (not used by `app.py`):** `gemini_engine.py` and `google-generativeai` — kept for reference; production path uses Groq only.

---

## Project Structure

```
project-drona/
├── app.py                         # Main Streamlit application
├── auth.py                        # Login and session layout
├── database.py                    # SQLite schema, CRUD, SLA helpers
├── ticket_processor.py            # Hybrid ML + LLM classification pipeline
├── ml_predictor.py                # Sentence Transformers + XGBoost predictors
├── llm_client.py                  # Groq client (classify, next action, resolution)
├── rag_engine.py                  # Semantic similarity search
├── priority_engine.py             # ML + keyword priority resolution
├── routing_engine.py              # Department routing + overrides
├── sla_engine.py                  # SLA minutes and compliance helpers
├── kanban.py                      # Kanban board renderer
├── generate_dataset.py            # Synthetic ticket generator + constants
├── train_xgboost_model.py         # Train/retrain ML models
├── populate_database_from_csv.py  # Load historical tickets for RAG
├── populate_rag_memory.py         # Alternative RAG population script
├── preprocess_data.py             # Dataset preprocessing
├── filter_english_only.py         # English dataset filter
├── test_rag_engine.py             # RAG smoke tests
├── test_ai_classification.py    # Classification tests
├── add_test_emails.py             # Gmail simulation test data
├── gmail_simulator.py             # Standalone email→ticket helper (not in main UI)
├── gemini_engine.py               # Legacy Gemini integration (unused)
├── fix_database.py                # DB repair utility
├── requirements.txt
├── .env.example
├── models/                        # Trained models (pre-built)
│   ├── sentence_transformer_model/
│   ├── category_model.pkl
│   ├── priority_model.pkl
│   ├── department_model.pkl
│   ├── sentiment_model.pkl
│   └── *_label_encoder.pkl
├── Data/                          # Training and import datasets
│   ├── train_data.csv
│   ├── val_data.csv
│   ├── test_data.csv
│   └── aa_dataset-tickets-multi-lang-5-2-50-version.csv
├── QUICK_START.md
├── RAG_SETUP_GUIDE.md
├── COMPANY_USER_TESTING_GUIDE.md
├── HOW_TO_POST_TICKETS.md
└── GEMINI_TO_GROQ_MIGRATION.md
```

---

## Installation & Setup

### Prerequisites
- Python 3.8+
- 4 GB+ RAM (8 GB recommended for RAG embedding cache)
- ~500 MB disk for models and database

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Groq API key (recommended)

Copy `.env.example` to `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=llama-3.3-70b-versatile
```

Get a free key at [Groq Console](https://console.groq.com/).

**Without `GROQ_API_KEY`:**
- ML classification still works
- RAG similarity search still works
- Root cause / resolution fall back to copied historical tickets
- Recommended next action uses a simple text fallback

**ML confidence threshold:** 65% (hardcoded in `app.py` → `get_ticket_processor(confidence_threshold=0.65)`).

### 3. Train models (optional)

Pre-trained models are included in `models/`. Retrain only if you change training data:

```bash
python train_xgboost_model.py
```

Uses `Data/train_data.csv`, `Data/val_data.csv`, `Data/test_data.csv`. Runtime ~5–10 minutes.

### 4. Populate RAG knowledge base (recommended)

```bash
python populate_database_from_csv.py
```

Imports from `Data/aa_dataset-tickets-multi-lang-5-2-50-version.csv` into SQLite. Without this, RAG returns few or no similar tickets until you resolve tickets manually.

Alternative:

```bash
python populate_rag_memory.py
```

### 5. Run the app

```bash
streamlit run app.py
```

Open **http://localhost:8501**

On first run: database schema is created, default users are seeded, Sentence Transformer loads into memory (~90 MB).

---

## Default User Accounts

### Admin & Department Users

| Username | Password | Role | Department |
|----------|----------|------|------------|
| `admin` | `admin123` | Admin | — |
| `infra` | `infra123` | Department User | Infra Team |
| `desktop` | `desktop123` | Department User | Desktop Support |
| `app` | `app123` | Department User | Application Support |
| `db` | `db123` | Department User | Database Team |
| `security` | `security123` | Department User | Security Team |
| `messaging` | `messaging123` | Department User | Messaging Team |
| `access` | `access123` | Department User | IT Access Team |
| `l1` | `l1123` | Department User | Service Desk L1 |
| `hrit` | `hrit123` | Department User | HR IT Team |

### Company Users

| Username | Password | Company |
|----------|----------|---------|
| `techcorp_user` | `techcorp123` | TechCorp Services |
| `tcs_user` | `tcs123` | TCS Global |
| `innotech_user` | `innotech123` | InnoTech Ltd |
| `finbank_user` | `finbank123` | FinBank Corp |
| `medsys_user` | `medsys123` | MedSystems |
| `cloud_user` | `cloud123` | CloudSphere |
| `edulearn_user` | `edulearn123` | EduLearn Inc |
| `apex_user` | `apex123` | Apex Retail |

**Quick test:** Login as `techcorp_user` / `techcorp123` → Submit New Ticket → pick a sample from the dropdown.

---

## Testing & Verification

### Test Groq LLM connection

```bash
python llm_client.py
```

Runs `generate_next_action()` with a sample VPN ticket. A successful run prints `✓ Groq client initialized` and a recommended action.

### Test full hybrid pipeline

```bash
python ticket_processor.py
```

Shows ML confidence scores, LLM fallback usage, and recommended next action.

### Test RAG engine

```bash
python test_rag_engine.py
```

### Test AI classification

```bash
python test_ai_classification.py
```

---

## SLA & Priority Reference

| Priority | SLA (minutes) |
|----------|---------------|
| High | 180 (3 hours) |
| Medium | 480 (8 hours) |
| Low | 960 (16 hours) |

**Keyword overrides** (examples): `server down`, `security breach`, `vpn down`, `urgent` → High.

**Company escalation:** Companies with ≥3 historical SLA breaches get new tickets auto-escalated one priority level.

---

## ML Classification Fields

| Field | Labels |
|-------|--------|
| Category | Incident, Request, Problem, Change |
| Priority | High, Medium, Low |
| Department | Infra Team, Desktop Support, Application Support, Database Team, Security Team, Messaging Team, IT Access Team, Service Desk L1, HR IT Team |
| Sentiment | Positive, Neutral, Negative, Urgent |

Each ML prediction includes a confidence score. Fields below 65% trigger Groq `classify_ticket_fallback()`.

---

## Troubleshooting

### Models not found

```
FileNotFoundError: Sentence Transformer model not found
```

```bash
python train_xgboost_model.py
```

### Root cause / resolution show RAG format (`Based on Similar Ticket ID…`)

This means Groq resolution did not run successfully. Check:

1. `GROQ_API_KEY` is set in `.env`
2. Restart Streamlit after editing `.env`
3. Admin → Performance Metrics → **AI Engine Status** should show green “Groq API Key Detected”
4. Submit a **new** ticket (old tickets keep whatever was stored at creation time)

### Groq works in terminal but not in Streamlit

Ensure `.env` is in the project root (`c:\project-drona\.env`) and restart:

```bash
streamlit run app.py
```

### No similar tickets / empty RAG

```bash
python populate_database_from_csv.py
```

Or create tickets, resolve them to **Done** in Kanban, then submit similar new tickets.

### RAG slow on first search

Normal. First query computes embeddings for filtered tickets (~10–30 s). Later queries use the in-memory cache (&lt;1 s while the app is running).

### Resolutions contain `<tel_num>`, `<email>` placeholders

The import CSV is anonymized. Placeholders come from historical data, not from Groq inventing them. Use your own company ticket history for production.

### Database corruption

```bash
# Windows — backup first, then delete and restart app
copy smart_ticket_engine.db smart_ticket_engine.db.backup
del smart_ticket_engine.db
streamlit run app.py
python populate_database_from_csv.py
```

### `torchvision` warnings

Safe to ignore for text-only models. Optional:

```powershell
$env:TRANSFORMERS_VERBOSITY="error"
```

---

## Additional Documentation

| File | Contents |
|------|----------|
| [QUICK_START.md](QUICK_START.md) | Fast setup walkthrough |
| [RAG_SETUP_GUIDE.md](RAG_SETUP_GUIDE.md) | RAG configuration and tuning |
| [COMPANY_USER_TESTING_GUIDE.md](COMPANY_USER_TESTING_GUIDE.md) | Sample tickets and test scenarios |
| [HOW_TO_POST_TICKETS.md](HOW_TO_POST_TICKETS.md) | API-style ticket submission examples |
| [GEMINI_TO_GROQ_MIGRATION.md](GEMINI_TO_GROQ_MIGRATION.md) | Groq migration notes |

---

## License

Educational and demonstration purposes.
