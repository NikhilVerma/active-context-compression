
from datasets import load_dataset

dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
instance = next(item for item in dataset if item["instance_id"] == "django__django-11019")
print(f"Problem: {instance['problem_statement']}")
print(f"Hints: {instance['hints_text']}")
