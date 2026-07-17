"""Shirabe tool 群 — LangChain(``langchain-core``)アダプタ。

Example:
    >>> from shirabe.langchain import shirabe_langchain_tools
    >>> from langchain_openai import ChatOpenAI
    >>> tools = shirabe_langchain_tools()
    >>> model = ChatOpenAI(model="gpt-4o").bind_tools(tools)

optional dependency: ``langchain-core>=0.3.40``(``pip install "shirabe-sdk[langchain]"``)。
利用元チャネルは ``X-Client: langchain`` でサーバー側の計測に伝わる。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .client import DEFAULT_BASE_URL, ShirabeClient, Transport
from .tools import TOOL_SPECS, ShirabeToolSpec

__all__ = ["shirabe_langchain_tools"]


def shirabe_langchain_tools(
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: Optional[float] = None,
    transport: Optional[Transport] = None,
    default_headers: Optional[Dict[str, str]] = None,
) -> List[Any]:
    """LangChain 用の Shirabe tool 群(7 本)を生成する。

    返り値は ``.bind_tools(...)`` や LangGraph の prebuilt agent にそのまま渡せる
    ``StructuredTool`` の配列。各 tool は結果を JSON 文字列で返す(LangChain の
    tool 出力規約に合わせる)。

    Args:
        api_key: 有料プランの API キー(``X-API-Key`` として送信、省略時は匿名)。
        base_url: API のベース URL(既定 ``https://shirabe.dev``)。
        timeout: リクエストタイムアウト秒。
        transport: テスト用の transport 差し替え。
        default_headers: 追加ヘッダー(``X-Client`` を上書き可)。

    Raises:
        ImportError: ``langchain-core`` が未インストールの場合。
    """
    from langchain_core.tools import StructuredTool  # 遅延 import(optional dependency)

    client = _build_client(api_key, base_url, timeout, transport, default_headers, "langchain")

    return [
        StructuredTool.from_function(
            func=_make_func(client, spec),
            name=spec.name,
            description=spec.description,
            args_schema=spec.params_json_schema,
        )
        for spec in TOOL_SPECS
    ]


def _build_client(
    api_key: Optional[str],
    base_url: str,
    timeout: Optional[float],
    transport: Optional[Transport],
    default_headers: Optional[Dict[str, str]],
    x_client: str,
) -> ShirabeClient:
    """``X-Client`` 既定値付きの :class:`ShirabeClient` を組み立てる。"""
    headers: Dict[str, str] = {"X-Client": x_client}
    headers.update(default_headers or {})
    kwargs: Dict[str, Any] = {
        "api_key": api_key,
        "base_url": base_url,
        "transport": transport,
        "default_headers": headers,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    return ShirabeClient(**kwargs)


def _make_func(client: ShirabeClient, spec: ShirabeToolSpec):
    """spec 1 件分の tool 実行関数を束縛する(結果は JSON 文字列)。"""

    def run(**kwargs: Any) -> str:
        return json.dumps(spec.invoke(client, kwargs), ensure_ascii=False)

    return run
