from opentelemetry import metrics
from dotenv import load_dotenv
import os
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
)

load_dotenv()

required_env_vars = {
    "GREPTIME_HOST": "db_host",
    "GREPTIME_DB": "db_name",
    # "GREPTIME_USER": "db_user",
    # "GREPTIME_PASSWORD": "db_password",
}

db_host, db_name, db_user, db_password = "", "", "", ""
for env_var, var_name in required_env_vars.items():
    value = os.getenv(env_var)
    if value is None:
        raise Exception(f"Environment variable {env_var} is not set")
    globals()[var_name] = value

scrape_interval = int(os.getenv("SCRAPE_INTERVAL_SEC", "60"))
is_mock = bool(os.getenv("IS_MOCK", False))

# Uncomment below lines to use basic auth
# auth = f"{db_user}:{db_password}"
# b64_auth = base64.b64encode(auth.encode()).decode("ascii")
endpoint = f"http://{db_host}/v1/otlp/v1/metrics"
exporter = OTLPMetricExporter(
    endpoint=endpoint,
    headers={
        # "Authorization": f"Basic {b64_auth}",
        "x-greptime-db-name": db_name,
    },
    timeout=5,
)

metric_reader = PeriodicExportingMetricReader(exporter, scrape_interval * 1000)
provider = MeterProvider(metric_readers=[metric_reader])
metrics.set_meter_provider(provider)
meter = metrics.get_meter("ev.metrics")
