# 图谱作为存储仓库 - 允许三元组 object 为 JSON/任意结构：变更清单（供确认）

本清单围绕“将图谱作为存储仓库，允许三元组 object 承载 JSON/任意结构”的决策，汇总需要修改的冲突点、影响面与最小改动实施计划，便于你逐项确认后推进实现。

---

## 1. 决策与目标
- 决策：允许知识图谱三元组的 object 字段存放非原子值（JSON/任意嵌套结构），并以此作为通用数据落盘形态。
- 目标：
  - 在不破坏现有字符串/标量 object 读写能力的前提下，扩展为“标量 + JSON”双形态，并保持对上层 Agent/Tool 的易用性。
  - 提供可查询、可索引、可管控（体积/权限/TTL）的最小能力闭环。
- 非目标：
  - 不要求在首发版就提供复杂 JSON Schema 校验与强一致事务；先保证“能存、能查、能控”。

---

## 2. 影响范围（模块级）
- 数据模型与存储抽象：三元组结构、底层 GraphStore/DB 适配层。
- 查询与索引：基于 predicate 与 JSON-Path 的轻量查询、必要索引策略。
- 工具基类 I/O 契约：工具产出/消费的图写入 payload 结构。
- 记忆层与轨迹：统一写入出口、避免工具直写存储；轨迹中对大 JSON 的可观测折叠与脱敏。
- Agent/Parser 与 Prompt：默认不对 JSON 内容做 thinking/validation，只做大小/安全检查。
- 测试与迁移：单元测试、兼容性与数据迁移脚本。

---

## 3. 需要修改的冲突与一致性要求（逐条）
1) 三元组数据模型仅支持标量的限制
- 冲突：当前模型默认 object 为字符串/标量，无法表达结构化对象。
- 修改：为三元组新增类型标记与 JSON 存储位。
  - 字段建议：object_kind ∈ {text, json}；object_text（可空）；object_json（可空）。
  - 兼容：保留原有 object_text 读写路径，新增 JSON 分支，不影响历史数据。

2) 存储抽象（GraphStore）能力不足
- 冲突：现有存储接口未区分 object 的类型，也未暴露 JSON Path 等查询能力。
- 修改：扩展接口以支持：
  - upsert_triple(subject, predicate, object, object_kind, ...)
  - get_triples(filter: subject/predicate/object_kind/object_size_range)
  - query_by_json_path(subject?, predicate, json_path, value_predicate)

3) 查询与索引策略缺失
- 冲突：缺少对 JSON 内容的可用查询路径与性能保障。
- 修改：
  - 规则：仅对“特定 predicate 白名单 + 常用 JSON-Path”提供查询与索引；其余走原始扫描或上层过滤。
  - 指标：限制 object_json 的最大体积（如 64KB/256KB，待确认），大对象仅允许通过对象 ID/引用查回。

4) 工具基类 I/O 契约未覆盖 JSON 写入
- 冲突：工具目前多以标量输出，未提供结构化入图约定。
- 修改：规范工具返回值中可包含 graph_upserts 数组：每项包含 subject、predicate、object_kind、object_text/object_json、meta（source/tool/version/ttl）。

5) 记忆与轨迹的写入路径分散
- 冲突：工具可能绕过记忆层直写存储，且轨迹对大 JSON 可观测性不足。
- 修改：
  - 强制通过 Memory/Graph 写入网关进行统一落盘与审计；禁止工具直连 DB。
  - 轨迹（trajectory）中对超阈值 JSON 进行折叠显示与哈希标识；支持脱敏字段表。

6) Agent/Parser 与 Prompt 的处理策略
- 冲突：历史默认做严格 parsing/validation；对 JSON 大对象不经济。
- 修改：
  - 与“这里不需要validation/thinking”的共识对齐：对 JSON 内容不做语义校验/推理，仅做大小/安全检查。
  - Prompt 中避免把大 JSON 直接回显到模型上下文，默认以摘要/字段片段呈现。

7) 迁移与兼容
- 冲突：老数据只有 object_text。
- 修改：不强制迁移；按需惰性升级。新增读写接口向后兼容（若 object_kind 为空，按 text 处理）。

---

