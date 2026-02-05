#!/usr/bin/env python3
"""
Extract PDF to clean text with proper paragraph handling.
Handles multi-column layouts and removes noise.
"""

import pymupdf
import re
import sys
from pathlib import Path


def extract_pdf_to_clean_text(pdf_path: str, output_path: str = None):
    """Extract PDF with layout-aware text extraction."""
    
    doc = pymupdf.open(pdf_path)
    
    all_text = []
    
    for page_num, page in enumerate(doc, 1):
        # Use "text" extraction with layout preservation
        # This handles columns better than raw extraction
        text = page.get_text("text", sort=True)
        
        # Clean up the text
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Skip page numbers (standalone numbers)
            if re.match(r'^\d{1,3}$', line):
                continue
                
            # Skip figure/table references that are just numbers
            if re.match(r'^Figure \d+\.\d+$', line):
                continue
                
            # Skip lines that are just section numbers
            if re.match(r'^\d+\.\d+(\.\d+)?$', line):
                continue
            
            cleaned_lines.append(line)
        
        # Join lines, handling hyphenation and sentence continuation
        page_text = ""
        for i, line in enumerate(cleaned_lines):
            # If line ends with hyphen, join without space
            if line.endswith('-'):
                page_text += line[:-1]
            # If next line starts lowercase, it's a continuation
            elif i < len(cleaned_lines) - 1 and cleaned_lines[i+1] and cleaned_lines[i+1][0].islower():
                page_text += line + " "
            else:
                page_text += line + "\n"
        
        if page_text.strip():
            all_text.append(f"\n--- Page {page_num} ---\n")
            all_text.append(page_text)
    
    num_pages = len(doc)
    doc.close()
    
    final_text = "".join(all_text)
    
    # Post-processing cleanup
    # Remove excessive whitespace
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)
    # Remove weird spacing patterns
    final_text = re.sub(r'  +', ' ', final_text)
    
    if output_path:
        Path(output_path).write_text(final_text, encoding='utf-8')
        print(f"Extracted {num_pages} pages to {output_path}")
        print(f"Total characters: {len(final_text)}")
    
    return final_text


def extract_with_blocks(pdf_path: str, output_path: str = None):
    """Alternative extraction using text blocks for better structure."""
    
    doc = pymupdf.open(pdf_path)
    all_text = []
    
    for page_num, page in enumerate(doc, 1):
        blocks = page.get_text("blocks", sort=True)
        
        page_text = []
        for block in blocks:
            if block[6] == 0:  # Text block (not image)
                text = block[4].strip()
                
                # Skip noise
                if not text:
                    continue
                if re.match(r'^\d{1,3}$', text):  # Page numbers
                    continue
                if len(text) < 3:  # Very short noise
                    continue
                    
                # Clean up internal whitespace
                text = re.sub(r'\s+', ' ', text)
                page_text.append(text)
        
        if page_text:
            all_text.append(f"\n\n=== Page {page_num} ===\n\n")
            all_text.append("\n\n".join(page_text))
    
    num_pages = len(doc)
    doc.close()
    
    final_text = "".join(all_text)
    
    if output_path:
        Path(output_path).write_text(final_text, encoding='utf-8')
        print(f"Extracted {len(doc)} pages to {output_path}")
        print(f"Total characters: {len(final_text)}")
    
    return final_text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extract_pdf_clean.py <input.pdf> [output.txt]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else pdf_path.replace('.pdf', '_clean.txt')
    
    print(f"Extracting {pdf_path}...")
    print("Method 1: Line-based extraction")
    extract_pdf_to_clean_text(pdf_path, output_path)
    
    # Also try block-based
    block_output = output_path.replace('.txt', '_blocks.txt')
    print(f"\nMethod 2: Block-based extraction")
    extract_with_blocks(pdf_path, block_output)
    
    print(f"\nDone! Compare both outputs to see which is cleaner.")
