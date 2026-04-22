"""Chunking and classification functions for document processing."""
from __future__ import annotations
import json, os, re, sys

try:
    from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter
    _HAS_LANGCHAIN = True
except ImportError:
    _HAS_LANGCHAIN = False

# ---------------------------------------------------------------------------
# Document classification
# ---------------------------------------------------------------------------

DOC_TYPES = frozenset({
    "prd", "tech-design", "reference", "guide", "explanation",
    "decision", "meeting-notes", "superteam-report", "plan",
    "changelog", "other",
})


def classify_by_regex(title: str, content_preview: str) -> str:
    """Regex-based doc_type classification (fallback when LLM unavailable).

    Scans title first, then content preview (up to 2000 chars).
    Returns one of DOC_TYPES; defaults to 'other'.
    """
    t = (title or "").strip().lower()
    p = (content_preview or "")[:2000].lower()

    # --- Title-first matching ---
    if re.search(r"(prd|需求文档|产品需求|product.?require)", t):
        return "prd"
    if re.search(r"(trd|技术方案|设计文档|架构设计|系统设计)", t):
        return "tech-design"
    if re.search(r"(api.?refer|接口文档|数据字典|配置说明|参数表)", t):
        return "reference"
    if re.search(r"(新人指南|入职手册|快速上手|环境搭建|操作手册|setup.?guide)", t):
        return "guide"
    if re.search(r"(最佳实践|踩坑|经验总结|知识沉淀|原理|best.?practice)", t):
        return "explanation"
    if re.search(r"(adr|技术选型|方案对比|评审结论|decision)", t):
        return "decision"
    if re.search(r"(会议纪要|meeting.?note|standup|sprint.?planning)", t):
        return "meeting-notes"
    if re.search(r"(周报|月报|w\d+|weekly|week\s?\d|复盘)", t):
        return "superteam-report"
    if re.search(r"(okr|q\d+|季度计划|roadmap|排期|里程碑|排行榜|积分规则)", t):
        return "plan"
    if re.search(r"(release.?note|changelog|变更记录|发版|hotfix)", t):
        return "changelog"

    # --- Content preview matching ---
    if re.search(r"(## 功能列表|用户故事|acceptance.?criteria|# prd)", p):
        return "prd"
    if re.search(r"(## 架构图|sequence.?diagram|api.?设计|技术方案)", p):
        return "tech-design"
    if re.search(r"(endpoint|GET /|POST /|parameters?:|swagger|openapi)", p):
        return "reference"
    if re.search(r"(## 故障现象|## 排查步骤|## 解决方案|runbook|sop|# 第一步|git clone|npm install|本地启动|账号申请)", p):
        return "guide"
    if re.search(r"(踩坑记录|经验总结|最佳实践|lessons?.?learned|知识沉淀)", p):
        return "explanation"
    if re.search(r"(方案对比|技术选型|vs\s|versus|评审结论|trade.?off)", p):
        return "decision"
    if re.search(r"(### 日期[：:]|参会人员[：:]|议题[：:]|结论[：:]|TODO[：:])", p):
        return "meeting-notes"
    if re.search(r"(【本周完成】|【下周计划】|【阻塞问题】|✅ 做得好的|❌ 需改进|💡 改进建议|行动项)", p):
        return "superteam-report"
    if re.search(r"(key.?result|里程碑|积分规则)", p):
        return "plan"
    if re.search(r"(## v\d|### bug.?fix|### feature|breaking.?change)", p):
        return "changelog"

    return "other"


def chunk_text(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """按段落优先切分，过长段落再按 max_chars 带 overlap 切分。
    max_chars=0 时不分块，整段保留（用于电子表格等宽内容）。"""
    if max_chars <= 0:
        return [text] if text.strip() else []
    chunks: list[str] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) <= max_chars:
            chunks.append(block)
            continue
        start = 0
        while start < len(block):
            end = start + max_chars
            piece = block[start:end]
            chunks.append(piece)
            start = end - overlap if overlap < max_chars else end
    return chunks


