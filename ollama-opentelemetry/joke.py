import openlit

from langchain_ollama.llms import OllamaLLM

openlit.init(otlp_endpoint="http://127.0.0.1:4318", disable_batch=True)

llm = OllamaLLM(model='deepseek-r1:1.5b')

print(llm.invoke("Tell me a joke"))
