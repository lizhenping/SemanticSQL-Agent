# Datasets

论文 §IV.A 共用 8 个 benchmark。本目录存放其中 **5 个**用于合成训练数据的数据库；另 3 个 Spider 变体（Spider-Syn / Spider-Realistic / Spider-DK）仅用于评估，从 Spider 派生，无需单独下载数据库。

> ⚠️ 本目录被 `.gitignore` 排除（35GB），不进版本库。通过阿里云盘下载（见下文）。

---

## 下载

数据集打包为 `data.tar`，上传至阿里云盘：

```bash
# 1. 从阿里云盘下载 data.tar
# 2. 解压到项目根目录
tar xf data.tar -C .
# 解压后得到 datasets/ 目录（包含 5 个 benchmark，35GB）
```

解压后确认目录结构：
```bash
ls datasets/
# bird  ehrsql  science_benchmark  spider  spider2
```

---

## 统一目录规则

所有 benchmark 遵循同一个路径规则：

```
datasets/<benchmark>/databases/<db_name>/<db_name>.sqlite
datasets/<benchmark>/qa/                                 # 问题-SQL 对（评估用，合成不读）
```

代码按此规则自动定位数据库：
```bash
# 代码内部拼接路径
{DB_ROOT}/{benchmark}/databases/{db}/{db}.sqlite
# DB_ROOT 默认为 datasets/，也可用环境变量覆盖
```

---

## 目录结构

```
datasets/
├── spider/                          # Spider 1.0（206 库）
│   ├── databases/
│   │   └── <db_name>/<db_name>.sqlite
│   └── qa/                          # train/dev/test 的 QA 文件
│       ├── train/train_spider.json
│       ├── eval/dev.json
│       └── tables.json
│
├── bird/                            # BIRD（81 库）
│   ├── databases/
│   │   └── <db_name>/
│   │       ├── <db_name>.sqlite
│   │       └── database_description/  # BIRD 列描述 CSV
│   └── qa/
│       ├── train/train.json
│       └── eval/dev.json
│
├── spider2/                         # Spider 2.0 SQLite 子集（30 库）
│   ├── databases/
│   └── qa/
│       └── eval/spider2-lite.jsonl
│
├── ehrsql/                          # EHRSQL（2 库：MIMIC-III + eICU）
│   ├── databases/
│   │   ├── mimic_iii/mimic_iii.sqlite
│   │   └── eicu/eicu.sqlite
│   └── qa/
│
└── science_benchmark/               # ScienceBenchmark（3 库）
    ├── databases/
    │   ├── cordis_temporary/cordis_temporary.sqlite
    │   ├── oncomx/oncomx.sqlite
    │   └── sdss/sdss.sqlite
    └── qa/
```

---

## 统计

| Benchmark | DB 数 | 域数 | 平均表/DB | 合成目标 | 角色 |
|-----------|-------|------|----------|---------|------|
| Spider 1.0 | 206 | 138 | 5.11 | 40,000 | 跨域解析 |
| Spider 2.0-SQLite | 30 | 8 | 13.8 | 20,000 | 企业级复杂度 |
| BIRD | 81 | 37 | 7.64 | 30,000 | 知识密集推理 |
| EHRSQL | 2 | 1 | 31.55 | 5,000 | 临床领域 |
| ScienceBenchmark | 3 | 3 | 16.67 | 5,000 | 科学领域 |

**总计：322 个 sqlite，35GB**

---

## 数据泄露防护

合成时**自动排除评估库**（dev/test），防止数据泄露：

| Benchmark | 评估库（禁合成） | 可合成库 |
|-----------|----------------|---------|
| Spider | 59 个（dev 20 + test 39） | 163 个 |
| BIRD | 11 个（dev） | 69 个 |
| Spider2 | 无（SQLite 子集本身就是合成用） | 30 个 |
| EHRSQL | 库级不隔离（train/eval 共用库，靠不读 QA 隔离） | 2 个 |
| ScienceBenchmark | 同上 | 3 个 |

查看某 benchmark 可用/禁用的库：
```bash
docker compose run --rm semanticsql list-dbs -b spider
```

隔离由 `semanticsql-agent/infra/dataset_split.py` 强制执行，任何命令（`run`、`run-benchmark`、`analyze`、`generate`）遇到评估库都会直接拒绝。

---

## 官方下载源（供参考）

如果阿里云盘链接不可用，可从官方源单独下载：

| Benchmark | 官方下载 |
|-----------|---------|
| Spider 1.0 | https://github.com/taoyds/spider |
| BIRD | https://bird-bench.github.io/ |
| Spider 2.0 | https://github.com/xlang-ai/Spider2 |
| EHRSQL | https://github.com/glee4810/EHRSQL |
| ScienceBenchmark | https://github.com/yizhang-unifr/nl-ql-data-augmentation |
