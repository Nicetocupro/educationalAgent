# 这个文件只负责图的构建、编译
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from .states import State, inputState
from .human_input import human_input
from .memory import load_memory, create_memory
from .Supervisor import Supervisor
from .verify_info import VerifyInfoAgent
from .ProfileAgent import ProfileAgent
from utils.models import model
from utils.JsonFileCheckpointer import MyJsonFileCheckpointer
from pathlib import Path

def should_interrupt(state: State):
    if state.get("customer_id") is not None: 
        return "continue"
    else:
        return "interrupt"

class Graph:
    """负责组装图"""
    def __init__(self, checkpoint_dir: str | Path = "./checkpoints"):

        in_memory_store = InMemoryStore()
        
        # self._checkpointer = MemorySaver()
        self._checkpointer = MyJsonFileCheckpointer(base_dir=Path(checkpoint_dir))

        verify_info_node = VerifyInfoAgent(model)
        human_input_node = human_input()
        supervisor_node = Supervisor(model, self._checkpointer, in_memory_store)
        profile_node = ProfileAgent()

        multi_agent_final = StateGraph(State, input_schema=inputState)
        multi_agent_final.add_node("verify_info", verify_info_node)
        multi_agent_final.add_node("human_input", human_input_node)
        multi_agent_final.add_node("profile_node", profile_node)
        multi_agent_final.add_node("load_memory", load_memory)
        multi_agent_final.add_node("supervisor", supervisor_node)
        multi_agent_final.add_node("create_memory", create_memory(model))

        multi_agent_final.add_edge(START, "verify_info")
        multi_agent_final.add_conditional_edges(
            "verify_info",
            should_interrupt,
            {
                "continue": "profile_node",
                "interrupt": "human_input",
            },
        )

        multi_agent_final.add_edge("human_input", "verify_info")
        multi_agent_final.add_edge("profile_node", "load_memory")
        multi_agent_final.add_edge("load_memory", "supervisor")
        multi_agent_final.add_edge("supervisor", "create_memory")
        multi_agent_final.add_edge("create_memory", END)

        self.app = multi_agent_final.compile(name="multi_agent_verify",checkpointer=self._checkpointer, store=in_memory_store)

    def invoke(self, messages: list, thread_id: str = "default") -> dict:
        """封装调用，外部不用关心 config 细节"""
        config = {"configurable": {"thread_id": thread_id}}
        return self.app.invoke({"messages": messages}, config=config)

    def stream(self, messages: list, thread_id: str = "default"):
        """封装流式调用"""
        config = {"configurable": {"thread_id": thread_id}}
        return self.app.stream(
            {"messages": messages},
            config=config,
            stream_mode="messages",
        )
    
    def get_state(self, thread_id: str = "default", checkpoint_id: str = "default"):

        if checkpoint_id == "default":
            config = {"configurable": {"thread_id": thread_id}}
        else:
            config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
        
        return self.app.get_state(config)
    
    def get_state_history(self, thread_id: str = "default", checkpoint_id: str = "default"):

        if checkpoint_id == "default":
            config = {"configurable": {"thread_id": thread_id}}
        else:
            config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
        
        return self.app.get_state_history(config)