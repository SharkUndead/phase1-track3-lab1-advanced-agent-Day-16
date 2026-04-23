from __future__ import annotations

import json
import time
from typing import Tuple

try:
    from openai import OpenAI
except ImportError:
    pass

from .schemas import QAExample, JudgeResult, ReflectionEntry
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM

# Maintained for backward compatibility if agents.py checks it
FAILURE_MODE_BY_QID = {}

def get_client() -> OpenAI:
    """Initialize OpenAI client."""
    return OpenAI()

def safe_json_loads(text: str) -> dict:
    """Safely parse JSON that might be wrapped in Markdown code blocks."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):]
    elif text.startswith("```"):
        text = text[len("```"):]
    
    if text.endswith("```"):
        text = text[:-len("```")]
        
    text = text.strip()
    
    try:
        return json.loads(text)
    except Exception:
        return {}

def call_llm_with_retry(messages: list[dict], response_format: dict | None = None) -> tuple[str, int]:
    """Execute LLM call with a 2-attempt retry block and fallback parsing."""
    client = get_client()
    kwargs = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.0,
    }
    
    if response_format:
        kwargs["response_format"] = response_format
        
    for attempt in range(2):
        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            
            # Use real token usage if available, fallback to length heuristic
            if response.usage:
                tokens = response.usage.total_tokens
            else:
                tokens = int(len(content) / 4)
                
            return content, tokens
        except Exception as e:
            if attempt == 1:
                # Return empty string to trigger fallback defaults instead of crashing
                print(f"LLM API Error: {e}")
                return "", 0
            time.sleep(1)
            
    return "", 0

def format_context(example: QAExample) -> str:
    """Format context strictly as specified."""
    return "\n".join([f"{c.title}: {c.text}" for c in example.context])


# -------------------------
# ACTOR
# -------------------------
def actor_answer(example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> tuple[str, int]:
    context_str = format_context(example)
    ref_mem_str = "\n".join(reflection_memory) if reflection_memory else "(none)"
    
    prompt = (
        f"Question:\n{example.question}\n\n"
        f"Context:\n{context_str}\n\n"
        f"Reflection memory:\n{ref_mem_str}"
    )
    
    messages = [
        {"role": "system", "content": ACTOR_SYSTEM},
        {"role": "user", "content": prompt}
    ]
    
    content, tokens = call_llm_with_retry(messages)
    
    # Estimate input tokens if API failed entirely
    if tokens == 0:
        tokens = int(len(prompt) / 4)
        
    return content.strip(), tokens


# -------------------------
# EVALUATOR
# -------------------------
def evaluator(example: QAExample, answer: str) -> tuple[JudgeResult, int]:
    prompt = f"Gold answer: {example.gold_answer}\nPredicted answer: {answer}"
    
    messages = [
        {"role": "system", "content": EVALUATOR_SYSTEM},
        {"role": "user", "content": prompt}
    ]
    
    content, tokens = call_llm_with_retry(messages, response_format={"type": "json_object"})
    data = safe_json_loads(content)
    
    score = int(data.get("score", 0))
    reason = str(data.get("reason", "Failed to parse Evaluator JSON"))
    missing = data.get("missing_evidence", [])
    spurious = data.get("spurious_claims", [])
    
    res = JudgeResult(
        score=score,
        reason=reason,
        missing_evidence=missing,
        spurious_claims=spurious
    )
    
    if tokens == 0:
        tokens = int(len(prompt) / 4)
        
    return res, tokens


# -------------------------
# REFLECTOR
# -------------------------
def reflector(example: QAExample, attempt_id: int, answer: str, judge: JudgeResult) -> tuple[ReflectionEntry, int]:
    context_str = format_context(example)
    
    prompt = (
        f"Question: {example.question}\n"
        f"Context:\n{context_str}\n\n"
        f"Predicted answer: {answer}\n"
        f"Evaluator reason: {judge.reason}\n"
        f"Missing evidence: {judge.missing_evidence}\n"
        f"Spurious claims: {judge.spurious_claims}\n"
    )
    
    messages = [
        {"role": "system", "content": REFLECTOR_SYSTEM},
        {"role": "user", "content": prompt}
    ]
    
    content, tokens = call_llm_with_retry(messages, response_format={"type": "json_object"})
    data = safe_json_loads(content)
    
    lesson = str(data.get("lesson", "Unknown failure reason."))
    next_strategy = str(data.get("next_strategy", "Try again by grounding the answer more carefully."))
    
    res = ReflectionEntry(
        attempt_id=attempt_id,
        failure_reason=judge.reason,
        lesson=lesson,
        next_strategy=next_strategy
    )
    
    if tokens == 0:
        tokens = int(len(prompt) / 4)
        
    return res, tokens
