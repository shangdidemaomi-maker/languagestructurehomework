"""
智能体②：BCC 检索智能体
职责：在分词后的语料上建 BCC 索引，用结构模式检索离合词
输入：seg_path → 离合词列表
输出：{query → [上下文字符串]}

三要素视角：
  🟦 单元 —— 词条 / 句子
  🟧 关系 —— 倒排索引 / 共现（A B 紧邻、A*B 同句）
  🟨 属性 —— 频次、位置、上下文

注：BCC 依赖 LangSC 原生库 libbcclib.dylib，需在已安装 LangSC 的环境中运行。
    A*B 模式参考 BCC 官方手册：https://bcc.blcu.edu.cn/
"""
import json
# LangSC 为本地库，依赖原生动态库 libgpflib.dylib / libbcclib.dylib / libjsslib.dylib
from LangSC import BCC


# 离合词列表（取第一个字 A 和第二个字 B）
LIHECI_WORDS = [
    "见面", "帮忙", "操心", "鞠躬", "洗澡",
    "睡觉", "结婚", "请假", "吃饭", "生气"
]


def a2_bcc(state: dict) -> dict:
    """
    输入 state 字段：seg_path (str)
    输出 state 字段：hits (dict)
    """
    print("【BCC 检索智能体】正在建索引并检索离合词...")

    seg_path = state.get("seg_path", "segment/seg.txt")

    # 🟦 在 segment 目录上初始化 BCC（自动建索引）
    bcc = BCC("segment")

    hits = {}
    for word in LIHECI_WORDS:
        a, b = word[0], word[1]

        # 🟧 模式1：紧邻（合用）—— 检索 "A B"（空格表示紧邻）
        query_cohesive = f"{a} {b}"
        try:
            result_cohesive = bcc.Run(query_cohesive, Command="Context", Number=50)
            data_cohesive = json.loads(result_cohesive) if isinstance(result_cohesive, str) else result_cohesive
            contexts_cohesive = data_cohesive.get("Context", [])
        except Exception as e:
            print(f"  ! 合用查询「{query_cohesive}」失败：{e}")
            contexts_cohesive = []

        # 🟧 模式2：同句（离用）—— 检索 "A*B"（* 表示同句任意距离）
        query_separated = f"{a}*{b}"
        try:
            result_separated = bcc.Run(query_separated, Command="Context", Number=100)
            data_separated = json.loads(result_separated) if isinstance(result_separated, str) else result_separated
            contexts_separated = data_separated.get("Context", [])
        except Exception as e:
            print(f"  ! 离用查询「{query_separated}」失败：{e}")
            contexts_separated = []

        hits[f"{word}_合用"] = contexts_cohesive
        hits[f"{word}_离用"] = contexts_separated

        print(f"  · 离合词「{word}」: 合用 {len(contexts_cohesive)} 条, 离用 {len(contexts_separated)} 条")

    print(f"  [OK] 完成！共检索 {len(LIHECI_WORDS)} 个离合词")
    return {"hits": hits}
