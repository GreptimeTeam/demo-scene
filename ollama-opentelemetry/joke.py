import openlit

from langchain_ollama.llms import OllamaLLM

openlit.init(
    otlp_endpoint="http://otel-collector:4318",
    application_name="llm-joke-app",
    environment="demo",
    disable_batch=True,
)

llm = OllamaLLM(model="deepseek-r1:1.5b", base_url="http://ollama:11434")

print(llm.invoke("Tell me a joke"))
