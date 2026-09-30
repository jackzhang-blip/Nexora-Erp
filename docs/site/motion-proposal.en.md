# Website motion and interactive sandbox

[简体中文](motion-proposal.zh-CN.md) · [Development guide](../development.en.md)

This describes the implemented light website showcase. It uses local sample data without contacting the ERP service. GitHub Pages remains disabled. Website styles do not affect the desktop application.

## Windows and scrolling

Three independent application windows retain sidebars, toolbars, tables, silver edges and subtle reflections. The desktop scene spans about 340vh with a viewport-height sticky stage. The main headline leaves through normal page scrolling. A single progress mapping controls the scene; reverse scrolling and direct jumps never perform business operations.

| Progress | Composition and connection |
| --- | --- |
| 0–20% | Centered receipt at about 85% width; stock and finance remain hidden to the right and cannot receive focus. |
| 20–38% | Receipt moves left and shrinks; stock enters from the right to form an approximate 40% / 60% pair. |
| 34–43% | First path draws from the receipt anchor to the inventory row. |
| 38–52% | Pair holds for reading and interaction; the node reaches the stock row. |
| 52–70% | Finance enters from the right; final widths are approximately 27% / 44% / 27%, leaving gaps. |
| 66–80% | Second path draws to the payable source, followed by its node. |
| 85–95% | Reverse nodes trace finance → inventory → receipt. |
| 95–100% | Completed relationship holds, then the sticky stage naturally releases into feature/progress content. |

Desktop uses native WebGL. The GPU projects silver frames, with shaders producing metallic highlights, contact shadows and fading reflections. A second transparent canvas renders teal connection ribbons and traveling nodes. HTML windows and the GPU share a 1800px perspective distance and scroll layout. Forms remain native interactive controls, and canvases never intercept pointer events.

Paths follow actual transformed source anchors. Inventory paths meet row edges rather than crossing quantity text. During focused editing, links move behind the windows while continuing to follow their anchors, leaving forms unobstructed. Hide links for filtered/invisible source rows, drafts or mismatched documents. Mobile uses SVG links traveling vertically along window edges. Nodes do not loop indefinitely.

## Business interaction

- Receipts: multiple documents, new/copy drafts, two suppliers, two warehouses, four materials, line addition/removal, date, quantity, unit price and confirmation. Confirmed receipts are read-only.
- Inventory: filter movements by warehouse, material or source number; inspect running and aggregate warehouse/material balances. Source links open the original receipt. Source filtering affects movements, while balances still represent the selected warehouse/material totals.
- Finance: filter by supplier, source number and payment status; inspect source/line detail, record partial payments or settle the remaining balance, and inspect payment history. Overpayment is rejected.
- Initial DEMO-001 contains Material A, quantity 12, unit price ¥10.00, stock +12 and payable ¥120.00. Opening stock is zero.
- Drafts create no stock or payable records. Confirmation is one pure state transition and cannot repeat. Payments only change paid/remaining amounts and payment history.
- Quantities use three fixed decimals; unit prices and payments use two. Round each line to cents before summing. Overflow, invalid dates and invalid numbers are rejected without replacing the previous business state.

## Focus, pause and data lifetime

Expand controls, navigation or source links enlarge the selected window to about 85% width over approximately 450ms, moving other windows to the sides. Manual mode prevents scrolling from replacing the current view. Input focus freezes the camera. Overview shows the three windows; Resume scroll aligns to current progress over about 300ms. Step buttons enter manual mode; exploring never requires completing business tasks.

Business data lives in page memory. Same-tab language links transfer data once via sessionStorage, deleting it when consumed. Refresh/reset restores the seed. Navigation remains available without storage, but restarts the demo. Restoration validates versions, document states, IDs, catalog values and payment balances.

## Implementation boundary

| File | Responsibility |
| --- | --- |
| `sandbox.mjs` | Pure business model, fixed-point amounts, derived stock/payables and transfer validation. |
| `sandbox-ui.mjs` | Bilingual HTML, forms, filters, source navigation and local language transfer. |
| `motion.mjs` | Sequential entry, focus, pause/resume, paths and media preferences. |
| `webgl-stage.mjs` | GPU projection, metallic frames, shadows/reflections, ribbon paths, nodes and context recovery. |
| `sandbox.css` | Independent window/stage styles, container queries, mobile and print. |

Native controls support keyboard interaction. Errors are linked to fields and results announced in a status region. Hidden/receded windows cannot take focus. Demand-driven requestAnimationFrame batches updates, with no continuous loop while idle, off-screen or hidden. Teardown removes listeners and observers.

WebGL initializes on the first dynamic desktop frame. Pixel density is capped at 2 and constrained by GPU renderbuffer limits. Initialization/shader failure or context loss immediately retains the HTML/CSS/SVG view without resetting business data. Context restoration rebuilds resources and requests a frame from current state; teardown releases programs and buffers. See the [WebGL interface](https://developer.mozilla.org/en-US/docs/Web/API/WebGLRenderingContext) and [context-loss testing extension](https://developer.mozilla.org/en-US/docs/Web/API/WEBGL_lose_context).

Mobile uses vertically stacked windows with a subtle visibility reveal and no sticky stage. All business operations remain available; wide tables scroll inside their windows. Reduced motion removes movement/perspective while retaining interaction and static links. Without JavaScript, static examples and documentation remain readable; demo controls do not perform operations.

## Verification

Automated coverage includes multiple materials/warehouses, rounding, duplicate confirmation, immutable confirmed documents, partial/excess payments, failure atomicity, language restoration, stage boundaries, reverse scrolling and direct jumps. Browser acceptance covers both languages, 1440×900 / 1280×720 desktop, 390px mobile, focused forms, tracing, pause/resume, reduced motion and no-script reading. Continuous scroll capture is stored in the task preview directory, not committed with the website.
