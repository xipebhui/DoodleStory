# UI Interaction Standard

## Purpose

Use this standard when designing or implementing product screens, especially list, create, detail, edit, delete, search, filter, and settings workflows.

This standard is separate from `docs/standards/frontend.md`. The frontend standard covers implementation quality. This standard covers how users move through the product, understand state, recover from mistakes, and complete work without friction.

## Source Baseline

- [Nielsen Norman Group: 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
- [GOV.UK Design System: Components](https://design-system.service.gov.uk/components/)
- [GOV.UK Design System: Patterns](https://design-system.service.gov.uk/patterns/)
- [Material Design 3](https://m3.material.io/)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [WAI-ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [Radix UI Accessibility](https://www.radix-ui.com/primitives/docs/overview/accessibility)

## Core Principles

1. Make system status visible. Loading, saving, saved, failed, empty, offline, dirty, and permission states must be obvious.
2. Keep users in control. Users need clear exits, back paths, cancel actions, and undo or confirmation for risky actions.
3. Prefer familiar patterns. Lists, forms, detail pages, settings, and payment flows should behave like users expect.
4. Reduce memory burden. Show context, labels, selected filters, current object names, and next steps instead of making users remember them.
5. Prevent errors before recovering from them. Validate early, disable impossible actions with explanations, and confirm destructive actions.
6. Preserve user work. Do not discard form input, filters, scroll position, or drafts without warning.
7. Keep interaction simpler than the data model. Do not expose internal architecture through awkward screens.
8. Use animation and decoration only when they clarify state or continuity.

## Default Product Shape

For operational tools, dashboards, admin panels, and lightweight SaaS products, default to this navigation shape:

- List page: find and choose an object.
- Create flow: add a new object with the minimum required information.
- Detail page: understand one object and access key actions.
- Edit flow: change a clear subset of object data.
- Confirmation or undo: protect irreversible or expensive changes.

Do not replace this shape with onboarding tours, multi-step wizards, nested modals, or custom gestures unless the workflow requires them.

## List Pages

List pages help users scan, find, compare, and act.

Required elements:

- Clear page title.
- Primary create action when creation is allowed.
- Search when the list can grow beyond easy scanning.
- Filters only for fields users actually use to narrow the list.
- Sort only for meaningful ordering.
- Loading state.
- Empty state with a useful next action.
- Error state with retry or recovery guidance.

Behavior rules:

1. Put the primary create action near the page title or list controls.
2. Keep row density appropriate for repeated work. Operational tools should be compact but readable.
3. Make object names or row titles the primary navigation target.
4. Preserve filters, search, pagination, and scroll position when users open an item and return.
5. Do not hide primary row actions behind hover-only UI. Hover can reveal convenience actions, but keyboard and touch users need access.
6. Use tables for comparison across columns. Use cards only when each item has rich media or varied content.
7. For long lists, prefer server-backed pagination, cursor loading, or virtualized lists only when the data volume requires it.
8. Do not add bulk actions until there is a verified bulk workflow.

Empty states:

- Say what is missing in user language.
- Offer the next likely action, such as creating the first item or clearing filters.
- Distinguish between "no data yet" and "no results match these filters."

## Create Flows

Create flows should collect only what is needed to create a valid object.

Choose the container by complexity:

- Inline create: one or two fields in an existing context.
- Modal dialog: short create flow that does not need deep context or navigation.
- Drawer: short-to-medium create or edit flow where the list/detail context should stay visible.
- Full page: many fields, multi-section forms, file uploads, preview, save draft, or collaboration.
- Step flow: only when the order matters or later inputs depend on earlier choices.

Behavior rules:

1. Make required fields clear.
2. Use labels, help text, and examples where users may hesitate.
3. Validate before submit when possible, and validate again on submit.
4. On failure, keep all user input and move focus to the first actionable error.
5. On success, take users to the most useful next place: the new detail page, the list with the new item highlighted, or a reset form for repeated creation.
6. Do not ask for optional metadata during first creation unless the next workflow depends on it.
7. Do not close a form while saving until the user can see success, failure, or progress.

## Detail Pages

Detail pages help users understand one object and decide what to do next.

Required elements:

- Object name or primary identifier.
- Status when status affects action.
- Key metadata and timestamps when useful.
- Primary action for the next likely task.
- Secondary actions grouped away from the primary action.
- Clear navigation back to the list or parent context.

Behavior rules:

1. Put the most important state near the title.
2. Group information by user task, not database table.
3. Show empty optional sections quietly; do not make missing optional data look like an error.
4. Keep dangerous actions visually separate from routine actions.
5. If the object can change elsewhere, show stale or refresh state when relevant.
6. Prefer direct links to related objects over duplicating large related datasets.

## Edit Flows

Edit flows should make the scope of change obvious.

Behavior rules:

1. Use a dedicated edit page for broad changes.
2. Use inline edit for small, low-risk fields where immediate context matters.
3. Use a modal or drawer for focused edits that should return to the same page.
4. Preserve unsaved changes and warn before navigation if changes would be lost.
5. Show saving and saved states.
6. After save, keep users near the changed content and show what changed.

## Buttons And Actions

Buttons should communicate exactly what will happen.

Rules:

1. Use one primary action per region.
2. Write button labels as verb plus object when possible: `Create project`, `Save settings`, `Delete member`.
3. Avoid vague labels such as `Submit`, `OK`, or `Next` unless the surrounding flow makes the action unmistakable.
4. Use links for navigation and buttons for actions that change state.
5. Disable buttons only when the reason is obvious or explained nearby.
6. During submit, prevent duplicate actions and show progress.
7. Icon-only buttons must have an accessible name and a tooltip when the icon is not universally obvious.
8. Destructive actions must not be the default focused action in confirmation dialogs.
9. Primary and destructive actions should not look the same.

Button hierarchy:

- Primary: one main action.
- Secondary: useful but less important action.
- Tertiary or link: navigation, cancel, or low-emphasis action.
- Destructive: delete, revoke, cancel subscription, overwrite, reset, or remove access.

## Feedback And State

Every user action should produce an appropriate response.

Use inline feedback for:

- Field validation.
- Save state near the edited content.
- Permission or availability issues tied to a specific control.

Use toast or snackbar feedback for:

- Non-blocking success.
- Background completion.
- Undo after a reversible action.

Use modal confirmation for:

- Destructive actions.
- Expensive actions.
- External side effects such as sending messages, charging money, publishing, or deleting data.

Use blocking progress only when:

- The user cannot safely continue.
- The operation changes critical state.
- The operation must finish before the next step.

## Display Mode Interaction

Use this section when the product supports light mode, dark mode, or system mode.

Rules:

1. Offer display mode as a user preference, usually in settings or an account menu. Do not make it compete with primary workflow actions.
2. Support three choices when feasible: `System`, `Light`, and `Dark`.
3. Default to `System` unless the product has a strong domain reason to start in one mode.
4. Apply mode changes immediately and keep users on the same page with the same unsaved work, filters, scroll position, and selected item.
5. Persist the user's explicit choice across sessions.
6. Make the current mode visible in the control through label, selected state, or icon plus accessible name.
7. Do not use mode changes as a navigation event or reload that loses state.
8. Keep all important statuses readable in both modes: success, warning, danger, disabled, selected, loading, empty, and focused.
9. Do not change information hierarchy between modes. Light and dark mode should feel like the same product.
10. If a product renders images, artwork, previews, charts, or generated media, verify that surrounding chrome does not distort how users judge the content.

## Loading, Latency, And Smoothness

Smoothness is not decoration. It is the absence of confusion during state changes.

Rules:

1. Show immediate pressed or busy feedback after user action.
2. Use skeletons for content loading when layout is predictable.
3. Use spinners for short indeterminate waits.
4. Use progress bars for long operations with measurable progress.
5. Avoid layout shift when data loads.
6. Preserve context after navigation: filters, selected tab, scroll position, and recently created item.
7. Prefer optimistic UI only when the operation is low-risk and rollback is simple.
8. If an operation may take a while, let users keep working or cancel when possible.
9. Do not stack multiple success toasts for repeated quick actions.

## Errors And Recovery

Errors should help users recover, not merely report failure.

Rules:

1. Explain what happened in user language.
2. Tell users what they can do next.
3. Keep technical details out of the primary message unless the user is expected to act on them.
4. Keep input values after validation or server errors.
5. For forms, show a summary if there are multiple errors and mark each field inline.
6. For permission errors, say what access is missing and who can resolve it when known.
7. For network errors, offer retry and preserve the user's work.

## Destructive And High-Risk Actions

High-risk actions include delete, revoke access, cancel subscription, overwrite, publish, send, charge, refund, reset, and bulk changes.

Rules:

1. Ask for confirmation when the result is hard to undo.
2. Include the object name in the confirmation.
3. Explain the consequence, not just the action.
4. Prefer undo for reversible actions.
5. Require stronger confirmation for irreversible or bulk destructive actions.
6. Do not hide destructive actions in the same menu position as routine actions.

## Accessibility Interaction Baseline

Custom components must follow established patterns.

Rules:

1. Dialogs trap focus while open and restore focus when closed.
2. Menus, comboboxes, tabs, accordions, listboxes, and tables follow WAI-ARIA APG keyboard patterns.
3. All interactive elements are reachable by keyboard.
4. Focus states are visible.
5. Status messages are announced when needed.
6. Touch targets are large enough for reliable use.
7. Color is never the only way to communicate state.

Prefer proven accessible component primitives such as Radix UI, React Aria, native HTML, or the selected design system before building custom interactive primitives.

## AI And Agent UI

When UI includes AI or agent behavior, users need more visibility and control than in ordinary CRUD flows.

Rules:

1. Show what the AI is doing while it works.
2. Distinguish draft, suggested, and committed output.
3. Ask for confirmation before external side effects.
4. Let users inspect, edit, retry, or cancel AI-generated actions when feasible.
5. Do not present uncertain AI output as system truth.
6. Preserve an activity trail for long-running or multi-step agent work.

## Review Checklist

Before calling a UI workflow done, confirm:

- The list page has loading, empty, error, and populated states.
- Create flow preserves input on failure and gives a clear success destination.
- Detail page exposes key state and next actions.
- Edit flow handles unsaved changes.
- Buttons use specific labels and show progress.
- Destructive actions require confirmation or provide undo.
- Light and dark modes preserve readability, state, and workflow context when supported.
- Keyboard and focus behavior work for dialogs, menus, tabs, and forms.
- Returning from detail to list preserves useful context.
- The UI does not add extra steps, modals, or tours without a real workflow need.
