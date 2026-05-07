"""Render a thinking block as a markdown blockquote element."""

from .card_session import CardSession


async def send_streaming_thinking(session: CardSession, text: str) -> None:
    if not text:
        return
    # Close the open text element so subsequent text starts fresh below
    # this thinking block, preserving event order.
    session.open_text_id = None

    quoted = "\n".join(f"> {line}" for line in text.splitlines() if line)
    elem_id = session.new_id("think")
    await session.insert_element(
        {"tag": "markdown", "element_id": elem_id, "content": quoted}
    )
