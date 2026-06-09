"""
Database fix script to add missing rag_memory table and check structure
"""
import sqlite3
import os

DB_NAME = os.path.join(os.path.dirname(__file__), "smart_ticket_engine.db")

def fix_database():
    """Add missing rag_memory table if it doesn't exist"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("DATABASE FIX UTILITY")
    print("=" * 60)
    
    # Check existing tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n✅ Existing tables: {', '.join(tables)}")
    
    # Add rag_memory table if missing
    if 'rag_memory' not in tables:
        print("\n⚠️  rag_memory table MISSING - Creating now...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rag_memory (
                memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                ticket_subject TEXT,
                ticket_description TEXT,
                incident_type TEXT,
                department TEXT,
                priority TEXT,
                root_cause TEXT,
                resolution_steps TEXT,
                resolution_time_mins REAL,
                sentiment TEXT,
                created_date TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
            )
        """)
        conn.commit()
        print("✅ rag_memory table created successfully!")
        
        # Create index for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rag_department_incident 
            ON rag_memory(department, incident_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rag_priority 
            ON rag_memory(priority)
        """)
        conn.commit()
        print("✅ Performance indexes created!")
    else:
        print("\n✅ rag_memory table already exists")
    
    # Check ticket count
    cursor.execute("SELECT COUNT(*) FROM tickets")
    ticket_count = cursor.fetchone()[0]
    print(f"\n📊 Total tickets in database: {ticket_count:,}")
    
    # Check rag_memory count
    cursor.execute("SELECT COUNT(*) FROM rag_memory")
    rag_count = cursor.fetchone()[0]
    print(f"📊 RAG memory entries: {rag_count:,}")
    
    if ticket_count > rag_count:
        print(f"\n⚠️  {ticket_count - rag_count:,} tickets need to be synced to RAG memory")
        print("💡 Run populate_rag_memory.py to sync resolved tickets to RAG knowledge base")
    
    conn.close()
    print("\n" + "=" * 60)
    print("✅ Database check complete!")
    print("=" * 60)

if __name__ == "__main__":
    fix_database()
