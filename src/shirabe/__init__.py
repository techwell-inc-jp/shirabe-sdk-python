"""Shirabe official thin SDK (Python). Zero dependencies.

See :class:`shirabe.client.ShirabeClient`. The headline is composite ``enrich``.
"""

from .client import (
    DEFAULT_BASE_URL,
    EnrichRecord,
    ShirabeClient,
    ShirabeError,
    Transport,
)

__version__ = "0.1.0"

__all__ = [
    "ShirabeClient",
    "ShirabeError",
    "EnrichRecord",
    "Transport",
    "DEFAULT_BASE_URL",
    "__version__",
]
