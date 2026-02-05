#!/usr/bin/env python3
"""
PDF Image Recreator - Extract, Describe, and Regenerate Images

This script:
1. Extracts images from a PDF
2. Describes each image using a vision model (Gemini)
3. Regenerates new images using Stable Diffusion
4. Creates a markdown document with text + new images for RAG

This avoids copyright issues by creating new derivative works.
"""

import os
import sys
import json
import base64
import asyncio
import argparse
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF
import httpx
from PIL import Image
import io


# Configuration
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
SD_API_URL = "http://localhost:7860"  # Stable Diffusion WebUI API


async def describe_image_with_gemini(image_bytes: bytes, context: str = "", retries: int = 3) -> str:
    """Use Gemini to describe an image with retry logic for rate limits."""
    if not GEMINI_API_KEY:
        raise ValueError("GOOGLE_API_KEY not set")
    
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = f"""You are describing an educational diagram from an automotive electronics textbook.
Describe this image in detail, focusing on:
- What type of diagram it is (circuit schematic, wiring diagram, component illustration, graph, etc.)
- All components shown and their labels
- Connections and relationships between components
- Any text, values, or measurements shown
- The educational purpose of this diagram

Context from surrounding text: {context if context else 'Not available'}

Provide a detailed technical description that could be used to recreate a similar educational diagram."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64_image
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }
    
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    params={"key": GEMINI_API_KEY},
                    json=payload
                )
                
                if response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = (2 ** attempt) * 5  # 5, 10, 20 seconds
                    print(f"    Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                result = response.json()
                
            return result["candidates"][0]["content"]["parts"][0]["text"]
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                wait_time = (2 ** attempt) * 5
                print(f"    Rate limited, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            raise
        except (KeyError, IndexError):
            return "Failed to describe image"
    
    return "Failed after retries (rate limited)"


async def generate_image_with_sd(description: str, output_path: Path) -> bool:
    """Generate a new image using Stable Diffusion based on description."""
    
    # Create a prompt for technical diagram generation
    prompt = f"""technical diagram, educational illustration, clean line art, 
automotive electronics, schematic style, white background, labeled components,
professional textbook quality, {description[:500]}"""
    
    negative_prompt = "photo, realistic, blurry, low quality, watermark, text overlay, copyright"
    
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": 30,
        "width": 768,
        "height": 512,
        "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{SD_API_URL}/sdapi/v1/txt2img",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
        if result.get("images"):
            image_data = base64.b64decode(result["images"][0])
            with open(output_path, "wb") as f:
                f.write(image_data)
            return True
    except Exception as e:
        print(f"  Warning: SD generation failed: {e}")
    
    return False


def extract_images_from_pdf(pdf_path: Path, output_dir: Path, min_size: int = 100):
    """Extract images from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    images = []
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images()
        
        # Also get page text for context
        page_text = page.get_text()[:500]  # First 500 chars for context
        
        for img_idx, img in enumerate(image_list):
            xref = img[0]
            
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Check image size
                pil_image = Image.open(io.BytesIO(image_bytes))
                width, height = pil_image.size
                
                # Skip tiny images (likely icons or bullets)
                if width < min_size or height < min_size:
                    continue
                
                # Skip mostly empty images
                if pil_image.mode in ('RGBA', 'LA'):
                    # Check if mostly transparent
                    if pil_image.split()[-1].getextrema()[1] < 10:
                        continue
                
                image_filename = f"page{page_num+1:04d}_img{img_idx+1:02d}.{image_ext}"
                image_path = output_dir / image_filename
                
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                
                images.append({
                    "page": page_num + 1,
                    "index": img_idx + 1,
                    "path": image_path,
                    "width": width,
                    "height": height,
                    "context": page_text,
                    "ext": image_ext
                })
                
                print(f"  Extracted: {image_filename} ({width}x{height})")
                
            except Exception as e:
                print(f"  Warning: Failed to extract image {img_idx} from page {page_num+1}: {e}")
    
    doc.close()
    return images


