"""
SemanticSQL 输出解析器 - 基于官方ReAct解析器逻辑
专注SQL生成完成检测，完全基于LangChain官方API
"""

import re
from typing import Union

from langchain.agents.agent import AgentAction, AgentFinish, AgentOutputParser
from langchain_core.exceptions import OutputParserException


class SemanticSQLOutputParser(AgentOutputParser):
    """SemanticSQL解析器 - 基于官方ReActSingleInputOutputParser逻辑
    
    设计原则：
    - 官方兼容：完全基于LangChain官方ReAct格式
    - 专注业务：专门针对SQL生成任务的完成检测
    - 错误处理：提供清晰的解析失败信息
    
    解析逻辑：
    1. Final Answer: -> AgentFinish (结束执行)
    2. Action: + Action Input: -> AgentAction (继续执行)
    3. 解析失败 -> OutputParserException (异常处理)
    """
    

    def parse(self, llm_output: str) -> Union[AgentAction, AgentFinish]:
        """解析LLM输出 - 完全基于官方ReAct格式
        
        官方检测逻辑：
        1. Final Answer: -> AgentFinish (结束)
        2. Action: + Action Input: -> AgentAction (继续)
        3. 解析失败 -> OutputParserException
        
        Args:
            llm_output: LLM的原始输出文本
            
        Returns:
            AgentAction或AgentFinish实例
            
        Raises:
            OutputParserException: 解析失败时抛出
        """
        
        # 预处理：过滤掉LLM输出中的think内容
        llm_output = self._clean_think_content(llm_output)
        
        # 1. 检查是否包含 Final Answer（官方ReAct结束信号）
        if "Final Answer:" in llm_output:
            # 提取 Final Answer 之后的内容
            final_answer = llm_output.split("Final Answer:")[-1].strip()
            
            # 处理SQL生成特殊情况：检查是否包含SQL
            if self._contains_sql_result(final_answer):
                # 提取并格式化SQL结果
                formatted_result = self._format_sql_result(final_answer)
                return AgentFinish(
                    return_values={"output": formatted_result},
                    log=llm_output
                )
            
            return AgentFinish(
                return_values={"output": final_answer},
                log=llm_output
            )
        
        # 2. 检查是否包含 Action 模式（官方逻辑）
        # 使用与官方相同的正则表达式
        if not re.search(r"Action\s*\d*\s*:[\s]*(.*?)", llm_output, re.DOTALL):
            raise OutputParserException(
                f"Could not parse LLM output: `{llm_output}`"
            )
        
        # 3. 提取 Action（官方逻辑）
        action_match = re.search(
            r"Action\s*\d*\s*:(.*?)(?=\n|Action\s*\d*\s*Input\s*\d*\s*:|Observation\s*:|$)", 
            llm_output, re.DOTALL
        )
        if not action_match:
            raise OutputParserException(f"Could not parse action from: `{llm_output}`")
        
        action = action_match.group(1).strip()
        
        # 4. 提取 Action Input（修改：支持Observation作为Action Input）
        action_input = ""
        
        # 首先尝试提取 Action Input
        action_input_match = re.search(
            r"Action\s*\d*\s*Input\s*\d*\s*:(.*?)(?=\n(?:Thought|Action|Final Answer|Observation)|$)", 
            llm_output, re.DOTALL
        )
        
        if action_input_match:
            action_input = action_input_match.group(1).strip()
        else:
            # 如果没有找到Action Input，尝试找Observation
            observation_match = re.search(
                r"Observation\s*:(.*?)(?=\n(?:Thought|Action|Final Answer)|$)", 
                llm_output, re.DOTALL
            )
            
            if observation_match:
                action_input = observation_match.group(1).strip()
            else:
                # 如果既没有Action Input也没有Observation，检查是否有相应的标识符
                if "Action Input:" in llm_output:
                    raise OutputParserException(f"Could not parse action input from: `{llm_output}`")
                elif "Observation:" in llm_output:
                    raise OutputParserException(f"Could not parse observation from: `{llm_output}`")
                # 如果都没有标识符，action_input保持为空字符串
        
        # 5. 移除可能的引号（与官方逻辑一致）
        if action_input.startswith('"') and action_input.endswith('"'):
            action_input = action_input[1:-1]
        elif action_input.startswith("'") and action_input.endswith("'"):
            action_input = action_input[1:-1]
        
        # 6. 验证工具名称
        action = self._validate_tool_name(action)
        
        return AgentAction(
            tool=action,
            tool_input=action_input,
            log=llm_output
        )

    
    def _contains_sql_result(self, text: str) -> bool:
        """检查文本是否包含SQL结果
        
        Args:
            text: 待检查的文本
            
        Returns:
            是否包含SQL
        """
        sql_indicators = [
            "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER",
            "```sql", "```SQL", "sql", "SQL"
        ]
        
        text_upper = text.upper()
        return any(indicator.upper() in text_upper for indicator in sql_indicators)
    
    def _format_sql_result(self, text: str) -> str:
        """格式化SQL结果
        
        Args:
            text: 原始文本
            
        Returns:
            格式化后的SQL结果
        """
        # 提取SQL代码块
        sql_pattern = r"```(?:sql|SQL)?\s*(.*?)\s*```"
        sql_match = re.search(sql_pattern, text, re.DOTALL | re.IGNORECASE)
        
        if sql_match:
            sql_code = sql_match.group(1).strip()
            # 保持原始格式的同时添加结构化信息
            return f"生成的SQL查询：\n\n```sql\n{sql_code}\n```\n\n{text}"
        
        return text
    
    def _validate_tool_name(self, tool_name: str) -> str:
        """验证和标准化工具名称
        
        Args:
            tool_name: 原始工具名称
            
        Returns:
            标准化的工具名称
        """
        # 移除多余空格和特殊字符
        tool_name = tool_name.strip()
        
        # 处理常见的工具名称格式问题
        if not tool_name:
            raise OutputParserException("Tool name cannot be empty")
        
        # 确保工具名称符合标准格式
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", tool_name):
            # 尝试清理工具名称
            clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", tool_name)
            clean_name = re.sub(r"_+", "_", clean_name)  # 合并多个下划线
            clean_name = clean_name.strip("_")  # 移除首尾下划线
            
            if clean_name and re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", clean_name):
                return clean_name
            
            raise OutputParserException(f"Invalid tool name format: {tool_name}")
        
        return tool_name
    
    def get_format_instructions(self) -> str:
        """获取格式化指令 - 与官方ReAct格式兼容
        
        Returns:
            格式化指令字符串
        """
        return """请按照以下格式回答：

Thought: 你应该始终思考要做什么
Action: 要采取的动作，应该是工具列表中的一个工具名称
Action Input: 动作的输入
Observation: 动作的结果
... (这个 Thought/Action/Action Input/Observation 可以重复N次)
Thought: 我现在知道最终答案了
Final Answer: 给用户的最终答案

注意：
- Action必须是提供的工具列表中的确切工具名称
- Action Input应该是工具需要的输入参数
- 当生成SQL时，请在Final Answer中提供清晰的SQL代码块
"""
    
    def _clean_think_content(self, text: str) -> str:
        """清理文本中的think内容
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        import re
        
        if not isinstance(text, str):
            return text
        
        # 1. 过滤 <think>...</think> 标签及其内容
        cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # 2. 过滤其他think变种标签
        cleaned_text = re.sub(r'<thought>.*?</thought>', '', cleaned_text, flags=re.DOTALL)
        
        # 3. 过滤详细的中文分析内容，保留标准ReAct格式
        lines = cleaned_text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            # 跳过过长的中文分析行（非标准ReAct格式）
            if (line.startswith('Thought:') and 
                len(line) > 100 and 
                '工具' in line and 
                'Action' not in line):
                # 替换为简化版本
                filtered_lines.append('Thought: 分析问题并选择合适的工具')
            elif line:
                filtered_lines.append(line)
        
        # 4. 清理多余的空行
        result = '\n'.join(filtered_lines)
        result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)  # 最多保留一个空行
        
        return result.strip()
    
    @property
    def _type(self) -> str:
        """解析器类型标识"""
        return "semantic_sql_react_parser"


def create_semantic_sql_parser() -> SemanticSQLOutputParser:
    """创建SemanticSQL解析器的便利函数
    
    Returns:
        配置好的SemanticSQLOutputParser实例
    """
    return SemanticSQLOutputParser()


def validate_llm_output(output: str) -> bool:
    """验证LLM输出格式是否符合ReAct要求
    
    Args:
        output: LLM输出文本
        
    Returns:
        输出格式是否有效
    """
    if not output or not isinstance(output, str):
        return False
    
    # 检查是否包含必要的ReAct元素
    has_final_answer = "Final Answer:" in output
    has_action = re.search(r"Action\s*\d*\s*:", output)
    has_thought = "Thought:" in output
    
    # 至少要有Final Answer或Action之一
    return has_final_answer or has_action


def extract_sql_from_output(output: str) -> str:
    """从输出中提取SQL代码
    
    Args:
        output: 包含SQL的文本
        
    Returns:
        提取的SQL代码，如果没有找到返回空字符串
    """
    # 尝试从代码块中提取
    sql_pattern = r"```(?:sql|SQL)?\s*(.*?)\s*```"
    sql_match = re.search(sql_pattern, output, re.DOTALL | re.IGNORECASE)
    
    if sql_match:
        return sql_match.group(1).strip()
    
    # 尝试从Final Answer中提取
    if "Final Answer:" in output:
        final_answer = output.split("Final Answer:")[-1].strip()
        sql_match = re.search(sql_pattern, final_answer, re.DOTALL | re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
    
    return ""