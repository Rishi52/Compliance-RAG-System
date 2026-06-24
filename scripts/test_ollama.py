from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen3:4b"
)

response = llm.invoke("Hello")

print(response.content)