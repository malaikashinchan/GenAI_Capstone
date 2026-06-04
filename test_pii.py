import json, glob
files = sorted(glob.glob("metadata/batch_history*.json"))
if files:
    with open(files[-1]) as f:
        data = json.load(f)
        print("Heal log from last batch:")
        for entry in data[-1].get("heal_log", []):
            print(f"[{entry['retry_num']}] {entry['node']} | {entry['error_type']} | {entry['error_msg'][:60]}")
