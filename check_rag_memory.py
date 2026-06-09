"""Quick script to check RAG memory/knowledge base"""
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

# Count tickets by status
cursor.execute("SELECT COUNT(*) FROM tickets WHERE status='Done'")
done_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(DISTINCT department) FROM tickets WHERE status='Done'")
dept_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(DISTINCT incident_type) FROM tickets WHERE status='Done'")
type_count = cursor.fetchone()[0]

cursor.execute("SELECT department, COUNT(*) as cnt FROM tickets WHERE status='Done' GROUP BY department ORDER BY cnt DESC")
dept_breakdown = cursor.fetchall()

print("="*60)
print("RAG KNOWLEDGE BASE (Memory)")
print("="*60)
print(f"\n📊 Total resolved tickets: {done_count:,}")
print(f"🏢 Unique departments: {dept_count}")
print(f"🎫 Unique incident types: {type_count}")

print(f"\n📂 Tickets per Department:")
for dept, cnt in dept_breakdown:
    print(f"  {dept}: {cnt:,}")

conn.close()
