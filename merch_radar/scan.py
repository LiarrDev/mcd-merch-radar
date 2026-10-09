"""扫描与聚合：多门店周边分布 + 积分限定周边监控。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .client import McdMcpClient
from .extract import MerchItem, extract_merch


@dataclass
class StoreHit:
    """一家门店的扫描结果。"""

    store_code: str
    store_name: str
    address: str
    items: list[MerchItem] = field(default_factory=list)
    error: str = ""


@dataclass
class MerchAggregate:
    """一款周边在所有被扫描门店中的分布。"""

    code: str
    name: str
    image: str
    kind: str
    prices: dict[str, float] = field(default_factory=dict)  # store_code → price
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def store_count(self) -> int:
        return len(self.prices)

    @property
    def price_range(self) -> str:
        vals = [v for v in self.prices.values() if v]
        if not vals:
            return "—"
        lo, hi = min(vals), max(vals)
        return f"¥{lo:.1f}" if lo == hi else f"¥{lo:.1f} – ¥{hi:.1f}"


@dataclass
class ScanResult:
    stores: list[StoreHit] = field(default_factory=list)
    aggregates: list[MerchAggregate] = field(default_factory=list)
    total_stores: int = 0
    ok_stores: int = 0


def scan_stores(
    client: McdMcpClient,
    city: str,
    keyword: str = "",
    limit: int = 3,
    be_type: int = 1,
) -> ScanResult:
    """扫描一个城市若干门店的在售周边。"""
    result = ScanResult()

    raw_stores = client.call(
        "query-nearby-stores",
        {
            "beType": be_type,
            "searchType": 2 if keyword else 1,
            "city": city,
            "keyword": keyword,
        },
    )
    stores = (raw_stores or [])[:limit] if isinstance(raw_stores, list) else []
    result.total_stores = len(stores)

    for st in stores:
        hit = StoreHit(
            store_code=str(st.get("storeCode", "")),
            store_name=st.get("storeName", ""),
            address=st.get("address", ""),
        )
        try:
            menu = client.call(
                "query-meals",
                {
                    "storeCode": hit.store_code,
                    "orderType": 1,
                    "beType": be_type,
                },
            )
            if isinstance(menu, dict):
                hit.items = extract_merch(menu)
                result.ok_stores += 1
            else:
                hit.error = "菜单返回为空"
        except Exception as exc:  # noqa: BLE001
            hit.error = str(exc)[:160]
        result.stores.append(hit)

    result.aggregates = _aggregate(result.stores)
    return result


def _aggregate(stores: list[StoreHit]) -> list[MerchAggregate]:
    """把各门店结果聚合成「一款周边 × 哪些店有」。"""
    table: dict[str, MerchAggregate] = {}
    for st in stores:
        for it in st.items:
            agg = table.get(it.code)
            if agg is None:
                agg = MerchAggregate(
                    code=it.code,
                    name=it.name,
                    image=it.image,
                    kind=it.kind,
                    categories=list(it.categories),
                    tags=list(it.tags),
                )
                table[it.code] = agg
            if it.price:
                agg.prices[st.store_code] = it.price
            for c in it.categories:
                if c not in agg.categories:
                    agg.categories.append(c)

    rows = list(table.values())
    rows.sort(key=lambda a: (-a.store_count, a.kind != "merch", a.name))
    return rows


@dataclass
class PointsMerch:
    """积分商城的限定周边。"""

    spu_id: int
    name: str
    points: int
    up_time: str
    down_time: str
    cat_name: str
    image: str
    selling: str
    status: int
    alive: bool = False
    verified: bool = False
    note: str = ""


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def scan_points_merch(
    client: McdMcpClient,
    cat_rule_ids: str = "2>8",
    verify: bool = True,
) -> tuple[list[PointsMerch], datetime | None]:
    """扫描积分商城限定周边。

    返回 ``(商品列表, 服务器时间)``。

    关键点：列表接口的 ``status=2``（上架）**不可信** —— 实测多件商品
    早已过期却仍标记为 2。因此这里做了两层校正：

    1. 用 ``upTime`` / ``downTime`` 与服务器真实时间比对
    2. 可选：调 ``mall-product-detail`` 二次校验（过期商品会返回"商品已下架"）
    """
    server_now = None
    try:
        info = client.call("now-time-info", {})
        if isinstance(info, dict):
            server_now = _parse_time(info.get("formatted", ""))
    except Exception:  # noqa: BLE001
        pass

    raw = client.call("mall-points-products", {"catRuleIds": cat_rule_ids})
    rows = raw if isinstance(raw, list) else []

    out: list[PointsMerch] = []
    for r in rows:
        up = r.get("upTime", "") or ""
        down = r.get("downTime", "") or ""
        dt_up, dt_down = _parse_time(up), _parse_time(down)
        alive = True
        if server_now:
            if dt_up and server_now < dt_up:
                alive = False
            if dt_down and server_now > dt_down:
                alive = False

        item = PointsMerch(
            spu_id=int(r.get("spuId") or 0),
            name=r.get("spuName", ""),
            points=int(r.get("point") or 0),
            up_time=up,
            down_time=down,
            cat_name=r.get("catName", ""),
            image=r.get("spuImage", ""),
            selling=r.get("selling", ""),
            status=int(r.get("status") or 0),
            alive=alive,
        )

        if not alive:
            item.note = "已过兑换期"
        elif verify:
            item.verified = True
            try:
                client.call("mall-product-detail", {"spuId": item.spu_id})
                item.note = "详情校验通过"
            except Exception as exc:  # noqa: BLE001
                item.verified = False
                item.alive = False
                item.note = f"详情校验失败：{str(exc)[:60]}"

        out.append(item)

    out.sort(key=lambda x: (not x.alive, x.points))
    return out, server_now
