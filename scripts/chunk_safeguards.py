import json
from langchain_text_splitters import RecursiveCharacterTextSplitter

INPUT_FILE = "data\\processed\\cis_safeguards.json"
OUTPUT_FILE = "data\\processed\\chunked_safeguards.json"

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    safeguards = json.load(f)

splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=600,
    chunk_overlap=100
)

chunked_records = []

for record in safeguards:
    chunks = splitter.split_text(record["content"])
    for idx, chunk in enumerate(chunks):
        chunked_records.append(
            {
                "chunk_id": f"{record['safeguard_id']}_{idx}",
                "page": record["page"],
                "control_id": record["control_id"],
                "control_name": record["control_name"],
                "safeguard_id": record["safeguard_id"],
                "safeguard_name": record["safeguard_name"],
                "content": chunk
            }
        )

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(chunked_records, f, indent=4)

print(f"Created {len(chunked_records)} chunks")
print(f"Saved to {OUTPUT_FILE}")