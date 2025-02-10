import openlit
from langchain_community.llms import Ollama

openlit.init(otlp_endpoint="http://127.0.0.1:4318", disable_batch=True)

llm = Ollama(model='deepseek-r1:1.5b')

print(llm.invoke("Tell me a joke"))
