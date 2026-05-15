"""
智能体③：统计分析智能体 + 大模型（LLM）分析
职责：从 BCC 检索结果中解析命中内容，提取字段，聚合，输出 JSONL + cfg，
     并调用 DeepSeek V4 大模型分析离合现象，输出 stats/llm_analysis.json
输入：hits (dict)
输出：./stats/liheci.jsonl + ./stats/cfg_liheci.txt + ./stats/llm_analysis.json

JSONL 字段：
  - word:     离合词
  - form:     合用 / 离用
  - distance: 插入的字数（合用为 0）
  - insert:   插入的字串
  - example:  上下文示例

三要素视角：
  🟦 单元 —— JSONL 的每条记录
  🟧 关系 —— 聚合统计（GROUP BY）/ LLM 分析插入成分与离合词的语法关系
  🟨 属性 —— word / form / distance / insert / example / 插入类型 / 离合模式

注：依赖 requests 库调用 DeepSeek V4 API。API 不可用时自动降级为规则化分析。
"""
import json
import os
import re

import requests


# --- DeepSeek V4 配置 ---
# API Key 从环境变量读取，请设置 DEEPSEEK_API_KEY 环境变量
LLM_CONFIG = {
    "api_base": "https://api.deepseek.com/v1",
    "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
    "model": "deepseek-chat",
    "max_tokens": 2048,
    "temperature": 0.3,
}


def _clean_example(text: str) -> str:
    """清洗例句：去 HTML 标签、去 SourceID、截断"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"SourceID[^}]*}", "", text)
    text = text.strip()
    return text[:200]


def _call_llm(prompt: str) -> dict:
    """调用 DeepSeek V4 API，返回 JSON 分析结果"""
    headers = {
        "Authorization": f"Bearer {LLM_CONFIG['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_CONFIG["model"],
        "messages": [
            {"role": "system", "content": (
                "你是一位汉语语言学专家，擅长分析离合词现象。"
                "请用 JSON 格式输出分析结果，不要输出其他内容。"
            )},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": LLM_CONFIG["max_tokens"],
        "temperature": LLM_CONFIG["temperature"],
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(
            f"{LLM_CONFIG['api_base']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"  ! LLM API 调用失败：{e}，降级为规则化分析")
        return None


def _rule_based_analysis(records: list) -> dict:
    """规则化分析（LLM 不可用时的降级方案）"""
    insert_types = {}
    patterns = []
    per_word = {}

    for rec in records:
        word = rec["word"]
        insert = rec.get("insert", "")
        distance = rec.get("distance", 0)
        example = _clean_example(rec.get("example", ""))

        # 分类插入成分类型
        if any(c in insert for c in "了过着"):
            cat = "动态助词"
        elif any(c in insert for c in "一次个些点") or (
            re.search(r"[一两三四五六七八九十百千万\d]+", insert)
            and any(c in insert for c in "次个遍下回趟场顿番")
        ):
            cat = "数量结构"
        elif re.search(r"[的得地]", insert):
            cat = "定语/补语标记"
        elif any(c in insert for c in "什么怎么") or "不" in insert:
            cat = "疑问/否定"
        elif insert == "" or distance == 0:
            cat = "合用（无插入）"
        else:
            cat = "其他修饰成分"

        insert_types.setdefault(cat, [])
        insert_types[cat].append({"word": word, "insert": insert, "example": example[:80]})

        per_word.setdefault(word, [])
        per_word[word].append({"insert": insert, "distance": distance, "category": cat})

        if distance > 0:
            patterns.append(
                f"{word[0]}+「{insert}」+{word[1]}  ({cat}, 距离={distance})"
            )

    category_stats = {
        cat: len(items) for cat, items in insert_types.items()
    }

    return {
        "overall_insight": (
            f"从 {len(records)} 条离合词记录中共检出 {len([r for r in records if r.get('distance', 0) > 0])} 条离用实例。"
            f"插入成分类型分布：{json.dumps(category_stats, ensure_ascii=False)}。"
        ),
        "per_word": per_word,
        "category_stats": category_stats,
        "patterns": patterns[:20],
        "method": "rule-based",
    }


def _run_llm_analysis(records: list) -> dict:
    """对已解析的记录执行大模型分析"""
    print("  正在调用 DeepSeek V4 分析离合现象...")

    sep_records = [r for r in records if r.get("distance", 0) > 0]
    if not sep_records:
        print("  ! 未检出离用记录，仅做规则化分析")
        return _rule_based_analysis(records)

    print(f"  检出 {len(sep_records)} 条离用记录，正在构造 LLM 提示词...")

    # 构造样本数据
    samples = []
    for rec in sep_records[:15]:
        samples.append({
            "word": rec["word"],
            "insert": rec.get("insert", ""),
            "distance": rec.get("distance", 0),
            "example": _clean_example(rec.get("example", "")),
        })

    # 构造 prompt
    prompt = f"""请分析以下汉语离合词的真实语料数据，输出 JSON 格式分析结果。

