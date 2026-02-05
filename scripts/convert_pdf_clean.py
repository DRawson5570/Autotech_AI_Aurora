#!/usr/bin/env python3
"""
Convert a PDF to a clean format by rendering pages as images.
This bypasses corrupted embedded image metadata that causes reshape errors.

Outputs:
- HTML file with embedded images (best for RAG - text + images)
- Or a new PDF with rendered pages

Requires: pdf2image, pytesseract (for OCR), pillow
"""

import argparse
import base64
import sys
from pathlib import Path
from io import BytesIO

try:
    from pdf2image import convert_from_path
    from PIL import Image
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdf2image", "pillow"])
    from pdf2image import convert_from_path
    from PIL import Image

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("Note: pytesseract not installed - OCR disabled. Install with: pip install pytesseract")

try:
    import fitz  # PyMuPDF for text extraction
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


def extract_text_from_pdf(pdf_path: str) -> dict[int, str]:
    """Extract text from PDF using PyMuPDF (preserves formatting better than OCR)."""
    if not HAS_FITZ:
        return {}
    
    page_texts = {}
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_texts[page_num] = page.get_text()
        doc.close()
    except Exception as e:
        print(f"Warning: Could not extract text with PyMuPDF: {e}")
    
    return page_texts


def convert_to_html(pdf_path: str, output_path: str, dpi: int = 150, use_ocr: bool = False):
    """
    Convert PDF to HTML with embedded images.
    Each page becomes an image with optional OCR text.
    """
    print(f"Converting {pdf_path} to HTML...")
    print(f"  DPI: {dpi}")
    print(f"  OCR: {use_ocr and HAS_OCR}")
    
    # Extract text first (faster and more accurate than OCR)
    page_texts = extract_text_from_pdf(pdf_path)
    
    # Convert PDF pages to images
    print("  Rendering pages...")
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
    except Exception as e:
        print(f"Error converting PDF: {e}")
        print("Make sure poppler-utils is installed: sudo apt install poppler-utils")
        sys.exit(1)
    
    print(f"  {len(images)} pages rendered")
    
    # Build HTML
    html_parts = [
        '<!DOCTYPE html>',
        '<html>',
        '<head>',
        f'<title>{Path(pdf_path).stem}</title>',
        '<meta charset="utf-8">',
        '<style>',
        '  body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }',
        '  .page { margin-bottom: 40px; border-bottom: 2px solid #ccc; padding-bottom: 20px; }',
        '  .page-num { color: #666; font-size: 14px; margin-bottom: 10px; }',
        '  .page-image { max-width: 100%; height: auto; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }',
        '  .page-text { margin-top: 15px; white-space: pre-wrap; font-size: 12px; color: #333; ',
        '               background: #f9f9f9; padding: 15px; border-radius: 4px; }',
        '</style>',
        '</head>',
        '<body>',
        f'<h1>{Path(pdf_path).stem}</h1>',
    ]
    
    for i, img in enumerate(images):
        print(f"  Processing page {i+1}/{len(images)}...", end='\r')
        
        # Convert image to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Get text for this page
        text = page_texts.get(i, '')
        
        # If no extracted text and OCR is enabled, try OCR
        if not text.strip() and use_ocr and HAS_OCR:
            try:
                text = pytesseract.image_to_string(img)
            except Exception as e:
                print(f"\n  Warning: OCR failed on page {i+1}: {e}")
                text = ''
        
        html_parts.extend([
            f'<div class="page" id="page-{i+1}">',
            f'  <div class="page-num">Page {i+1}</div>',
            f'  <img class="page-image" src="data:image/png;base64,{img_base64}" alt="Page {i+1}">',
        ])
        
        if text.strip():
            # Escape HTML in text
            text_escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html_parts.append(f'  <div class="page-text">{text_escaped}</div>')
        
        html_parts.append('</div>')
    
    html_parts.extend([
        '</body>',
        '</html>',
    ])
    
    print(f"\n  Writing {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))
    
    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"  Done! Output: {output_path} ({size_mb:.1f} MB)")


def convert_to_pdf(pdf_path: str, output_path: str, dpi: int = 150):
    """
    Convert PDF to a new clean PDF by rendering pages as images.
    This creates a larger file but bypasses corrupted metadata.
    """
    print(f"Converting {pdf_path} to clean PDF...")
    print(f"  DPI: {dpi}")
    
    # Convert PDF pages to images
    print("  Rendering pages...")
    try:
        images = convert_from_path(pdf_path, dpi=dpi)
    except Exception as e:
        print(f"Error converting PDF: {e}")
        print("Make sure poppler-utils is installed: sudo apt install poppler-utils")
        sys.exit(1)
    
    print(f"  {len(images)} pages rendered")
    
    # Convert to RGB if necessary and save as PDF
    print("  Creating PDF...")
    rgb_images = []
    for img in images:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        rgb_images.append(img)
    
    # Save as PDF
    rgb_images[0].save(
        output_path,
        save_all=True,
        append_images=rgb_images[1:],
        resolution=dpi,
        quality=85
    )
    
    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    print(f"  Done! Output: {output_path} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(
        description='Convert PDF to clean format (bypasses corrupted images)'
    )
    parser.add_argument('input', help='Input PDF file')
    parser.add_argument('-o', '--output', help='Output file (default: input_clean.html or .pdf)')
    parser.add_argument('-f', '--format', choices=['html', 'pdf'], default='html',
                        help='Output format (default: html)')
    parser.add_argument('--dpi', type=int, default=150,
                        help='Resolution for rendering (default: 150, use 200+ for better quality)')
    parser.add_argument('--ocr', action='store_true',
                        help='Use OCR for text extraction (slower, use if PDF has no embedded text)')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        suffix = '.html' if args.format == 'html' else '_clean.pdf'
        output_path = str(input_path.with_suffix('')) + suffix
    
    if args.format == 'html':
        convert_to_html(str(input_path), output_path, dpi=args.dpi, use_ocr=args.ocr)
    else:
        convert_to_pdf(str(input_path), output_path, dpi=args.dpi)


if __name__ == '__main__':
    main()
