"""
智能体状态管理 - 极简设计
基于设计文档的完全重构：只有2个字段的极简状态
"""

from typing import Dict, Any, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """智能体状态 - 极简设计
    
    设计原则：
    - 极简原则：只有2个核心字段，去除所有复杂状态管理
    - 无状态化：状态只用于传递必要参数，不存储业务逻辑
    - 类型安全：使用TypedDict确保类型检查
    
    状态字段：
    - current_input: 用户当前输入的查询或任务描述
    - database_params: 数据库连接参数，包含连接信息和配置
    
    注意：
    所有业务状态都通过Neo4j记忆系统在工具间传递，
    Agent状态只负责传递运行时必需的基础参数
    """
    current_input: str                        # 用户输入
    database_params: Optional[Dict[str, Any]] # 数据库连接参数


def create_agent_state(
    user_input: str,
    database_params: Optional[Dict[str, Any]] = None
) -> AgentState:
    """创建智能体状态的便利函数
    
    Args:
        user_input: 用户输入文本
        database_params: 数据库参数字典，可选
        
    Returns:
        标准化的AgentState实例
    """
    return AgentState(
        current_input=user_input,
        database_params=database_params or {}
    )


def validate_agent_state(state: AgentState) -> bool:
    """验证智能体状态的有效性
    
    Args:
        state: 待验证的状态
        
    Returns:
        状态是否有效
    """
    if not isinstance(state, dict):
        return False
    
    # 检查必需字段
    if "current_input" not in state:
        return False
    
    if not state["current_input"] or not isinstance(state["current_input"], str):
        return False
    
    # 检查可选字段类型
    if "database_params" in state:
        if state["database_params"] is not None and not isinstance(state["database_params"], dict):
            return False
    
    return True


def extract_database_info(state: AgentState) -> Dict[str, Any]:
    """从状态中提取数据库信息
    
    Args:
        state: 智能体状态
        
    Returns:
        数据库信息字典
    """
    db_params = state.get("database_params", {})
    if not db_params:
        return {
            "database": "unknown",
            "host": "localhost",
            "port": 3306,
            "user": "root"
        }
    
    return {
        "database": db_params.get("database", "unknown"),
        "host": db_params.get("host", "localhost"),
        "port": db_params.get("port", 3306),
        "user": db_params.get("user", "root"),
        "password": db_params.get("password", ""),
        "charset": db_params.get("charset", "utf8mb4")
    }


def get_current_input(state: AgentState) -> str:
    """获取当前用户输入
    
    Args:
        state: 智能体状态
        
    Returns:
        用户输入字符串
    """
    return state.get("current_input", "")


def update_state_input(state: AgentState, new_input: str) -> AgentState:
    """更新状态中的用户输入
    
    Args:
        state: 原始状态
        new_input: 新的用户输入
        
    Returns:
        更新后的状态
    """
    return AgentState(
        current_input=new_input,
        database_params=state.get("database_params")
    )