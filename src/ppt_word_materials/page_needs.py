from __future__ import annotations

import re


FAMILY_KEYWORDS = {
    "chart": (
        "增长", "比例", "占比", "规模", "亿元", "数量", "目标", "趋势",
        "倍增", "撬动", "实缴", "收益", "绩效", "指标", "2030",
    ),
    "table": (
        "对比", "清单", "职责", "分工", "能力", "指标", "计划", "阶段",
        "时间", "目标", "六类", "五类", "四类", "八项", "矩阵",
    ),
    "diagram": (
        "架构", "体系", "机制", "流程", "路径", "闭环", "环节", "协同",
        "转化", "接口", "链条", "配置", "母基金", "1+4+N", "委托",
    ),
    "image": (
        "产业", "园区", "中心", "区域", "城市", "能源", "电站", "企业",
        "机构", "团队", "项目", "地图", "基础设施",
    ),
    "logo": (
        "机构", "团队", "公司", "管理人", "合作方", "合作伙伴", "联合",
        "尚融资本", "简石资本", "全联并购公会",
    ),
}

PAGE_LABEL = re.compile(r"^第\s*\d+\s*页")
ENTITY_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z]{2,10}?(?:资本|公司|集团|协会|公会|研究院|研究所|科技局)"
)
GENERIC_ENTITIES = {
    "社会资本", "政府投资基金", "政府引导基金", "投资基金", "产业基金",
    "并购基金", "母基金", "子基金", "基金公司",
}
DATA_SIGNALS = ("增长", "比例", "占比", "规模", "亿元", "数量", "目标", "趋势", "指标", "2030")
PROCESS_SIGNALS = ("架构", "体系", "机制", "流程", "路径", "闭环", "环节", "协同", "链条")
CASE_SIGNALS = ("案例", "项目落地", "标杆项目", "典型项目")
SCENE_SIGNALS = ("产业", "园区", "厂房", "基地", "能源", "电站", "城市", "基础设施")
ENTITY_SIGNALS = ("公司介绍", "机构介绍", "管理人", "团队", "合作方", "合作伙伴")


def _title(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return next((line for line in lines if not PAGE_LABEL.match(line)), "")


def _entities(text: str) -> list[str]:
    found: list[str] = []
    for entity in ENTITY_PATTERN.findall(text):
        if entity in GENERIC_ENTITIES or any(term in entity for term in ("投资基金", "引导基金", "产业基金")):
            continue
        if entity not in found:
            found.append(entity)
    return found


def _page_type(number: int, text: str, compact: str, entities: list[str]) -> str:
    title = _title(text)
    if number == 1 and "合作建议" in compact:
        return "cover"
    if number <= 2 and any(marker in compact for marker in ("目录", "报告说明", "阅读指引")):
        return "navigation"
    if re.match(r"^第[一二三四五六七八九十]+部分", title) and len(compact) < 40:
        return "transition"
    if any(signal in text for signal in DATA_SIGNALS) and re.search(r"\d", text):
        return "data"
    if any(signal in text for signal in PROCESS_SIGNALS):
        return "process"
    if entities and (any(signal in title for signal in ENTITY_SIGNALS) or any(entity in title for entity in entities)):
        return "entity"
    if any(signal in text for signal in CASE_SIGNALS):
        return "case"
    if any(signal in text for signal in SCENE_SIGNALS):
        return "scene"
    if any(signal in title for signal in ("总结", "结语", "下一步", "合作建议")):
        return "conclusion"
    return "explanation"


def _intent_for(page_type: str) -> tuple[str, list[int], list[str], list[str]]:
    mapping = {
        "cover": ("none", [0, 0], [], []),
        "navigation": ("none", [0, 0], [], []),
        "transition": ("none", [0, 0], [], []),
        "conclusion": ("light", [0, 2], [], ["structural_visual", "scene_visual"]),
        "data": ("standard", [3, 8], ["factual_visual"], ["structural_visual"]),
        "process": ("standard", [3, 8], ["structural_visual"], ["factual_visual"]),
        "entity": ("standard", [4, 8], ["identity"], ["factual_visual", "scene_visual", "structural_visual"]),
        "case": ("standard", [4, 8], ["scene_visual"], ["identity", "factual_visual"]),
        "scene": ("standard", [4, 8], ["scene_visual"], ["factual_visual", "structural_visual"]),
        "explanation": ("light", [1, 4], [], ["factual_visual", "structural_visual", "scene_visual"]),
    }
    return mapping[page_type]


def build_page_need_card(page: dict[str, object]) -> dict[str, object]:
    number = int(page["number"])
    text = str(page.get("text") or "")
    compact = "".join(text.split())
    entities = _entities(text)
    page_type = _page_type(number, text, compact, entities)
    intensity, candidate_range, required_roles, acceptable_roles = _intent_for(page_type)
    if page_type in {"cover", "navigation", "transition"}:
        return {
            "page": number,
            "page_type": page_type,
            "need_status": "not_needed",
            "visual_intensity": intensity,
            "candidate_range": candidate_range,
            "required_roles": required_roles,
            "acceptable_roles": acceptable_roles,
            "entities": entities,
            "avoid_roles": ["decorative", "forbidden"],
            "preferred_families": [],
            "allowed_families": [],
            "matched_signals": [],
            "reason": "封面、说明或导航页不强制添加原始材料",
        }

    family_hits: dict[str, list[str]] = {}
    for family, keywords in FAMILY_KEYWORDS.items():
        hits = [keyword for keyword in keywords if keyword.lower() in text.lower()]
        if hits:
            family_hits[family] = hits
    preferred = sorted(
        family_hits,
        key=lambda family: (-len(family_hits[family]), family),
    )
    if not preferred:
        preferred = ["diagram", "image"]

    return {
        "page": number,
        "page_type": page_type,
        "need_status": "useful_if_supported",
        "visual_intensity": intensity,
        "candidate_range": candidate_range,
        "required_roles": required_roles,
        "acceptable_roles": acceptable_roles,
        "entities": entities,
        "avoid_roles": ["decorative", "forbidden"],
        "preferred_families": preferred,
        "allowed_families": ["chart", "table", "diagram", "image", "logo"],
        "matched_signals": [
            keyword for family in preferred for keyword in family_hits.get(family, [])
        ][:12],
        "reason": "仅在原始材料直接支持本页主张时添加，允许no_match",
    }


def build_page_need_cards(
    logical_pages: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [build_page_need_card(page) for page in logical_pages]
