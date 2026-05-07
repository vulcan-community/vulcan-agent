"""ChatCompletion helpers for slash-command replies.

Every command returns the same shape — an assistant-role ChatCompletion
labelled `vulcan-system` — so we wrap it in one helper here.
"""

import time
import uuid

from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

SYSTEM_MODEL = "vulcan-system"


def system_completion(text: str) -> ChatCompletion:
    """Build a single-choice ChatCompletion with `text` as the assistant
    reply and the conventional `vulcan-system` model label."""
    return ChatCompletion(
        id=str(uuid.uuid4()),
        object="chat.completion",
        created=int(time.time()),
        model=SYSTEM_MODEL,
        choices=[
            Choice(
                index=0,
                finish_reason="stop",
                message=ChatCompletionMessage(role="assistant", content=text),
            )
        ],
    )
