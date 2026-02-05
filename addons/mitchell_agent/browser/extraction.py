"""
Data Extraction
===============
Extracts structured data from ShopKeyPro pages.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, List, Any
from pathlib import Path
import uuid

from playwright.async_api import Page

log = logging.getLogger(__name__)


class DataExtractor:
    """
    Extracts structured data from ShopKeyPro pages.
    
    Handles extraction of:
    - Fluid capacities
    - Torque specs
    - TSBs (Technical Service Bulletins)
    - DTC codes
    - Reset procedures
    - Wiring diagrams (SVG)
    - General tables and lists
    
    Usage:
        extractor = DataExtractor(page)
        fluids = await extractor.extract_fluids()
        specs = await extractor.extract_torque_specs()
    """
    
    def __init__(self, page: Page, output_dir: Optional[Path] = None):
        """
        Initialize data extractor.
        
        Args:
            page: Playwright Page instance
            output_dir: Directory for saved images/files
        """
        self.page = page
        self.output_dir = output_dir or Path("/tmp/mitchell_extraction")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def extract_table(
        self,
        table_selector: str = "table",
        include_headers: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Extract data from an HTML table.
        
        Args:
            table_selector: CSS selector for table
            include_headers: Use first row as headers
            
        Returns:
            List of row dicts
        """
        rows = []
        
        try:
            table = self.page.locator(table_selector).first
            
            if not await table.is_visible(timeout=3000):
                return rows
            
            # Get headers
            headers = []
            if include_headers:
                header_cells = await table.locator("thead th, tr:first-child th").all()
                for cell in header_cells:
                    text = await cell.text_content()
                    headers.append(text.strip() if text else f"col_{len(headers)}")
            
            # Get body rows
            body_rows = await table.locator("tbody tr, tr").all()
            start_idx = 1 if include_headers and not headers else 0
            
            for row_loc in body_rows[start_idx:]:
                cells = await row_loc.locator("td").all()
                
                if not cells:
                    continue
                
                row_data = {}
                for i, cell in enumerate(cells):
                    text = await cell.text_content()
                    key = headers[i] if i < len(headers) else f"col_{i}"
                    row_data[key] = text.strip() if text else ""
                
                if any(v for v in row_data.values()):
                    rows.append(row_data)
                    
        except Exception as e:
            log.error(f"Error extracting table: {e}")
        
        return rows
    
    async def extract_key_value_pairs(
        self,
        container_selector: str = ".dataSection",
    ) -> Dict[str, str]:
        """
        Extract key-value pairs from a container.
        
        Handles formats like:
        - "Label: Value"
        - <dt>Label</dt><dd>Value</dd>
        - <span class="label">Label</span><span class="value">Value</span>
        
        Returns:
            Dict of label -> value pairs
        """
        data = {}
        
        try:
            container = self.page.locator(container_selector).first
            
            if not await container.is_visible(timeout=3000):
                return data
            
            # Try dt/dd pairs first
            dt_elements = await container.locator("dt").all()
            if dt_elements:
                for dt in dt_elements:
                    label = await dt.text_content()
                    dd = dt.locator("~ dd").first
                    value = await dd.text_content()
                    
                    if label:
                        data[label.strip().rstrip(":")] = value.strip() if value else ""
            else:
                # Try text parsing with colons
                text = await container.text_content()
                if text:
                    for line in text.split("\n"):
                        if ":" in line:
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                data[parts[0].strip()] = parts[1].strip()
                                
        except Exception as e:
            log.error(f"Error extracting key-value pairs: {e}")
        
        return data
    
    async def extract_list_items(
        self,
        list_selector: str = "ul, ol",
    ) -> List[str]:
        """
        Extract items from a list.
        
        Returns:
            List of item texts
        """
        items = []
        
        try:
            list_loc = self.page.locator(list_selector).first
            
            if await list_loc.is_visible(timeout=3000):
                li_elements = await list_loc.locator("li").all()
                
                for li in li_elements:
                    text = await li.text_content()
                    if text:
                        items.append(text.strip())
                        
        except Exception as e:
            log.error(f"Error extracting list items: {e}")
        
        return items
    
    async def extract_fluids(self) -> Dict[str, Any]:
        """
        Extract fluid capacities data.
        
        Returns:
            Dict with fluid types and capacities
        """
        data = {
            "engine_oil": {},
            "coolant": {},
            "transmission": {},
            "other": {},
        }
        
        try:
            # Common patterns in fluid capacity sections
            sections = await self.page.locator(
                ".fluidSection, .capacitySection, article"
            ).all()
            
            for section in sections:
                text = await section.text_content()
                if not text:
                    continue
                
                text_lower = text.lower()
                
                # Categorize by fluid type
                if "engine oil" in text_lower or "motor oil" in text_lower:
                    data["engine_oil"] = await self._parse_fluid_section(section)
                elif "coolant" in text_lower or "antifreeze" in text_lower:
                    data["coolant"] = await self._parse_fluid_section(section)
                elif "transmission" in text_lower or "transaxle" in text_lower:
                    data["transmission"] = await self._parse_fluid_section(section)
                else:
                    # Extract any key-value pairs
                    pairs = await self._parse_fluid_section(section)
                    data["other"].update(pairs)
                    
        except Exception as e:
            log.error(f"Error extracting fluids: {e}")
        
        return data
    
    async def _parse_fluid_section(self, section_loc) -> Dict[str, str]:
        """Parse a fluid capacity section."""
        data = {}
        
        try:
            # Look for table format first
            rows = await section_loc.locator("tr").all()
            
            if rows:
                for row in rows:
                    cells = await row.locator("td, th").all()
                    if len(cells) >= 2:
                        label = await cells[0].text_content()
                        value = await cells[1].text_content()
                        if label:
                            data[label.strip()] = value.strip() if value else ""
            else:
                # Try text parsing
                text = await section_loc.text_content()
                if text:
                    # Match patterns like "Capacity: 5.7 qts"
                    matches = re.findall(
                        r"([A-Za-z\s]+):\s*([\d.]+\s*(?:qts?|liters?|gal|oz|ml)?)",
                        text,
                        re.IGNORECASE
                    )
                    for label, value in matches:
                        data[label.strip()] = value.strip()
                        
        except Exception as e:
            log.error(f"Error parsing fluid section: {e}")
        
        return data
    
    async def extract_torque_specs(self) -> List[Dict[str, str]]:
        """
        Extract torque specifications.
        
        Returns:
            List of torque spec dicts with component, spec, notes
        """
        specs = []
        
        try:
            # Try table extraction
            specs = await self.extract_table("table")
            
            if not specs:
                # Try list format
                items = await self.extract_list_items()
                for item in items:
                    # Parse "Component - 20 ft-lbs" format
                    parts = re.split(r"\s*[-–]\s*", item, 1)
                    if len(parts) == 2:
                        specs.append({
                            "component": parts[0].strip(),
                            "torque": parts[1].strip(),
                        })
                        
        except Exception as e:
            log.error(f"Error extracting torque specs: {e}")
        
        return specs
    
    async def extract_tsb_list(self) -> List[Dict[str, str]]:
        """
        Extract TSB (Technical Service Bulletin) list.
        
        Returns:
            List of TSB dicts with ref, title, date
        """
        tsbs = []
        
        try:
            # TSBs are typically in a table within modal
            table = self.page.locator(".modalDialogView table").first
            
            if await table.is_visible(timeout=3000):
                rows = await table.locator("tbody tr").all()
                
                for row in rows:
                    cells = await row.locator("td").all()
                    
                    if len(cells) >= 2:
                        tsb = {
                            "ref": await cells[0].text_content() or "",
                            "title": await cells[1].text_content() or "",
                            "date": await cells[2].text_content() if len(cells) > 2 else "",
                        }
                        tsb = {k: v.strip() for k, v in tsb.items()}
                        
                        if tsb["ref"] or tsb["title"]:
                            tsbs.append(tsb)
                            
        except Exception as e:
            log.error(f"Error extracting TSBs: {e}")
        
        return tsbs
    
    async def extract_dtc_info(self, dtc_code: str = "") -> Dict[str, Any]:
        """
        Extract DTC (Diagnostic Trouble Code) information.
        
        Args:
            dtc_code: The specific DTC code
            
        Returns:
            Dict with code, description, causes, diagnostics
        """
        info = {
            "code": dtc_code,
            "description": "",
            "causes": [],
            "diagnostics": [],
        }
        
        try:
            # Get main description
            desc_loc = self.page.locator(".dtcDescription, .codeDescription").first
            if await desc_loc.is_visible(timeout=3000):
                info["description"] = await desc_loc.text_content() or ""
                info["description"] = info["description"].strip()
            
            # Get causes section
            causes_loc = self.page.locator(".causes, .possibleCauses")
            if await causes_loc.is_visible(timeout=2000):
                items = await causes_loc.locator("li").all()
                for item in items:
                    text = await item.text_content()
                    if text:
                        info["causes"].append(text.strip())
            
            # Get diagnostic steps
            diag_loc = self.page.locator(".diagnostics, .testProcedure")
            if await diag_loc.is_visible(timeout=2000):
                items = await diag_loc.locator("li, .step").all()
                for item in items:
                    text = await item.text_content()
                    if text:
                        info["diagnostics"].append(text.strip())
                        
        except Exception as e:
            log.error(f"Error extracting DTC info: {e}")
        
        return info
    
    async def extract_svg_diagram(
        self,
        save_as_png: bool = True,
        min_width: int = 1200,
    ) -> Optional[Dict[str, str]]:
        """
        Extract SVG diagram from page.
        
        Args:
            save_as_png: Convert to PNG
            min_width: Minimum width for scaling
            
        Returns:
            Dict with svg_content, png_path, filename
        """
        result = {}
        
        try:
            # Find SVG object element
            svg_object = self.page.locator("object.clsArticleSvg").first
            
            if not await svg_object.is_visible(timeout=5000):
                log.warning("SVG object not found")
                return None
            
            # Extract SVG content via JavaScript
            svg_content = await svg_object.evaluate("""
                obj => {
                    const doc = obj.contentDocument;
                    if (doc && doc.documentElement) {
                        return doc.documentElement.outerHTML;
                    }
                    return null;
                }
            """)
            
            if not svg_content:
                log.warning("Could not extract SVG content")
                return None
            
            result["svg_content"] = svg_content
            
            # Generate unique filename
            file_id = str(uuid.uuid4())[:8]
            result["filename"] = f"diagram_{file_id}"
            
            # Save SVG
            svg_path = self.output_dir / f"{result['filename']}.svg"
            svg_path.write_text(svg_content)
            result["svg_path"] = str(svg_path)
            
            if save_as_png:
                # Scale and convert to PNG
                png_path = await self._convert_svg_to_png(
                    svg_content,
                    result["filename"],
                    min_width,
                )
                if png_path:
                    result["png_path"] = png_path
                    
        except Exception as e:
            log.error(f"Error extracting SVG diagram: {e}")
        
        return result if result else None
    
    async def _convert_svg_to_png(
        self,
        svg_content: str,
        filename: str,
        min_width: int,
    ) -> Optional[str]:
        """Convert SVG to PNG with scaling."""
        try:
            import cairosvg
            
            # Parse dimensions
            width_match = re.search(r'width="(\d+)"', svg_content)
            height_match = re.search(r'height="(\d+)"', svg_content)
            
            orig_width = int(width_match.group(1)) if width_match else 800
            orig_height = int(height_match.group(1)) if height_match else 600
            
            # Calculate scale factor
            if orig_width < min_width:
                scale = min_width / orig_width
            else:
                scale = 1.0
            
            output_width = int(orig_width * scale)
            output_height = int(orig_height * scale)
            
            # Convert to PNG
            png_path = self.output_dir / f"{filename}.png"
            
            cairosvg.svg2png(
                bytestring=svg_content.encode("utf-8"),
                write_to=str(png_path),
                output_width=output_width,
                output_height=output_height,
            )
            
            log.info(f"Saved PNG: {png_path} ({output_width}x{output_height})")
            return str(png_path)
            
        except ImportError:
            log.warning("cairosvg not installed - PNG conversion unavailable")
        except Exception as e:
            log.error(f"Error converting SVG to PNG: {e}")
        
        return None
    
    async def take_screenshot(
        self,
        selector: Optional[str] = None,
        full_page: bool = False,
    ) -> Optional[str]:
        """
        Take a screenshot.
        
        Args:
            selector: CSS selector for specific element
            full_page: Capture full page
            
        Returns:
            Path to saved screenshot
        """
        try:
            file_id = str(uuid.uuid4())[:8]
            path = self.output_dir / f"screenshot_{file_id}.png"
            
            if selector:
                element = self.page.locator(selector).first
                if await element.is_visible(timeout=3000):
                    await element.screenshot(path=str(path))
                else:
                    return None
            else:
                await self.page.screenshot(path=str(path), full_page=full_page)
            
            log.info(f"Screenshot saved: {path}")
            return str(path)
            
        except Exception as e:
            log.error(f"Error taking screenshot: {e}")
            return None
    
    async def extract_page_text(self) -> str:
        """
        Extract all visible text from page.
        
        Returns:
            Page text content
        """
        try:
            return await self.page.locator("body").text_content() or ""
        except Exception as e:
            log.error(f"Error extracting page text: {e}")
            return ""
    
    async def extract_links(
        self,
        container_selector: str = "body",
    ) -> List[Dict[str, str]]:
        """
        Extract links from a container.
        
        Returns:
            List of dicts with text, href
        """
        links = []
        
        try:
            container = self.page.locator(container_selector)
            link_locs = await container.locator("a").all()
            
            for loc in link_locs:
                text = await loc.text_content()
                href = await loc.get_attribute("href")
                
                if text and text.strip():
                    links.append({
                        "text": text.strip(),
                        "href": href or "",
                    })
                    
        except Exception as e:
            log.error(f"Error extracting links: {e}")
        
        return links
