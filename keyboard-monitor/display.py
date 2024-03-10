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

most_frequent_key, most_frequent_combo = st.columns(2)
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
most_frequent_combo.metric("Most frequent combo", df.hits[0])

top_frequent_keys, top_frequent_combos = st.columns(2)
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits NOT LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 10;
""")
top_frequent_keys.header("Top 10 keys")
top_frequent_keys.dataframe(df)
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 10;
""")
top_frequent_combos.header("Top 10 combos")
top_frequent_combos.dataframe(df)

# 一个日期选择器展示当天每个小时的 hits 数量
