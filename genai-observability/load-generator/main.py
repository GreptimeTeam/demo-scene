"""
Generates diverse LLM requests to produce rich telemetry data.

Scenarios:
1. Short questions (fast, low token)
2. Long-form generation (slow, high token)
3. Multi-turn conversations (context accumulation)
4. Multi-model comparison (same prompt, different models)
5. Error injection (invalid model name, empty messages)
6. Burst traffic (rapid-fire short requests)
7. Tool/function calling (multi-step traces)
"""

import os
import random
import signal
import sys
import time

from openai import OpenAI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# --- OTel setup (traces + metrics) ---
endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

trace_provider = TracerProvider()
trace_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
)
trace.set_tracer_provider(trace_provider)

metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
    export_interval_millis=15000,
)
meter_provider = MeterProvider(metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

OpenAIInstrumentor().instrument()

# --- Config ---
MODEL = os.getenv("MODEL_NAME", "gpt-4o-mini")
MODELS = [m.strip() for m in os.getenv("MODELS", MODEL).split(",") if m.strip()]
RPS = float(os.getenv("RPS", "0.5"))
if RPS <= 0:
    raise ValueError(f"RPS must be positive, got: {RPS}")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "ollama"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

SHORT_PROMPTS = [
    "What is GreptimeDB?",
    "Explain OpenTelemetry in one sentence.",
    "What is a time-series database?",
    "Define observability.",
    "What is PromQL?",
]

LONG_PROMPTS = [
    "Write a detailed comparison of GreptimeDB, InfluxDB, and TimescaleDB "
    "covering architecture, query language, scalability, and cost. "
    "Include specific technical details and use cases for each.",
    "Explain the complete architecture of OpenTelemetry including the SDK, "
    "collector, exporters, and semantic conventions. Give code examples.",
]

MULTI_TURN = [
    [
        {"role": "user", "content": "What is a time-series database?"},
        {
            "role": "assistant",
            "content": "A database optimized for timestamped data.",
        },
        {"role": "user", "content": "Give me 3 examples with their key differences."},
    ],
]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"}
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a math expression",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]

TOOL_PROMPTS = [
    "What's the weather in Tokyo?",
    "What's the weather in New York right now?",
    "Calculate 42 * 17 + 3",
]

MOCK_TOOL_RESULTS = {
    "get_weather": '{"temperature": 22, "condition": "sunny", "humidity": 65}',
    "calculate": '{"result": 717}',
}


def scenario_short():
    """Quick question, randomized token limit for diverse output lengths."""
    prompt = random.choice(SHORT_PROMPTS)
    model = random.choice(MODELS)
    client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=random.randint(50, 150),
    )


def scenario_long():
    """Long generation, randomized token limit for varied output sizes."""
    prompt = random.choice(LONG_PROMPTS)
    client.chat.completions.create(
        model=MODELS[0],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=random.randint(300, 800),
    )


def scenario_multi_turn():
    """Multi-turn conversation with context."""
    messages = random.choice(MULTI_TURN)
    client.chat.completions.create(
        model=MODELS[0],
        messages=messages,
        max_tokens=200,
    )


def scenario_comparison():
    """Same prompt to different models for A/B comparison."""
    prompt = random.choice(SHORT_PROMPTS)
    for model in MODELS:
        try:
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=random.randint(50, 150),
            )
        except Exception as e:
            print(f"  Model {model} error: {e}")


def scenario_error():
    """Trigger errors via invalid model names."""
    fake_models = ["nonexistent-model-xyz", "invalid-llm-404", "fake-gpt-000"]
    try:
        client.chat.completions.create(
            model=random.choice(fake_models),
            messages=[{"role": "user", "content": "test"}],
        )
    except Exception:
        pass  # Error is captured in the span


def scenario_burst():
    """Burst of 2-3 short requests with small gaps to create visible traffic spikes."""
    count = random.randint(2, 3)
    model = random.choice(MODELS)
    for i in range(count):
        try:
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": random.choice(SHORT_PROMPTS)}],
                max_tokens=random.randint(30, 80),
            )
        except Exception as e:
            print(f"  Burst request error: {e}")
        if i < count - 1:
            time.sleep(0.5)


def scenario_tool_call():
    """Function calling with tool use — generates multi-step traces."""
    model = MODELS[0]
    prompt = random.choice(TOOL_PROMPTS)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=TOOLS,
        max_tokens=200,
    )
    # If model wants to call tools, send back mock results
    choice = response.choices[0]
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        messages = [
            {"role": "user", "content": prompt},
            choice.message,
        ]
        for tc in choice.message.tool_calls:
            result = MOCK_TOOL_RESULTS.get(
                tc.function.name, '{"error": "unknown tool"}'
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )
        # Second call to get final response with tool results
        client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=200,
        )


SCENARIOS = [
    (scenario_short, 40),  # 40% short questions
    (scenario_long, 12),  # 12% long generation
    (scenario_multi_turn, 8),  # 8% multi-turn
    (scenario_comparison, 5),  # 5% model comparison
    (scenario_error, 10),  # 10% errors
    (scenario_burst, 10),  # 10% burst traffic
    (scenario_tool_call, 15),  # 15% function calling
]


def pick_scenario():
    r = random.randint(1, 100)
    cumulative = 0
    for fn, weight in SCENARIOS:
        cumulative += weight
        if r <= cumulative:
            return fn
    return SCENARIOS[0][0]


def shutdown(signum, frame):
    print("\nShutting down, flushing telemetry...")
    trace_provider.force_flush()
    meter_provider.force_flush()
    sys.exit(0)


def main():
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    interval = 1.0 / RPS
    print(f"GenAI Load Generator: models={MODELS}, rps={RPS}")
    cycle = 0
    while True:
        cycle += 1
        fn = pick_scenario()
        t0 = time.time()
        try:
            fn()
            elapsed = time.time() - t0
            print(f"[{cycle}] {fn.__name__} ({elapsed:.2f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[{cycle}] {fn.__name__} ERROR: {e}")
        # Adaptive sleep: deduct request duration so total cycle ≈ 1/RPS
        remaining = interval - elapsed
        if remaining > 0:
            time.sleep(remaining)


if __name__ == "__main__":
    main()