async def process_images(images: list, output_dir: Path, describe_only: bool = False):
    """Process extracted images - describe and optionally regenerate."""
    
    descriptions_dir = output_dir / "descriptions"
    regenerated_dir = output_dir / "regenerated"
    descriptions_dir.mkdir(exist_ok=True)
    regenerated_dir.mkdir(exist_ok=True)
    
    results = []
    
    for i, img_info in enumerate(images):
        print(f"\nProcessing image {i+1}/{len(images)}: {img_info['path'].name}")
        
        # Read original image
        with open(img_info["path"], "rb") as f:
            image_bytes = f.read()
        
        # Convert to PNG if needed for Gemini
        if img_info["ext"].lower() not in ("png", "jpg", "jpeg", "gif", "webp"):
            pil_image = Image.open(io.BytesIO(image_bytes))
            png_buffer = io.BytesIO()
            pil_image.save(png_buffer, format="PNG")
            image_bytes = png_buffer.getvalue()
        
        # Describe with Gemini
        print("  Describing with Gemini...")
        try:
            description = await describe_image_with_gemini(image_bytes, img_info["context"])
        except Exception as e:
            print(f"  Error describing: {e}")
            description = "Failed to describe image"
        
        # Save description
        desc_path = descriptions_dir / f"{img_info['path'].stem}.md"
        with open(desc_path, "w") as f:
            f.write(f"# Image: {img_info['path'].name}\n\n")
            f.write(f"**Page:** {img_info['page']}\n")
            f.write(f"**Size:** {img_info['width']}x{img_info['height']}\n\n")
            f.write("## Description\n\n")
            f.write(description)
        
        print(f"  Description saved: {desc_path.name}")
        
        # Regenerate with Stable Diffusion
        regenerated_path = None
        if not describe_only:
            print("  Regenerating with Stable Diffusion...")
            regen_path = regenerated_dir / f"{img_info['path'].stem}_regen.png"
            if await generate_image_with_sd(description, regen_path):
                regenerated_path = regen_path
                print(f"  Regenerated: {regen_path.name}")
        
        results.append({
            "original": str(img_info["path"]),
            "page": img_info["page"],
            "description": description,
            "description_file": str(desc_path),
            "regenerated": str(regenerated_path) if regenerated_path else None
        })
        
        # Delay to avoid rate limiting (Gemini free tier is ~15 RPM)
        await asyncio.sleep(4.0)
    
    return results


def create_combined_document(pdf_path: Path, results: list, output_dir: Path):
    """Create a combined markdown document with text and image descriptions."""
    
    doc = fitz.open(pdf_path)
    output_path = output_dir / "combined_content.md"
    
    with open(output_path, "w") as f:
        f.write(f"# {pdf_path.stem}\n\n")
        f.write("*Content extracted and images recreated to avoid copyright infringement*\n\n")
        f.write("---\n\n")
        
        # Create lookup of images by page
        images_by_page = {}
        for r in results:
            page = r["page"]
            if page not in images_by_page:
                images_by_page[page] = []
            images_by_page[page].append(r)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            if text.strip():
                f.write(f"## Page {page_num + 1}\n\n")
                f.write(text)
                f.write("\n\n")
                
                # Add image descriptions for this page
                if page_num + 1 in images_by_page:
                    for img in images_by_page[page_num + 1]:
                        f.write("### [Figure]\n\n")
                        f.write(img["description"])
                        if img["regenerated"]:
                            rel_path = Path(img["regenerated"]).name
                            f.write(f"\n\n![Recreated diagram](regenerated/{rel_path})\n")
                        f.write("\n\n")
                
                f.write("---\n\n")
    
    doc.close()
    print(f"\nCombined document saved: {output_path}")
    return output_path


async def main():
    parser = argparse.ArgumentParser(description="Extract, describe, and recreate PDF images")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--output-dir", "-o", help="Output directory", default=None)
    parser.add_argument("--describe-only", "-d", action="store_true", 
                        help="Only describe images, don't regenerate")
    parser.add_argument("--min-size", type=int, default=100,
                        help="Minimum image dimension to extract (default: 100)")
    parser.add_argument("--max-images", type=int, default=None,
                        help="Maximum number of images to process")
    
    args = parser.parse_args()
    
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)
    
    output_dir = Path(args.output_dir) if args.output_dir else Path(f"./output_{pdf_path.stem}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    originals_dir = output_dir / "originals"
    
    print(f"Processing: {pdf_path}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Step 1: Extract images
    print("=" * 50)
    print("Step 1: Extracting images from PDF...")
    print("=" * 50)
    images = extract_images_from_pdf(pdf_path, originals_dir, args.min_size)
    print(f"\nExtracted {len(images)} images")
    
    if not images:
        print("No images found to process")
        sys.exit(0)
    
    # Limit if requested
    if args.max_images:
        images = images[:args.max_images]
        print(f"Processing first {len(images)} images")
    
    # Step 2: Describe and regenerate
    print()
    print("=" * 50)
    print("Step 2: Describing and regenerating images...")
    print("=" * 50)
    results = await process_images(images, output_dir, args.describe_only)
    
    # Step 3: Create combined document
    print()
    print("=" * 50)
    print("Step 3: Creating combined document...")
    print("=" * 50)
    combined_path = create_combined_document(pdf_path, results, output_dir)
    
    # Save results summary
    results_path = output_dir / "processing_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print()
    print("=" * 50)
    print("COMPLETE!")
    print("=" * 50)
    print(f"  Original images: {originals_dir}")
    print(f"  Descriptions: {output_dir / 'descriptions'}")
    if not args.describe_only:
        print(f"  Regenerated images: {output_dir / 'regenerated'}")
    print(f"  Combined document: {combined_path}")
    print(f"  Results JSON: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
