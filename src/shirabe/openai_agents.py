"""Shirabe tool 群 — OpenAI Agents SDK(``openai-agents``)アダプタ。

Example:
    >>> from agents import Agent, Runner
    >>> from shirabe.openai_agents import shirabe_openai_agents_tools
    >>> agent = Agent(
    ...     name="assistant",
    ...     instructions="日本のデータは Shirabe tool で裏取りして答える。",
    ...     tools=shirabe_openai_agents_tools(),
    ... )
    >>> result = Runner.run_sync(agent, "「東海林裕子」さんの氏名の読みを調べて。")

optional dependency: ``openai-agents>=0.1``(``pip install "shirabe-sdk[openai-agents]"``、
Python 3.9+)。利用元チャネルは ``X-Client: openai-agents`` でサーバー側の計測に伝わる。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from .client import DEFAULT_BASE_URL, ShirabeClient, Transport
from .langchain import _build_client
from .tools import TOOL_SPECS, ShirabeToolSpec

__all__ = ["shirabe_openai_agents_tools"]


def shirabe_openai_agents_tools(
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: Optional[float] = None,
    transport: Optional[Transport] = None,
    default_headers: Optional[Dict[str, str]] = None,
) -> List[Any]:
    """OpenAI Agents SDK 用の Shirabe tool 群(7 本)を生成する。

    返り値は ``Agent(tools=...)`` にそのまま渡せる ``FunctionTool`` の配列。
    optional フィールド(``shirabe_calendar`` の ``categories`` 等)を保つため
    ``strict_json_schema=False`` で生成する。HTTP 呼出は同期(urllib)のため
    ``asyncio.to_thread`` でイベントループ外に逃がす。

    Args:
        api_key: 有料プランの API キー(``X-API-Key`` として送信、省略時は匿名)。
        base_url: API のベース URL(既定 ``https://shirabe.dev``)。
        timeout: リクエストタイムアウト秒。
        transport: テスト用の transport 差し替え。
        default_headers: 追加ヘッダー(``X-Client`` を上書き可)。

    Raises:
        ImportError: ``openai-agents`` が未インストールの場合。
    """
    from agents import FunctionTool  # 遅延 import(optional dependency)

    client = _build_client(api_key, base_url, timeout, transport, default_headers, "openai-agents")

    return [
        FunctionTool(
            name=spec.name,
            description=spec.description,
            params_json_schema=spec.params_json_schema,
            on_invoke_tool=_make_on_invoke(client, spec),
            strict_json_schema=False,
        )
        for spec in TOOL_SPECS
    ]


def _make_on_invoke(client: ShirabeClient, spec: ShirabeToolSpec):
    """spec 1 件分の ``on_invoke_tool`` callback を束縛する(結果は JSON 文字列)。"""

    async def on_invoke(_ctx: Any, args_json: str) -> str:
        args: Dict[str, Any] = json.loads(args_json) if args_json else {}
        result = await asyncio.to_thread(spec.invoke, client, args)
        return json.dumps(result, ensure_ascii=False)

    return on_invoke
