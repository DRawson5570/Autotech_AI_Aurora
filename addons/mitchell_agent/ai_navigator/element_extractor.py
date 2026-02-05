"""
Element Extractor for AI-Driven Navigation
===========================================

Extracts ALL interactive elements from the current page state,
including modals, shadow DOM, nested elements, and dynamic content.

The extracted elements are formatted as JSON for the LLM to reason about.
"""

import asyncio
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from playwright.async_api import Page, Locator

from .logging_config import get_logger

log = get_logger(__name__)


@dataclass
class ElementInfo:
    """Structured info about an interactive element."""
    id: int                      # Unique ID for this extraction session
    tag: str                     # HTML tag (button, a, input, select, etc.)
    selector: str                # CSS selector to target this element
    text: str                    # Visible text content
    aria_label: Optional[str]    # aria-label attribute
    title: Optional[str]         # title attribute
    role: Optional[str]          # ARIA role
    element_id: Optional[str]    # HTML id attribute
    element_class: Optional[str] # CSS classes
    href: Optional[str]          # href for links
    input_type: Optional[str]    # type for inputs
    placeholder: Optional[str]   # placeholder for inputs
    disabled: bool               # Is element disabled?
    visible: bool                # Is element visible?
    in_modal: bool               # Is element inside a modal/dialog?
    depth: int                   # Nesting depth (for tree structures)
    parent_text: Optional[str]   # Parent element's text (context)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, filtering out None values for cleaner JSON."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != ""}


