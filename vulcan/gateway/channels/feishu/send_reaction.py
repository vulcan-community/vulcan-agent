import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageReactionRequest,
    CreateMessageReactionRequestBody,
    Emoji,
)


def send_reaction(
    client: lark.Client,
    message_id: str,
    emoji_type: str = "Typing",
) -> None:
    request = (
        CreateMessageReactionRequest.builder()
        .message_id(message_id)
        .request_body(
            CreateMessageReactionRequestBody.builder()
            .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
            .build()
        )
        .build()
    )
    assert client.im is not None
    client.im.v1.message_reaction.create(request)
