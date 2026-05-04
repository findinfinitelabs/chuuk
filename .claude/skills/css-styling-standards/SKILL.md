---
name: css-styling-standards
description: Styling conventions for the Chuuk Dictionary frontend — Mantine v8 theme, CSS Modules per page, global app-shell CSS, multilingual / accented-character considerations. Use when adding or modifying styles in `frontend/src/`.
---

# CSS Styling Standards

The frontend uses **Mantine v8** primitives + **CSS Modules** for page-local styling + a small global stylesheet. There is no Tailwind, no styled-components, no BEM. Don't introduce one.

## Style architecture

| Layer | File(s) | Purpose |
|---|---|---|
| Mantine reset & component CSS | imported in [`main.tsx`](../../../frontend/src/main.tsx) | base reset, Mantine component styling |
| App-shell layout | [`frontend/src/App.css`](../../../frontend/src/App.css) | header, navbar, content frame |
| Global typography / overrides | [`frontend/src/index.css`](../../../frontend/src/index.css) | body font, link defaults |
| Theme tokens | [`frontend/src/theme.ts`](../../../frontend/src/theme.ts) | colors, radii, font stacks |
| Page-local styles | `frontend/src/pages/<Page>.module.css` | scoped to one page |

CSS Module files in use: `Compose.module.css`, `Grammar.module.css`, `Sentences.module.css`, `Verbs.module.css`. Plain `.css` (not modules) is used for older pages: `Database.css`, `Login.css`, `PublicationDetail.css`, `TranslationGame.css`. **Prefer Modules for any new page.**

## Mantine theme (current)

[`theme.ts`](../../../frontend/src/theme.ts) — keep changes here, not scattered in components:

- `primaryColor: 'violet'` (custom 10-shade palette).
- Secondary palette `ocean` (also 10 shades).
- `primaryShade: { light: 6, dark: 8 }`.
- `fontFamily`: native system stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", ...`) — explicitly **not** Noto. Don't switch.
- `headings.fontFamily`: same system stack.
- `defaultRadius: 'md'`, `cursorType: 'pointer'`, `autoContrast: true`, `luminanceThreshold: 0.3`.

Color references in components should use Mantine tokens (`c="violet.7"`, `bg="gray.0"`) so theme changes propagate.

## App is light-oriented

Despite the loading screen using `#1a1b1e`, there is no dark-mode toggle and no `colorScheme: 'dark'` configuration. The shipped UI is light. Don't author dark-first overrides unless we add a real toggle.

## Mantine vs CSS — when to use what

- **Spacing, layout, color, typography, radii, shadows:** Mantine props (`p`, `m`, `gap`, `c`, `bg`, `radius`, `shadow`).
- **Page-specific composition (a 3-column dictionary grid, a verb conjugation table):** CSS Modules.
- **App-shell, header, nav:** [`App.css`](../../../frontend/src/App.css). Use class names already wired into `<AppShell classNames={{ header: 'app-header', navbar: 'app-navbar' }}>`.
- **Inline `style={{ ... }}`:** acceptable for one-off dynamic values; reach for a Module if it grows past ~3 declarations.

## Multilingual / accented-character rules

- The native font stack renders Chuukese accents (`á é í ó ú`, `ā ē ī ō ū`) without extra config.
- Don't `text-transform: uppercase` Chuukese strings — it strips diacritics on some platforms. If you need visual emphasis, use weight/color.
- Word-break: Chuukese words are short; avoid `word-break: break-all` which breaks accent ligatures. Use `overflow-wrap: anywhere` only as a last resort on tight columns.
- For dictionary entries, monospace looks bad — stick with the proportional system stack.

## Responsive breakpoints

Use Mantine's defaults via the `visibleFrom` / `hiddenFrom` props or `theme.breakpoints` rather than hand-rolled media queries. Existing custom breakpoints in [`App.css`](../../../frontend/src/App.css#L178) match Mantine's `sm` (`48em`) — keep alignment if you add new ones.

## Accessibility

- Aim for WCAG AA. `autoContrast: true` plus `luminanceThreshold: 0.3` handles most text-on-color cases automatically.
- Don't disable focus outlines globally. If they're ugly on a custom button, restyle them, don't hide them.
- All interactive elements get a real `<button>` or `<a>` (Mantine components do this by default).

## Adding a new page's styles

```tsx
// MyPage.tsx
import classes from './MyPage.module.css';
<div className={classes.grid}>...</div>
```

```css
/* MyPage.module.css */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--mantine-spacing-md);
}
```

Use Mantine CSS variables (`--mantine-color-*`, `--mantine-spacing-*`, `--mantine-radius-*`) inside Module files instead of hard-coded values — they re-theme automatically.

## Pitfalls

- Loading the Mantine CSS imports **after** `index.css` reorders the cascade and breaks several components — keep the order in [`main.tsx`](../../../frontend/src/main.tsx).
- `@mantine/notifications` and `@mantine/dropzone` need their own CSS imports; both are already wired up. Adding `@mantine/charts` (or any other Mantine sub-package) requires adding its `styles.css` import too.
- Don't import a CSS Module from a non-page component without prefixing class names — names get hashed but `:global` leaks if used carelessly.
- `ModalsProvider` is **not** currently mounted in `main.tsx`. If you start using `@mantine/modals`'s imperative API (`modals.open(...)`), wire the provider first.
