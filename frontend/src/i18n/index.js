// Minimal i18n: a dictionary per language in this folder, looked up by t(key, params).
// The active language comes from <html lang>, which FastAPI sets from APP_LANGUAGE.

export const DEFAULT_LANG = 'vi'

// Every sibling <code>.js file is a dictionary; adding one registers the language.
const modules = import.meta.glob('./!(index).js', { eager: true })
const dictionaries = Object.fromEntries(
  Object.entries(modules).map(([path, mod]) => [path.slice(2, -3), mod.default]),
)

const requested = typeof document !== 'undefined' ? document.documentElement.lang : ''
export const lang = dictionaries[requested] ? requested : DEFAULT_LANG
const dict = dictionaries[lang]

export function t(key, params) {
  const text = dict[key]
  if (text === undefined) {
    if (import.meta.env.DEV) console.warn(`[i18n] missing key "${key}" for "${lang}"`)
    return key
  }
  return params ? text.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`) : text
}

// Like t(), but falls back to the raw value for values the dictionary does not know
// (e.g. an enum the API adds later).
export function label(prefix, value) {
  return dict[`${prefix}.${value}`] ?? dict[`${prefix}.${String(value).toLowerCase()}`] ?? value
}
