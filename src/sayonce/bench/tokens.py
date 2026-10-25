"""Token counting for the benchmark (spec section 8.3).

Uses tiktoken's o200k_base encoding when it is available. tiktoken downloads
the encoding file on first use; if that is not possible (offline machine,
blocked network) we fall back to an approximate counter and say so in the
results (column "tokenizer"). Final report numbers should come from tiktoken.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

_APPROX_RE = re.compile(r"\s?[A-Za-z]+|\s?\d{1,3}|\s?[^\sA-Za-z\d]+|\s+")


class TokenCounter:
    def __init__(self, prefer: str = "o200k_base"):
        self.name = "approx"
        self._enc = None
        try:
            import tiktoken

            self._enc = tiktoken.get_encoding(prefer)
            self.name = prefer
        except Exception:
            self._enc = None

    @property
    def exact(self) -> bool:
        return self._enc is not None

    def encode(self, text: str) -> list[int] | list[str]:
        if self._enc is not None:
            return self._enc.encode(text, disallowed_special=())
        return _approx_tokens(text)

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def count_json(self, obj: Any) -> int:
        """Tokens of an object rendered as compact JSON (how information is 'read')."""
        return self.count(to_text(obj))

    def common_prefix(self, a: str, b: str) -> int:
        """Number of leading tokens two prompts share (what a prefix cache could reuse)."""
        ta, tb = self.encode(a), self.encode(b)
        n = 0
        for x, y in zip(ta, tb):
            if x != y:
                break
            n += 1
        return n


def _approx_tokens(text: str) -> list[str]:
    """Roughly mimics a BPE pre-tokenizer: words, short number groups, punctuation.

    Long words are split into 4-character pieces. Good enough for relative
    comparisons; within about 20% of tiktoken on English JSON.
    """
    out: list[str] = []
    for m in _APPROX_RE.finditer(text):
        piece = m.group()
        if len(piece) > 8 and piece.strip().isalpha():
            out.extend(piece[i : i + 4] for i in range(0, len(piece), 4))
        else:
            out.append(piece)
    return out


def to_text(obj: Any) -> str:
    """Canonical text form of wire information: compact JSON, bytes as hex."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, default=_default)


def _default(o: Any) -> Any:
    if isinstance(o, (bytes, bytearray)):
        return o.hex()
    if hasattr(o, "__int__"):
        return int(o)
    raise TypeError(f"cannot render {type(o).__name__}")


@lru_cache(maxsize=1)
def default_counter() -> TokenCounter:
    return TokenCounter()
