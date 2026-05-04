from .base_channel import BaseChannel


def get_channel_cls(name: str) -> type[BaseChannel]:
    if name == "feishu":
        from .feishu.feishu_channel import FeishuChannel

        return FeishuChannel
    raise ValueError(f"Unsupported channel: {name}")
