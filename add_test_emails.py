"""
Quick script to add test emails to the Gmail Inbox Simulation
Run this, then view them in the Streamlit app!
"""

from database import add_gmail_email
from datetime import datetime

# Test emails covering different scenarios
test_emails = [
    {
        "sender": "john.urgent@techcorp.com",
        "company": "TechCorp Services",
        "subject": "🚨 URGENT: Production Database Down!",
        "body": """
        CRITICAL INCIDENT - ALL HANDS ON DECK
        
        Our production database server crashed at 2:00 PM and is completely unresponsive.
        All customer-facing services are down. This is affecting approximately 50,000 users.
        
        Error in logs: "Fatal: Database connection pool exhausted"
        
        We need immediate assistance to restore services. Revenue loss is $10,000 per hour.
        
        Please escalate to senior database team immediately!
        
        John Peterson
        DevOps Lead
        TechCorp Services
        """
    },
    {
        "sender": "sarah.smith@finbank.com",
        "company": "FinBank Corp",
        "subject": "VPN Connection Problems",
        "body": """
        Hi Support,
        
        I've been unable to connect to the company VPN since this morning.
        I've tried:
        - Restarting my laptop
        - Reinstalling the VPN client
        - Using different WiFi networks
        
        Still getting "Authentication failed" error. I need to access internal 
        systems for client meetings today.
        
        Can someone help me troubleshoot this?
        
        Thanks,
        Sarah Smith
        Financial Analyst
        """
    },
    {
        "sender": "mike.jones@cloudspan.com",
        "company": "CloudSphere",
        "subject": "Laptop running extremely slow",
        "body": """
        Hello,
        
        My laptop has been running very slowly for the past week. 
        It takes 10 minutes just to boot up, and applications freeze constantly.
        
        I've tried:
        - Closing unnecessary programs
        - Restarting multiple times
        - Running Windows Update
        
        Nothing seems to help. Could someone take a look?
        
        Not super urgent, but it's affecting my productivity.
        
        Best regards,
        Mike Jones
        Marketing Team
        """
    },
    {
        "sender": "lisa.chen@medsystems.com",
        "company": "MedSystems",
        "subject": "Need access to shared drive",
        "body": """
        Hi IT Team,
        
        I'm a new employee who started last Monday. I need access to the 
        "Medical Records - Q2" shared drive to complete my onboarding tasks.
        
        My manager is Dr. Williams in the Clinical Operations department.
        
        Could you please grant me read/write access?
        
        Thank you!
        Lisa Chen
        Clinical Data Analyst
        """
    },
    {
        "sender": "robert.davis@apexretail.com",
        "company": "Apex Retail",
        "subject": "Password reset needed",
        "body": """
        Support Team,
        
        I forgot my password and need it reset. I've tried the self-service 
        portal but it says my account is locked.
        
        My employee ID is: APX-2847
        
        Can you help unlock and reset my password?
        
        Thanks,
        Robert Davis
        Store Manager
        """
    },
    {
        "sender": "emma.wilson@edulearn.com",
        "company": "EduLearn Inc",
        "subject": "Question about Office 365 features",
        "body": """
        Hello,
        
        I have a few questions about our Office 365 subscription:
        
        1. Can I use Teams for external meetings with clients?
        2. What's the storage limit for OneDrive?
        3. Is there a way to schedule emails in Outlook?
        
        Not urgent - just curious about these features.
        
        Thanks for your help!
        Emma Wilson
        Content Developer
        """
    },
    {
        "sender": "david.park@innotech.com",
        "company": "InnoTech Ltd",
        "subject": "Printer not working - 3rd floor",
        "body": """
        Hi,
        
        The printer on the 3rd floor (HP LaserJet in the east wing) is jammed 
        and showing a "Paper Jam" error. I've tried opening all the trays but 
        can't find any stuck paper.
        
        Several people are waiting to print important documents for a client 
        presentation this afternoon.
        
        Could someone come take a look?
        
        David Park
        Sales Team
        """
    },
    {
        "sender": "jennifer.lee@tcs.com",
        "company": "TCS Global",
        "subject": "Email not receiving attachments",
        "body": """
        Dear Support,
        
        For the past 2 days, I'm not receiving any email attachments. 
        The emails arrive but they show "Attachment removed for security reasons."
        
        This is blocking important work as clients are sending contracts and 
        documents that I need to review urgently.
        
        Please investigate and fix this issue ASAP.
        
        Jennifer Lee
        Legal Department
        TCS Global
        """
    }
]

print("=" * 80)
print("ADDING TEST EMAILS TO GMAIL INBOX SIMULATION")
print("=" * 80)

for idx, email in enumerate(test_emails, 1):
    print(f"\n📧 Adding email {idx}/{len(test_emails)}...")
    print(f"   From: {email['sender']}")
    print(f"   Subject: {email['subject']}")
    
    add_gmail_email(
        sender=email['sender'],
        company=email['company'],
        subject=email['subject'],
        body=email['body']
    )
    
    print(f"   ✅ Added successfully!")

print("\n" + "=" * 80)
print(f"🎉 SUCCESS! Added {len(test_emails)} test emails to the inbox simulation!")
print("=" * 80)

print("\n📋 NEXT STEPS:")
print("1. Start the Streamlit app:")
print("   streamlit run app.py")
print("\n2. Login with:")
print("   Username: admin")
print("   Password: admin123")
print("\n3. Navigate to 'Gmail Simulation Gateway' tab")
print("\n4. Click 'Convert Email to Ticket' on any email")
print("\n5. Watch the AI classify it automatically! 🚀")
print("\n" + "=" * 80)
