import argparse
import os
from time import sleep
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import itertools

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('file', type=str, help='File to ingest')
parser.add_argument('--precision', type=str, help='Precision of the data', default='ns')
args = parser.parse_args()

with open(args.file) as f:
    lines = f.readlines()

load_dotenv()
url = os.environ["GREPTIME_HOST"].rstrip('/')
url = f"{url}/v1/influxdb/"
token = os.environ["GREPTIME_USERNAME"] + ":" + os.environ["GREPTIME_PASSWORD"]
org = "my-org" # GreptimeDB doesn't use orgs
bucket = os.environ["GREPTIME_DATABASE"]

client = InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

# TODO implement itertools.batched with a functionn to drop requirement of Python 3.12+
for batch_lines in itertools.batched(lines, 1000):
    write_api.write(bucket=bucket, write_precision=args.precision, record=batch_lines)
    print(f'Wrote {len(batch_lines)} lines')
    sleep(1) # sleep for 1 second avoid rate limit

print('Done')
