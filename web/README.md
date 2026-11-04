# ai-os web console

React, TypeScript, Tailwind CSS and shadcn/ui-style components (Radix), built with
Vite. ai-os serves the build: the page at `/`, everything else under `/static`, the
JSON API under `/api` (see `aios/web/`).

The Docker image builds it (the `web` stage in the Dockerfile), so rebuilding the
image deploys it.

## Working on it

```sh
cd web && npm ci && npm run build   # typecheck + build
```

`npm run dev` serves it with hot reload and sends `/api` to an ai-os on port 8099,
e.g. one started locally with `web.auth.mode: dev` (see the main README). Commit
`package-lock.json` when dependencies change: the image installs with `npm ci`.

If the repo sits in a synced folder (Google Drive and the like), `node_modules` breaks
there: work on a copy (`rsync -a --exclude node_modules --exclude dist web/ /tmp/aios-web/`)
and copy the changed files back.

- `src/components/ui/` are shadcn/ui components, kept close to upstream.
- `src/pages/` is one file per page; `src/pages/chat/` is the chat, whose live
  updates are `use-live-conversation.ts`.
- `src/lib/api.ts` holds the API types; keep them in step with `aios/web/routes/`.
