from langchain_core.messages import HumanMessage
from agent.graph import Graph
import uuid

graph = Graph()
supervisor_node = graph.app.nodes.get("supervisor")  # 或者你 graph 里注册的节点名
print("supervisor_node type:", type(supervisor_node))

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
            print(graph.get_state())
    print()



if __name__ == "__main__":
    while True:
        user_input = input("\n🧑 你：").strip()
        if user_input.lower() == "quit":
            break
        thread_id = uuid.uuid4()
        chat(user_input, thread_id)