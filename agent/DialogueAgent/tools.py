from langchain_core.tools import tool

@tool
def get_policy_from_ES(query: str) -> str:
    """从ES数据库中检索政策原始文档，适合关键词匹配类查询"""
    return "【模拟ES结果】奖学金申请截止时间为每年10月31日，需提交成绩单和推荐信"

@tool
def get_graph_from_Neo4j(query: str) -> str:
    """从Neo4j知识图谱中进行多跳推理查询，适合条件关联类问题，如'满足XX条件能申请什么'"""
    return "【模拟Neo4j结果】科研项目经历 → 可申请科创类奖学金 → 需满足GPA≥3.5"

@tool
def get_policy_from_rag(query: str) -> str:
    """从向量数据库中语义检索政策文档，适合模糊语义类查询"""
    return "【模拟RAG结果】根据书院住宿管理规定第三条，学生可申请换宿"

@tool
def get_profile(customer_id: int) -> str:
    """根据学生ID从画像数据库获取该学生的兴趣标签和科研画像"""
    return f"【模拟画像】学生{customer_id}：AI爱好者 / 借阅频次高 / 参与过1项科研项目"
