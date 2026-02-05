"""
Tire Specs Tool - Retrieves tire and TPMS information.
"""
import asyncio
import random
from typing import Dict, List, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle, random_delay


class TireSpecsTool(MitchellTool):
    """
    Retrieves tire specifications and TPMS information.
    
    Access: Quick Access Panel > Tire Info (#tpmsTireFitmentQuickAccess)
    
    Returns information including:
    - Tire fitment specifications
    - TPMS sensor part numbers
    - Lift points for tire service
    - Tire pressure specifications
    """
    
    name = "get_tire_specs"
    description = "Get tire specifications and TPMS sensor information"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        query: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get tire and TPMS specifications.
        
        Args:
            vehicle: Vehicle specification
            query: Optional search query within tire data
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with tire specifications
        """
        # Enable debug screenshots if requested
        if kwargs.get('debug_screenshots'):
            self.debug_screenshots = True
            self._screenshot_counter = 0
        
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
                print(f"[TireTool] Skipping vehicle selection (already selected)")
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
            
            # Quick Access panel is on the HOME view, not inside any module
            tire_selector = self.get_selector("quick_access.tire_info") or "#tpmsTireFitmentQuickAccess"
            home_sel = self.get_selector("module_selector.home") or "li.home a"
            
            # First check if quick access is already visible
            quick_access_visible = False
            try:
                qa_elem = await self.browser.query_selector("#quickLinkRegion")
                if qa_elem and await qa_elem.is_visible():
                    quick_access_visible = True
            except:
                pass
            
            if not quick_access_visible:
                # Navigate to Home to get the quick access panel
                await random_delay(500, 1000)
                try:
                    await self.browser.click(home_sel, timeout=5000)
                except:
                    pass
                await random_delay(1200, 2000)
            
            # Close any existing modal
            await self.close_modal()
            
            # Remove any modal mask
            await self.browser.evaluate(
                "document.querySelector('.modal_mask')?.remove()"
            )
            
            # Step 3: Before clicking tire info
            await self.save_debug_screenshot("03_before_tire_click")
            
            # Click Tire Info quick access (use #quickLinkRegion prefix)
            selector = tire_selector
            if selector.startswith("#") and not selector.startswith("#quickLinkRegion"):
                selector = f"#quickLinkRegion {selector}"
            await random_delay(400, 800)
            await self.browser.click(selector, timeout=10000)
            await random_delay(2000, 3500)
            
            # Step 4: Tire modal open
            await self.save_debug_screenshot("04_tire_modal_open")
            
            # Extract tire data
            tire_data = await self._extract_tire_data()
            
            # Step 5: After extraction
            await self.save_debug_screenshot("05_data_extracted")
            
            # Close the modal
            await self.close_modal()
            
            # Step 6: Final state
            await self.save_debug_screenshot("06_final_state")
            
            if not tire_data:
                return ToolResult(
                    success=False,
                    error="Could not extract tire specifications",
                    source=self.name
                )
            
            return ToolResult(
                success=True,
                data=tire_data,
                source=self.name,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            await self.save_debug_screenshot("error_state")
            return ToolResult(
                success=False,
                error=f"Error retrieving tire specifications: {str(e)}",
                source=self.name
            )
    
    async def _extract_tire_data(self) -> Dict[str, Any]:
        """Extract tire and TPMS data from the page."""
        if not self.browser:
            return {}
        
        try:
            result = await self.browser.evaluate("""
                (() => {
                    const data = {
                        tire_fitment: [],
                        tpms_sensors: [],
                        lift_points: [],
                        reset_procedures: [],
                        general_info: []
                    };
                    
                    // Helper to clean text (remove JS artifacts)
                    function cleanText(text) {
                        if (!text) return '';
                        // Remove script content patterns
                        text = text.replace(/\\$\\(document\\)[\\s\\S]*?\\}\\);/g, '');
                        text = text.replace(/\\$\\([^)]+\\)[\\s\\S]*?;/g, '');
                        text = text.replace(/function\\s*\\([^)]*\\)\\s*\\{[\\s\\S]*?\\}/g, '');
                        text = text.replace(/window\\.[A-Za-z]+/g, '');
                        text = text.replace(/setTimeout\\s*\\([\\s\\S]*?\\);/g, '');
                        text = text.replace(/if\\s*\\([^)]+\\)\\s*\\{[^}]*\\}/g, '');
                        text = text.replace(/var\\s+[a-zA-Z_$][a-zA-Z0-9_$]*\\s*=/g, '');
                        text = text.replace(/opener\\.[A-Za-z]+/g, '');
                        text = text.replace(/\\s+/g, ' ').trim();
                        return text;
                    }
                    
                    // Helper to check if text looks like JS code
                    function isJavaScript(text) {
                        if (!text) return false;
                        const jsPatterns = [
                            /\\$\\(document\\)/,
                            /\\$\\(function/,
                            /setTimeout/,
                            /window\\.PD/,
                            /opener\\./,
                            /function\\s*\\(/,
                            /\\.ready\\s*\\(/,
                            /GraphicsManagerModule/
                        ];
                        return jsPatterns.some(p => p.test(text));
                    }
                    
                    // This page is a regular content page, not a modal
                    // Look for content in main page area or iframe
                    let container = document.querySelector('.modalDialogView') 
                                 || document.querySelector('#mainContent')
                                 || document.querySelector('.content')
                                 || document.querySelector('iframe')?.contentDocument?.body
                                 || document.body;
                    
                    if (!container) return data;
                    
                    // Track seen content to avoid duplicates
                    const seenContent = new Set();
                    
                    // Extract Tire Fitment table
                    const tables = container.querySelectorAll('table');
                    for (const table of tables) {
                        const tableText = table.textContent?.toLowerCase() || '';
                        
                        // Check table headers
                        const headers = [];
                        const headerRow = table.querySelector('thead tr, tr:has(th)');
                        if (headerRow) {
                            headerRow.querySelectorAll('th').forEach(th => {
                                headers.push(cleanText(th.textContent).toLowerCase());
                            });
                        }
                        
                        // Process data rows
                        const rows = table.querySelectorAll('tbody tr, tr:has(td)');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length === 0) continue;
                            
                            const rowData = {};
                            const rowValues = [];
                            cells.forEach((cell, i) => {
                                const text = cleanText(cell.textContent);
                                if (text && !isJavaScript(text)) {
                                    const key = headers[i] || 'col_' + i;
                                    rowData[key] = text;
                                    rowValues.push(text);
                                }
                            });
                            
                            // Skip empty or duplicate rows
                            const rowSig = rowValues.join('|');
                            if (rowValues.length === 0 || seenContent.has(rowSig)) continue;
                            seenContent.add(rowSig);
                            
                            // Categorize based on content
                            const rowText = rowValues.join(' ').toLowerCase();
                            if (rowText.includes('tpms') || rowText.includes('sensor') || 
                                rowText.includes('schrader') || rowText.includes('dill')) {
                                data.tpms_sensors.push(rowData);
                            } else if (tableText.includes('size description') || 
                                       tableText.includes('tire') || tableText.includes('wheel')) {
                                data.tire_fitment.push(rowData);
                            } else {
                                data.general_info.push(rowData);
                            }
                        }
                    }
                    
                    // Extract section content (like reset procedures and lift points)
                    const sections = container.querySelectorAll('section, .section, div[class*="content"]');
                    for (const section of sections) {
                        // Skip script/style elements
                        if (section.closest('script') || section.closest('style')) continue;
                        
                        const heading = section.querySelector('h1, h2, h3, h4, .header');
                        const headingText = cleanText(heading?.textContent || '');
                        
                        // Get content excluding scripts
                        const clone = section.cloneNode(true);
                        clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
                        const content = cleanText(clone.textContent);
                        
                        if (!content || isJavaScript(content) || seenContent.has(content.substring(0, 100))) continue;
                        seenContent.add(content.substring(0, 100));
                        
                        const contentLower = content.toLowerCase();
                        
                        if (contentLower.includes('reset') || contentLower.includes('relearn') ||
                            contentLower.includes('ateq') || contentLower.includes('bartec')) {
                            data.reset_procedures.push({
                                title: headingText || 'TPMS Reset Procedure',
                                steps: content
                            });
                        } else if (contentLower.includes('lift') || contentLower.includes('jack') ||
                                   contentLower.includes('hoist')) {
                            data.lift_points.push({
                                title: headingText || 'Lift Points',
                                info: content
                            });
                        }
                    }
                    
                    // Also look for clickable links that expand content
                    const links = container.querySelectorAll('a[href*="#"], a.expandable, a[data-toggle]');
                    const linkTitles = [];
                    links.forEach(link => {
                        const text = cleanText(link.textContent);
                        if (text && !isJavaScript(text) && text.length < 100) {
                            linkTitles.push(text);
                        }
                    });
                    
                    if (linkTitles.length > 0) {
                        data.available_sections = linkTitles;
                    }
                    
                    return data;
                })()
            """)
            return result if isinstance(result, dict) else {}
        except Exception as e:
            print(f"Error extracting tire data: {e}")
            return {}
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        
        if not data:
            return "No tire specifications found."
        
        lines = ["**Tire & TPMS Specifications:**\n"]
        
        # Tire Fitment
        if data.get("tire_fitment"):
            lines.append("**Tire Fitment:**")
            for item in data["tire_fitment"]:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if v:
                            lines.append(f"  - {k}: {v}")
                else:
                    lines.append(f"  - {item}")
            lines.append("")
        
        # TPMS Sensors
        if data.get("tpms_sensors"):
            lines.append("**TPMS Sensors:**")
            for item in data["tpms_sensors"]:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if v:
                            lines.append(f"  - {k}: {v}")
                else:
                    lines.append(f"  - {item}")
            lines.append("")
        
        # Lift Points
        if data.get("lift_points"):
            lines.append("**Lift Points:**")
            for item in data["lift_points"]:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if v:
                            lines.append(f"  - {k}: {v}")
                else:
                    lines.append(f"  - {item}")
            lines.append("")
        
        # General Info
        if data.get("general_info"):
            lines.append("**Additional Information:**")
            for item in data["general_info"]:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if v:
                            lines.append(f"  - {k}: {v}")
                else:
                    lines.append(f"  - {item}")
        
        return "\n".join(lines)
