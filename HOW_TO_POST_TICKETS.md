# How to Post Messages/Tickets to the System

This guide explains all the ways you can send messages, create tickets, or post data to the Smart Ticket Understanding Engine.

---

## 🌐 Method 1: Through the Web UI (Streamlit)

### Start the Application
```bash
streamlit run app.py
```

### Login
- Username: `admin`
- Password: `admin123`

### Navigate to "Gmail Simulation Gateway" Tab
- View incoming emails
- Click "Convert Email to Ticket" button
- System automatically classifies and routes the ticket

---

## 📧 Method 2: Add Test Emails Programmatically

### Create a Python Script

Create a file called `add_test_emails.py`:

```python
from database import add_gmail_email

# Add a test email to the inbox simulation
add_gmail_email(
    sender="john.doe@techcorp.com",
    company="TechCorp Services",
    subject="VPN Connection Issue - Urgent!",
    body="""
    Hi Support Team,
    
    I'm unable to connect to the company VPN since this morning. 
    I've tried restarting my laptop and the VPN client multiple times 
    but still getting connection timeout errors.
    
    This is blocking critical work as I need to access internal systems 
    for an important client meeting in 30 minutes.
    
    Please help ASAP!
    
    Thanks,
    John Doe
    IT Department
    """
)

print("✅ Test email added to inbox simulation!")
```

### Run the Script
```bash
python add_test_emails.py
```

### View in the App
1. Refresh the Streamlit app (press R)
2. Go to "Gmail Simulation Gateway"
3. You'll see the new email
4. Click "Convert Email to Ticket"

---

## 🔧 Method 3: Direct Ticket Creation via Python API

### Create a Direct Ticket Script

Create `create_ticket_direct.py`:

```python
from database import add_ticket
from datetime import datetime

# Create a ticket directly (bypassing the ML/LLM pipeline)
ticket_dict = {
    "company_name": "TechCorp Services",
    "employee_name": "Jane Smith",
    "employee_email": "jane.smith@techcorp.com",
    "ticket_subject": "Password Reset Request",
    "ticket_description": "I forgot my password and need it reset urgently. Cannot access my email.",
    "ticket_text": "Password Reset Request. I forgot my password and need it reset urgently. Cannot access my email.",
    "received_channel": "Phone",
    "incident_type": "Access",
    "ml_priority": "High",
    "keyword_priority": "High", 
    "final_priority": "High",
    "department": "Service Desk L1",
    "sentiment": "Urgent",
    "root_cause": "Forgotten password",
    "resolution_steps": "Reset password via Active Directory",
    "ai_recommended_resolution": "Contact user to verify identity, then reset password through AD.",
    "status": "New",
    "assigned_engineer": None,
    "engineer_remarks": "",
    "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "closed_date": None,
    "resolution_time_mins": None,
    "sla_mins": 180,  # 3 hours for High priority
    "sla_status": "In Progress",
    "escalation_required": 0,
    "failure_case_flag": 0
}

ticket_id = add_ticket(ticket_dict)
print(f"✅ Ticket #{ticket_id} created successfully!")
```

### Run the Script
```bash
python create_ticket_direct.py
```

---

## 🤖 Method 4: Using the Hybrid ML/LLM Pipeline

### Create a Ticket with AI Classification

Create `create_ticket_ai.py`:

```python
from app import execute_ticket_creation_pipeline

# This uses the full AI pipeline (ML + LLM + Gemini + RAG)
ticket_id, ticket_dict, rag_rec = execute_ticket_creation_pipeline(
    company="TechCorp Services",
    employee="Alice Johnson",
    email="alice.johnson@techcorp.com",
    subject="Database Connection Timeout",
    description="""
    Our production database is timing out frequently since yesterday evening.
    Multiple users are reporting slow queries and connection failures.
    This is affecting our critical e-commerce platform.
    Error logs show: "Connection timeout after 30 seconds"
    """,
    channel="Email"
)

print(f"✅ Ticket #{ticket_id} created with AI classification!")
print(f"📊 Category: {ticket_dict['incident_type']}")
print(f"📊 Priority: {ticket_dict['final_priority']}")
print(f"📊 Department: {ticket_dict['department']}")
print(f"📊 Sentiment: {ticket_dict['sentiment']}")
```

### Run the Script
```bash
python create_ticket_ai.py
```

---

## 📝 Method 5: Bulk Import from CSV

### Create a CSV File

Create `bulk_tickets.csv`:

```csv
company_name,employee_name,employee_email,subject,description
TechCorp Services,Bob Wilson,bob@techcorp.com,Printer Not Working,Office printer on 3rd floor is jammed and won't print
TechCorp Services,Carol Davis,carol@techcorp.com,Laptop Screen Flickering,My laptop screen has been flickering since this morning
FinBank Corp,David Lee,david@finbank.com,Cannot Access VPN,VPN client shows authentication error when trying to connect
```

### Create Import Script