# JavaScript to extract all interactive elements
EXTRACT_ELEMENTS_JS = """
() => {
    const results = [];
    let elementId = 0;
    
    // Check if element is visible
    function isVisible(el) {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
        }
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }
    
    // Check if element is in a modal/dialog
    function isInModal(el) {
        let current = el;
        while (current) {
            const tag = current.tagName?.toLowerCase();
            const role = current.getAttribute?.('role');
            // className can be SVGAnimatedString for SVG elements, so convert to string
            const classes = (current.className?.toString?.() || current.className || '').toLowerCase();
            
            if (tag === 'dialog' || 
                role === 'dialog' || 
                role === 'alertdialog' ||
                classes.includes('modal') ||
                classes.includes('dialog') ||
                classes.includes('overlay') ||
                classes.includes('popup') ||
                classes.includes('modaldialogview')) {
                return true;
            }
            current = current.parentElement;
        }
        return false;
    }
    
    // Get depth in DOM tree (useful for nested menus/trees)
    function getDepth(el) {
        let depth = 0;
        let current = el;
        while (current.parentElement) {
            current = current.parentElement;
            depth++;
        }
        return depth;
    }
    
    // Get parent's text for context
    function getParentText(el) {
        const parent = el.parentElement;
        if (!parent) return null;
        const clone = parent.cloneNode(true);
        // Remove the element itself to get surrounding text
        const children = clone.querySelectorAll('*');
        children.forEach(c => c.remove());
        const text = clone.textContent?.trim().slice(0, 50);
        return text || null;
    }
    
    // Build a unique CSS selector for an element
    function buildSelector(el) {
        // Prefer ID
        if (el.id) {
            return '#' + CSS.escape(el.id);
        }
        
        // Try unique class combination
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/).filter(c => c);
            if (classes.length > 0) {
                const selector = el.tagName.toLowerCase() + '.' + classes.map(c => CSS.escape(c)).join('.');
                if (document.querySelectorAll(selector).length === 1) {
                    return selector;
                }
            }
        }
        
        // Try aria-label
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) {
            const selector = `${el.tagName.toLowerCase()}[aria-label="${CSS.escape(ariaLabel)}"]`;
            if (document.querySelectorAll(selector).length === 1) {
                return selector;
            }
        }
        
        // Try text content for buttons/links
        const text = el.textContent?.trim();
        if (text && text.length < 50 && ['A', 'BUTTON', 'SPAN'].includes(el.tagName)) {
            // We'll use :has-text in Playwright
            return `${el.tagName.toLowerCase()}:has-text("${text.slice(0, 30).replace(/"/g, '\\"')}")`;
        }
        
        // Fallback: nth-child path
        let path = [];
        let current = el;
        while (current && current !== document.body) {
            let index = 1;
            let sibling = current.previousElementSibling;
            while (sibling) {
                if (sibling.tagName === current.tagName) index++;
                sibling = sibling.previousElementSibling;
            }
            path.unshift(`${current.tagName.toLowerCase()}:nth-of-type(${index})`);
            current = current.parentElement;
            if (path.length > 5) break;  // Limit depth
        }
        return path.join(' > ');
    }
    
    // Extract info from a single element
    function extractElement(el, inModalContext = false) {
        let text = el.textContent?.trim().slice(0, 100) || '';
        const rect = el.getBoundingClientRect();
        
        // Give meaningful names to empty close buttons
        if (!text && el.classList.contains('close')) {
            text = '[X] Close Modal';
        }
        
        return {
            id: elementId++,
            tag: el.tagName.toLowerCase(),
            selector: buildSelector(el),
            text: text,
            aria_label: el.getAttribute('aria-label'),
            title: el.getAttribute('title'),
            role: el.getAttribute('role'),
            element_id: el.id || null,
            element_class: el.className?.toString().slice(0, 100) || null,
            href: el.href || null,
            input_type: el.type || null,
            placeholder: el.placeholder || null,
            disabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
            visible: isVisible(el),
            in_modal: inModalContext || isInModal(el),
            depth: getDepth(el),
            parent_text: getParentText(el),
            // Bounding box for potential visual reference
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height)
        };
    }
    
    // Interactive element selectors
    const interactiveSelectors = [
        'a[href]',
        'button',
        'input',
        'select',
        'textarea',
        '[role="button"]',
        '[role="link"]',
        '[role="menuitem"]',
        '[role="tab"]',
        '[role="treeitem"]',
        '[role="option"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="switch"]',
        '[role="combobox"]',
        '[role="listbox"]',
        '[onclick]',
        '[tabindex]:not([tabindex="-1"])',
        '.clickable',
        '.btn',
        'li.usercontrol',  // Mitchell-specific tree nodes
        'li.qualifier',    // Mitchell-specific options
        'li.node',         // Mitchell-specific tree nodes
        '.treeNode',       // Tree navigation
        '.menuItem',       // Menu items
        '.nav-link',       // Navigation links
        '.accordion-header', // Accordions
        '[data-toggle]',   // Bootstrap-style toggles
        '[data-action]',   // Custom action elements
        // ShopKeyPro-specific elements
        '.accessItem',     // Quick access panel items (Fluid Capacities, etc.)
        '[id*="Access"]',  // Elements with Access in ID
        '[id*="Quick"]',   // Elements with Quick in ID
        '#quickLinkRegion div[id]',  // Quick link region items
        'span.close',      // ShopKeyPro modal close button (no text, CSS styled X)
        '.modalDialogView .close',  // Modal close buttons
        // Estimate Guide operations - these are h2 elements inside li inside .itemsContainer
        '.itemsContainer li',   // Estimate Guide operation list items
        '.itemsContainer h2',   // Estimate Guide operation headers (clickable)
        '.rightPane li',        // Right pane list items
        // TSB table links - clickable links inside TSB category tables (NO href!)
        '.modalDialogView table a',  // TSB links inside modal tables
        '.modalDialogView table td a',  // TSB title links specifically
        'a.visitedBulletin',   // TSB links that have been visited (no href)
        'a.bulletinItem',      // TSB links (no href)
        '.bulletinListTable a', // Any link in TSB table
        // "See XYZ" links in modals - often no href, just onclick
        '.modalDialogView a',  // Any link inside modal (catches "See Component Location" links)
        'a.clsExtHyperlink',   // "See Component Location" cross-reference links (no href)
        // 1Search result links (no href, no class, just plain <a> in search results container)
        '#searchResultsRegion a',  // Search result links
        '.proDemandResults a',     // Search result links (alternate container)
        // OneView cards (search result detail cards like "Component Connector", "Wiring Diagrams")
        '.oneViewCard',            // OneView result cards
        '[class*="Card"]',         // Any element with Card in class name
        '[class*="card"]',         // Any element with card in class name (lowercase)
        '.resultCard',             // Search result cards
    ];
    
    // Track processed elements to avoid duplicates
    const processed = new Set();
    
    // First, extract from main document
    const mainSelector = interactiveSelectors.join(', ');
    document.querySelectorAll(mainSelector).forEach(el => {
        if (isVisible(el) && !processed.has(el)) {
            processed.add(el);
            results.push(extractElement(el, false));
        }
    });
    
    // Then, check for modals/dialogs that might be open
    // This ensures modal elements are marked with in_modal=true
    const modalSelectors = [
        '.modal',
        '.modalDialogView',  // Mitchell-specific
        '[role="dialog"]',
        '[role="alertdialog"]',
        '.dialog',
        '.popup',
        '.overlay:not(.hidden)'
    ];
    
    modalSelectors.forEach(modalSel => {
        document.querySelectorAll(modalSel).forEach(modal => {
            if (isVisible(modal)) {
                modal.querySelectorAll(mainSelector).forEach(el => {
                    if (isVisible(el) && !processed.has(el)) {
                        processed.add(el);
                        results.push(extractElement(el, true));
                    }
                });
            }
        });
    });
    
    // Check shadow DOM (limited support)
    document.querySelectorAll('*').forEach(el => {
        if (el.shadowRoot) {
            try {
                el.shadowRoot.querySelectorAll(mainSelector).forEach(shadowEl => {
                    if (isVisible(shadowEl) && !processed.has(shadowEl)) {
                        processed.add(shadowEl);
                        const info = extractElement(shadowEl, false);
                        info.in_shadow_dom = true;
                        results.push(info);
                    }
                });
            } catch (e) {
                // Shadow DOM access denied
            }
        }
    });
    
    return results;
}
"""


