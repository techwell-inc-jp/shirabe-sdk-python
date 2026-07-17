"""Shirabe tool 群の共有仕様 — framework 非依存(標準ライブラリのみ)。

``shirabe.langchain``(LangChain)と ``shirabe.openai_agents``(OpenAI Agents SDK)の
両アダプタが、この 1 箇所の仕様(name / description / JSON Schema / invoke)から
tool を生成する。npm 版 ``shirabe-sdk`` の ``tool-specs`` と同一の 7 tool 構成。

依存ゼロを維持するためスキーマは素の JSON Schema dict で持つ(pydantic 不使用)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

from .client import ShirabeClient

__all__ = ["ShirabeToolSpec", "TOOL_SPECS"]

_ENRICH_COMPONENTS = ("address", "name", "corporation", "calendar")


@dataclass(frozen=True)
class ShirabeToolSpec:
    """framework 非依存の tool 仕様。

    Attributes:
        name: tool 名(snake_case、``shirabe_`` prefix)。
        description: LLM 向けの説明(英語、いつ呼ぶべきかを明示)。
        params_json_schema: 入力の JSON Schema(dict)。
        invoke: client と検証済み引数から API を呼ぶ callable。
    """

    name: str
    description: str
    params_json_schema: Dict[str, Any]
    invoke: Callable[[ShirabeClient, Dict[str, Any]], Any]


def _name_schema(example: str) -> Dict[str, Any]:
    """氏名 1 フィールドの JSON Schema を作る。"""
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": f"A Japanese full name, e.g. {example}"},
        },
        "required": ["name"],
    }


def _law_id_schema() -> Dict[str, Any]:
    """法人番号 1 フィールドの JSON Schema を作る。"""
    return {
        "type": "object",
        "properties": {
            "law_id": {
                "type": "string",
                "description": "A 13-digit Japanese corporate number, e.g. 1234567890123",
            },
        },
        "required": ["law_id"],
    }


def _enrich_invoke(client: ShirabeClient, args: Dict[str, Any]) -> Any:
    """enrich 用 invoke(``fields`` を record から分離して渡す)。"""
    record = {k: v for k, v in args.items() if k != "fields" and v is not None}
    fields = args.get("fields")
    return client.enrich(record, fields=fields)


#: Shirabe が公開する tool 群(live で匿名呼出可能なエンドポイントに対応)。
#: すべて日本固有データの「確定値」を構造化 JSON で返す。読み・法人番号など
#: LLM が幻覚しやすい値を、出典付きの権威データで裏取りするのが用途。
TOOL_SPECS: Tuple[ShirabeToolSpec, ...] = (
    ShirabeToolSpec(
        name="shirabe_normalize_address",
        description=(
            "Normalize a Japanese address into structured components (prefecture, city, town, etc.) "
            "using the official ABR (Address Base Registry) data. Returns the canonical form plus "
            "attribution. Use when you need the authoritative parsed form of a Japanese address string."
        ),
        params_json_schema={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "A Japanese address string, e.g. 東京都港区六本木6-10-1",
                },
            },
            "required": ["address"],
        },
        invoke=lambda client, args: client.normalize_address(args["address"]),
    ),
    ShirabeToolSpec(
        name="shirabe_split_name",
        description=(
            "Split a Japanese full name into family name and given name (IPAdic-based). "
            "Use when you have a full Japanese personal name and need the surname/given-name boundary."
        ),
        params_json_schema=_name_schema("山田太郎"),
        invoke=lambda client, args: client.split_name(args["name"]),
    ),
    ShirabeToolSpec(
        name="shirabe_name_reading",
        description=(
            "Estimate the reading (furigana) of a Japanese personal name via IPAdic + JMnedict "
            "two-stage lookup. Japanese name readings are NOT unique, so this returns the most likely "
            "reading PLUS the full set of attested reading candidates and the source. "
            "Use instead of guessing a reading; never assume a single reading."
        ),
        params_json_schema=_name_schema("東海林裕子"),
        invoke=lambda client, args: client.name_reading(args["name"]),
    ),
    ShirabeToolSpec(
        name="shirabe_validate_corporation",
        description=(
            "Validate a Japanese corporate number (houjin bangou, 13 digits): format, mod-9 checksum, "
            "and existence in the National Tax Agency registry. Use to check a corporate number before "
            "trusting it; LLMs frequently miscompute the checksum."
        ),
        params_json_schema=_law_id_schema(),
        invoke=lambda client, args: client.validate_corporation(args["law_id"]),
    ),
    ShirabeToolSpec(
        name="shirabe_lookup_corporation",
        description=(
            "Look up a Japanese corporation by its corporate number (houjin bangou, 13 digits) and return "
            "the registered company name, address, corporate type, and closure info, with attribution. "
            "Use to resolve a corporate number to authoritative company details."
        ),
        params_json_schema=_law_id_schema(),
        invoke=lambda client, args: client.lookup_corporation(args["law_id"]),
    ),
    ShirabeToolSpec(
        name="shirabe_calendar",
        description=(
            "Get Japanese calendar information for a single date: rokuyo (六曜), koyomi notes, zodiac, "
            "solar terms, and per-purpose auspiciousness scores. Use for questions about Japanese "
            "calendar/almanac values on a given date (e.g. is it a good day for a wedding?)."
        ),
        params_json_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "A date in YYYY-MM-DD, e.g. 2026-07-01"},
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional purpose categories to score, e.g. ['wedding','moving']",
                },
            },
            "required": ["date"],
        },
        invoke=lambda client, args: client.calendar(args["date"], categories=args.get("categories")),
    ),
    ShirabeToolSpec(
        name="shirabe_enrich",
        description=(
            "Composite enrichment: normalize a Japanese address, split/read a name, resolve a corporate "
            "number, and look up calendar info in ONE call. Provide any subset of fields. Requires a Hub "
            "Pro/Enterprise license API key (anonymous callers get a 500/month trial). Use when a record "
            "mixes several Japanese identifiers and you want them all normalized together."
        ),
        params_json_schema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Japanese address to normalize"},
                "name": {"type": "string", "description": "Japanese personal name to split/read"},
                "company_name": {
                    "type": "string",
                    "description": "Company name (alternative to corporate_number)",
                },
                "corporate_number": {
                    "type": "string",
                    "description": "13-digit Japanese corporate number",
                },
                "date": {"type": "string", "description": "Date (YYYY-MM-DD) for calendar info"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(_ENRICH_COMPONENTS)},
                    "description": (
                        "Limit which components to process; defaults to those inferred from the record"
                    ),
                },
            },
            "required": [],
        },
        invoke=_enrich_invoke,
    ),
)
