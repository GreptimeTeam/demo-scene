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

df = conn.query("SELECT COUNT(*) AS total_hits FROM keyboard_monitor", ttl=5)
st.metric("Total hits", df.total_hits[0])

most_frequent_key, most_frequent_combo = st.columns(2)
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits NOT LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 1;
""", ttl=5)
most_frequent_key.metric("Most frequent key", df.hits.iloc[0] if not df.empty else "No data")
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 1;
""", ttl=5)
most_frequent_combo.metric("Most frequent combo", df.hits.iloc[0] if not df.empty else "No data")

top_frequent_keys, top_frequent_combos = st.columns(2)
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits NOT LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 10;
""", ttl=5)
top_frequent_keys.subheader("Top 10 keys")
top_frequent_keys.dataframe(df)
df = conn.query("""
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
WHERE hits LIKE '%+%'
GROUP BY hits
ORDER BY times DESC limit 10;
""", ttl=5)
top_frequent_combos.subheader("Top 10 combos")
top_frequent_combos.dataframe(df)

st.header("Find your inputs frequency of day")
local_tz = tzlocal.get_localzone()
d = st.date_input("Pick a day:", value=datetime.date.today())
start = datetime.datetime.combine(d, datetime.time.min, tzinfo=local_tz)
end = datetime.datetime.combine(d + datetime.timedelta(days=1), datetime.time.min, tzinfo=local_tz)
start_utc = start.astimezone(datetime.timezone.utc).isoformat()
end_utc = end.astimezone(datetime.timezone.utc).isoformat()
query = f"""
SELECT 
    ts,
    COUNT(1) RANGE '1h' as times
FROM keyboard_monitor
WHERE ts >= '{start_utc}' AND ts < '{end_utc}'
ALIGN '1h'
ORDER BY ts ASC;
"""
df = conn.query(query, ttl=5)
df['ts'] = df['ts'].dt.tz_localize(pytz.utc).dt.tz_convert(local_tz)
st.dataframe(df)
