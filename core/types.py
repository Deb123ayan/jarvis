from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class ActionType(Enum):
    TOOL_CALL = "TOOL_CALL"
    DONE = "DONE"
    CLARIFY = "CLARIFY"

@dataclass
class Action:
    type: ActionType
    tool: str | None
    args: dict
    response: str | None
    reasoning: str

@dataclass
class Observation:
    content: str
    is_error: bool = False
    error: str | None = None
    duration_ms: int = 0

@dataclass
class AgentResult:
    response: str
    steps: int = 0
    tools_used: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    partial: bool = False

@dataclass
class Context:
    active_app: str
    window_title: str
    time_of_day: str
    recent_commands: list[str]
    relevant_memories: list[str]
    graph_context: dict

@dataclass  
class Memory:
    id: str
    text: str
    category: str
    confidence: float
    created_at: datetime
    last_accessed: datetime
    access_count: int
