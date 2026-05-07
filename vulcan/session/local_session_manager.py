import json
import uuid
from pathlib import Path
from typing import List

from openai.types.conversations.message import Message
from openai.types.responses.response_input_text import ResponseInputText

from ..types.session import Session, SessionItem
from ..utils.logger import get_logger
from .base_session_manager import BaseSessionManager

logger = get_logger(__name__)


class LocalSessionManager(BaseSessionManager):
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        super().__init__()

    def create_session(self, channel_id: str, session_id: str) -> None:
        channel_path = self.session_dir / channel_id
        if not channel_path.exists():
            channel_path.mkdir(parents=True, exist_ok=True)

        session_file = channel_path / f"{session_id}.jsonl"
        if session_file.exists():
            logger.warning(f"Session {session_file} exist, skip creation.")
        else:
            session_file.touch()

    def append_to_session(
        self,
        channel_id: str,
        session_id: str,
        item: SessionItem,
    ) -> None:
        session_file = self.session_dir / channel_id / f"{session_id}.jsonl"
        if not session_file.exists():
            logger.warning(
                f"Session {session_file} not existing, create it first."
            )
            self.create_session(channel_id=channel_id, session_id=session_id)

        with session_file.open("a") as f:
            f.write(item.model_dump_json() + "\n")

    def get_session(self, channel_id: str, session_id: str) -> Session:
        session_file = self.session_dir / channel_id / f"{session_id}.jsonl"
        if not session_file.exists():
            raise FileNotFoundError(
                f"Session {session_id} does not exist for channel {channel_id}."
            )

        items = []
        with session_file.open("r") as f:
            for line in f:
                item = json.loads(line)
                items.append(item)

        return Session(items=items)

    def delete_session(self, channel_id: str, session_id: str) -> None:
        session_file = self.session_dir / channel_id / f"{session_id}.jsonl"
        if not session_file.exists():
            raise FileNotFoundError(
                f"Session {session_id} does not exist for channel {channel_id}."
            )

        session_file.unlink()

    def get_session_ids(self, channel_id: str) -> List[str]:
        session_ids = []
        channel_path = self.session_dir / channel_id
        if channel_path.exists():
            for file in channel_path.glob("*.jsonl"):
                session_ids.append(file.stem)
        return session_ids

    def assembly_history_messages(
        self, channel_id: str, session_id: str
    ) -> Message:
        """Render the prior transcript as a single user-role `Message` by
        concatenating every JSONL line verbatim (messages, tool calls, tool
        outputs, reasoning — everything). The current turn's user input is
        expected to be appended AFTER this call, so it is not included here.
        """
        session_file = self.session_dir / channel_id / f"{session_id}.jsonl"

        lines: list[str] = []
        if session_file.exists():
            with session_file.open("r") as f:
                for raw in f:
                    raw = raw.strip()
                    if raw:
                        lines.append(raw)

        text = (
            "<previous_conversations>\n"
            + "\n".join(lines)
            + "\n</previous_conversations>"
            if lines
            else ""
        )
        return Message(
            id=str(uuid.uuid4()),
            type="message",
            role="user",
            status="completed",
            content=[ResponseInputText(type="input_text", text=text)],
        )
