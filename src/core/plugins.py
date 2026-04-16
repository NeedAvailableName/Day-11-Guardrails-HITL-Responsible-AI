"""
Production-grade ADK Plugins for Lab 11 Assignment (Enhanced Resilience)
"""
import time
import json
import re
from collections import defaultdict, deque
from datetime import datetime

from google.adk.plugins import base_plugin
from google.genai import types

# --- 1. Rate Limiter ---
class RateLimitPlugin(base_plugin.BasePlugin):
    """Blocks users who send too many requests in a specific time window."""

    def __init__(self, max_requests=10, window_seconds=60):
        super().__init__(name="rate_limiter")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Global window for simplicity in lab, or per user if context available
        self.user_windows = defaultdict(deque)
        self.blocked_count = 0

    async def on_user_message_callback(self, *, invocation_context, user_message):
        # Fallback to 'anonymous' if context is empty
        user_id = str(getattr(invocation_context, "user_id", "anonymous"))
        now = time.time()
        window = self.user_windows[user_id]

        # Clean up old timestamps
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        if len(window) >= self.max_requests:
            self.blocked_count += 1
            wait_time = int(window[0] + self.window_seconds - now)
            # Ensure wait_time is at least 1
            wait_time = max(1, wait_time)
            return types.Content(
                role="model",
                parts=[types.Part.from_text(text=f"Rate limit exceeded. Please wait {wait_time} seconds.")]
            )

        window.append(now)
        return None  # Allow


# --- 2. Audit Logger ---
class AuditLogPlugin(base_plugin.BasePlugin):
    """Records every interaction for security monitoring and forensics."""

    def __init__(self, log_file="audit_log.json"):
        super().__init__(name="audit_log")
        self.log_file = log_file
        self.logs = []
        self.active_requests = {}

    def _extract_text(self, content: types.Content) -> str:
        if not content or not content.parts: return ""
        return "".join(p.text for p in content.parts if hasattr(p, 'text') and p.text)

    async def on_user_message_callback(self, *, invocation_context, user_message):
        req_id = id(invocation_context)
        input_text = self._extract_text(user_message)

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "input": input_text,
            "start_time": time.time(),
            "status": "pending",
            "blocked": False
        }
        self.logs.append(log_entry)
        self.active_requests[req_id] = log_entry
        self.export_logs()
        return None

    async def after_model_callback(self, *, callback_context, llm_response):
        req_id = id(callback_context)
        entry = self.active_requests.get(req_id)
        
        if entry:
            end_time = time.time()
            entry["latency_ms"] = int((end_time - entry["start_time"]) * 1000)
            entry["output"] = self._extract_text(llm_response.content)
            entry["status"] = "success"
        
        self.export_logs()
        return llm_response

    def export_logs(self):
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(self.logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Audit log export error: {e}")


# --- 3. Enhanced LLM Judge ---
class EnhancedLlmJudgePlugin(base_plugin.BasePlugin):
    """Uses a separate LLM to evaluate responses on multiple quality criteria."""

    def __init__(self, judge_agent, judge_runner):
        super().__init__(name="enhanced_judge")
        self.judge_agent = judge_agent
        self.judge_runner = judge_runner
        self.fail_count = 0

    async def after_model_callback(self, *, callback_context, llm_response):
        if not llm_response.content or not llm_response.content.parts:
            return llm_response

        response_text = "".join(p.text for p in llm_response.content.parts if hasattr(p, 'text'))
        
        judge_prompt = f"Evaluate this AI response:\n\n{response_text}"
        from core.utils import chat_with_agent
        try:
            # Short timeout or error handling for quota
            verdict_text, _ = await chat_with_agent(self.judge_agent, self.judge_runner, judge_prompt)
            if "VERDICT: FAIL" in verdict_text.upper():
                self.fail_count += 1
                llm_response.content = types.Content(
                    role="model",
                    parts=[types.Part.from_text(text="I'm sorry, but my response was flagged for safety. How else can I help with your banking?")]
                )
        except Exception as e:
            print(f"Warning: Enhanced Judge error: {e}")
        
        return llm_response
