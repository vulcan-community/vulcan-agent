# Vulcan Agent

![Vulcan](assets/logo.svg)

**The dispatch layer for pluggable agent runtimes.**

Vulcan puts Claude Code, OpenAI Codex, base OpenAI Chat Completions (and, soon, Google ADK and others) behind one OpenAI-compatible API, one JSONL conversation archive per session, and one slash-command control plane. The same conversation can hop between agent runtimes mid-stream via `/switch`.

An "agent runtime" here is a full orchestration stack — model, tool surface, sandbox, reasoning loop — not just an LLM. That distinction is the point: Vulcan is not a model router (LiteLLM / OpenRouter territory, which swap weights behind the same Chat Completions shape). Vulcan sits one level up — you swap the whole agent *stack*.

See [docs/content/docs/en/index.mdx](docs/content/docs/en/index.mdx) for the full site; the sections below are a sketch.

## Architecture

```text
clients (OpenAI HTTP / Feishu / Slack / ...)
        │
        ▼
┌─── inbound adapters ────┐    ┌─── control plane ─────┐
│ api_server middleware   │    │ commands              │
│   → invoke()            │    │  /help /version       │
│ channels (Feishu, ...)  │    │  /switch /runtime     │
│   → invoke_stream()     │    │  /sessions /session   │
└───────────┬─────────────┘    └──────────┬────────────┘
            │                             │
            └────────────► gateway ◄──────┘
                              │
                              ▼
                       runtime.invoke()
                 (Claude Code / Codex / base OpenAI / ...)
```

The gateway exposes two entry points. The API server calls `gateway.invoke()` and returns one `ChatCompletion`. Channels call `gateway.invoke_stream()` and render `SessionItem`s as the runtime emits them — text deltas, thinking, tool calls, tool outputs.

## Concepts

- **Gateway** — the orchestrator. `invoke()` returns a `ChatCompletion`, `invoke_stream()` yields `SessionItem`s; the first wraps the second.
- **Runtime** — an agent stack behind a small interface: `BaseRuntime.invoke(ctx) -> AsyncIterator[SessionItem]` and `is_installed() -> bool`. Every call is stateless — the gateway pre-builds a `(history_message, current_message)` pair and hands it over; the runtime's own session is fresh each turn.
- **Session** — a JSONL transcript at `~/.vulcan/sessions/<channel_id>/<session_id>.jsonl`. Each line is an OpenAI `ConversationItem`. Sessions are isolated per source: API requests use `channel_id="gateway"`, channels use the channel's name.
- **Channel** — a transport adapter. `BaseChannel.invoke(session_id, user_message)` forwards to the gateway with `channel_id = self.name`. Feishu today; Slack, Discord planned.
- **Command** — a control-plane slash command. Short-circuits the runtime call and returns a synthetic `vulcan-system` completion.
- **Persona** — three template files (`IDENTITY.md`, `SOUL.md`, `TOOL.md`) copied to `~/.vulcan/agent/` on first start. Each runtime decides where to inject the rendered persona (system-prompt append for Claude Code, prompt prepend for Codex, system role for base OpenAI).

## Supported agent runtimes

| Runtime       | Status  | Backend                                                                                |
| ------------- | ------- | -------------------------------------------------------------------------------------- |
| `claude-code` | ✅      | [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python)            |
| `codex`       | ✅      | [`openai-codex-sdk`](https://pypi.org/project/openai-codex-sdk/) (wraps the `codex` CLI) |
| `base-openai` | ✅      | [`openai`](https://github.com/openai/openai-python) Chat Completions                   |
| `google-adk`  | planned | `google-adk`                                                                           |

Each runtime ships as an optional extra — `uv sync --extra claude-code`, `--extra codex`, or comma-separate them. The [runtime reference](docs/content/docs/en/reference/runtimes.mdx) lists per-runtime capabilities and gotchas.

## Channels

| Channel | Status  | Backend                                                                     |
| ------- | ------- | --------------------------------------------------------------------------- |
| Feishu  | ✅      | [`lark-oapi`](https://github.com/larksuite/oapi-sdk-python) long-connection |
| Slack   | planned | Slack Events API                                                            |
| Discord | planned | `discord.py`                                                                |

## Quick start

```python
from pathlib import Path
from vulcan.gateway.gateway import Gateway

Gateway(home_dir=Path("~/.vulcan").expanduser()).start()
```

The server listens on `http://0.0.0.0:4000`. Talk to it like any OpenAI endpoint — the `model` field is the **runtime name** (from `/runtime`), not an LLM identifier:

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: default" \
  -d '{
    "model": "claude-code",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

For the full walk-through see the [tutorial](docs/content/docs/en/tutorials/quick-start.mdx).

## Configuration

Runtimes and channels are declared in `~/.vulcan/vulcan.json` (validated by `GatewayConfig` with `extra="forbid"`). Example:

```json
{
  "default_runtime": "claude-code",
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
    "feishu": { "enable": false, "config": {} }
  }
}
```

`default_runtime` is the fallback for sessions with no prior binding. Runtime selection is per-session: `/switch <name>` from any chat rebinds that session's `.meta.json` sidecar, and the API's `"model"` field behaves the same way. Channels do not pick a runtime. The `name` field accepts the alias `"model"` in JSON. Empty `base_url` / `api_key` fall back to the SDK default and the local credential chain (for `claude-code` that means your existing `claude` CLI login; for `codex` it means `~/.codex/auth.json`). See [`config` reference](docs/content/docs/en/reference/config.mdx) for the full schema.

## Project layout

```text
vulcan/
├── api_server/       OpenAI-compatible HTTP layer (calls gateway.invoke)
├── consts.py         GATEWAY_CHANNEL_ID and other constants
├── gateway/          Gateway.invoke + invoke_stream orchestrator
│   ├── channels/     BaseChannel + concrete channels (Feishu, ...)
│   └── commands/     BaseCommand + slash commands
├── runtime/          BaseRuntime + concrete backends
│   ├── base_openai/  OpenAI-compatible base runtime
│   ├── claude_code/  Claude Code runtime
│   └── codex/        OpenAI Codex CLI runtime
├── session/          Transcript storage (LocalSessionManager → JSONL)
├── types/            GatewayConfig / AgentConfig / InvocationContext
├── utils/            Message factories, ChatCompletion helpers, logger
└── template/         Default home dir layout (vulcan.json, agent/, sessions/)
```

## Documentation

The full site is in [`docs/`](docs/) and organised as [Diátaxis](https://diataxis.fr/):

- [Tutorial](docs/content/docs/en/tutorials/quick-start.mdx) — zero to a working conversation.
- [How-to guides](docs/content/docs/en/how-to/) — add a runtime, connect Feishu, write a command, drive Vulcan from the `openai` SDK.
- [Reference](docs/content/docs/en/reference/) — slash commands, runtime catalog, channel catalog, config schema.
- [Explanation](docs/content/docs/en/explanation/) — architecture, why pluggable agent runtimes (not model routing), how the stateless runtime interface works.

Simplified Chinese version at [`docs/content/docs/zh-cn/`](docs/content/docs/zh-cn/).

## Status

Early. The orchestration is locked. Runtime adapters and channels are still filling in. Single-user only for now.
