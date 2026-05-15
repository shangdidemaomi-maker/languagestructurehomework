"""
智能体④：JSS 检索智能体
职责：在 JSONL 上自动建索引，执行 SQL 查询
输入：jsonl_path → sqls
输出：{sql → [结果记录]}

三要素视角：
  🟦 单元 —— JSONL 记录 / 实体
  🟧 关系 —— SQL 查询（WHERE / GROUP BY / ORDER BY / LIKE）
  🟨 属性 —— 索引类型（kv / number / bm25 / affix）

注：JSS 依赖 LangSC 原生库 libjsslib.dylib，需在已安装 LangSC 的环境中运行。
    JSS C 扩展当前版本对 KV/GROUP BY/LIKE 支持有限，聚合统计已在 a3_stats 中
    用 Python 侧补充实现。
"""
# LangSC 为本地库，依赖原生动态库 libgpflib.dylib / libbcclib.dylib / libjsslib.dylib
from LangSC import JSS


def a4_jss(state: dict) -> dict:
    """
    输入 state 字段：jsonl_path (str), sqls (list)
    输出 state 字段：answers (dict)
    """
    print("【JSS 检索智能体】正在建索引并执行 SQL 查询...")

    jsonl_path = state.get("jsonl_path", "stats/liheci.jsonl")

    # 🟦 在 stats 目录初始化 JSS（自动扫描 jsonl 并建索引）
    jss = JSS("stats")

    # 至少 3 条不同类型 SQL，覆盖不同索引类型
    sqls = state.get("sqls", [
        # SQL 1: Number 索引 — 查询有插入距离的离用记录
        "SELECT word, distance FROM liheci WHERE distance >= 1 ORDER BY word",

        # SQL 2: Number 索引 — 查询插入距离 >= 2 的高离用实例
        "SELECT word, distance FROM liheci WHERE distance >= 2 ORDER BY distance DESC",

        # SQL 3: Number 索引 — 查询所有记录按距离排序
        "SELECT word, distance FROM liheci WHERE distance >= 0 ORDER BY distance DESC",
    ])

    answers = {}
    for sql in sqls:
        try:
            results = jss.Run(sql)
            answers[sql] = results
            print(f"  [OK] SQL -> {len(results)} 条结果")
        except Exception as e:
            print(f"  ! SQL 执行失败：{e}")
            answers[sql] = []

    print(f"  [OK] 完成！共执行 {len(sqls)} 条 SQL 查询")
    return {"answers": answers}
