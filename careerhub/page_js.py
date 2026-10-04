"""page_js module of Career Hub. See MAP.md for what lives where."""


COLLECT_JS = r"""
() => {
  window.__afid = window.__afid || 0;
  const T = el => (el ? (el.innerText || el.textContent || '') : '').replace(/\s+/g, ' ').trim();
  const shown = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const usable = el => shown(el) || [...(el.labels || [])].some(shown) ||
                    (el.type === 'file' && el.parentElement && shown(el.parentElement));
  const byIds = ids => ids.split(/\s+/).map(i => T(document.getElementById(i))).join(' ').trim();
  const ownLabel = el => {
    let t = el.getAttribute('aria-label'); if (t && t.trim()) return t.trim();
    const lb = el.getAttribute('aria-labelledby'); if (lb) { t = byIds(lb); if (t) return t; }
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l && T(l)) return T(l); }
    const pl = el.closest('label'); if (pl && T(pl)) return T(pl);
    return '';
  };
  const groupLabel = el => {
    const g = el.closest('fieldset, [role=radiogroup], [role=group], [data-automation-id^="formField"]');
    if (!g) return '';
    let t = g.getAttribute('aria-label'); if (t) return t.trim();
    const lb = g.getAttribute('aria-labelledby'); if (lb) { t = byIds(lb); if (t) return t; }
    const lg = g.querySelector('legend, label'); return lg ? T(lg) : '';
  };
  // Text shown next to a field that is not tied to it in the HTML (e.g. Keka: <div>Company Name</div><input placeholder="Keka">)
  const HINT = /\b(max(imum)?\s+(file\s+)?size|\d+\s*(mb|kb)\b|accepted|allowed|supported formats?|drag|drop|browse)/i;   // a size / format hint, not a field name
  const visualLabel = el => {
    let node = el;
    for (let depth = 0; depth < 4 && node; depth++) {
      const p = node.parentElement; if (!p) break;
      if (depth > 0 && p.querySelectorAll('input:not([type=hidden]), select, textarea').length > 1) break;   // stay in this field's own block
      const cands = [...p.querySelectorAll('label, legend, span, div, p, h3, h4, h5, h6, strong, b')]
        .filter(c => !c.contains(el) && !c.querySelector('input, select, textarea, button') &&
                     (c.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING));
      for (let i = cands.length - 1; i >= 0; i--) { const t = T(cands[i]); if (t && /[A-Za-z]{2}/.test(t) && t.length <= 90 && !HINT.test(t) && shown(cands[i])) return t; }
      node = p;
    }
    return '';
  };
  // Text right after a checkbox/radio (e.g. "By applying, you accept the Privacy Policy...")
  const followText = el => {
    let n = el.nextSibling, out = '';
    for (let i = 0; i < 4 && n && out.length < 400; i++, n = n.nextSibling) {
      if (n.nodeType === 1 && n.matches('input, select, textarea, button')) break;
      out += ' ' + (n.nodeType === 3 ? n.textContent : T(n));
    }
    return out.replace(/\s+/g, ' ').trim();
  };
  const labelOf = el => {
    let own = ownLabel(el); const grp = groupLabel(el);
    if (!own && (el.type === 'checkbox' || el.type === 'radio')) own = followText(el);
    if (!own) own = grp;
    else if (grp && own.length < 12 && !grp.includes(own)) own = grp + ' - ' + own;   // e.g. "From - Month"
    if (!own) own = visualLabel(el);
    if (own) return own;
    el.dataset.afweak = '1';                    // only a placeholder / field name: an example, not a real label
    return el.placeholder || el.name || el.getAttribute('data-automation-id') || el.id || '';
  };
  const isReq = (el, label) => el.required || el.getAttribute('aria-required') === 'true' || label.includes('*');
  const tag = el => { if (!el.dataset.afid) el.dataset.afid = String(++window.__afid); return el.dataset.afid; };
  const EMPTY = /^(select|choose|--|please select)/i;

  // LinkedIn Easy Apply & similar: only look inside the open modal
  const dlg = [...document.querySelectorAll('[role=dialog], [aria-modal=true]')]
      .find(d => shown(d) && d.querySelector('input, select, textarea'));
  const root = dlg || document;
  const out = [], radios = {};

  root.querySelectorAll('input, textarea, select, button[aria-haspopup="listbox"]').forEach(el => {
    if (el.disabled || !usable(el) || el.closest('header, nav')) return;
    const type = (el.type || '').toLowerCase();

    if (el.tagName === 'BUTTON') {                                   // Workday custom dropdown
      const label = labelOf(el), val = T(el);
      out.push({id: tag(el), kind: 'dropdown', label, value: EMPTY.test(val) ? '' : val, required: isReq(el, label)});
      return;
    }
    if (['hidden', 'submit', 'button', 'reset', 'image', 'search', 'password'].includes(type)) return;
    const picker = /datepicker|datetimepicker|flatpickr|date-picker/i.test(el.className || '') || el.hasAttribute('data-provide');
    if (el.readOnly && type !== 'file' && !picker) return;      // read-only date pickers are filled by script

    if (type === 'radio') {
      const key = el.name || groupLabel(el) || 'radio';
      const g = radios[key] || (radios[key] = {id: 'rg_' + key, kind: 'radio', label: groupLabel(el) || key,
                                                 value: '', options: [], required: false});
      const ol = ownLabel(el) || el.value;
      g.options.push({id: tag(el), label: ol});
      if (el.checked) g.value = ol;
      g.required = g.required || isReq(el, g.label);
      return;
    }
    if (type === 'checkbox') {
      const label = labelOf(el);
      out.push({id: tag(el), kind: 'checkbox', label, value: el.checked ? 'yes' : '', required: isReq(el, label)});
      return;
    }
    if (type === 'file') {
      const label = labelOf(el) || 'file upload';
      out.push({id: tag(el), kind: 'file', label, value: el.files && el.files.length ? el.files[0].name : '',
                required: isReq(el, label)});
      return;
    }
    if (el.tagName === 'SELECT') {
      const label = labelOf(el);
      const opts = [...el.options].filter(o => o.value !== '' && !EMPTY.test(o.text.trim())).map(o => o.text.trim());
      const cur = el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
      const value = cur && cur.value !== '' && !EMPTY.test(cur.text.trim()) ? cur.text.trim() : '';
      out.push({id: tag(el), kind: 'select', label, value, options: opts, required: isReq(el, label)});
      return;
    }
    const label = labelOf(el);
    const combo = el.getAttribute('role') === 'combobox' || el.getAttribute('aria-autocomplete') === 'list'
                  || el.dataset.automationId === 'searchBox';
    out.push({id: tag(el), kind: combo ? 'combo' : (el.tagName === 'TEXTAREA' ? 'textarea' : 'text'),
              label, value: el.value || '', required: isReq(el, label), auto: el.dataset.automationId || '', itype: type, picker: !!picker});
  });
  Object.values(radios).forEach(g => out.push(g));
  out.forEach(o => {
    const el = document.querySelector(`[data-afid="${o.id}"]`);
    o.weak = !!(el && el.dataset.afweak);
    const nm = el ? (el.name || el.id || '') : '';     // field name helps tell apart boxes sharing one label ('Mobile')
    o.nm = /[a-z]/i.test(nm) && nm.length <= 40 && !/[0-9a-f]{12,}/i.test(nm) ? nm : '';
    o.captcha = /captcha|security code|verification code/i.test(o.label + ' ' + (el ? (el.name || '') + ' ' + (el.id || '') + ' ' + (el.placeholder || '') : ''));
  });
  return out;
}
"""


