"""命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .client import McdMcpClient, McpError
from .render import render_report
from .scan import scan_points_merch, scan_stores

DEFAULT_CITIES = "上海市:南京东路,北京市:王府井,广州市:天河"


def parse_cities(spec: str) -> list[tuple[str, str]]:
    """把 "上海市:南京东路,北京市:王府井" 解析成 [(city, keyword)]。"""
    out: list[tuple[str, str]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            city, kw = part.split(":", 1)
        else:
            city, kw = part, ""
        out.append((city.strip(), kw.strip()))
    return out


def cmd_scan(args: argparse.Namespace) -> int:
    token = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if not token:
        print(
            "错误：未设置环境变量 MCD_MCP_TOKEN。\n"
            "请在 https://open.mcd.cn/mcp 申请 Token 后：\n"
            "  export MCD_MCP_TOKEN='你的Token'",
            file=sys.stderr,
        )
        return 2

    client = McdMcpClient(token=token)
    cities = parse_cities(args.cities)

    results: list[tuple[str, object]] = []
    for city, kw in cities:
        print(f"扫描 {city} {kw} ...", file=sys.stderr)
        try:
            results.append((city, scan_stores(client, city, kw, limit=args.limit)))
        except McpError as exc:
            print(f"  {city} 失败：{exc}", file=sys.stderr)
            return 1

    points = None
    server_now = None
    if args.points:
        print("扫描积分限定周边 ...", file=sys.stderr)
        try:
            points, server_now = scan_points_merch(client, verify=args.verify)
        except McpError as exc:
            print(f"  积分商城失败：{exc}", file=sys.stderr)

    report = render_report(results, points, server_now)  # type: ignore[arg-type]

    if args.json:
        payload = {
            "cities": [
                {
                    "city": c,
                    "stores": [
                        {
                            "storeCode": s.store_code,
                            "storeName": s.store_name,
                            "items": [
                                {
                                    "code": i.code,
                                    "name": i.name,
                                    "price": i.price,
                                    "kind": i.kind,
                                    "categories": i.categories,
                                }
                                for i in s.items
                            ],
                        }
                        for s in r.stores
                    ],
                }
                for c, r in results  # type: ignore[misc]
            ]
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(report)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"\n已写入 {args.out}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="merch-radar",
        description="麦麦周边雷达 · 找出各门店在售的麦当劳周边",
    )
    p.add_argument(
        "--cities",
        default=DEFAULT_CITIES,
        help='城市与定位词，格式 "城市:关键词,城市:关键词"，默认三城',
    )
    p.add_argument("--limit", type=int, default=3, help="每城最多扫描门店数")
    p.add_argument("--points", action="store_true", help="同时扫描积分限定周边")
    p.add_argument(
        "--no-verify",
        dest="verify",
        action="store_false",
        help="跳过 mall-product-detail 二次校验（省调用）",
    )
    p.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    p.add_argument("--out", default="", help="同时把 Markdown 写入文件")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return cmd_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
