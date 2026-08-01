# Arena Per-Player Thinking Cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a session-only per-player thinking cap (ms, default 10000) on the `/arena` Set up game screen and pass each loaded model’s budget into `predict`.

**Architecture:** Keep tournament time controls unchanged. Arena holds two React state values (`moveTimeLimitMsA` / `moveTimeLimitMsB`). Each `ModelLoader` renders a number input. `playModelMove` takes the active slot’s limit and calls `model.predict(history, legalMoves, moveTimeLimitMs)`. Align `DEFAULT_MOVE_TIME_LIMIT_MS` in `model.ts` to `10_000` so any fallback matches the UI. Contract tests follow the existing source-read style in `site/tests/rendered-html.test.mjs`.

**Tech Stack:** Next.js client component (`arena-client.tsx`), existing worker model bridge (`model.ts`), Node test runner (`node --test`), CSS in `globals.css`.

## Global Constraints

- Default thinking cap: `10000` ms per player slot.
- UI units: milliseconds; range `1`–`600000` (same ceiling as tournament create).
- Session-only state: no `localStorage`, no share-URL params, no PGN headers.
- Per-player controls on each `ModelLoader` card.
- Human moves ignore the cap; only loaded models receive `moveTimeLimitMs`.
- Do not change tournament create/run, grace factor `1.25`, or package interface.
- Prefer existing form patterns (`create-tournament-form.tsx` number inputs).
- PR must include before/after screenshots of the Set up game screen.
- Work on a feature branch; open a PR (do not push straight to `main` for this deliverable).
- Skip project-wide unrelated refactors. Do not run full `npm test` after every micro-step if a narrower command exists; run the focused contract test plus `typecheck:model` before the PR task.

---

### Task 1: Contract tests for default and arena wiring

**Files:**
- Modify: `site/tests/rendered-html.test.mjs`
- Modify: `site/app/arena/model.ts` (default only, later in Task 2 — tests first here)
- Test: `site/tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: existing source-read test style (`readFile` + `assert.match`)
- Produces: failing tests that lock:
  - `DEFAULT_MOVE_TIME_LIMIT_MS = 10_000`
  - arena state defaults `10000`
  - `ModelLoader` thinking-cap label
  - `predict(..., moveTimeLimitMs)` call site in arena

- [ ] **Step 1: Add failing contract tests**

Append these tests to `site/tests/rendered-html.test.mjs` near the other arena source tests (after the “arena defaults Player 1 to a random side…” test is a good place):

```js
test("arena casual default move time limit is 10 seconds", async () => {
  const model = await readFile(new URL("../app/arena/model.ts", import.meta.url), "utf8");
  assert.match(model, /export const DEFAULT_MOVE_TIME_LIMIT_MS = 10_000;/);
});

