import json
from pathlib import Path
from typing import List

from ..types.session import Session, SessionItem
from ..utils.logger import get_logger
from .base_session_manager import BaseSessionManager

logger = get_logger(__name__)


class LocalSessionManager(BaseSessionManager):
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        super().__init__()

    def create_session(self, user_id: str, session_id: str) -> None:
        user_path = self.session_dir / user_id
        if not user_path.exists():
            user_path.mkdir(parents=True, exist_ok=True)

        user_session_file = user_path / f"{session_id}.jsonl"
        if user_session_file.exists():
            logger.warning(f"Session {user_session_file} exist, skip creation.")
        else:
            user_session_file.touch()

    def append_to_session(
        self,
        user_id: str,
        session_id: str,
        item: SessionItem,
    ) -> None:
        user_session_file = self.session_dir / user_id / f"{session_id}.jsonl"
        if not user_session_file.exists():
            logger.warning(
                f"Session {user_session_file} not existing, create it first."
            )
            self.create_session(user_id=user_id, session_id=session_id)

        with user_session_file.open("a") as f:
            f.write(item.model_dump_json() + "\n")

    def get_session(self, user_id: str, session_id: str) -> Session:
        user_session_file = self.session_dir / user_id / f"{session_id}.jsonl"
        if not user_session_file.exists():
            raise FileNotFoundError(
                f"Session {session_id} does not exist for user {user_id}."
            )

        items = []
        with user_session_file.open("r") as f:
            for line in f:
                item = json.loads(line)
                items.append(item)

        return Session(items=items)

    def delete_session(self, user_id: str, session_id: str) -> None:
        user_session_file = self.session_dir / user_id / f"{session_id}.jsonl"
        if not user_session_file.exists():
            raise FileNotFoundError(
                f"Session {session_id} does not exist for user {user_id}."
            )

        user_session_file.unlink()

    def get_session_ids(self, user_id: str) -> List[str]:
        session_ids = []
        user_path = self.session_dir / user_id
        if user_path.exists():
            for file in user_path.glob("*.jsonl"):
                session_ids.append(file.stem)
        return session_ids
