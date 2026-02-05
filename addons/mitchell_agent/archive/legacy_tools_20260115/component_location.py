"""
Component Location Tool - Find electrical component locations.

Updated 2026-01-09: Initial implementation.
Access: Quick Access Panel > Electrical Component Locations (#electricalComponentLocationAccess)

Structure:
- Modal with top-level category links
- Categories lead to tree views with li.usercontrol nodes
- Leaf nodes (.leaf) are clickable for content
- Branch nodes (.branch) can be expanded
"""
import asyncio
import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .base import MitchellTool, ToolResult, Vehicle, random_delay

# Set up logging
logger = logging.getLogger("component_location_tool")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler("/tmp/component_location_tool.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)


@dataclass
class ComponentLocation:
    """Component location information."""
    code: str = ""
    name: str = ""
    location: str = ""
    view: str = ""  # Which diagram/view it's in
    category: str = ""  # Fuse block, ground, etc.
    details: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "code": self.code,
            "name": self.name,
            "location": self.location,
        }
        if self.view:
            result["view"] = self.view
        if self.category:
            result["category"] = self.category
        if self.details:
            result["details"] = self.details
        return result


# Map search terms to category hints
CATEGORY_HINTS = {
    "fuse": ["FUSE", "ELECTRICAL CENTER", "X50", "X51"],
    "relay": ["RELAY", "FUSE", "ELECTRICAL CENTER"],
    "ground": ["GROUND", "G100", "G200"],
    "radio": ["INSTRUMENT PANEL", "CENTER CONSOLE", "RADIO"],
    "door": ["DOOR"],
    "engine": ["ENGINE COMPARTMENT", "POWERTRAIN", "FRONT OF VEHICLE"],
    "battery": ["BATTERY", "UNDERHOOD"],
    "sensor": ["ENGINE", "POWERTRAIN"],
    "module": ["INSTRUMENT PANEL", "ENGINE", "POWERTRAIN"],
    "ecm": ["ENGINE", "POWERTRAIN"],
    "bcm": ["BODY", "INSTRUMENT PANEL"],
    "transmission": ["POWERTRAIN", "TRANSMISSION"],
    "abs": ["BRAKE", "WHEEL"],
    "airbag": ["PASSENGER", "DRIVER", "SEAT"],
    "light": ["HEADLIGHT", "LIGHT", "FRONT", "REAR"],
    "headlight": ["FRONT OF VEHICLE", "HEADLIGHT"],
    "taillight": ["REAR", "LUGGAGE", "TAILLIGHT"],
    "fuel": ["FUEL TANK", "UNDERBODY", "POWERTRAIN"],
    "pump": ["FUEL TANK", "ENGINE"],
}


