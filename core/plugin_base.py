from abc import ABC, abstractmethod
from dataclasses import dataclass
from .types import Context

@dataclass
class Tool:
    name: str
    description: str
    args_schema: dict
    handler: callable
    risk_level: str = "low"

class JarvisPlugin(ABC):
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "local"
    
    @property
    @abstractmethod
    def tools(self) -> list[Tool]:
        """Tools this plugin exposes to the LLM."""
        ...
    
    def background_tasks(self) -> list[callable]:
        """Async coroutines to run continuously in background."""
        return []
    
    def on_load(self):
        """Called when plugin is loaded."""
        pass
    
    def on_unload(self):
        """Called before plugin is removed."""
        pass
    
    def on_context_change(self, context: Context):
        """Called when active app or window changes. Optional."""
        pass
