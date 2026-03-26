from langchain_core.tools import tool

@tool
def push_notification(customer_id: int, notification_type: str, content: str) -> str:
    """
    向学生发送主动推送通知。
    notification_type 可选值:
      - policy_reminder: 政策截止提醒（如奖学金申报即将截止）
      - resource_match: 资源匹配推送（如新讲座、科创活动）
      - growth_guide: 成长引导推送（如长期无借阅记录时推送阅读推荐）
    """
    print(f"【模拟推送】→ 学生{customer_id} | 类型: {notification_type} | 内容: {content}")
    return f"推送成功：已向学生{customer_id}发送{notification_type}类通知"