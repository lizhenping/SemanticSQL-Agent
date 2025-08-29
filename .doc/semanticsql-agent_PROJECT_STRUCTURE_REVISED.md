# SemanticSQL Agent 项目结构设计（修订版）

## 1. 核心设计理念调整

### 1.1 工具命名规范
- 所有工具类必须以 `Tool` 结尾
- 文件名必须以 `_tool.py` 结尾
- 保持命名一致性

### 1.2 生成流程明确
1. 场景生成（ScenarioTool）
2. 操作选择（OperationTool）
3. 问题生成（QuestionTool）
4. SQL生成（SQLGenerationTool）

### 1.3 执行记录位置
- 在 Agent 层记录执行轨迹
- 工具只负责具体功能，不记录执行历史
- 使用 AgentExecution 统一管理

### 1.4 简化设计
- 去除过度设计的部分
- 保持简洁实用

## 2. 优化后的项目结构

```
semanticsql-agent/
├── README.md
├── setup.py
├── requirements.txt
├── .env.example
├── .gitignore
│
├── config/
│   ├── __init__.py
│   ├── settings.py              # 统一配置管理
│   └── config.yaml             # 默认配置文件
│
├── core/
│   ├── __init__.py
│   ├── models.py               # 所有数据模型
│   ├── exceptions.py           # 自定义异常
│   └── constants.py            # 常量定义
│
├── agent/
│   ├── __init__.py
│   ├── base_agent.py           # 基础Agent（含执行记录）
│   ├── smart_sql_agent.py      # SQL数据生成Agent
│   └── execution_tracker.py    # 执行轨迹记录器
│
├── tools/
│   ├── __init__.py
│   ├── base_tool.py            # 工具基类
│   │
│   ├── analysis/               # 分析工具
│   │   ├── __init__.py
│   │   ├── schema_extraction_tool.py   # 数据库结构提取
│   │   ├── domain_analysis_tool.py     # 领域分析
│   │   ├── field_classification_tool.py # 字段分类
│   │   └── er_analysis_tool.py         # 关系分析
│   │
│   ├── generation/             # 生成工具
│   │   ├── __init__.py
│   │   ├── scenario_tool.py           # 场景生成
│   │   ├── operation_selection_tool.py # 操作选择
│   │   ├── question_generation_tool.py # 问题生成
│   │   └── sql_generation_tool.py     # SQL生成
│   │
│   ├── validation/             # 验证执行工具
│   │   ├── __init__.py
│   │   ├── sql_validation_tool.py     # SQL语法验证
│   │   └── sql_execution_tool.py      # SQL执行测试
│   │
│   └── reflection/             # 反思优化工具
│       ├── __init__.py
│       └── sql_reflection_tool.py      # SQL执行反思与优化
│
├── prompts/
│   ├── __init__.py
│   ├── system_prompt.yaml      # 系统提示词
│   ├── tool_prompts.yaml       # 工具提示词
│   └── prompt_manager.py       # 提示词管理器
│
├── utils/
│   ├── __init__.py
│   ├── database.py             # 数据库连接工具
│   ├── llm_client.py           # LLM客户端（支持Qwen）
│   ├── logger.py               # 日志配置
│   └── helpers.py              # 辅助函数
│
├── cli/
│   ├── __init__.py
│   └── cli.py                  # 命令行接口
│
├── output/                     # 输出目录（运行时生成）
│   └── .gitkeep
│
├── tests/
│   ├── __init__.py
│   ├── test_tools/             # 工具测试
│   ├── test_agent/             # 智能体测试
│   └── test_integration.py     # 集成测试
│
└── examples/
    ├── __init__.py
    ├── basic_usage.py          # 基础示例
    └── custom_tool.py          # 自定义工具示例
```

## 3. 核心组件详解

### 3.1 执行记录设计

```python
# agent/execution_tracker.py
class ExecutionTracker:
    """执行轨迹记录器"""
    
    def __init__(self):
        self.steps = []
        self.start_time = None
        self.end_time = None
        
    def record_step(self, step_type: str, content: str, 
                   tool_name: str = None, result: Any = None):
        """记录执行步骤"""
        step = {
            "timestamp": datetime.now(),
            "type": step_type,
            "content": content,
            "tool": tool_name,
            "result": result
        }
        self.steps.append(step)
        
    def get_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        return {
            "total_steps": len(self.steps),
            "duration": (self.end_time - self.start_time).seconds,
            "tools_used": list(set(s["tool"] for s in self.steps if s["tool"])),
            "success": all(s.get("result", {}).get("success", True) for s in self.steps)
        }
```

### 3.2 工具基类优化

```python
# tools/base_tool.py
class BaseTool(ABC):
    """工具基类 - 简化版"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        返回格式：
        {
            "success": bool,
            "data": Any,
            "error": Optional[str]
        }
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """获取Function Calling schema"""
        # 自动从run方法的参数生成schema
        pass
```

### 3.3 生成流程工具

