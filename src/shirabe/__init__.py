"""Shirabe official thin SDK (Python). Zero dependencies in the core.

See :class:`shirabe.client.ShirabeClient`. The headline is composite ``enrich``.

Ready-made agent tools (optional extras):

- ``shirabe.langchain.shirabe_langchain_tools`` — LangChain (``pip install "shirabe-sdk[langchain]"``)
- ``shirabe.openai_agents.shirabe_openai_agents_tools`` — OpenAI Agents SDK
  (``pip install "shirabe-sdk[openai-agents]"``)
"""

from .client import (
    DEFAULT_BASE_URL,
    EnrichRecord,
    ShirabeClient,
    ShirabeError,
    Transport,
)

__version__ = "0.2.0"

__all__ = [
    "ShirabeClient",
    "ShirabeError",
    "EnrichRecord",
    "Transport",
    "DEFAULT_BASE_URL",
    "__version__",
]
