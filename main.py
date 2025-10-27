from typing import List
import json
import random
import string
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent


from dotenv import load_dotenv


load_dotenv()

# --------- Tools ----------

@tool
def write_json(filepath: str, data: dict) -> str:
    # Write a python dictionary as JSON to a file with pretty formatting
    try:
        with open(filepath, 'w', encoding=utf-8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return f"Succesfully wrote JSON data ti '{filepath}' ({len(json.dumps(data))} characters)."
    except Exception as e:
        return f"Error writing JSON: {str(e)}"