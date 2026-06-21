from __future__ import annotations

import json
from pathlib import Path

from src.services.metadata_extractor import extract_metadata
from src.services.pdf_loader import extract_pdf_text


BASE_DIR = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = BASE_DIR / "src" / "data" / "analysis"
PAPERS_JSON_PATH = BASE_DIR / "src" / "data" / "papers.json"


def main() -> None:
    moon_pdf = BASE_DIR / "paper" / "01_基础联邦优化" / "1eeb9f563b1d454eb82c88693d80e4ab-moon.pdf"
    moon_raw = extract_pdf_text(moon_pdf)["raw_text"]
    moon_meta = extract_metadata(moon_raw)

    updates = {
        "1eeb9f563b1d454eb82c88693d80e4ab-moon": {
            "short": "MOON",
            "title": "The Effect of Hyper-parameters in Model-contrastive Federated Learning Algorithm",
            "authors": ["Shen Chen", "Zekai Lin", "Jing Ma"],
            "first_author": "Shen Chen",
            "venue": "2023 IEEE International Conference on Sensors, Electronics and Computer Engineering (ICSECE)",
            "idea": (
                "在本地训练中同时计算当前模型、全局模型与上一轮本地模型的表示，并加入模型对比损失，"
                "使当前表示靠近全局表示、远离历史本地表示，从而稳定非IID场景下的本地更新方向。"
            ),
            "citations": moon_meta["citations"],
            "arxiv_id": None,
            "metadata_verification_notes": "标题、作者、会议信息与 DOI 已按 Crossref 结果校正；引用作者与标题按新规则重新解析。",
        },
        "a93e13033a934717852c1182b8d6fd88-fedprox": {
            "short": "FedProx",
            "title": "Federated Optimization in Heterogeneous Networks",
            "authors": ["Tian Li", "Anit Kumar Sahu", "Ameet Talwalkar", "Virginia Smith"],
            "first_author": "Tian Li",
            "idea": (
                "通过在客户端局部目标中加入与当前全局模型的近端约束项，限制本地更新偏离过远，"
                "并允许不同设备在异构系统条件下执行不同强度的本地优化。"
            ),
            "metadata_verification_notes": "修正了标题中的 markdown 残片与作者污染，保留 DOI 对应期刊来源。",
        },
        "d5cfb5ed140544c9acf0a48b0f3e3022-fedadam": {
            "short": "FedAdam",
            "title": "Adaptive Federated Optimization",
            "authors": [
                "Sashank J. Reddi",
                "Zachary Charles",
                "Manzil Zaheer",
                "Zachary Garrett",
                "Keith Rush",
                "Jakub Konečný",
                "Sanjiv Kumar",
                "H. Brendan McMahan",
            ],
            "first_author": "Sashank J. Reddi",
            "idea": (
                "将自适应优化器放在服务器端对客户端平均更新进行再优化，"
                "用累积的一阶与二阶信息自适应调整全局步长，同时保持客户端训练与通信开销不变。"
            ),
            "metadata_verification_notes": "修正了标题前缀与作者脚注残片，保留 DOI 对应 AAAI 来源。",
        },
    }

    for paper_id, fields in updates.items():
        analysis_path = ANALYSIS_DIR / f"{paper_id}.json"
        analysis_payload = json.loads(analysis_path.read_text(encoding="utf-8"))
        analysis_payload.update(fields)
        analysis_path.write_text(json.dumps(analysis_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    papers_payload = json.loads(PAPERS_JSON_PATH.read_text(encoding="utf-8"))
    for paper in papers_payload["papers"]:
        fields = updates.get(paper["id"])
        if fields:
            paper.update(fields)
    PAPERS_JSON_PATH.write_text(json.dumps(papers_payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
