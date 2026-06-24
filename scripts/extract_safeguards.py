import pdfplumber
import re
import json

PDF_PATH = "data\\raw\\CIS_Controls_Guide_v8.1.2_0325_v2.pdf"
OUTPUT_PATH = "data\\processed\\cis_safeguards.json"

CONTROL_START_PAGE = 20
CONTROL_END_PAGE = 95

records = []

current_control_id = None
current_control_name = None

control_pattern = re.compile(r"CONTROL\s+(\d+)")
safeguard_pattern = re.compile(
    r"Safeguard\s+(\d+\.\d+):\s*(.+)"
)

with pdfplumber.open(PDF_PATH) as pdf:

    for page_num, page in enumerate(
            pdf.pages[CONTROL_START_PAGE - 1 : CONTROL_END_PAGE],
            start=CONTROL_START_PAGE):

        text = page.extract_text()

        if not text:
            continue

        # Detect Control
        lines = text.split("\n")

        for i, line in enumerate(lines):

            control_match = control_pattern.search(line)

            if control_match:

                current_control_id = control_match.group(1)

                if i + 1 < len(lines):
                    current_control_name = lines[i + 1].strip()

        # Detect Safeguards
        matches = list(
            safeguard_pattern.finditer(text)
        )

        for idx, match in enumerate(matches):

            safeguard_id = match.group(1)
            safeguard_name = match.group(2)

            start = match.end()

            if idx < len(matches) - 1:
                end = matches[idx + 1].start()
            else:
                end = len(text)

            content = text[start:end].strip()

            records.append(
                {
                    "page": page_num,
                    "control_id": current_control_id,
                    "control_name": current_control_name,
                    "safeguard_id": safeguard_id,
                    "safeguard_name": safeguard_name,
                    "content": content
                }
            )

unique_records = {}

for record in records:
    unique_records[record["safeguard_id"]] = record

records = list(unique_records.values())

with open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8"
) as f:
    json.dump(records, f, indent=4)

print(f"Extracted {len(records)} safeguards")
print(f"Saved to {OUTPUT_PATH}")