BUTTONS_JS = r"""
(sel) => {
  const shown = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  window.__afb = window.__afb || 0;
  return [...document.querySelectorAll(sel || 'button, input[type=submit], [role=button]')]
    .filter(b => shown(b) && !b.disabled && b.getAttribute('aria-disabled') !== 'true')
    .map(b => { if (!b.dataset.afbtn) b.dataset.afbtn = String(++window.__afb);
      return {id: b.dataset.afbtn, auto: b.dataset.automationId || '',
              text: (b.innerText || b.value || b.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim()}; });
}
"""


TITLE_JS = r"""
() => {
  const shown = e => e.getClientRects().length > 0;
  const dlg = [...document.querySelectorAll('[role=dialog], [aria-modal=true]')].find(shown);
  const root = dlg || document;
  const h = [...root.querySelectorAll('[data-automation-id="pageHeaderTitle"], h1, h2, h3')]
              .find(e => shown(e) && e.innerText.trim());
  const n = root.querySelectorAll('input, select, textarea').length;
  return {title: h ? h.innerText.trim().slice(0, 80) : '', count: n};
}
"""


ERRORS_JS = r"""
() => {
  const shown = e => e.getClientRects().length > 0;
  const sel = '[role=alert], [data-automation-id="errorMessage"], [data-automation-id="inputAlert"], ' +
              '.artdeco-inline-feedback--error, .error-message, .field-error, .error';
  return [...new Set([...document.querySelectorAll(sel)].filter(shown)
          .map(e => e.innerText.replace(/\s+/g, ' ').trim()).filter(t => t && t.length < 300))];
}
"""


JOB_BADGE_JS = r"""
(() => { if (window.top !== window) return;
  const add = () => { if (document.getElementById('__af_badge')) return;
    const d = document.createElement('div'); d.id = '__af_badge';
    d.textContent = '● Career Hub is working in this window';
    d.style.cssText = 'position:fixed;left:12px;bottom:12px;z-index:2147483647;background:#4f46e5;color:#fff;' +
      'font:600 12px -apple-system,Segoe UI,sans-serif;padding:6px 11px;border-radius:99px;pointer-events:none;' +
      'opacity:.92;box-shadow:0 2px 8px rgba(0,0,0,.25)';
    (document.body || document.documentElement).appendChild(d); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
"""
