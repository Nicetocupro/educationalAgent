from agent.states import State
from .tools import get_portrait_from_db

class ProfileAgent:
    """
    画像加载节点 —— 不需要 LLM，纯数据加载。
    从画像数据库拉取用户画像，写入 state 供后续所有 Agent 使用。
    """

    def __call__(self, state:State)->dict:
        customer_id = state.get("customer_id")

        if not customer_id:
            return {
                "portrait": "暂无画像：未获取到学生ID",
            }
        
        portrait = get_portrait_from_db.invoke({"customer_id": customer_id})

        return {
            "portrait": portrait,
        }