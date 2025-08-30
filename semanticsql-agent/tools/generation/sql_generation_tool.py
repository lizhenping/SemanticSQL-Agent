"""
SQL生成工具 - 根据问题生成SQL查询
"""

from typing import Dict, Any, List, Optional
from openai import OpenAI
import re

from tools.base_tool import BaseTool, ToolParameter
from core.models import SQLOperation
from core.exceptions import LLMError, GenerationError


class SQLGenerationTool(BaseTool):
    """生成SQL查询语句"""
    
    def __init__(self, config: Any):
        super().__init__(config)
        # 初始化LLM客户端
        self.llm_client = OpenAI(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key
        )
        self.model = config.llm.model
        self.temperature = 0.1  # SQL生成使用低温度
    
    @property
    def name(self) -> str:
        return "generate_sql"
    
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
    
    def _execute(self, question: str, schema_info: Dict[str, Any],
                 operations: List[str] = None, dialect: str = "mysql",
                 use_llm: bool = True) -> Dict[str, Any]:
        """
        生成SQL查询
        
        Returns:
            包含SQL和元数据的字典
        """
        if use_llm and self.llm_client:
            sql = self._generate_with_llm(question, schema_info, operations, dialect)
        else:
            sql = self._generate_with_rules(question, schema_info, operations, dialect)
        
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
            self.logger.warning(f"LLM SQL generation failed: {e}")
            return self._generate_with_rules(question, schema_info, operations, dialect)
    
    def _generate_with_rules(self, question: str, schema_info: Dict[str, Any],
                            operations: List[str] = None, dialect: str = "mysql") -> str:
        """基于规则生成SQL"""
        # 分析问题意图
        intent = self._analyze_question_intent(question)
        
        # 识别相关表
        tables = self._identify_tables(question, schema_info)
        
        # 识别字段
        columns = self._identify_columns(question, schema_info, tables)
        
        # 识别条件
        conditions = self._identify_conditions(question)
        
        # 构建SQL
        sql = self._build_sql_from_components(
            intent, tables, columns, conditions, operations, dialect
        )
        
        return sql
    
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
                col_desc = f"  - {col['name']} ({col['data_type']})"
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
    
    def _analyze_question_intent(self, question: str) -> str:
        """分析问题意图"""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ["统计", "计算", "总数", "平均", "最大", "最小"]):
            return "aggregation"
        elif any(word in question_lower for word in ["排名", "前几", "最高", "最低"]):
            return "ranking"
        elif any(word in question_lower for word in ["关联", "对应", "相关"]):
            return "join"
        else:
            return "simple_select"
    
    def _identify_tables(self, question: str, schema_info: Dict[str, Any]) -> List[str]:
        """识别相关表"""
        tables = []
        question_lower = question.lower()
        
        # 表名映射
        table_keywords = {
            "用户": ["user", "customer", "member"],
            "订单": ["order", "purchase"],
            "产品": ["product", "item", "goods"],
            "员工": ["employee", "staff"]
        }
        
        for keyword, table_patterns in table_keywords.items():
            if keyword in question:
                for table_name in schema_info.get("tables", {}).keys():
                    if any(pattern in table_name.lower() for pattern in table_patterns):
                        tables.append(table_name)
        
        # 如果没找到，返回第一个表
        if not tables and schema_info.get("tables"):
            tables.append(list(schema_info["tables"].keys())[0])
        
        return list(set(tables))
    
    def _identify_columns(self, question: str, schema_info: Dict[str, Any],
                         tables: List[str]) -> List[str]:
        """识别相关字段"""
        columns = []
        
        # 常见字段映射
        column_keywords = {
            "名称": ["name", "title"],
            "数量": ["quantity", "count", "amount"],
            "价格": ["price", "cost"],
            "时间": ["date", "time", "created_at"],
            "状态": ["status", "state"]
        }
        
        for keyword, col_patterns in column_keywords.items():
            if keyword in question:
                for table in tables:
                    if table in schema_info.get("tables", {}):
                        for col in schema_info["tables"][table].get("columns", []):
                            if any(pattern in col["name"].lower() for pattern in col_patterns):
                                columns.append(f"{table}.{col['name']}")
        
        # 如果没找到，使用*
        if not columns:
            columns = ["*"]
        
        return columns
    
    def _identify_conditions(self, question: str) -> List[str]:
        """识别查询条件"""
        conditions = []
        
        # 时间条件
        if "本月" in question:
            conditions.append("DATE_FORMAT(date_column, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')")
        elif "今年" in question:
            conditions.append("YEAR(date_column) = YEAR(NOW())")
        
        # 状态条件
        if "有效" in question:
            conditions.append("status = 'active'")
        
        # 数值条件
        import re
        numbers = re.findall(r'\d+', question)
        if numbers and any(word in question for word in ["大于", "超过"]):
            conditions.append(f"amount > {numbers[0]}")
        
        return conditions
    
    def _build_sql_from_components(self, intent: str, tables: List[str],
                                  columns: List[str], conditions: List[str],
                                  operations: List[str] = None, dialect: str = "mysql") -> str:
        """从组件构建SQL"""
        if intent == "aggregation":
            # 聚合查询
            sql = f"SELECT COUNT(*) as total, AVG(amount) as avg_amount\n"
        else:
            # 普通查询
            sql = f"SELECT {', '.join(columns)}\n"
        
        sql += f"FROM {tables[0]}\n"
        
        # 添加JOIN
        if len(tables) > 1:
            for table in tables[1:]:
                sql += f"JOIN {table} ON {tables[0]}.id = {table}.{tables[0]}_id\n"
        
        # 添加WHERE条件
        if conditions:
            sql += f"WHERE {' AND '.join(conditions)}\n"
        
        # 添加GROUP BY（如果是聚合）
        if intent == "aggregation" and "GROUP" in (operations or []):
            sql += "GROUP BY category\n"
        
        # 添加ORDER BY
        if intent == "ranking":
            sql += "ORDER BY amount DESC\nLIMIT 10\n"
        
        return sql.strip() + ";"
    
    def _postprocess_sql(self, sql: str, dialect: str) -> str:
        """后处理SQL"""
        # 格式化SQL
        sql = sql.strip()
        
        # 确保有分号
        if not sql.endswith(';'):
            sql += ';'
        
        # 根据方言调整
        if dialect == "postgresql":
            sql = sql.replace("DATE_FORMAT", "TO_CHAR")
        elif dialect == "sqlite":
            sql = sql.replace("DATE_FORMAT", "strftime")
        
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