"""
Test RAG Engine with Sentence Transformers
Verifies that the RAG engine can find similar tickets using semantic embeddings.
"""

from rag_engine import find_similar_tickets, get_rag_recommendations

def test_rag():
    """Test RAG engine with sample queries"""
    
    print("\n" + "="*80)
    print("RAG ENGINE TEST - SENTENCE TRANSFORMERS")
    print("="*80)
    
    # Test queries
    test_tickets = [
        "Printer is not working in my office. I need urgent help with printing documents.",
        "Cannot connect to VPN from home. Getting timeout errors.",
        "Need to reset my password. Forgot my login credentials.",
        "Laptop is running very slow and keeps freezing.",
        "Email server is down. Cannot send or receive emails."
    ]
    
    for idx, test_ticket in enumerate(test_tickets, 1):
        print(f"\n{'='*80}")
        print(f"TEST {idx}: {test_ticket}")
        print('='*80)
        
        # Get RAG recommendations
        rag_rec = get_rag_recommendations(test_ticket)
        
        print(f"\nRAG Analysis:")
        print(f"  - Is Outlier: {rag_rec['is_outlier']}")
        print(f"  - Max Similarity: {rag_rec['max_similarity']*100:.1f}%")
        print(f"  - Predicted Root Cause: {rag_rec['predicted_root_cause']}")
        
        print(f"\n  Similar Tickets Found: {len(rag_rec['similar_tickets'])}")
        for i, match in enumerate(rag_rec['similar_tickets'][:3], 1):
            ticket = match['ticket']
            score = match['score']
            print(f"\n    [{i}] Ticket #{ticket['ticket_id']} - Similarity: {score*100:.1f}%")
            print(f"        Subject: {ticket['ticket_subject'][:80]}...")
            print(f"        Department: {ticket['department']}")
            print(f"        Status: {ticket['status']}")
        
        print(f"\n  Recommended Resolution:")
        print(f"    {rag_rec['recommended_resolution'][:200]}...")
    
    print(f"\n{'='*80}")
    print("RAG ENGINE TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    test_rag()
