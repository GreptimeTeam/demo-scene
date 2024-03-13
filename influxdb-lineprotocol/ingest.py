import argparse
import os
import sys
from time import sleep
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import itertools

if sys.version_info >= (3, 12):
    batched = itertools.batched
else:
    def batched(iterable, n):
        iter_ = iter(iterable)
        while True:
            batch = tuple(itertools.islice(iter_, n))
            if not batch:
                break
            yield batch

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('file', type=str, help='File to ingest')
parser.add_argument('--precision', type=str, help='Precision of the data', default='ns')
args = parser.parse_args()

load_dotenv()
url = os.environ["GREPTIME_HOST"].rstrip('/')
url = f"{url}/v1/influxdb/"
token = os.environ["GREPTIME_USERNAME"] + ":" + os.environ["GREPTIME_PASSWORD"]
org = "my-org" # GreptimeDB doesn't use orgs
bucket = os.environ["GREPTIME_DATABASE"]

client = InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

with open(args.file) as f:
    for batch_lines in batched(f, 1000):
        write_api.write(bucket=bucket, write_precision=args.precision, record=batch_lines)
        print(f'Wrote {len(batch_lines)} lines')
        sleep(1) # sleep for 1 second avoid rate limit

# NOTE - Write data points directly is possible:
#
# import time
# from influxdb_client import Point, WritePrecision
# p = Point("my_measurement").tag("location", "Prague").field("temperature", 25.3).time(time.time_ns(), WritePrecision.NS)
# write_api.write(bucket=bucket, record=p)

print('Done')
