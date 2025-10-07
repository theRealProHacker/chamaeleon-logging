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
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import create_client, Client
from flask import Flask, request, jsonify, send_from_directory

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = Flask(__name__, static_folder="static", static_url_path="/static")

type Message = dict
type ChatHistory = list[Message]

chat_cache: dict[str, tuple[str, ChatHistory, float]] = {}

def is_real_msg(msg: Message):
    return "role" in msg and "content" in msg


def analyze_chat(chat: dict[str, Any]) -> dict[str, Any]:
    messages = chat["messages"]
    timestamp = chat["timestamp"]

    return {
        "id": chat.get("id"),
        "chat_timestamp": timestamp,
        "user_message_count": sum(1 for msg in messages if msg.get("role") == "user"),
        "messages": messages,
    }


def generate_month_keys(count: int = 12) -> list[str]:
    today = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = []
    for offset in range(count - 1, -1, -1):
        year = today.year
        month = today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        months.append(f"{year:04d}-{month:02d}")
    return months


def format_month_label(month_key: str) -> str:
    try:
        dt = datetime.strptime(month_key, "%Y-%m")
        return dt.strftime("%B %Y")
    except ValueError:
        return month_key


def get_month_bounds(month_key: str) -> tuple[datetime, datetime]:
    dt = datetime.strptime(month_key, "%Y-%m")
    start = datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)
    if dt.month == 12:
        end = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def build_monthly_summary(analyses: list[dict[str, Any]], month_keys: list[str]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {month: 0 for month in month_keys}
    for analysis in analyses:
        ts = analysis.get("chat_timestamp")
        if not isinstance(ts, datetime):
            continue
        key = ts.strftime("%Y-%m")
        if key in counts:
            counts[key] += 1
    return [
        {
            "key": month,
            "label": format_month_label(month),
            "count": counts.get(month, 0)
        }
        for month in month_keys
    ]


def compute_totals(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    total_chats = len(analyses)
    total_user_messages = sum(analysis.get("user_message_count", 0) for analysis in analyses)
    duration_values = [analysis.get("duration_seconds", 0.0) for analysis in analyses if analysis.get("has_duration")]
    avg_user_messages = total_user_messages / total_chats if total_chats else 0.0
    avg_duration = sum(duration_values) / len(duration_values) if duration_values else 0.0
    return {
        "total_chats": total_chats,
        "avg_user_messages_per_chat": avg_user_messages,
        "avg_chat_duration_seconds": avg_duration,
    }


def build_daily_counts(analyses: list[dict[str, Any]], start: datetime, end: datetime) -> list[dict[str, Any]]:
    day = start
    buckets: dict[str, dict[str, Any]] = {}
    while day < end:
        key = day.strftime("%Y-%m-%d")
        buckets[key] = {
            "date": key,
            "label": day.strftime("%d %b"),
            "count": 0
        }
        day += timedelta(days=1)

    for analysis in analyses:
        ts = analysis["chat_timestamp"]
        if not isinstance(ts, datetime):
            continue
        if ts < start or ts >= end:
            continue
        key = ts.strftime("%Y-%m-%d")
        if key in buckets:
            buckets[key]["count"] += 1

    return list(buckets.values())


def build_month_detail(analyses: list[dict[str, Any]], month_key: str) -> Optional[dict[str, Any]]:
    try:
        start, end = get_month_bounds(month_key)
    except ValueError:
        return None

    month_chats: list[dict[str, Any]] = []
    for analysis in analyses:
        for candidate in (analysis.get("chat_timestamp"), analysis.get("start_ts")):
            if isinstance(candidate, datetime) and start <= candidate < end:
                month_chats.append(analysis)
                break

    metrics = compute_totals(month_chats)
    daily_counts = build_daily_counts(month_chats, start, end)

    chat_details = []
    for analysis in month_chats:
        messages_payload = [
            {
                "role": message.get("role"),
                "content": message.get("content"),
                "timestamp": isoparse(message.get("timestamp"))
            }
            for message in analysis.get("messages", [])
        ]
        chat_details.append({
            "id": analysis.get("id"),
            "user_message_count": analysis.get("user_message_count", 0),
            "messages": messages_payload,
        })

    chat_details.sort(key=lambda item: item.get("started_at") or "")

    return {
        "month": month_key,
        "label": format_month_label(month_key),
        "metrics": metrics,
        "daily_counts": daily_counts,
        "chats": chat_details,
    }


def build_dashboard_payload(chats: list[dict[str, Any]], month_key: Optional[str]) -> dict[str, Any]:
    analyses = [analyze_chat(chat) for chat in chats]
    month_keys = generate_month_keys()
    monthly_summary = build_monthly_summary(analyses, month_keys)
    totals = compute_totals(analyses)
    month_detail = None
    if month_key:
        month_detail = build_month_detail(analyses, month_key)
    return {
        "monthly_summary": monthly_summary,
        "totals": totals,
        "selected_month": month_detail,
    }


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/dashboard")
def dashboard_data():
    month_key = request.args.get("month")
    response = supabase.table("chats").select("*").execute()
    data = response.data
    payload = build_dashboard_payload(data, month_key)
    return payload

@app.get("/status")
async def chat_status():
    return f"""
    Chat cache size (last 48 hours): {len(chat_cache)}
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
    

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8000, debug=True)