import os
import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from database import get_connection

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

_embedding_model = None
_cached_embeddings = None
_cached_tickets = None
_cache_timestamp = None

def get_rag_embedding_model():
    """Loads the pre-trained Sentence Transformer model for RAG."""
    global _embedding_model
    
    if _embedding_model is not None:
        return _embedding_model
    
    embedding_model_path = Path(MODELS_DIR) / "sentence_transformer_model"
    
    if embedding_model_path.exists():
        print("Loading Sentence Transformer for RAG...")
        _embedding_model = SentenceTransformer(str(embedding_model_path))
        print("[OK] RAG Sentence Transformer loaded")
        return _embedding_model
    else:
        print(f"WARNING: Sentence Transformer model not found at {embedding_model_path}")
        print("Please run train_xgboost_model.py first to train the model.")
        return None

def find_similar_tickets(new_ticket_text, top_n=3, use_cache=True, department=None, incident_type=None, priority=None):
    """
    Uses Sentence Transformer embeddings to compute semantic similarity against
    historical closed/resolved tickets in the SQLite database.
    
    PERFORMANCE OPTIMIZATION: Filters by ML predictions (department, incident_type, priority)
    before computing embeddings, reducing search space dramatically.
    
    This method uses semantic embeddings which understand meaning, not just keywords.
    For example: "printer not working" will match "printing device malfunction"
    
    Args:
        new_ticket_text: Text of the new ticket
        top_n: Number of similar tickets to return
        use_cache: Whether to use cached embeddings (default: True)
        department: Filter by department (from ML prediction)
        incident_type: Filter by incident type (from ML prediction)
        priority: Filter by priority (from ML prediction)
    """
    global _cached_embeddings, _cached_tickets, _cache_timestamp
    
    embedding_model = get_rag_embedding_model()
    if not embedding_model:
        print("WARNING: RAG embedding model not available. Cannot find similar tickets.")
        return []
        
    conn = get_connection()
    cursor = conn.cursor()
    
    # Build dynamic query with ML-based filters
    query = """
        SELECT ticket_id, ticket_subject, ticket_description, ticket_text, 
               root_cause, resolution_steps, department, incident_type, status, final_priority
        FROM tickets 
        WHERE (status = 'Done' OR root_cause IS NOT NULL)
    """
    params = []
    
    # Apply ML prediction filters for faster, more accurate search
    if department:
        query += " AND department = ?"
        params.append(department)
    
    if incident_type:
        query += " AND incident_type = ?"
        params.append(incident_type)
    
    # Optional: Prioritize same or higher priority tickets
    if priority:
        priority_order = {'Low': 1, 'Medium': 2, 'High': 3}
        current_level = priority_order.get(priority, 2)
        # Include tickets of similar or higher priority
        query += " AND CASE final_priority WHEN 'High' THEN 3 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 1 ELSE 1 END >= ?"
        params.append(max(1, current_level - 1))  # Include one level below
    
    query += " ORDER BY created_date DESC LIMIT 1000"
    
    cursor.execute(query, params)
    historical_tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not historical_tickets:
        print(f"INFO: No historical tickets found matching filters (dept={department}, type={incident_type}).")
        # Fallback: Try without filters
        if department or incident_type:
            print("      Retrying without filters...")
            return find_similar_tickets(new_ticket_text, top_n, use_cache=False, 
                                       department=None, incident_type=None, priority=None)
        return []
    
    # Extract historical ticket text
    hist_texts = [t["ticket_text"] for t in historical_tickets]
    
    # Check if we can use cached embeddings
    # Cache key based on filters
    cache_key = f"{department}_{incident_type}_{priority}"
    use_cached = False
    if use_cache and _cached_embeddings is not None and _cached_tickets is not None:
        # For now, simple cache - can be enhanced with per-filter caching
        if len(_cached_tickets) == len(historical_tickets):
            use_cached = True
            hist_vecs = _cached_embeddings
            print(f"RAG: Using cached embeddings for {len(historical_tickets)} tickets (dept={department}, type={incident_type})...")
    
    # Create semantic embeddings if not cached
    if not use_cached:
        try:
            filter_info = []
            if department: filter_info.append(f"dept={department}")
            if incident_type: filter_info.append(f"type={incident_type}")
            filter_str = ", ".join(filter_info) if filter_info else "no filters"
            
            print(f"RAG: Computing similarity against {len(historical_tickets)} tickets ({filter_str})...")
            print("     (This may take 10-30 seconds on first run, then cached)")
            
            hist_vecs = embedding_model.encode(
                hist_texts, 
                convert_to_numpy=True, 
                show_progress_bar=True,  # Show progress for long operations
                batch_size=32  # Process in batches
            )
            
            # Cache the embeddings for next time
            _cached_embeddings = hist_vecs
            _cached_tickets = historical_tickets
            _cache_timestamp = datetime.now()
            
            print(f"RAG: Embeddings cached for future searches")
            
        except Exception as e:
            print(f"Error during embedding creation: {e}")
            return []
    
    # Encode new ticket
    try:
        new_vec = embedding_model.encode([new_ticket_text], convert_to_numpy=True)
    except Exception as e:
        print(f"Error encoding new ticket: {e}")
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
    
    if scored_tickets:
        print(f"RAG: Top match has {scored_tickets[0]['score']*100:.1f}% similarity")
    
    return scored_tickets[:top_n]

def get_rag_recommendations(new_ticket_text, department=None, incident_type=None, priority=None):
    """
    Retrieves RAG recommendations including:
    - Similar tickets
    - Recommended root cause
    - Recommended resolution steps
    - Outlier flag (if similarity score of top ticket is < 0.15)
    
    Args:
        new_ticket_text: Text of the new ticket
        department: Department filter (from ML prediction)
        incident_type: Incident type filter (from ML prediction)
        priority: Priority filter (from ML prediction)
    """
    similar_matches = find_similar_tickets(
        new_ticket_text, 
        department=department, 
        incident_type=incident_type, 
        priority=priority
    )
    
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
