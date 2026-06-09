"""
Populate RAG memory table with resolved tickets from the tickets table.
This creates the knowledge base for RAG recommendations.
"""
import sqlite3
import os
from datetime import datetime

DB_NAME = os.path.join(os.path.dirname(__file__), "smart_ticket_engine.db")

def populate_rag_memory():
    """Sync resolved tickets to rag_memory table for RAG knowledge base"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("=" * 70)
    print("RAG MEMORY POPULATION UTILITY")
    print("=" * 70)
    
    # Get count of resolved tickets
    cursor.execute("""
        SELECT COUNT(*) 
        FROM tickets 
        WHERE status = 'Done' AND resolution_steps IS NOT NULL
    """)
    total_resolved = cursor.fetchone()[0]
    print(f"\n📊 Found {total_resolved:,} resolved tickets")
    
    # Check how many are already in rag_memory
    cursor.execute("SELECT COUNT(*) FROM rag_memory")
    existing_count = cursor.fetchone()[0]
    print(f"📊 Existing RAG memory entries: {existing_count:,}")
    
    # Get ticket IDs already in rag_memory
    cursor.execute("SELECT ticket_id FROM rag_memory")
    existing_ids = set(row[0] for row in cursor.fetchall())
    
    # Insert resolved tickets that aren't in rag_memory yet
    cursor.execute("""
        SELECT 
            ticket_id, ticket_subject, ticket_description,
            incident_type, department, final_priority,
            root_cause, resolution_steps, resolution_time_mins,
            sentiment, created_date
        FROM tickets
        WHERE status = 'Done' AND resolution_steps IS NOT NULL
    """)
    
    tickets_to_add = []
    for row in cursor.fetchall():
        ticket_id = row[0]
        if ticket_id not in existing_ids:
            tickets_to_add.append(row)
    
    print(f"\n🔄 Inserting {len(tickets_to_add):,} new tickets into RAG memory...")
    
    if tickets_to_add:
        cursor.executemany("""
            INSERT INTO rag_memory (
                ticket_id, ticket_subject, ticket_description,
                incident_type, department, priority,
                root_cause, resolution_steps, resolution_time_mins,
                sentiment, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tickets_to_add)
        
        conn.commit()
        print(f"✅ Successfully added {len(tickets_to_add):,} tickets to RAG memory!")
    else:
        print("✅ RAG memory is already up to date!")
    
    # Final statistics
    cursor.execute("SELECT COUNT(*) FROM rag_memory")
    final_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT department, COUNT(*) 
        FROM rag_memory 
        GROUP BY department 
        ORDER BY COUNT(*) DESC
    """)
    dept_stats = cursor.fetchall()
    
    print(f"\n📊 RAG Memory Statistics:")
    print(f"   Total entries: {final_count:,}")
    print(f"\n   By Department:")
    for dept, count in dept_stats:
        print(f"      {dept}: {count:,}")
    
    conn.close()
    print("\n" + "=" * 70)
    print("✅ RAG memory population complete!")
    print("=" * 70)

if __name__ == "__main__":
    populate_rag_memory()
