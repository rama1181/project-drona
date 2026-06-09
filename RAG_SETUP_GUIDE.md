# RAG Engine Setup Guide

## Overview

The RAG (Retrieval-Augmented Generation) engine in this project uses **Sentence Transformers** to find similar historical tickets and provide intelligent recommendations based on semantic similarity.

## How RAG Works

### Architecture

```
New Ticket
    ↓
Sentence Transformer Embedding (all-MiniLM-L6-v2)
    ↓
Semantic Similarity Search (Cosine Similarity)
    ↓
Query Historical "Done" Tickets from Database
    ↓
Rank by Similarity Score
    ↓
Extract Root Cause + Resolution Steps
    ↓
Pass Context to LLM (Groq)
    ↓
Generate Enhanced Resolution
```

### Key Components

1. **Sentence Transformers**: Uses `all-MiniLM-L6-v2` model for semantic embeddings
   - Understands **meaning**, not just keywords
   - "printer broken" matches "printing device malfunction"
   - 384-dimensional embeddings

2. **Knowledge Base**: Historical resolved tickets from SQLite database
   - Query: `WHERE status = 'Done' OR root_cause IS NOT NULL`
   - Stores: ticket_text, root_cause, resolution_steps, department, etc.

3. **Similarity Scoring**: Cosine similarity between embeddings
   - Scores range from 0.0 (no match) to 1.0 (perfect match)
   - Top 3 similar tickets are retrieved

4. **Outlier Detection**: Flags unusual tickets
   - Threshold: < 0.15 (15% similarity)
   - Indicates new problem types

5. **LLM Enhancement**: Similar tickets passed to Groq LLM
   - LLM uses RAG context to generate informed resolutions
   - Fallback to RAG if LLM fails

## Setup Instructions

### Step 1: Train the Sentence Transformer Model

The sentence transformer model is trained as part of the ML pipeline:

```bash
python train_xgboost_model.py
```

This will:
- Download `all-MiniLM-L6-v2` from Hugging Face
- Train XGBoost classifiers on your data
- Save the sentence transformer to `models/sentence_transformer_model/`

**Expected output:**
```
Loading Sentence Transformer model: all-MiniLM-L6-v2
Creating semantic embeddings...
[OK] Sentence Transformer saved to: models/sentence_transformer_model
```

### Step 2: Populate Database with Historical Tickets

Since you're starting fresh, you need to load the CSV data into the database:

```bash
python populate_database_from_csv.py
```

This will:
- Read tickets from `Data/aa_dataset-tickets-multi-lang-5-2-50-version.csv`
- Map CSV fields to database schema
- Insert tickets as "Done" status with resolutions
- Create root causes based on ticket content

**Expected output:**
```
POPULATING DATABASE FROM CSV
Found 200 tickets to process
Inserting tickets into database...
Successfully imported: 200 tickets
The RAG engine can now use these 200 historical tickets as knowledge base.
```

### Step 3: Test RAG Engine

Verify the RAG engine is working:

```bash
python test_rag_engine.py
```

This will:
- Test 5 different ticket scenarios
- Show similarity scores for each match
- Display recommended resolutions
- Verify semantic search is working

**Expected output:**
```
TEST 1: Printer is not working in my office...
RAG Analysis:
  - Is Outlier: False
  - Max Similarity: 78.3%
  - Similar Tickets Found: 3
    [1] Ticket #42 - Similarity: 78.3%
        Subject: Printer offline in Building A
```

## Using RAG in the Application

### In `app.py` Workflow

The RAG engine is automatically integrated:

```python
# 1. Process ticket
rag_rec = get_rag_recommendations(ticket_text)

# 2. Pass to LLM
llm_resolution = llm_client.generate_resolution(
    subject, description,
    incident_type, priority, department, sentiment,
    rag_similar_tickets=rag_rec.get("similar_tickets", [])  # RAG context
)

# 3. Use LLM-enhanced resolution
if llm_resolution['success']:
    root_cause = llm_resolution["root_cause"]
    resolution = llm_resolution["full_response"]
else:
    # Fallback to RAG
    root_cause = rag_rec["predicted_root_cause"]
    resolution = rag_rec["recommended_resolution"]
```

