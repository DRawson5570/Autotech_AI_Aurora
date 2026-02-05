"""
Component Tests Tool - Retrieves component test information and pinouts.

Updated 2026-01-09: Initial implementation with mapped selectors.
Access: Quick Access Panel > Component Tests (#ctmQuickAccess)

Structure:
- Tree with system nodes (li.usercontrol.node.branch)
- Component nodes (li.usercontrol.node.leaf) 
- Detail page has: Module Location, Operation, Pinouts table

Systems: ABS, Body Electrical, Charging System, Engine, HVAC System, Starting System, Transmission
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle, random_delay

# Set up logging
logger = logging.getLogger("component_tests_tool")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler("/tmp/component_tests_tool.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)


class ComponentTestsTool(MitchellTool):
    """
    Retrieves component test information and pinouts.
    
    Access: Quick Access Panel > Component Tests (#ctmQuickAccess)
    
    Supports:
    - Browse by system category (ABS, Body Electrical, etc.)
    - Search for specific component (ABS Module, Wheel Speed Sensors)
    - Get pinout tables and operation descriptions
    """
    
    name = "get_component_tests"
    description = "Get component test information, pinouts, and operation descriptions"
    tier = 1
    
    # Hardcoded config - no longer loaded from JSON
    _ct_config = {
        "semantic_mapping": {},  # Optional: map search terms to component names
        "systems": {},  # Optional: system -> components mapping
    }
    
    def __init__(self, browser_controller=None):
        super().__init__(browser_controller)
    
    def _get_semantic_component(self, search_term: str) -> Optional[str]:
        """Map search term to actual component name using semantic_mapping."""
        mapping = self._ct_config.get("semantic_mapping", {})
        term_lower = search_term.lower()
        
        # Direct match
        if term_lower in mapping:
            return mapping[term_lower]
        
        # Partial match
        for key, value in mapping.items():
            if key in term_lower or term_lower in key:
                return value
        
        return None
    
    def _get_system_for_component(self, component: str) -> Optional[str]:
        """Find which system contains a component."""
        systems = self._ct_config.get("systems", {})
        comp_lower = component.lower()
        
        for system_name, system_data in systems.items():
            components = system_data.get("components", [])
            for comp in components:
                if comp.lower() == comp_lower or comp_lower in comp.lower():
                    return system_name
        
        return None
    
    async def execute(
        self,
        vehicle: Vehicle,
        component: Optional[str] = None,
        system: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get component test information.
        
        Args:
            vehicle: Vehicle specification
            component: Specific component to find (e.g., "Wheel Speed Sensors", "Electronic Brake Control Module")
            system: System category (e.g., "ABS", "Charging System", "HVAC System")
            query: Alternative search query
            **kwargs: Additional options
            
        Returns:
            ToolResult with component test information
        """
        search_term = component or query
        logger.info(f"Component tests: component={component}, system={system}, query={query}")
        
        if not self.browser:
            return ToolResult(
                success=False,
                error="Browser controller not available",
                source=self.name
            )
        
        try:
            # Skip vehicle selection if flag is set (vehicle already selected via plate lookup)
            if kwargs.get('skip_vehicle_selection'):
                print(f"[ComponentTestsTool] Skipping vehicle selection (already selected)")
                vehicle_selected = True
            else:
                # Ensure vehicle is selected
                vehicle_selected = await self.ensure_vehicle_selected(vehicle)
            if not vehicle_selected:
                return ToolResult(
                    success=False,
                    error="Could not select vehicle",
                    source=self.name
                )
            
            # Open Component Tests via quick access
            await self._open_component_tests()
            
            # Map search term to actual component name
            target_component = None
            target_system = system
            
            if search_term:
                # Try semantic mapping first
                mapped = self._get_semantic_component(search_term)
                if mapped:
                    target_component = mapped
                    logger.info(f"Mapped '{search_term}' -> '{target_component}'")
                else:
                    target_component = search_term
                
                # Find system if not specified
                if not target_system:
                    target_system = self._get_system_for_component(target_component)
                    logger.info(f"Found system for component: {target_system}")
            
            # Navigate and extract
            if target_system:
                # Expand the system category
                expanded = await self._expand_system(target_system)
                if not expanded:
                    logger.warning(f"Could not expand system: {target_system}")
                
                await random_delay(1000, 1500)
                
                if target_component:
                    # Click specific component
                    result = await self._click_component(target_component)
                else:
                    # List components in the system
                    result = await self._list_system_components(target_system)
            elif target_component:
                # Search across all systems
                result = await self._search_all_systems(target_component)
            else:
                # List all available systems
                result = await self._list_systems()
            
            if result:
                return ToolResult(
                    success=True,
                    data=result.get("data", result),
                    source=self.name,
                    images=result.get("images", [])
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Component not found: {search_term or system or 'no search term'}",
                    source=self.name
                )
                
        except Exception as e:
            logger.exception(f"Error in component tests: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to get component tests: {str(e)}",
                source=self.name
            )
    
    async def _open_component_tests(self) -> None:
        """Open the Component Tests page via quick access."""
        logger.info("Opening Component Tests")
        
        # Get home to access quick access panel
        home_sel = self.get_selector("module_selector.home") or "li.home a"
        
        # Check if quick access is visible
        quick_access_visible = False
        try:
            qa_elem = await self.browser.query_selector("#quickLinkRegion")
            if qa_elem and await qa_elem.is_visible():
                quick_access_visible = True
        except:
            pass
        
        if not quick_access_visible:
            try:
                await self.browser.click(home_sel, timeout=5000)
            except:
                pass
            await random_delay(1200, 2000)
        
        # Close any existing modal
        await self.close_modal()
        
        # Click Component Tests quick access
        selector = self._ct_config.get("quick_access", "#ctmQuickAccess")
        logger.info(f"Clicking: {selector}")
        await self.browser.click(selector, timeout=10000)
        await random_delay(2000, 3000)
        
        logger.info("Component Tests page opened")
    
    async def _expand_system(self, system_name: str) -> bool:
        """Expand a system category in the tree using mapped selectors."""
        logger.info(f"Expanding system: {system_name}")
        
        tree_sel = self._ct_config.get("tree_selectors", {})
        system_link_sel = tree_sel.get("system_link", "li.usercontrol.node.branch > a")
        
        result = await self.browser.evaluate("""
            (args) => {
                const { systemName, systemLinkSel } = args;
                const systemLower = systemName.toLowerCase();
                
                // Find system links
                const links = document.querySelectorAll(systemLinkSel);
                
                for (const link of links) {
                    const text = link.textContent?.trim() || '';
                    
                    if (text.toLowerCase() === systemLower || 
                        text.toLowerCase().includes(systemLower)) {
                        // Click to expand
                        link.click();
                        return { expanded: true, system: text };
                    }
                }
                
                // Fallback: try any link containing the system name
                const allLinks = document.querySelectorAll('li.usercontrol a');
                for (const link of allLinks) {
                    const text = link.textContent?.trim() || '';
                    if (text.toLowerCase() === systemLower) {
                        link.click();
                        return { expanded: true, system: text, fallback: true };
                    }
                }
                
                return { error: 'System not found', searched: systemName };
            }
        """, {"systemName": system_name, "systemLinkSel": system_link_sel})
        
        logger.info(f"Expand result: {result}")
        
        if result.get("error"):
            return False
        
        await random_delay(1500, 2000)
        return True
    
    async def _click_component(self, component_name: str) -> Optional[Dict]:
        """Click a specific component and extract its details."""
        logger.info(f"Clicking component: {component_name}")
        
        tree_sel = self._ct_config.get("tree_selectors", {})
        component_link_sel = tree_sel.get("component_link", "li.usercontrol.node.leaf > a")
        
        click_result = await self.browser.evaluate("""
            (args) => {
                const { componentName, componentLinkSel } = args;
                const compLower = componentName.toLowerCase();
                
                // Find component links (leaf nodes)
                const links = document.querySelectorAll(componentLinkSel);
                
                // Exact match first
                for (const link of links) {
                    const text = link.textContent?.trim() || '';
                    if (text.toLowerCase() === compLower) {
                        link.click();
                        return { clicked: text, exact: true };
                    }
                }
                
                // Partial match
                for (const link of links) {
                    const text = link.textContent?.trim() || '';
                    if (text.toLowerCase().includes(compLower) || 
                        compLower.includes(text.toLowerCase())) {
                        link.click();
                        return { clicked: text, partial: true };
                    }
                }
                
                // Fallback: any leaf node containing words
                const words = compLower.split(/\s+/);
                for (const link of links) {
                    const text = link.textContent?.trim().toLowerCase() || '';
                    if (words.some(w => w.length > 3 && text.includes(w))) {
                        link.click();
                        return { clicked: link.textContent?.trim(), word_match: true };
                    }
                }
                
                return { error: 'Component not found' };
            }
        """, {"componentName": component_name, "componentLinkSel": component_link_sel})
        
        logger.info(f"Click result: {click_result}")
        
        if click_result.get("error"):
            return None
        
        await random_delay(2000, 2500)
        
        # Extract the component details
        return await self._extract_component_details(click_result.get("clicked", component_name))
    
    async def _extract_component_details(self, component_name: str = "") -> Dict:
        """Extract component test details from the current page."""
        logger.info("Extracting component details")
        
        content = await self.browser.evaluate("""
            () => {
                const result = {
                    title: '',
                    module_location: '',
                    operation: '',
                    pinouts: [],
                    sections: []
                };
                
                // Get title from breadcrumb or heading
                const breadcrumb = document.querySelector('.breadcrumb, [class*="breadcrumb"]');
                const heading = document.querySelector('h1, h2, .title, .articleTitle');
                result.title = heading?.textContent?.trim() || 
                              breadcrumb?.textContent?.trim() || '';
                
                // Look for Module Location section
                const locationHeader = Array.from(document.querySelectorAll('h3, h4, .sectionHeader, strong, b'))
                    .find(el => el.textContent?.toLowerCase().includes('module location') || 
                               el.textContent?.toLowerCase().includes('location'));
                
                if (locationHeader) {
                    // Get text after the header
                    let sibling = locationHeader.nextElementSibling || locationHeader.parentElement?.nextElementSibling;
                    while (sibling && !sibling.matches('h3, h4, .sectionHeader, table')) {
                        const text = sibling.textContent?.trim();
                        if (text) {
                            result.module_location += text + ' ';
                        }
                        sibling = sibling.nextElementSibling;
                    }
                    // Also check if text is in same element
                    const parentText = locationHeader.parentElement?.textContent?.trim() || '';
                    if (parentText.length > locationHeader.textContent.length) {
                        result.module_location = parentText.replace(locationHeader.textContent, '').trim();
                    }
                }
                
                // Look for Operation section
                const operationHeader = Array.from(document.querySelectorAll('h3, h4, .sectionHeader, strong, b'))
                    .find(el => el.textContent?.toLowerCase().includes('operation'));
                
                if (operationHeader) {
                    let sibling = operationHeader.nextElementSibling || operationHeader.parentElement?.nextElementSibling;
                    while (sibling && !sibling.matches('h3, h4, .sectionHeader, table')) {
                        const text = sibling.textContent?.trim();
                        if (text) {
                            result.operation += text + ' ';
                        }
                        sibling = sibling.nextElementSibling;
                    }
                    const parentText = operationHeader.parentElement?.textContent?.trim() || '';
                    if (parentText.length > operationHeader.textContent.length && !result.operation) {
                        result.operation = parentText.replace(operationHeader.textContent, '').trim();
                    }
                }
                
                // Look for Pinouts table
                const pinoutsHeader = Array.from(document.querySelectorAll('h3, h4, .sectionHeader, strong, b'))
                    .find(el => el.textContent?.toLowerCase().includes('pinout'));
                
                if (pinoutsHeader) {
                    // Find the table after it
                    let tableEl = pinoutsHeader.nextElementSibling;
                    while (tableEl && !tableEl.matches('table')) {
                        tableEl = tableEl.nextElementSibling;
                    }
                    
                    if (!tableEl) {
                        // Table might be in same container
                        tableEl = pinoutsHeader.closest('section, div')?.querySelector('table');
                    }
                    
                    if (tableEl) {
                        const rows = tableEl.querySelectorAll('tr');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td, th');
                            if (cells.length >= 2) {
                                const pin = cells[0]?.textContent?.trim() || '';
                                const desc = cells[1]?.textContent?.trim() || '';
                                if (pin && desc) {
                                    result.pinouts.push({ pin, description: desc });
                                }
                            }
                        }
                    }
                }
                
                // Also get any tables on the page
                const tables = document.querySelectorAll('table');
                for (const table of tables) {
                    const rows = table.querySelectorAll('tr');
                    if (rows.length > 0 && result.pinouts.length === 0) {
                        const tableData = [];
                        for (const row of rows) {
                            const cells = [...row.querySelectorAll('td, th')].map(c => c.textContent?.trim());
                            if (cells.length >= 2 && cells.some(c => c)) {
                                tableData.push(cells);
                            }
                        }
                        if (tableData.length > 0) {
                            result.pinouts = tableData.map(row => ({
                                pin: row[0] || '',
                                description: row.slice(1).join(' - ')
                            }));
                        }
                    }
                }
                
                // Get all section headers and content
                const sections = document.querySelectorAll('section, .section, [class*="content"] > div');
                for (const section of sections) {
                    const header = section.querySelector('h3, h4, .header')?.textContent?.trim();
                    const content = section.textContent?.trim();
                    if (header && content && content.length > header.length) {
                        result.sections.push({
                            title: header,
                            content: content.substring(0, 1000)
                        });
                    }
                }
                
                return result;
            }
        """)
        
        logger.info(f"Extracted: title='{content.get('title', '')[:50]}', pinouts={len(content.get('pinouts', []))}")
        
        # Extract images
        images = await self.extract_images_from_modal()
        
        result = {
            "data": content,
            "images": images if images else []
        }
        
        return result
    
    async def _list_system_components(self, system_name: str) -> Optional[Dict]:
        """List all components under a system category."""
        logger.info(f"Listing components in: {system_name}")
        
        components = await self.browser.evaluate("""
            (systemName) => {
                const systemLower = systemName.toLowerCase();
                const components = [];
                
                // Find the system node
                const nodes = document.querySelectorAll('li.usercontrol.node');
                let systemNode = null;
                
                for (const node of nodes) {
                    const text = node.textContent?.trim().toLowerCase() || '';
                    if (text.startsWith(systemLower) || text.includes(systemLower)) {
                        systemNode = node;
                        break;
                    }
                }
                
                if (!systemNode) return { error: 'System not found' };
                
                // Get child components
                const children = systemNode.querySelectorAll('li.usercontrol.leaf a, ul li a');
                for (const child of children) {
                    const text = child.textContent?.trim();
                    if (text) {
                        components.push(text);
                    }
                }
                
                return {
                    system: systemName,
                    components: components
                };
            }
        """, system_name)
        
        logger.info(f"Found {len(components.get('components', []))} components")
        
        return {"data": components}
    
    async def _search_all_systems(self, search_term: str) -> Optional[Dict]:
        """Search for a component across all systems."""
        logger.info(f"Searching all systems for: {search_term}")
        
        # First expand all systems
        await self._expand_all_systems()
        
        # Then click the component
        return await self._click_component(search_term)
    
    async def _expand_all_systems(self) -> None:
        """Expand all system categories."""
        logger.info("Expanding all systems")
        
        for _ in range(3):  # Multiple passes for nested nodes
            expanded = await self.browser.evaluate("""
                () => {
                    const collapsed = document.querySelectorAll('li.usercontrol.node.branch:not(.open)');
                    let count = 0;
                    
                    for (const node of collapsed) {
                        const expander = node.querySelector('.expander, .toggle, > span[class*="expand"]');
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
    
    async def _list_systems(self) -> Dict:
        """List all available system categories."""
        logger.info("Listing all systems")
        
        systems = await self.browser.evaluate("""
            () => {
                const systems = [];
                
                // Find top-level tree nodes
                const nodes = document.querySelectorAll('li.usercontrol.node.branch > a, li.usercontrol.node > a');
                
                for (const link of nodes) {
                    const text = link.textContent?.trim();
                    if (text && !systems.includes(text)) {
                        systems.push(text);
                    }
                }
                
                // Also check for direct links
                const directLinks = document.querySelectorAll('.tree a, .treeview a');
                for (const link of directLinks) {
                    const text = link.textContent?.trim();
                    if (text && !systems.includes(text)) {
                        systems.push(text);
                    }
                }
                
                return systems.slice(0, 20);
            }
        """)
        
        logger.info(f"Found {len(systems)} systems")
        
        return {
            "data": {
                "message": "Available systems in Component Tests",
                "systems": systems
            }
        }
    
    async def _close_modal(self) -> None:
        """Close any open modal."""
        try:
            await self.browser.evaluate("""
                () => {
                    const closeBtn = document.querySelector('.modalDialogView .close, .modal .close');
                    if (closeBtn) closeBtn.click();
                }
            """)
            await random_delay(300, 500)
        except Exception as e:
            logger.debug(f"Error closing modal: {e}")
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        if not data:
            return "No data found"
        
        lines = []
        
        # Title
        if data.get("title"):
            lines.append(f"**{data['title']}**\n")
        
        # Module Location
        if data.get("module_location"):
            lines.append(f"**Module Location:**")
            lines.append(data["module_location"].strip())
            lines.append("")
        
        # Operation
        if data.get("operation"):
            lines.append(f"**Operation:**")
            lines.append(data["operation"].strip())
            lines.append("")
        
        # Pinouts
        if data.get("pinouts"):
            lines.append(f"**Pinouts:**")
            for pin in data["pinouts"][:20]:  # Limit to 20
                if isinstance(pin, dict):
                    lines.append(f"  Pin {pin.get('pin', '?')}: {pin.get('description', '')}")
                else:
                    lines.append(f"  {pin}")
            lines.append("")
        
        # Systems list
        if data.get("systems"):
            lines.append("**Available Systems:**")
            for system in data["systems"]:
                lines.append(f"  - {system}")
        
        # Components list
        if data.get("components"):
            lines.append(f"**Components in {data.get('system', 'system')}:**")
            for comp in data["components"]:
                lines.append(f"  - {comp}")
        
        return "\n".join(lines) if lines else str(data)