def _is_markdown(text: str) -> bool:
    """检测文本是否包含 Markdown 结构标记。

    扫描前 5000 字符。需要至少 2 种标记共现。排除代码文件。
    """
    first_line = text.lstrip()[:50]
    if any(first_line.startswith(s) for s in ("#!/", "import ", "from ", "def ", "class ", "package ")):
        return False
    sample = text[:5000]
    indicators = [
        re.search(r"^#{1,6}\s", sample, re.MULTILINE),
        re.search(r"^```", sample, re.MULTILINE),
        re.search(r"^\|.*\|.*\|", sample, re.MULTILINE),
        re.search(r"^[-*+]\s", sample, re.MULTILINE),
        re.search(r"^\d+\.\s", sample, re.MULTILINE),
    ]
    return sum(1 for i in indicators if i) >= 2


def chunk_smart(text: str, max_chars: int = 1500, overlap: int = 200,
                format_hint: str = "auto") -> list[str]:
    """智能分块：Markdown 用 MarkdownTextSplitter，纯文本用 RecursiveCharacterTextSplitter。

    langchain-text-splitters 未安装时降级到 chunk_text()。
    max_chars=0 时不分块（电子表格兼容）。
    format_hint: "markdown" | "plain" | "auto"
    """
    if max_chars <= 0:
        return [text] if text.strip() else []
    if not _HAS_LANGCHAIN:
        print("⚠️  langchain-text-splitters not installed — falling back to chunk_text().",
              file=sys.stderr)
        return chunk_text(text, max_chars=max_chars, overlap=overlap)
    use_markdown = (
        format_hint == "markdown"
        or (format_hint == "auto" and _is_markdown(text))
    )
    if use_markdown:
        splitter = MarkdownTextSplitter(chunk_size=max_chars, chunk_overlap=overlap)
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chars, chunk_overlap=overlap,
            separators=["\n\n", "\n", "。", "．", ". ", "；", "; ", "，", ", ", " ", ""],
        )
    chunks = splitter.split_text(text)
    return [c.strip() for c in chunks if c.strip()]


def _ensure_dashscope_key() -> bool:
    """Load DASHSCOPE_API_KEY from config files if not in env."""
    if os.environ.get("DASHSCOPE_API_KEY"):
        return True
    from pathlib import Path
    for cfg_path in [
        Path.home() / ".dingtalk-skills" / "config",
        Path.home() / ".notion-skills" / "config",
    ]:
        if cfg_path.exists():
            for line in cfg_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("DASHSCOPE_API_KEY="):
                    os.environ["DASHSCOPE_API_KEY"] = line.split("=", 1)[1].strip()
                    return True
    return False


def classify_by_llm(title: str, content_preview: str, model: str = "qwen-plus") -> str:
    """Use DashScope Qwen to classify doc_type from title + content preview.

    Returns one of DOC_TYPES. Falls back to classify_by_regex on any failure.
    """
    try:
        import dashscope
        from dashscope import Generation
    except ImportError:
        return classify_by_regex(title, content_preview)

    if not _ensure_dashscope_key():
        return classify_by_regex(title, content_preview)

    prompt = f"""你是文档分类助手。根据文档标题和内容预览，判断文档属于以下哪个类型。
只输出类型名称（一个英文短横线词），不要任何解释或前缀。

类型定义：
- prd: 产品需求文档。包括功能需求、用户故事、Campaign方案、拉新策略、产品设计方案、需求规格等
- tech-design: 技术方案。包括架构设计、技术调研报告、系统设计、整合方案、TRD等
- reference: 参考资料。包括API文档、数据字典、配置说明、SDK文档、数据模型说明等
- guide: 指南/教程。包括操作手册、入职手册、环境搭建、部署指南等
- explanation: 概念解释/知识沉淀。包括行业分析、竞品分析、最佳实践、原理讲解、叙事文档(Narrative)、战略分析(Strategic Bible)、商业方案、Investor Update、Pitch Deck等
- decision: 决策记录。包括方案对比、技术选型、ADR、评审结论等
- meeting-notes: 会议纪要
- superteam-report: 周报/月报/复盘
- plan: 规划/路线图。包括OKR、迭代排期、里程碑、积分规则、Roadmap等
- changelog: 变更记录/发版说明
- other: 仅用于代码文件(.py/.sql/.html/.csv/.yaml)、原始数据dump、无法识别的内容

重要规则：
1. 英文文档同样适用以上分类，不要因为是英文就归为other
2. Sales Deck、Pitch Deck、Investor Update、Narrative 等归为 explanation
3. Campaign方案、需求v1.0/v2.0 等归为 prd
4. 只有真正的代码/数据文件才归为 other

标题：{title}
内容预览：
{content_preview[:1500]}

类型："""

    try:
        response = Generation.call(
            model=model,
            prompt=prompt,
            result_format='message',
            temperature=0.0,
            top_p=0.8,
            seed=42,
            max_tokens=20
        )
        if response.status_code != 200:
            return classify_by_regex(title, content_preview)

        result = response.output.choices[0].message.content.strip().lower().replace('"', '').replace("'", "")
        for dt in DOC_TYPES:
            if dt in result:
                return dt
        return classify_by_regex(title, content_preview)

    except Exception:
        return classify_by_regex(title, content_preview)


