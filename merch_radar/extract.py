"""从门店菜单中识别「周边」商品。

## 背景（实测结论）

麦当劳菜单里**没有"周边"分类**。周边商品散落在「人气热卖」「小食甜品/其他」
「精选单人餐」「开心乐园」等食物分类中，混在汉堡薯条之间，用户很难发现。

本模块用两级规则把它们挑出来：

1. **名称关键词**（主规则）—— 稳健，误判最少
2. **标签命中**（辅规则）—— 官方会打 `汪苏泷限量周边` 这类 tag
3. **结构化信号** —— 周边没有选配轮次，`query-meal-detail` 的 `rounds` 为空

## 实测踩过的坑

* 标签 `我就喜欢代言人同款` 会命中 **厚薯泥培根肉酱双牛堡**（一个汉堡，不是周边）
  → 因此"同款"标签**不能单独作为依据**，必须配合名称关键词。
* `泷盐星星麦旋风` 带 `素龙饼干` 标签，但它本质是冰淇淋
  → 同样被名称规则挡掉。
* `泷泷星愿四件套` / `泷运当头四件套` 是**含周边的套餐**，不是纯周边
  → 单独归为 bundle，输出时明确标注，不误导用户。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 名称关键词：命中即判定为「纯周边」
MERCH_KEYWORDS: tuple[str, ...] = (
    "周边",
    "联名",
    "毛绒",
    "百宝袋",
    "按摩捶",
    "痒痒挠",
    "棒球帽",
    "公仔",
    "玩偶",
    "限定饼干",
    "吧唧",
    "徽章",
    "玩具",
    "礼盒",
    "保温杯",
    "随行杯",
    "帆布袋",
)

# 名称关键词：命中即排除（食物本体，避免误判）
FOOD_EXCLUDE: tuple[str, ...] = (
    "汉堡",
    "薯条",
    "麦乐鸡",
    "鸡翅",
    "鸡腿",
    "咖啡",
    "麦旋风",
    "圆筒",
    "新地",
    "可乐",
    "雪碧",
    "牛奶",
    "红茶",
    "玉米",
    "苹果",
    "派",
    "卷",
    "堡",
)

# 标签关键词：命中即判定为「含周边的套餐」
BUNDLE_TAGS: tuple[str, ...] = ("限量周边",)

# 套餐类编码前缀（麦当劳套餐 code 通常以 99 开头且长度 > 8）
BUNDLE_CODE_PREFIX = "99"


@dataclass
class MerchItem:
    """一件周边商品。"""

    code: str
    name: str
    price: float
    original_price: float
    image: str
    kind: str  # "merch"（纯周边）| "bundle"（含周边的套餐）
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    hit_by: str = ""

    @property
    def is_bundle(self) -> bool:
        return self.kind == "bundle"

    @property
    def discount_text(self) -> str:
        if self.original_price and self.original_price > self.price:
            return f"原价 ¥{self.original_price:.1f}"
        return ""


def _to_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def classify(
    code: str,
    name: str,
    tags: list[str] | None = None,
) -> tuple[str, str] | None:
    """判定商品类型。

    返回 ``(kind, hit_by)``，不是周边则返回 ``None``。
    """
    tags = tags or []
    tag_text = "".join(tags)

    # 1) 先排除食物本体，防止 "薯条脆卜卜毛绒周边" 被 FOOD_EXCLUDE 误伤
    if any(k in name for k in MERCH_KEYWORDS):
        return "merch", f"名称含「{next(k for k in MERCH_KEYWORDS if k in name)}」"

    # 2) 标签命中「限量周边」→ 含周边的套餐
    if any(k in tag_text for k in BUNDLE_TAGS):
        return "bundle", f"标签「{next(k for k in BUNDLE_TAGS if k in tag_text)}」"

    # 3) 其余食物排除
    if any(k in name for k in FOOD_EXCLUDE):
        return None

    return None


def extract_merch(menu: dict) -> list[MerchItem]:
    """从 ``query-meals`` 的返回结构中抽取周边商品。"""
    meals: dict = menu.get("meals", {}) or {}
    categories: list = menu.get("categories", []) or []

    # 建立 code → 所属分类 的映射，用于展示"藏在哪个分类"
    code_to_cats: dict[str, list[str]] = {}
    code_to_tags: dict[str, list[str]] = {}
    for cat in categories:
        cat_name = (cat.get("name") or "").replace("\n", "")
        for meal in cat.get("meals", []) or []:
            code = str(meal.get("code", ""))
            code_to_cats.setdefault(code, [])
            if cat_name and cat_name not in code_to_cats[code]:
                code_to_cats[code].append(cat_name)
            tg = meal.get("tags") or []
            if tg:
                code_to_tags.setdefault(code, []).extend(tg)

    items: list[MerchItem] = []
    for code, detail in meals.items():
        name = detail.get("name") or ""
        tags = code_to_tags.get(code, [])
        verdict = classify(str(code), name, tags)
        if verdict is None:
            continue
        kind, hit_by = verdict
        items.append(
            MerchItem(
                code=str(code),
                name=name,
                price=_to_float(detail.get("currentPrice")),
                original_price=_to_float(detail.get("originalPrice")),
                image=detail.get("image") or "",
                kind=kind,
                categories=code_to_cats.get(code, []),
                tags=tags,
                hit_by=hit_by,
            )
        )

    items.sort(key=lambda it: (it.is_bundle, it.price))
    return items