# JavaScript to get page context (title, URL, visible text summary)
GET_PAGE_CONTEXT_JS = """
() => {
    // Get page title
    const title = document.title || '';
    
    // Get breadcrumb if present
    const breadcrumb = document.querySelector('.breadcrumb, [aria-label="breadcrumb"], .crumb');
    const breadcrumbText = breadcrumb?.textContent?.trim() || '';
    
    // Get main headings
    const headings = [];
    document.querySelectorAll('h1, h2, h3').forEach(h => {
        const text = h.textContent?.trim();
        if (text && text.length < 100) {
            headings.push(text);
        }
    });
    
    // Check for visible SHOPKEYPRO modal (not cookie consent)
    // ShopKeyPro uses .modalDialogView for its modals
    // Ignore cookie consent popups (OneTrust, etc.)
    let hasModal = false;
    let modalTitle = '';
    
    const shopkeyModal = document.querySelector('.modalDialogView');
    if (shopkeyModal && window.getComputedStyle(shopkeyModal).display !== 'none') {
        hasModal = true;
        modalTitle = shopkeyModal.querySelector('.header, h1, h2, .title')?.textContent?.trim() || 'Modal Open';
    }
    
    // Also check for role="dialog" but exclude cookie consent
    if (!hasModal) {
        const dialogs = document.querySelectorAll('[role="dialog"]');
        for (const d of dialogs) {
            const text = d.textContent?.toLowerCase() || '';
            // Skip cookie/privacy dialogs
            if (text.includes('cookie') || text.includes('privacy') || text.includes('consent')) {
                continue;
            }
            if (window.getComputedStyle(d).display !== 'none') {
                hasModal = true;
                modalTitle = d.querySelector('.header, h1, h2, .title')?.textContent?.trim() || '';
                break;
            }
        }
    }
    
    // Get selected vehicle info if visible
    const vehicleInfo = document.querySelector('.vehicle-info, .vehicleDisplay, #vehicleDescription, #vehicleSelectorButton');
    const vehicleText = vehicleInfo?.textContent?.trim() || '';
    
    // Get any error messages
    const errors = [];
    document.querySelectorAll('.error, .alert-danger, .errorMessage, [role="alert"]').forEach(e => {
        const text = e.textContent?.trim();
        if (text) errors.push(text);
    });
    
    // Get tab states
    const tabs = [];
    document.querySelectorAll('[role="tab"], .tab, .nav-tab').forEach(tab => {
        tabs.push({
            text: tab.textContent?.trim(),
            active: tab.classList.contains('active') || tab.getAttribute('aria-selected') === 'true'
        });
    });
    
    return {
        url: window.location.href,
        title: title,
        breadcrumb: breadcrumbText,
        headings: headings.slice(0, 5),
        hasModal: hasModal,
        modalTitle: modalTitle,
        vehicleInfo: vehicleText,
        errors: errors,
        tabs: tabs.slice(0, 10)
    };
}
"""


