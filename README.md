# Smart Ticket Understanding Engine

The **Smart Ticket Understanding Engine** is a complete, production-grade intelligent Service Desk Management Platform. Designed to mimic the operations of enterprise tools like ServiceNow and Jira Service Desk, the system leverages Machine Learning (NLP), Cosine Similarity, SQLite database triggers, and a modern Streamlit interface to optimize ticketing workflows, predict categories, retrieve root causes (RAG), and monitor SLA compliance.

---

## Architecture Modules

### Module 1: Ticket Classification
Uses TF-IDF Vectorization and Logistic Regression models trained on corporate IT incident texts. It classifies tickets across:
- **Incident Type**: Network, Hardware, Software, Access, Messaging, Application, Database, Security, HR.
- **Priority**: Predicted ML priority class (Critical, High, Medium, Low).
- **Department Routing**: Directs to the correct team (e.g. Infra Team, Desktop Support).
- **Sentiment/Urgency**: Predicts negative, neutral, or positive customer sentiment.

### Module 2: Routing Engine
Routes tickets to the assigned team. It processes the ML department classification alongside override mappings (e.g., password lockouts default to Service Desk L1, database errors go to Database Team, access requests go to IT Access Team).

### Module 3: RAG Engine
Implements Retrieval-Augmented ticket lookup. Incoming descriptions are vectorized and scanned against historical closed tickets using **Cosine Similarity**. The engine extracts and outputs:
- Top 3 matching tickets with their respective similarity scores.
- Historical Root Causes.
- Resolution steps.
- **Outlier Detection**: Flags tickets with a similarity score < 0.15 as outliers, alerting admins that a new classification category might be required.

### Module 4: Priority & SLA Engine
- **Hybrid Priority**: Integrates ML priority predictions with keyword search priority overrides (e.g. phrases like "production down" and "ransomware" trigger Critical priority, "unable to login" triggers High, and "slow" triggers Medium). The highest rank wins (Critical > High > Medium > Low).
- **SLA Engine**: Applies strict response windows based on priority:
  - **Critical**: 120 mins
  - **High**: 180 mins
  - **Medium**: 480 mins
  - **Low**: 960 mins
- Automatically checks compliance status (Met / Breached), calculating resolution times and delays.

### Module 5: Workflow Engine
Provides interactive columns (**New**, **In Progress**, **Escalated**, **Done**). Allows status tracking, assigning engineers, and logging transitions in the audit trail. Toggles `escalation_required` or `failure_case_flag` flags based on breach or reopen actions.

### Module 6: Knowledge Base
Aggregates historical root causes and successful resolutions. Tracks and renders **Reuse Metrics** specifying how many times a given resolution template or root cause was recommended/applied to incoming tickets.

### Module 7: Management Dashboard
Renders executive charts using Plotly:
- Metrics: Volumes, Active Backlog, Met Rates, Average Resolution Speed.
- Charts: Department Workload, Incident Distribution, Priority Split, SLA Compliance.
- **Radar KPI Chart**: Tracks SLA compliance, Closure rate, Routing Accuracy, KB Coverage, and Speed.
- **Capacity Planning**: Provides staffing suggestions based on queue backlogs and average resolution rates.

### Module 8: Continuous Learning
- **Anomaly Viewer**: Displays outlier tickets (< 0.15 similarity) for validation.
- **Feedback Loop**: Allows engineers to correct routing department or category, automatically raising a flag to alert that the models should be adjusted.
- **Dynamic Model Retraining**: Trigger retraining directly from the UI to refit TF-IDF vectorizers and classification weights on live SQLite rows.

---

## Technology Stack
- **Frontend**: Streamlit
- **Backend/Scripts**: Python
- **Database**: SQLite (`smart_ticket_engine.db`)
- **Machine Learning**: Scikit-Learn (TF-IDF Vectorizer + Logistic Regression)
- **Mathematical Search**: Cosine Similarity via Scikit-Learn
- **Visualization**: Plotly

---

## Installation and Execution

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Generate SQLite database and CSV Dataset**:
   ```bash
   python generate_dataset.py
   ```

3. **Train Machine Learning Models**:
   ```bash
   python train_model.py
   ```

4. **Launch Streamlit Dashboard**:
   ```bash
   streamlit run app.py
   ```

---

## Default User Accounts

- **Admin**: `admin` / `admin123` (Full system privileges)
- **Infra Team**: `infra` / `infra123`
- **Desktop Support**: `desktop` / `desktop123`
- **Application Support**: `app` / `app123`
- **Database Team**: `db` / `db123`
- **Security Team**: `security` / `security123`
- **Messaging Team**: `messaging` / `messaging123`
- **IT Access Team**: `access` / `access123`
- **Service Desk L1**: `l1` / `l1123`
- **HR IT Team**: `hrit` / `hrit123`
