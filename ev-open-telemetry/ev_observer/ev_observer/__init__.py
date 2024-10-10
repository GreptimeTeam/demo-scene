import os, base64
from dotenv import load_dotenv
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
)

load_dotenv()

db_http_scheme = os.getenv("GREPTIME_SCHEME") or "http"
db_host = os.getenv("GREPTIME_HOST") or "greptimedb"
db_port = os.getenv("GREPTIME_PORT") or 4000
db_name = os.getenv("GREPTIME_DB") or "public"
db_user = os.getenv("GREPTIME_USERNAME") or ""
db_password = os.getenv("GREPTIME_PASSWORD") or ""

scrape_interval = int(os.getenv("SCRAPE_INTERVAL_SEC", "60"))
is_mock = bool(os.getenv("IS_MOCK", False))

# Uncomment below lines to use basic auth
auth = f"{db_user}:{db_password}"
b64_auth = base64.b64encode(auth.encode()).decode("ascii")
endpoint = f"{db_http_scheme}://{db_host}:{db_port}/v1/otlp/v1/metrics"
exporter = OTLPMetricExporter(
    endpoint=endpoint,
    headers={
        "Authorization": f"Basic {b64_auth}",
        "x-greptime-db-name": db_name,
    },
    timeout=5,
)

metric_reader = PeriodicExportingMetricReader(exporter, scrape_interval * 1000)
provider = MeterProvider(metric_readers=[metric_reader])
metrics.set_meter_provider(provider)
meter = metrics.get_meter("ev.metrics")