def chunk_with_llm(text: str, title: str = "", model: str = "qwen-plus") -> tuple[list[str], str]:
    """Use DashScope Qwen to semantically chunk text and classify doc_type.

    Returns (chunks, doc_type). On any failure, falls back to local chunking
    with regex classification.
    """
    try:
        import dashscope
        from dashscope import Generation
    except ImportError:
        raise RuntimeError("dashscope SDK not available. Run: pip3 install --user dashscope") from None

    def _fallback(t: str, ti: str) -> tuple[list[str], str]:
        return chunk_smart(t), classify_by_regex(ti, t[:2000])

    # Fallback to local if API key missing
    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("⚠️  DASHSCOPE_API_KEY not set — falling back to local chunking.", file=sys.stderr)
        return _fallback(text, title)

    prompt = f"""你是一个专业的文档处理助手。请将以下长文本按语义主题和逻辑段落切分为多个独立、完整、不重叠的片段（chunks）。每个片段应：
- 表达一个清晰的主题或意图；
- 长度在 300–800 字符之间；
- 不切断句子或代码块；
- 保持原始语言（中文）；
- 输出为严格 JSONL 格式，每行一个对象：{{"text": "..."}}

同时，请判断这篇文档属于以下哪个类型，在第一行的 JSON 中增加 "doc_type" 字段：
- prd: 产品需求文档
- tech-design: 技术方案/架构设计
- reference: 参考手册/API文档
- guide: 指南/教程/操作手册
- explanation: 概念解释/知识沉淀
- decision: 决策记录/方案对比
- meeting-notes: 会议纪要
- superteam-report: 周报/月报/复盘
- plan: 规划/OKR/路线图
- changelog: 变更记录/发版说明
- other: 其他

请只输出 JSONL，不要任何解释、前缀、后缀或 markdown。

=== 文档开始 ===\n{text[:12000]}\n=== 文档结束 ==="""

    try:
        response = Generation.call(
            model=model,
            prompt=prompt,
            result_format='message',
            temperature=0.1,
            top_p=0.8,
            seed=42,
            max_tokens=4096
        )
        if response.status_code != 200:
            print(f"⚠️  LLM API failed: {response.status_code} {response.message}", file=sys.stderr)
            return _fallback(text, title)

        content = response.output.choices[0].message.content.strip()
        chunks = []
        doc_type = ""
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or not line.startswith('{'):
                continue
            try:
                obj = json.loads(line)
                if 'text' in obj and isinstance(obj['text'], str) and obj['text'].strip():
                    chunks.append(obj['text'].strip())
                if not doc_type and obj.get('doc_type'):
                    doc_type = obj['doc_type'].strip()
            except json.JSONDecodeError:
                continue

        if not chunks:
            print("⚠️  LLM returned no valid chunks — falling back to local.", file=sys.stderr)
            return _fallback(text, title)

        # Validate doc_type
        if doc_type not in DOC_TYPES:
            doc_type = classify_by_regex(title, text[:2000])

        return chunks, doc_type

    except Exception as e:
        print(f"⚠️  LLM chunking failed: {e}", file=sys.stderr)
        return _fallback(text, title)
