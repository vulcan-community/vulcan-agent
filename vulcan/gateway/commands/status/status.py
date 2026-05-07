from typing import TYPE_CHECKING

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


class StatusCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="status",
            description=(
                "Report this conversation's current session plus its"
                " runtime and model configuration: /status"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        del args
        sess = self._gateway.session_manager
        mgr = self._gateway.runtime_manager
        default_runtime = self._gateway.config.default_runtime

        session_id = self._current_session_id(channel_id, conversation_id)
        bound_name = sess.get_session_runtime(channel_id, session_id)
        resolved_name = bound_name or default_runtime
        runtime_label = (
            bound_name
            if bound_name
            else f"(unbound → default: {default_runtime})"
        )

        session_file = sess.session_dir / channel_id / f"{session_id}.jsonl"
        item_count = 0
        if session_file.exists():
            with session_file.open("r") as f:
                for line in f:
                    if line.strip():
                        item_count += 1

        runtime = mgr.get_runtime(resolved_name)
        if runtime is None:
            runtime_status = mgr.status.get(resolved_name, "not-registered")
            runtime_class = "—"
            model_lines = [
                "  name       : —",
                "  provider   : —",
                "  base_url   : —",
                "  api_key    : —",
            ]
        else:
            runtime_status = "enabled"
            runtime_class = type(runtime).__name__
            model = runtime.agent_config.model
            base_url = model.base_url if model.base_url else "(default)"
            api_key_state = (
                "set" if model.api_key else "(empty — using SDK default)"
            )
            model_lines = [
                f"  name       : {model.name}",
                f"  provider   : {model.provider}",
                f"  base_url   : {base_url}",
                f"  api_key    : {api_key_state}",
            ]

        lines = [
            "Conversation:",
            f"  channel         : {channel_id}",
            f"  conversation    : {conversation_id}",
            f"  current session : {session_id}",
            f"  items           : {item_count}",
            f"  runtime         : {runtime_label}",
            "",
            "Runtime:",
            f"  name       : {resolved_name}",
            f"  status     : {runtime_status}",
            f"  class      : {runtime_class}",
            "",
            "Model:",
            *model_lines,
        ]
        return self._reply("\n".join(lines))