```python
# tools/generation/scenario_tool.py
class ScenarioTool(BaseTool):
    """场景生成工具"""
    
    @property
    def name(self) -> str:
        return "scenario_generator"
    
    @property
    def description(self) -> str:
        return "基于数据库结构和领域生成业务场景"
    
    def run(self, schema_info: Dict, domain_info: Dict) -> Dict[str, Any]:
        """生成业务场景"""
        scenarios = []
        
        # 基于规则生成不同类型的场景
        scenarios.extend(self._generate_basic_scenarios(schema_info))
        scenarios.extend(self._generate_domain_scenarios(domain_info))
        scenarios.extend(self._generate_complex_scenarios(schema_info))
        
        return {
            "success": True,
            "data": {
                "scenarios": scenarios,
                "count": len(scenarios)
            }
        }

# tools/generation/operation_selection_tool.py
class OperationSelectionTool(BaseTool):
    """操作选择工具"""
    
    @property
    def name(self) -> str:
        return "operation_selector"
    
    @property
    def description(self) -> str:
        return "为每个场景选择合适的SQL操作类型"
    
    def run(self, scenarios: List[Dict]) -> Dict[str, Any]:
        """为场景选择操作"""
        operations = []
        
        for scenario in scenarios:
            ops = self._select_operations(scenario)
            operations.append({
                "scenario_id": scenario["id"],
                "operations": ops
            })
        
        return {
            "success": True,
            "data": {"operations": operations}
        }

# tools/generation/question_generation_tool.py
class QuestionGenerationTool(BaseTool):
    """问题生成工具"""
    
    @property
    def name(self) -> str:
        return "question_generator"
    
    @property
    def description(self) -> str:
        return "基于场景和操作生成自然语言问题"
    
    def run(self, scenarios: List[Dict], operations: List[Dict]) -> Dict[str, Any]:
        """生成自然语言问题"""
        questions = []
        
        for scenario, ops in zip(scenarios, operations):
            scenario_questions = self._generate_questions(scenario, ops)
            questions.extend(scenario_questions)
        
        return {
            "success": True,
            "data": {"questions": questions}
        }
```

### 3.4 反思工具简化

```python
# tools/reflection/sql_reflection_tool.py
class SQLReflectionTool(BaseTool):
    """SQL反思优化工具 - 统一处理执行分析和质量改进"""
    
    @property
    def name(self) -> str:
        return "sql_reflector"
    
    @property
    def description(self) -> str:
        return "分析SQL执行结果并提供优化建议"
    
    def run(self, sql: str, execution_result: Dict, 
            schema_info: Dict) -> Dict[str, Any]:
        """反思SQL执行并提供改进"""
        
        analysis = {
            "execution_analysis": self._analyze_execution(execution_result),
            "quality_score": self._calculate_quality_score(sql, execution_result),
            "optimization_suggestions": self._suggest_optimizations(sql, schema_info),
            "improved_sql": None
        }
        
        # 如果需要改进，生成优化后的SQL
        if analysis["quality_score"] < 0.8:
            analysis["improved_sql"] = self._improve_sql(sql, analysis["optimization_suggestions"])
        
        return {
            "success": True,
            "data": analysis
        }
```

### 3.5 智能体中的执行记录

```python
# agent/base_agent.py
class BaseAgent(ABC):
    """基础智能体 - 包含执行记录"""
    
    def __init__(self, config: Config):
        self.config = config
        self.llm_client = self._create_llm_client()
        self.tools = {}
        self.execution_tracker = ExecutionTracker()
    
    def run(self, task: str, context: Dict = None) -> AgentExecution:
        """执行任务并记录轨迹"""
        self.execution_tracker.start()
        
        try:
            # ReAct循环
            while not self._is_complete():
                # Think
                thought = self._think(context)
                self.execution_tracker.record_step("thought", thought)
                
                # Act
                action = self._decide_action(thought)
                self.execution_tracker.record_step("action", f"Using {action['tool']}")
                
                # Execute
                result = self._execute_tool(action)
                self.execution_tracker.record_step(
                    "observation", 
                    str(result),
                    tool_name=action['tool'],
                    result=result
                )
                
                # Update context
                context = self._update_context(context, result)
        
        finally:
            self.execution_tracker.end()
            
        return self._build_execution_result()
```

## 4. 简化的输出处理

```python
# utils/output_handler.py
class OutputHandler:
    """统一的输出处理器"""
    
    @staticmethod
    def save_dataset(dataset: Dict, output_path: str, format: str = "json"):
        """保存数据集"""
        if format == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=2)
        elif format == "jsonl":
            with open(output_path, "w", encoding="utf-8") as f:
                for example in dataset["examples"]:
                    f.write(json.dumps(example, ensure_ascii=False) + "\n")
        elif format == "csv":
            # CSV导出逻辑
            pass
    
    @staticmethod
    def format_for_training(dataset: Dict, target: str = "default") -> Dict:
        """格式化为训练格式"""
        if target == "huggingface":
            return {
                "dataset": [
                    {
                        "instruction": ex["question"],
                        "input": "",
                        "output": ex["sql"]
                    }
                    for ex in dataset["examples"]
                ]
            }
        return dataset
```

## 5. 关键改进总结

### 5.1 命名规范统一
- 所有工具文件以 `_tool.py` 结尾
- 工具类以 `Tool` 结尾
- 保持一致性

### 5.2 生成流程清晰
1. 场景生成 → 2. 操作选择 → 3. 问题生成 → 4. SQL生成
- 每个步骤职责明确
- 流程可追踪

### 5.3 执行记录集中
- 在Agent层统一记录
- 工具专注于功能实现
- 使用ExecutionTracker管理

### 5.4 设计简化
- 合并相似功能（如反思工具）
- 去除过度设计的适配器
- 保持实用性

### 5.5 输出处理简化
- 使用简单的工具函数
- 支持基本格式转换
- 避免过度抽象

这个修订后的结构更加清晰、实用，避免了过度设计，同时保持了良好的扩展性。