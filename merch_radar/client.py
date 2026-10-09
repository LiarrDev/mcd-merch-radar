"""麦当劳 MCP Streamable HTTP 客户端。

只依赖标准库，无第三方依赖。

关键设计：服务端在 JSON-RPC 结果的 ``structuredContent`` 字段里直接返回
业务结构化 JSON，因此本项目**不做 markdown 文本正则解析**，直接取结构化字段。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"


class McpError(RuntimeError):
    """MCP 调用失败。"""


class McdMcpClient:
    """极简 MCP Streamable HTTP 客户端。"""

    def __init__(
        self,
        token: str | None = None,
        url: str = DEFAULT_URL,
        timeout: float = 30.0,
    ) -> None:
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "").strip()
        if not self.token:
            raise McpError(
                "缺少 MCP Token。请设置环境变量 MCD_MCP_TOKEN，"
                "或在 https://open.mcd.cn/mcp 申请。"
            )
        self.url = url
        self.timeout = timeout
        self._id = 0
        self._initialized = False

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # pragma: no cover
            detail = exc.read().decode("utf-8", "ignore")[:300]
            raise McpError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover
            raise McpError(f"网络错误: {exc.reason}") from exc

        # 服务端可能以 SSE 形式返回，取最后一个 data: 行
        if raw.lstrip().startswith("event:") or "data:" in raw[:200]:
            lines = [ln for ln in raw.splitlines() if ln.startswith("data:")]
            if not lines:
                raise McpError("SSE 响应中没有 data 行")
            raw = lines[-1][5:].strip()

        return json.loads(raw)

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def initialize(self) -> dict[str, Any]:
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "mcd-merch-radar", "version": "1.0.0"},
                },
            }
        )
        if "error" in result:
            raise McpError(f"initialize 失败: {result['error']}")
        self._initialized = True
        return result.get("result", {})

    def call(self, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        """调用工具，返回 structuredContent（若有），否则返回 content 文本。"""
        if not self._initialized:
            self.initialize()
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments or {}},
            }
        )
        if "error" in result:
            raise McpError(f"{tool} 调用失败: {result['error']}")
        payload = result.get("result", {})

        structured = payload.get("structuredContent")
        if isinstance(structured, dict):
            if structured.get("success") is False:
                raise McpError(
                    f"{tool} 业务失败: {structured.get('message')} "
                    f"(code={structured.get('code')})"
                )
            return structured.get("data")

        for item in payload.get("content", []):
            if item.get("type") == "text":
                return item.get("text")
        return None
