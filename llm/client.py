"""
llm/client.py — Ollama HTTP client for JARVIS.

Two paths:
  1. _process_conversational() — plain streaming chat for non-tool requests.
     Chunks by sentence and enqueues directly to TTS.

  2. _process_with_tools() — sends tool schema in system prompt, parses JSON
     response, dispatches tool calls via the registry, then speaks the result.

Routing is decided by llm/prompt_builder.is_tool_intent().
"""

import json
import os
import random
import threading
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from core.events import bus, Event
from core.config import config
from llm.prompt_builder import build_system_prompt, is_tool_intent

if TYPE_CHECKING:
    from tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Model routing (PRD §6.3)
# ---------------------------------------------------------------------------

DEEP_TRIGGERS = [
    "plan", "analyze", "summarize", "write", "explain", "compare",
    "research", "remember everything", "think about",
]


def _route_model(transcript: str, fast_model: str, deep_model: str) -> str:
    """Choose fast or deep model based on transcript content and length."""
    lower = transcript.lower()
    if any(t in lower for t in DEEP_TRIGGERS):
        return deep_model
    if len(transcript.split()) > 30:
        return deep_model
    return fast_model


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    def __init__(self, registry: "ToolRegistry | None" = None):
        self.fast_model = config.get("models.fast", "meta-llama/llama-3.3-70b-instruct")
        self.deep_model = config.get("models.deep", "deepseek/deepseek-chat")
        self.base_url = config.get("system.openrouter_url", "https://openrouter.ai/api/v1/chat/completions")
        
        self.api_keys = [
            config.get("system.openrouter_api_key_1", os.environ.get("OPENROUTER_API_KEY_1")),
            config.get("system.openrouter_api_key_2", os.environ.get("OPENROUTER_API_KEY_2"))
        ]
        self.api_keys = [k for k in self.api_keys if k]
        if not self.api_keys:
            key = config.get("system.openrouter_api_key", os.environ.get("OPENROUTER_API_KEY", ""))
            if key: self.api_keys.append(key)
            
        self.registry = registry

        # Conversation history (working memory — simple list for Phase 2)
        self._history: list[dict] = []

        bus.subscribe(Event.TRANSCRIPT_READY, self._on_transcript)
        logger.info(
            f"LLMClient ready. Fast: {self.fast_model} | Deep: {self.deep_model}"
        )

    def set_registry(self, registry: "ToolRegistry"):
        """Attach the tool registry (can be set after construction)."""
        self.registry = registry

    # ------------------------------------------------------------------
    # Event handler — dispatches to background thread immediately
    # ------------------------------------------------------------------

    def _on_transcript(self, transcript: str):
        threading.Thread(
            target=self._dispatch,
            args=(transcript,),
            daemon=True,
            name="LLMDispatch",
        ).start()

    def _dispatch(self, transcript: str):
        model = _route_model(transcript, self.fast_model, self.deep_model)
        logger.info(f"Routing '{transcript[:60]}...' → model={model}")

        if self.registry and is_tool_intent(transcript):
            self._process_with_tools(transcript, model)
        else:
            self._process_conversational(transcript, model)

    # ------------------------------------------------------------------
    # Path 1 — Conversational (no tools, streaming to TTS)
    # ------------------------------------------------------------------

    def _process_conversational(self, transcript: str, model: str):
        logger.info("LLM path: conversational (streaming)")
        messages = self._build_messages(
            transcript,
            system="You are JARVIS, a helpful local AI assistant. Keep responses concise and conversational."
        )

        current_api_key = random.choice(self.api_keys) if self.api_keys else ""

        try:
            with httpx.stream(
                "POST",
                self.base_url,
                headers={"Authorization": f"Bearer {current_api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                },
                timeout=30.0,
            ) as response:
                response.raise_for_status()
                full_response = ""
                buffer = ""

                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        token = choices[0].get("delta", {}).get("content", "")
                        if not token:
                            continue
                        full_response += token
                        buffer += token

                        if buffer.endswith((".", "?", "!", ":", "\n")):
                            sentence = buffer.strip()
                            if len(sentence) > 2:
                                bus.publish(Event.TTS_ENQUEUE, sentence)
                            buffer = ""
                    except json.JSONDecodeError:
                        continue

                if buffer.strip():
                    bus.publish(Event.TTS_ENQUEUE, buffer.strip())

                self._history.append({"role": "user", "content": transcript})
                self._history.append({"role": "assistant", "content": full_response})
                # Keep history bounded (last 24 messages = 12 turns)
                self._history = self._history[-24:]
                logger.success("Conversational LLM response completed.")

        except Exception as e:
            logger.error(f"LLM conversational error: {e}")
            bus.publish(Event.TTS_ENQUEUE, "Sorry, I had trouble reaching the language model.")

    # ------------------------------------------------------------------
    # Path 2 — Tool-aware (JSON, single dispatch)
    # ------------------------------------------------------------------

    def _process_with_tools(self, transcript: str, model: str):
        logger.info("LLM path: tool-aware (JSON)")

        system_prompt = build_system_prompt(self.registry)
        messages = self._build_messages(transcript, system=system_prompt)

        current_api_key = random.choice(self.api_keys) if self.api_keys else ""

        try:
            with httpx.stream(
                "POST",
                self.base_url,
                headers={"Authorization": f"Bearer {current_api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.1,
                },
                timeout=45.0,
            ) as response:
                response.raise_for_status()
                raw = ""
                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        token = choices[0].get("delta", {}).get("content", "")
                        if token:
                            raw += token
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.error(f"LLM tool-aware error: {e}")
            bus.publish(Event.TTS_ENQUEUE, "Sorry, I had trouble reaching the language model.")
            return

        raw = raw.strip()
        logger.debug(f"LLM raw output: {raw[:300]}")

        # Try to parse as JSON tool call
        try:
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            parsed = json.loads(raw)
            action_type = parsed.get("action_type", "").lower()

            # Auto-correct if the model put the tool name in action_type by mistake
            if action_type != "tool_call" and action_type != "clarify":
                if "tool" in parsed and "args" in parsed:
                    action_type = "tool_call"

            if action_type == "tool_call":
                tool_name = parsed.get("tool", "")
                args = parsed.get("args", {})
                reasoning = parsed.get("reasoning", "")
                logger.info(f"Tool call: {tool_name}({args}) — {reasoning}")

                observation = self.registry.execute(tool_name, args)
                result_text = observation.content

                # Ask LLM to produce a spoken summary of the result
                summary = self._summarize_result(transcript, tool_name, result_text, model)
                bus.publish(Event.TTS_ENQUEUE, summary)

                self._history.append({"role": "user", "content": transcript})
                self._history.append({"role": "assistant", "content": summary})
                self._history = self._history[-24:]

            elif action_type == "clarify":
                question = parsed.get("question", "Can you clarify that?")
                bus.publish(Event.TTS_ENQUEUE, question)

            else:
                # Treat as a plain text response
                bus.publish(Event.TTS_ENQUEUE, raw)

        except (json.JSONDecodeError, KeyError):
            # LLM returned plain text — speak it directly
            logger.debug("LLM returned plain text (not JSON) in tool path — speaking directly.")
            bus.publish(Event.TTS_ENQUEUE, raw)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_messages(self, transcript: str, system: str) -> list[dict]:
        """Combine system prompt, conversation history, and new user message."""
        messages = [{"role": "system", "content": system}]
        messages.extend(self._history[-12:])  # last 6 turns
        messages.append({"role": "user", "content": transcript})
        return messages

    def _summarize_result(
        self, original_query: str, tool_name: str, result: str, model: str
    ) -> str:
        """
        Ask the LLM to convert a raw tool result into a natural spoken sentence.
        Falls back to the raw result if LLM call fails.
        """
        prompt = (
            f"The user asked: '{original_query}'\n"
            f"The tool '{tool_name}' returned:\n{result}\n\n"
            f"Summarize this result in one or two short, natural spoken sentences "
            f"suitable for a voice assistant. No markdown. No bullet points."
        )
        current_api_key = random.choice(self.api_keys) if self.api_keys else ""
        try:
            resp = httpx.post(
                self.base_url,
                headers={"Authorization": f"Bearer {current_api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a voice assistant. Summarize tool results naturally."},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "temperature": 0.3,
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", result).strip()
        except Exception as e:
            logger.warning(f"Result summarization failed: {e} — using raw result.")
            # Truncate long raw results for voice
            return result[:400] if len(result) > 400 else result
