from langchain_core.messages import HumanMessage
from agent.graph import Graph
import uuid
"""
如果作为服务端的话，不应该这样去启动，应该是只需要提供创造thread_id的接口
而不是每次都要，初始化 Graph()
"""

graph = Graph()

def chat(user_input: str, thread_id: str = "user_001"):
    print("🤖 助手：", end="", flush=True)

    """
    result = graph.invoke([HumanMessage(content=user_input)], thread_id)

    for message in result["messages"]:
        message.pretty_print()

    """
    for chunk, metadata in graph.stream([HumanMessage(content=user_input)], thread_id):
        if chunk.content and metadata.get("langgraph_node") == "supervisor":
            print(chunk.content, end="", flush=True)

    print()

if __name__ == "__main__":

    thread_id = str(uuid.uuid4())

    while True:
        user_input = input("\n🧑 你：").strip()
        if user_input.lower() == "quit":
            break
        
        chat(user_input, thread_id=thread_id)
    
    print(graph.get_state(thread_id))