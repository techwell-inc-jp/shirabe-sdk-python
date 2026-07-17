"""Shirabe official thin SDK — 依存ゼロ(標準ライブラリのみ)の型付きクライアント。

目玉は複合 enrich(``POST /api/v1/enrich``): 住所・人名・法人番号・暦を 1 メソッド
``client.enrich(record)`` で横断正規化する。coding agent が PyPI からそのまま利用できる。

ランタイム依存ゼロ(``urllib`` を使用)。日本語 body は UTF-8 バイト + UA 付きで送る。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict

__all__ = [
    "ShirabeClient",
    "ShirabeError",
    "EnrichRecord",
    "Transport",
    "DEFAULT_BASE_URL",
]

DEFAULT_BASE_URL = "https://shirabe.dev"
_DEFAULT_TIMEOUT = 8.0
_USER_AGENT = "shirabe-python/0.2.0"


class EnrichRecord(TypedDict, total=False):
    """enrich の入力レコード。全フィールド optional、1 つ以上必須。"""

    address: str
    name: str
    company_name: str
    corporate_number: str
    date: str


# transport: (method, url, headers, body_bytes, timeout) -> (status, text)
# テストや非標準ランタイム向けに差し替え可能(npm 版の fetch 注入に相当)。
Transport = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, str]]


class ShirabeError(Exception):
    """Shirabe API が非 2xx を返したときに送出される例外。

    ``body`` に解析済みレスポンス本体を保持するため、429/403 の ``license_recommend`` や
    503 の per-component ``results`` を except 側で参照できる。
    """

    def __init__(self, message: str, code: str, status: int, body: Any) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.body = body


def _urllib_transport(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[bytes],
    timeout: float,
) -> Tuple[int, str]:
    """標準ライブラリ urllib による既定 transport。

    HTTPError(4xx/5xx)は (status, text) に正規化して返し、上位で ShirabeError に変換させる。
    ネットワーク到達不能は ShirabeError(status=0)に変換する。
    """
    req = urllib.request.Request(url=url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8") if exc.fp is not None else ""
        return exc.code, text
    except urllib.error.URLError as exc:
        raise ShirabeError(f"network error: {exc.reason}", "NETWORK_ERROR", 0, None) from exc


class ShirabeClient:
    """Shirabe API クライアント(thin、依存ゼロ)。

    Example:
        >>> shirabe = ShirabeClient(api_key="shrb_lic_...")
        >>> out = shirabe.enrich({
        ...     "address": "東京都港区六本木6-10-1",
        ...     "name": "山田太郎",
        ...     "corporate_number": "1234567890123",
        ...     "date": "2026-07-01",
        ... })
        >>> out["results"]["address"]["status"]
        'ok'
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        transport: Optional[Transport] = None,
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_headers: Dict[str, str] = dict(default_headers or {})
        self._transport: Transport = transport or _urllib_transport

    def enrich(
        self,
        record: EnrichRecord,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """複合 enrich — 住所・人名・法人番号・暦を 1 コールで横断正規化する。

        Hub Pro/Enterprise license 専用(匿名は体験枠 500 回/月/IP)。component は部分成功し、
        全 component 利用不能(HTTP 503)時は :class:`ShirabeError`(``body['results']`` 参照可)。

        Args:
            record: 1 つ以上のフィールドを持つレコード。
            fields: 対象 component の明示指定(省略時は record から自動推定)。

        Returns:
            合成結果(``results`` + 集約 ``attribution``)。

        Raises:
            ShirabeError: 非 2xx(400/401/403/429/503)時。
        """
        payload: Dict[str, Any] = {"record": record}
        if fields is not None:
            payload["fields"] = list(fields)
        return self.request("POST", "/api/v1/enrich", body=payload)

    def calendar(
        self,
        date: str,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """単日の暦情報(六曜・暦注・干支・二十四節気・用途別スコア)を取得する。"""
        query = ""
        if categories:
            from urllib.parse import quote

            query = "?categories=" + quote(",".join(categories))
        return self.request("GET", f"/api/v1/calendar/{date}{query}")

    def normalize_address(self, address: str) -> Dict[str, Any]:
        """単一住所を正規化する(ABR 準拠、CC BY 4.0 attribution 同梱)。"""
        return self.request("POST", "/api/v1/address/normalize", body={"address": address})

    def split_name(self, name: str) -> Dict[str, Any]:
        """日本人の氏名を姓・名に分割する(IPAdic ベース、confidence 同梱)。"""
        return self.request("POST", "/api/v1/text/name-split", body={"name": name})

    def name_reading(self, name: str) -> Dict[str, Any]:
        """氏名の読み(ふりがな)を推定する。

        読みは非一意のため、最頻の ``reading`` に加え収載読みの全候補 ``candidates`` と
        出典(``attribution``)を返す。
        """
        return self.request("POST", "/api/v1/text/name-reading", body={"name": name})

    def validate_corporation(self, law_id: str) -> Dict[str, Any]:
        """法人番号(13 桁)を検証する(形式 + チェックディジット + レジストリ実在)。"""
        return self.request("POST", "/api/v1/corporation/validate", body={"law_id": law_id})

    def lookup_corporation(self, law_id: str) -> Dict[str, Any]:
        """法人番号から登記上の商号・所在地・法人種別を照会する(attribution 同梱)。"""
        return self.request("POST", "/api/v1/corporation/lookup", body={"law_id": law_id})

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """低レベルリクエスト(任意の Shirabe エンドポイントを叩く escape hatch)。

        Raises:
            ShirabeError: 非 2xx 時(``body`` を保持)。
        """
        headers: Dict[str, str] = {"Accept": "application/json", "User-Agent": _USER_AGENT}
        headers.update(self.default_headers)
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        data: Optional[bytes] = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            # ensure_ascii=False + utf-8 で日本語をそのまま送る(MSYS curl の byte 化け回避と同方針)。
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        status, text = self._transport(method, self.base_url + path, headers, data, self.timeout)
        parsed = _parse_body(text)

        if not 200 <= status < 300:
            raise ShirabeError(_error_message(parsed, status), _error_code(parsed), status, parsed)
        return parsed


def _parse_body(text: str) -> Any:
    """レスポンス本体を JSON として解析する(JSON でなければ文字列、空なら None)。"""
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


def _error_code(body: Any) -> str:
    """解析済み body から ``error.code`` を取り出す(無ければ "HTTP_ERROR")。"""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and isinstance(err.get("code"), str):
            return err["code"]
    return "HTTP_ERROR"


def _error_message(body: Any, status: int) -> str:
    """解析済み body から ``error.message`` を取り出す(無ければ status からの既定文)。"""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and isinstance(err.get("message"), str):
            return err["message"]
    return f"Shirabe API responded {status}"
