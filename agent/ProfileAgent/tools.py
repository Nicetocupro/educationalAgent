from langchain_core.tools import tool

@tool
def get_portrait_from_db(customer_id: int) -> str:
    """
    根据学生ID从画像数据库中查询用户画像标签。
    返回画像字符串，供后续Agent使用。
    """
    # 壳子：模拟从 MySQL 画像数据库查询
    mock_portraits = {
        1: "兴趣领域:人工智能,借阅偏好:技术类书籍,科研状态:参与中,活跃度:高",
        2: "兴趣领域:文史哲,借阅偏好:人文类书籍,科研状态:未参与,活跃度:中",
    }
    portrait = mock_portraits.get(customer_id, "暂无画像数据")
    return portrait