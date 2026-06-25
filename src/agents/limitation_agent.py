from __future__ import annotations

from src.llm.provider import UnifiedLLMProvider


async def analyze_limitations(title: str, abstract: str, raw_text: str) -> dict:
    provider = UnifiedLLMProvider()
    return await provider.complete_json(
        "你是一名严谨、克制的学术审稿助手，擅长识别论文局限性。必须使用中文输出合法 JSON，禁止输出 JSON 之外的任何内容。",
        f"""
    任务：
    阅读论文标题、摘要和正文片段，识别论文的局限性（limitations）。

    请严格遵循以下原则：

    总体原则
    1. 优先提取作者明确承认的局限性。
    2. 只有当正文存在充分证据支持时，才允许进行谨慎推断。
    3. 不允许基于常识、个人经验或领域偏见进行猜测。
    4. 如果证据不足，不要生成对应局限。
    5. 宁缺毋滥，避免把“未来工作”“改进方向”自动视为局限。

    局限类型定义
    - paper_claimed：
      作者在论文中明确表达或暗示的局限性，例如：
      - limitations
      - weaknesses
      - future work 中明确指出的不足
      - "we only ..."
      - "our method cannot ..."
      - "one limitation is ..."
      - "we leave ... for future work"

    - inferred：
      根据论文内容可以直接推导出的局限，但必须满足：
      ① 能提供明确文本证据；
      ② 推断链路很短；
      ③ 不依赖外部知识。

      合法示例：
      - 实验仅在单一数据集验证 → 泛化能力验证不足；
      - 缺少与主流强基线比较 → 比较充分性不足；
      - 未进行消融实验 → 难以判断关键模块贡献。

      非法示例：
      - “可能无法工业落地”
      - “可能存在伦理风险”
      - “可能计算开销很大”
      除非论文明确提供相关证据，否则禁止生成。

    【evidence 要求】
    - evidence 必须来自给定文本。
    - 尽量保留论文原文关键表述。
    - 使用简洁中文概括，不得编造引用。
    - 若正文存在明显对应句，可进行忠实转述。

    【severity 定义】
    只能取以下值：
    - low：影响较小，不影响主要结论；
    - medium：影响结论适用范围或实验充分性；
    - high：可能显著削弱论文核心结论的可信度。

    【输出要求】
    返回 JSON，格式严格如下,必须用中文回答：

    {{
      "limitations": "对论文局限性的整体总结，100字以内；若未发现明确局限，则说明“给定文本中未发现充分证据支持明确局限”。",
      "limitation_points": [
        {{
          "point": "局限性的简洁描述",
          "evidence": "对应证据或忠实转述",
          "type": "paper_claimed 或 inferred",
          "severity": "low、medium 或 high"
        }}
      ]
    }}

    【质量检查】
    在输出前自行检查：
    - 是否存在无证据推断；
    - inferred 是否能够被给定文本直接支持；
    - evidence 是否与 point 一致；
    - JSON 是否合法。

    标题：
    {title}

    摘要：
    {abstract}

    正文片段：
    {raw_text[:]}
    """.strip(),
        trace_label="limitation_agent",
        max_retries=1,
    )
