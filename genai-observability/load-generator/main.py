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
8. RAG pipeline (retrieve → rerank → generate)
9. Multi-step chain (summarize → analyze)
"""

import os
import random
import signal
import sys
import time

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

# --- OTel setup (traces + metrics + logs) ---
endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4000/v1/otlp")

trace_provider = TracerProvider()
trace_provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=f"{endpoint}/v1/traces",
            # Required: tells GreptimeDB to parse spans using its trace pipeline,
            # which flattens span attributes (e.g. gen_ai.*) into queryable columns.
            headers={"x-greptime-pipeline-name": "greptime_trace_v1"},
        )
    )
)
trace.set_tracer_provider(trace_provider)

metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
    export_interval_millis=15000,
)
meter_provider = MeterProvider(metric_readers=[metric_reader])
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

# Auto-instruments all OpenAI SDK calls — each chat.completions.create()
# becomes a span with gen_ai.* attributes (model, tokens, finish_reason, etc.)
OpenAIInstrumentor().instrument()

# Separate tracer for custom parent spans. Scenarios that use this tracer
# create multi-level trace trees: our custom spans become parents, and
# auto-instrumented LLM spans nest underneath as children.
tracer = trace.get_tracer("genai-load-generator")

# --- Config ---
MODEL = os.getenv("MODEL_NAME", "gpt-4o-mini")
# Use `or` instead of getenv default — docker-compose passes empty string (not unset)
# when the host var is absent, so getenv("MODELS", fallback) would return "" not fallback.
MODELS = [m.strip() for m in (os.getenv("MODELS") or MODEL).split(",") if m.strip()]
RPS = float(os.getenv("RPS", "0.5"))
if RPS <= 0:
    raise ValueError(f"RPS must be positive, got: {RPS}")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY") or "ollama",
    base_url=os.getenv("OPENAI_BASE_URL") or None,
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

# RAG_QUERIES[i] and RAG_CONTEXTS[i] are paired — same index yields a matching Q&A pair.
RAG_QUERIES = [
    "How does GreptimeDB handle time-series data ingestion?",
    "What is the difference between tags and fields in GreptimeDB?",
    "How do I set up OpenTelemetry with GreptimeDB?",
    "Explain GreptimeDB Flow for continuous aggregation.",
]

RAG_CONTEXTS = [
    "GreptimeDB uses a columnar storage engine optimized for time-series workloads. "
    "It supports OTLP, Prometheus remote write, InfluxDB line protocol, and SQL for ingestion.",
    "In GreptimeDB, tags (primary keys) are indexed columns used for filtering and grouping, "
    "while fields store the actual measurements. Tags are stored as strings.",
    "Send traces directly to GreptimeDB's /v1/otlp endpoint via OTLP HTTP. "
    "Set the x-greptime-pipeline-name header to greptime_trace_v1 for trace ingestion.",
    "GreptimeDB Flow provides continuous aggregation similar to materialized views. "
    "Define a source query over raw data and a sink table for pre-computed results.",
]

CHAIN_TOPICS = [
    "the impact of AI on software engineering practices",
    "best practices for designing time-series database schemas",
    "observability strategies for microservices architectures",
    "trade-offs between SQL and NoSQL for IoT data",
]


# ---------------------------------------------------------------------------
# Scenarios: flat (single LLM call, one span) vs nested (custom parent spans
# wrapping LLM calls, producing multi-level trace trees in the waterfall view).
# ---------------------------------------------------------------------------


def scenario_short():
    """Quick question — flat trace, single span."""
    prompt = random.choice(SHORT_PROMPTS)
    model = random.choice(MODELS)
    client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=random.randint(50, 150),
    )


def scenario_long():
    """Long generation — flat trace, high token count."""
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
    """Trigger errors via invalid model names — error is captured in the span."""
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
    """Function calling — nested trace: plan → execute tools → synthesize.

    Trace tree (when model invokes tools):
      tool_call_pipeline
      ├── plan_tool_use
      │   └── chat <model>          (auto-instrumented)
      ├── execute_tools
      │   └── tool.<name>           (simulated latency)
      └── synthesize_answer
          └── chat <model>          (auto-instrumented)
    """
    model = MODELS[0]
    prompt = random.choice(TOOL_PROMPTS)
    with tracer.start_as_current_span("tool_call_pipeline") as pipeline:
        pipeline.set_attribute("pipeline.type", "tool_call")
        pipeline.set_attribute("pipeline.prompt", prompt)

        with tracer.start_as_current_span("plan_tool_use"):
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                tools=TOOLS,
                max_tokens=200,
            )

        choice = response.choices[0]
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            messages = [
                {"role": "user", "content": prompt},
                choice.message,
            ]
            with tracer.start_as_current_span("execute_tools") as tools_span:
                tools_span.set_attribute("tools.count", len(choice.message.tool_calls))
                for tc in choice.message.tool_calls:
                    with tracer.start_as_current_span(
                        f"tool.{tc.function.name}"
                    ) as tool_span:
                        tool_span.set_attribute("tool.name", tc.function.name)
                        tool_span.set_attribute("tool.arguments", tc.function.arguments)
                        # Simulate tool execution latency
                        time.sleep(random.uniform(0.02, 0.08))
                        result = MOCK_TOOL_RESULTS.get(
                            tc.function.name, '{"error": "unknown tool"}'
                        )
                        tool_span.set_attribute("tool.result", result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )

            with tracer.start_as_current_span("synthesize_answer"):
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=200,
                )


def scenario_rag():
    """Simulated RAG pipeline — nested trace with retrieval and generation.

    Trace tree:
      rag_pipeline
      ├── retrieve_documents        (simulated latency)
      │   └── rerank                (simulated latency)
      └── generate_answer
          └── chat <model>          (auto-instrumented, real LLM call)
    """
    model = MODELS[0]
    idx = random.randrange(len(RAG_QUERIES))
    query = RAG_QUERIES[idx]
    context = RAG_CONTEXTS[idx]

    with tracer.start_as_current_span("rag_pipeline") as pipeline:
        pipeline.set_attribute("rag.query", query)

        # Step 1: Simulate vector DB retrieval
        with tracer.start_as_current_span("retrieve_documents") as retrieve:
            time.sleep(random.uniform(0.03, 0.10))
            num_docs = random.randint(3, 8)
            retrieve.set_attribute("rag.num_candidates", num_docs)

            # Step 1b: Simulate reranking
            with tracer.start_as_current_span("rerank") as rerank:
                time.sleep(random.uniform(0.01, 0.05))
                top_k = min(3, num_docs)
                rerank.set_attribute("rag.top_k", top_k)

        # Step 2: Generate answer with retrieved context
        with tracer.start_as_current_span("generate_answer"):
            client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Answer based on this context:\n{context}",
                    },
                    {"role": "user", "content": query},
                ],
                max_tokens=random.randint(100, 300),
            )


def scenario_chain():
    """Sequential LLM chain — step 2 uses step 1's output.

    Trace tree:
      llm_chain
      ├── step_summarize
      │   └── chat <model>          (auto-instrumented)
      └── step_analyze
          └── chat <model>          (auto-instrumented, prompt includes summary)
    """
    model = MODELS[0]
    topic = random.choice(CHAIN_TOPICS)

    with tracer.start_as_current_span("llm_chain") as chain:
        chain.set_attribute("chain.topic", topic)
        chain.set_attribute("chain.steps", 2)

        # Step 1: Summarize
        with tracer.start_as_current_span("step_summarize"):
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": f"Write a brief 2-sentence summary about {topic}.",
                    }
                ],
                max_tokens=100,
            )
            summary = resp.choices[0].message.content or ""

        # Step 2: Analyze
        with tracer.start_as_current_span("step_analyze"):
            client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": f"Given this summary: '{summary}'\n\n"
                        f"List 3 key insights or implications.",
                    }
                ],
                max_tokens=200,
            )


SCENARIOS = [
    (scenario_short, 25),  # 25% short questions (flat)
    (scenario_long, 8),  # 8% long generation (flat)
    (scenario_multi_turn, 5),  # 5% multi-turn (flat)
    (scenario_comparison, 4),  # 4% model comparison (flat)
    (scenario_error, 8),  # 8% errors
    (scenario_burst, 5),  # 5% burst traffic
    (scenario_tool_call, 15),  # 15% tool calling (nested)
    (scenario_rag, 18),  # 18% RAG pipeline (nested)
    (scenario_chain, 12),  # 12% multi-step chain (nested)
]


def pick_scenario():
    fns, weights = zip(*SCENARIOS)
    return random.choices(fns, weights=weights)[0]


def shutdown(signum, frame):
    print("\nShutting down, flushing telemetry...")
    trace_provider.force_flush()
    meter_provider.force_flush()
    log_provider.force_flush()
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
