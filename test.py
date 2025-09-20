import asyncio
from app import clean_chat_history, log_chat, make_key_chat_history

async def test_1():
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

async def test():
    """Gets two chats and compares them"""

    chat1_id = "30859bdc-717b-4b8c-ad33-bd473717c38d"
    chat2_id = "587ee75e-c20b-4fd7-8aef-aae71402bcc1"

    # load chats from supabase
    from app import supabase

    chat1 = supabase.table("chats").select("*").eq("id", chat1_id).execute().data[0]["messages"]
    chat2 = supabase.table("chats").select("*").eq("id", chat2_id).execute().data[0]["messages"]

    # print("Chat 1 messages:")
    # for msg in chat1:
    #     print(msg)

    # print("\n\nChat 2 messages:")
    # for msg in chat2:
    #     print(msg)

    if clean_chat_history(chat1) != clean_chat_history(make_key_chat_history(chat2)):
        print("Chats do not match")

        # which message is different?
        for i, (msg1, msg2) in enumerate(zip(chat1, chat2)):
            if msg1 != msg2:
                print(f"Message {i} is different:")
                print(f"Chat 1: {msg1}")
                print(f"Chat 2: {msg2}")


asyncio.run(test())