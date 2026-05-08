"""Accumulate thinking chunks into a single markdown blockquote element.

Runtimes with token-level streaming (e.g. `ClaudeCodeRuntime` with
`include_partial_messages=True`) emit one `ResponseReasoningItem` per
delta. Without accumulation, each delta would get its own card element
and the thinking block would render as a stacked column of one-token
blockquotes. Mirrors `send_streaming_msg`'s behavior for text.
"""

from .card_session import CardSession


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" for line in text.splitlines() if line.strip())


async def send_streaming_thinking(session: CardSession, text: str) -> None:
    if not text:
        return
    # A thinking chunk closes any open text element so subsequent text
    # starts a fresh element below this block.
    session.open_text_id = None

    buf = session.open_think_buf + text
    quoted = _quote(buf)
    if session.open_think_id is None:
        elem_id = session.new_id("think")
        await session.insert_element(
            {"tag": "markdown", "element_id": elem_id, "content": quoted}
        )
        session.open_think_id = elem_id
    else:
        await session.set_content(session.open_think_id, quoted)
    session.open_think_buf = buf
