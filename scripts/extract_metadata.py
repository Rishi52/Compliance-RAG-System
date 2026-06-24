import pdfplumber
import re
import json

PDF_PATH = "data\\raw\\CIS_Controls_Guide_v8.1.2_0325_v2.pdf"
OUTPUT_PATH = "data\\processed\\cis_controls_metadata.json"

records = []

current_control_id = None
current_control_name = None

control_pattern = re.compile(r"CONTROL\s+(\d+)")
safeguard_pattern = re.compile(
    r"Safeguard\s+(\d+\.\d+):\s*(.+)")

with pdfplumber.open(PDF_PATH) as pdf:

    for page_num, page in enumerate(pdf.pages, start=1):

        text = page.extract_text()

        if not text:
            continue

        lines = text.split("\n")

        for i, line in enumerate(lines):

            # ------------------------
            # CONTROL DETECTION
            # ------------------------
            control_match = control_pattern.search(line)

            if control_match:

                current_control_id = control_match.group(1)

                # next line generally contains control name
                if i + 1 < len(lines):
                    current_control_name = lines[i + 1].strip()

            # ------------------------
            # SAFEGUARD DETECTION
            # ------------------------
            safeguard_match = safeguard_pattern.search(line)

            if safeguard_match:

                safeguard_id = safeguard_match.group(1)
                safeguard_name = safeguard_match.group(2)

                records.append(
                    {
                        "page": page_num,
                        "control_id": current_control_id,
                        "control_name": current_control_name,
                        "safeguard_id": safeguard_id,
                        "safeguard_name": safeguard_name
                    }
                )

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(records, f, indent=4)

print(f"Extracted {len(records)} safeguards")
print(f"Saved to {OUTPUT_PATH}")