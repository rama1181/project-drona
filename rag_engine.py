import os
import joblib
import sqlite3
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from database import get_connection

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

def get_rag_vectorizer():
    """Loads the pre-trained TF-IDF vectorizer."""
    vectorizer_path = os.path.join(MODELS_DIR, "rag_vectorizer.pkl")
    if os.path.exists(vectorizer_path):
        return joblib.load(vectorizer_path)
    return None

def find_similar_tickets(new_ticket_text, top_n=3):
    """
    Vectorizes the new ticket text and computes cosine similarity against
    historical closed/resolved tickets in the SQLite database.
    """
    vectorizer = get_rag_vectorizer()
    if not vectorizer:
        return []
        
    conn = get_connection()
    cursor = conn.cursor()
    # Query resolved tickets to serve as the Knowledge Base
    cursor.execute("""
        SELECT ticket_id, ticket_subject, ticket_description, ticket_text, 
               root_cause, resolution_steps, department, incident_type, status
        FROM tickets 
        WHERE status = 'Done' OR root_cause IS NOT NULL
    """)
    historical_tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not historical_tickets:
        return []
        
    # Extract historical ticket text
    hist_texts = [t["ticket_text"] for t in historical_tickets]
    
    # Vectorize
    try:
        new_vec = vectorizer.transform([new_ticket_text])
        hist_vecs = vectorizer.transform(hist_texts)
    except Exception as e:
        print(f"Error during vectorization: {e}")
        return []
        
    # Calculate cosine similarity
    similarities = cosine_similarity(new_vec, hist_vecs).flatten()
    
    # Pair tickets with scores and sort
    scored_tickets = []
    for idx, score in enumerate(similarities):
        scored_tickets.append({
            "ticket": historical_tickets[idx],
            "score": float(score)
        })
        
    # Sort in descending order of similarity
    scored_tickets = sorted(scored_tickets, key=lambda x: x["score"], reverse=True)
    
    return scored_tickets[:top_n]

def get_rag_recommendations(new_ticket_text):
    """
    Retrieves RAG recommendations including:
    - Similar tickets
    - Recommended root cause
    - Recommended resolution steps
    - Outlier flag (if similarity score of top ticket is < 0.15)
    """
    similar_matches = find_similar_tickets(new_ticket_text)
    
    if not similar_matches:
        # Default fallback recommendations if knowledge base is empty
        return {
            "similar_tickets": [],
            "predicted_root_cause": "Unknown - Insufficient knowledge base.",
            "recommended_resolution": "1. Escalate to L1 Service Desk.\n2. Review system configurations manual.\n3. Search external support documents.",
            "is_outlier": True,
            "max_similarity": 0.0
        }
        
    top_match = similar_matches[0]
    top_score = top_match["score"]
    
    is_outlier = top_score < 0.15
    
    # Extract root cause and resolution steps from top matches
    predicted_root_cause = top_match["ticket"]["root_cause"] if top_match["ticket"]["root_cause"] else "Undetermined"
    
    # Construct structured recommendation steps
    rec_res_steps = []
    rec_res_steps.append(f"### [Recommended Resolution (Based on Similar Ticket ID {top_match['ticket']['ticket_id']} - Match: {top_score:.1%})]")
    rec_res_steps.append(top_match["ticket"]["resolution_steps"])
    
    # Add alternative references if available
    if len(similar_matches) > 1:
        alt_match = similar_matches[1]
        if alt_match["score"] >= 0.10:
            rec_res_steps.append(f"\n### [Alternative Action (Based on Similar Ticket ID {alt_match['ticket']['ticket_id']} - Match: {alt_match['score']:.1%})]")
            rec_res_steps.append(alt_match["ticket"]["resolution_steps"])
            
    recommended_resolution = "\n".join(rec_res_steps)
    
    return {
        "similar_tickets": similar_matches,
        "predicted_root_cause": predicted_root_cause,
        "recommended_resolution": recommended_resolution,
        "is_outlier": is_outlier,
        "max_similarity": top_score
    }
