# Arena per-player thinking cap

Date: 2026-08-01  
Status: approved for implementation planning

## Problem

Tournaments already configure a single per-move wall-clock limit (`moveTimeLimitMs`) and pass it into each package’s `chooseMove`. Casual `/arena` play does not: `playModelMove` calls `model.predict(history, legalMoves)` with no budget, so the model layer falls back to a hard-coded 30s default. Players cannot set or compare thinking budgets when setting up a game.

## Goal

Add a UI-configurable thinking cap on the arena **Set up game** screen so each player slot has its own per-move budget (default **10000 ms**). Open a pull request with a terse description and before/after screenshots of that screen.

## Non-goals

- Changing tournament create/run configuration (already has tournament-wide `moveTimeLimitMs`).
- Persisting caps in `localStorage` or share URLs.
- Editing caps mid-game after **Start game**.
- Changing the runner grace factor (`1.25×`) or package interface.

## Decisions

| Choice | Value |
| --- | --- |
| Scope | Separate cap per player (Player 1 and Player 2) |
| Units | Milliseconds in the UI |
| Default | `10000` for each slot |
| Persistence | Session-only React state |
| UI placement | Number input on each `ModelLoader` card |
| Fallback constant | `DEFAULT_MOVE_TIME_LIMIT_MS` becomes `10_000` |

## Behavior

1. Each `ModelLoader` shows a **Thinking cap (ms)** number input.
2. Both slots initialize to `10000`.
3. Valid range matches the tournament form ceiling: `min={1}`, `max={600000}`.
4. Only loaded models consume a cap. Human moves are unlimited and ignore the control.
5. When a model moves, the arena resolves the active slot (A or B from mode/turn) and calls:

   ```ts
   model.predict(history, legalMoves, moveTimeLimitMs)
   ```

6. Existing worker enforcement still applies: hard kill at `hardMoveLimitMs(moveTimeLimitMs)` (`ceil(limit * 1.25)`). Overrun remains a forfeit.
7. Caps are not written to localStorage, share URL params, or PGN headers.
8. Starting a new setup (reload / new game returning to setup) resets to the defaults unless the React tree still holds prior state for that page session.

## UI

- Label: `Thinking cap (ms)`
- Helper text: `Per-move budget passed to the package.`
- Placement: on each player card beneath the reference/load controls so the cap stays visually tied to that player.
- Disabled/irrelevant styling is unnecessary for empty human slots; the value is simply unused until a model occupies the slot.
- Style with existing arena/setup form patterns in `globals.css` (no new design system).

## Data flow

```
ModelLoader A/B input
  → moveTimeLimitMsA / moveTimeLimitMsB state in ArenaClient
  → playModelMove / stepOnce resolves active slot
  → BrowserChessModel.predict(history, legalMoves, moveTimeLimitMs)
  → worker chooseMove({ …, moveTimeLimitMs })
  → runner timeout hardMoveLimitMs(moveTimeLimitMs)
```

### State

```ts
const DEFAULT_ARENA_MOVE_TIME_LIMIT_MS = 10_000;
const [moveTimeLimitMsA, setMoveTimeLimitMsA] = useState(DEFAULT_ARENA_MOVE_TIME_LIMIT_MS);
const [moveTimeLimitMsB, setMoveTimeLimitMsB] = useState(DEFAULT_ARENA_MOVE_TIME_LIMIT_MS);
```

Prefer one shared constant used by both the UI defaults and `model.ts`’s `DEFAULT_MOVE_TIME_LIMIT_MS`, or set both to `10_000` explicitly and keep them aligned in the PR.

### Active-slot resolution

- **Model vs model:** side to move maps to Player 1 color → slot A, else slot B.
- **Human vs model:** the single loaded model’s slot supplies the cap.
- **stepOnce** uses the same resolution path as autoplay so manual stepping cannot bypass the budget.

## Files likely touched

- `site/app/arena/arena-client.tsx` — state, `ModelLoader` props/UI, `playModelMove` wiring
- `site/app/arena/model.ts` — default `DEFAULT_MOVE_TIME_LIMIT_MS` → `10_000`
- `site/app/globals.css` — only if the new input needs spacing helpers to match setup cards
- Tests under `site/tests/` only if existing coverage asserts the old 30s default

## Verification

1. **UI smoke:** open `/arena` setup; both player cards show thinking cap inputs defaulting to `10000`.
2. **Budget wiring:** load two models, set distinct caps (e.g. `1000` and `10000`), start a model-vs-model game; each side’s `chooseMove` receives its own `moveTimeLimitMs` (confirm via adapter that budgets search, or by forcing a slow path / overrun on the tight cap).
3. **Human path:** one model + empty second slot; only the model is bounded; human moves never hit the worker timer.
4. **Default alignment:** any `predict` call without an explicit limit uses `10_000`.
5. **Regression:** existing play-game / model worker tests still pass; update assertions if they pin `30000`.

## PR deliverable

- Branch off `main`, implement the above, push, open a pull request.
- Description: terse summary of per-player arena thinking caps (default 10s / 10000 ms).
- Attach **before** and **after** screenshots of the **Set up game** screen on `/arena` with the new controls visible in the after image.

## Implementation notes

- Keep validation boring: positive finite integer in range; coerce empty/invalid input back to the last good value or the default on blur if the existing form style does that; otherwise mirror the tournament number-input pattern (controlled numeric state).
- Do not plumb caps through share-url helpers in this change.
- Teaching posture: the control is the same mechanism tournaments already use (`moveTimeLimitMs`); arena is exposing it for casual inspection and unequal budgets.
