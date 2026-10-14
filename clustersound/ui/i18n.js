// Interface language. English is the source language: the English text itself is the key, so
// t('Settings') reads naturally in the code and needs no catalog entry in English. Other languages
// map English text to their translation in locales/<lang>.js (strict JSON after "export default",
// so tests can read it). The language is chosen in Settings › General and applied at startup.
import it from './locales/it.js';

export const LANGUAGES = { en: 'English', it: 'Italiano' };
const CATALOGS = { en: {}, it };

let lang = 'en';
const missing = new Set();

export function setLang(code) {
  lang = CATALOGS[code] ? code : 'en';
  document.documentElement.lang = lang;
}

export const getLang = () => lang;

/** Translate English text; {name} placeholders are filled from vars. */
export function t(text, vars) {
  if (!text) return text ?? '';
  let s = CATALOGS[lang][text];
  if (s === undefined) {
    s = text;
    if (lang !== 'en' && !missing.has(text)) { missing.add(text); console.warn(`[i18n] missing ${lang}:`, text); }
  }
  return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s;
}

/** Translate the static markup: data-i18n (text), data-i18n-html, -title, -placeholder, -label. */
export function applyI18n(root = document) {
  for (const el of root.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  for (const el of root.querySelectorAll('[data-i18n-html]')) el.innerHTML = t(el.dataset.i18nHtml);
  for (const attr of ['title', 'placeholder', 'label']) {
    const data = `data-i18n-${attr}`;
    for (const el of root.querySelectorAll(`[${data}]`)) el.setAttribute(attr, t(el.getAttribute(data)));
  }
}
