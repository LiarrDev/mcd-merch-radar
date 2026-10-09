"""输出渲染：Markdown 报告。"""

from __future__ import annotations

from .scan import MerchAggregate, PointsMerch, ScanResult


def _fmt_ts(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


def short_store(name: str) -> str:
    """把「麦当劳上海黄浦悦荟广场餐厅」压缩成「上海·黄浦悦荟广场」。"""
    s = name.replace("麦当劳", "").strip()
    for suffix in ("餐厅", "店", "分店"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s[:14] or name[:14]


def render_city(result: ScanResult, city: str) -> str:
    """渲染单个城市的门店周边清单。"""
    lines: list[str] = []
    lines.append(f"## {city}")
    lines.append("")

    if not result.stores:
        lines.append("_未找到门店。_")
        lines.append("")
        return "\n".join(lines)

    lines.append(
        f"扫描门店 **{result.ok_stores}/{result.total_stores}** 家，"
        f"共发现 **{len(result.aggregates)}** 款周边。"
    )
    lines.append("")

    if not result.aggregates:
        lines.append("_这些门店当前没有在售周边。_")
        lines.append("")
        for st in result.stores:
            if st.error:
                lines.append(f"- {st.store_name}：{st.error}")
        lines.append("")
        return "\n".join(lines)

    # 分布矩阵
    stores = [s for s in result.stores if not s.error]
    header = "| 周边 | 价格 | " + " | ".join(
        short_store(s.store_name) for s in stores
    ) + " |"
    sep = "|---|---|" + "|".join([":-:"] * len(stores)) + "|"
    lines.append(header)
    lines.append(sep)

    for agg in result.aggregates:
        tag = "（含周边套餐）" if agg.kind == "bundle" else ""
        cells = []
        for s in stores:
            cells.append("✅" if s.store_code in agg.prices else "—")
        lines.append(
            f"| {agg.name}{tag} | {agg.price_range} | " + " | ".join(cells) + " |"
        )
    lines.append("")

    # 门店独享款
    exclusive = [a for a in result.aggregates if a.store_count < len(stores)]
    if exclusive:
        lines.append("**门店差异款**（并非所有门店都有）：")
        lines.append("")
        for agg in exclusive:
            where = [
                s.store_name
                for s in stores
                if s.store_code in agg.prices
            ]
            lines.append(f"- **{agg.name}** — 仅在 {'、'.join(where)}")
        lines.append("")

    # 隐藏位置
    lines.append("**它们藏在哪些分类里：**")
    lines.append("")
    cat_map: dict[str, list[str]] = {}
    for agg in result.aggregates:
        for c in agg.categories:
            cat_map.setdefault(c, []).append(agg.name)
    for cat, names in sorted(cat_map.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"- `{cat}` → {'、'.join(names)}")
    lines.append("")

    for st in result.stores:
        if st.error:
            lines.append(f"> {st.store_name} 扫描失败：{st.error}")
    if any(s.error for s in result.stores):
        lines.append("")

    return "\n".join(lines)


def render_points(items: list[PointsMerch], server_now) -> str:
    """渲染积分商城限定周边。"""
    lines: list[str] = []
    lines.append("## 积分限定周边")
    lines.append("")
    lines.append(f"服务器时间：{_fmt_ts(server_now)}")
    lines.append("")

    if not items:
        lines.append("_当前积分商城没有限定周边在架。_")
        lines.append("")
        return "\n".join(lines)

    lines.append("| 商品 | 积分 | 兑换窗口 | 状态 |")
    lines.append("|---|---:|---|:-:|")
    for it in items:
        window = f"{it.up_time[:16]} → {it.down_time[:16]}"
        mark = "✅ 可兑换" if it.alive else f"❌ {it.note or '已过期'}"
        lines.append(f"| {it.name} | {it.points} | {window} | {mark} |")
    lines.append("")

    stale = [i for i in items if i.status == 2 and not i.alive]
    if stale:
        lines.append(
            f"> ⚠️ 有 **{len(stale)}** 件商品接口标记 `status=2`（上架），"
            "但按兑换窗口比对已过期。列表的 status 字段不可信，"
            "本项目以 `upTime`/`downTime` 与服务器时间比对为准。"
        )
        lines.append("")

    return "\n".join(lines)


def render_report(
    cities: list[tuple[str, ScanResult]],
    points: list[PointsMerch] | None = None,
    server_now=None,
) -> str:
    """渲染完整报告。"""
    lines: list[str] = []
    lines.append("# 📦 麦麦周边雷达")
    lines.append("")

    total = {a.code for _, r in cities for a in r.aggregates}
    stores_ok = sum(r.ok_stores for _, r in cities)
    stores_all = sum(r.total_stores for _, r in cities)
    lines.append(
        f"> 扫描 **{len(cities)}** 座城市 / **{stores_ok}/{stores_all}** 家门店，"
        f"共发现 **{len(total)}** 款在售周边。"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    for city, result in cities:
        lines.append(render_city(result, city))

    if points is not None:
        lines.append("---")
        lines.append("")
        lines.append(render_points(points, server_now))

    lines.append("---")
    lines.append("")
    lines.append("_数据来源：麦当劳中国 MCP · 非麦当劳官方产品_")
    return "\n".join(lines)
