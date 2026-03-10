"""
Minimal GenAI application instrumented with OpenTelemetry.
Demonstrates: chat completion with gen_ai.* semantic conventions.
"""

import os

from openai import OpenAI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4000/v1/otlp")

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=f"{endpoint}/v1/traces",
            # Required: tells GreptimeDB to parse spans using its trace pipeline,
            # which flattens span attributes (e.g. gen_ai.*) into queryable columns.
            headers={"x-greptime-pipeline-name": "greptime_trace_v1"},
        )
    )
)
trace.set_tracer_provider(provider)

meter_provider = MeterProvider(
    metric_readers=[
        PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
        )
    ]
)
metrics.set_meter_provider(meter_provider)

log_provider = LoggerProvider()
log_provider.add_log_record_processor(
    BatchLogRecordProcessor(
        OTLPLogExporter(
            endpoint=f"{endpoint}/v1/logs",
            headers={"X-Greptime-Log-Table-Name": "genai_conversations"},
        )
    )
)
set_logger_provider(log_provider)

OpenAIInstrumentor().instrument()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY") or "ollama",
    base_url=os.getenv("OPENAI_BASE_URL") or None,
)

MODEL = os.getenv("MODEL_NAME", "gpt-4o-mini")


def chat(prompt: str, model: str = MODEL) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    print(chat("What is OpenTelemetry in one sentence?"))
    print(chat("Explain GreptimeDB in two sentences."))
    provider.force_flush()
    meter_provider.force_flush()
    log_provider.force_flush()
