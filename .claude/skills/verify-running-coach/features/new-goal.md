# New goal and plan

A runner enters a half/full marathon goal, establishes fitness (chat, race time, or VDOT), and gets a generated training plan.

## Sub-features

- `goal-form-validate` rejects a bad target time, a race date under 10 weeks out, and missing fields.
- `goal-manual-race` computes VDOT and book level from a race time.
- `goal-manual-vdot` accepts a VDOT (20 to 85) directly.
- `goal-chat` runs the fitness chat: distance opener, one question, then a result card.
- `goal-submit` creates the goal and lands on the plan page with a ready plan.

## How to get to it (user POV)

- Nav link `Mục Tiêu Mới` (`/app/new`).
- `Tạo mục tiêu đầu tiên của bạn` link on an empty dashboard or history.

## Driving it with Claude in Chrome + psql

Preconditions: baseline; open `http://127.0.0.1:8010/app/new` in a new tab.

- **Manual race entry.** Click `Tôi đã biết thời gian thi đấu hoặc VDOT của mình`, keep distance `10K`, set textbox `52:00` to `52:00`, see a pill `VDOT 38` and a level badge, click `Sử dụng`. The card shows `CẤP 1/10 - NGƯỜI MỚI TẬP` and `VDOT 38`.
- **Fill the goal.** Set textbox `1:55:00` to `1:55:00`, the date input to a date at least 70 days out, leave `4` days selected.
- **Submit.** Click `Tạo Kế Hoạch Của Tôi`. The URL becomes `/app/goals/<uuid>` and the page shows `Kế Hoạch Tập Luyện Của Bạn` and `VERIFY-FAKE-PLAN 12 weeks`.
- **Second view.** `psql "$VERIFY_DATABASE_URL" -c "select vdot,fitness_level,plan_status from user_goals"` shows `38 | beginner | ready`; workouts count for the plan is 36.
- **Validation.** Submit with an empty form: errors `Nhập theo định dạng H:MM:SS (vd: 1:55:00)` and `Bắt buộc` appear and no row is inserted.
- **Chat.** Click `Bắt Đầu Đánh Giá`, answer the opener (`nam, 30 tuổi`), then any text (`10K 52 phút`). A result card with VDOT appears and the chat closes.

## Gotchas

- The chat result is canned by the fake AI (male, 30, 10K 52:00); it proves the flow and Python scoring, not model behavior.
- The manual race path was proven in the creation of this skill; the chat and validation paths were not run.
- `form_input` on the date input needs `YYYY-MM-DD`.