### RAG Return Structure

```python
{
    "similar_tickets": [
        {
            "ticket": {
                "ticket_id": 123,
                "ticket_subject": "...",
                "ticket_description": "...",
                "root_cause": "...",
                "resolution_steps": "...",
                "department": "...",
                "incident_type": "..."
            },
            "score": 0.85  # 85% similarity
        },
        # ... more tickets
    ],
    "predicted_root_cause": "Root cause from top match",
    "recommended_resolution": "Structured resolution steps",
    "is_outlier": False,
    "max_similarity": 0.85
}
```

## Configuration

### Similarity Threshold (Outlier Detection)

Edit `rag_engine.py`:

```python
# Line ~89
is_outlier = top_score < 0.15  # Change threshold (0.0 to 1.0)
```

**Recommendations:**
- `0.10`: Very strict - few outliers
- `0.15`: Balanced (default)
- `0.20`: More outliers flagged

### Number of Similar Tickets

Edit function calls:

```python
# Default: top 3
similar_tickets = find_similar_tickets(ticket_text, top_n=5)  # Change to 5
```

### Alternative Ticket Threshold

Edit `rag_engine.py`:

```python
# Line ~107
if alt_match["score"] >= 0.10:  # Change threshold for alternative suggestions
```

## Troubleshooting

### Error: "Sentence Transformer model not found"

**Solution:**
```bash
python train_xgboost_model.py
```

### Error: "No historical tickets found in database"

**Solution:**
```bash
python populate_database_from_csv.py
```

### Low Similarity Scores (all < 20%)

**Possible causes:**
1. Knowledge base too small - add more tickets
2. Ticket language mismatch - ensure consistent language
3. Very unique problem - this is expected for outliers

**Solution:** Populate more diverse historical tickets

### RAG is Slow

**Causes:**
- Large knowledge base (> 10,000 tickets)
- Computing embeddings on CPU

**Solutions:**
1. Use GPU if available (automatic in sentence-transformers)
2. Cache historical embeddings (advanced optimization)
3. Filter knowledge base by department/category

## Advanced: Caching Historical Embeddings

For better performance with large databases, pre-compute embeddings:

```python
# Future optimization
# Store embeddings in database as BLOB column
# Only compute embedding for new ticket
# Compare against pre-computed historical embeddings
```

## Files Involved

- `rag_engine.py` - Main RAG implementation
- `populate_database_from_csv.py` - Database population script
- `test_rag_engine.py` - RAG testing script
- `models/sentence_transformer_model/` - Trained sentence transformer
- `smart_ticket_engine.db` - SQLite database with tickets

## Key Differences from TF-IDF

| Feature | TF-IDF (Old) | Sentence Transformers (New) |
|---------|--------------|----------------------------|
| Understanding | Keywords only | Semantic meaning |
| "printer broken" vs "printing device malfunction" | Low similarity | High similarity |
| Multilingual | No | Yes (if using multilingual model) |
| Embeddings | Sparse vectors | Dense 384-dim vectors |
| Model size | ~1 MB | ~90 MB |
| Performance | Fast | Slower but more accurate |

## Next Steps

1. ✅ Train sentence transformer: `python train_xgboost_model.py`
2. ✅ Populate database: `python populate_database_from_csv.py`
3. ✅ Test RAG: `python test_rag_engine.py`
4. ✅ Run application: `streamlit run app.py`
5. ✅ Create new tickets and see RAG recommendations

## Summary

The RAG engine provides **intelligent, context-aware recommendations** by:
- Using semantic similarity (not just keywords)
- Learning from historical resolutions
- Detecting outlier/new problems
- Enhancing LLM responses with real historical data

When you start the app fresh, the knowledge base is empty. Use the population script to load historical tickets from CSV, then RAG will provide accurate recommendations based on past resolutions.
