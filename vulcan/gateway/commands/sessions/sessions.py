from datetime import datetime
from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class SessionsCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="sessions",
            description=(
                "List sessions under this conversation, newest first."
                " `*` marks the current session: /sessions"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        del args
        sess = self._gateway.session_manager
        current = sess.resolve_current_session(
            channel_id,
            conversation_id,
            self._gateway.config.default_runtime,
        )
        session_ids = sess.list_conversation_sessions(
            channel_id, conversation_id
        )

        rows: list[str] = []
        for sid in session_ids:
            jsonl = sess.session_dir / channel_id / f"{sid}.jsonl"
            when = datetime.fromtimestamp(jsonl.stat().st_ctime).isoformat(
                timespec="seconds"
            )
            runtime = sess.get_session_runtime(channel_id, sid) or "—"
            mark = "*" if sid == current else " "
            rows.append(f"  [{mark}] {sid}  {when}  runtime={runtime}")

        header = (
            f"Sessions for {channel_id}/{conversation_id} (current={current}):"
        )
        text = header + "\n" + ("\n".join(rows) if rows else "  (none)")
        return self._reply(text)
