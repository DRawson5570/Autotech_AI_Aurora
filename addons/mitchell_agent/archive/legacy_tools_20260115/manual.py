"""
Browse Manual Tool - Navigates Service Manual tree structure.
"""
import asyncio
from typing import Dict, List, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle


# Service Manual categories - hardcoded since they rarely change
SERVICE_MANUAL_CATEGORIES = [
    "Brakes",
    "Electrical", 
    "Transmission",
    "Steering",
    "Suspension",
    "HVAC",
    "Engine Mechanical",
    "Drivelines & Axles",
    "Body & Frame",
    "Accessories & Equipment",
    "General Information",
    "Maintenance",
    "Restraints",
    "Quick Lookups",
    "Engine Performance"
]


class BrowseManualTool(MitchellTool):
    """
    Tier 3 Tool - Navigates the Service Manual tree structure.
    
    Access: Module Selector > Service Manual (li.serviceManual a)
    
    Allows browsing the complete Service Manual tree with categories:
    - Brakes, Electrical, Transmission, Steering, Suspension
    - HVAC, Engine Mechanical, Drivelines & Axles
    - Body & Frame, Accessories & Equipment
    - General Information, Maintenance, Restraints
    - Quick Lookups, Engine Performance
    
    Each category has subcategories and topics leading to articles.
    """
    
    name = "browse_manual"
    description = "Browse Service Manual by category and topic"
    tier = 3
    
    async def execute(
        self,
        vehicle: Vehicle,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        topic: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Browse the Service Manual tree.
        
        Args:
            vehicle: Vehicle specification
            category: Top-level category (e.g., "Brakes", "Electrical")
            subcategory: Subcategory within category
            topic: Specific topic within subcategory
            query: Alternative query string to search within manual
            
        Returns:
            ToolResult with manual content or tree navigation info
        """
        if not self.browser:
            return ToolResult(
                success=False,
                error="Browser controller not available",
                source=self.name
            )
        
        try:
            # Ensure vehicle is selected
            await self.ensure_vehicle_selected(vehicle)
            
            # Close any existing modal
            await self.close_modal()
            await self.browser.evaluate(
                "document.querySelector('.modal_mask')?.remove()"
            )
            
            # Navigate to Service Manual module
            service_manual_selector = self.get_selector("module_selector.service_manual")
            await self.browser.click(service_manual_selector, timeout=5000)
            await asyncio.sleep(2)
            
            # If no category specified, return available categories
            if not category and not query:
                categories = await self._get_categories()
                return ToolResult(
                    success=True,
                    data={
                        "type": "category_list",
                        "categories": categories
                    },
                    source=self.name
                )
            
            # If query is provided, search within manual tree
            if query and not category:
                # Try to match query to a category
                category = self._match_query_to_category(query)
            
            # Navigate to category
            if category:
                expanded = await self._expand_category(category)
                if not expanded:
                    return ToolResult(
                        success=False,
                        error=f"Could not find category: {category}",
                        source=self.name
                    )
                
                await asyncio.sleep(1)
                
                # If no subcategory, return subcategories
                if not subcategory and not query:
                    subcategories = await self._get_subcategories(category)
                    return ToolResult(
                        success=True,
                        data={
                            "type": "subcategory_list",
                            "category": category,
                            "subcategories": subcategories
                        },
                        source=self.name
                    )
                
                # Navigate to subcategory
                target_subcategory = subcategory or query
                if target_subcategory:
                    expanded = await self._expand_subcategory(target_subcategory)
                    if not expanded:
                        # Return available subcategories
                        subcategories = await self._get_subcategories(category)
                        return ToolResult(
                            success=True,
                            data={
                                "type": "subcategory_list",
                                "category": category,
                                "subcategories": subcategories,
                                "note": f"Subcategory '{target_subcategory}' not found"
                            },
                            source=self.name
                        )
                    
                    await asyncio.sleep(1)
                    
                    # If topic specified, get the article
                    if topic:
                        content = await self._get_topic_content(topic)
                        return ToolResult(
                            success=True,
                            data={
                                "type": "article",
                                "category": category,
                                "subcategory": target_subcategory,
                                "topic": topic,
                                "content": content
                            },
                            source=self.name
                        )
                    
                    # Return topics list
                    topics = await self._get_topics()
                    return ToolResult(
                        success=True,
                        data={
                            "type": "topic_list",
                            "category": category,
                            "subcategory": target_subcategory,
                            "topics": topics
                        },
                        source=self.name
                    )
            
            # Return what we have
            return ToolResult(
                success=True,
                data={
                    "type": "category_list",
                    "categories": SERVICE_MANUAL_CATEGORIES
                },
                source=self.name
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error browsing manual: {str(e)}",
                source=self.name
            )
    
    def _match_query_to_category(self, query: str) -> Optional[str]:
        """Match a query string to a Service Manual category."""
        query_lower = query.lower()
        
        category_keywords = {
            "Brakes": ["brake", "abs", "parking brake", "bleeding"],
            "Electrical": ["wiring", "electrical", "fuse", "relay", "lighting"],
            "Transmission": ["trans", "gear", "clutch", "automatic", "manual trans"],
            "Steering": ["steering", "power steering", "rack", "column"],
            "Suspension": ["suspension", "shock", "strut", "control arm", "ball joint"],
            "HVAC": ["hvac", "air conditioning", "a/c", "heater", "climate"],
            "Engine Mechanical": ["engine", "timing", "head gasket", "oil leak"],
            "Drivelines & Axles": ["axle", "differential", "cv joint", "driveshaft"],
            "Body & Frame": ["body", "door", "window", "trim", "frame"],
            "Accessories & Equipment": ["accessory", "equipment", "module"],
            "General Information": ["general", "specification", "vin"],
            "Maintenance": ["maintenance", "service interval", "filter"],
            "Restraints": ["airbag", "seatbelt", "restraint", "srs"],
            "Quick Lookups": ["quick", "lookup"],
            "Engine Performance": ["performance", "fuel", "emission", "idle"]
        }
        
        for category, keywords in category_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return category
        
        return None
    
    async def _get_categories(self) -> List[str]:
        """Get top-level categories from Service Manual tree."""
        if not self.browser:
            return SERVICE_MANUAL_CATEGORIES
        
        try:
            result = await self.browser.evaluate("""
                (() => {
                    const categories = [];
                    const nodes = document.querySelectorAll('ul.usercontrol.tree > li.usercontrol.node[data-level="0"]');
                    
                    for (const node of nodes) {
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.trim();
                        if (text) {
                            categories.push(text);
                        }
                    }
                    
                    return categories.length > 0 ? categories : null;
                })()
            """)
            return result if result else SERVICE_MANUAL_CATEGORIES
        except Exception:
            return SERVICE_MANUAL_CATEGORIES
    
    async def _expand_category(self, category: str) -> bool:
        """Expand a category in the tree."""
        if not self.browser:
            return False
        
        try:
            result = await self.browser.evaluate(f"""
                (() => {{
                    const target = '{category.lower()}';
                    const nodes = document.querySelectorAll('li.usercontrol.node[data-level="0"]');
                    
                    for (const node of nodes) {{
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.toLowerCase() || '';
                        if (text.includes(target) || target.includes(text.split(' ')[0])) {{
                            const expander = node.querySelector('.treeExpandCollapseIcon');
                            if (expander) {{
                                expander.click();
                                return true;
                            }}
                        }}
                    }}
                    return false;
                }})()
            """)
            return bool(result)
        except Exception:
            return False
    
    async def _get_subcategories(self, category: str) -> List[str]:
        """Get subcategories under a category."""
        if not self.browser:
            return []
        
        try:
            result = await self.browser.evaluate(f"""
                (() => {{
                    const subcats = [];
                    const target = '{category.lower()}';
                    const nodes = document.querySelectorAll('li.usercontrol.node');
                    
                    let inCategory = false;
                    
                    for (const node of nodes) {{
                        const level = node.getAttribute('data-level');
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.trim() || '';
                        
                        if (level === '0' && text.toLowerCase().includes(target)) {{
                            inCategory = true;
                            continue;
                        }}
                        
                        if (inCategory) {{
                            if (level === '0') break;  // Next top category
                            if (level === '1') {{
                                subcats.push(text);
                            }}
                        }}
                    }}
                    
                    return subcats;
                }})()
            """)
            return result if isinstance(result, list) else []
        except Exception:
            return []
    
    async def _expand_subcategory(self, subcategory: str) -> bool:
        """Expand a subcategory in the tree."""
        if not self.browser:
            return False
        
        try:
            result = await self.browser.evaluate(f"""
                (() => {{
                    const target = '{subcategory.lower()}';
                    const nodes = document.querySelectorAll('li.usercontrol.node[data-level="1"]');
                    
                    for (const node of nodes) {{
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.toLowerCase() || '';
                        if (text.includes(target) || target.includes(text.split(' ')[0])) {{
                            const expander = node.querySelector('.treeExpandCollapseIcon');
                            if (expander) {{
                                expander.click();
                                return true;
                            }}
                        }}
                    }}
                    return false;
                }})()
            """)
            return bool(result)
        except Exception:
            return False
    
    async def _get_topics(self) -> List[str]:
        """Get topics (leaf nodes) in current tree expansion."""
        if not self.browser:
            return []
        
        try:
            result = await self.browser.evaluate("""
                (() => {
                    const topics = [];
                    const nodes = document.querySelectorAll('li.usercontrol.node.leaf');
                    
                    for (const node of nodes) {
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.trim();
                        if (text) {
                            topics.push(text);
                        }
                    }
                    
                    return topics;
                })()
            """)
            return result if isinstance(result, list) else []
        except Exception:
            return []
    
    async def _get_topic_content(self, topic: str) -> str:
        """Get content for a specific topic."""
        if not self.browser:
            return ""
        
        try:
            # Escape topic for JavaScript
            escaped_topic = topic.lower().replace("'", "\\'")
            
            # Click on the topic to open it
            js_code = f"""
                (() => {{
                    const target = '{escaped_topic}';
                    const nodes = document.querySelectorAll('li.usercontrol.node.leaf');
                    
                    for (const node of nodes) {{
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.toLowerCase() || '';
                        if (text.includes(target)) {{
                            const showIcon = node.querySelector('.showContentIcon');
                            if (showIcon) {{
                                showIcon.click();
                                return true;
                            }}
                        }}
                    }}
                    return false;
                }})()
            """
            clicked = await self.browser.evaluate(js_code)
            
            if not clicked:
                return ""
            
            await asyncio.sleep(2)
            
            # Extract content from modal
            content = await self.browser.evaluate("""
                (() => {
                    const modal = document.querySelector('.modalDialogView:last-child');
                    if (!modal) return '';
                    
                    const content = modal.querySelector('.content');
                    return content ? content.innerText : '';
                })()
            """)
            
            # Close the content modal
            await self.close_modal()
            
            return content if isinstance(content, str) else ""
        except Exception:
            return ""
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        
        if not data:
            return "No manual content found."
        
        result_type = data.get("type", "")
        
        if result_type == "category_list":
            categories = data.get("categories", [])
            lines = ["**Service Manual Categories:**\n"]
            for cat in categories:
                lines.append(f"  - {cat}")
            return "\n".join(lines)
        
        if result_type == "subcategory_list":
            category = data.get("category", "")
            subcats = data.get("subcategories", [])
            note = data.get("note", "")
            
            lines = [f"**{category} - Subcategories:**\n"]
            for subcat in subcats:
                lines.append(f"  - {subcat}")
            if note:
                lines.append(f"\n_{note}_")
            return "\n".join(lines)
        
        if result_type == "topic_list":
            category = data.get("category", "")
            subcategory = data.get("subcategory", "")
            topics = data.get("topics", [])
            
            lines = [f"**{category} > {subcategory} - Topics:**\n"]
            for topic in topics:
                lines.append(f"  - {topic}")
            return "\n".join(lines)
        
        if result_type == "article":
            category = data.get("category", "")
            subcategory = data.get("subcategory", "")
            topic = data.get("topic", "")
            content = data.get("content", "")
            
            header = f"**{category} > {subcategory} > {topic}**\n\n"
            return header + content
        
        return str(data)
