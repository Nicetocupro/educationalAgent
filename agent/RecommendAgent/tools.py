from langchain_core.tools import tool
from typing import Union

@tool
def recommendation_engine(portrait_tags: Union[str, list], recommendation_type: str) -> str:
    """
    根据学生画像标签和推荐类型，返回个性化推荐列表。
    portrait_tags: 画像标签，字符串或列表均可
    recommendation_type 可选值: book / activity / scholarship / mentor
    """
    # 统一转成字符串处理
    if isinstance(portrait_tags, list):
        portrait_tags = ", ".join(portrait_tags)

    mock_data = {
        "book": "《机器学习》周志华 / 《深度学习》花书",
        "activity": "第十二届全国大学生创新创业大赛（截止4月30日）",
        "scholarship": "国家励志奖学金（适合有科研项目经历的同学）",
        "mentor": "张XX教授 - 人工智能方向，招募大二以上本科生"
    }
    return mock_data.get(recommendation_type, "暂无匹配推荐资源")