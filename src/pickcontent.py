#!/usr/bin/env python3
import fitz  # PyMuPDF
import re
import os
import glob
import argparse
from typing import List, Tuple, Optional

def extract_toc_from_pages(
    input_pdf: str, 
    toc_pages: Tuple[int, int], 
    page_offset: int = 0
) -> Optional[List[List]]:
    """
    Extracts TOC from specific pages of a PDF using visual structure analysis.
    
    Logic:
    1. Scan a range of pages for text lines.
    2. Identify entries starting with a section number (e.g., "1.", "2.3").
    3. Find the corresponding page number on the same or subsequent lines.
    4. Construct a hierarchical TOC structure.
    
    :param input_pdf: Path to the input PDF file.
    :param toc_pages: A tuple of (start_page, end_page) for the TOC pages (1-indexed).
    :param page_offset: Number to add to the extracted page number to get the real PDF page index.
    """
    if not os.path.exists(input_pdf):
        print(f"Error: File '{input_pdf}' not found.")
        return None

    try:
        doc = fitz.open(input_pdf)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return None

    extracted_toc = []
    
    # Regex for Section Number (e.g., 1., 1.1., A.1)
    sec_re = re.compile(r"^(([A-Z\d]+\.)+[A-Z\d]*|[A-Z\d]+\.)")
    # Regex for Page Number (must have preceding dots/spaces and be at end of line)
    page_re = re.compile(r"(\s+[\.·_-]*\s*|\.{2,}\s*)(\d+)$")

    print(f"[*] Analyzing: {os.path.basename(input_pdf)}")
    print(f"[*] Scanning TOC pages: {toc_pages[0]} to {toc_pages[1]} with offset {page_offset}")

    for p in range(toc_pages[0] - 1, toc_pages[1]):
        if p >= len(doc):
            break
        
        page = doc[p]
        text = page.get_text("text")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        i = 0
        last_consumed_idx = -1
        while i < len(lines):
            line = lines[i]
            
            # 1. Start with a Section Number?
            s_match = sec_re.match(line)
            if not s_match:
                i += 1
                continue

            section_num = s_match.group(0).strip()
            entry_closed = False
            
            # 2. Find Page Number (Look ahead up to 3 lines)
            for j in range(i, min(i + 3, len(lines))):
                combined_text = " ".join(lines[i:j+1])
                p_match = page_re.search(combined_text)
                
                if p_match:
                    page_val = int(p_match.group(2))
                    
                    # Extract title physically between section number and page number
                    title_text = combined_text[s_match.end():p_match.start()].strip()
                    
                    # Clean Title: Remove filler characters
                    title_text = re.sub(r'[\.·_-]{2,}', ' ', title_text)
                    title_text = re.sub(r'\s+', ' ', title_text).strip()
                    
                    # Heuristic: If title is empty, it might be on the line BEFORE the section number
                    if not title_text and i > 0 and i > last_consumed_idx + 1:
                        prev_line = lines[i-1]
                        if not sec_re.match(prev_line) and not page_re.search(prev_line):
                            title_text = prev_line
                    
                    # Determine hierarchy level from section number dots
                    # "1." -> Level 1; "1.1." -> Level 2
                    dot_count = section_num.strip('.').count('.')
                    level = dot_count + 1

                    display_title = (section_num + " " + title_text).strip()
                    dest_page = page_val + page_offset
                    
                    if len(display_title) > 1:
                        extracted_toc.append([level, display_title, dest_page])
                        # print(f"  [Found] L{level} | {display_title[:60]:<60} | P{dest_page}")
                    
                    last_consumed_idx = j
                    i = j
                    entry_closed = True
                    break
            
            i += 1

    if not extracted_toc:
        print("[!] Warning: No valid TOC items identified.")
        doc.close()
        return None

    # Normalization for PDF hierarchy compliance (no level jumps)
    print("[*] Normalizing hierarchy levels...")
    normalized_toc = []
    for i, (level, title, page) in enumerate(extracted_toc):
        if i == 0:
            new_level = 1
        else:
            prev_level = normalized_toc[-1][0]
            new_level = min(level, prev_level + 1)
        normalized_toc.append([new_level, title, page])

    # Save fixed PDF
    output_pdf = input_pdf.replace(".pdf", "_fixed.pdf")
    try:
        doc.set_toc(normalized_toc)
        doc.save(output_pdf)
        print(f"[*] Successfully processed {len(normalized_toc)} items.")
        print(f"[*] Refined PDF saved as: {output_pdf}")
    except Exception as e:
        print(f"Error saving PDF: {e}")
    finally:
        doc.close()
    
    return normalized_toc

def main():
    parser = argparse.ArgumentParser(description="Extract TOC from PDF pages and set as outline.")
    parser.add_argument("file", nargs="?", help="PDF file to process")
    parser.add_argument("--start", type=int, default=12, help="Start page of TOC (1-indexed)")
    parser.add_argument("--end", type=int, default=23, help="End page of TOC (1-indexed)")
    parser.add_argument("--offset", type=int, default=23, help="Page offset (number added to TOC page numbers)")
    
    args = parser.parse_args()
    
    if args.file:
        extract_toc_from_pages(args.file, (args.start, args.end), args.offset)
    else:
        # Auto-detect PDF if no file provided
        pdf_files = glob.glob('*.pdf')
        pdf_files = [f for f in pdf_files if '_fixed' not in f]
        if pdf_files:
            # Default for Zeidler book if no args provided and file exists
            TARGET_FILE = pdf_files[0]
            extract_toc_from_pages(TARGET_FILE, (args.start, args.end), args.offset)
        else:
            print("No PDF files found in current directory.")

if __name__ == "__main__":
    main()
