```mermaid
graph TD
    subgraph "入口 (Entry Point)"
        CLI[cli.py]
    end

    subgraph "Agent 核心 (Strategy Pattern)"
        AgentFactory["agent.py (工厂)"]
        BaseAgent["base_agent.py (抽象策略)"]
        TraeAgent["trae_agent.py (具体策略)"]
    end

    subgraph "工具系统 (Command Pattern)"
        ToolInterface["tools/base.py (抽象命令)"]
        BashTool["tools/bash_tool.py (具体命令)"]
        EditTool["tools/edit_tool.py (具体命令)"]
        TaskDoneTool["tools/task_done_tool.py (具体命令)"]
        OtherTools["... (其他工具)"]
    end

    subgraph "LLM 客户端 (Abstract Factory)"
        BaseLLMClient["utils/llm_clients/base_client.py (抽象工厂)"]
        OpenAIClient["utils/llm_clients/openai_client.py (具体产品)"]
        OtherClients["... (其他客户端)"]
    end

    subgraph "配置管理 (Singleton-like)"
        Config["utils/config.py (单例配置)"]
    end

    subgraph "提示工程 (Prompt Engineering)"
        AgentPrompt["prompt/agent_prompt.py"]
    end

    %% 关系定义
    CLI -- "调用" --> AgentFactory
    AgentFactory -- "创建" --> TraeAgent
    TraeAgent -- "继承" --> BaseAgent
    TraeAgent -- "使用" --> ToolInterface
    TraeAgent -- "使用" --> BaseLLMClient
    TraeAgent -- "使用" --> AgentPrompt
    TraeAgent -- "读取" --> Config

    ToolInterface <|-- BashTool
    ToolInterface <|-- EditTool
    ToolInterface <|-- TaskDoneTool
    ToolInterface <|-- OtherTools

    BaseLLMClient <|-- OpenAIClient
    BaseLLMClient <|-- OtherClients

    AgentFactory -- "读取" --> Config
    BaseLLMClient -- "读取" --> Config
```