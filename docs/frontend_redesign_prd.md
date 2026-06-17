# FEWS Frontend Redesign PRD

## Objective

Upgrade the FEWS server-rendered UI so audit users can upload approval data, interpret fraud signals, and follow up findings faster with a polished internal-tool interface.

## Scope

- Keep the existing FastAPI/Jinja architecture.
- Apply a restrained, shadcn-inspired visual system using native HTML, CSS, and small vanilla JavaScript.
- Use the organization logo colors only as palette reference: deep blue, active cyan, and lime success accents.
- Do not display logo assets or recreate logo-like brand marks in the app; use text-only `FEWS` branding.
- Improve all visible pages: login, app shell, dashboard, upload approval, alert center, reports, logs, and legacy transaction views.
- Preserve existing routes, forms, and backend behavior.
- Avoid React/Tailwind migration for this pass so the project remains easy to zip and deploy to Vercel.
- Keep this pass visual-only: no new routes, API contracts, database fields, export behavior, charts, or backend features.

## UX Goals

- Make risk severity obvious at a glance.
- Reduce visual noise in the dashboard and alert center.
- Make upload workflow feel deliberate and confidence-building.
- Keep dense tables readable with sticky headers, clearer row separation, and responsive scroll.
- Provide consistent page headers, buttons, badges, filters, cards, and empty states.
- Avoid generic AI-slop aesthetics: no decorative logo blocks, noisy gradients, heavy glows, excessive pills, or warm legacy tones in primary UI.

## Reference Direction

- 21st.dev dashboard/admin/sidebar/table patterns: dense but clean operational layouts.
- shadcn/ui dashboard examples: neutral surfaces, subtle borders, consistent control sizing, concise side navigation.
- Bimbel Nurul Fikri logo palette translated into UI tokens only:
  - Primary/nav: `#0050A0`, `#0060B0`
  - Active/info: `#1080E0`, `#1090F0`, `#30B0F0`
  - Success/positive: `#80E000` with soft success surfaces
  - Surface/text/border: white, cool gray, charcoal/navy
  - Danger: restrained audit red for high-risk states

## Constraints

- No new heavy frontend dependencies.
- No loss of accessibility for forms and links.
- CSS should remain standalone in `app/static/style.css`.
- JavaScript should be progressive enhancement only; forms must still work without it.
- No logo image usage in sidebar, login, cards, empty states, or decorative blocks.
