import fitz  # PyMuPDF
import re
import os
import glob

def extract_toc_from_pages(input_pdf, toc_pages, page_offset=0):
    """
    EXTREME STRICT MODE (Enhanced):
    1. Entry MUST start with a Section Number (e.g., "1.", "1.1").
    2. Search up to 3 lines to find the closing Page Number.
    3. Title is the text physically between Section Number and Page Number.
    4. If Title is empty/dots, pull it from the immediate previous unused line.
    5. Determine Level strictly from Section Number dots.
    """
    if not os.path.exists(input_pdf):
        print(f"Error: File '{input_pdf}' not found.")
        return

    doc = fitz.open(input_pdf)
    extracted_toc = []
    
    # 1. Regex for Section Number (MUST be at the start of a line)
    sec_re = re.compile(r"^(([A-Z\d]+\.)+[A-Z\d]*|[A-Z\d]+\.)")
    
    # 2. Regex for Page Number (at the end of a line)
    # Require leading dots or significant space to confirm it's a page field
    page_re = re.compile(r"(\s+[\.·_-]*\s*|\.{2,}\s*)(\d+)$")

    print(f"--- Analyzing: {os.path.basename(input_pdf)} ---")

    for p in range(toc_pages[0] - 1, toc_pages[1]):
        if p >= len(doc): break
        
        page = doc[p]
        text = page.get_text("text")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        i = 0
        last_consumed_idx = -1
        while i < len(lines):
            line = lines[i]
            
            # Every valid entry MUST start with a Section Number
            s_match = sec_re.match(line)
            if not s_match:
                # Discard lines with no section number at start
                i += 1
                continue

            section_num = s_match.group(0).strip()
            entry_closed = False
            
            # Look ahead up to 3 lines to find the closing Page Number
            for j in range(i, min(i + 3, len(lines))):
                combined_text = " ".join(lines[i:j+1])
                p_match = page_re.search(combined_text)
                
                if p_match:
                    page_val = int(p_match.group(2))
                    # Extract title text between Section Number end and Page Number start
                    s_m_final = sec_re.match(combined_text)
                    title_text = combined_text[s_m_final.end():p_match.start()].strip()
                    
                    # Clean Title (Remove filler dots)
                    title_text = re.sub(r'[\.·_-]{2,}', ' ', title_text)
                    title_text = re.sub(r'\s+', ' ', title_text).strip()
                    
                    # FIX: If title is empty, it might be on the line BEFORE the section number
                    if not title_text and i > 0 and i > last_consumed_idx + 1:
                        prev_line = lines[i-1]
                        # Ensure the previous line wasn't a TOC entry itself
                        if not sec_re.match(prev_line) and not page_re.search(prev_line):
                            title_text = prev_line
                    
                    # Level is strictly based on dots in the section number
                    # 1. (0 dots) -> L1; 1.1 (1 dot) -> L2; 1.1.1 (2 dots) -> L3
                    dot_count = section_num.strip('.').count('.')
                    level = dot_count + 1

                    display_title = (section_num + " " + title_text).strip()
                    dest_page = page_val + page_offset
                    
                    if len(display_title) > 1:
                        extracted_toc.append([level, display_title, dest_page])
                        print(f"  [Found] L{level} | {display_title[:60]:<60} | P{dest_page}")
                    
                    last_consumed_idx = j
                    i = j
                    entry_closed = True
                    break
            
            if not entry_closed:
                # Discard sections that don't have a page number within 3 lines
                pass
            
            i += 1

    if not extracted_toc:
        print("Error: No valid TOC items identified.")
        doc.close()
        return

    # Normalization for PDF hierarchy compliance
    print("\nNormalizing hierarchy levels...")
    normalized_toc = []
    for i, (level, title, page) in enumerate(extracted_toc):
        if i == 0:
            new_level = 1
        else:
            prev_level = normalized_toc[-1][0]
            new_level = min(level, prev_level + 1)
        normalized_toc.append([new_level, title, page])

    doc.set_toc(normalized_toc)
    output_pdf = input_pdf.replace(".pdf", "_fixed.pdf")
    doc.save(output_pdf)
    doc.close()
    print(f"\nSuccessfully processed {len(normalized_toc)} items.")
    print(f"Refined PDF saved as: {output_pdf}")

if __name__ == "__main__":
    pdf_files = glob.glob('*.pdf')
    pdf_files = [f for f in pdf_files if '_fixed' not in f]
    if pdf_files:
        TARGET_FILE = pdf_files[0]
        # TOC pages for Zeidler QFT book
        TOC_RANGE = [12, 23] 
        OFFSET = 23 
        extract_toc_from_pages(TARGET_FILE, TOC_RANGE, OFFSET)
