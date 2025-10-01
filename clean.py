"""
Clean up the database
"""

from app import clean_chat_history, gen_key, make_key_chat_history, supabase

def clean_db():
    # sort by timestamp
    all_chats = supabase.table("chats").select("*").order("timestamp", desc=True).execute().data

    memory = {}

    for chat in all_chats:
        messages = clean_chat_history(chat["messages"])

        if gen_key(messages) in memory:
            supabase.table("chats").delete().eq("id", chat["id"]).execute()
            print(f"Deleted duplicate chat {chat['id']}")
        else:
            while True:
                messages = make_key_chat_history(messages)
                if not messages:
                    break
                memory[gen_key(messages)] = chat


clean_db()