test("arena setup exposes a per-player thinking cap defaulting to 10000 ms", async () => {
  const arena = await readFile(new URL("../app/arena/arena-client.tsx", import.meta.url), "utf8");

  assert.match(arena, /DEFAULT_MOVE_TIME_LIMIT_MS/);
  assert.match(arena, /useState\(DEFAULT_MOVE_TIME_LIMIT_MS\)/);
  assert.match(arena, /Thinking cap \(ms\)/);
  assert.match(arena, /Per-move budget passed to the package/);
  assert.match(arena, /moveTimeLimitMs=\{moveTimeLimitMsA\}/);
  assert.match(arena, /moveTimeLimitMs=\{moveTimeLimitMsB\}/);
  assert.match(
    arena,
    /model\.predict\(\s*activeGame\.history\(\),\s*activeGame\.moves\(\),\s*moveTimeLimitMs\s*\)/,
  );
  assert.doesNotMatch(arena, /chess-gpt:arena-move-time/);
  assert.doesNotMatch(arena, /searchParams\.(get|set)\(["']t(?:ime)?/);
});
```

If the multiline `predict` regex is brittle against formatting, keep the single-line form the implementation will use:

```js
assert.match(arena, /model\.predict\(activeGame\.history\(\), activeGame\.moves\(\), moveTimeLimitMs\)/);
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `site/`:

```bash
node --test tests/rendered-html.test.mjs
```

Expected: FAIL on the new tests (`DEFAULT_MOVE_TIME_LIMIT_MS = 30_000` still present; no thinking-cap UI strings).

- [ ] **Step 3: Commit the failing tests**

```bash
git add site/tests/rendered-html.test.mjs
git commit -m "test: require arena per-player thinking caps"
```

---

### Task 2: Default move time limit 10s + ModelLoader cap UI

**Files:**
- Modify: `site/app/arena/model.ts` (export default constant)
- Modify: `site/app/arena/arena-client.tsx` (import, state, ModelLoader props/UI, call sites)
- Modify: `site/app/globals.css` (minimal spacing for the new field)
- Test: `site/tests/rendered-html.test.mjs`

**Interfaces:**
- Consumes: `DEFAULT_MOVE_TIME_LIMIT_MS` from `./model`
- Produces:
  - `ModelLoader` props include `moveTimeLimitMs: number` and `onMoveTimeLimitMs: (value: number) => void`
  - `playModelMove(model, actor, moveTimeLimitMs: number)`
  - Arena state: two `useState(DEFAULT_MOVE_TIME_LIMIT_MS)` values

- [ ] **Step 1: Change the model default**

In `site/app/arena/model.ts`, replace:

```ts
/** Per-move budget used for casual arena games, which have no tournament clock. */
export const DEFAULT_MOVE_TIME_LIMIT_MS = 30_000;
```

with:

```ts
/** Per-move budget used for casual arena games when the caller omits a limit. */
export const DEFAULT_MOVE_TIME_LIMIT_MS = 10_000;
```

- [ ] **Step 2: Import the constant and add session state**

In `site/app/arena/arena-client.tsx`, extend the model import:

```ts
import {
  DEFAULT_MOVE_TIME_LIMIT_MS,
  loadBrowserModel,
  type BrowserChessModel,
  type LoadProgress,
} from "./model";
```

Beside the other setup state (near `sidePreference`), add:

```ts
const [moveTimeLimitMsA, setMoveTimeLimitMsA] = useState(DEFAULT_MOVE_TIME_LIMIT_MS);
const [moveTimeLimitMsB, setMoveTimeLimitMsB] = useState(DEFAULT_MOVE_TIME_LIMIT_MS);
```

- [ ] **Step 3: Thread the limit through `playModelMove` and callers**

Replace `playModelMove` so it accepts and forwards the budget:

```ts
const playModelMove = useCallback(
  async (model: BrowserChessModel, actor: string, moveTimeLimitMs: number) => {
    const epoch = gameEpoch.current;
    const activeGame = gameRef.current;
    if (activeGame.isGameOver()) return;
    setThinking(actor);
    setGameError(null);
    const started = performance.now();
    try {
      const prediction = await model.predict(
        activeGame.history(),
        activeGame.moves(),
        moveTimeLimitMs,
      );
      // ...existing success path unchanged...
    } catch (error) {
      // ...existing error path unchanged...
    } finally {
      if (gameEpoch.current === epoch) setThinking(null);
    }
  },
  [],
);
```

Update the autoplay effect’s candidate resolution to carry the slot limit. Replace the `activeModel` IIFE so it returns `{ model, actor, moveTimeLimitMs } | null`:

```ts
const activeModel = (() => {
  if (!running || game.isGameOver()) return null;
  if (mode === "models") {
    return game.turn() === player1Color
      ? modelA.model && {
          model: modelA.model,
          actor: modelA.model.info.name,
          moveTimeLimitMs: moveTimeLimitMsA,
        }
      : modelB.model && {
          model: modelB.model,
          actor: modelB.model.info.name,
          moveTimeLimitMs: moveTimeLimitMsB,
        };
  }
  if (game.turn() === humanColor) return null;
  if (modelA.model) {
    return {
      model: modelA.model,
      actor: modelA.model.info.name,
      moveTimeLimitMs: moveTimeLimitMsA,
    };
  }
  if (modelB.model) {
    return {
      model: modelB.model,
      actor: modelB.model.info.name,
      moveTimeLimitMs: moveTimeLimitMsB,
    };
  }
  return null;
})();
```

And the effect:

```ts
() => void playModelMove(
  activeModel.model,
  activeModel.actor,
  activeModel.moveTimeLimitMs,
),
```

Update `stepOnce` the same way — include `moveTimeLimitMs` on each candidate and pass it through:

```ts
async function stepOnce() {
  if (thinking || game.isGameOver()) return;
  const candidate =
    mode === "models"
      ? game.turn() === player1Color
        ? modelA.model && {
            model: modelA.model,
            actor: modelA.model.info.name,
            moveTimeLimitMs: moveTimeLimitMsA,
          }
        : modelB.model && {
            model: modelB.model,
            actor: modelB.model.info.name,
            moveTimeLimitMs: moveTimeLimitMsB,
          }
      : game.turn() !== humanColor
        ? modelA.model
          ? {
              model: modelA.model,
              actor: modelA.model.info.name,
              moveTimeLimitMs: moveTimeLimitMsA,
            }
          : modelB.model && {
              model: modelB.model,
              actor: modelB.model.info.name,
              moveTimeLimitMs: moveTimeLimitMsB,
            }
        : null;
  if (candidate) {
    await playModelMove(candidate.model, candidate.actor, candidate.moveTimeLimitMs);
  }
}
```

- [ ] **Step 4: Extend `ModelLoader` with the thinking-cap control**

Update both call sites:

```tsx
<ModelLoader
  label="Player 1"
  role="Model · optional"
  slot={modelA}
  moveTimeLimitMs={moveTimeLimitMsA}
  onMoveTimeLimitMs={setMoveTimeLimitMsA}
  onReference={(reference) => updateReference("a", reference)}
  onLoad={() => void loadModel("a")}
/>
```

```tsx
<ModelLoader
  label="Player 2"
  role="Optional · Human if empty"
  slot={modelB}
  moveTimeLimitMs={moveTimeLimitMsB}
  onMoveTimeLimitMs={setMoveTimeLimitMsB}
  onReference={(reference) => updateReference("b", reference)}
  onLoad={() => void loadModel("b")}
/>
```

Replace the `ModelLoader` function with:

```tsx
function ModelLoader({
  label,
  role,
  slot,
  moveTimeLimitMs,
  onMoveTimeLimitMs,
  onReference,
  onLoad,
}: {
  label: string;
  role: string;
  slot: ModelSlot;
  moveTimeLimitMs: number;
  onMoveTimeLimitMs: (value: number) => void;
  onReference: (reference: string) => void;
  onLoad: () => void;
}) {
  const inputId = `model-${label.toLowerCase().replace(" ", "-")}`;
  const capId = `${inputId}-thinking-cap`;
  const percent = slot.progress?.totalBytes
    ? Math.min(100, (slot.progress.loadedBytes / slot.progress.totalBytes) * 100)
    : null;
  return (
    <article className="model-loader">
      <header><span>{label}</span><small>{role}</small></header>
      <label htmlFor={inputId}>Hugging Face model</label>
      <div className="model-input-row">
        <input
          id={inputId}
          type="text"
          value={slot.reference}
          onChange={(event) => onReference(event.target.value)}
          placeholder="owner/repository@commit"
          spellCheck={false}
          autoCapitalize="none"
          autoCorrect="off"
        />
        <button type="button" onClick={onLoad} disabled={slot.phase === "loading"}>
          {slot.phase === "loading" ? "Loading…" : slot.phase === "ready" ? "Reload" : "Load"}
        </button>
      </div>
      <label className="thinking-cap-field" htmlFor={capId}>
        <span>Thinking cap (ms)</span>
        <input
          id={capId}
          type="number"
          min={1}
          max={600000}
          required
          value={moveTimeLimitMs}
          onChange={(event) => onMoveTimeLimitMs(Number(event.target.value))}
        />
        <small>Per-move budget passed to the package.</small>
      </label>
      {slot.phase === "loading" && slot.progress ? (
        <div className="load-progress" aria-live="polite">
          <div><i style={{ width: percent === null ? "24%" : `${percent}%` }} /></div>
          <span>
            {slot.progress.label} · {formatBytes(slot.progress.loadedBytes)}
            {slot.progress.totalBytes ? ` / ${formatBytes(slot.progress.totalBytes)}` : ""}
          </span>
        </div>
      ) : null}
      {slot.model ? (
        <div className="model-summary">
          {slot.profileId
            ? <Link href={modelPageHref(slot.model.info.reference)}><strong>{slot.model.info.name}</strong></Link>
            : <strong>{slot.model.info.name}</strong>}
          <span>
            {slot.model.info.runtime} · {formatBytes(slot.model.info.artifactBytes)} ·{" "}
            {slot.model.info.pinned ? "Pinned" : "Mutable"}
          </span>
          <code title={`SHA-256 ${slot.model.info.digest}`}>
            SHA {slot.model.info.digest.slice(0, 12)}…
          </code>
        </div>
      ) : null}
      {slot.error ? <p className="model-error" role="alert">{slot.error}</p> : null}
    </article>
  );
}
```

- [ ] **Step 5: Add minimal CSS**

In `site/app/globals.css`, after the `.arena-page-v2 .model-input-row button` rules (~line 675), add:

```css
.arena-page-v2 .thinking-cap-field {
  display: grid;
  gap: 0.3rem;
  margin-top: 0.55rem;
}
.arena-page-v2 .thinking-cap-field > span {
  color: var(--muted);
  font-size: 0.55rem;
  font-weight: 850;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.arena-page-v2 .thinking-cap-field > input {
  min-height: 2.25rem;
  width: 100%;
  max-width: 12rem;
  padding: 0 0.55rem;
  border: 1px solid var(--line);
  border-radius: 0.2rem;
  background: transparent;
  font: inherit;
}
.arena-page-v2 .thinking-cap-field > small {
  color: var(--muted);
  font-size: 0.57rem;
  line-height: 1.35;
}
```

- [ ] **Step 6: Run focused verification**

```bash
cd site
node --test tests/rendered-html.test.mjs
npm run typecheck:model
```

Expected: all rendered-html tests PASS; typecheck clean.

If `rendered-html` server-render tests need a prior build and fail on missing `dist/`, run:

```bash
npm run build && node --test tests/rendered-html.test.mjs
```

- [ ] **Step 7: Commit**

```bash
git add site/app/arena/model.ts site/app/arena/arena-client.tsx site/app/globals.css
git commit -m "feat(arena): per-player thinking cap on setup"
```

---

### Task 3: Visual smoke, screenshots, and pull request

**Files:**
- Create (local only, do not commit binaries unless the repo already stores PR media): screenshot files used in the PR body
- No production code changes expected unless smoke reveals a bug

**Interfaces:**
- Consumes: working `/arena` setup UI from Task 2
- Produces: GitHub PR with terse description + before/after screenshots

- [ ] **Step 1: Ensure a feature branch**

If still on `main`:

```bash
git checkout -b arena-thinking-cap
```

Cherry-pick or ensure Tasks 1–2 commits are on this branch. Do not merge to `main` yet.

- [ ] **Step 2: Capture the before screenshot**

If you no longer have pre-change UI locally, use `main` briefly:

```bash
git stash push -u -m "wip-thinking-cap"   # only if dirty
git checkout main
cd site && npm run dev
```

Open `/arena`, wait for **Set up game**, screenshot the sidebar with Player 1 / side picker / Player 2 / Start game. Save as `before-setup-game.png` (Desktop or `/tmp` is fine — not committed).

Return to the feature branch and restore any stash:

```bash
git checkout arena-thinking-cap
git stash pop   # if used
```

- [ ] **Step 3: Capture the after screenshot and smoke the budget path**

```bash
cd site && npm run dev
```

Open `/arena` Set up game:

1. Confirm both players show **Thinking cap (ms)** defaulting to `10000`.
2. Change Player 1 to `1000` and Player 2 to `5000`; reload must not be required for the values to stick in-session.
3. Optionally load a known package and start a game long enough to see a model move without error (full dual-model load is best-effort if network/HF is available).
4. Screenshot the setup sidebar with both caps visible → `after-setup-game.png`.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin HEAD
gh pr create --title "feat(arena): per-player thinking cap" --body "$(cat <<'EOF'
## Summary
- Add a session-only per-player **Thinking cap (ms)** on the `/arena` Set up game screen (default `10000`).
- Pass each loaded model’s budget into `predict` / `chooseMove`; align casual default `DEFAULT_MOVE_TIME_LIMIT_MS` to 10s.

## Screenshots
### Before
<!-- attach before-setup-game.png -->

### After
<!-- attach after-setup-game.png -->

## Test plan
- [x] `node --test tests/rendered-html.test.mjs` (or full `npm test` if dist build required)
- [x] `npm run typecheck:model`
- [x] Manual: caps visible at 10000; distinct values accepted; model move still works
EOF
)"
```

After `gh pr create`, upload `before-setup-game.png` and `after-setup-game.png` as PR image attachments (drag-and-drop on GitHub or `gh pr edit` with uploaded URLs). The PR body must show both images inline.

- [ ] **Step 5: Record the PR URL**

Paste the PR URL into the session handoff / final message. Do not mark the goal complete until the PR exists with screenshots.

---

## Spec coverage checklist

| Spec requirement | Task |
| --- | --- |
| Per-player caps on each ModelLoader | Task 2 |
| Default 10000 ms | Tasks 1–2 |
| Milliseconds UI, range 1–600000 | Task 2 |
| Session-only (no storage/URL) | Task 1 negative asserts + Task 2 |
| `predict(..., moveTimeLimitMs)` wiring for autoplay and stepOnce | Task 2 |
| `DEFAULT_MOVE_TIME_LIMIT_MS = 10_000` | Tasks 1–2 |
| Human unlimited / models only | Task 2 (no predict on human path) |
| No tournament changes | — (untouched) |
| Before/after screenshots + PR | Task 3 |

## Self-review notes

- No TBD/placeholder steps.
- Predict call signature matches `BrowserChessModel.predict(history, legalMoves, moveTimeLimitMs?)`.
- Tournament `SMOKE_MOVE_TIME_LIMIT_MS = 30_000` intentionally unchanged (registration smoke, not arena default).
- Share-url helpers stay untouched.
