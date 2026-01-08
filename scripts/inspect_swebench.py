
from datasets import load_dataset
import statistics

def analyze_swebench():
    print("Loading SWE-bench Lite dataset...")
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    
    print(f"Total instances: {len(dataset)}")
    
    instances = []
    for item in dataset:
        instances.append({
            "id": item["instance_id"],
            "repo": item["repo"],
            "desc_len": len(item["problem_statement"]),
            "patch_lines": len(item["patch"].splitlines()),
            "test_lines": len(item["test_patch"].splitlines())
        })
    
    # Sort by description length
    print("\nTop 5 by problem statement length:")
    sorted_by_desc = sorted(instances, key=lambda x: x["desc_len"], reverse=True)
    for i in sorted_by_desc[:5]:
        print(f"{i['id']} ({i['repo']}): {i['desc_len']} chars")
        
    # Sort by patch size (complexity of fix)
    print("\nTop 5 by patch lines:")
    sorted_by_patch = sorted(instances, key=lambda x: x["patch_lines"], reverse=True)
    for i in sorted_by_patch[:5]:
        print(f"{i['id']} ({i['repo']}): {i['patch_lines']} lines")

    # Group by repo
    repo_counts = {}
    for i in instances:
        repo_counts[i["repo"]] = repo_counts.get(i["repo"], 0) + 1
        
    print("\nInstances by repository:")
    for repo, count in sorted(repo_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{repo}: {count}")

if __name__ == "__main__":
    analyze_swebench()
