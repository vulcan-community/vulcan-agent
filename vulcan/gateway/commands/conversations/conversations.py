from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class ConversationsCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="conversations",
            description=(
                "List every conversation across all channels."
                " `*` marks the current one: /conversations"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        del args
        sess = self._gateway.session_manager
        try:
            rows: list[str] = []
            for ch in sess.list_channels():
                for cid, current_sid in sess.list_conversations(ch):
                    runtime = sess.get_session_runtime(ch, current_sid) or "—"
                    n = len(sess.list_conversation_sessions(ch, cid))
                    is_curr = ch == channel_id and cid == conversation_id
                    mark = "*" if is_curr else " "
                    rows.append(
                        f"  [{mark}] {ch}/{cid}  current={current_sid} "
                        f"runtime={runtime} sessions={n}"
                    )
            text = "Conversations:\n" + (
                "\n".join(rows) if rows else "  (none)"
            )
            return self._reply(text)
        except Exception as e:
            return self._reply(
                f"Failed to list conversations: {type(e).__name__}: {e}"
            )
