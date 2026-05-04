# Feishu Channel

A `BaseChannel` implementation that bridges Feishu (Lark) chat to Vulcan. Inbound messages are forwarded to the gateway stream; assistant text, thinking, and tool events render progressively into a single Feishu interactive card.

## Long-connection transport. No webhook needed.

The channel uses Feishu's long-connection event subscription via [`lark-oapi`](https://github.com/larksuite/oapi-sdk-python). It opens an outbound WebSocket and receives events through it, so you don't have to expose a public URL.

## Configure in vulcan.json. Enable to start.

```json
{
  "channels": {
    "feishu": {
      "enable": true,
      "runtime": "claude-code",
      "config": {
        "app_id": "cli_...",
        "app_secret": "..."
      }
    }
  }
}
```

Install the optional dependency group:

```bash
uv sync --extra feishu
```

The gateway picks up `channels.feishu` at startup and registers it against the named runtime.

## Forward to gateway. Skip the runtime plumbing.

The channel doesn't talk to a runtime directly — it forwards to `Gateway.invoke_stream()`, which centralizes session save, slash-command match, and runtime dispatch. `channel.invoke_stream()` passes no `runtime_name`, so the gateway routes to `curr_runtime`. The `/switch <name>` slash command flips that pointer from inside any chat.

## Receive an event. Render the stream into one card.

Construction wires the lark `EventDispatcherHandler`, then spawns a daemon thread for `ws.start()` so gateway init doesn't block. Each inbound message hits `on_message` (the sync dispatcher entry), which schedules `handle_event` on the running loop:

1. `send_reaction` — acknowledge with an OK emoji.
2. `CardSession.start()` — create a CardKit card and reply to the source message with it.
3. `invoke_stream(user_id, session_id, user_message)` — the gateway saves the turn and dispatches to `curr_runtime`.
4. Each yielded `SessionItem` is rendered into the live card by event type.
5. `CardSession.finish()` — flip streaming mode off so the AI-generating indicator clears.

## Match the event to the rendering.

| Event                                                       | Rendering                                                          |
| ----------------------------------------------------------- | ------------------------------------------------------------------ |
| Text chunks                                                 | Accumulated into one streaming markdown element                    |
| `ResponseReasoningItem` (thinking)                          | New markdown element rendered as `>` blockquote                    |
| `ResponseFunctionToolCallItem`                              | New `collapsible_panel` titled with the tool name; body shows args |
| `ResponseFunctionToolCallOutputItem` (matched by `call_id`) | Same panel's inner markdown updated to add a `result` section      |

## One concern per file. Easy to read.

- `feishu_channel.py` — the `BaseChannel` subclass; `on_message` dispatcher entry + `handle_event` async orchestration.
- `card_session.py` — `CardSession` coordinator: holds `card_id`, sequence counter, `last_element_id`, and the `tool_state` map; exposes `start()` / `finish()` / `insert_element()` / `set_content()` for the send_* modules.
- `send_streaming_msg.py` — text chunk → open markdown element.
- `send_streaming_thinking.py` — thinking → blockquote markdown element.
- `send_tool.py` — `send_tool_call` opens the collapsible panel; `send_tool_result` pairs by `call_id` and updates the same panel's inner markdown to add the result.
- `send_reaction.py` — emoji reaction on the source message.
