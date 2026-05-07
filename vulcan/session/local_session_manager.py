import json
import uuid
from pathlib import Path

from openai.types.conversations.message import Message

from ..types.session import Session, SessionItem
from ..utils.logger import get_logger
from ..utils.messages import user_message
from .base_session_manager import BaseSessionManager

logger = get_logger(__name__)


def _new_session_id() -> str:
    """Generate a short random session id (12 hex chars = 48 bits)."""
    return uuid.uuid4().hex[:12]


class LocalSessionManager(BaseSessionManager):
    """Two-layer identity storage.

    A **conversation** is the stable user-facing address (Feishu chat_id,
    HTTP `X-Conversation-Id` header). It is the thing that persists across
    `/new`. Conversations are tracked by a tiny pointer file at
    `<channel_id>/_conversations/<conversation_id>.json` = ``{"current_session_id": "..."}``.

    A **session** is a concrete transcript — one `<session_id>.jsonl`
    file plus its `<session_id>.meta.json` sidecar, keyed by a random
    12-hex-char id. The meta sidecar stores ``{"runtime_name": "...",
    "conversation_id": "..."}``; the back-pointer to `conversation_id`
    lets us list "all sessions under this conversation" without scanning
    every pointer file.

    `/new` allocates a fresh session and moves the conversation pointer
    to it; `/resume <session_id>` moves the pointer to an existing one.
    """

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        super().__init__()

    # ---- conversation layer -------------------------------------------------

    def resolve_current_session(
        self,
        channel_id: str,
        conversation_id: str,
        default_runtime: str,
    ) -> str:
        """Return the current session id for this conversation.

        If the pointer file is absent (first message on this
        conversation), allocate a fresh session bound to
        ``default_runtime`` and install the pointer.
        """
        existing = self._read_conversation_pointer(channel_id, conversation_id)
        if existing is not None:
            return existing

        session_id = _new_session_id()
        self.create_session(
            channel_id, session_id, default_runtime, conversation_id
        )
        self._write_conversation_pointer(
            channel_id, conversation_id, session_id
        )
        logger.info(
            f"resolved new session: {channel_id}/{conversation_id} "
            f"→ {session_id} (runtime={default_runtime})"
        )
        return session_id

    def rotate_current_session(
        self,
        channel_id: str,
        conversation_id: str,
        default_runtime: str,
    ) -> str:
        """Allocate a fresh session and move the conversation pointer
        to it. The new session inherits the previous session's
        runtime_name; falls back to ``default_runtime`` if there was no
        previous session or its meta is unreadable.
        """
        prev = self._read_conversation_pointer(channel_id, conversation_id)
        if prev is not None:
            inherited = (
                self.get_session_runtime(channel_id, prev) or default_runtime
            )
        else:
            inherited = default_runtime

        session_id = _new_session_id()
        self.create_session(channel_id, session_id, inherited, conversation_id)
        self._write_conversation_pointer(
            channel_id, conversation_id, session_id
        )
        logger.info(
            f"rotated session: {channel_id}/{conversation_id} "
            f"{prev} → {session_id} (runtime={inherited})"
        )
        return session_id

    def set_current_session_id(
        self, channel_id: str, conversation_id: str, session_id: str
    ) -> None:
        """Point a conversation at an existing session (for `/resume`)."""
        self._write_conversation_pointer(
            channel_id, conversation_id, session_id
        )

    def list_conversation_sessions(
        self, channel_id: str, conversation_id: str
    ) -> list[str]:
        """Return session ids belonging to this conversation, newest first
        (by jsonl file ctime). Sessions are identified via their meta
        sidecar's `conversation_id` back-pointer.
        """
        channel_path = self.session_dir / channel_id
        if not channel_path.exists():
            return []

        matches: list[tuple[float, str]] = []
        for meta_file in channel_path.glob("*.meta.json"):
            try:
                data = json.loads(meta_file.read_text())
            except json.JSONDecodeError:
                continue
            if data.get("conversation_id") != conversation_id:
                continue
            sid = meta_file.name.removesuffix(".meta.json")
            jsonl = channel_path / f"{sid}.jsonl"
            if not jsonl.exists():
                continue
            matches.append((jsonl.stat().st_ctime, sid))
        matches.sort(reverse=True)
        return [sid for _, sid in matches]

    def list_conversations(self, channel_id: str) -> list[tuple[str, str]]:
        """Return `(conversation_id, current_session_id)` pairs for this
        channel, sorted by pointer-file mtime (newest first)."""
        conv_dir = self.session_dir / channel_id / "_conversations"
        if not conv_dir.exists():
            return []
        rows: list[tuple[float, str, str]] = []
        for ptr_file in conv_dir.glob("*.json"):
            try:
                data = json.loads(ptr_file.read_text())
            except json.JSONDecodeError:
                continue
            sid = data.get("current_session_id")
            if not isinstance(sid, str):
                continue
            cid = ptr_file.stem
            rows.append((ptr_file.stat().st_mtime, cid, sid))
        rows.sort(reverse=True)
        return [(cid, sid) for _, cid, sid in rows]

    def list_channels(self) -> list[str]:
        """Return channel_ids that have a sessions/ directory on disk."""
        if not self.session_dir.exists():
            return []
        return sorted(d.name for d in self.session_dir.iterdir() if d.is_dir())

    # ---- session layer (existing surface, slightly extended) ----------------

    def create_session(
        self,
        channel_id: str,
        session_id: str,
        runtime_name: str,
        conversation_id: str,
    ) -> None:
        """Idempotently ensure a session's jsonl + meta exist on disk.

        Touches the `.jsonl` if missing and writes the `.meta.json`
        sidecar with ``runtime_name`` and a ``conversation_id``
        back-pointer. Safe to call every turn.
        """
        channel_path = self.session_dir / channel_id
        channel_path.mkdir(parents=True, exist_ok=True)

        session_file = channel_path / f"{session_id}.jsonl"
        if not session_file.exists():
            session_file.touch()
            logger.info(f"created session: {session_file}")

        self._write_session_meta(
            channel_id,
            session_id,
            {
                "runtime_name": runtime_name,
                "conversation_id": conversation_id,
            },
        )

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

    def session_exists(self, channel_id: str, session_id: str) -> bool:
        return (self.session_dir / channel_id / f"{session_id}.jsonl").exists()

    def assembly_history_messages(
        self, channel_id: str, session_id: str
    ) -> Message:
        """Render the prior transcript as a single user-role `Message` by
        concatenating every JSONL line verbatim (messages, tool calls,
        tool outputs, reasoning — everything). The current turn's user
        input is expected to be appended AFTER this call.
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
        meta = self._read_session_meta(channel_id, session_id)
        if meta is None:
            return None
        name = meta.get("runtime_name")
        return name if isinstance(name, str) and name else None

    def get_session_conversation(
        self, channel_id: str, session_id: str
    ) -> str | None:
        meta = self._read_session_meta(channel_id, session_id)
        if meta is None:
            return None
        cid = meta.get("conversation_id")
        return cid if isinstance(cid, str) and cid else None

    def set_session_runtime(
        self, channel_id: str, session_id: str, runtime_name: str
    ) -> None:
        meta = self._read_session_meta(channel_id, session_id) or {}
        meta["runtime_name"] = runtime_name
        self._write_session_meta(channel_id, session_id, meta)

    # ---- private file layout ------------------------------------------------

    def _meta_path(self, channel_id: str, session_id: str) -> Path:
        return self.session_dir / channel_id / f"{session_id}.meta.json"

    def _conversation_pointer_path(
        self, channel_id: str, conversation_id: str
    ) -> Path:
        return (
            self.session_dir
            / channel_id
            / "_conversations"
            / f"{conversation_id}.json"
        )

    def _read_session_meta(
        self, channel_id: str, session_id: str
    ) -> dict | None:
        path = self._meta_path(channel_id, session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            logger.warning(f"malformed session meta: {path}")
            return None
        return data if isinstance(data, dict) else None

    def _write_session_meta(
        self, channel_id: str, session_id: str, data: dict
    ) -> None:
        path = self._meta_path(channel_id, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def _read_conversation_pointer(
        self, channel_id: str, conversation_id: str
    ) -> str | None:
        path = self._conversation_pointer_path(channel_id, conversation_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            logger.warning(f"malformed conversation pointer: {path}")
            return None
        sid = data.get("current_session_id")
        return sid if isinstance(sid, str) and sid else None

    def _write_conversation_pointer(
        self,
        channel_id: str,
        conversation_id: str,
        session_id: str,
    ) -> None:
        path = self._conversation_pointer_path(channel_id, conversation_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"current_session_id": session_id}))
