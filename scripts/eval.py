"""智服通 - 检索质量离线评测脚本

用一组「问题 → 期望知识库分类」的用例，评估混合检索在给定
query 下是否召回正确分类的片段（Top-K 命中率）。

用法：
    python scripts/eval.py

输出：
    - 逐条用例：查询、期望分类、Top-3 实际分类、是否命中
    - 汇总：命中率、Top-1 命中率
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.logger import get_logger
from app.rag.retriever import retrieve

logger = get_logger("eval")

# 评测用例：问题 → 期望命中的知识库分类
CASES: list[tuple[str, str]] = [
    ("我忘记登录密码了，怎么重置？", "accounts"),
    ("公司内网 WiFi 怎么连接？", "network"),
    ("如何申请安装 Office 软件？", "software"),
    ("笔记本风扇声音很大，是坏了吗？", "hardware"),
    ("离职员工的账号权限怎么注销？", "security"),
    ("如何提交报修工单？", "general"),
    ("邮箱密码多久需要强制更换一次？", "accounts"),
    ("VPN 连不上了怎么办？", "network"),
    ("打印机一直提示墨盒错误怎么处理？", "hardware"),
]


def main() -> int:
    hits = 0
    top1_hits = 0
    print(f"{'查询':<14} {'期望分类':<10} {'Top-1':<10} {'Top-3分类':<32} 命中")
    print("─" * 84)
    for query, expected in CASES:
        results = retrieve(query, top_k=5)
        categories = [r.metadata.get("category", "") for r in results]
        ok = expected in categories
        top1_ok = bool(categories) and categories[0] == expected
        hits += ok
        top1_hits += top1_ok
        mark = "✓" if ok else "✗"
        print(
            f"{query:<14} {expected:<10} {(categories[0] if categories else '—'):<10} "
            f"{' , '.join(categories[:3]):<32} {mark}"
        )

    total = len(CASES)
    print("─" * 84)
    print(
        f"Top-3 命中率: {hits}/{total} = {hits / total * 100:.0f}%   "
        f"Top-1 命中率: {top1_hits}/{total} = {top1_hits / total * 100:.0f}%"
    )
    return 0 if hits == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
