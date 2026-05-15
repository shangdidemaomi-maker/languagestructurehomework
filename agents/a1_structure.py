"""
智能体①：结构分析智能体
职责：使用 GPF 对生语料进行分词 + 词性标注
输入：corpus/corpus.txt（GBK，每行一句）
输出：segment/seg.txt（每行：词1/POS1 词2/POS2 ...）

三要素视角：
  🟦 单元 —— 每个词（token）
  🟧 关系 —— 词在句中的线性顺序
  🟨 属性 —— 词性（POS）标注
"""
import json
import os
from LangSC import GPF


def a1_structure(state: dict) -> dict:
    """
    输入 state 字段：corpus_path (str)
    输出 state 字段：seg_path (str)
    """
    print("【结构分析智能体】正在分词 + 词性标注...")

    corpus_path = state.get("corpus_path", "corpus/corpus.txt")
    seg_dir = "segment"
    seg_path = os.path.join(seg_dir, "seg.txt")

    if not os.path.exists(seg_dir):
        os.makedirs(seg_dir)

    # 🟦 创建 GPF 实例（分词工具）
    gpf = GPF("segment")

    with open(corpus_path, "r", encoding="gbk", errors="ignore") as fi, \
         open(seg_path, "w", encoding="gbk") as fo:
        line_count = 0
        for line in fi:
            line = line.strip()
            if not line:
                continue
            try:
                # 🟨 解析句子：得到每个词的词性标注
                js = gpf.Parse(line, Structure="POS")
                segment = json.loads(js)
                # 🟧 输出词序列（用空格连接）
                fo.write(" ".join(segment) + "\n")
                line_count += 1
                if line_count % 1000 == 0:
                    print(f"  已处理 {line_count} 行...", end="\r")
            except Exception as e:
                print(f"  警告：处理失败 → {line[:30]}... [{e}]")

    print(f"\n  [OK] 完成！共处理 {line_count} 行，输出到 {seg_path}")
    return {"seg_path": seg_path}
    