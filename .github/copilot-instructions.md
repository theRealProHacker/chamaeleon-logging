# Chamaeleon Logging - AI Coding Instructions

## Project Overview
This is a **chat history deduplication and logging service** that receives chat conversations via POST requests, intelligently merges conversation continuations, and stores them in Supabase. The core challenge is identifying when a new chat request is a continuation of an existing conversation versus a completely new chat.

## Architecture & Data Flow

### Core Components
- **Flask API** (`app.py`): Single endpoint `/log` that processes chat histories
- **Dashboard** (`static/index.html`): Interactive web UI for visualizing and exploring chat analytics
- **In-memory cache** (`chat_cache`): 48-hour TTL cache for fast conversation matching
- **Supabase database**: Persistent storage with `chats` table containing `messages` JSONB field
- **Key generation system**: Creates conversation fingerprints for deduplication

### Critical Data Structures
```python
type Message = dict  # Must have "role" and "content" for real messages
type ChatHistory = list[Message]
chat_cache: dict[str, tuple[str, ChatHistory, int]]  # key -> (db_id, history, timestamp)
```

## Key Business Logic Patterns

### 1. Message Filtering
Use `is_real_msg(msg)` to distinguish actual conversation messages from metadata:
- Real messages: `{"role": "user/assistant", "content": "..."}`
- Metadata: `{"type": "tool_call", "data": {...}}`, `{"type": "recommendations", ...}`

### 2. Conversation Key Generation
- `gen_key(chat_history)`: Creates semicolon-separated string of "role: content" pairs
- Only includes real messages (filters out tool calls, recommendations, etc.)
- Used for cache lookups and deduplication

### 3. Chat Continuation Detection
- `make_key_chat_history()`: Removes the last user message to create lookup key
- Assumption: New requests always end with a fresh user message followed by assistant response
- Cache lookup uses the "everything except the last user message" pattern

### 4. HTML Cleaning Pipeline
- `clean_html_tags()`: Decodes HTML entities and strips tags before storage
- `clean_chat_history()`: Applies cleaning to all real messages in a conversation

## Development Workflows

### Testing
- Run `python test.py` to execute async test scenarios
- Test functions use actual Supabase connections - ensure `.env` is configured
- `test()` function compares specific chat IDs from database

### Database Maintenance
- Run `python clean.py` to remove duplicate conversations from Supabase
- Uses same key generation logic to identify and delete duplicates
- Processes chats in reverse chronological order (newest first)

### Local Development
```powershell
# Install dependencies
pip install -r requirements.txt

# Set up environment
# Ensure .env contains SUPABASE_URL and SUPABASE_KEY

# Run the Flask app
python app.py
```

## Project-Specific Patterns

### Cache Management
- 48-hour TTL with periodic cleanup in `/log` endpoint
- Cache keys are conversation fingerprints, values are `(db_id, full_history, timestamp)` tuples
- Cache enables O(1) continuation detection vs. database scanning

### Conversation Merging Strategy
When updating existing chats:
1. Find last real message in cached history
2. Locate same message in new request
3. Append only new messages after that point
4. Update both cache and database with merged result

### Error Handling Philosophy
- Uses assertions for critical business logic violations
- Example: `assert last_real_msg is not None` when merging conversations
- Implies corrupted data states should fail fast rather than continue

## Integration Points

### Dashboard Features
- **Interactive Charts**: Monthly, daily, weekday, and hourly chat distribution visualizations using Chart.js
- **Message Explorer**: Browse detailed chat conversations with filters by month and weekday
- **Export Functionality**: Download filtered chat data as JSON with metadata
  - Export includes human-readable filter info (month/weekday) in filename
  - Format: `chamaeleon-chats_{filter}_{datetime}.json`
  - Excludes internal timing fields (`duration_seconds`, `started_at`, `ended_at`)
  - Includes export metadata with timestamp and filter parameters

### Supabase Schema
- Table: `chats`
- Key fields: `id` (UUID), `messages` (JSONB array), `timestamp`
- RPC function: `chat_count()` for statistics

### Environment Configuration
- `SUPABASE_URL`: Database connection endpoint
- `SUPABASE_KEY`: Service role key for database access
- Both loaded via `python-dotenv` from `.env` file

## Common Debugging Scenarios

### Cache Miss Investigation
Check if `gen_key()` output matches between requests - HTML encoding differences often cause mismatches.

### Conversation Merging Issues
Verify `make_key_chat_history()` correctly identifies the lookup key by examining the last user message removal logic.

### Database Inconsistencies
Run `clean.py` to identify and resolve duplicate conversations that bypassed the deduplication logic.