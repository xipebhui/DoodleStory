# Frontend Development Standard

## Purpose

Use this standard when adding or changing frontend code. Build usable product screens first, keep implementation accessible and maintainable, and avoid decorative complexity that does not serve the workflow.

## Source Baseline

- [MDN: Web performance](https://developer.mozilla.org/en-US/docs/Web/Performance)
- [MDN: CSS and JavaScript accessibility best practices](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Accessibility/CSS_and_JavaScript)
- [W3C: WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [React documentation](https://react.dev/)
- [Next.js project structure](https://nextjs.org/docs/app/getting-started/project-structure)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [ESLint configuration documentation](https://eslint.org/docs/latest/use/configure/)
- [Prettier options documentation](https://prettier.io/docs/options.html)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

## Rules

1. Build the actual user workflow as the first screen for apps and tools. Do not create a marketing landing page unless the user asked for one.
2. Use semantic HTML and accessible controls before custom interaction patterns.
3. Meet WCAG-oriented basics: visible focus states, labels for inputs, meaningful button text or accessible names, sufficient contrast, and keyboard operability.
4. Keep components small and purpose-driven. Extract shared components after duplication is real.
5. Prefer TypeScript for non-trivial frontend projects unless the existing project is JavaScript-only.
6. Use framework routing, data fetching, and rendering conventions instead of hand-rolled alternatives.
7. In React and Next.js, keep client components limited to interactive UI that needs browser state or effects.
8. Avoid global state until local state, props, URL state, or server data are insufficient.
9. Use images and visual assets deliberately. Avoid generic decorative backgrounds when the product, data, or workflow needs clarity.
10. Validate and encode user-controlled data before rendering or sending it to APIs.
11. Keep linting and formatting automated through the existing project tooling. If no tooling exists, add it only when frontend work becomes real enough to justify it.

## Design Expectations

- Operational tools should favor dense but readable layouts, predictable navigation, and fast scanning.
- Consumer, creative, or game experiences may use richer visual treatment when it supports the purpose.
- Cards are for repeated items, modals, and framed tools. Do not nest cards inside cards.
- Text must fit its container across desktop and mobile.
- Responsive behavior should be designed with explicit layout constraints, not accidental wrapping.

## Theme Modes

Use this section when the UI supports light mode, dark mode, or system-based appearance.

### Default Rule

Frontend projects should support both light and dark display modes when the product is expected to be used repeatedly or for long sessions. Small one-off pages may start with one mode only, but app surfaces, dashboards, editors, and operational tools should be designed so a second mode can be added without rewriting components.

### Implementation Rules

1. Use semantic color tokens, not raw colors scattered through components. Examples: `surface`, `surface-muted`, `text-primary`, `text-secondary`, `border-subtle`, `accent`, `danger`, `success`, `warning`, `focus`.
2. Keep component structure identical across modes. Theme changes should swap tokens, not duplicate components.
3. Respect the user's system preference through `prefers-color-scheme` when no explicit user choice exists.
4. Persist explicit user choice when the user selects light mode, dark mode, or system mode.
5. Avoid flash of the wrong theme during initial load when the framework allows early theme resolution.
6. Validate contrast, focus states, disabled states, hover states, selected states, charts, badges, and skeleton/loading states in both modes.
7. Do not communicate status by color alone. Icons, labels, or text must still carry meaning across modes.
8. Do not invert images, generated artwork, logos, or user-uploaded media unless the asset is specifically designed for it.
9. Avoid separate one-off shadow systems per mode. Use subtle borders, elevation, and contrast consistently.
10. Do not introduce a heavy theme framework only to support light/dark mode; use the selected stack's normal theming pattern first.

## Performance Expectations

- Optimize the critical path: avoid unnecessary client JavaScript, large unused assets, and render-blocking work.
- Use framework image, font, and bundle optimization features when available.
- Measure before adding complex performance machinery.

## List Data Fetching

Use this section when building list pages, tables, search results, admin indexes, dashboards, feeds, or any UI that displays multiple records.

### Default Rule

List pages must load bounded summary data. Do not request every record and then paginate, filter, search, or sort only on the client.

The backend owns pagination limits. The frontend may choose page size from allowed values, but the API must enforce a default limit and a maximum limit.

### Request Shape

List requests should include only the state needed to reproduce the list:

- page number and page size, or cursor and limit
- search query
- filters
- sort key and direction
- optional lightweight view mode

Persist list state in the URL or another restorable navigation state when users are likely to return to the same list.

### Response Shape

List responses should return:

- summary fields required for the visible row, card, or table
- stable item identifier
- status fields needed for list actions
- pagination metadata, such as total count, next cursor, or has-more

List responses must not include full detail payloads by default. Do not include large text bodies, logs, histories, full child collections, file contents, audit trails, or deeply nested related objects unless the list visibly needs that exact data and the payload remains bounded.

Detail pages should load detail data by ID through a detail query or endpoint. Expanded rows may request extra data lazily for the selected row only.

### Pagination Rules

1. Every dynamic list must have a default page size or limit.
2. Every dynamic list API must enforce a maximum page size or limit.
3. Use server-side filtering, searching, and sorting for data that can grow beyond a small documented bound.
4. Use cursor pagination for changing feeds, infinite scroll, or large datasets where offset pagination becomes unstable or expensive.
5. Offset pagination is acceptable for small and medium admin lists when stable ordering and reasonable limits are enforced.
6. Infinite scroll still needs backend limits, loading boundaries, and an accessible way to reach later content.
7. Static option lists may load all values only when the dataset has a documented small upper bound.

### Prohibited Patterns

- Fetching all records to compute pagination in the browser.
- Fetching all records to run search, filtering, or sorting in the browser when the dataset can grow.
- Returning detail payloads for every list item.
- Returning unbounded child arrays for every list item.
- Triggering one detail request per row on initial list render.
- Hiding an unbounded request behind a loading spinner or skeleton.

### Review Checklist

Before calling a list page done, confirm:

- The list request has a limit, page size, or cursor.
- The backend enforces a default and maximum limit.
- The list response contains only summary fields.
- Detail data loads separately.
- Search, filters, sort, pagination, and return navigation preserve useful state.
- The implementation does not make one extra detail request per visible row unless that behavior is intentional, bounded, and documented.

## Verification

When frontend code exists, `./scripts/check.sh` should eventually run the project-selected checks, such as:

```bash
npm run lint
npm run build
```

For visual or interaction-heavy work, verify in a real browser and record what was checked.
