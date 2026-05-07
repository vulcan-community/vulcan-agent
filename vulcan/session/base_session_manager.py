from abc import ABC, abstractmethod

from openai.types.conversations.message import Message

from ..types.session import Session, SessionItem


class BaseSessionManager(ABC):
    def __init__(self): ...

    # ---- conversation layer -------------------------------------------------

    @abstractmethod
    def resolve_current_session(
        self,
        channel_id: str,
        conversation_id: str,
        default_runtime: str,
    ) -> str: ...

    @abstractmethod
    def rotate_current_session(
        self,
        channel_id: str,
        conversation_id: str,
        default_runtime: str,
    ) -> str: ...

    @abstractmethod
    def set_current_session_id(
        self, channel_id: str, conversation_id: str, session_id: str
    ) -> None: ...

    @abstractmethod
    def list_conversation_sessions(
        self, channel_id: str, conversation_id: str
    ) -> list[str]: ...

    @abstractmethod
    def list_conversations(self, channel_id: str) -> list[tuple[str, str]]: ...

    @abstractmethod
    def list_channels(self) -> list[str]: ...

    # ---- session layer ------------------------------------------------------

    @abstractmethod
    def create_session(
        self,
        channel_id: str,
        session_id: str,
        runtime_name: str,
        conversation_id: str,
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
    def session_exists(self, channel_id: str, session_id: str) -> bool: ...

    @abstractmethod
    def assembly_history_messages(
        self, channel_id: str, session_id: str
    ) -> Message: ...

    @abstractmethod
    def get_session_runtime(
        self, channel_id: str, session_id: str
    ) -> str | None: ...

    @abstractmethod
    def get_session_conversation(
        self, channel_id: str, session_id: str
    ) -> str | None: ...

    @abstractmethod
    def set_session_runtime(
        self, channel_id: str, session_id: str, runtime_name: str
    ) -> None: ...
