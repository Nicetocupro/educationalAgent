from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field
from typing import List
from agent.states import State
from langchain.messages import HumanMessage, SystemMessage

class UserProfile(BaseModel):
    customer_id: str = Field(
        description="The customer ID of the customer"
    )

    # 添加一些想添加的特征，但需要和画像部分分开
    music_preferences: List[str] = Field(
        description="The music preferences of the customer"
    )

create_memory_prompt = """You are an expert analyst that is observing a conversation that has taken place between a customer and a customer support assistant. The customer support assistant works for a digital music store, and has utilized a multi-agent team to answer the customer's request. 
You are tasked with analyzing the conversation that has taken place between the customer and the customer support assistant, and updating the memory profile associated with the customer. 
You specifically care about saving any music interest the customer has shared about themselves, particularly their music preferences to their memory profile.

<core_instructions>
1. The memory profile may be empty. If it's empty, you should ALWAYS create a new memory profile for the customer.
2. You should identify any music interest the customer during the conversation and add it to the memory profile **IF** it is not already present.
3. For each key in the memory profile, if there is no new information, do NOT update the value - keep the existing value unchanged.
4. ONLY update the values in the memory profile if there is new information.
</core_instructions>

<expected_format>
The customer's memory profile should have the following fields:
- customer_id: the customer ID of the customer
- music_preferences: the music preferences of the customer

IMPORTANT: ENSURE your response is an object with these fields.
</expected_format>


<important_context>
**IMPORTANT CONTEXT BELOW**
To help you with this task, I have attached the conversation that has taken place between the customer and the customer support assistant below, as well as the existing memory profile associated with the customer that you should either update or create. 

The conversation between the customer and the customer support assistant that you should analyze is as follows:
{conversation}

The existing memory profile associated with the customer that you should either update or create based on the conversation is as follows:
{memory_profile}

</important_context>

Reminder: Take a deep breath and think carefully before responding.
"""

def format_user_memory(user_data):
    """Formats music preferences from users, if available."""
    profile = user_data['memory']
    result = ""
    if hasattr(profile, 'music_preferences') and profile.music_preferences:
        result += f"Music Preferences: {', '.join(profile.music_preferences)}"
    return result.strip()

def load_memory(state: State, store: BaseStore):
    """Loads music preferences from users, if available."""
    
    user_id = state["customer_id"]
    namespace = ("memory_profile", user_id)
    existing_memory = store.get(namespace, "user_memory")
    print(store.get(namespace, "user_memory"))
    print()
    formatted_memory = ""
    if existing_memory and existing_memory.value:
        formatted_memory = format_user_memory(existing_memory.value)

    return {"loaded_memory" : formatted_memory}


# memory.py

def create_memory(model):
    """工厂函数，返回一个已绑定 model 的 node 函数"""

    def _create_memory(state: State, store: BaseStore):
        user_id = str(state["customer_id"])
        namespace = ("memory_profile", user_id)
        formatted_memory = state["loaded_memory"]

        formatted_system_message = SystemMessage(
            content=create_memory_prompt.format(
                conversation=state["messages"],
                memory_profile=formatted_memory,
            )
        )
        user_prompt = HumanMessage(
            content="Please analyze the conversation and update the customer's memory profile according to the instructions."
        )

        updated_memory = (
            model.with_structured_output(UserProfile)
            .invoke([formatted_system_message, user_prompt])
        )

        store.put(namespace, "user_memory", {"memory": updated_memory})
        # create_memory 不需要更新 state，返回空 dict 即可
        return {}

    return _create_memory