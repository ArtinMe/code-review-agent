"""Fixed content for the scripted debate demo. Nothing here comes from a model."""

ORIGINAL = '''import sqlite3

def find_orders(db_path, customer):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM orders WHERE customer = '{customer}'")
    rows = cursor.fetchall()
    totals = []
    for i in range(len(rows) + 1):
        totals.append(rows[i][2])
    return sum(totals)
'''

# The patch both models agree on in the demo. It fixes the agreed findings and
# deliberately doesn't guess the total column's name for SUM(): that name isn't
# in this file, which is the same rule the real fixer follows.
AGREED_FIX = '''import sqlite3
from contextlib import closing

def find_orders(db_path, customer):
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE customer = ?", (customer,))
        rows = cursor.fetchall()
    totals = []
    for i in range(len(rows)):
        totals.append(rows[i][2])
    return sum(totals)
'''
