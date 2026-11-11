# Plan view

Shows a goal's plan: summary, week count, phase badges, and a collapsible table of workouts for each week.

## Sub-features

- `plan-header` shows title, summary, `12 Tuần` and phase badges (`Nền Tảng · 4 Tuần`, `Tăng Tiến · 4`, `Đỉnh Cao · 2`, `Giảm Tải · 2`).
- `plan-weeks` lists weeks with `Ngày/Loại/Quãng đường/Vùng/Ghi chú` tables.
- `plan-missing` shows `Không tìm thấy mục tiêu.` for an unknown goal id.

## How to get to it (user POV)

- After submitting a goal.
- `Xem kế hoạch` on a history row.
- `Xem toàn bộ kế hoạch →` on the dashboard.

## Driving it with Claude in Chrome + psql

Preconditions: a goal exists (run `new-goal.md`).

- **Open.** Navigate to `/app/goals/<goalId>` (id from `select id from user_goals`). Header and badges above are visible; week 1 shows rows `Thứ 2 Chạy nhẹ 6 km`, `Thứ 4`, `Thứ 7 Chạy dài 11 km`.
- **Unknown id.** Navigate to `/app/goals/00000000-0000-0000-0000-000000000000`; the not-found message and a `← Mục tiêu mới` link appear.

## Gotchas

- Only weeks 1-2 are expanded by default; others are collapsed.
- Not yet run in full: the unknown-id path.
