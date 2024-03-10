import os
from dotenv import load_dotenv
import streamlit as st


st.title("Keyboard Monitor")

load_dotenv()
conn = st.connection(
    "greptimedb",
    type="sql",
    url=os.environ['DATABASE_URL'],
)

df = conn.query("SELECT COUNT(*) AS total_hits FROM keyboard_monitor")
st.metric("Total hits", df.total_hits[0])
most_frequent_key, most_frequent_combos = st.columns(2)
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits NOT LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 1;
""")
most_frequent_key.metric("Most frequent key", df.hits[0])
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 1;
""")
most_frequent_combos.metric("Most frequent combos", df.hits[0])