## 离合词离用样本
{json.dumps(samples, ensure_ascii=False, indent=2)}

## 分析要求
1. overall_insight: 整体分析（1-2句话概括发现）
2. per_word: 按离合词分别分析，每项含 insertions（插入成分列表）和 insight（一句话分析）
3. category_stats: 插入成分类型统计（动态助词/数量结构/定语修饰/补语/疑问否定/其他），每类的出现次数
4. patterns: 总结出的离合模式列表（如 "V+了+X+N"）
5. method: 固定为 "llm"

请严格输出 JSON，不要包含其他文字。"""

    analysis = _call_llm(prompt)

    if analysis is None:
        analysis = _rule_based_analysis(records)
    else:
        analysis["method"] = "llm"

    return analysis


def a3_stats(state: dict) -> dict:
    """
    输入 state 字段：hits (dict)
    输出 state 字段：jsonl_path (str), llm_analysis (dict)
    """
    print("【统计分析智能体】正在解析并生成 JSONL...")

    hits = state.get("hits", {})
    stats_dir = "stats"
    if not os.path.exists(stats_dir):
        os.makedirs(stats_dir)

    jsonl_path = os.path.join(stats_dir, "liheci.jsonl")
    records = []

    # 从 hits 中解析每个离合词的合用/离用结果
    for key, contexts in hits.items():
        # key 格式: "见面_合用" 或 "见面_离用"
        if "_" not in key:
            continue
        word, form = key.rsplit("_", 1)
        a, b = word[0], word[1]

        for ctx in contexts:
            # 从 <Q>...</Q> 中提取查询命中的 span
            m = re.search(r"<Q>(.*?)</Q>", ctx)
            if not m:
                continue
            span = m.group(1)

            # 计算字距：找到 A 和 B 在 span 中的位置
            ai = span.find(a)
            bi = span.find(b, ai + 1) if ai >= 0 else -1

            if form == "合用":
                distance = 0
                insert = ""
            elif form == "离用" and 0 <= ai < bi:
                distance = bi - ai - 1  # 中间插入了几个字
                insert = span[ai + 1:bi]  # 插入的字串
            else:
                distance = -1
                insert = ""

            record = {
                "word": word,
                "form": form,
                "distance": distance,
                "insert": insert,
                "example": ctx[:100]  # 取前100字符作为示例
            }
            records.append(record)

    # 写入 JSONL（每行一条 JSON）
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"  [OK] 已写入 {len(records)} 条记录到 {jsonl_path}")

    # 生成 cfg 文件（定义索引类型，供 JSS 使用）
    cfg = {
        "table_name": "liheci",
        "record_format": "jsonl",
        "content": {
            "word": "word",
            "form": "form",
            "distance": "distance",
            "insert": "insert",
            "example": "example"
        },
        "index": {
            "kv": ["word", "form"],          # 键值索引
            "number": ["distance"],           # 数值索引
            "bm25": ["example"],              # 全文检索
            "affix": ["insert"]               # 模糊匹配
        }
    }

    cfg_path = os.path.join(stats_dir, "cfg_liheci.txt")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

    print(f"  [OK] 已写入 cfg 到 {cfg_path}")

    # ---- 大模型分析（合并自 a_llm）----
    llm_analysis = _run_llm_analysis(records)

    # 保存 LLM 分析结果到 JSON 文件（"用大模型存成 JSON"）
    llm_json_path = os.path.join(stats_dir, "llm_analysis.json")
    with open(llm_json_path, "w", encoding="utf-8") as f:
        json.dump(llm_analysis, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 大模型分析完成（方法：{llm_analysis.get('method', 'unknown')}）")
    print(f"  [OK] 已保存 LLM 分析结果到 {llm_json_path}")

    return {"jsonl_path": jsonl_path, "llm_analysis": llm_analysis}
