
from datasets import load_dataset

dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
instance = next(item for item in dataset if item["instance_id"] == "pylint-dev__pylint-7080")
print(f"Problem: {instance['problem_statement'][:2000]}...") # Truncate because it's huge
print(f"Hints: {instance['hints_text']}")
