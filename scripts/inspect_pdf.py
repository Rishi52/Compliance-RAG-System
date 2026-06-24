import pdfplumber

pdf_path = "data\\raw\\CIS_Controls_Guide_v8.1.2_0325_v2.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total Pages: {len(pdf.pages)}")

    # Check a few important pages
    pages_to_check = [19, 20, 21]  # pages where Control 1 starts

    for page_num in pages_to_check:
        page = pdf.pages[page_num]
        text = page.extract_text()

        print("\n" + "=" * 80)
        print(f"PAGE {page_num + 1}")
        print("=" * 80)

        if text:
            print(text[:2000])  # first 2000 chars
        else:
            print("No text extracted")