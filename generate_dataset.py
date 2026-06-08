import pandas as pd
import numpy as np
import random
import sqlite3
import os
from datetime import datetime, timedelta

# List of Companies
COMPANIES = ["TCS Global", "TechCorp Services", "InnoTech Ltd", "FinBank Corp", "MedSystems", "CloudSphere", "EduLearn Inc", "Apex Retail"]

# List of Employees
FIRST_NAMES = ["John", "Sarah", "Emily", "Michael", "David", "Jessica", "James", "Amanda", "Robert", "Ashley", "Daniel", "Lisa", "William", "Karen", "Thomas", "Nancy"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson"]

# Departments
DEPARTMENTS = [
    "Infra Team", "Desktop Support", "Application Support", "Database Team",
    "Security Team", "Messaging Team", "IT Access Team", "Service Desk L1", "HR IT Team"
]

# Engineers by Department
ENGINEERS = {
    "Infra Team": ["Robert Infra", "Steven Cable"],
    "Desktop Support": ["Jack Hardware", "Peter Screws"],
    "Application Support": ["Anna Code", "Dave Debugger"],
    "Database Team": ["Nora Index", "Carl Query"],
    "Security Team": ["Alice Firewall", "Bob Secure"],
    "Messaging Team": ["Mary Mail", "Gary Outlook"],
    "IT Access Team": ["Sam Permit", "Tina Key"],
    "Service Desk L1": ["Leo Helpdesk", "Sally Support"],
    "HR IT Team": ["Heidi HR", "Richard Staff"]
}

# Incident templates mapping: incident_type -> detailed info
TEMPLATES = [
    # Network
    {
        "incident_type": "Network",
        "subject": "VPN connection drops frequently",
        "description": "My corporate VPN connection keeps dropping every 5 minutes while I'm trying to work from home. Need urgent help as client call is scheduled.",
        "department": "Infra Team",
        "keywords": ["vpn down", "urgent", "client call"],
        "root_cause": "Outdated VPN client version causing handshake timeout with the gateway.",
        "resolution_steps": "1. Verify VPN credentials.\n2. Reset VPN profile.\n3. Upgrade to latest Cisco AnyConnect client.\n4. Clear cached credentials.\n5. Restart VPN client.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Network",
        "subject": "Complete outage in office WiFi network",
        "description": "The entire second floor is experiencing a complete outage on the office WiFi network. No devices can connect, server down for local services.",
        "department": "Infra Team",
        "keywords": ["complete outage", "server down"],
        "root_cause": "Core router stack loop due to a misconfigured VLAN switch.",
        "resolution_steps": "1. Log into core router switch interface.\n2. Reset switch loop protection control.\n3. Restore router default VLAN routing configuration.\n4. Restart office access points.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Network",
        "subject": "Router configuration error in branch office",
        "description": "Branch office router is slow and throwing intermittent packet loss errors. Intermittent issue with routing tables.",
        "department": "Infra Team",
        "keywords": ["slow", "intermittent issue"],
        "root_cause": "Corrupted BGP routing table entry on the branch router gateway.",
        "resolution_steps": "1. Reset branch gateway router.\n2. Clear BGP cache routing protocols.\n3. Re-sync routing metrics with the primary hub.",
        "sentiment": "Neutral"
    },
    # Hardware
    {
        "incident_type": "Hardware",
        "subject": "Laptop screen flickers and blue screen of death",
        "description": "My Lenovo laptop screen is flickering continuously, followed by a Blue Screen (BSOD). Client call scheduled, customer impacted.",
        "department": "Desktop Support",
        "keywords": ["customer impacted", "client call"],
        "root_cause": "Faulty Intel HD Graphics driver causing memory dump crash.",
        "resolution_steps": "1. Boot laptop into Safe Mode.\n2. Uninstall current display drivers.\n3. Download and install verified Lenovo stable GPU drivers.\n4. Restart laptop.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Hardware",
        "subject": "Office printer issue - paper jam and network offline",
        "description": "The printer in the main hall has a printer issue. It says paper jam but we cleared it, and it remains offline.",
        "department": "Desktop Support",
        "keywords": ["printer issue", "intermittent issue"],
        "root_cause": "Optical paper feed sensor dirty with paper dust.",
        "resolution_steps": "1. Open printer side access door.\n2. Clean the internal optical feed sensors with compressed air.\n3. Reset printer print spooler queue.",
        "sentiment": "Neutral"
    },
    {
        "incident_type": "Hardware",
        "subject": "Request for a new wireless keyboard and desktop mouse",
        "description": "My keyboard has some keys that do not work. Submitting an information request for a replacement keyboard.",
        "department": "Desktop Support",
        "keywords": ["information request"],
        "root_cause": "Physical wear and tear of keyboard membrane.",
        "resolution_steps": "1. Assign replacement keyboard from desktop support inventory.\n2. Update hardware serial number in asset tracker.",
        "sentiment": "Positive"
    },
    # Software
    {
        "incident_type": "Software",
        "subject": "OS Issue - Windows update failed loop",
        "description": "My laptop is stuck in an infinite loop saying 'Undoing changes made to your computer' after a Windows Update failed. High urgency.",
        "department": "Application Support",
        "keywords": ["urgent"],
        "root_cause": "Corrupt system registry hive after interrupted Windows update transaction.",
        "resolution_steps": "1. Access WinRE recovery menu.\n2. Revert pending system updates via Command Prompt command dism.\n3. Run SFC scan.\n4. Reboot OS normally.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Software",
        "subject": "Installation request for MS Visio and Project",
        "description": "I need MS Visio and Project installed on my local machine for project diagrams. Installation request.",
        "department": "Application Support",
        "keywords": ["installation request"],
        "root_cause": "Standard software request needing automated package push.",
        "resolution_steps": "1. Check software license pool availability.\n2. Push Visio MSI package through SCCM deployment.\n3. Verify app launcher on target machine.",
        "sentiment": "Positive"
    },
    # Access
    {
        "incident_type": "Access",
        "subject": "Locked out of AD account - unable to login",
        "description": "I locked my active directory account after entering password incorrectly. Unable to login to workstation.",
        "department": "Service Desk L1",
        "keywords": ["unable to login"],
        "root_cause": "User entered expired password multiple times causing AD lockout policy trigger.",
        "resolution_steps": "1. Look up user Active Directory profile.\n2. Verify identity via security verification questions.\n3. Unlock AD account.\n4. Issue temporary reset password.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Access",
        "subject": "Shared folder access request",
        "description": "Please grant access to the shared finance folder for audit files. Account creation and permissions request.",
        "department": "IT Access Team",
        "keywords": ["account creation", "information request"],
        "root_cause": "Standard role change requiring access control modification.",
        "resolution_steps": "1. Verify manager approval via approval chain.\n2. Add user account to security group SG-Finance-Read.\n3. Force AD replication.",
        "sentiment": "Neutral"
    },
    # Messaging
    {
        "incident_type": "Messaging",
        "subject": "Outlook email issue - cannot send emails",
        "description": "Outlook is throwing an error '0x8004010F' and won't send emails. Intermittent email issue.",
        "department": "Messaging Team",
        "keywords": ["email issue", "intermittent issue"],
        "root_cause": "Corrupted Outlook offline address book file (OAB).",
        "resolution_steps": "1. Close Outlook.\n2. Delete local .oab files from AppData cache.\n3. Re-open Outlook and force send/receive sync.",
        "sentiment": "Neutral"
    },
    # Application
    {
        "incident_type": "Application",
        "subject": "Production payment failure in checkout portal",
        "description": "The online payment failure is occurring. Production down, customers cannot complete purchases. Complete outage on payment gateway.",
        "department": "Application Support",
        "keywords": ["production down", "payment failure", "complete outage"],
        "root_cause": "SSL certificate handshake error with payment processor due to obsolete TLS protocol version.",
        "resolution_steps": "1. Review application exception logs.\n2. Enable TLS 1.3 in payment module configuration.\n3. Deploy hotfix to prod cluster.\n4. Perform transaction test.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Application",
        "subject": "Application error - slow reports query",
        "description": "The inventory system reports dashboard is very slow and times out frequently. Report issue.",
        "department": "Application Support",
        "keywords": ["slow", "report issue"],
        "root_cause": "Missing index on transaction_date column in reporting database.",
        "resolution_steps": "1. Analyze report query execution plan.\n2. Identify missing query indices.\n3. Implement index optimization.\n4. Verify dashboard rendering speed.",
        "sentiment": "Neutral"
    },
    # Database
    {
        "incident_type": "Database",
        "subject": "Database corruption in SQL Server",
        "description": "Database corruption detected on DB-PROD-01. Customer table reports data page corruptions, database corruption threat, severe data loss risk.",
        "department": "Database Team",
        "keywords": ["database corruption", "data loss"],
        "root_cause": "Disk hardware controller write failure corrupted SQL database data pages.",
        "resolution_steps": "1. Run DBCC CHECKDB command.\n2. Restore database from last clean backup differential.\n3. Re-apply transaction logs.\n4. Validate record counts.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Database",
        "subject": "Database issue - query locking causing timeouts",
        "description": "Database issue. Long running lock blocks multiple critical queries on application database, causing slow response times.",
        "department": "Database Team",
        "keywords": ["database issue", "slow"],
        "root_cause": "Unindexed foreign keys causing table scans and deadlock loops.",
        "resolution_steps": "1. Run sp_who2 to identify blocking SPID.\n2. Terminate blocker process safely.\n3. Add missing query index.\n4. Refactor transaction isolation level.",
        "sentiment": "Neutral"
    },
    # Security
    {
        "incident_type": "Security",
        "subject": "Ransomware alert on local fileserver",
        "description": "Ransomware warning! Internal file server files have extension .locked. Security breach! Complete outage of documents.",
        "department": "Security Team",
        "keywords": ["ransomware", "security breach", "complete outage"],
        "root_cause": "Malware execution via email attachment bypass.",
        "resolution_steps": "1. Isolate target file server from local area network.\n2. Terminate infected system processes.\n3. Scan active directory for lateral movement indicators.\n4. Restore documents from cold backup storage.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Security",
        "subject": "Certificate expired error on internal portal",
        "description": "Users are getting a security warning on internal portals. Certificate expired error, unable to login securely.",
        "department": "Security Team",
        "keywords": ["certificate expired", "unable to login"],
        "root_cause": "Automation script failed to renew SSL certificate from internal Certificate Authority.",
        "resolution_steps": "1. Generate CSR on web server.\n2. Submit request to corporate PKI portal.\n3. Install updated SSL certificate in IIS binding.\n4. Verify HTTPS routing.",
        "sentiment": "Negative"
    },
    {
        "incident_type": "Security",
        "subject": "Phishing email detected targeting team inbox",
        "description": "We received an email looking like it's from executive leadership asking for urgent bank info. Possible phishing attempt.",
        "department": "Security Team",
        "keywords": ["urgent", "security breach"],
        "root_cause": "Spoofed email domain bypassing DMARC policies.",
        "resolution_steps": "1. Analyze email header headers.\n2. Block sender domain at Exchange Gateway.\n3. Delete phishing emails from user mailboxes.\n4. Update SPF/DKIM policy records.",
        "sentiment": "Negative"
    },
    # HR
    {
        "incident_type": "HR",
        "subject": "Onboarding request for new engineer starting next week",
        "description": "Please complete onboarding setup for the new team member, including account creation and onboarding documents.",
        "department": "HR IT Team",
        "keywords": ["onboarding", "account creation"],
        "root_cause": "Standard recruitment profile pipeline entry.",
        "resolution_steps": "1. Create AD login credentials.\n2. Allocate laptop and workspace peripherals.\n3. Provision Microsoft 365 license.\n4. Schedule HR welcome briefing.",
        "sentiment": "Positive"
    }
]

def generate_mock_emails():
    """Generates 5 initial simulated emails."""
    return [
        {
            "sender_email": "jane.manager@retailcorp.com",
            "company_name": "RetailCorp",
            "subject": "New employee onboarding - Alice Johnson",
            "email_body": "Hello Support, please handle onboarding account creation for Alice Johnson starting next Monday. She needs standard application permissions.",
            "received_time": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "converted_to_ticket": 0
        },
        {
            "sender_email": "security_alerts@tcsglobal.com",
            "company_name": "TCS Global",
            "subject": "Urgent: Phishing email detected in finance dept",
            "email_body": "An email claiming to be our CFO asking for bank transfers is circulating. Multiple users reported it. Looks like a phishing scam. Urgently block domain.",
            "received_time": (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            "converted_to_ticket": 0
        },
        {
            "sender_email": "ops_engineer@cloudsphere.com",
            "company_name": "CloudSphere",
            "subject": "Database corruption issue on test database",
            "email_body": "Our staging MySQL node failed disk checks and is reporting database corruption on schema indexes. Please check RAG and advise.",
            "received_time": (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
            "converted_to_ticket": 0
        },
        {
            "sender_email": "robert.worker@inno.com",
            "company_name": "InnoTech Ltd",
            "subject": "WiFi slow and dropping in room 405",
            "email_body": "Hi Desk, our team meeting is disrupted. WiFi is super slow with intermittent issue reconnecting. Please check local router configuration.",
            "received_time": (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
            "converted_to_ticket": 0
        },
        {
            "sender_email": "boss@finbank.com",
            "company_name": "FinBank Corp",
            "subject": "Production payment failure - customers cannot checkout",
            "email_body": "CRITICAL: The production environment is throwing payment failure alerts. This is causing complete outage in sales. Urgent attention required!",
            "received_time": (datetime.now() - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
            "converted_to_ticket": 0
        }
    ]

def map_ml_priority_from_template(keywords):
    """Maps priority predicted by keyword logic (used as mock ML priority)."""
    # Simply make ML priority align close to keywords to simulate a train-ready model
    if any(k in ["server down", "production down", "security breach", "ransomware", "data loss", "payment failure", "database corruption", "complete outage"] for k in keywords):
        return "Critical"
    elif any(k in ["urgent", "client call", "customer impacted", "unable to login", "vpn down", "application unavailable", "certificate expired"] for k in keywords):
        return "High"
    elif any(k in ["slow", "intermittent issue", "printer issue", "report issue", "email issue"] for k in keywords):
        return "Medium"
    else:
        return "Low"

def generate_ticket_record(index, template, created_date, status_case):
    """Generates a structured dictionary representing a ticket."""
    company = random.choice(COMPANIES)
    fname = random.choice(FIRST_NAMES)
    lname = random.choice(LAST_NAMES)
    emp_name = f"{fname} {lname}"
    emp_email = f"{fname.lower()}.{lname.lower()}@{company.lower().replace(' ', '')}.com"
    channel = random.choice(["Email", "Chat", "Service Portal", "Manual"])
    
    # Priority resolution
    kw_prio = map_ml_priority_from_template(template["keywords"])
    
    # Add minor noise for ML priority
    ml_prio = kw_prio
    if random.random() < 0.15:
        ml_prio = random.choice(["Critical", "High", "Medium", "Low"])
        
    # Final Priority resolution
    prio_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    final_prio = kw_prio if prio_order[kw_prio] >= prio_order[ml_prio] else ml_prio
    
    # SLA mapping
    sla_mins_map = {"Critical": 120, "High": 180, "Medium": 480, "Low": 960}
    sla_mins = sla_mins_map[final_prio]
    
    dept = template["department"]
    engineer = random.choice(ENGINEERS[dept])
    
    # Cases setup:
    # 1. Normal (Done within SLA)
    # 2. Failure Case (Has failure flag, e.g. bugs/bad initial classification)
    # 3. Escalated (In Progress or Escalated, status = Escalated)
    # 4. Reopened (Status = In Progress, failure flag = 1)
    # 5. SLA Breach (Done, but time > SLA limit)
    
    status = "New"
    failure_case_flag = 0
    escalation_required = 0
    sla_status = "In Progress"
    closed_date = None
    resolution_time_mins = None
    remarks = ""
    
    if status_case == "Normal":
        status = "Done"
        sla_status = "Met"
        resolution_time_mins = round(random.uniform(10, sla_mins * 0.9), 1)
        closed_dt = created_date + timedelta(minutes=resolution_time_mins)
        closed_date = closed_dt.strftime("%Y-%m-%d %H:%M:%S")
        remarks = "Resolved as per standard procedures. Tested and verified."
    elif status_case == "Failure":
        status = "Done"
        sla_status = "Met"
        resolution_time_mins = round(random.uniform(30, sla_mins * 0.95), 1)
        closed_dt = created_date + timedelta(minutes=resolution_time_mins)
        closed_date = closed_dt.strftime("%Y-%m-%d %H:%M:%S")
        remarks = "Resolved but customer complained of side effects. Ticket flagged."
        failure_case_flag = 1
    elif status_case == "Escalated":
        status = "Escalated"
        escalation_required = 1
        remarks = "Requires L2 / L3 assistance. Transferring queue."
    elif status_case == "Reopened":
        status = "In Progress"
        failure_case_flag = 1
        remarks = "Ticket was reopened due to recurring issues."
    elif status_case == "SLA_Breach":
        status = "Done"
        sla_status = "Breached"
        resolution_time_mins = round(sla_mins + random.uniform(20, 300), 1)
        closed_dt = created_date + timedelta(minutes=resolution_time_mins)
        closed_date = closed_dt.strftime("%Y-%m-%d %H:%M:%S")
        remarks = "Delayed resolution due to pending approvals and hardware parts arrival."
        escalation_required = 1
        
    created_date_str = created_date.strftime("%Y-%m-%d %H:%M:%S")
    
    ticket_text = f"{template['subject']}. {template['description']}"
    
    return {
        "company_name": company,
        "employee_name": emp_name,
        "employee_email": emp_email,
        "ticket_subject": template["subject"],
        "ticket_description": template["description"],
        "ticket_text": ticket_text,
        "received_channel": channel,
        "incident_type": template["incident_type"],
        "ml_priority": ml_prio,
        "keyword_priority": kw_prio,
        "final_priority": final_prio,
        "department": dept,
        "sentiment": template["sentiment"],
        "root_cause": template["root_cause"],
        "resolution_steps": template["resolution_steps"],
        "ai_recommended_resolution": f"AI Recommended Resolution:\n{template['resolution_steps']}",
        "status": status,
        "assigned_engineer": engineer,
        "engineer_remarks": remarks,
        "created_date": created_date_str,
        "closed_date": closed_date,
        "resolution_time_mins": resolution_time_mins,
        "sla_mins": sla_mins,
        "sla_status": sla_status,
        "escalation_required": escalation_required,
        "failure_case_flag": failure_case_flag
    }

def main():
    print("Generating ticket dataset...")
    random.seed(42)
    tickets = []
    
    # Generate 110 tickets
    # We want a distribution: 
    # Normal: 70
    # Failure: 10
    # Escalated: 10
    # Reopened: 10
    # SLA Breach: 10
    cases_distribution = (["Normal"] * 70) + (["Failure"] * 10) + (["Escalated"] * 10) + (["Reopened"] * 10) + (["SLA_Breach"] * 10)
    
    start_date = datetime.now() - timedelta(days=15)
    
    for i, status_case in enumerate(cases_distribution):
        template = random.choice(TEMPLATES)
        # Advance date progress
        created_date = start_date + timedelta(hours=3 * i) + timedelta(minutes=random.randint(0, 59))
        ticket = generate_ticket_record(i+1, template, created_date, status_case)
        tickets.append(ticket)
        
    df = pd.DataFrame(tickets)
    
    # Store to CSV
    csv_path = os.path.join(os.path.dirname(__file__), "tickets_dataset.csv")
    df.to_csv(csv_path, index=False)
    print(f"Dataset stored successfully in {csv_path}. Row count: {len(df)}")
    
    # Seed SQLite database
    print("Seeding SQLite database tickets table...")
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "smart_ticket_engine.db"))
    cursor = conn.cursor()
    
    # Clean previous tickets
    cursor.execute("DELETE FROM tickets")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='tickets'")
    cursor.execute("DELETE FROM ticket_history")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='ticket_history'")
    cursor.execute("DELETE FROM gmail_inbox_simulation")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='gmail_inbox_simulation'")
    
    for ticket in tickets:
        query = """
            INSERT INTO tickets (
                company_name, employee_name, employee_email, ticket_subject, ticket_description, 
                ticket_text, received_channel, incident_type, ml_priority, keyword_priority, 
                final_priority, department, sentiment, root_cause, resolution_steps, 
                ai_recommended_resolution, status, assigned_engineer, engineer_remarks, 
                created_date, closed_date, resolution_time_mins, sla_mins, sla_status, 
                escalation_required, failure_case_flag
            ) VALUES (
                :company_name, :employee_name, :employee_email, :ticket_subject, :ticket_description, 
                :ticket_text, :received_channel, :incident_type, :ml_priority, :keyword_priority, 
                :final_priority, :department, :sentiment, :root_cause, :resolution_steps, 
                :ai_recommended_resolution, :status, :assigned_engineer, :engineer_remarks, 
                :created_date, :closed_date, :resolution_time_mins, :sla_mins, :sla_status, 
                :escalation_required, :failure_case_flag
            )
        """
        cursor.execute(query, ticket)
        ticket_id = cursor.lastrowid
        
        # Log initial history for all tickets
        cursor.execute("""
            INSERT INTO ticket_history (ticket_id, old_status, new_status, updated_by, updated_time, remarks)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, "None", ticket["status"], "System", ticket["created_date"], "Ticket created via CSV dataset generation"))
        
    # Seed mock emails
    print("Seeding SQLite database gmail_inbox_simulation table...")
    emails = generate_mock_emails()
    for email in emails:
        cursor.execute("""
            INSERT INTO gmail_inbox_simulation (sender_email, company_name, subject, email_body, received_time, converted_to_ticket)
            VALUES (:sender_email, :company_name, :subject, :email_body, :received_time, :converted_to_ticket)
        """, email)
        
    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    main()
