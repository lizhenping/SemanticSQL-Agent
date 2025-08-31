"""
SQL生成工具 - 根据问题生成SQL查询
"""

from typing import Dict, Any, List, Optional
from openai import OpenAI
import re

from tools.base_tool import BaseTool, ToolParameter
from models.schemas import SQLOperation
from models.exceptions import LLMError, GenerationError
from config.settings import Settings


class SQLGenerationTool(BaseTool):
    """生成SQL查询语句"""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        # 初始化LLM客户端
        self.llm_client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key
        )
        self.model = settings.llm_model
        self.temperature = 0.1  # SQL生成使用低温度
    
    @property
    def name(self) -> str:
        return "sql_generation"
    
    @property
    def description(self) -> str:
        return "根据自然语言问题生成对应的SQL查询"
    
    @property
    def category(self) -> str:
        return "generation"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="question",
                type="string",
                description="自然语言问题",
                required=True
            ),
            ToolParameter(
                name="schema_info",
                type="object",
                description="数据库结构信息",
                required=True
            ),
            ToolParameter(
                name="operations",
                type="array",
                description="期望的SQL操作",
                required=False,
                default=[]
            ),
            ToolParameter(
                name="dialect",
                type="string",
                description="SQL方言",
                required=False,
                enum=["mysql", "postgresql", "sqlite"],
                default="mysql"
            ),
            ToolParameter(
                name="use_llm",
                type="boolean",
                description="是否使用LLM",
                required=False,
                default=True
            )
        ]
    
    def _execute(self, question: str, schema_info: Any,
                 operations: List[str] = None, dialect: str = "mysql",
                 use_llm: bool = True) -> Dict[str, Any]:
        """
        生成SQL查询
        
        Returns:
            包含SQL和元数据的字典
        """
        # 转换schema_info为字典格式
        if isinstance(schema_info, str):
            # 如果是字符串，解析为简单的表信息
            schema_dict = self._parse_schema_string(schema_info)
        elif isinstance(schema_info, dict):
            schema_dict = schema_info
        else:
            raise ValueError(f"Unsupported schema_info type: {type(schema_info)}")
        
        # 只使用LLM生成，不使用规则降级
        if not (use_llm and self.llm_client):
            raise GenerationError("LLM生成被禁用，无法生成SQL")
            
        sql = self._generate_with_llm(question, schema_dict, operations, dialect)
        
        # 后处理
        sql = self._postprocess_sql(sql, dialect)
        
        # 分析SQL
        analysis = self._analyze_sql(sql)
        
        return {
            "sql": sql,
            "dialect": dialect,
            "tables_used": analysis["tables"],
            "operations_used": analysis["operations"],
            "has_aggregation": analysis["has_aggregation"],
            "has_join": analysis["has_join"],
            "complexity": self._estimate_complexity(analysis)
        }
    
    def _generate_with_llm(self, question: str, schema_info: Dict[str, Any],
                          operations: List[str] = None, dialect: str = "mysql") -> str:
        """使用LLM生成SQL"""
        try:
            prompt = self._build_sql_prompt(question, schema_info, operations, dialect)
            
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(dialect)},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=500
            )
            
            sql = response.choices[0].message.content.strip()
            
            # 提取SQL语句
            sql = self._extract_sql_from_response(sql)
            
            return sql
            
        except Exception as e:
            self.logger.error(f"LLM SQL generation failed: {e}")
            raise GenerationError(f"LLM SQL生成失败: {e}")
    
    def _parse_schema_string(self, schema_string: str) -> Dict[str, Any]:
        """解析schema字符串为字典格式"""
        # 从字符串中提取表信息
        tables = {}
        
        # 简单解析："aid_info表包含id, amount, aid_type等字段"
        import re
        table_match = re.search(r'(\w+)表', schema_string)
        if table_match:
            table_name = table_match.group(1)
            
            # 提取字段名
            fields_match = re.search(r'包含([^等]+)', schema_string)
            if fields_match:
                fields_str = fields_match.group(1)
                columns = []
                for field in re.split(r'[,，\s]+', fields_str.strip()):
                    field = field.strip()
                    if field:
                        columns.append({
                            "name": field,
                            "type": "VARCHAR",
                            "is_primary": field == "id"
                        })
                
                tables[table_name] = {
                    "columns": columns
                }
        
        return {"tables": tables}
    
    def _build_sql_prompt(self, question: str, schema_info: Dict[str, Any],
                         operations: List[str] = None, dialect: str = "mysql") -> str:
        """构建SQL生成提示词"""
        prompt = f"""将以下自然语言问题转换为{dialect} SQL查询：

问题：{question}

数据库结构：
"""
        
        # 添加表结构信息
        for table_name, table_info in schema_info.get("tables", {}).items():
            prompt += f"\n表名：{table_name}\n字段：\n"
            for col in table_info.get("columns", [])[:15]:  # 限制字段数量
                col_type = col.get('type', col.get('data_type', 'unknown'))
                col_desc = f"  - {col['name']} ({col_type})"
                if col.get("is_primary"):
                    col_desc += " PRIMARY KEY"
                if col.get("is_foreign"):
                    col_desc += " FOREIGN KEY"
                prompt += col_desc + "\n"
        
        if operations:
            prompt += f"\n期望的SQL操作：{', '.join(operations)}\n"
        
        prompt += """
要求：
1. 只返回SQL语句，不要有其他解释
2. SQL语句要符合语法规范
3. 使用合适的表和字段名
4. 考虑性能优化

SQL查询："""
        
        return prompt
    
    def _get_system_prompt(self, dialect: str) -> str:
        """获取系统提示词"""
        return f"""你是一个{dialect}数据库专家，擅长将自然语言问题转换为高效的SQL查询。
你生成的SQL要：
1. 语法正确
2. 性能优化
3. 结果准确
4. 符合{dialect}方言特性
只返回SQL语句，不要包含解释或其他内容。"""
    
    def _extract_sql_from_response(self, response: str) -> str:
        """从响应中提取SQL"""
        # 移除markdown代码块标记
        sql = re.sub(r'```sql?\s*\n?', '', response)
        sql = re.sub(r'```\s*$', '', sql)
        
        # 移除前后空白
        sql = sql.strip()
        
        # 如果没有分号，添加分号
        if sql and not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    
    def _postprocess_sql(self, sql: str, dialect: str) -> str:
        """后处理SQL"""
        # 格式化SQL
        sql = sql.strip()
        
        # 确保有分号
        if not sql.endswith(';'):
            sql += ';'
        
        return sql
    
    def _analyze_sql(self, sql: str) -> Dict[str, Any]:
        """分析SQL语句"""
        sql_upper = sql.upper()
        
        # 提取表名
        tables = []
        from_match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if from_match:
            tables.append(from_match.group(1))
        
        join_matches = re.findall(r'JOIN\s+(\w+)', sql, re.IGNORECASE)
        tables.extend(join_matches)
        
        # 识别操作
        operations = []
        if 'SELECT' in sql_upper:
            operations.append('SELECT')
        if 'JOIN' in sql_upper:
            operations.append('JOIN')
        if 'GROUP BY' in sql_upper:
            operations.append('GROUP')
        if 'ORDER BY' in sql_upper:
            operations.append('ORDER')
        
        return {
            "tables": tables,
            "operations": operations,
            "has_aggregation": any(func in sql_upper for func in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']),
            "has_join": 'JOIN' in sql_upper,
            "has_subquery": '(SELECT' in sql_upper.replace(' ', '')
        }
    
    def _estimate_complexity(self, analysis: Dict[str, Any]) -> str:
        """估算SQL复杂度"""
        score = 0
        
        score += len(analysis["tables"])
        score += len(analysis["operations"])
        
        if analysis["has_aggregation"]:
            score += 2
        if analysis["has_join"]:
            score += 2
        if analysis["has_subquery"]:
            score += 3
        
        if score <= 3:
            return "simple"
        elif score <= 6:
            return "medium"
        else:
            return "complex"