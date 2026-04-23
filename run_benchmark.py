from __future__ import annotations

import json
from pathlib import Path
from tqdm import tqdm
from itertools import islice

from datasets import load_dataset

from src.reflexion_lab.agents import ReflexionAgent
from src.reflexion_lab.schemas import QAExample, ContextChunk
from src.reflexion_lab.utils import normalize_answer, save_jsonl
from src.reflexion_lab.reporting import build_report, save_report

def classify_difficulty(row: dict) -> str:
    """
    Classify difficulty based on the number of supporting facts and context paragraphs.
    """
    num_facts = len(row.get("supporting_facts", {}).get("title", []))
    num_ctx = len(row.get("context", {}).get("title", []))
    
    # Heuristic based on typical HotpotQA fullwiki (10 context paragraphs, 2-4 facts)
    score = num_facts + num_ctx
    if score <= 12:
        return "easy"
    elif score == 13:
        return "medium"
    else:
        return "hard"

def fetch_hotpot_samples(n_samples: int = 100) -> list[QAExample]:
    """
    Load HotpotQA validation set (streaming), classify difficulty,
    enforce a stratified quota (40/40/20), and save the dataset.
    """
    out_file = Path(f"data/hotpot_stratified_{n_samples}.json")
    if out_file.exists():
        print("Loaded dataset from local file")
        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            loaded_examples = [QAExample(**ex) for ex in data[:n_samples]]
            print(f"Total loaded examples: {len(loaded_examples)}")
            return loaded_examples
            
    print("Streaming HotpotQA dataset...")
    dataset_stream = load_dataset("hotpot_qa", "fullwiki", split="validation", streaming=True)
    
    easy_q = int(n_samples * 0.4)
    med_q = int(n_samples * 0.4)
    hard_q = n_samples - easy_q - med_q
    
    quotas = {"easy": easy_q, "medium": med_q, "hard": hard_q}
    samples_by_diff = {"easy": [], "medium": [], "hard": []}
    
    for row in dataset_stream:
        diff = classify_difficulty(row)
        
        if len(samples_by_diff[diff]) < quotas[diff]:
            # Map context to ContextChunk
            context_chunks = []
            for title, sentences in zip(row["context"]["title"], row["context"]["sentences"]):
                context_chunks.append(ContextChunk(title=title, text=" ".join(sentences)))
            
            example = QAExample(
                qid="",  # Placeholder, assigned later
                difficulty=diff,
                question=row["question"],
                gold_answer=row["answer"],
                context=context_chunks
            )
            samples_by_diff[diff].append(example)
            
        # Stop streaming once all quotas are met
        if all(len(samples_by_diff[d]) == quotas[d] for d in quotas):
            break
            
    # Combine and assign sequential QIDs
    final_examples = samples_by_diff["easy"] + samples_by_diff["medium"] + samples_by_diff["hard"]
    for i, ex in enumerate(final_examples):
        ex.qid = f"hp{i}"
        
    # Print Distribution
    counts = {d: len(samples_by_diff[d]) for d in quotas}
    print(f"Difficulty Distribution: {counts}")
    
    # Save to data/hotpot_stratified_{n_samples}.json
    out_file = Path(f"data/hotpot_stratified_{n_samples}.json")
    out_file.parent.mkdir(exist_ok=True, parents=True)
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump([ex.model_dump() for ex in final_examples], f, indent=2, ensure_ascii=False)
        
    print(f"Saved stratified dataset to: {out_file}")
    print(f"Total loaded examples: {len(final_examples)}")
    
    return final_examples

def main(out_dir: str = "outputs/hotpot_100_run", reflexion_attempts: int = 3) -> None:
    print("Running in MOCK mode (no API calls)")
    # 1. Fetch and map dataset
    examples = fetch_hotpot_samples(100)
    
    # 2. Initialize the agent (Ensure agents.py imports llm_runtime to prevent mock leakage)
    agent = ReflexionAgent(max_attempts=reflexion_attempts)
    
    records = []
    correct_count = 0
    
    print(f"\nRunning QA Pipeline on {len(examples)} examples...")
    
    # 3. Pipeline Execution with Progress Logging
    for i, example in enumerate(tqdm(examples, desc="Evaluating")):
        record = agent.run(example)
        records.append(record)
        
        # 4. Evaluation using exact string normalization
        pred_norm = normalize_answer(record.predicted_answer)
        gold_norm = normalize_answer(record.gold_answer)
        is_match = (pred_norm == gold_norm)
        
        if is_match:
            correct_count += 1
            
        # 5. Debug Visibility (Print first 3 samples)
        if i < 3:
            tqdm.write(f"\n--- Debug Sample {i+1} ---")
            tqdm.write(f"Question:   {example.question}")
            tqdm.write(f"Predicted:  {record.predicted_answer}")
            tqdm.write(f"Gold:       {example.gold_answer}")
            tqdm.write(f"Match:      {is_match} (Pred Norm: '{pred_norm}' | Gold Norm: '{gold_norm}')")
            tqdm.write("-" * 25)

        # 6. Intermittent Progress Logging (Every 10 samples)
        if (i + 1) % 10 == 0:
            current_acc = (correct_count / (i + 1)) * 100
            tqdm.write(f"Processed {i + 1}/100 - Running Accuracy: {current_acc:.1f}%")

    # Compute final accuracy
    final_accuracy = correct_count / len(examples)
    
    print(f"\nTotal processed examples: {len(records)}")
    
    # 7. Safeguard: Detect fake accuracy
    if final_accuracy == 1.0:
        print("\nWARNING: Suspicious 100% accuracy — check for data leakage or mock logic!")

    # Save standard lab artifacts
    out_path = Path(out_dir)
    save_jsonl(out_path / "reflexion_runs.jsonl", records)
    
    report = build_report(records, dataset_name="hotpot_qa_val_100", mode="mock")
    json_path, md_path = save_report(report, out_path)
    
    # Final Output Display
    print("\n" + "="*40)
    print("           FINAL RESULTS")
    print("="*40)
    print(f"Total Evaluated: {len(examples)}")
    print(f"Correct Answers: {correct_count}")
    print(f"Final Accuracy:  {final_accuracy:.2%}")
    print(f"\nArtifacts saved to: {out_dir}")

if __name__ == "__main__":
    main()
