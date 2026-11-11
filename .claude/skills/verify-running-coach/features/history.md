# Goal history

A table of every submitted goal with status, a link to the plan, and delete.

## Sub-features

- `hist-list` rows show submitted date, target, race date, fitness and status badge (`Sẵn sàng`).
- `hist-view` `Xem kế hoạch` opens the plan.
- `hist-delete` `Xóa` removes the goal and its plan after confirmation.
- `hist-empty` shows `Chưa có mục tiêu nào.`

## How to get to it (user POV)

- Nav link `Lịch Sử` (`/app/history`).

## Driving it with Claude in Chrome + psql

Preconditions: at least one goal (run `new-goal.md`).

- **List.** Open `/app/history`; one row with `Sẵn sàng`.
- **Delete.** Run `window.confirm = () => true` via the JS tool, click `Xóa`; the row disappears and `select count(*) from user_goals` returns 0 (plans and workouts for it are gone too).

## Gotchas

- The native confirm dialog blocks the browser tool if not overridden first.
- Not yet run in this skill's proof.