@dataclass
class PageState:
    """Current state of the page."""
    url: str
    title: str
    breadcrumb: str
    headings: List[str]
    has_modal: bool
    modal_title: str
    vehicle_info: str
    errors: List[str]
    tabs: List[Dict[str, Any]]
    elements: List[ElementInfo]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "breadcrumb": self.breadcrumb,
            "headings": self.headings,
            "has_modal": self.has_modal,
            "modal_title": self.modal_title,
            "vehicle_info": self.vehicle_info,
            "errors": self.errors,
            "tabs": self.tabs,
            "element_count": len(self.elements),
            "elements": [e.to_dict() for e in self.elements]
        }
    
    def to_llm_context(self, max_elements: int = None) -> str:
        """Format page state for LLM consumption. If max_elements is None, show all."""
        lines = []
        
        lines.append(f"=== PAGE STATE ===")
        lines.append(f"URL: {self.url}")
        lines.append(f"Title: {self.title}")
        
        if self.breadcrumb:
            lines.append(f"Breadcrumb: {self.breadcrumb}")
        
        if self.vehicle_info:
            lines.append(f"Vehicle: {self.vehicle_info}")
        
        if self.headings:
            lines.append(f"Headings: {', '.join(self.headings)}")
        
        if self.has_modal:
            lines.append(f"MODAL OPEN: {self.modal_title}")
        
        if self.errors:
            lines.append(f"ERRORS: {', '.join(self.errors)}")
        
        if self.tabs:
            active_tabs = [t['text'] for t in self.tabs if t.get('active')]
            all_tabs = [t['text'] for t in self.tabs]
            lines.append(f"Tabs: {', '.join(all_tabs)}")
            if active_tabs:
                lines.append(f"Active Tab: {', '.join(active_tabs)}")
        
        lines.append("")
        lines.append(f"=== INTERACTIVE ELEMENTS ({len(self.elements)} total) ===")
        
        # Prioritize visible, non-disabled elements
        visible_elements = [e for e in self.elements if e.visible and not e.disabled]
        
        # If modal is open, prioritize modal elements
        if self.has_modal:
            modal_elements = [e for e in visible_elements if e.in_modal]
            other_elements = [e for e in visible_elements if not e.in_modal]
            sorted_elements = modal_elements + other_elements
        else:
            sorted_elements = visible_elements
        
        # Limit elements if max_elements is specified
        elements_to_show = sorted_elements if max_elements is None else sorted_elements[:max_elements]
        
        for elem in elements_to_show:
            # Build a concise description
            parts = [f"[{elem.id}]", elem.tag.upper()]
            
            if elem.text:
                parts.append(f'"{elem.text[:40]}"')
            elif elem.aria_label:
                parts.append(f'aria="{elem.aria_label[:40]}"')
            elif elem.title:
                parts.append(f'title="{elem.title[:40]}"')
            elif elem.placeholder:
                parts.append(f'placeholder="{elem.placeholder[:40]}"')
            
            if elem.element_id:
                parts.append(f'id={elem.element_id}')
            
            if elem.in_modal:
                parts.append("[MODAL]")
            
            if elem.href:
                parts.append(f'href={elem.href[:50]}')
            
            lines.append(" ".join(parts))
        
        if max_elements is not None and len(sorted_elements) > max_elements:
            lines.append(f"... and {len(sorted_elements) - max_elements} more elements")
        
        return "\n".join(lines)


