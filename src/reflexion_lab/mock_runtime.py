from __future__ import annotations

from .schemas import QAExample, JudgeResult, ReflectionEntry

# Kept for backward compatibility if needed elsewhere
FAILURE_MODE_BY_QID = {}

# -------------------------
# Helper: format context
# -------------------------
def format_context(example: QAExample) -> str:
    return "\n".join([f"{c.title}: {c.text}" for c in example.context])


# -------------------------
# ACTOR
# -------------------------
def actor_answer(example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> tuple[str, int]:
    context_str = format_context(example)
    reflection_str = "\n".join(reflection_memory) if reflection_memory else "(none)"
    
    # Extract numerical ID to create deterministic, pseudo-random behavior
    try:
        qid_num = int(example.qid.replace("hp", ""))
    except ValueError:
        qid_num = sum(ord(c) for c in example.qid)
        
    mod = qid_num % 10
    
    # Attempt 1 (or ReAct agent): 50% success rate
    if attempt_id == 1 or not reflection_memory:
        if mod == 0:
            answer = "unknown"
        elif mod in [1, 3]:
            answer = "incomplete bridge entity"
        elif mod in [2, 4]:
            answer = "wrong extracted entity"
        else:
            answer = example.gold_answer
            
    # Attempt 2+ (Reflexion): Fixes some errors but not all (80% total success rate)
    else:
        if mod == 0:
            answer = "still unknown" # Unfixable failure
        elif mod == 4:
            answer = "another wrong entity" # Drifted again, unfixable
        else:
            answer = example.gold_answer # Successfully reflected and fixed
            
    # Simulate token usage: text length / 4
    prompt_len = len(example.question) + len(context_str) + len(reflection_str)
    token_estimate = int((prompt_len + len(answer)) / 4)
    
    return answer, token_estimate


# -------------------------
# EVALUATOR
# -------------------------
def evaluator(example: QAExample, answer: str) -> tuple[JudgeResult, int]:
    from .utils import normalize_answer
    
    prompt_len = len(example.gold_answer) + len(answer)
    
    # 1. Exact Match
    if normalize_answer(example.gold_answer) == normalize_answer(answer):
        res = JudgeResult(
            score=1, 
            reason="Final answer matches the gold answer after normalization.",
            missing_evidence=[],
            spurious_claims=[]
        )
    # 2. Gave up
    elif "unknown" in answer:
        res = JudgeResult(
            score=0, 
            reason="Agent gave up and failed to extract any entity.", 
            missing_evidence=["Failed to identify any relevant facts from the context."], 
            spurious_claims=[]
        )
    # 3. Incomplete multi-hop
    elif "incomplete" in answer:
        res = JudgeResult(
            score=0, 
            reason="The answer stopped at the first hop and never completed the second hop.", 
            missing_evidence=["Need to traverse from the bridge entity to the final entity."], 
            spurious_claims=[]
        )
    # 4. Entity drift / hallucination
    else:
        res = JudgeResult(
            score=0, 
            reason="The final answer selected the wrong entity from the context.", 
            missing_evidence=["Need to ground the answer using the exact constraint from the question."], 
            spurious_claims=[answer]
        )
        
    # Simulate token usage: text length / 4
    token_estimate = int((prompt_len + len(res.reason)) / 4)
    
    return res, token_estimate


# -------------------------
# REFLECTOR
# -------------------------
def reflector(example: QAExample, attempt_id: int, answer: str, judge: JudgeResult) -> tuple[ReflectionEntry, int]:
    context_str = format_context(example)
    
    prompt_len = len(example.question) + len(context_str) + len(answer) + len(judge.reason)
    
    if "unknown" in answer:
        lesson = "The agent failed to find any matching entity."
        strategy = "Search harder and re-read all context paragraphs systematically."
    elif "incomplete" in answer:
        lesson = "The agent stopped reasoning prematurely after identifying the bridge entity."
        strategy = "Identify the bridge entity, then explicitly look for the second-hop constraint."
    else:
        lesson = "The agent extracted a prominent but incorrect entity, failing to verify the specific constraint."
        strategy = "Check the exact constraint requested in the question before finalizing the entity extraction."
        
    res = ReflectionEntry(
        attempt_id=attempt_id, 
        failure_reason=judge.reason, 
        lesson=lesson, 
        next_strategy=strategy
    )
    
    # Simulate token usage: text length / 4
    token_estimate = int((prompt_len + len(lesson) + len(strategy)) / 4)
    
    return res, token_estimate