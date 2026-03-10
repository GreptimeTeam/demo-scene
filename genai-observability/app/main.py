"""
Minimal GenAI application instrumented with OpenTelemetry.
Demonstrates: chat completion with gen_ai.* semantic conventions.
"""

import os

from openai import OpenAI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
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
