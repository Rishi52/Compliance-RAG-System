import json


with open(
    "data/processed/cis_safeguards.json",
    "r",
    encoding="utf-8"
) as f:
    data = json.load(f)

unique_safeguards = set()

for item in data:
    unique_safeguards.add(item["safeguard_id"])

print("Total Records:", len(data))
print("Unique Safeguards:", len(unique_safeguards))