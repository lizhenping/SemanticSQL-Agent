"""知识存储抽象层（infra/storage.py）

设计原则：
- DRY：6 个 JSONL 文件的路径映射和读写逻辑只此一处
  替代各工具散落的 os.path.dirname(__file__) 路径计算
- 可测试性：KnowledgeStore 协议可注入内存实现做单测

layer 名 -> 文件名映射（唯一真相源）：
  schema    -> schema_extraction.jsonl       (K1)
  domain    -> domain_analysis.jsonl          (K2)
  field     -> field_analysis.jsonl           (K3) ← 当前 query_evidence 缺这个！
  column    -> column_analysis.jsonl          (K4)
  table     -> table_analysis.jsonl           (K5)
  er        -> er_analysis.jsonl              (K6)
  questions -> questions.jsonl                (Phase 2 产物)
  sql       -> sql_results.jsonl              (Phase 2 产物)
  diagnosis_trace -> diagnosis_trace.jsonl    (Phase 3 可审计轨迹)
  corpus_manifest -> corpus_manifest.jsonl    (训练样本准入裁决)
"""

import json
import logging
from pathlib import Path
from typing import Any, Protocol, Union


class KnowledgeStore(Protocol):
    """知识存储协议（可注入内存实现做单测）"""

    def load(self, layer: str) -> list[dict]:
        """加载某层知识（返回 JSON 记录列表）"""
        ...

    def save(self, layer: str, data: Union[list[dict], dict]) -> None:
        """保存某层知识（覆盖写）"""
        ...

    def append(self, layer: str, record: dict) -> None:
        """追加一条记录"""
        ...

    def exists(self, layer: str) -> bool:
        """某层知识是否存在"""
        ...


class JSONLKnowledgeStore:
    """JSONL 文件实现（替代散落的路径计算）

    所有工具通过此类读写 JSONL，不再各自 os.path.join。
    history_dir 是唯一路径来源。
    """

    # layer 名 -> 文件名映射（DRY：唯一真相源）
    LAYER_FILES = {
        "schema":     "schema_extraction.jsonl",
        "domain":     "domain_analysis.jsonl",
        "field":      "field_analysis.jsonl",
        "column":     "column_analysis.jsonl",
        "table":      "table_analysis.jsonl",
        "er":         "er_analysis.jsonl",
        "questions":  "questions.jsonl",
        "sql":        "sql_results.jsonl",
        "diagnosis_trace": "diagnosis_trace.jsonl",
        "corpus_manifest": "corpus_manifest.jsonl",
    }

    def __init__(self, history_dir: Union[str, Path]):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def _path(self, layer: str) -> Path:
        """获取某层 JSONL 文件路径"""
        if layer not in self.LAYER_FILES:
            raise ValueError(f"未知知识层: {layer}（支持: {list(self.LAYER_FILES.keys())}）")
        return self.history_dir / self.LAYER_FILES[layer]

    def load(self, layer: str) -> list[dict]:
        """加载某层知识（返回记录列表）"""
        path = self._path(layer)
        if not path.exists():
            self.logger.debug(f"文件不存在: {path}")
            return []
        records = []
        try:
            import jsonlines
            with jsonlines.open(path) as reader:
                for obj in reader:
                    records.append(obj)
        except Exception as e:
            # 降级到纯 JSON 行读取
            self.logger.warning(f"jsonlines 读取失败，降级纯文本: {e}")
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        return records

    def save(self, layer: str, data: Union[list[dict], dict]) -> None:
        """保存某层知识（覆盖写）"""
        path = self._path(layer)
        if isinstance(data, dict):
            data = [data]
        try:
            import jsonlines
            with jsonlines.open(path, mode="w") as writer:
                for record in data:
                    writer.write(record)
        except Exception as e:
            # 降级到纯 JSON 行写入
            self.logger.warning(f"jsonlines 写入失败，降级纯文本: {e}")
            with open(path, "w", encoding="utf-8") as f:
                for record in data:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.logger.debug(f"保存 {len(data)} 条记录 -> {path}")

    def append(self, layer: str, record: dict) -> None:
        """追加一条记录"""
        path = self._path(layer)
        try:
            import jsonlines
            with jsonlines.open(path, mode="a") as writer:
                writer.write(record)
        except Exception:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def exists(self, layer: str) -> bool:
        """某层知识是否存在"""
        return self._path(layer).exists()

    def list_layers(self) -> list[str]:
        """列出所有已存在的层"""
        return [layer for layer in self.LAYER_FILES if self.exists(layer)]


class InMemoryKnowledgeStore:
    """内存实现（单测用，不碰文件系统）"""

    def __init__(self):
        self._data: dict[str, list[dict]] = {}

    def load(self, layer: str) -> list[dict]:
        return self._data.get(layer, [])

    def save(self, layer: str, data: Union[list[dict], dict]) -> None:
        if isinstance(data, dict):
            data = [data]
        self._data[layer] = list(data)

    def append(self, layer: str, record: dict) -> None:
        if layer not in self._data:
            self._data[layer] = []
        self._data[layer].append(record)

    def exists(self, layer: str) -> bool:
        return layer in self._data and len(self._data[layer]) > 0

    def list_layers(self) -> list[str]:
        return [k for k, v in self._data.items() if v]
