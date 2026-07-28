"""Streaming helpers: filter Qwen-style <think>...</think> blocks from LLM output.

Kept free of LangChain imports so it is unit-testable with minimal dependencies.
"""

import re


def strip_think(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from a complete text."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


class ThinkFilter:
    """Filters <think>...</think> blocks out of a streamed token sequence.

    Tags can be split across chunks, so a small tail is buffered until it is
    known whether it starts a tag.
    """

    OPEN = "<think>"
    CLOSE = "</think>"

    def __init__(self):
        self.buf = ""
        self.in_think = False

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        out = ""
        while True:
            if self.in_think:
                idx = self.buf.find(self.CLOSE)
                if idx == -1:
                    # Keep only enough tail to detect a split closing tag.
                    self.buf = self.buf[-(len(self.CLOSE) - 1):]
                    return out
                self.buf = self.buf[idx + len(self.CLOSE):]
                self.in_think = False
            else:
                idx = self.buf.find(self.OPEN)
                if idx == -1:
                    # Emit everything except a tail that might begin "<think>".
                    keep = 0
                    for k in range(min(len(self.OPEN) - 1, len(self.buf)), 0, -1):
                        if self.buf.endswith(self.OPEN[:k]):
                            keep = k
                            break
                    emit_upto = len(self.buf) - keep
                    out += self.buf[:emit_upto]
                    self.buf = self.buf[emit_upto:]
                    return out
                out += self.buf[:idx]
                self.buf = self.buf[idx + len(self.OPEN):]
                self.in_think = True

    def flush(self) -> str:
        rest = "" if self.in_think else self.buf
        self.buf = ""
        return rest
