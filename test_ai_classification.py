"""
Test the Hybrid ML/LLM AI Classification Pipeline
This script tests tickets directly without the UI
"""

import os
from ticket_processor import TicketProcessor

# Ensure GROQ_API_KEY is set (optional but recommended)
groq_key = os.environ.get("GROQ_API_KEY")
if not groq_key:
    print("⚠️  Warning: GROQ_API_KEY not found in environment")
    print("   LLM fallback and action recommendations will use basic mode")
    print("   Add GROQ_API_KEY to .env file for full features\n")

print("=" * 80)
print("TESTING HYBRID ML/LLM CLASSIFICATION PIPELINE")
print("=" * 80)

# Initialize the ticket processor
processor = TicketProcessor(confidence_threshold=0.65)

# Get system info
info = processor.get_system_info()
print(f"\n✓ Ticket Processor Initialized")
print(f"  Approach: {info['approach']}")
print(f"  Confidence Threshold: {info['confidence_threshold']*100:.0f}%")
print(f"  LLM Available: {info['llm_available']}")
if info['llm_available']:
    print(f"  LLM Model: {info['llm_model']}")

# Test tickets
test_tickets = [
    {
        "title": "Critical Production Outage",
        "text": """
        URGENT! Our entire production environment is down. All customer-facing 
        services are unavailable. Database is not responding to queries. 
        Error logs show connection pool exhausted. Need immediate escalation!
        Revenue impact: $15,000/hour. Multiple customers calling support.
        """
    },
    {
        "title": "VPN Connection Issue",
        "text": """
        I can't connect to the company VPN this morning. Tried restarting 
        laptop and reinstalling VPN client. Still getting timeout errors.
        Need access for important client meeting in 1 hour.
        """
    },
    {
        "title": "New Employee Access Request",
        "text": """
        Hi, I'm a new hire who started this week. I need access to the 
        shared drives, email distribution lists, and project management 
        tools. My manager is John Smith in the Marketing department.
        """
    },
    {
        "title": "Printer Not Working",
        "text": """
        The printer on the 2nd floor is jammed. Showing paper jam error 
        but I can't find any stuck paper. Several people need to print 
        documents for a meeting this afternoon.
        """
    },
    {
        "title": "Slow Computer Performance",
        "text": """
        My laptop has been really slow lately. Takes forever to boot up 
        and applications keep freezing. Already tried restarting and 
        closing programs. Not blocking work but very annoying.
        """
    }
]

# Process each ticket
for idx, ticket in enumerate(test_tickets, 1):
    print(f"\n{'='*80}")
    print(f"TEST {idx}/{len(test_tickets)}: {ticket['title']}")
    print('='*80)
    
    print(f"\n📝 Ticket Text:")
    print(f"{ticket['text'].strip()}\n")
    
    # Process the ticket
    result = processor.process_ticket(ticket['text'])
    
    # Display results
    print("🤖 AI CLASSIFICATION RESULTS:")
    print("-" * 80)
    
    confidence_icon = lambda c: "✅" if c >= 0.65 else "⚠️ "
    
    print(f"\n1. Category:    {result['category']:20s} {confidence_icon(result['category_confidence'])} ({result['category_confidence']*100:.1f}% confidence)")
    print(f"2. Priority:    {result['priority']:20s} {confidence_icon(result['priority_confidence'])} ({result['priority_confidence']*100:.1f}% confidence)")
    print(f"3. Department:  {result['department']:20s} {confidence_icon(result['department_confidence'])} ({result['department_confidence']*100:.1f}% confidence)")
    print(f"4. Sentiment:   {result['sentiment']:20s} {confidence_icon(result['sentiment_confidence'])} ({result['sentiment_confidence']*100:.1f}% confidence)")
    
    # Classification source
    print(f"\n📊 Classification Source: {result['classification_source'].upper()}")
    if result['llm_fallback_used']:
        print(f"   ⚠️  LLM fallback activated for: {', '.join(result['low_confidence_fields'])}")
        print(f"   Reason: ML confidence below 65% threshold")
    else:
        print(f"   ✅ ML predictions were confident (no LLM fallback needed)")
    
    # Recommended action
    print(f"\n5. RECOMMENDED NEXT ACTION:")
    print("-" * 80)
    print(result['recommended_action'])
    
    if not result['llm_success']:
        print(f"\n⚠️  Note: Using fallback action (LLM error: {result['llm_error']})")

print("\n" + "=" * 80)
print("TESTING COMPLETE!")
print("=" * 80)

print("\n📊 SUMMARY:")
print(f"  Total tickets tested: {len(test_tickets)}")
print(f"  ML+LLM hybrid pipeline: {'✅ Active' if info['llm_available'] else '⚠️  Partial (No GROQ_API_KEY)'}")
print(f"  Confidence threshold: {info['confidence_threshold']*100:.0f}%")

print("\n💡 TO IMPROVE RESULTS:")
if not info['llm_available']:
    print("  1. Add GROQ_API_KEY to your .env file")
    print("     Get your key from: https://console.groq.com/")
print("  2. Run more training iterations: python train_xgboost_model.py")
print("  3. Add more training data to Data/ folder")

print("\n" + "=" * 80)
