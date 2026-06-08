import os
import sqlite3
from datetime import datetime
from database import get_connection, mark_email_converted

# =====================================================================
# GMAIL API INTEGRATION INSTRUCTIONS (For production use)
# =====================================================================
# To connect this to a real Gmail account instead of the simulation:
#
# 1. Install dependencies:
#    pip install google-auth-oauthlib google-api-python-client
#
# 2. Go to Google Cloud Console, create a project, and enable the Gmail API.
# 3. Create OAuth 2.0 Client credentials and download the credentials.json.
# 4. Use the following snippet to authenticate and retrieve real emails:
#
#    from google.oauth2.credentials import Credentials
#    from google_auth_oauthlib.flow import InstalledAppFlow
#    from googleapiclient.discovery import build
#
#    # Scopes required for reading emails
#    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
#
#    def get_gmail_service():
#        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
#        creds = flow.run_local_server(port=0)
#        return build('gmail', 'v1', credentials=creds)
#
#    def fetch_real_emails():
#        service = get_gmail_service()
#        results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=10).execute()
#        messages = results.get('messages', [])
#        email_data = []
#        for msg in messages:
#            m = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
#            headers = m['payload']['headers']
#            subject = [h['value'] for h in headers if h['name'] == 'Subject'][0]
#            sender = [h['value'] for h in headers if h['name'] == 'From'][0]
#            body = m['snippet'] # Simplified body extraction
#            email_data.append({"sender": sender, "subject": subject, "body": body})
#        return email_data
# =====================================================================

def get_simulated_emails():
    """Retrieves all unconverted simulated emails from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email_id, sender_email, company_name, subject, email_body, received_time 
        FROM gmail_inbox_simulation 
        WHERE converted_to_ticket = 0
        ORDER BY email_id DESC
    """)
    emails = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return emails

def get_all_simulated_emails():
    """Retrieves all simulated emails including converted ones."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email_id, sender_email, company_name, subject, email_body, received_time, converted_to_ticket 
        FROM gmail_inbox_simulation 
        ORDER BY email_id DESC
    """)
    emails = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return emails
