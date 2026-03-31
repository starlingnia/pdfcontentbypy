import fitz
import re
import os
import glob

# --- Logic from changecontent.py ---

def get_rough_toc(doc):
    """Scans the entire document for headings based on font size."""
    toc = []
    SIZE_H1 = 15.0
    SIZE_H2 = 12.0
    
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        pending_title = []
        pending_level = 0
        
        def flush_title():
            nonlocal pending_title, pending_level
            if pending_title and pending_level > 0:
                full_title = " ".join(pending_title).strip()
                if full_title.isdigit():
                    pass
                else:
                    blacklist = ["123", "Contents", "Table of Contents", "目录"]
                    if full_title not in blacklist:
                        toc.append([pending_level, full_title, page_num + 1])
            pending_title = []
            pending_level = 0

        for block in blocks:
            if "lines" not in block: continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    size = span["size"]
                    if not text: continue
                    
                    current_level = 0
                    if size > SIZE_H1:
                        current_level = 1
                    elif size > SIZE_H2:
                        current_level = 2
                    
                    if current_level == 0:
                        flush_title()
                    else:
                        if current_level == pending_level:
                            pending_title.append(text)
                        else:
                            flush_title()
                            pending_level = current_level
                            pending_title.append(text)
        flush_title()
    return toc

# --- Logic from pickcontent.py ---

def extract_detailed_toc_from_pages(doc, start_page, end_page):
    """Extracts detailed TOC from specific pages using regex."""
    extracted_toc = []
    sec_re = re.compile(r"^(([A-Z\d]+\.)+[A-Z\d]*|[A-Z\d]+\.)")
    page_re = re.compile(r"(\s+[\.·_-]*\s*|\.{2,}\s*)(\d+)$")

    for p in range(start_page - 1, end_page):
        if p >= len(doc): break
        page = doc[p]
        text = page.get_text("text")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        i = 0
        last_consumed_idx = -1
        while i < len(lines):
            line = lines[i]
            s_match = sec_re.match(line)
            if not s_match:
                i += 1
                continue

            section_num = s_match.group(0).strip()
            for j in range(i, min(i + 3, len(lines))):
                combined_text = " ".join(lines[i:j+1])
                p_match = page_re.search(combined_text)
                if p_match:
                    page_val = int(p_match.group(2))
                    title_text = combined_text[s_match.end():p_match.start()].strip()
                    title_text = re.sub(r'[\.·_-]{2,}', ' ', title_text)
                    title_text = re.sub(r'\s+', ' ', title_text).strip()
                    
                    if not title_text and i > 0 and i > last_consumed_idx + 1:
                        prev_line = lines[i-1]
                        if not sec_re.match(prev_line) and not page_re.search(prev_line):
                            title_text = prev_line
                    
                    dot_count = section_num.strip('.').count('.')
                    level = dot_count + 1
                    display_title = (section_num + " " + title_text).strip()
                    
                    if len(display_title) > 1:
                        extracted_toc.append([level, display_title, page_val])
                    
                    last_consumed_idx = j
                    i = j
                    break
            i += 1
    return extracted_toc

def get_section_num(title):
    """Extracts leading section number like '1.1' or '1.'"""
    match = re.match(r"^(([A-Z\d]+\.)+[A-Z\d]*|[A-Z\d]+\.)", title)
    return match.group(0).strip('.') if match else None

def normalize_title(title):
    """Normalize title for matching by removing section numbers and dots."""
    # Remove dots at the end (filler)
    title = re.sub(r'[\.·_-]{2,}', '', title)
    # Remove leading section numbers
    title = re.sub(r'^(([A-Z\d]+\.)+[A-Z\d]*|[A-Z\d]+\.)\s*', '', title)
    return title.lower().strip()

