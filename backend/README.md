# Shopping Assistant — Backend

FastAPI backend for the Shopping Assistant Chrome Extension. Provides AI-powered product search using Google Gemini, user authentication with Google OAuth, and persistent chat history stored in Supabase PostgreSQL.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI + Uvicorn |
| Database | Supabase (PostgreSQL) via SQLAlchemy |
| AI Agent | DeepAgents + Google Gemini 2.0 Flash |
| Search Tool | Tavily (internet search) |
| Auth | JWT (python-jose) + bcrypt + Google OAuth |

## Project Structure

```
backend/
├── main.py              # FastAPI app entry point, CORS, router registration
├── database.py          # SQLAlchemy engine + Supabase connection
├── models.py            # DB models: User, Conversation, ChatMessage, SearchHistory
├── schemas.py           # Pydantic request/response schemas
├── auth_utils.py        # JWT creation/verification, password hashing, get_current_user
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── routers/
│   ├── auth.py          # POST /auth/register, /auth/login, /auth/google
│   └── search.py        # POST /search, GET/DELETE /conversations, /history
└── services/
    └── agent.py         # Gemini AI agent with Tavily search tool
```

## Setup

### 1. Clone and enter the backend directory

```bash
cd Capstone/backend
```

### 2. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
# Supabase PostgreSQL connection string
DATABASE_URL=postgresql://postgres.xxxxx:password@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres

# JWT secret — generate a strong one:
# python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=your_generated_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=43200

# Google Gemini API key (https://aistudio.google.com/apikey)
GOOGLE_API_KEY=your_google_api_key

# Tavily search API key (https://tavily.com)
TAVILY_API_KEY=your_tavily_api_key
```

### 5. Run the server

```bash
uvicorn main:app --reload
```

The server starts at `http://localhost:8000`. API docs available at `http://localhost:8000/docs`.

## API Endpoints

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | — | Register with email + password |
| `POST` | `/auth/login` | — | Login, returns JWT token |
| `POST` | `/auth/google` | — | Google OAuth login (server-side token verification) |

### Search

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/search` | Optional | AI-powered product search. If `user_id` provided, saves chat to DB |

### Conversations (JWT Required)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/conversations` | 🔒 JWT | List all conversations for current user |
| `GET` | `/conversations/{id}` | 🔒 JWT | Get conversation with full message history |
| `DELETE` | `/conversations/{id}` | 🔒 JWT | Delete conversation and all messages |

### History (JWT Required)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/history` | 🔒 JWT | Get search history for current user |
| `POST` | `/history` | 🔒 JWT | Save a search history item |
| `DELETE` | `/history/{id}` | 🔒 JWT | Delete a history item |

## Usage Examples

### Register a new user

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "name": "User", "password": "mypassword"}'
```

### Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "mypassword"}'
```

Response:
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "User",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Search (public)

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "가성비 무선 마우스 추천", "platform": "danawa"}'
```

### Get conversations (requires JWT)

```bash
curl http://localhost:8000/conversations \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

## Database Schema

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐
│  users   │────<│ conversations │────<│ chat_messages │
├──────────┤     ├───────────────┤     ├──────────────┤
│ id (PK)  │     │ id (PK)       │     │ id (PK)      │
│ email    │     │ user_id (FK)  │     │ conv_id (FK) │
│ name     │     │ title         │     │ role         │
│ google_id│     │ platform      │     │ content      │
│ password │     │ created_at    │     │ created_at   │
│ image    │     │ updated_at    │     └──────────────┘
└──────────┘     └───────────────┘
```

## Security

- **Google OAuth**: Access tokens are verified **server-side** by calling Google's userinfo API — no client-side data is trusted
- **JWT Protection**: All conversation/history endpoints require a valid JWT in the `Authorization: Bearer` header
- **Password Hashing**: bcrypt via passlib
- **CORS**: Currently `allow_origins=["*"]` for development. Restrict to your extension ID for production:
  ```python
  allow_origins=["chrome-extension://your-extension-id"]
  ```
