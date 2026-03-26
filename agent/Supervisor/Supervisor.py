from langchain.messages import SystemMessage, ToolMessage
from agent.states import State
from .tools import create_dialogue_tool, create_recommend_tool, create_push_tool
from agent.DialogueAgent import DialogueAgent
from agent.RecommendAgent import RecommendAgent
from agent.PushAgent import PushAgent

supervisor_prompt = """
你是书院教育智能体的核心调度器（Supervisor），负责理解学生意图、路由到合适的子Agent、并维护对话记忆。

## 当前学生信息
- 学生ID：{customer_id}
- 学生画像：{portrait}
- 历史记忆摘要：{loaded_memory}

## 你的三项核心职责

### 1. 意图分类
每轮对话开始时，先判断用户意图属于哪个类别：
- **policy_query**：政策咨询类 —— 问具体规定、条件、流程、截止时间等
  示例："我能申请哪些奖学金""导师双选怎么操作""学业预警的标准是什么"
- **recommendation**：资源推荐类 —— 问书籍、活动、实验室、讲座等个性化推荐
  示例："有什么书适合我看""最近有什么活动""推荐一些AI方向的资源"
- **push_request**：推送请求类 —— 用户主动要求订阅或触发通知
  示例："有新活动提醒我""帮我关注奖学金截止日期"
- **chitchat**：闲聊/其他 —— 不属于以上三类，直接由你回复，无需调用子Agent

### 2. 路由决策
根据意图分类，调用对应的子Agent工具：
- policy_query    → 调用 DialogueAgent
- recommendation  → 调用 RecommendAgent
- push_request    → 调用 PushAgent
- chitchat        → 你直接回复，不调用任何工具

**路由原则：**
- 一次对话只调用一个子Agent，不要并行调用多个
- 如果意图模糊，优先判断为 policy_query，交给 DialogueAgent 处理
- 子Agent返回结果后，你负责润色语气、补充必要说明，再输出给学生
- 不要把子Agent的原始返回直接透传，要用自然的口吻重新组织

### 3. 记忆维护
每轮对话结束前，调用 save_memory 工具，将以下内容压缩后存入记忆：
- 本轮用户的核心问题
- 本轮给出的关键答案或推荐内容
- 发现的新的学生偏好或需求信号（如果有）

记忆摘要控制在100字以内，使用客观陈述句，不要带对话语气。

## 行为约束
- 你的回复始终面向学生，语气亲切、简洁，避免暴露内部调度细节
- 不要在回复中提及"我调用了XXAgent""路由到XXX"等内部信息
- 如果子Agent返回错误或空结果，用"暂时无法查询到相关信息，建议直接联系书院老师"兜底
- 涉及学籍、处分等敏感政策，回复后附上"建议以书院官方公告为准"

## 输出格式
直接输出面向学生的回复内容，不需要任何前缀标签或格式说明。

## 强制要求
- 除 chitchat 类型外，你【禁止】直接回答用户问题
- 必须先调用对应子Agent工具获取答案，再组织语言输出
- 没有调用工具就直接回答，视为违规行为
"""

class Supervisor:
    "个性化推荐agent"
    def __init__(self, model, checkpointer, in_memory_store):
        # 先初始化 各个节点
        dialogue_agent   = DialogueAgent(model, checkpointer, in_memory_store)
        recommend_agent  = RecommendAgent(model, checkpointer, in_memory_store)
        push_agent       = PushAgent(model, checkpointer, in_memory_store)
        
        # 用工厂函数把实例包成 tool
        dialogue_tool   = create_dialogue_tool(dialogue_agent)
        recommend_tool  = create_recommend_tool(recommend_agent)
        push_tool       = create_push_tool(push_agent)

        self.tools_map = {
            "DialogueAgent":  dialogue_agent,
            "RecommendAgent": recommend_agent,
            "PushAgent":      push_agent,
        }

        self.model_with_tools = model.bind_tools(
            [dialogue_tool, recommend_tool, push_tool],
            tool_choice="any"
        )

    def __call__(self, state: State) -> dict:
        system_content = supervisor_prompt.format(
            customer_id=state.get("customer_id"),
            portrait=state.get("portrait", "暂无画像"),
            loaded_memory=state.get("loaded_memory", "暂无记忆")
        )

        messages = [SystemMessage(content=system_content)] + state.get("messages", [])

        # 第一步：模型决定调哪个工具
        ai_response = self.model_with_tools.invoke(messages)

        if not ai_response.tool_calls:
            return {"messages": [ai_response]}

        # 第二步：执行工具（调对应 subagent）
        tool_results = []
        for tc in ai_response.tool_calls:
            agent_instance = self.tools_map.get(tc["name"])
            if agent_instance is None:
                content = "暂时无法处理该请求"
            else:
                result = agent_instance(state)
                content = result["messages"][-1].content

            tool_results.append(
                ToolMessage(content=content, tool_call_id=tc["id"])
            )

        # 第三步：把工具结果交回模型生成最终回复
        final_messages = messages + [ai_response] + tool_results
        final_response = self.model_with_tools.invoke(final_messages)

        return {"messages": [final_response]}
