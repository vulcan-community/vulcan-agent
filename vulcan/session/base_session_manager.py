from abc import ABC, abstractmethod

from openai.types.conversations.message import Message

from ..types.session import Session, SessionItem


class BaseSessionManager(ABC):
    def __init__(self): ...

    @abstractmethod
    def create_session(
        self, channel_id: str, session_id: str, runtime_name: str
    ) -> None: ...

    @abstractmethod
    def append_to_session(
        self,
        channel_id: str,
        session_id: str,
        item: SessionItem,
    ) -> None: ...

    @abstractmethod
    def get_session(self, channel_id: str, session_id: str) -> Session: ...

    @abstractmethod
    def delete_session(self, channel_id: str, session_id: str): ...

    @abstractmethod
    def get_session_ids(self, channel_id: str) -> list[str]: ...

    @abstractmethod
    def assembly_history_messages(
        self, channel_id: str, session_id: str
    ) -> Message: ...

    @abstractmethod
    def get_session_runtime(
        self, channel_id: str, session_id: str
    ) -> str | None: ...

    @abstractmethod
    def set_session_runtime(
        self, channel_id: str, session_id: str, runtime_name: str
    ) -> None: ...
