import shutil
import time
import uuid
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.conversations.message import Message
from openai.types.responses.response_output_text import ResponseOutputText

from ..api_server.app import VulcanAPIServer
from ..runtime.runtime_manager import RuntimeManager
from ..session.local_session_manager import LocalSessionManager
from ..types.agent import AgentConfig, Instruction
from ..types.gateway import GatewayConfig
from ..types.invocation import InvocationContext
from ..types.session import SessionItem
from ..utils.logger import get_logger
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

        from ..runtime import get_runtime_cls

        for runtime_name, runtime_config in self.config.runtimes.items():
            if not runtime_config.enable:
                logger.info(f"runtime disabled, skip: {runtime_name}")
                continue

            runtime_cls = get_runtime_cls(runtime_name)
            runtime_instance = runtime_cls(
                name=runtime_name,
                agent_config=AgentConfig(
                    instruction=Instruction(
                        identity=self.identity_str,
                        soul=self.soul_str,
                        tool=self.tool_str,
                    ),
                    model=runtime_config.model,
                ),
            )
            self.runtime_manager.register_runtime(runtime_instance)
            logger.info(
                f"registered runtime: {runtime_name} ({runtime_cls.__name__})"
            )

    def _register_commands(self) -> None:
        from .commands.runtimes.runtimes import RuntimesCommand
        from .commands.session.session import SessionCommand
        from .commands.sessions.sessions import SessionsCommand
        from .commands.switch.switch import SwitchCommand

        for cls in (
            SwitchCommand,
            SessionsCommand,
            SessionCommand,
            RuntimesCommand,
        ):
            cmd = cls(gateway=self)
            self.command_manager.register_command(cmd)
            logger.info(f"registered command: /{cmd.command}")

    async def invoke_stream(
        self,
        user_id: str,
        session_id: str,
        user_message: Message,
        runtime_name: str | None = None,
    ) -> AsyncIterator[SessionItem]:
        """Run one turn end-to-end and yield SessionItem stream as runtime
        produces them (text, thinking, tool_call, tool_output, ...).

        Channels use this to render progressively. The non-streaming
        `invoke()` wraps this and aggregates into a ChatCompletion.
        """
        message_text = "".join(
            getattr(c, "text", "") for c in user_message.content
        )

        # 1. slash command match (control-plane, not saved to session)
        command = self.command_manager.match_command(message_text)
        if command:
            logger.info(f"command matched: /{command.command}")
            completion = command.exec(command.parse_args(message_text))
            cmd_text = completion.choices[0].message.content or ""
            yield Message(
                id=str(uuid.uuid4()),
                type="message",
                role="assistant",
                status="completed",
                content=[
                    ResponseOutputText(
                        type="output_text",
                        text=cmd_text,
                        annotations=[],
                    )
                ],
            )
            return

        # 2. save user message to session
        self.session_manager.append_to_session(
            user_id, session_id, user_message
        )

        # 3. pick runtime
        if runtime_name is not None:
            runtime = self.runtime_manager.get_runtime(runtime_name)
        else:
            runtime = self.runtime_manager.curr_runtime
        assert runtime is not None

        # 4. build invocation context
        ctx = InvocationContext(
            user_id=user_id,
            session=self.session_manager.get_session(user_id, session_id),
            message={"role": "user", "content": message_text},
        )
        logger.info(f"invoking runtime: {runtime.name}")

        # 5. drive runtime, yield each item, accumulate assistant text
        text_parts: list[str] = []
        async for item in runtime.invoke(ctx):
            if isinstance(item, Message) and item.role == "assistant":
                for c in item.content:
                    text_parts.append(getattr(c, "text", ""))
            yield item

        # 6. persist aggregated assistant message
        final_text = "".join(text_parts)
        assistant_item = Message(
            id=str(uuid.uuid4()),
            type="message",
            role="assistant",
            status="completed",
            content=[
                ResponseOutputText(
                    type="output_text",
                    text=final_text,
                    annotations=[],
                )
            ],
        )
        self.session_manager.append_to_session(
            user_id, session_id, assistant_item
        )
        logger.info(f"runtime done: {runtime.name} reply_len={len(final_text)}")

    async def invoke(
        self,
        user_id: str,
        session_id: str,
        user_message: Message,
        runtime_name: str | None = None,
    ) -> ChatCompletion:
        """Non-streaming convenience wrapper around invoke_stream — collects
        assistant text from yielded items into a single ChatCompletion."""
        text_parts: list[str] = []
        model_name = runtime_name or (
            self.runtime_manager.curr_runtime.name
            if self.runtime_manager.curr_runtime
            else "vulcan-system"
        )
        async for item in self.invoke_stream(
            user_id, session_id, user_message, runtime_name
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

    def _register_channels(self) -> None:
        from ..gateway.channels import get_channel_cls

        for channel_name, channel_config in self.config.channels.items():
            if not channel_config.enable:
                logger.debug(f"channel disabled, skip: {channel_name}")
                continue

            channel_cls = get_channel_cls(channel_name)
            default_runtime = self.runtime_manager.get_runtime(
                channel_config.runtime
            )
            if not default_runtime:
                logger.error(
                    f"{channel_name}'s runtime {channel_config.runtime} not exist, skip init this channel"
                )
                continue
            channel_instance = channel_cls(
                name=channel_name,
                gateway=self,
                default_runtime=default_runtime,
                config=channel_config.config,
            )
            setattr(self, f"{channel_name}_channel", channel_instance)
            logger.info(
                f"registered channel: {channel_name} "
                f"-> runtime={channel_config.runtime}"
            )

    def start(self) -> None:
        logger.info("starting gateway on http://0.0.0.0:4000")
        uvicorn.run(self.api_server.app, host="0.0.0.0", port=4000)
