import datetime
import os
from dotenv import load_dotenv
import pytz
import streamlit as st
import tzlocal


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
top_frequent_keys.subheader("Top 10 keys")
top_frequent_keys.dataframe(df)
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 10;
""")
top_frequent_combos.subheader("Top 10 combos")
top_frequent_combos.dataframe(df)

st.header("Find your inputs frequency of day")
local_tz = tzlocal.get_localzone()
hours = int(local_tz.utcoffset(datetime.datetime.now()).total_seconds() / 3600)
if hours > 0:
    offset = f" + INTERVAL '{hours} hours'"
elif hours < 0:
    offset = f" - INTERVAL '{hours} hours'"
else:
    offset = ''
d = st.date_input("Pick a day:", value=datetime.date.today())
query = f"""
SELECT 
    ts,
    COUNT(1) RANGE '1h' as times
FROM keyboard_monitor
WHERE date_trunc('day', ts{offset}) = '{d}'
ALIGN '1h'
ORDER BY ts ASC
LIMIT 10;
"""
df = conn.query(query)
df['ts'] = df['ts'].dt.tz_localize(pytz.utc).dt.tz_convert(local_tz)
st.dataframe(df)
