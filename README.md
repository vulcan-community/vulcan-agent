# Vulcan Agent

![Vulcan](assets/logo.svg)

**Pluggable runtimes. Single API.**

Vulcan Agent sits between your client (OpenWebUI, the `openai` SDK, `curl`, Feishu, ...) and an agent runtime (Claude Code, OpenAI-compatible, Codex, Google ADK, ...). You wire runtimes and channels through one config file. Vulcan owns the session transcript and dispatches each turn to the runtime you pick.

## Architecture

```text
clients (OpenAI HTTP / Feishu / Slack / ...)
        │
        ▼
┌─── inbound adapters ────┐    ┌─── control plane ─────┐
│ api_server middleware   │    │ commands              │
│   → invoke()            │    │  /help /switch        │
│ channels (Feishu, ...)  │    │  /sessions /session   │
│   → invoke_stream()     │    │  /runtime             │
└───────────┬─────────────┘    └──────────┬────────────┘
            │                             │
            └────────────► gateway ◄──────┘
                              │
                              ▼
                       runtime.invoke()
                  (Claude Code / OpenAI / ...)
```

The gateway exposes two entry points. The API server calls `gateway.invoke()` and returns one `ChatCompletion`. Channels call `gateway.invoke_stream()` and render `SessionItem`s as the runtime emits them — text deltas, thinking, tool calls, tool outputs.

## Concepts

- **Gateway** — the orchestrator. Two entry points: `invoke()` returns a `ChatCompletion`, `invoke_stream()` yields `SessionItem`s. The first is a wrapper that consumes the second.
- **Runtime** — a pluggable agent backend implementing `BaseRuntime.invoke(ctx) -> AsyncIterator[SessionItem]`. Each runtime decides how to translate the transcript into its native input.
- **Session** — a JSONL transcript at `~/.vulcan/sessions/<channel_id>/<session_id>.jsonl`. Each line is an OpenAI `ConversationItem`. Sessions are isolated per source: API requests use `channel_id="gateway"`, channels use the channel's name.
- **Channel** — a transport adapter. `BaseChannel.invoke()` and `invoke_stream()` forward to the gateway. Feishu today; Slack, Discord planned.
- **Command** — a control-plane slash command. Short-circuits the runtime call and returns a synthetic completion.
- **Persona** — three template files (`IDENTITY.md`, `SOUL.md`, `TOOL.md`) copied to `~/.vulcan/agent/` on first start. The gateway feeds them into `AgentConfig.instruction`; each runtime decides how to inject.

## Supported runtimes

| Runtime           | Status  | Backend                                                                     |
| ----------------- | ------- | --------------------------------------------------------------------------- |
| Claude Code       | ✅      | [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python) |
| Base OpenAI       | ✅      | [`openai`](https://github.com/openai/openai-python) Chat Completions        |
| Codex             | planned | `codex-app-server`                                                          |
| Google ADK        | planned | `google-adk`                                                                |

`ClaudeCodeRuntime` streams four item types: `Message`, `ResponseReasoningItem`, `ResponseFunctionToolCallItem`, `ResponseFunctionToolCallOutputItem`. It uses `max_thinking_tokens` to enable thinking and `setting_sources=[]` to isolate from local `~/.claude/settings.json` when you supply a custom `base_url`/`api_key`.

`BaseOpenAIRuntime` is a subclassable base for any OpenAI-compatible Chat Completions endpoint. Override `build_messages` for custom prompt structure or `invoke` for tool/reasoning support.

## Channels

| Channel | Status  | Backend                                                                     |
| ------- | ------- | --------------------------------------------------------------------------- |
| Feishu  | ✅      | [`lark-oapi`](https://github.com/larksuite/oapi-sdk-python) long-connection |
| Slack   | planned | Slack Events API                                                            |
| Discord | planned | `discord.py`                                                                |

Feishu uses `gateway.invoke_stream()` to drive a CardKit progressive card so users see text, thinking, and tool calls land as they happen.

## Quick start

```python
from pathlib import Path
from vulcan.gateway.gateway import Gateway, prepare_home_dir

home = Path("~/.vulcan").expanduser()
prepare_home_dir(home)
Gateway(home_dir=home).start()
```

The server listens on `http://0.0.0.0:4000`. Talk to it like any OpenAI endpoint:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: default" \
  -d '{
    "model": "claude-code",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

For full setup, see the [docs](docs/content/docs/en/quick-start.mdx).

## Configuration

Runtimes and channels are declared in `~/.vulcan/vulcan.json` (validated by `GatewayConfig` with `extra="forbid"`):

```json
{
  "runtimes": {
    "claude-code": {
      "enable": true,
      "model": {
        "name": "claude-sonnet-4-5",
        "provider": "anthropic",
        "base_url": "",
        "api_key": ""
      }
    }
  },
  "channels": {
    "feishu": { "enable": false, "runtime": "claude-code", "config": {} }
  }
}
```

`name` accepts the alias `"model"` in JSON. Empty `base_url`/`api_key` fall back to the SDK default and the local credential chain.

## Project layout

```text
vulcan/
├── api_server/       OpenAI-compatible HTTP layer (calls gateway.invoke)
├── consts.py         GATEWAY_CHANNEL_ID and other constants
├── gateway/          Gateway.invoke + invoke_stream orchestrator
│   ├── channels/     BaseChannel + concrete channels (Feishu, ...)
│   └── commands/     BaseCommand + slash commands
├── runtime/          BaseRuntime + concrete backends
│   ├── claude_code/  Claude Code runtime
│   └── base_openai/  OpenAI-compatible base runtime
├── session/          Transcript storage (LocalSessionManager → JSONL)
├── types/            GatewayConfig / AgentConfig / InvocationContext
└── template/         Default home dir layout (vulcan.json, agent/, sessions/)
```

## Status

Early. The orchestration is locked. Runtime adapters and channels are still filling in. Single-user only for now.