class ComponentLocationTool(MitchellTool):
    """
    Finds electrical component locations.
    
    Access: Quick Access Panel > Electrical Component Locations (#electricalComponentLocationAccess)
    
    Supports:
    - Fuse/relay lookup by number or description
    - Component location by name or code  
    - Ground point lookup
    - General electrical component search
    """
    
    name = "get_component_location"
    description = "Find electrical component locations, fuse boxes, grounds, and connectors"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        component: Optional[str] = None,
        query: Optional[str] = None,
        location_type: Optional[str] = None,  # "fuse", "ground", "connector", etc.
        **kwargs
    ) -> ToolResult:
        """
        Get component location information.
        
        Args:
            vehicle: Vehicle specification
            component: Component to find (e.g., "F15 fuse", "radio", "G100")
            query: Alternative query string
            location_type: Type filter (fuse, ground, connector, module)
            **kwargs: Additional options
            
        Returns:
            ToolResult with component location information
        """
        search_term = component or query
        if not search_term:
            return ToolResult(
                success=False,
                error="Please specify a component to locate (e.g., 'radio', 'F15 fuse', 'G100 ground')"
            )
        
        logger.info(f"Component location search: {search_term}, type: {location_type}")
        
        try:
            # Open Component Locations via quick access
            await self._open_component_locations()
            
            # Determine which category to search based on query
            category = self._determine_category(search_term, location_type)
            logger.info(f"Searching category: {category}")
            
            # Navigate to appropriate category and search
            result = await self._search_for_component(search_term, category)
            
            if result:
                # Extract images from result dict to put at ToolResult level
                images = None
                if isinstance(result, dict) and 'images' in result:
                    images = result.pop('images')
                
                return ToolResult(
                    success=True,
                    data=result.to_dict() if isinstance(result, ComponentLocation) else result,
                    images=images
                )
            else:
                # Try master component list as fallback
                logger.info("Trying Master Electrical Component List fallback")
                result = await self._search_master_list(search_term)
                
                if result:
                    # Extract images from result dict to put at ToolResult level
                    images = None
                    if isinstance(result, dict) and 'images' in result:
                        images = result.pop('images')
                    
                    return ToolResult(
                        success=True,
                        data=result,
                        images=images
                    )
                
                return ToolResult(
                    success=False,
                    error=f"Component '{search_term}' not found in electrical component locations"
                )
                
        except Exception as e:
            logger.exception(f"Error in component location: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to get component location: {str(e)}"
            )
        finally:
            await self._close_modal()
    
    async def _open_component_locations(self) -> None:
        """Open the Component Locations modal via quick access."""
        logger.info("Opening Electrical Component Locations")
        
        # Click the quick access button
        await self.browser.click("#electricalComponentLocationAccess")
        await random_delay(1500, 2000)
        
        # Wait for modal
        await self.browser.wait_for_selector(".modalDialogView", timeout=10000)
        logger.info("Modal opened")
    
    def _determine_category(self, search_term: str, location_type: Optional[str]) -> str:
        """Determine which category to search based on the query."""
        term_lower = search_term.lower()
        
        # Check for fuse pattern (F15, F1, etc.)
        if re.match(r'^f\d+', term_lower) or 'fuse' in term_lower:
            return "fuse"
        
        # Check for ground pattern (G100, G200, etc.)
        if re.match(r'^g\d+', term_lower) or 'ground' in term_lower:
            return "ground"
        
        # Check for relay
        if 'relay' in term_lower:
            return "relay"
        
        # Check explicit location type
        if location_type:
            return location_type.lower()
        
        # Default to master list for general searches
        return "master"
    
    async def _search_for_component(self, search_term: str, category: str) -> Optional[Any]:
        """Search for component in the appropriate category."""
        
        if category in ["fuse", "relay"]:
            return await self._search_fuse_blocks(search_term)
        elif category == "ground":
            return await self._search_grounds(search_term)
        else:
            return await self._search_master_list(search_term)
    
    def _wants_diagram(self, search_term: str) -> bool:
        """Check if user wants an actual diagram/image."""
        term_lower = search_term.lower()
        diagram_keywords = ['diagram', 'image', 'picture', 'photo', 'view', 'layout', 'box']
        return any(kw in term_lower for kw in diagram_keywords)
    
    async def _search_fuse_blocks(self, search_term: str) -> Optional[Dict]:
        """Search fuse block views for a fuse or relay."""
        logger.info(f"Searching fuse blocks for: {search_term}")
        
        # Check if user wants the actual diagram image
        wants_diagram = self._wants_diagram(search_term)
        logger.info(f"User wants diagram: {wants_diagram}")
        
        # Extract fuse number if present (F12 -> 12)
        fuse_match = re.match(r'^f(\d+)', search_term.lower())
        fuse_number = fuse_match.group(1) if fuse_match else None
        logger.info(f"Fuse number extracted: {fuse_number}")
        
        # Click on Electrical Center Identification Views category
        click_result = await self.browser.evaluate("""
            () => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                // Look for the category link
                const links = modal.querySelectorAll('a');
                for (const link of links) {
                    const text = link.textContent.toUpperCase();
                    if (text.includes('ELECTRICAL CENTER') || text.includes('IDENTIFICATION')) {
                        link.click();
                        return { clicked: link.textContent.trim() };
                    }
                }
                return { error: 'Fuse category not found' };
            }
        """)
        
        logger.info(f"Category click result: {click_result}")
        
        if click_result.get('error'):
            return None
        
        await random_delay(1500, 2000)
        
        # Expand all tree nodes to see all fuse blocks
        await self._expand_all_tree_nodes()
        
        # Get all fuse block label views (the ones with fuse tables)
        fuse_blocks = await self.browser.evaluate("""
            () => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return [];
                
                const items = modal.querySelectorAll('li.usercontrol.leaf a');
                const blocks = [];
                
                for (const link of items) {
                    const text = link.textContent?.trim() || '';
                    // Look for "Label" views which contain the fuse tables
                    if (text.includes('Label') || text.includes('Relay')) {
                        blocks.push(text);
                    }
                }
                return blocks;
            }
        """)
        
        logger.info(f"Found fuse blocks with labels: {fuse_blocks}")
        
        # If user wants the diagram, extract the visual fuse block image
        if wants_diagram:
            logger.info("User wants diagram - extracting fuse block image")
            diagram_result = await self._extract_fuse_block_diagram(fuse_blocks)
            if diagram_result:
                return diagram_result
        
        # If searching for specific fuse number, search each block's table
        if fuse_number:
            for block_name in fuse_blocks[:5]:  # Check up to 5 blocks
                logger.info(f"Searching fuse block: {block_name}")
                content = await self._click_and_extract_fuse_content(block_name, fuse_number)
                if content and content.get('found_fuse'):
                    return content
            
            # Fuse not found in any block
            return {
                "error": f"Fuse F{fuse_number} not found",
                "searched_blocks": fuse_blocks[:5],
                "note": "Try a different fuse number or search 'fuse' to see all blocks"
            }
        
        # No specific fuse - just click first label view
        if fuse_blocks:
            content = await self._click_and_extract_content(fuse_blocks[0])
            if content:
                content['available_blocks'] = fuse_blocks
                return content
        
        return None
    
    async def _extract_fuse_block_diagram(self, fuse_blocks: List[str]) -> Optional[Dict]:
        """Extract the actual fuse block diagram image.
        
        Navigates to the diagram view and extracts the SVG/image.
        """
        logger.info("Extracting fuse block diagram")
        
        # Look for diagram views (not just label/table views)
        diagram_views = await self.browser.evaluate("""
            () => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return [];
                
                const items = modal.querySelectorAll('li.usercontrol a');
                const views = [];
                
                for (const link of items) {
                    const text = link.textContent?.trim() || '';
                    // Look for actual diagram views (X50A, X51A blocks, etc.)
                    // Prefer views WITHOUT "Label" which are the actual component diagrams
                    if (text.includes('X50') || text.includes('X51') || text.includes('Fuse Block')) {
                        // Prioritize non-label views
                        const isLabel = text.includes('Label');
                        views.push({ text: text, isLabel: isLabel });
                    }
                }
                
                // Sort so non-label views come first
                views.sort((a, b) => a.isLabel - b.isLabel);
                return views.map(v => v.text);
            }
        """)
        
        logger.info(f"Found diagram views: {diagram_views}")
        
        # If we have X50A or X51A without "Label", try those first (they have the actual diagrams)
        # Otherwise fall back to label views and try to screenshot the content area
        
        for view_name in diagram_views[:3]:
            logger.info(f"Trying to extract diagram from: {view_name}")
            
            # Click on the view
            clicked = await self.browser.evaluate("""
                (viewName) => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return false;
                    
                    const links = modal.querySelectorAll('li.usercontrol a');
                    for (const link of links) {
                        if (link.textContent?.trim() === viewName) {
                            link.click();
                            return true;
                        }
                    }
                    return false;
                }
            """, view_name)
            
            if not clicked:
                continue
            
            await random_delay(2000, 2500)  # Wait for content to load
            
            # Try to extract SVG or take screenshot of the content area
            images = await self._extract_fuse_diagram_images()
            
            if images:
                logger.info(f"Extracted {len(images)} diagram images from {view_name}")
                return {
                    "view": view_name,
                    "diagram_type": "fuse_block",
                    "message": f"Fuse block diagram from {view_name}",
                    "images": images
                }
        
        # Fallback: screenshot the entire content area
        logger.info("Fallback: taking screenshot of content area")
        screenshot_image = await self._screenshot_content_area()
        if screenshot_image:
            return {
                "view": diagram_views[0] if diagram_views else "Fuse Block",
                "diagram_type": "fuse_block",
                "message": "Fuse block diagram (screenshot)",
                "images": [screenshot_image]
            }
        
        return None
    
    async def _extract_fuse_diagram_images(self) -> List[Dict[str, str]]:
        """Extract fuse diagram images from the current view.
        
        Tries multiple methods: SVG objects, img elements, or content screenshot.
        """
        import base64
        images = []
        
        # First try to find SVG objects (like wiring diagrams)
        svg_data = await self.browser.evaluate("""
            () => {
                const results = [];
                const serializer = new XMLSerializer();
                
                // Look for SVG objects in content area
                const svgObjects = document.querySelectorAll('object.clsArticleSvg, object[data*=".svg"], .clsArticleImage object');
                
                for (let i = 0; i < svgObjects.length; i++) {
                    const obj = svgObjects[i];
                    try {
                        const svgDoc = obj.contentDocument;
                        if (svgDoc) {
                            const svgEl = svgDoc.querySelector('svg');
                            if (svgEl) {
                                const clone = svgEl.cloneNode(true);
                                const svgString = serializer.serializeToString(clone);
                                results.push({
                                    name: `Fuse Block Diagram ${i + 1}`,
                                    svg: svgString,
                                    type: 'svg'
                                });
                            }
                        }
                    } catch (e) {
                        console.error('Error extracting SVG:', e);
                    }
                }
                
                return results;
            }
        """)
        
        # Convert SVGs to PNG
        if svg_data:
            try:
                import cairosvg
                for item in svg_data:
                    if item.get('svg'):
                        png_bytes = cairosvg.svg2png(
                            bytestring=item['svg'].encode('utf-8'),
                            output_width=1200
                        )
                        b64_data = base64.b64encode(png_bytes).decode('utf-8')
                        images.append({
                            "name": item.get('name', 'Fuse Block Diagram'),
                            "base64": b64_data,
                            "mime_type": "image/png"
                        })
                        logger.info(f"Converted SVG to PNG: {item.get('name')}")
            except ImportError:
                logger.warning("cairosvg not available for SVG conversion")
            except Exception as e:
                logger.error(f"Error converting SVG: {e}")
        
        # If no SVGs, try to find img elements with actual diagrams
        if not images:
            img_data = await self.browser.evaluate("""
                () => {
                    const results = [];
                    // Look for images in the content area (not tracking pixels)
                    const imgs = document.querySelectorAll('.clsArticleImage img, .modalDialogView img, #contentArea img');
                    
                    for (const img of imgs) {
                        // Skip tiny images (tracking pixels, icons)
                        if (img.naturalWidth > 100 && img.naturalHeight > 100) {
                            results.push({
                                src: img.src,
                                alt: img.alt || 'Diagram',
                                width: img.naturalWidth,
                                height: img.naturalHeight
                            });
                        }
                    }
                    return results;
                }
            """)
            
            # Take screenshots of large images
            for img_info in img_data[:3]:
                try:
                    img_el = await self.browser.query_selector(f'img[src="{img_info["src"]}"]')
                    if img_el:
                        screenshot_bytes = await img_el.screenshot()
                        b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
                        images.append({
                            "name": img_info.get('alt', 'Fuse Block Diagram'),
                            "base64": b64_data,
                            "mime_type": "image/png"
                        })
                        logger.info(f"Screenshot of img element: {img_info.get('alt')}")
                except Exception as e:
                    logger.error(f"Error screenshotting image: {e}")
        
        return images
    
    async def _screenshot_content_area(self) -> Optional[Dict[str, str]]:
        """Take a screenshot of the main content area as fallback."""
        import base64
        
        try:
            # Find the main content/article area
            content_el = await self.browser.query_selector(
                '.clsArticle, .modalDialogView .content, #contentArea, .articleContent'
            )
            
            if content_el:
                screenshot_bytes = await content_el.screenshot()
                b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
                logger.info("Took screenshot of content area")
                return {
                    "name": "Fuse Block Content",
                    "base64": b64_data,
                    "mime_type": "image/png"
                }
        except Exception as e:
            logger.error(f"Error screenshotting content area: {e}")
        
        return None

    async def _expand_all_tree_nodes(self) -> None:
        """Expand all collapsed tree nodes."""
        logger.info("Expanding all tree nodes")
        
        for _ in range(5):  # Try multiple times to expand nested nodes
            expanded = await self.browser.evaluate("""
                () => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return 0;
                    
                    // Find collapsed branch nodes and expand them
                    const collapsed = modal.querySelectorAll('li.usercontrol.node.branch:not(.open)');
                    let count = 0;
                    
                    for (const node of collapsed) {
                        const expander = node.querySelector('.expander, .toggle, > a');
                        if (expander) {
                            expander.click();
                            count++;
                        }
                    }
                    return count;
                }
            """)
            
            logger.info(f"Expanded {expanded} nodes")
            
            if expanded == 0:
                break
                
            await random_delay(500, 700)
    
    async def _click_and_extract_fuse_content(self, block_name: str, fuse_number: str) -> Optional[Dict]:
        """Click a fuse block and search its table for a specific fuse."""
        
        # Click the fuse block
        click_result = await self.browser.evaluate("""
            (blockName) => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                const items = modal.querySelectorAll('li.usercontrol.leaf a');
                for (const link of items) {
                    if (link.textContent?.trim() === blockName) {
                        link.click();
                        return { clicked: true };
                    }
                }
                return { error: 'Block not found' };
            }
        """, block_name)
        
        if click_result.get('error'):
            return None
        
        await random_delay(1500, 2000)
        
        # Search the table for the fuse number
        result = await self.browser.evaluate("""
            (fuseNum) => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                const tables = modal.querySelectorAll('table');
                
                for (const table of tables) {
                    const headers = [...table.querySelectorAll('th, thead td')].map(h => h.textContent?.trim());
                    const rows = table.querySelectorAll('tbody tr');
                    
                    for (const row of rows) {
                        const cells = [...row.querySelectorAll('td')];
                        const rowText = row.textContent || '';
                        
                        // Look for fuse number in row (F12, F12UA, etc.)
                        const fusePattern = new RegExp('\\\\bF' + fuseNum + '\\\\b|\\\\bF' + fuseNum + '[A-Z]', 'i');
                        if (fusePattern.test(rowText)) {
                            return {
                                found_fuse: true,
                                fuse_number: 'F' + fuseNum,
                                row_data: cells.map(c => c.textContent?.trim()),
                                headers: headers
                            };
                        }
                    }
                }
                
                return { found_fuse: false };
            }
        """, fuse_number)
        
        logger.info(f"Fuse search result in {block_name}: {result}")
        
        if result.get('found_fuse'):
            result['fuse_block'] = block_name
            # Extract images from the fuse block view
            images = await self.extract_images_from_modal()
            if images:
                result['images'] = images
                logger.info(f"Captured {len(images)} images from fuse block")
            return result
        
        return result
    
    async def _search_grounds(self, search_term: str) -> Optional[Dict]:
        """Search ground views for a ground point."""
        logger.info(f"Searching grounds for: {search_term}")
        
        # Extract ground number if present (G100 -> 100)
        ground_match = re.match(r'^g(\d+)', search_term.lower())
        ground_number = ground_match.group(1) if ground_match else None
        logger.info(f"Ground number extracted: {ground_number}")
        
        # Click on Ground Views category
        click_result = await self.browser.evaluate("""
            () => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                const links = modal.querySelectorAll('a');
                for (const link of links) {
                    const text = link.textContent.toUpperCase();
                    if (text.includes('GROUND')) {
                        link.click();
                        return { clicked: link.textContent.trim() };
                    }
                }
                return { error: 'Ground category not found' };
            }
        """)
        
        logger.info(f"Ground category click result: {click_result}")
        
        if click_result.get('error'):
            return None
        
        await random_delay(1500, 2000)
        
        # Expand all tree nodes to see all grounds
        await self._expand_all_tree_nodes()
        
        # Get all ground view items
        ground_views = await self.browser.evaluate("""
            () => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return [];
                
                const items = modal.querySelectorAll('li.usercontrol.leaf a');
                const views = [];
                
                for (const link of items) {
                    const text = link.textContent?.trim() || '';
                    views.push(text);
                }
                return views;
            }
        """)
        
        logger.info(f"Found ground views: {ground_views}")
        
        # If searching for specific ground, search each view's content
        if ground_number:
            for view_name in ground_views[:10]:  # Check up to 10 views
                logger.info(f"Searching ground view: {view_name}")
                content = await self._click_and_extract_ground_content(view_name, ground_number)
                if content and content.get('found_ground'):
                    return content
            
            # Ground not found - return available views
            return {
                "error": f"Ground G{ground_number} not found",
                "searched_views": ground_views[:10],
                "note": "Try a different ground number or search 'ground' to see all views"
            }
        
        # No specific ground - click first view and return content
        if ground_views:
            content = await self._click_and_extract_content(ground_views[0])
            if content:
                content['available_views'] = ground_views
                return content
        
        return None
    
    async def _click_and_extract_ground_content(self, view_name: str, ground_number: str) -> Optional[Dict]:
        """Click a ground view and search for a specific ground point."""
        
        # Click the ground view
        click_result = await self.browser.evaluate("""
            (viewName) => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                const items = modal.querySelectorAll('li.usercontrol.leaf a');
                for (const link of items) {
                    if (link.textContent?.trim() === viewName) {
                        link.click();
                        return { clicked: true };
                    }
                }
                return { error: 'View not found' };
            }
        """, view_name)
        
        if click_result.get('error'):
            return None
        
        await random_delay(1500, 2000)
        
        # Search for the ground number in tables or text
        result = await self.browser.evaluate("""
            (groundNum) => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                const groundPattern = new RegExp('\\\\bG' + groundNum + '\\\\b', 'i');
                
                // Check tables
                const tables = modal.querySelectorAll('table');
                for (const table of tables) {
                    const headers = [...table.querySelectorAll('th, thead td')].map(h => h.textContent?.trim());
                    const rows = table.querySelectorAll('tbody tr, tr');
                    
                    for (const row of rows) {
                        const rowText = row.textContent || '';
                        if (groundPattern.test(rowText)) {
                            const cells = [...row.querySelectorAll('td')];
                            return {
                                found_ground: true,
                                ground_number: 'G' + groundNum,
                                row_data: cells.map(c => c.textContent?.trim()),
                                headers: headers
                            };
                        }
                    }
                }
                
                // Check text content 
                const content = modal.querySelector('.content, .main')?.textContent || modal.textContent;
                if (groundPattern.test(content)) {
                    // Try to extract the relevant section
                    const lines = content.split('\\n');
                    const relevantLines = lines.filter(l => groundPattern.test(l));
                    return {
                        found_ground: true,
                        ground_number: 'G' + groundNum,
                        text: relevantLines.slice(0, 5)
                    };
                }
                
                return { found_ground: false };
            }
        """, ground_number)
        
        logger.info(f"Ground search result in {view_name}: {result}")
        
        if result.get('found_ground'):
            result['ground_view'] = view_name
            # Extract images from the ground view
            images = await self.extract_images_from_modal()
            if images:
                result['images'] = images
                logger.info(f"Captured {len(images)} images from ground view")
            return result
        
        return result
    
    async def _search_master_list(self, search_term: str) -> Optional[Dict]:
        """Search the Master Electrical Component List."""
        logger.info(f"Searching master list for: {search_term}")
        
        # Click on Master Electrical Component List
        click_result = await self.browser.evaluate("""
            () => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                const links = modal.querySelectorAll('a');
                for (const link of links) {
                    const text = link.textContent.toUpperCase();
                    if (text.includes('MASTER') && text.includes('COMPONENT')) {
                        link.click();
                        return { clicked: link.textContent.trim() };
                    }
                }
                return { error: 'Master list not found' };
            }
        """)
        
        logger.info(f"Master list click result: {click_result}")
        
        if click_result.get('error'):
            return None
        
        # Wait for the table to load (it has 400+ rows, takes time)
        for attempt in range(10):  # Try up to 10 times (5 seconds total)
            await random_delay(500, 600)
            table_check = await self.browser.evaluate("""
                () => {
                    const modal = document.querySelector('.modalDialogView');
                    const table = modal?.querySelector('table');
                    const rows = table?.querySelectorAll('tr')?.length || 0;
                    return { rows: rows };
                }
            """)
            logger.info(f"Table load check {attempt + 1}: {table_check.get('rows', 0)} rows")
            if table_check.get('rows', 0) > 10:
                break
        
        # The master list is a table - search it
        result = await self.browser.evaluate("""
            (searchTerm) => {
                const termLower = searchTerm.toLowerCase();
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                // Look for table rows
                const rows = modal.querySelectorAll('tr');
                const matches = [];
                
                for (const row of rows) {
                    const text = row.textContent.toLowerCase();
                    if (text.includes(termLower)) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            matches.push({
                                code: cells[0]?.textContent?.trim() || '',
                                name: cells[1]?.textContent?.trim() || '',
                                option: cells[2]?.textContent?.trim() || '',
                                location: cells[3]?.textContent?.trim() || '',
                            });
                        }
                    }
                }
                
                return { matches: matches.slice(0, 10) };
            }
        """, search_term)
        
        if result.get('matches') and len(result['matches']) > 0:
            return {
                "components": result['matches'],
                "source": "Master Electrical Component List"
            }
        
        return None
    
    async def _search_tree_for_term(self, search_term: str) -> Optional[Dict]:
        """Search the tree view for matching items."""
        logger.info(f"Searching tree for: {search_term}")
        
        # First expand all tree nodes to see everything
        await self._expand_all_tree_nodes()
        
        # Get all tree items and search for matches
        result = await self.browser.evaluate("""
            (searchTerm) => {
                const termLower = searchTerm.toLowerCase();
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                const items = modal.querySelectorAll('li.usercontrol');
                const matches = [];
                
                for (const item of items) {
                    const text = item.textContent?.trim().toLowerCase() || '';
                    if (text.includes(termLower)) {
                        const link = item.querySelector('a');
                        const isLeaf = item.classList.contains('leaf');
                        matches.push({
                            text: link?.textContent?.trim() || item.textContent?.trim().substring(0, 100),
                            isLeaf: isLeaf,
                            classes: item.className
                        });
                    }
                }
                
                return { 
                    total_items: items.length,
                    matches: matches.slice(0, 10)
                };
            }
        """, search_term)
        
        logger.info(f"Tree search result: {result}")
        
        if not result.get('matches') or len(result['matches']) == 0:
            return None
        
        # If we found a matching leaf, click it to get content
        leaf_match = next((m for m in result['matches'] if m.get('isLeaf')), None)
        
        if leaf_match:
            # Click the leaf to open its content
            content = await self._click_and_extract_content(leaf_match['text'])
            if content:
                return content
        
        # Return the list of matches
        return {
            "matches": [m['text'] for m in result['matches']],
            "note": "Multiple matches found - be more specific or click a result"
        }
    
    async def _click_and_extract_content(self, item_text: str) -> Optional[Dict]:
        """Click a tree item and extract its content."""
        logger.info(f"Clicking item: {item_text}")
        
        # Click the matching item
        click_result = await self.browser.evaluate("""
            (itemText) => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                const items = modal.querySelectorAll('li.usercontrol.leaf a');
                for (const link of items) {
                    if (link.textContent?.trim() === itemText) {
                        link.click();
                        return { clicked: true };
                    }
                }
                return { error: 'Item not found' };
            }
        """, item_text)
        
        if click_result.get('error'):
            return None
        
        await random_delay(1500, 2000)
        
        # Extract content - could be a table or diagram info
        content = await self.browser.evaluate("""
            () => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal' };
                
                // Look for table content
                const tables = modal.querySelectorAll('table');
                const tableData = [];
                
                for (const table of tables) {
                    const headers = [...table.querySelectorAll('th, thead td')].map(h => h.textContent?.trim());
                    const rows = [...table.querySelectorAll('tbody tr')].map(row => {
                        return [...row.querySelectorAll('td')].map(cell => cell.textContent?.trim());
                    });
                    if (rows.length > 0) {
                        tableData.push({ headers, rows: rows.slice(0, 20) });
                    }
                }
                
                // Get any text content
                const textBlocks = [];
                const paragraphs = modal.querySelectorAll('p, .content, .description');
                for (const p of paragraphs) {
                    const text = p.textContent?.trim();
                    if (text && text.length > 10) {
                        textBlocks.push(text.substring(0, 500));
                    }
                }
                
                // Get title/heading
                const heading = modal.querySelector('h1, h2, h3, .title')?.textContent?.trim();
                
                return {
                    heading: heading,
                    tables: tableData.slice(0, 3),
                    text: textBlocks.slice(0, 5)
                };
            }
        """)
        
        logger.info(f"Extracted content: {content}")
        
        # Extract images from the view
        images = await self.extract_images_from_modal()
        
        if content and (content.get('tables') or content.get('text')):
            result = {
                "view": item_text,
                "heading": content.get('heading', ''),
                "tables": content.get('tables', []),
                "text": content.get('text', [])
            }
            if images:
                result['images'] = images
                logger.info(f"Captured {len(images)} images from view")
            return result
        
        result = {"view": item_text, "note": "Content loaded - check diagram"}
        if images:
            result['images'] = images
            logger.info(f"Captured {len(images)} images from view")
        return result
    
    async def _close_modal(self) -> None:
        """Close the modal dialog."""
        try:
            await self.browser.evaluate("""
                () => {
                    const closeBtn = document.querySelector('.modalDialogView .close, .modalDialogView [class*="close"]');
                    if (closeBtn) closeBtn.click();
                }
            """)
            await random_delay(300, 500)
        except Exception as e:
            logger.debug(f"Error closing modal: {e}")
    
    def _format_result(self, result: Any) -> str:
        """Format result for display."""
        if isinstance(result, ComponentLocation):
            lines = []
            if result.code:
                lines.append(f"Code: {result.code}")
            if result.name:
                lines.append(f"Name: {result.name}")
            if result.location:
                lines.append(f"Location: {result.location}")
            if result.view:
                lines.append(f"View: {result.view}")
            if result.category:
                lines.append(f"Category: {result.category}")
            return "\n".join(lines)
        elif isinstance(result, dict):
            if 'components' in result:
                lines = [f"Found {len(result['components'])} component(s):"]
                for comp in result['components'][:5]:
                    lines.append(f"  - {comp.get('code', '')} {comp.get('name', '')}: {comp.get('location', '')}")
                return "\n".join(lines)
            elif 'matches' in result:
                lines = ["Matching items:"]
                for match in result['matches'][:10]:
                    lines.append(f"  - {match}")
                return "\n".join(lines)
            elif 'view' in result:
                return f"View: {result.get('view', '')}\n{result.get('note', '')}"
        
        return str(result)