Create `import_bulk_tickets.py`:

```python
import pandas as pd
from app import execute_ticket_creation_pipeline

# Read CSV file
df = pd.read_csv('bulk_tickets.csv')

# Process each ticket
for index, row in df.iterrows():
    print(f"\n📨 Processing ticket {index + 1}/{len(df)}...")
    
    ticket_id, ticket_dict, rag_rec = execute_ticket_creation_pipeline(
        company=row['company_name'],
        employee=row['employee_name'],
        email=row['employee_email'],
        subject=row['subject'],
        description=row['description'],
        channel="Bulk Import"
    )
    
    print(f"✅ Ticket #{ticket_id} created!")
    print(f"   Category: {ticket_dict['incident_type']}")
    print(f"   Priority: {ticket_dict['final_priority']}")
    print(f"   Routed to: {ticket_dict['department']}")

print(f"\n🎉 Successfully imported {len(df)} tickets!")
```

### Run the Import
```bash
python import_bulk_tickets.py
```

---

## 🌐 Method 6: REST API Integration (Future Enhancement)

Currently, the system uses Streamlit UI. To create a REST API:

### Install FastAPI
```bash
pip install fastapi uvicorn
```

### Create `api.py`

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app import execute_ticket_creation_pipeline

app = FastAPI(title="Smart Ticket API")

class TicketRequest(BaseModel):
    company: str
    employee: str
    email: str
    subject: str
    description: str
    channel: str = "API"

@app.post("/api/tickets")
async def create_ticket(ticket: TicketRequest):
    """Create a new ticket with AI classification"""
    try:
        ticket_id, ticket_dict, rag_rec = execute_ticket_creation_pipeline(
            company=ticket.company,
            employee=ticket.employee,
            email=ticket.email,
            subject=ticket.subject,
            description=ticket.description,
            channel=ticket.channel
        )
        
        return {
            "success": True,
            "ticket_id": ticket_id,
            "category": ticket_dict['incident_type'],
            "priority": ticket_dict['final_priority'],
            "department": ticket_dict['department'],
            "sentiment": ticket_dict['sentiment']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Smart Ticket Understanding Engine API"}
```

### Run the API
```bash
uvicorn api:app --reload --port 8000
```

### Post via cURL or Postman
```bash
curl -X POST "http://localhost:8000/api/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "company": "TechCorp Services",
    "employee": "Test User",
    "email": "test@techcorp.com",
    "subject": "Test Ticket",
    "description": "This is a test ticket from API",
    "channel": "API"
  }'
```

---

## 🔍 Method 7: Real Gmail Integration (Production)

For production use with real Gmail:

### Install Google API Client
```bash
pip install google-auth-oauthlib google-api-python-client
```

### Setup Instructions (Already in gmail_simulator.py)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project
3. Enable Gmail API
4. Create OAuth 2.0 credentials
5. Download `credentials.json`
6. Uncomment the Gmail integration code in `gmail_simulator.py`

---

## 📊 Summary of Methods

| Method | Use Case | Complexity | AI Classification |
|--------|----------|------------|-------------------|
| **Web UI** | Manual ticket creation | Easy | ✅ Yes |
| **Email Simulation** | Testing workflows | Easy | ✅ Yes |
| **Direct Python API** | Bypass AI for testing | Medium | ❌ No |
| **AI Pipeline Script** | Programmatic with AI | Medium | ✅ Yes |
| **Bulk CSV Import** | Large-scale data entry | Medium | ✅ Yes |
| **REST API** | External integrations | Advanced | ✅ Yes |
| **Real Gmail** | Production deployment | Advanced | ✅ Yes |

---

## 🎯 Quick Start Example

Here's the simplest way to add a test ticket:

```python
# quickstart_ticket.py
from database import add_gmail_email

add_gmail_email(
    sender="urgent@company.com",
    company="TechCorp Services", 
    subject="URGENT: Production Server Down!",
    body="Production server is completely down. All services are unavailable. This is a P1 incident!"
)

print("✅ Urgent ticket added! Open Streamlit app and convert it.")
```

```bash
python quickstart_ticket.py
streamlit run app.py
```

Then in the app:
1. Login as `admin` / `admin123`
2. Go to "Gmail Simulation Gateway"
3. Click "Convert Email to Ticket"
4. Watch the AI classify it! 🚀

---

## 💡 Tips

- **Use Gmail Simulation** for testing - it's the easiest way
- **Use Bulk Import** for loading many tickets at once
- **Use Direct API** when you need precise control
- **Use AI Pipeline** when you want smart classification
- The system automatically:
  - Classifies category, priority, department, sentiment
  - Routes to the correct team
  - Generates resolution recommendations
  - Tracks SLA compliance

---

## ❓ Need Help?

Check these files for more details:
- `database.py` - Database functions
- `app.py` - Main application logic
- `gmail_simulator.py` - Email simulation
- `ticket_processor.py` - AI classification pipeline
