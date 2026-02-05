"""
Search Mitchell Tool - 1Search fallback for any query.
"""
import asyncio
import random
from typing import Dict, List, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle, random_delay


class SearchMitchellTool(MitchellTool):
    """
    1Search - Unified search across all ShopKeyPro content.
    
    This is the Tier 2 fallback tool that searches across:
    - SureTrack Real Fixes (actual shop repair data)
    - Service Manual articles
    - Wiring diagrams
    - Component tests
    - Parts & Labor estimates
    
    Access: Module Selector > 1Search (li.oneView a)
    """
    
    name = "search_mitchell"
    description = "Search all ShopKeyPro content (1Search fallback)"
    tier = 2
    
    async def execute(
        self,
        vehicle: Vehicle,
        query: str = "",
        max_results: int = 10,
        **kwargs
    ) -> ToolResult:
        """
        Search ShopKeyPro for the given query.
        
        Args:
            vehicle: Vehicle specification
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with search results
        """
        # Enable debug screenshots if requested
        if kwargs.get('debug_screenshots'):
            self.debug_screenshots = True
            self._screenshot_counter = 0
        
        if not query:
            return ToolResult(
                success=False,
                error="No search query provided",
                source=self.name
            )
        
        if not self.browser:
            return ToolResult(
                success=False,
                error="Browser controller not available",
                source=self.name
            )
        
        try:
            # Step 1: Initial state
            await self.save_debug_screenshot("01_initial_state")
            
            # Skip vehicle selection if flag is set (vehicle already selected via plate lookup)
            if kwargs.get('skip_vehicle_selection'):
                print(f"[SearchTool] Skipping vehicle selection (already selected)")
                vehicle_selected = True
            else:
                # Ensure vehicle is selected
                vehicle_selected = await self.ensure_vehicle_selected(vehicle)
            
            # Step 2: After vehicle selection
            await self.save_debug_screenshot("02_after_vehicle_select")
            
            # Check if additional options are required
            if not vehicle_selected:
                required_opts = self.get_pending_required_options()
                if required_opts:
                    return ToolResult(
                        success=False,
                        error="Additional vehicle options required",
                        source=self.name,
                        needs_more_info=True,
                        required_options=required_opts
                    )
                return ToolResult(
                    success=False,
                    error="Could not select vehicle",
                    source=self.name
                )
            
            # Get selectors from config
            search_module_sel = self.get_selector("module_selector.one_search")
            
            # Step 3: Before navigating to search
            await self.save_debug_screenshot("03_before_search_nav")
            
            # Navigate to 1Search module
            await random_delay(500, 1000)
            await self.browser.click(search_module_sel or "li.oneView a", timeout=5000)
            await random_delay(2000, 3000)
            
            # Step 4: On search page
            await self.save_debug_screenshot("04_search_page")
            
            # Escape query for JavaScript
            escaped_query = query.replace("'", "\\'")
            
            # Clear any existing search and enter new query
            await random_delay(400, 800)
            js_code = f"""
                const searchBox = document.querySelector('.searchBox');
                if (searchBox) {{
                    searchBox.value = '';
                    searchBox.value = '{escaped_query}';
                    searchBox.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            """
            await self.browser.evaluate(js_code)
            await random_delay(500, 800)
            
            # Submit the search via button click
            await self.browser.evaluate("""
                document.querySelector('button.submit')?.click()
            """)
            await random_delay(3000, 4500)  # Wait for results to load
            
            # Step 5: Search results
            await self.save_debug_screenshot("05_search_results")
            
            # Extract search results
            results = await self._extract_search_results(max_results)
            
            # Step 6: After extraction
            await self.save_debug_screenshot("06_data_extracted")
            
            if not results:
                return ToolResult(
                    success=True,
                    data={
                        "query": query,
                        "results": [],
                        "total_count": 0,
                        "message": "No results found for this query"
                    },
                    source=self.name,
                    auto_selected_options=self.get_auto_selected_options() or None
                )
            
            # Step 7: Final state
            await self.save_debug_screenshot("07_final_state")
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results["items"],
                    "total_count": results["total"],
                    "categories": results.get("categories", [])
                },
                source=self.name,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            await self.save_debug_screenshot("error_state")
            return ToolResult(
                success=False,
                error=f"Error searching: {str(e)}",
                source=self.name
            )
    
    async def _extract_search_results(self, max_results: int) -> Optional[Dict[str, Any]]:
        """Extract search results from the page."""
        if not self.browser:
            return None
        
        try:
            result = await self.browser.evaluate(f"""
                (() => {{
                    const results = {{}};
                    
                    // Get result counts
                    const counts = Array.from(document.querySelectorAll('.resultCount'))
                        .map(el => parseInt(el.textContent) || 0);
                    results.total = counts.reduce((a, b) => a + b, 0);
                    
                    // Get category titles
                    const titles = Array.from(document.querySelectorAll('.resultsTitle'))
                        .map(el => el.textContent.trim());
                    results.categories = titles;
                    
                    // Get result items from the content region
                    const contentRegion = document.querySelector('#ContentRegion');
                    if (!contentRegion) return results;
                    
                    const items = [];
                    
                    // Look for card-like elements
                    const cards = contentRegion.querySelectorAll('[class*=card], [class*=result], .item');
                    cards.forEach((card, idx) => {{
                        if (idx >= {max_results}) return;
                        
                        const title = card.querySelector('h3, h4, .title, a')?.textContent?.trim();
                        const desc = card.querySelector('p, .description, .snippet')?.textContent?.trim();
                        const link = card.querySelector('a')?.href;
                        
                        if (title) {{
                            items.push({{
                                title: title.substring(0, 200),
                                description: desc?.substring(0, 300) || '',
                                link: link || ''
                            }});
                        }}
                    }});
                    
                    // If no cards found, try to get text-based results
                    if (items.length === 0) {{
                        const text = contentRegion.textContent;
                        const lines = text.split('\\n')
                            .map(l => l.trim())
                            .filter(l => l.length > 10 && l.length < 200);
                        
                        // Get unique lines as results
                        const seen = new Set();
                        for (const line of lines) {{
                            if (items.length >= {max_results}) break;
                            if (!seen.has(line) && !line.includes('Cookie') && !line.includes('Privacy')) {{
                                seen.add(line);
                                items.push({{
                                    title: line.substring(0, 100),
                                    description: '',
                                    link: ''
                                }});
                            }}
                        }}
                    }}
                    
                    results.items = items;
                    return results;
                }})()
            """)
            return result if isinstance(result, dict) else None
        except Exception as e:
            print(f"Error extracting search results: {e}")
            return None
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        lines = [
            f"**Search Results for: {data['query']}**",
            f"Found {data['total_count']} results\n"
        ]
        
        if data.get('categories'):
            lines.append("**Categories:** " + ", ".join(data['categories'][:5]))
            lines.append("")
        
        for i, item in enumerate(data['results'][:10], 1):
            lines.append(f"{i}. **{item['title']}**")
            if item.get('description'):
                lines.append(f"   {item['description'][:150]}...")
            lines.append("")
        
        if not data['results']:
            lines.append("No specific results found. Try a different search term.")
        
        return "\n".join(lines)
