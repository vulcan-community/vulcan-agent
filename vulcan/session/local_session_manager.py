import json
from pathlib import Path

from openai.types.conversations.message import Message

from ..types.session import Session, SessionItem
from ..utils.logger import get_logger
from ..utils.messages import user_message
from .base_session_manager import BaseSessionManager

logger = get_logger(__name__)


class LocalSessionManager(BaseSessionManager):
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        super().__init__()

    def create_session(
        self, channel_id: str, session_id: str, runtime_name: str
    ) -> None:
        """Idempotently ensure a session exists and is bound to a runtime.

        Creates the channel directory, touches the `.jsonl` transcript (if
        missing), and writes the `.meta.json` sidecar with `runtime_name`.
        Safe to call every turn — existing transcripts are not touched,
        and re-binding is as cheap as overwriting the meta file.
        """
        channel_path = self.session_dir / channel_id
        channel_path.mkdir(parents=True, exist_ok=True)

        session_file = channel_path / f"{session_id}.jsonl"
        if not session_file.exists():
            session_file.touch()
            logger.info(f"created session: {session_file}")

        self.set_session_runtime(channel_id, session_id, runtime_name)

    def append_to_session(
        self,
        channel_id: str,
        session_id: str,
        item: SessionItem,
    ) -> None:
        session_file = self.session_dir / channel_id / f"{session_id}.jsonl"
        assert session_file.exists(), (
            f"session {session_file} must be created via create_session()"
            " before appending"
        )
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

        return Session(
            runtime_name=self.get_session_runtime(channel_id, session_id),
            items=items,
        )

    def delete_session(self, channel_id: str, session_id: str) -> None:
        session_file = self.session_dir / channel_id / f"{session_id}.jsonl"
        if not session_file.exists():
            raise FileNotFoundError(
                f"Session {session_id} does not exist for channel {channel_id}."
            )

        session_file.unlink()
        meta_file = self._meta_path(channel_id, session_id)
        if meta_file.exists():
            meta_file.unlink()

    def get_session_ids(self, channel_id: str) -> list[str]:
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
        return user_message(text)

    def get_session_runtime(
        self, channel_id: str, session_id: str
    ) -> str | None:
        """Return the runtime name bound to this session, or None if the
        sidecar meta file is missing or malformed."""
        meta_file = self._meta_path(channel_id, session_id)
        if not meta_file.exists():
            return None
        try:
            data = json.loads(meta_file.read_text())
        except json.JSONDecodeError:
            logger.warning(f"malformed session meta: {meta_file}")
            return None
        name = data.get("runtime_name")
        return name if isinstance(name, str) and name else None

    def set_session_runtime(
        self, channel_id: str, session_id: str, runtime_name: str
    ) -> None:
        """Persist the runtime binding for this session to its sidecar
        meta file. Creates the channel directory on demand."""
        meta_file = self._meta_path(channel_id, session_id)
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        meta_file.write_text(json.dumps({"runtime_name": runtime_name}))

    def _meta_path(self, channel_id: str, session_id: str) -> Path:
        return self.session_dir / channel_id / f"{session_id}.meta.json"
