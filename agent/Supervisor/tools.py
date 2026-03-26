from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from langchain.messages import HumanMessage
from typing import Annotated

def create_dialogue_tool(dialogue_agent_instance):
    """
    用闭包把已初始化的 DialogueAgent 实例捕获进来，
    返回一个可以挂到 Supervisor 上的 tool。
    """

    @tool(
        "DialogueAgent",
        description="""
        对话推理 Agent。
        当用户需要政策咨询、多轮问答、查询奖学金/导师/课程等具体政策信息时调用。
        输入 query 为用户的核心问题（由你提炼，不要原样转发整段对话）。
        """
    )
    def call_dialogue_subagent(
        query: str,
        state: Annotated[dict, InjectedState]  # LangGraph 自动注入，Supervisor 无需手动传
    ) -> str:
        """
        query: Supervisor 提炼出的用户核心问题
        state: 由 LangGraph 自动注入的当前 graph state（含 portrait、loaded_memory 等）
        """
        result = dialogue_agent_instance(state)      # ← __call__，不是 .invoke()
        return result["messages"][-1].content

    return call_dialogue_subagent

def create_recommend_tool(recommend_agent_instance):
    """
    原理同上
    """
    @tool(
        "RecommendAgent",
        description="""
        "个性化推荐agent"
        """
    )
    def call_recommend_subagent(
        query: str,
        state: Annotated[dict, InjectedState]  # LangGraph 自动注入，Supervisor 无需手动传
    ) -> str:
        result = recommend_agent_instance(state)     # ← 同上
        
        return result["messages"][-1].content
    
    return call_recommend_subagent

def create_push_tool(push_agent_instance):
    """
    原理同上
    """
    @tool(
        "PushAgent",
        description="""
        "推送agent"
        """
    )
    def call_push_subagent(
        query: str,
        state: Annotated[dict, InjectedState]  # LangGraph 自动注入，Supervisor 无需手动传
    ) -> str:
        result = push_agent_instance(state)     

        return result["messages"][-1].content
    
    return call_push_subagent

