import json

with open(
    "data\\processed\\chunked_safeguards.json",
    "r",
    encoding="utf-8"
) as f:
    data = json.load(f)

print("Total Chunks:", len(data))
print()

print(data[0]["chunk_id"])
print(data[0]["safeguard_name"])
print(data[0]["content"])