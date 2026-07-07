"""ShirabeClient (Python) のテスト。標準ライブラリ unittest のみ(依存ゼロ)。

transport を差し替えてネットワークなしで検証する(npm 版の fetch 注入に相当)。
"""

import json
import unittest

from shirabe import ShirabeClient, ShirabeError


class FakeTransport:
    """応答固定の transport。呼び出し引数を records に記録する。"""

    def __init__(self, status=200, body=None):
        self.status = status
        self.text = json.dumps(body if body is not None else {})
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        return self.status, self.text

    @property
    def first(self):
        return self.calls[0]


class TestEnrich(unittest.TestCase):
    def test_posts_record_with_api_key(self):
        t = FakeTransport(200, {"results": {"address": {"status": "ok"}}, "attribution": []})
        client = ShirabeClient(api_key="shrb_lic_abc", transport=t)

        out = client.enrich({"address": "東京都港区六本木6-10-1"})

        self.assertEqual(out["results"]["address"]["status"], "ok")
        call = t.first
        self.assertEqual(call["method"], "POST")
        self.assertEqual(call["url"], "https://shirabe.dev/api/v1/enrich")
        self.assertEqual(call["headers"]["X-API-Key"], "shrb_lic_abc")
        self.assertEqual(call["headers"]["Content-Type"], "application/json")
        # 日本語が UTF-8 バイトで欠損なく送られている。
        self.assertEqual(json.loads(call["body"].decode("utf-8")), {"record": {"address": "東京都港区六本木6-10-1"}})

    def test_includes_fields(self):
        t = FakeTransport(200, {"results": {}, "attribution": []})
        ShirabeClient(transport=t).enrich({"name": "山田太郎"}, fields=["name", "calendar"])
        self.assertEqual(
            json.loads(t.first["body"].decode("utf-8")),
            {"record": {"name": "山田太郎"}, "fields": ["name", "calendar"]},
        )

    def test_omits_api_key_when_anonymous(self):
        t = FakeTransport(200, {"results": {}, "attribution": []})
        ShirabeClient(transport=t).enrich({"date": "2026-07-01"})
        self.assertNotIn("X-API-Key", t.first["headers"])

    def test_raises_on_429_with_license_recommend(self):
        t = FakeTransport(
            429,
            {
                "error": {
                    "code": "ENRICH_TRIAL_LIMIT_EXCEEDED",
                    "message": "trial limit reached",
                    "license_recommend": {"sku": "hub_pro"},
                }
            },
        )
        client = ShirabeClient(transport=t)
        with self.assertRaises(ShirabeError) as ctx:
            client.enrich({"address": "x"})
        err = ctx.exception
        self.assertEqual(err.code, "ENRICH_TRIAL_LIMIT_EXCEEDED")
        self.assertEqual(err.status, 429)
        self.assertEqual(err.body["error"]["license_recommend"]["sku"], "hub_pro")

    def test_raises_on_503_with_results_in_body(self):
        t = FakeTransport(503, {"results": {"address": {"status": "unavailable"}}, "attribution": []})
        with self.assertRaises(ShirabeError) as ctx:
            ShirabeClient(transport=t).enrich({"address": "x"})
        err = ctx.exception
        self.assertEqual(err.status, 503)
        self.assertEqual(err.body["results"]["address"]["status"], "unavailable")


class TestConfig(unittest.TestCase):
    def test_custom_base_url_strips_trailing_slash(self):
        t = FakeTransport(200, {"results": {}, "attribution": []})
        ShirabeClient(base_url="https://staging.shirabe.dev/", transport=t).enrich({"date": "2026-07-01"})
        self.assertEqual(t.first["url"], "https://staging.shirabe.dev/api/v1/enrich")

    def test_sends_user_agent(self):
        t = FakeTransport(200, {"results": {}, "attribution": []})
        ShirabeClient(transport=t).enrich({"date": "2026-07-01"})
        self.assertIn("shirabe-python/", t.first["headers"]["User-Agent"])


class TestConvenience(unittest.TestCase):
    def test_calendar_get_with_categories(self):
        t = FakeTransport(200, {"date": "2026-07-01"})
        ShirabeClient(transport=t).calendar("2026-07-01", categories=["wedding", "moving"])
        call = t.first
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["url"], "https://shirabe.dev/api/v1/calendar/2026-07-01?categories=wedding%2Cmoving")
        self.assertIsNone(call["body"])

    def test_normalize_address_posts(self):
        t = FakeTransport(200, {"result": None, "candidates": []})
        ShirabeClient(transport=t).normalize_address("東京都港区六本木6-10-1")
        self.assertEqual(
            json.loads(t.first["body"].decode("utf-8")), {"address": "東京都港区六本木6-10-1"}
        )


if __name__ == "__main__":
    unittest.main()
