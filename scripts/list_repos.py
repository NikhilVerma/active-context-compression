
from datasets import load_dataset

def list_candidates():
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    # Group by repo
    candidates = {}
    for item in dataset:
        repo = item["repo"]
        if repo not in candidates:
            candidates[repo] = []
        candidates[repo].append(item["instance_id"])
        
    print("Available Repos and Counts:")
    for repo, ids in candidates.items():
        print(f"{repo}: {len(ids)} instances")
        # Print first 2 IDs as examples
        print(f"  e.g., {ids[:2]}")

if __name__ == "__main__":
    list_candidates()