## 4. 最小改动实施计划（建议按 PR 拆分）
- PR1 数据模型+存储接口
  - 增加三元组字段 object_kind/object_json（或等效映射）。
  - 扩展 GraphStore/DAO：upsert_triple、get_triples、query_by_json_path。
  - 基础体积限制与白名单配置（predicate -> 允许 JSON/最大体积/索引路径）。

- PR2 记忆层与工具基类
  - Memory 层新增 graph_write/graph_read 统一出入口，接入审计与折叠策略。
  - 工具基类支持返回 graph_upserts；示例工具对齐新契约。

- PR3 Agent/Parser/Prompt
  - Parser 跳过对 JSON 内容的语义校验，仅做大小/安全检查。
  - Prompt 调整：展示 JSON 摘要而非全量；提供“需要详情再取”的操作手柄。

- PR4 查询与索引
  - 针对白名单 predicate 建立必要索引/物化视图（视底层引擎）。
  - 提供 JSON Path 查询的薄封装与示例。

- PR5 测试与迁移
  - 单测：JSON 写入/读取/查询/体积限制/轨迹折叠/兼容读。
  - 可选迁移脚本：将部分热点 predicate 的历史数据升级为 JSON。

---

## 5. 待你确认的决策点（请逐项回复）
1) 体积上限：单个 object_json 最大字节数（建议 64KB/256KB/自定义）。
2) 白名单策略：哪些 predicate 允许 JSON？哪些需要查询索引？
3) 查询形态：是否提供 JSON Path 封装 API？是否允许 LIKE/contains 退化？
4) 索引策略：按 predicate+json_path 建索引，还是仅 predicate 级？
5) 存储后端：当前图存/DB 类型与可用 JSON/索引能力（影响实现细节）。
6) 安全与脱敏：需默认脱敏的字段列表与审计开关策略。
7) TTL/清理：是否为大对象设置 TTL 与异步清理流程？

---

## 6. 验收标准
- 能写：工具通过统一网关写入 JSON 对象三元组，并落轨迹（大对象折叠显示）。
- 能读/能查：按 subject/predicate 读取 JSON；对白名单 predicate 提供 JSON Path 条件过滤。
- 可控：超过体积上限直接拒绝并给出明确错误；轨迹中不泄漏脱敏字段；写入均有审计元数据。
- 兼容：旧有文本 object 的读写与查询不受影响；无强制全量迁移。
- 性能：在配好索引的白名单谓词上，常用查询能稳定在预期 SLA（请给出你的 SLA 目标）。

---

## 7. 牵涉文件（参考，以便后续改动定位）
- 数据与存储：
  - semanticsql-agent/models/base.py（或等效三元组/存储定义）
  - semanticsql-agent/utils/database.py, semanticsql-agent/models/database.py（存储与 DAO 层）
- 工具与记忆：
  - semanticsql-agent/tools/base_tool.py（工具基类返回结构）
  - semanticsql-agent/utils/memory.py（统一图写入/读取网关）
  - semanticsql-agent/utils/trajectory.py（轨迹记录与折叠）
- Agent 与解析/提示：
  - semanticsql-agent/agent/sql_agent.py, semanticsql-agent/agent/base_agent.py
  - semanticsql-agent/utils/thinking_parser.py（跳过 JSON 语义校验的策略）
  - semanticsql-agent/prompts/manager.py 及 templates（JSON 摘要展示策略）
- 测试：
  - semanticsql-agent/tests/test_tools.py / test_thinking_parser.py / test_database.py 等

---

## 8. 风险与缓解
- 存储膨胀与索引开销：体积上限 + 白名单 + TTL/清理。
- 查询复杂度上升：限制 JSON Path 的范围，优先 predicate 定位，再 JSON 局部过滤。
- 数据质量不可控：首版不做 Schema 校验，但保留扩展点；关键谓词可选启用 Schema 验证。
- 上下文污染：轨迹折叠 + Prompt 摘要化，避免把大 JSON 直接喂给模型。

---

## 9. 下一步
请按“第5节决策点”逐项给出你的选择或备注。如果你确认无需增补，我们将按“第4节 PR 计划”提交最小改动实现方案。