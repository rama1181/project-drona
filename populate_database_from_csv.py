"""
Populate Database from CSV Dataset
Loads historical tickets from CSV files into the database to build the RAG knowledge base.
"""

import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import random
from pathlib import Path
from database import get_connection, init_db, seed_users

def safe_str(value, default=''):
    """Safely convert value to string, handling NaN and None"""
    if pd.isna(value) or value is None:
        return default
    return str(value)

def map_csv_to_database_fields(row):
    """Map CSV columns to database ticket fields"""
    
    # Skip rows with missing critical fields
    if pd.isna(row.get('subject')) or pd.isna(row.get('body')):
        return None
    
    # Map CSV priority to database priority format (3 levels)
    priority_map = {
        'low': 'Low',
        'medium': 'Medium',
        'high': 'High',
        'critical': 'High'  # Map critical to high
    }
    
    # Map CSV queue to department
    queue_map = {
        'Technical Support': 'Desktop Support',
        'Billing and Payments': 'Service Desk L1',
        'Returns and Exchanges': 'Service Desk L1',
        'Account Management': 'IT Access Team',
        'Product Information': 'Service Desk L1',
        'General Inquiries': 'Service Desk L1'
    }
    
    # Map CSV type to incident type
    type_map = {
        'Incident': 'Incident',
        'Request': 'Service Request',
        'Problem': 'Incident',
        'Change': 'Service Request'
    }
    
    # Safely get values
    subject = safe_str(row.get('subject', ''), 'No Subject')
    body = safe_str(row.get('body', ''), 'No description provided.')
    answer = safe_str(row.get('answer', ''), 'Resolution provided and ticket closed.')
    
    # Generate ticket text
    ticket_text = f"{subject}. {body}"
    
    # Random company names for diversity
    companies = [
        'TCS Global', 'TechCorp Services', 'InnoTech Ltd', 
        'FinBank Corp', 'MedSystems', 'CloudSphere', 
        'EduLearn Inc', 'Apex Retail'
    ]
    
    # Random employee names
    first_names = ['John', 'Sarah', 'Michael', 'Emma', 'David', 'Lisa', 'James', 'Maria']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']
    
    employee_name = f"{random.choice(first_names)} {random.choice(last_names)}"
    company_name = random.choice(companies)
    employee_email = f"{employee_name.replace(' ', '.').lower()}@{company_name.replace(' ', '').lower()}.com"
    
    # Calculate random resolution time
    priority_str = safe_str(row.get('priority', 'medium'), 'medium').lower()
    priority_val = priority_map.get(priority_str, 'Medium')
    base_resolution = {'High': 120, 'Medium': 480, 'Low': 1440}
    resolution_mins = random.randint(
        int(base_resolution[priority_val] * 0.5),
        int(base_resolution[priority_val] * 1.5)
    )
    
    # Random creation date (last 90 days)
    days_ago = random.randint(1, 90)
    created_date = datetime.now() - timedelta(days=days_ago)
    closed_date = created_date + timedelta(minutes=resolution_mins)
    
    # Determine SLA
    sla_map = {'High': 180, 'Medium': 480, 'Low': 960}
    sla_mins = sla_map[priority_val]
    sla_status = 'Met' if resolution_mins <= sla_mins else 'Breached'
    
    # Sentiment analysis
    sentiment_keywords = {
        'Positive': ['thank', 'appreciate', 'excellent', 'great', 'satisfied'],
        'Negative': ['urgent', 'critical', 'frustrated', 'disappointed', 'problem', 'issue'],
        'Neutral': []
    }
    
    text_lower = ticket_text.lower()
    if any(word in text_lower for word in sentiment_keywords['Negative']):
        sentiment = 'Negative'
    elif any(word in text_lower for word in sentiment_keywords['Positive']):
        sentiment = 'Positive'
    else:
        sentiment = 'Neutral'
    
    # Get ticket type and queue safely
    ticket_type = safe_str(row.get('type', 'Incident'), 'Incident')
    queue = safe_str(row.get('queue', 'General Inquiries'), 'General Inquiries')
    
    ticket = {
        'company_name': company_name,
        'employee_name': employee_name,
        'employee_email': employee_email,
        'ticket_subject': subject,
        'ticket_description': body,
        'ticket_text': ticket_text,
        'received_channel': random.choice(['Email', 'Portal', 'Phone']),
        'incident_type': type_map.get(ticket_type, 'Incident'),
        'ml_priority': priority_val,
        'keyword_priority': priority_val,
        'final_priority': priority_val,
        'department': queue_map.get(queue, 'Service Desk L1'),
        'sentiment': sentiment,
        'root_cause': generate_root_cause(subject, body),
        'resolution_steps': answer,
        'ai_recommended_resolution': answer,
        'status': 'Done',
        'assigned_engineer': f"{random.choice(['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'])} {random.choice(['Kumar', 'Patel', 'Singh', 'Shah'])}",
        'engineer_remarks': 'Ticket resolved successfully',
        'created_date': created_date.strftime("%Y-%m-%d %H:%M:%S"),
        'closed_date': closed_date.strftime("%Y-%m-%d %H:%M:%S"),
        'resolution_time_mins': resolution_mins,
        'sla_mins': sla_mins,
        'sla_status': sla_status,
        'escalation_required': 1 if sla_status == 'Breached' else 0,
        'failure_case_flag': 0
    }
    
    return ticket

