# shirabe-sdk (Python)

Official thin SDK for [Shirabe](https://shirabe.dev) — the Japan-specific, AI-native API platform.
**Zero dependencies in the core** (standard library only). Python 3.8+.

The headline is **composite enrich**: normalize a messy customer record across four Japanese
identifiers — **address, personal name, corporate number, calendar date** — in a single call.
Ready-made **LangChain / OpenAI Agents SDK tools** are available as optional extras
(see [Agent tools](#agent-tools-langchain--openai-agents-sdk)).

```bash
pip install shirabe-sdk
```

The import name stays `shirabe`:

## Quick start

```python
import os
from shirabe import ShirabeClient

shirabe = ShirabeClient(api_key=os.environ.get("SHIRABE_API_KEY"))

out = shirabe.enrich({
    "address": "東京都港区六本木6-10-1 森タワー",
    "name": "山田太郎",
    "corporate_number": "1234567890123",
    "date": "2026-07-01",
})

out["results"]["address"]["status"]   # "ok" | "skipped" | "unavailable" | "error"
out["results"]["name"]["split"]       # {"family": "山田", "given": "太郎", ...}
out["attribution"]                    # aggregated CC BY 4.0 / dictionary attribution (do not strip)
```

`fields` is auto-detected from the record. Pass it explicitly to limit components:

```python
shirabe.enrich({"name": "山田太郎", "date": "2026-07-01"}, fields=["name", "calendar"])
```

## Access & pricing

`enrich` is a **Hub Pro / Hub Enterprise** license capability (`api_key="shrb_lic_..."`),
with an **anonymous trial of 500 calls/month per IP** for evaluation. Each component degrades
independently; if every requested component is unavailable the call raises `ShirabeError` with
HTTP 503 and the per-component `results` available on `err.body`.

See <https://shirabe.dev/pricing> for SKUs and an AI-callable quote endpoint.

## Errors

Non-2xx responses raise `ShirabeError` with the parsed body attached:

```python
from shirabe import ShirabeError

try:
    shirabe.enrich({"address": "..."})
except ShirabeError as err:
    err.code     # e.g. "ENRICH_TRIAL_LIMIT_EXCEEDED"
    err.status   # HTTP status
    err.body["error"]["license_recommend"]  # hub_pro recommendation on 403/429
```

## Other endpoints

```python
shirabe.calendar("2026-07-01", categories=["wedding"])  # 六曜・暦注・用途別スコア
shirabe.normalize_address("東京都港区六本木6-10-1")        # ABR 準拠の住所正規化
shirabe.split_name("山田太郎")                            # 姓名分割(IPAdic、confidence 付き)
shirabe.name_reading("東海林裕子")                        # 読み推定(最頻 + 収載候補の全網羅)
shirabe.validate_corporation("1234567890123")            # 法人番号 検証(checksum + レジストリ実在)
shirabe.lookup_corporation("1234567890123")              # 法人番号 → 商号・所在地・法人種別
shirabe.request("GET", "/api/v1/...")                    # low-level escape hatch
```

## Agent tools (LangChain / OpenAI Agents SDK)

Seven ready-made tools — address normalization, name split/reading, corporate number
validate/lookup, calendar, and composite enrich — generated from a single framework-agnostic
spec (`shirabe.tools`). Most endpoints need **no API key**.

**LangChain** (`pip install "shirabe-sdk[langchain]"`, langchain-core >= 0.3.40):

```python
from shirabe.langchain import shirabe_langchain_tools
from langchain_openai import ChatOpenAI

tools = shirabe_langchain_tools()
model = ChatOpenAI(model="gpt-4o").bind_tools(tools)
```

Works as-is with LangGraph prebuilt agents:

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(ChatOpenAI(model="gpt-4o"), shirabe_langchain_tools())
```

**OpenAI Agents SDK** (`pip install "shirabe-sdk[openai-agents]"`, Python 3.9+):

```python
from agents import Agent, Runner
from shirabe.openai_agents import shirabe_openai_agents_tools

agent = Agent(
    name="assistant",
    instructions="日本のデータは Shirabe tool で裏取りして答える。",
    tools=shirabe_openai_agents_tools(),
)
result = Runner.run_sync(agent, "「東海林裕子」さんの氏名の読みを調べて。")
```

Both factories accept the same options as `ShirabeClient`
(`api_key`, `base_url`, `timeout`, `transport`, `default_headers`).

## Custom transport

For non-standard runtimes or testing, inject a `transport` callable
`(method, url, headers, body, timeout) -> (status, text)`:

```python
ShirabeClient(transport=my_transport, base_url="https://staging.shirabe.dev")
```

## License

MIT © Techwell Inc. Address data normalization is derived from the Digital Agency Address Base
Registry (CC BY 4.0); the `attribution` field returned by the API must not be stripped downstream.
