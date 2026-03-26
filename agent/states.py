from typing_extensions import TypedDict
from typing import Annotated, List
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.managed.is_last_step import RemainingSteps

# 定义 state 节点
class inputState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]

class State(inputState):
    customer_id: int
    loaded_memory: str
    remaining_steps: int
    portrait: str # 人物画像
