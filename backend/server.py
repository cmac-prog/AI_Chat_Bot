# server.py
from typing import List, Literal, Optional, Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

import json
import random
import re
import os

# LangChain core (version-agnostic pieces)
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

# ---------- env ----------
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    print("WARNING: OPENAI_API_KEY not set; LLM calls will fail.")

# ---------- helpers ----------
_slug_re = re.compile(r"[^a-z0-9]+")

def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = _slug_re.sub(".", s).strip(".")
    return s or "user"

def _tznow() -> datetime:
    try:
        return datetime.now().astimezone()
    except Exception:
        return datetime.now(timezone.utc)

# ---------- tools ----------
@tool
def write_json(filepath: str, data: dict) -> str:
    """Write a python dictionary as JSON to a file with pretty formatting."""
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False)
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return f"Successfully wrote JSON to '{filepath}' ({len(text)} characters)."
    except Exception as e:
        return f"Error writing JSON: {e}"

@tool
def read_json(filepath: str) -> str:
    """Read and return the contents of a JSON file (pretty-printed) or an error."""
    try:
        p = Path(filepath)
        data = json.loads(p.read_text(encoding="utf-8"))
        return json.dumps(data, indent=2, ensure_ascii=False)
    except FileNotFoundError:
        return f"Error: File '{filepath}' not found."
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON in file - {e}"
    except Exception as e:
        return f"Error reading JSON: {e}"

@tool
def generate_sample_user(
    first_names: List[str],
    last_names: List[str],
    domains: List[str],
    min_age: int,
    max_age: int,
) -> dict:
    """Generate sample user data. Count is len(first_names)."""
    if not first_names:
        return {"error": "first_names list cannot be empty"}
    if not last_names:
        return {"error": "last_names list cannot be empty"}
    if not domains:
        return {"error": "domains list cannot be empty"}
    if min_age > max_age:
        return {"error": f"min_age ({min_age}) cannot be greater than max_age ({max_age})"}
    if min_age < 0 or max_age < 0:
        return {"error": "ages must be non-negative"}

    users = []
    for i, first in enumerate(first_names):
        last   = last_names[i % len(last_names)]
        domain = domains[i % len(domains)]
        first_slug, last_slug = _slugify(first), _slugify(last)
        email = f"{first_slug}.{last_slug}@{domain.strip().lower()}"
        users.append({
            "id": i + 1,
            "firstName": first,
            "lastName": last,
            "email": email,
            "username": f"{first_slug}{random.randint(100, 999)}",
            "age": random.randint(min_age, max_age),
            "registeredAt": (_tznow() - timedelta(days=random.randint(1, 365))).isoformat(),
        })
    return {"users": users, "count": len(users)}

@tool
def save_users(
    filepath: str,
    first_names: List[str] = None,
    last_names: List[str] = None,
    domains: List[str] = None,
    min_age: int = 18,
    max_age: int = 65,
) -> str:
    """Generate users and write them to a JSON file in one atomic step (sensible defaults)."""
    try:
        if not first_names:
            first_names = ["John", "Jane", "Mike"]
        if not last_names:
            last_names = ["Smith", "Jones", "Brown"]
        if not domains:
            domains = ["example.com"]

        data = generate_sample_user.func(
            first_names=first_names,
            last_names=last_names,
            domains=domains,
            min_age=min_age,
            max_age=max_age,
        )
        if "error" in data:
            return f"Error generating users: {data['error']}"

        text = json.dumps(data, indent=2, ensure_ascii=False)
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return f"Saved {data['count']} users to '{filepath}'."
    except Exception as e:
        return f"Error saving users: {e}"

TOOLS = [write_json, read_json, generate_sample_user, save_users]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

SYSTEM_MESSAGE = (
    "You are DataGen, a helpful assistant that generates sample data for applications. "
    "To generate users, you need: first_names (list), last_names (list), domains (list), min_age, max_age. "
    "Fill these values yourself without asking if the user leaves them out. "
    "When asked to save users, prefer the save_users tool. If no filepath is provided, default to 'users.json'. "
    "If the user refers to 'those users' from a previous request, ask them to specify details again."
)

# ---------- LLM (with native tool calling) ----------
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, timeout=30, max_retries=1)
llm_with_tools = llm.bind_tools(TOOLS)

# ---------- simple tool-calling loop ----------
def run_chat(input_text: str, history_msgs: List[HumanMessage | AIMessage]) -> str:
    """
    Minimal agent loop:
    - Send system + history + human to model (with tools bound)
    - If the AI returns tool_calls, execute them and send ToolMessages back
    - Repeat until the AI returns a normal text reply
    """
    messages: List[Any] = [SystemMessage(SYSTEM_MESSAGE), *history_msgs, HumanMessage(content=input_text)]

    for _ in range(8):  # safety cap to avoid infinite loops
        ai: AIMessage = llm_with_tools.invoke(messages)
        messages.append(ai)

        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            # normal reply
            return ai.content if isinstance(ai.content, str) else json.dumps(ai.content)

        # execute each requested tool
        for tc in tool_calls:
            name: str = tc.get("name", "")
            args: Dict[str, Any] = tc.get("args", {}) or {}
            call_id: str = tc.get("id", "")
            tool = TOOLS_BY_NAME.get(name)
            if not tool:
                messages.append(ToolMessage(content=f"Error: unknown tool '{name}'", tool_call_id=call_id))
                continue
            try:
                # Prefer tool.invoke if available; fallback to direct func
                result = tool.invoke(args) if hasattr(tool, "invoke") else tool.func(**args)
            except Exception as e:
                result = f"Error running tool '{name}': {e}"
            # ToolMessage needs the tool_call_id so the model can correlate results
            messages.append(ToolMessage(content=str(result), tool_call_id=call_id))

    return "Error: exceeded tool-calling loop limit."

# ---------- FastAPI ----------
class PastMsg(BaseModel):
    role: Literal["user","assistant"]
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[PastMsg]] = []

class ChatResponse(BaseModel):
    reply: str

app = FastAPI(title="DataGen Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Map history into LC messages
    history_msgs: List[HumanMessage | AIMessage] = []
    for m in (req.history or []):
        history_msgs.append(HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content))

    reply_text = run_chat(req.message, history_msgs)
    return ChatResponse(reply=reply_text)

# Run with:
# uvicorn server:app --reload --port 8000
