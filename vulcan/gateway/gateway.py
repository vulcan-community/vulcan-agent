import shutil
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import uvicorn
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.conversations.message import Message

from ..api_server.app import VulcanAPIServer
from ..runtime.runtime_manager import RuntimeManager
from ..session.local_session_manager import LocalSessionManager
from ..types.agent import AgentConfig, Instruction
from ..types.gateway import GatewayConfig
from ..types.invocation import InvocationContext
from ..types.session import SessionItem
from ..utils.logger import get_logger
from ..utils.messages import assistant_message, message_text
from .commands.command_manager import CommandManager

logger = get_logger(__name__)


def prepare_home_dir(home_dir: Path):
    template_dir = Path(__file__).resolve().parent.parent / "template"
    home_dir.mkdir(parents=True, exist_ok=True)

    for item in template_dir.iterdir():
        target = home_dir / item.name
        if target.exists():
            continue

        elif item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    logger.info(f"home dir ready: {home_dir}")


class Gateway:
    def __init__(self, home_dir: Path) -> None:
        logger.info(f"initializing gateway, home_dir={home_dir}")
        self.home_dir = home_dir
        prepare_home_dir(home_dir)

        self.session_manager = LocalSessionManager(
            session_dir=home_dir / "sessions"
        )

        self.config = GatewayConfig.model_validate_json(
            (home_dir / "vulcan.json").read_text()
        )

        self.identity_str = (home_dir / "agent" / "IDENTITY.md").read_text()
        self.soul_str = (home_dir / "agent" / "SOUL.md").read_text()
        self.tool_str = (home_dir / "agent" / "TOOL.md").read_text()

        self.runtime_manager = RuntimeManager()
        self._register_runtimes()

        self.command_manager = CommandManager()
        self._register_commands()

        self._register_channels()

        self.api_server = VulcanAPIServer(gateway=self)
        logger.info("gateway ready")

    def _register_runtimes(self):
        from ..runtime import KNOWN_RUNTIMES
        from ..types.gateway import ModelConfig

        instruction = Instruction(
            identity=self.identity_str,
            soul=self.soul_str,
            tool=self.tool_str,
        )
        for runtime_name, runtime_cls in KNOWN_RUNTIMES.items():
            cfg = self.config.runtimes.get(runtime_name)
            agent_config = AgentConfig(
                instruction=instruction,
                model=cfg.model if cfg is not None else ModelConfig(),
            )
            self.runtime_manager.register(
                name=runtime_name,
                cls=runtime_cls,
                cfg=cfg,
                agent_config=agent_config,
            )

    def _register_commands(self) -> None:
        from .commands.help.help import HelpCommand
        from .commands.new.new import NewCommand
        from .commands.runtime.runtime import RuntimeCommand
        from .commands.session.session import SessionCommand
        from .commands.sessions.sessions import SessionsCommand
        from .commands.status.status import StatusCommand
        from .commands.switch.switch import SwitchCommand
        from .commands.version.version import VersionCommand

        for cls in (
            NewCommand,
            SwitchCommand,
            SessionsCommand,
            SessionCommand,
            RuntimeCommand,
            VersionCommand,
            StatusCommand,
            HelpCommand,
        ):
            cmd = cls(gateway=self)
            self.command_manager.register_command(cmd)
            logger.info(f"registered command: /{cmd.command}")

    def _register_channels(self) -> None:
        from ..gateway.channels import get_channel_cls

        for channel_name, channel_config in self.config.channels.items():
            if not channel_config.enable:
                logger.debug(f"channel disabled, skip: {channel_name}")
                continue

            channel_cls = get_channel_cls(channel_name)
            channel_instance = channel_cls(
                name=channel_name,
                gateway=self,
                config=channel_config.config,
            )
            setattr(self, f"{channel_name}_channel", channel_instance)
            logger.info(f"registered channel: {channel_name}")

    async def invoke_stream(
        self,
        channel_id: str,
        session_id: str,
        user_message: Message,
    ) -> AsyncIterator[SessionItem]:
        """Run one turn end-to-end and yield SessionItem stream as runtime
        produces them (text, thinking, tool_call, tool_output, ...).

        Runtime selection lives entirely on the session's meta sidecar —
        `/switch` mutates it, and callers that want to rebind explicitly
        (e.g. the API middleware forwarding a request's `"model"` field)
        write it directly via `session_manager.set_session_runtime()`
        before calling this. The gateway itself only reads.

        Channels use this to render progressively. The non-streaming
        `invoke()` wraps this and aggregates into a ChatCompletion.
        """
        user_text = message_text(user_message)

        # 1. slash command match (control-plane, not saved to session).
        #    `/switch` mutates the session meta here and returns.
        command = self.command_manager.match_command(user_text)
        if command:
            logger.info(f"command matched: /{command.command}")
            completion = command.exec(
                command.parse_args(user_text), channel_id, session_id
            )
            cmd_text = completion.choices[0].message.content or ""
            yield assistant_message(cmd_text)
            return

        # 2. resolve runtime for this session and ensure it exists.
        #    priority: session meta > config.default_runtime.
        #    create_session is idempotent — touches the jsonl if missing
        #    and (re)writes the meta sidecar.
        resolved_name = (
            self.session_manager.get_session_runtime(channel_id, session_id)
            or self.config.default_runtime
        )
        self.session_manager.create_session(
            channel_id, session_id, resolved_name
        )
        runtime = self.runtime_manager.get_runtime(resolved_name)
        assert runtime is not None, f"runtime '{resolved_name}' is not enabled"

        # 3. assemble history BEFORE appending the current turn so it is
        #    excluded from history_message.
        history_message = self.session_manager.assembly_history_messages(
            channel_id, session_id
        )

        # 4. save current user message to session
        self.session_manager.append_to_session(
            channel_id, session_id, user_message
        )

        # 5. build invocation context — runtime sees two messages: a
        #    pre-rendered history + the current user input.
        ctx = InvocationContext(
            channel_id=channel_id,
            history_message=history_message,
            message=user_message,
        )
        logger.info(f"invoking runtime: {runtime.name}")

        # 6. drive runtime, yield each item, accumulate assistant text
        text_parts: list[str] = []
        async for item in runtime.invoke(ctx):
            if isinstance(item, Message) and item.role == "assistant":
                text_parts.append(message_text(item))
            yield item

        # 7. persist aggregated assistant message
        final_text = "".join(text_parts)
        self.session_manager.append_to_session(
            channel_id, session_id, assistant_message(final_text)
        )
        logger.info(f"runtime done: {runtime.name} reply_len={len(final_text)}")

    async def invoke(
        self,
        channel_id: str,
        session_id: str,
        user_message: Message,
    ) -> ChatCompletion:
        """Non-streaming convenience wrapper around invoke_stream — collects
        assistant text from yielded items into a single ChatCompletion."""
        text_parts: list[str] = []
        # The ChatCompletion.model label mirrors what invoke_stream picks:
        # session meta > config.default_runtime.
        model_name = (
            self.session_manager.get_session_runtime(channel_id, session_id)
            or self.config.default_runtime
        )
        async for item in self.invoke_stream(
            channel_id, session_id, user_message
        ):
            if isinstance(item, Message) and item.role == "assistant":
                for c in item.content:
                    text_parts.append(getattr(c, "text", ""))

        return ChatCompletion(
            id=str(uuid.uuid4()),
            object="chat.completion",
            created=int(time.time()),
            model=model_name,
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant",
                        content="".join(text_parts),
                    ),
                )
            ],
        )

    def start(self) -> None:
        logger.info("starting gateway on http://0.0.0.0:4000")
        uvicorn.run(self.api_server.app, host="0.0.0.0", port=4000)