async def extract_interactive_elements(page: Page) -> List[ElementInfo]:
    """
    Extract all interactive elements from the page.
    
    Args:
        page: Playwright Page object
        
    Returns:
        List of ElementInfo objects
    """
    try:
        raw_elements = await page.evaluate(EXTRACT_ELEMENTS_JS)
        
        elements = []
        for raw in raw_elements:
            elem = ElementInfo(
                id=raw.get("id", 0),
                tag=raw.get("tag", ""),
                selector=raw.get("selector", ""),
                text=raw.get("text", ""),
                aria_label=raw.get("aria_label"),
                title=raw.get("title"),
                role=raw.get("role"),
                element_id=raw.get("element_id"),
                element_class=raw.get("element_class"),
                href=raw.get("href"),
                input_type=raw.get("input_type"),
                placeholder=raw.get("placeholder"),
                disabled=raw.get("disabled", False),
                visible=raw.get("visible", True),
                in_modal=raw.get("in_modal", False),
                depth=raw.get("depth", 0),
                parent_text=raw.get("parent_text"),
            )
            elements.append(elem)
        
        log.info(f"Extracted {len(elements)} interactive elements")
        return elements
        
    except Exception as e:
        log.error(f"Failed to extract elements: {e}")
        return []


async def get_page_state(page: Page) -> PageState:
    """
    Get complete page state including context and elements.
    
    Args:
        page: Playwright Page object
        
    Returns:
        PageState object
    """
    try:
        # Get page context
        context = await page.evaluate(GET_PAGE_CONTEXT_JS)
        
        # Get interactive elements
        elements = await extract_interactive_elements(page)
        
        return PageState(
            url=context.get("url", ""),
            title=context.get("title", ""),
            breadcrumb=context.get("breadcrumb", ""),
            headings=context.get("headings", []),
            has_modal=context.get("hasModal", False),
            modal_title=context.get("modalTitle", ""),
            vehicle_info=context.get("vehicleInfo", ""),
            errors=context.get("errors", []),
            tabs=context.get("tabs", []),
            elements=elements,
        )
        
    except Exception as e:
        log.error(f"Failed to get page state: {e}")
        return PageState(
            url="", title="", breadcrumb="", headings=[],
            has_modal=False, modal_title="", vehicle_info="",
            errors=[str(e)], tabs=[], elements=[]
        )


async def get_visible_text(page: Page, max_length: int = 10000) -> str:
    """
    Extract visible text from the page for data extraction.
    
    Args:
        page: Playwright Page object
        max_length: Maximum text length to return
        
    Returns:
        Visible text content
    """
    try:
        # Get text from main content area if identifiable, else body
        text = await page.evaluate("""
        () => {
            // Try to find main content area
            const contentSelectors = [
                '.rightPane',        // Estimate Guide parts/labor data table
                '.content',
                '.main-content', 
                '#content',
                'main',
                '.article-content',
                '.modalDialogView',  // Mitchell modal content
                '.dataView',         // Mitchell data views
                '.resultsContainer'
            ];
            
            for (const sel of contentSelectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent?.trim()) {
                    return el.textContent;
                }
            }
            
            // Fallback to body
            return document.body.textContent;
        }
        """)
        
        # Clean up whitespace
        text = " ".join(text.split())
        return text[:max_length]
        
    except Exception as e:
        log.error(f"Failed to get visible text: {e}")
        return ""
