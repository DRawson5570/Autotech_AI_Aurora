from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import Page

log = logging.getLogger(__name__)


# We keep discovery intentionally conservative: it *suggests* selectors and saves them,
# but doesn't attempt any bot-evasion or bypassing.


@dataclass
class DiscoveredSelectors:
    sel_year_dropdown: str = ""
    sel_make_dropdown: str = ""
    sel_model_dropdown: str = ""
    sel_engine_dropdown: str = ""
    sel_vehicle_apply_button: str = ""

    sel_search_input: str = ""
    sel_search_submit: str = ""
    sel_results_container: str = ""

    sel_content_frame: str = ""
    sel_tech_content_root: str = ""
    sel_breadcrumb: str = ""
    sel_page_title: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__.keys()}  # type: ignore[attr-defined]


def load_profile(path: str) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_profile(path: str, data: dict[str, str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


async def discover_selectors(page: Page) -> DiscoveredSelectors:
    """Attempt to discover key UI selectors from the current page DOM.

    This is heuristic and portal/layout dependent. It works best when run headful once.
    """

    # The script runs in the page context and returns candidate CSS selectors.
    js = r"""
() => {
  const q = (sel, root=document) => root.querySelector(sel);
  const qa = (sel, root=document) => Array.from(root.querySelectorAll(sel));

  const norm = (s) => (s || '').toLowerCase().replace(/\s+/g,' ').trim();

  const cssPath = (el) => {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) return `#${CSS.escape(el.id)}`;
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 6) {
      let part = el.nodeName.toLowerCase();
      if (el.classList && el.classList.length) {
        // Keep only a couple classes to reduce brittleness
        const cls = Array.from(el.classList).slice(0,2).map(c => `.${CSS.escape(c)}`).join('');
        part += cls;
      }
      const parent = el.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.nodeName === el.nodeName);
        if (siblings.length > 1) {
          const idx = siblings.indexOf(el) + 1;
          part += `:nth-of-type(${idx})`;
        }
      }
      parts.unshift(part);
      el = parent;
    }
    return parts.join(' > ');
  };

  const labelFor = (input) => {
    if (!input) return '';
    const id = input.getAttribute('id');
    if (id) {
      const lbl = q(`label[for="${CSS.escape(id)}"]`);
      if (lbl) return norm(lbl.textContent);
    }
    // sometimes label wraps the input
    const wrapped = input.closest('label');
    if (wrapped) return norm(wrapped.textContent);
    return '';
  };

  const findSelectByLabel = (keywords) => {
    const selects = qa('select');
    const scored = selects.map(sel => {
      const text = norm(labelFor(sel) + ' ' + (sel.getAttribute('aria-label')||'') + ' ' + (sel.getAttribute('name')||''));
      let score = 0;
      for (const kw of keywords) {
        if (text.includes(kw)) score += 3;
      }
      // bonus if it has lots of options
      score += Math.min(2, Math.floor((sel.options?.length || 0) / 10));
      return {sel, score, text};
    }).filter(x => x.score > 0).sort((a,b)=>b.score-a.score);
    return scored.length ? cssPath(scored[0].sel) : '';
  };

  const findInputBy = (keywords) => {
    const inputs = qa('input[type="search"], input[type="text"], input:not([type])');
    const scored = inputs.map(inp => {
      const blob = norm(
        (inp.getAttribute('placeholder')||'') + ' ' +
        (inp.getAttribute('aria-label')||'') + ' ' +
        (inp.getAttribute('name')||'') + ' ' +
        labelFor(inp)
      );
      let score = 0;
      for (const kw of keywords) {
        if (blob.includes(kw)) score += 3;
      }
      return {inp, score, blob};
    }).filter(x => x.score > 0).sort((a,b)=>b.score-a.score);
    return scored.length ? cssPath(scored[0].inp) : '';
  };

  const findButtonNear = (inputSel) => {
    const inp = q(inputSel);
    if (!inp) return '';
    const container = inp.closest('form') || inp.parentElement || document.body;
    const btns = qa('button, input[type="submit"]', container);
    const scored = btns.map(b => {
      const t = norm(b.textContent || b.getAttribute('value') || b.getAttribute('aria-label') || '');
      let score = 0;
      if (t.includes('search')) score += 5;
      if (t.includes('go')) score += 2;
      if (t.includes('submit')) score += 2;
      return {b, score, t};
    }).sort((a,b)=>b.score-a.score);
    return scored.length && scored[0].score > 0 ? cssPath(scored[0].b) : '';
  };

  const largestIframe = () => {
    const iframes = qa('iframe');
    if (!iframes.length) return '';
    const scored = iframes.map(f => {
      const r = f.getBoundingClientRect();
      const area = Math.max(0, r.width) * Math.max(0, r.height);
      return {f, area};
    }).sort((a,b)=>b.area-a.area);
    return scored[0].area > 10000 ? cssPath(scored[0].f) : '';
  };

  const resultsContainer = () => {
    // heuristic: container with many links and significant text
    const candidates = qa('div, section, main, article').slice(0, 400);
    const scored = candidates.map(el => {
      const links = el.querySelectorAll('a').length;
      const textLen = (el.innerText || '').trim().length;
      let score = 0;
      if (links >= 3) score += 3;
      if (links >= 10) score += 3;
      if (textLen > 200) score += 2;
      return {el, score, links, textLen};
    }).filter(x => x.score >= 5).sort((a,b)=>b.score-a.score);
    return scored.length ? cssPath(scored[0].el) : '';
  };

  const techRoot = () => {
    // pick a large content-looking node
    const candidates = qa('main, article, div').slice(0, 600);
    const scored = candidates.map(el => {
      const textLen = (el.innerText || '').trim().length;
      const links = el.querySelectorAll('a').length;
      const imgs = el.querySelectorAll('img,svg').length;
      let score = 0;
      if (textLen > 500) score += 5;
      if (textLen > 1500) score += 3;
      if (imgs > 0) score += 1;
      if (links > 5) score += 1;
      return {el, score, textLen};
    }).filter(x => x.score >= 6).sort((a,b)=>b.score-a.score);
    return scored.length ? cssPath(scored[0].el) : '';
  };

  const out = {
    sel_year_dropdown: findSelectByLabel(['year']),
    sel_make_dropdown: findSelectByLabel(['make']),
    sel_model_dropdown: findSelectByLabel(['model']),
    sel_engine_dropdown: findSelectByLabel(['engine', 'motor']),
    sel_vehicle_apply_button: '',

    sel_search_input: findInputBy(['search', 'keyword']),
    sel_search_submit: '',
    sel_results_container: resultsContainer(),

    sel_content_frame: largestIframe(),
    sel_tech_content_root: '',
    sel_breadcrumb: '',
    sel_page_title: '',
  };

  if (out.sel_search_input) {
    out.sel_search_submit = findButtonNear(out.sel_search_input);
  }

  // For apply button, look for a button with Apply/OK/Go near vehicle selects
  const selects = [out.sel_year_dropdown, out.sel_make_dropdown, out.sel_model_dropdown, out.sel_engine_dropdown].filter(Boolean);
  if (selects.length) {
    const first = q(selects[0]);
    const root = first ? (first.closest('form') || first.parentElement || document.body) : document.body;
    const btns = qa('button, input[type="submit"]', root);
    const scored = btns.map(b => {
      const t = norm(b.textContent || b.getAttribute('value') || b.getAttribute('aria-label') || '');
      let score = 0;
      if (t.includes('apply')) score += 5;
      if (t === 'ok') score += 3;
      if (t.includes('go')) score += 2;
      if (t.includes('set')) score += 1;
      return {b, score};
    }).sort((a,b)=>b.score-a.score);
    if (scored.length && scored[0].score > 0) out.sel_vehicle_apply_button = cssPath(scored[0].b);
  }

  // If no iframe, pick tech root in main doc; iframe content root is discovered later by python if needed.
  out.sel_tech_content_root = techRoot();

  return out;
}
"""

    raw: dict[str, Any] = await page.evaluate(js)

    d = DiscoveredSelectors()
    for k in d.to_dict().keys():
        v = raw.get(k)
        if isinstance(v, str):
            setattr(d, k, v)

    log.info("Discovered selectors: %s", {k: v for k, v in d.to_dict().items() if v})
    return d


def merge_profile(existing: dict[str, str], discovered: DiscoveredSelectors) -> dict[str, str]:
    merged = dict(existing)
    for k, v in discovered.to_dict().items():
        if v and not merged.get(k):
            merged[k] = v
    return merged
