from openai.types.conversations.message import Message
from pydantic import BaseModel


class InvocationContext(BaseModel):
    channel_id: str
    history_message: Message
    message: Message
