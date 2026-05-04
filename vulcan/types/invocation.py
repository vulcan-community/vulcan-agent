from openai.types.chat import ChatCompletionUserMessageParam
from pydantic import BaseModel

from .session import Session


class InvocationContext(BaseModel):
    user_id: str
    session: Session
    message: ChatCompletionUserMessageParam
