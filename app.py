# Gets post requests with chat histories
# If the chat histories only contain one message, they are new and get entered into the database with a timestamp. 
# The database returns a unique identifier for the new chat history.
# The chat is then cached on server for 24 hours with the database key
# Now when a new chat history is received, the beginning will be used to find the previous history in the cache and retrieve the key. 
# The key is then used to update the database with the new messages

import html.entities
import os
import re
import time

from dotenv import load_dotenv
from supabase import create_client, Client
from flask import Flask, request

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = Flask(__name__)

type Message = dict
type ChatHistory = list[Message]

chat_cache: dict[str, tuple[str, ChatHistory], int] = {}

def is_real_msg(msg: Message):
    return "role" in msg and "content" in msg

@app.get("/")
async def chat_count():
    return f"""
    Chat count (last 24 hours): {len(chat_cache)}
    <br>
    Total chat count: {supabase.rpc("chat_count").execute().data}
    """.strip()

def gen_key(chat_history: ChatHistory):
    # filter for messages
    return ";".join((msg["role"]+": "+msg["content"]) for msg in chat_history if is_real_msg(msg))

html_tag_pattern = re.compile(r'<.*?>')
def clean_html_tags(text: str) -> str:
    for key, val in reversed(html.entities.html5.items()):
        # if "quot" in key.lower():
        #     text = text.replace("&quot;", '"')
        #     continue
        text = text.replace("&"+key, val)
    return html_tag_pattern.sub("", text)

def clean_chat_history(chat_history: ChatHistory) -> ChatHistory:
    return [{
        "role": msg["role"],
        "content": clean_html_tags(msg["content"])
    } if is_real_msg(msg) else msg for msg in chat_history]

def make_key_chat_history(chat_history: ChatHistory)->ChatHistory:
    key_chat_history = chat_history[:]
    while True:
        msg = key_chat_history.pop()
        if is_real_msg(msg) and msg["role"] == "user":
            break
    return key_chat_history

@app.post("/log")
async def log_chat():
    chat_history: ChatHistory = request.get_json()
    if len(chat_history) > 1:
        chat_history = clean_chat_history(chat_history)
        key_chat_history = make_key_chat_history(chat_history)
        key = gen_key(key_chat_history)

        # Check if chat is in cache
        if key in chat_cache:
            # Existing chat, find in cache and update database
            (db_index, old_history, _) = chat_cache[key]

            # add new messages to history
            # find the last "real" message in the old chat (mess). 
            # Find that in the new chat, then append everything after that message from the new chat to the old chat
            last_real_msg = next((msg for msg in reversed(old_history) if is_real_msg(msg)), None)
            assert last_real_msg is not None, "No real message found in old chat"

            new_history = old_history + chat_history[chat_history.index(last_real_msg)+1:]

            chat_cache[gen_key(new_history)] = (key, new_history, time.time())
            supabase.table("chats").update({"messages": new_history}).eq("id", db_index).execute()
            return {"status": "chat updated", "chat_id": key}
    
    # New chat, insert into database
    key = gen_key(chat_history)
    response = supabase.table("chats").insert({"messages": chat_history}).execute()
    chat_id = response.data[0]['id']
    chat_cache[key] = (chat_id, chat_history, time.time())

    # Clear old chat histories from cache
    for k, (db_index, old_history, timestamp) in list(chat_cache.items()):
        if time.time() - timestamp > 48 * 60 * 60:
            del chat_cache[k]

    return {"status": "new chat logged", "chat_id": chat_id}
    