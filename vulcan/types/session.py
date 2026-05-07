from openai.types.conversations import ConversationItem
from pydantic import BaseModel

type SessionItem = ConversationItem


class Session(BaseModel):
    """vulcan session, modeled after OpenAI's Conversation.

    `items` is the canonical transcript — the source of truth.
    Each ConversationItem is a discriminated union (by `type`) of:
      - Message              (user / assistant / system text)
      - function_call        (tool call from the model)
      - function_call_output (tool result)
      - reasoning            (model thinking)
      - compaction           (summary of compacted prior items)
      - mcp_call / mcp_*     (MCP tool calls)
      - and more

    Runtimes read items to build their prompt context, and the API server
    appends new items as events stream back from a runtime.
    """

    runtime_name: str | None = None
    items: list[SessionItem]
