"""Factory helpers and text utilities for OpenAI `SessionItem` variants.

Runtimes and the gateway build the same four shapes over and over —
assistant-role `Message`, `ResponseReasoningItem`, tool call, and tool
output. Keep the construction in one place so call sites stay focused on
what the runtime is actually emitting.
"""

import json
import uuid

from openai.types.conversations.message import Message
from openai.types.responses.response_function_tool_call_item import (
    ResponseFunctionToolCallItem,
)
from openai.types.responses.response_function_tool_call_output_item import (
    ResponseFunctionToolCallOutputItem,
)
from openai.types.responses.response_input_text import ResponseInputText
from openai.types.responses.response_output_text import ResponseOutputText
from openai.types.responses.response_reasoning_item import (
    Content as ReasoningContent,
)
from openai.types.responses.response_reasoning_item import (
    ResponseReasoningItem,
)


def message_text(msg: Message) -> str:
    """Concatenate the `text` of every content block on `msg`."""
    return "".join(getattr(c, "text", "") for c in msg.content)


def user_message(text: str) -> Message:
    """Build a user-role `Message` with a single `input_text` block."""
    return Message(
        id=str(uuid.uuid4()),
        type="message",
        role="user",
        status="completed",
        content=[ResponseInputText(type="input_text", text=text)],
    )


def assistant_message(text: str) -> Message:
    """Build an assistant-role `Message` with a single `output_text` block."""
    return Message(
        id=str(uuid.uuid4()),
        type="message",
        role="assistant",
        status="completed",
        content=[
            ResponseOutputText(type="output_text", text=text, annotations=[])
        ],
    )


def reasoning_item(text: str) -> ResponseReasoningItem:
    """Build a `ResponseReasoningItem` with a single reasoning-text block."""
    return ResponseReasoningItem(
        id=str(uuid.uuid4()),
        type="reasoning",
        summary=[],
        content=[ReasoningContent(type="reasoning_text", text=text)],
    )


def tool_call_item(
    call_id: str, name: str, arguments: dict | str
) -> ResponseFunctionToolCallItem:
    """Build a function_call SessionItem. `arguments` is JSON-encoded if
    given as a dict; passed through verbatim if already a string."""
    if isinstance(arguments, str):
        args_json = arguments
    else:
        args_json = json.dumps(arguments, ensure_ascii=False)
    return ResponseFunctionToolCallItem(
        id=str(uuid.uuid4()),
        type="function_call",
        call_id=call_id,
        name=name,
        arguments=args_json,
        status="completed",
    )


def tool_output_item(
    call_id: str, output: str, is_error: bool = False
) -> ResponseFunctionToolCallOutputItem:
    """Build a function_call_output SessionItem."""
    return ResponseFunctionToolCallOutputItem(
        id=str(uuid.uuid4()),
        type="function_call_output",
        call_id=call_id,
        output=output,
        status="incomplete" if is_error else "completed",
    )
