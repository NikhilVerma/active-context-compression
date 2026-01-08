
from datasets import load_dataset

dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
instance = next(item for item in dataset if item["instance_id"] == "pallets__flask-5063")
print(f"Problem: {instance['problem_statement'][:500]}...")