def generate_root_cause(subject, body):
    """Generate a plausible root cause based on the ticket content"""
    subject_lower = subject.lower()
    body_lower = body.lower()
    
    # Security related
    if any(word in subject_lower + body_lower for word in ['security', 'breach', 'attack', 'malware', 'virus']):
        return 'Security vulnerability detected in system components'
    
    # Account related
    elif any(word in subject_lower + body_lower for word in ['account', 'login', 'password', 'access']):
        return 'User authentication or authorization configuration issue'
    
    # Network/Connectivity
    elif any(word in subject_lower + body_lower for word in ['network', 'connection', 'offline', 'vpn', 'connectivity']):
        return 'Network connectivity or configuration issue'
    
    # Billing
    elif any(word in subject_lower + body_lower for word in ['billing', 'invoice', 'payment', 'charge']):
        return 'Billing system configuration or data synchronization issue'
    
    # Hardware
    elif any(word in subject_lower + body_lower for word in ['printer', 'device', 'hardware', 'projector', 'monitor']):
        return 'Hardware malfunction or driver compatibility issue'
    
    # Software
    elif any(word in subject_lower + body_lower for word in ['software', 'application', 'app', 'program']):
        return 'Software bug or configuration mismatch'
    
    # Default
    else:
        return 'Configuration issue requiring standard troubleshooting steps'

def populate_database(csv_file, limit=None):
    """Populate database with tickets from CSV file"""
    
    print(f"\n{'='*80}")
    print(f"POPULATING DATABASE FROM CSV")
    print(f"{'='*80}")
    
    # Read CSV
    print(f"\nReading CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    
    if limit:
        df = df.head(limit)
    
    print(f"Found {len(df)} tickets to process")
    
    # Initialize database
    print("\nInitializing database...")
    init_db()
    seed_users()
    print("[OK] Database initialized")
    
    # Connect to database
    conn = get_connection()
    cursor = conn.cursor()
    
    # Insert tickets
    success_count = 0
    error_count = 0
    
    print(f"\nInserting tickets into database...")
    
    for idx, row in df.iterrows():
        try:
            ticket = map_csv_to_database_fields(row)
            
            # Skip if ticket is None (missing critical fields)
            if ticket is None:
                error_count += 1
                continue
            
            cursor.execute("""
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
            """, ticket)
            
            success_count += 1
            
            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{len(df)} tickets...")
                conn.commit()
                
        except Exception as e:
            error_count += 1
            print(f"  Error processing ticket {idx + 1}: {str(e)}")
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*80}")
    print(f"IMPORT COMPLETE")
    print(f"{'='*80}")
    print(f"Successfully imported: {success_count} tickets")
    print(f"Errors: {error_count}")
    print(f"\nThe RAG engine can now use these {success_count} historical tickets as knowledge base.")
    
    return success_count, error_count

if __name__ == "__main__":
    # Get the CSV file path
    data_dir = Path(__file__).parent / "Data"
    csv_file = data_dir / "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
    
    if not csv_file.exists():
        print(f"ERROR: CSV file not found at {csv_file}")
        print("Available CSV files:")
        for f in data_dir.glob("*.csv"):
            print(f"  - {f.name}")
    else:
        # Populate database (use limit=100 for testing, None for all)
        populate_database(csv_file, limit=None)
