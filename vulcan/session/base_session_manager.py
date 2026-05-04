from abc import ABC, abstractmethod
from typing import List

from ..types.session import Session, SessionItem


class BaseSessionManager(ABC):
    def __init__(self): ...

    @abstractmethod
    def create_session(self, user_id: str, session_id: str) -> None: ...

    @abstractmethod
    def append_to_session(
        self,
        user_id: str,
        session_id: str,
        item: SessionItem,
    ) -> None: ...

    @abstractmethod
    def get_session(self, user_id: str, session_id: str) -> Session: ...

    @abstractmethod
    def delete_session(self, user_id: str, session_id: str): ...

    @abstractmethod
    def get_session_ids(self, user_id: str) -> List[str]: ...
