from agent.states import State
from langgraph.types import interrupt
from langchain.messages import HumanMessage

class human_input:
    def __call__(self, state: State):
        user_input = interrupt("Please provide input.")
        return {"messages": [HumanMessage(content=user_input)]}
    
