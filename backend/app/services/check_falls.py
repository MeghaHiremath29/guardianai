import sqlite3

c = sqlite3.connect("guardianai.db")

r = c.execute(
    "SELECT id, event_type, status, confidence, created_at "
    "FROM emergencies "
    "WHERE event_type='FALL' "
    "ORDER BY created_at DESC "
    "LIMIT 5"
)

for row in r.fetchall():
    print(row)

c.close()