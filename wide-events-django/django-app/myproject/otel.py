# myproject/otel.py
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


# Add OTLP HTTP Exporter for remote observability
# otlp_exporter = OTLPSpanExporter(
#     endpoint="http://localhost:4318/v1/traces"  # OTLP HTTP endpoint
# )
# trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

# Instrument Django
DjangoInstrumentor().instrument()
# Instrument Sqlite3
SQLite3Instrumentor().instrument()

logger.debug("OpenTelemetry instrumentation initialized successfully.")