def main():
    pdf_files = glob.glob('*.pdf')
    pdf_files = [f for f in pdf_files if '_fixed' not in f and '_final' not in f]
    if not pdf_files:
        print("No PDF found.")
        return
    
    input_pdf = pdf_files[0]
    doc = fitz.open(input_pdf)
    
    print(f"[*] Analyzing {input_pdf}...")
    
    # 1. Get rough TOC from body
    rough_toc = get_rough_toc(doc)
    print(f"[*] Found {len(rough_toc)} major items in body.")

    # 2. Identify TOC ranges and parts
    contents_pages = []
    for page_num, page in enumerate(doc):
        text = page.get_text("text")[:100].strip()
        if text.startswith("Contents") or "Table of Contents" in text:
            contents_pages.append(page_num + 1)
    
    # Deduplicate Contents pages that are very close (e.g., multi-page TOC)
    unique_contents = []
    if contents_pages:
        unique_contents.append(contents_pages[0])
        for cp in contents_pages[1:]:
            if cp > unique_contents[-1] + 20: 
                unique_contents.append(cp)
    
    if not unique_contents:
        unique_contents = [12] # Default fallback

    print(f"[*] Found Contents pages at: {unique_contents}")
    
    # Define parts of the document based on unique_contents
    # Part 1: from first Contents until next Contents
    # Part 2: from second Contents until next Contents...
    parts = []
    for i, cp in enumerate(unique_contents):
        start_body = cp
        end_body = unique_contents[i+1] if i+1 < len(unique_contents) else len(doc)
        parts.append({
            'toc_start': cp,
            'body_range': (start_body, end_body)
        })

    final_toc = []
    current_offset = 0
    
    for part in parts:
        print(f"[*] Processing part starting with Contents on P{part['toc_start']}...")
        detailed_items = extract_detailed_toc_from_pages(doc, part['toc_start'], part['toc_start'] + 20)
        print(f"  - Found {len(detailed_items)} detailed items in this part's TOC.")
        
        # Filter rough_toc for this part
        part_rough_toc = [item for item in rough_toc if part['body_range'][0] <= item[2] <= part['body_range'][1]]
        
        # Match within this part
        for det_item in detailed_items:
            det_level, det_title, det_page = det_item
            det_norm = normalize_title(det_title)
            det_sec = get_section_num(det_title)
            
            match_found = False
            for rough_level, rough_title, rough_page in part_rough_toc:
                rough_norm = normalize_title(rough_title)
                rough_sec = get_section_num(rough_title)
                
                # Match section number (best)
                if det_sec and rough_sec and det_sec == rough_sec:
                    match_found = True
                # Match title (exact or good substring)
                elif det_norm and rough_norm and (det_norm == rough_norm or (len(det_norm) > 12 and det_norm in rough_norm)):
                    match_found = True
                
                if match_found:
                    if det_level == 1:
                        new_offset = rough_page - det_page
                        if new_offset != current_offset:
                            print(f"    [Match] '{det_title}' -> P{rough_page} (Printed P{det_page}). New offset: {new_offset}")
                            current_offset = new_offset
                    break
            
            # Corrected page number
            corrected_page = det_page + current_offset
            if corrected_page < 1 or corrected_page > len(doc):
                print(f"    [!] Warning: Corrected page {corrected_page} out of range for '{det_title}'. Using printed page {det_page}.")
                corrected_page = det_page # Fallback

            final_toc.append([det_level, det_title, corrected_page])

    if final_toc:
        # Re-insert the book titles from rough_toc (L1)
        book_titles = [item for item in rough_toc if item[0] == 1]
        for bt in book_titles:
            exists = any(abs(item[2] - bt[2]) < 2 for item in final_toc)
            if not exists:
                final_toc.append(bt)
        
        final_toc.sort(key=lambda x: x[2])
        
        print("[*] Normalizing hierarchy levels...")
        normalized_toc = []
        for i, (level, title, page) in enumerate(final_toc):
            if i == 0:
                new_level = 1
            else:
                prev_level = normalized_toc[-1][0]
                new_level = min(level, prev_level + 1)
            normalized_toc.append([new_level, title, page])

        output_pdf = input_pdf.replace(".pdf", "_final.pdf")
        doc.set_toc(normalized_toc)
        doc.save(output_pdf)
        print(f"[*] Successfully processed {len(normalized_toc)} items.")
        print(f"[*] Final PDF saved as: {output_pdf}")
    else:
        print("[!] No TOC items generated.")

if __name__ == "__main__":
    main()
