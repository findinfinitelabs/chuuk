---
name: react-typescript-frontend
description: Patterns for the Chuuk Dictionary React + TypeScript frontend — Vite, Mantine v8, React 19, React Router v7, axios with cookie sessions, and permission-gated routing. Use when adding pages, wiring API calls, modifying navigation, or extending the user/auth context.
---

# React TypeScript Frontend

Single Vite app under [`frontend/`](../../../frontend), built into `frontend/dist` and served by the Flask container in production (no Static Web Apps). React 19, TypeScript ~5.9, Mantine 8.3.x, React Router 7.

## Stack reality check

From [frontend/package.json](../../../frontend/package.json):
- `react` / `react-dom` 19.2.x
- `@mantine/core` 8.3.x + `@mantine/hooks`, `@mantine/dates`, `@mantine/dropzone`, `@mantine/modals`, `@mantine/notifications`, `@mantine/tiptap`
- `@tabler/icons-react` 3.x
- `react-router-dom` 7.10.x
- `axios` 1.13.x
- `vite` 7.x, `typescript` ~5.9, `eslint` 9 + `typescript-eslint` 8

There is **no** path-alias setup (no `@/` imports), and **no** `frontend/src/api/` directory. API calls use `axios` directly with relative URLs (the Vite dev server proxies `/api` to the Flask backend; production serves both from the same origin).

## Bootstrap layout

```
frontend/src/
  main.tsx           # createRoot, BrowserRouter, MantineProvider styles imports
  App.tsx            # Auth state, AppShell, route table, permission gating
  App.css            # Global app-shell layout
  index.css          # Resets / base typography
  theme.ts           # Mantine theme (violet primary, system font stack)
  contexts/
    UserContext.tsx  # Provides { user, permissions, hasPermission }
  hooks/
    useUserCache.ts  # localStorage scoped per user_email
  components/
    Footer.tsx
    GrammarLearning.tsx
  pages/             # All pages — see route map below
```

`BrowserRouter` lives in [`main.tsx`](../../../frontend/src/main.tsx), **not** in `App.tsx`. Mantine CSS imports must come **before** `index.css` to keep cascade correct.

## Route map (current)

From [`App.tsx`](../../../frontend/src/App.tsx#L429):

| Path | Component | Permission |
|---|---|---|
| `/` | `Home` | `home` |
| `/lookup` | `Lookup` | `lookup` |
| `/translate` | `Translate` | `translate` |
| `/sentences` | `Sentences` | `sentences` |
| `/article-analysis` | `ArticleAnalysis` | `article_analysis` |
| `/verbs` | `Verbs` | `verbs` |
| `/database` | `Database` | `database` |
| `/publications` | `Publications` | `publications` |
| `/publications/new` | `NewPublication` | `publications` |
| `/publications/:id` | `PublicationDetail` | `publications` |
| `/translation-game` | `TranslationGame` | `translation_game` |
| `/grammar` | `Grammar` | `grammar` |
| `/compose` | `Compose` | `compose` |
| `/admin/users` | `AdminUsers` | `admin` |
| `/login` | `Login` | (public) |

When adding a page: add the file under `frontend/src/pages/`, add the import + `<Route>` in `App.tsx`, add a `<NavLink>` wrapped with `hasPermission(...)`, and add the corresponding key to the backend `ROLE_PERMISSIONS` map.

## Auth wiring

`App.tsx` calls `GET /api/auth/status` on mount ([App.tsx](../../../frontend/src/App.tsx#L88)) and stores `{ user, permissions }` in local state, broadcasting via `UserContext`. Login flow:

```ts
// Login.tsx posts to /api/auth/login or /api/auth/magic-link
onLoginSuccess({ user, permissions })  // sets state, navigate('/')
```

The contract `{ user: User, permissions: string[] }` is fixed — keep it stable when changing the login page.

Page-view tracking is fire-and-forget: every `location.pathname` change posts to `/api/auth/track-page` ([App.tsx](../../../frontend/src/App.tsx#L74)).

## Mantine usage

Theme: [`theme.ts`](../../../frontend/src/theme.ts) sets `primaryColor: 'violet'`, system-font stack, `defaultRadius: 'md'`, `autoContrast: true`. The app is **light-oriented by default** — there's no dark-mode toggle wired up despite the loading screen using `#1a1b1e`.

Use Mantine props (`p="md"`, `c="violet.7"`, etc.) over hand-written CSS when possible. Page-specific styles go in CSS Modules co-located with the page (e.g. [`Compose.module.css`](../../../frontend/src/pages/Compose.module.css), [`Sentences.module.css`](../../../frontend/src/pages/Sentences.module.css)). Global app-shell styling lives in [`App.css`](../../../frontend/src/App.css).

`<MantineProvider theme={chuukTheme}>` wraps everything in `App.tsx` and is also wrapped around the loading + login states — don't drop it from those branches.

## Async / data patterns

- Use raw `axios` with relative paths. The session cookie is sent automatically (same-origin).
- For SSE (e.g. publication processing), use `EventSource` directly — see [`PublicationDetail.tsx`](../../../frontend/src/pages/PublicationDetail.tsx#L123).
- For per-user persistence (UI state, recent searches), prefer the [`useUserCache`](../../../frontend/src/hooks/useUserCache.ts) hook — it namespaces `localStorage` by `user_email` so two accounts on the same device don't collide.
- No global state library; lift state into `App` or use React context. Don't introduce Redux/Zustand without a real reason.
- File uploads use `@mantine/dropzone`. The `accept` list must align with backend `ALLOWED_EXTENSIONS` ([app.py](../../../app.py#L248)).

## Build & dev

```bash
cd frontend
npm install
npm run dev      # Vite on :5173, proxies /api → :5000
npm run build    # tsc -b && vite build → frontend/dist
npm run lint
```

The full-stack dev script [`dev-start.sh`](../../../dev-start.sh) starts both Flask and Vite.

## TypeScript tips

- `tsconfig.app.json` is `strict`. Don't widen it.
- API response shapes are usually inlined as local `interface`s in the consuming page — there's no shared `types/` directory yet. If a shape is reused in 3+ places, factor it to a `frontend/src/types.ts`.
- `react-router-dom` 7 still re-exports the v6 hooks (`useNavigate`, `useLocation`, `Routes`, `Route`). Don't reach for the data-router APIs — the app uses the classic `<Routes>` declaration in `App.tsx`.

## Pitfalls

- The loading-state background is hard-coded `#1a1b1e` — visible flash on first paint. If this matters, move it into the theme.
- `axios` 1.13 defaults `withCredentials` to false, but cookies work because we're same-origin in prod. If you ever introduce a separate frontend host, you must enable `axios.defaults.withCredentials = true` AND configure CORS on Flask.
- Don't `import 'axios'` and add interceptors that transform error shapes globally — pages currently `try/catch` their own errors and any rewrite would have to be applied site-wide.
- Mantine v8 changed several prop names from v7 (e.g. `position` → `justify`). When porting external snippets, double-check.
