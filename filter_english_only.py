"""
Filter database to keep only English tickets and remove other languages
This will significantly improve performance by reducing dataset size
"""
import sqlite3
import os
import re

DB_NAME = os.path.join(os.path.dirname(__file__), "smart_ticket_engine.db")

def is_english(text):
    """
    Simple heuristic to detect if text is primarily English.
    Checks for:
    - High ratio of ASCII characters
    - Common English words
    - Low presence of non-Latin scripts
    """
    if not text:
        return False
    
    # Count ASCII vs non-ASCII characters
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    total_chars = len(text)
    ascii_ratio = ascii_chars / total_chars if total_chars > 0 else 0
    
    # If more than 85% ASCII, likely English
    if ascii_ratio > 0.85:
        return True
    
    # Check for non-Latin scripts (Cyrillic, Arabic, Chinese, etc.)
    non_latin_pattern = re.compile(r'[\u0400-\u04FF\u0600-\u06FF\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF]')
    if non_latin_pattern.search(text):
        return False
    
    return ascii_ratio > 0.7


def filter_english_tickets():
    """Remove non-English tickets from database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("=" * 70)
    print("ENGLISH-ONLY TICKET FILTER")
    print("=" * 70)
    
    # Get current counts
    cursor.execute("SELECT COUNT(*) FROM tickets")
    total_before = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM rag_memory")
    rag_before = cursor.fetchone()[0]
    
    print(f"\n📊 Current Database State:")
    print(f"   Tickets: {total_before:,}")
    print(f"   RAG Memory: {rag_before:,}")
    
    # Get all tickets and check language
    print(f"\n🔍 Analyzing ticket languages...")
    cursor.execute("""
        SELECT ticket_id, ticket_subject, ticket_description 
        FROM tickets
    """)
    
    english_ids = []
    non_english_ids = []
    
    for ticket_id, subject, description in cursor.fetchall():
        text_to_check = f"{subject} {description}"
        if is_english(text_to_check):
            english_ids.append(ticket_id)
        else:
            non_english_ids.append(ticket_id)
    
    print(f"\n📊 Language Analysis:")
    print(f"   ✅ English tickets: {len(english_ids):,}")
    print(f"   ❌ Non-English tickets: {len(non_english_ids):,}")
    
    if non_english_ids:
        print(f"\n🗑️  Removing {len(non_english_ids):,} non-English tickets...")
        
        # Delete in batches for performance
        batch_size = 1000
        for i in range(0, len(non_english_ids), batch_size):
            batch = non_english_ids[i:i+batch_size]
            placeholders = ','.join('?' * len(batch))
            
            # Delete from tickets table
            cursor.execute(f"DELETE FROM tickets WHERE ticket_id IN ({placeholders})", batch)
            
            # Delete from rag_memory
            cursor.execute(f"DELETE FROM rag_memory WHERE ticket_id IN ({placeholders})", batch)
            
            # Delete from ticket_history
            cursor.execute(f"DELETE FROM ticket_history WHERE ticket_id IN ({placeholders})", batch)
            
            print(f"   Processed {min(i+batch_size, len(non_english_ids)):,} / {len(non_english_ids):,}", end='\r')
        
        conn.commit()
        print(f"\n   ✅ Deleted {len(non_english_ids):,} non-English tickets")
    else:
        print("\n✅ All tickets are already in English!")
    
    # Get final counts
    cursor.execute("SELECT COUNT(*) FROM tickets")
    total_after = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM rag_memory")
    rag_after = cursor.fetchone()[0]
    
    print(f"\n📊 Final Database State:")
    print(f"   Tickets: {total_after:,} (removed {total_before - total_after:,})")
    print(f"   RAG Memory: {rag_after:,} (removed {rag_before - rag_after:,})")
    
    # Vacuum database to reclaim space
    print(f"\n🧹 Optimizing database (VACUUM)...")
    cursor.execute("VACUUM")
    print(f"✅ Database optimized!")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ English-only filtering complete!")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    print("\n⚠️  WARNING: This will permanently delete non-English tickets!")
    print("Make sure you have a backup if needed.\n")
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response == 'yes':
        filter_english_tickets()
    else:
        print("❌ Operation cancelled.")
