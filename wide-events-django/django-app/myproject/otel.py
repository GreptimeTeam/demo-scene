# myproject/otel.py
import os
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor

# Initialize tracing
resource = Resource.create({"service.name": "myproject"})
trace.set_tracer_provider(TracerProvider(resource=resource))
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

# Add OTLP HTTP Exporter if endpoint is provided
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
    logger.info(f"OTLP Exporter enabled with endpoint: {otlp_endpoint}")
else:
    logger.info("OTLP Exporter disabled: OTEL_EXPORTER_OTLP_ENDPOINT not set")

# Instrument Django
DjangoInstrumentor().instrument()
# Instrument Sqlite3
SQLite3Instrumentor().instrument()

logger.debug("OpenTelemetry instrumentation initialized successfully.")
