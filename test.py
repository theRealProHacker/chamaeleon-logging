import asyncio
from app import log_chat

async def test():
    await log_chat([
        {"role": "user", "content": "Hello!"},
        {"type": "tool_call", "data": {"content": "example"}},
        {"role": "assistant", "content": "Hi there! How can I help you today?"},
    ])

    await log_chat([
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there! How can I help you today?"},
        {"role": "user", "content": "What's the weather like today?"},
        {"role": "assistant", "content": "It's sunny and warm today."},
        {"type": "recommendations", "data": {"items": ["Check the weather app", "Take an umbrella just in case"]}}
    ])

asyncio.run(test())