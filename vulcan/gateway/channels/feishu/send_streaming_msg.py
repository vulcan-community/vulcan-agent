"""Stream a text chunk into the active text element of a CardSession.

Consecutive chunks accumulate into one markdown element; non-text events
(thinking, tool) close the open text and force the next text chunk to
start a fresh element.
"""

from .card_session import CardSession


async def send_streaming_msg(session: CardSession, chunk: str) -> None:
    if not chunk:
        return
    session.full_text += chunk
    if session.open_text_id is None:
        elem_id = session.new_id("text")
        session.open_text_buf = chunk
        await session.insert_element(
            {"tag": "markdown", "element_id": elem_id, "content": chunk}
        )
        session.open_text_id = elem_id
    else:
        session.open_text_buf += chunk
        await session.set_content(session.open_text_id, session.open_text_buf)
