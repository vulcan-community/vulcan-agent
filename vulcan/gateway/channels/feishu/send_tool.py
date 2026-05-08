"""Render tool invocations as collapsible_panel elements.

`send_tool_call` inserts a new panel whose header is the tool name and
whose body is a markdown element showing the args. The inner markdown's
element_id is remembered keyed by call_id, so the matching
`send_tool_result` updates that same element in place to add the result
section — keeping call and result visually paired in one collapsible.
"""

from .card_session import CardSession


def collapsible_panel_element(
    panel_id: str, body_id: str, title_md: str, body_md: str
) -> dict:
    return {
        "tag": "collapsible_panel",
        "element_id": panel_id,
        "expanded": False,
        "background_color": "grey-50",
        "header": {
            "title": {"tag": "markdown", "content": title_md},
            "vertical_align": "center",
            "padding": "4px 0px 4px 8px",
            "icon": {
                "tag": "standard_icon",
                "token": "down-small-ccm_outlined",
                "size": "16px 16px",
            },
            "icon_position": "right",
            "icon_expanded_angle": -180,
        },
        "border": {"color": "grey", "corner_radius": "5px"},
        "vertical_spacing": "8px",
        "padding": "8px 8px 8px 8px",
        "elements": [
            {
                "tag": "markdown",
                "element_id": body_id,
                "content": body_md,
            }
        ],
    }


async def send_tool_call(
    session: CardSession, call_id: str, name: str, args_json: str
) -> None:
    session.open_text_id = None
    session.open_think_id = None
    session.open_think_buf = ""
    panel_id = session.new_id("tool")
    body_id = session.new_id("toolbody")
    session.tool_state[call_id] = (body_id, args_json)
    body_md = f"**args**\n```\n{args_json}\n```"
    await session.insert_element(
        collapsible_panel_element(
            panel_id=panel_id,
            body_id=body_id,
            title_md=f"🔧 `{name}`",
            body_md=body_md,
        )
    )


async def send_tool_result(
    session: CardSession, call_id: str, output: str, is_error: bool
) -> None:
    session.open_text_id = None
    session.open_think_id = None
    session.open_think_buf = ""
    state = session.tool_state.get(call_id)
    if state is None:
        return
    body_id, args = state
    marker = "✗" if is_error else "✓"
    body_md = (
        f"**args**\n```\n{args}\n```\n\n**result** {marker}\n```\n{output}\n```"
    )
    await session.set_content(body_id, body_md)
