# PIIOS Frontend — Design Guidelines

This is the single source of truth for the visual language implemented in
`dashboard/lib/components.py` (`inject_base_styles()` and the component
functions). If a page needs a new visual treatment, add it to
`components.py` and document it here — never invent a one-off style
directly inside a page file.

## Design intent

PIIOS is a family-office / CIO investment workstation, not a consumer
finance app. The reference points are Bloomberg Terminal, BlackRock
Aladdin, and Morningstar Direct: dense, precise, low-animation,
high-trust. Every visual choice should read as restrained and
institutional rather than playful or "gamified."

Avoid: bright saturated colours, flashing/pulsing elements, gradients,
large rounded "app" cards, emoji-heavy copy (a small number of
functional icons — ⚠️ ℹ️ ✅ 🔒 ⏳ — are fine; decorative emoji are not),
confetti/animation on interaction, dark mode neon accents.

## Colour usage

| Token | Hex | Usage |
|---|---|---|
| Ink navy | `#0B1F3A` | Titles, section headers, primary text emphasis |
| Slate blue | `#1F4E79` | Secondary accents, links, timeline rail, neutral badges |
| Steel blue | `#3D7EA6` | Chart accent (2nd series) |
| Pale steel | `#7FA8C9` | Chart accent (3rd series) |
| Border grey | `#D9DEE4` | Card borders, table borders |
| Muted grey | `#5B6472` | Captions, secondary labels, disabled text |
| Faint grey | `#8A93A0` | Timestamps, tertiary metadata |
| Success green | `#1E7145` | Low risk, high confidence, healthy/compliant states |
| Warning amber | `#B4690E` | Medium risk, medium confidence, pending/attention states |
| Critical red | `#B3261E` | High/critical risk, low confidence, breaches, errors |

Colour is never the only signal — every badge pairs colour with a text
label (e.g. "🔴 HIGH", not a bare red dot), so the app remains usable
without colour perception.

## Typography

- Use Streamlit's default system font stack; do not import custom web fonts.
- Section headers (`section_header()`) are bold, `#0B1F3A`, with a 2px
  navy underline — this is the only heading style in the app; do not use
  raw `st.header`/`st.subheader` on new pages, prefer `section_header()`
  for consistency.
- Captions/help text are `#5B6472`, ~0.86rem — used for the one line of
  context under a section header or a data-freshness note.
- Body copy uses Streamlit defaults (no custom sizing) to keep long-form
  text (thesis narrative, rationale) easy to read.

## Spacing

- Sections are separated with `section_header()` (which carries its own
  top margin) or `st.divider()` between major page regions — do not mix
  both back-to-back for the same boundary.
- Cards (`piios-card`) use `0.9rem 1.1rem` padding and `0.7rem` bottom
  margin — consistent across recommendation cards, evidence cards,
  governance issue cards, and disabled cards.
- KPI rows use `st.columns` with equal width per `KPIItem` — do not mix
  KPI rows with a different column count on the same page without reason.

## Badge meanings

### Status badges (`status_badge()`, workflow state of a recommendation)

| Status | Meaning |
|---|---|
| ⚪ DRAFT | Proposal generated, not yet reviewed |
| 🔵 RESEARCHED | Supporting research attached/reviewed |
| 🔵 RISK_CHECKED | Reviewed against portfolio risk/IPS constraints |
| 🟠 PENDING_REVIEW | Awaiting an explicit human decision |
| 🟢 APPROVED | A human has approved this proposal |
| ⚫ ARCHIVED | Rejected, superseded, or closed out |

### Confidence badges (`confidence_badge()`, `confidence_tone()`)

| Band | Score range | Colour |
|---|---|---|
| High | ≥ 75 | Success green |
| Medium | 50–74 | Warning amber |
| Low | < 50 | Critical red |

These bands are a **presentation grouping** of the backend's own
`confidence_score` field. They must never be used to justify computing a
new score — if the backend adds a component breakdown, render it as-is
via `confidence_breakdown_card()` rather than re-deriving a band from it.

### Risk / severity badges (`risk_badge()`, `severity_badge()`)

| Severity | Colour |
|---|---|
| HIGH / CRITICAL | Critical red |
| MEDIUM / MODERATE / WARNING | Warning amber |
| LOW / MINOR | Success green |
| anything else | Muted grey |

### Governance colours

Governance issue cards (`governance_issue_card()`) reuse the risk/severity
palette above for the severity badge, and the status-badge palette for
any workflow-style status string. A governance item without a mapped
status renders the raw string with the muted-grey neutral badge rather
than guessing a colour.

### Pending / disabled badges

`pending_badge()` and `disabled_card()` always use muted grey with a 🔒 or
⏳ icon and dashed borders — this is the *only* visual pattern used to
mean "no backend contract exists yet." Do not reuse dashed-grey styling
for anything else, and do not use solid styling for a placeholder — the
dashed border is load-bearing signal that the section is inert.

## Accessibility rules

- Every colour-coded badge includes a text label; colour is never the
  sole carrier of meaning.
- Minimum text size for body copy follows Streamlit defaults (no
  sub-0.75rem body text); captions may go to 0.76–0.86rem but are always
  secondary/supplementary information, never the only copy for a fact.
- Interactive elements (buttons, selects, expanders) use Streamlit's
  native components rather than custom HTML/JS, preserving built-in
  keyboard navigation and screen-reader semantics.
- Disabled form fields (e.g. in the Decisions page) always carry a
  `help=` string explaining *why* they're disabled, not just that they are.
- Donut charts (`allocation_donut()`) always render an adjacent legend
  with percentage labels — colour segments are never the only way to
  read a value.
- Advisory/warning banners use both an icon and an explicit sentence —
  never an icon alone.

## Component inventory

All defined in `dashboard/lib/components.py`; import via
`from lib import components as ui`.

`inject_base_styles`, `section_header`, `KPIItem` / `kpi_row`, `metric_tile`,
`confidence_badge` / `confidence_tone`, `risk_badge`, `pending_badge`,
`empty_state_card`, `error_state_card`, `loading_skeleton`, `disabled_card`,
`TimelineEvent` / `timeline` / `audit_timeline` / `decision_timeline`,
`confidence_breakdown_card`, `evidence_card`, `recommendation_card`,
`portfolio_allocation_card`, `governance_issue_card`, `pipeline_flow`,
`allocation_donut`. Plus re-exported from `lib.ui`: `page_header`,
`advisory_banner`, `api_gap_notice`, `render`, `status_badge`,
`severity_badge`, `ADVISORY_BOUNDARY`.
