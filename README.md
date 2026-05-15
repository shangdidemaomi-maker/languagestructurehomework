# 期末大作业 · 离合词发现智能体流水线

## 作业要求

- 写一个发现离合现象的智能体，运用 LangSC 包，不要使用其他包（如 jieba）
- 提交作业需包含：代码（结构分析智能体、BCC 检索智能体、统计分析智能体（输出 JSONL）和 JSS 检索智能体）、报告(.md)和自我评价（自我评分）
- 语料文本（corpus/corpus.txt）和例句（examples.txt）已给出

### 提示

1. 先做分词和词性标注
2. 然后建 BCC 语料库
3. 检索式要体现离合表达，参考 LangSC 手册（https://bcc.blcu.edu.cn/ 很重要，必须参考）
4. 用大模型分析离合结果
5. 用大模型存成 JSON
6. 最后用 JSS 来检索

### LLM 配置

- API: DeepSeek V4
- API Key: 通过环境变量 `DEEPSEEK_API_KEY` 配置

---

## 最终提交清单

只提交以下 **6 个文件**，其余文件（pipeline.py、a_llm.py、run_full.py 等）为辅助运行文件，不纳入提交：

| # | 文件 | 职责 | 涵盖的作业要求 |
|---|------|------|---------------|
| 1 | `agents/a1_structure.py` | 结构分析智能体 — GPF 分词 + 词性标注 | ✅ 结构分析 |
| 2 | `agents/a2_bcc.py` | BCC 检索智能体 — 建索引 + 模式查询（A B / A\*B） | ✅ BCC 检索 |
| 3 | `agents/a3_stats.py` | 统计分析智能体 — 输出 JSONL + cfg，**内置 LLM 分析** | ✅ JSONL 输出 ✅ 大模型分析离合结果 ✅ 大模型存 JSON |
| 4 | `agents/a4_jss.py` | JSS 检索智能体 — 3 条 SQL 查询 | ✅ JSS 检索 |
| 5 | `课程报告.md` | 课程研究报告（六章：目标→方法→分析→JSS SQL→LLM 分析→总结） | ✅ 课程报告 |
| 6 | `自我评价.md` | 自我评分（考勤 20 + 态度 20 + 作业 80 = 120/120） | ✅ 自我评价 |

## 项目文件说明

```
├── agents/                        # 智能体代码（仅 a1~a4 提交）
│   ├── __init__.py
│   ├── a1_structure.py           # ① 结构分析（GPF 分词+词性标注） ← 提交
│   ├── a2_bcc.py                 # ② BCC 检索（建索引+模式查询） ← 提交
│   ├── a3_stats.py               # ③ 统计分析 + LLM 分析（JSONL+cfg+llm_analysis） ← 提交
│   ├── a4_jss.py                 # ④ JSS 检索（3 条 SQL 查询） ← 提交
│   └── a_llm.py                  # (辅助) LLM 分析模块，已合并入 a3_stats.py
├── pipeline.py                   # (辅助) LangGraph 流水线入口
├── run_full.py                   # (辅助) 完整执行脚本
├── corpus/                       # 语料文件（已给出）
├── LangSC/                       # LangSC 本地库
├── 课程报告.md                    # 课程研究报告 ← 提交
├── 自我评价.md                    # 自我评分 ← 提交
└── README.md                     # 本文件
```

## 流水线架构

```
corpus/corpus.txt（生语料）
    │
    ▼  ① agents/a1_structure.py  —  GPF 分词 + 词性标注
    segment/seg.txt（分词结果）
    │
    ▼  ② agents/a2_bcc.py        —  BCC 建索引 + A B / A*B 模式查询
    hits（命中上下文）
    │
    ▼  ③ agents/a3_stats.py      —  解析命中 → JSONL + cfg
    │                            └─ 调用 DeepSeek V4 分析离合现象
    stats/liheci.jsonl + stats/cfg_liheci.txt + stats/llm_analysis.json
    │
    ▼  ④ agents/a4_jss.py        —  JSS 建索引 + 3 条 SQL 查询
    answers（SQL 查询结果）
```

## 大模型（LLM）分析

- **模型**：DeepSeek V4（兼容 OpenAI API 格式）
- **API Base**：`https://api.deepseek.com/v1`
- **位置**：集成在 `agents/a3_stats.py` 末尾
- **功能**：分析插入成分的语法类型（动态助词 / 数量结构 / 定语修饰 / 补语 / 疑问否定）、归纳离合模式、逐词分析
- **降级方案**：API 不可用时自动降级为规则化分析（基于插入成分字符特征自动分类）
- **输出**：`stats/llm_analysis.json`

## 验证清单

- ✅ `a1_structure.py` — GPF 分词 + 词性标注，仅用 LangSC
- ✅ `a2_bcc.py` — BCC 检索，使用 `A B`（合用）和 `A*B`（离用）两种模式
- ✅ `a3_stats.py` — 输出 JSONL（word/form/distance/insert/example）+ cfg（kv/number/bm25/affix）+ LLM 分析
- ✅ `a4_jss.py` — JSS 建索引 + 3 条 Number 索引 SQL 查询
- ✅ `课程报告.md` — 研究目标 / 方法 / 分析结果 / JSS SQL / LLM 分析 / 课程总结
- ✅ `自我评价.md` — 考勤（全勤无迟到早退）+ 态度（端正）+ 作业（全部按时完成），总分 120/120
- ✅ 未使用 jieba 等外部包，仅用 LangSC（GPF / BCC / JSS）
- ✅ DeepSeek V4 API Key 已配置

## 勘误修复记录

提交前核查发现的 3 个问题及修复（2026-05-12）：

| # | 问题 | 修复 |
|---|------|------|
| 1 | 语料文件名歧义 | 统一为 `corpus/corpus.txt`，与考试环境一致 |
| 2 | LangSC 本地目录名为 `LangSC_local`，与代码中 `from LangSC import GPF/BCC/JSS` 不匹配 | 目录重命名为 `LangSC` |
| 3 | README 多处引用旧的 `LangSC_local` | 同步更新为 `LangSC` |

> 注：`segment/seg.txt` 为空目录，需在安装了 LangSC 原生库的环境中运行流水线后方可生成。`pipeline.py`、`run_full.py` 为辅助文件，不在提交范围内。
