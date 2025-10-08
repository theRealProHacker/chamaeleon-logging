import asyncio

from app import clean_chat_history, gen_key, log_chat, make_key_chat_history, supabase

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

    chat1_id = "935294cf-d555-4f33-9446-468898e79ae6"
    chat2_id = "2ae34133-0197-45e6-9c3c-90efa61740b8"

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

    chat1 = clean_chat_history(make_key_chat_history(chat1))
    chat2 = clean_chat_history(chat2)

    print("Chat 1 length:", len(chat1))
    print("Chat 2 length:", len(chat2))

    if chat1 != chat2:
        assert gen_key(chat1) != gen_key(chat2)
        print("Chats do not match")

        # which message is different?
        for i, (msg1, msg2) in enumerate(zip(chat1, chat2)):
            if msg1 != msg2:
                print(f"Message {i} is different:")
                print(f"Chat 1 (cleaned): {msg1}")
                print(f"Chat 2 (cleaned): {msg2}")
    else:
        assert gen_key(chat1) == gen_key(chat2)
        print("Chats match")


# asyncio.run(test())

# Get the number of chats in september 2025

chat_number = supabase.table("chats").select("id", count="exact").gte("timestamp", "2025-09-01T00:00:00Z").lt("timestamp", "2025-10-01T00:00:00Z").execute()
print("Number of chats in September 2025:", chat_number.count)