"""tool 仕様(shirabe.tools)+ 各アダプタのテスト。

core 部分は標準ライブラリのみで検証。アダプタは optional dependency が
インストールされている場合のみ実行する(未インストールなら skip)。
transport 差し替えでネットワークなしで検証する。
"""

import asyncio
import json
import unittest

from shirabe import ShirabeClient
from shirabe.tools import TOOL_SPECS

try:
    import langchain_core  # noqa: F401

    _HAS_LANGCHAIN = True
except ImportError:
    _HAS_LANGCHAIN = False

try:
    import agents  # noqa: F401

    _HAS_AGENTS = True
except ImportError:
    _HAS_AGENTS = False


class FakeTransport:
    """応答固定の transport。呼び出し引数を records に記録する。"""

    def __init__(self, status=200, body=None):
        self.status = status
        self.text = json.dumps(body if body is not None else {"ok": True}, ensure_ascii=False)
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        return self.status, self.text

    @property
    def first(self):
        return self.calls[0]


class TestToolSpecs(unittest.TestCase):
    def test_seven_specs_with_unique_names(self):
        names = [s.name for s in TOOL_SPECS]
        self.assertEqual(len(names), 7)
        self.assertEqual(len(set(names)), 7)
        for n in names:
            self.assertTrue(n.startswith("shirabe_"))

    def test_schemas_are_object_json_schema(self):
        for s in TOOL_SPECS:
            self.assertEqual(s.params_json_schema["type"], "object", s.name)
            self.assertIn("properties", s.params_json_schema, s.name)
            self.assertTrue(s.description, s.name)

    def test_invoke_routes_to_expected_endpoints(self):
        expected = {
            "shirabe_normalize_address": ({"address": "東京都港区六本木6-10-1"}, "/api/v1/address/normalize"),
            "shirabe_split_name": ({"name": "山田太郎"}, "/api/v1/text/name-split"),
            "shirabe_name_reading": ({"name": "東海林裕子"}, "/api/v1/text/name-reading"),
            "shirabe_validate_corporation": ({"law_id": "1234567890123"}, "/api/v1/corporation/validate"),
            "shirabe_lookup_corporation": ({"law_id": "1234567890123"}, "/api/v1/corporation/lookup"),
            "shirabe_calendar": ({"date": "2026-07-17"}, "/api/v1/calendar/2026-07-17"),
            "shirabe_enrich": ({"name": "山田太郎"}, "/api/v1/enrich"),
        }
        for spec in TOOL_SPECS:
            t = FakeTransport()
            client = ShirabeClient(transport=t)
            args, path = expected[spec.name]
            spec.invoke(client, args)
            self.assertTrue(t.first["url"].endswith(path), spec.name)

    def test_enrich_invoke_separates_fields_from_record(self):
        t = FakeTransport()
        client = ShirabeClient(transport=t)
        spec = next(s for s in TOOL_SPECS if s.name == "shirabe_enrich")
        spec.invoke(client, {"name": "山田太郎", "date": "2026-07-17", "fields": ["name"]})
        sent = json.loads(t.first["body"].decode("utf-8"))
        self.assertEqual(sent, {"record": {"name": "山田太郎", "date": "2026-07-17"}, "fields": ["name"]})


class TestClientNewMethods(unittest.TestCase):
    def test_default_headers_are_sent(self):
        t = FakeTransport()
        ShirabeClient(transport=t, default_headers={"X-Client": "langchain"}).split_name("山田太郎")
        self.assertEqual(t.first["headers"]["X-Client"], "langchain")

    def test_new_methods_post_utf8_body(self):
        t = FakeTransport()
        ShirabeClient(transport=t).name_reading("東海林裕子")
        self.assertEqual(t.first["method"], "POST")
        self.assertEqual(json.loads(t.first["body"].decode("utf-8")), {"name": "東海林裕子"})


@unittest.skipUnless(_HAS_LANGCHAIN, "langchain-core が未インストール")
class TestLangChainAdapter(unittest.TestCase):
    def test_generates_seven_structured_tools(self):
        from shirabe.langchain import shirabe_langchain_tools

        tools = shirabe_langchain_tools(transport=FakeTransport())
        self.assertEqual(len(tools), 7)
        self.assertEqual({t.name for t in tools}, {s.name for s in TOOL_SPECS})

    def test_invoke_returns_json_string_and_sends_x_client(self):
        from shirabe.langchain import shirabe_langchain_tools

        t = FakeTransport(200, {"reading": "しょうじゆうこ"})
        tools = shirabe_langchain_tools(transport=t)
        tool = next(x for x in tools if x.name == "shirabe_name_reading")

        out = tool.invoke({"name": "東海林裕子"})

        self.assertIsInstance(out, str)
        self.assertEqual(json.loads(out), {"reading": "しょうじゆうこ"})
        self.assertEqual(t.first["headers"]["X-Client"], "langchain")


@unittest.skipUnless(_HAS_AGENTS, "openai-agents が未インストール")
class TestOpenAIAgentsAdapter(unittest.TestCase):
    def test_generates_seven_function_tools(self):
        from agents import FunctionTool

        from shirabe.openai_agents import shirabe_openai_agents_tools

        tools = shirabe_openai_agents_tools(transport=FakeTransport())
        self.assertEqual(len(tools), 7)
        for tool in tools:
            self.assertIsInstance(tool, FunctionTool)
            self.assertFalse(tool.strict_json_schema)

    def test_on_invoke_returns_json_string_and_sends_x_client(self):
        from shirabe.openai_agents import shirabe_openai_agents_tools

        t = FakeTransport(200, {"rokuyo": {"name": "先負"}})
        tools = shirabe_openai_agents_tools(transport=t)
        tool = next(x for x in tools if x.name == "shirabe_calendar")

        out = asyncio.run(tool.on_invoke_tool(None, json.dumps({"date": "2026-07-17"})))

        self.assertEqual(json.loads(out), {"rokuyo": {"name": "先負"}})
        self.assertEqual(t.first["headers"]["X-Client"], "openai-agents")


if __name__ == "__main__":
    unittest.main()
