# Release review dossier

## Direction

A steel-blue release dossier with a numbered section index, hard rules between evidence blocks and stamped policy verdicts. The public page reads as an inspection file, with findings arranged as rows rather than a metric-card grid.

## Outside reference

[GOV.UK task list guidance](https://design-system.service.gov.uk/components/task-list/), inspected on 2026-10-22. Design takeaway: Task names and adjacent statuses should make completed and outstanding work easy to distinguish.

This is an original composition and stylesheet. No reference-site code, logos, photographs or proprietary fonts were imported. Fonts use local system stacks; diagrams are original SVG/CSS. No new runtime dependency or third-party request was added.

## Data and behavior

Pass/block verdicts remain responses from the verifier. The public cover says recorded evidence. The styling review verifies the existing signed scanner bundle and checks its actual blocking advisories. It does not claim that a new scanner campaign was run.

API contracts, authorization, persistence, core algorithms and benchmark datasets were not changed. Existing benchmark outputs remain historical. UI verification and new recordings are saved separately under [docs/results/ui-redesign](results/ui-redesign/).

## Interaction and access

Buttons retain their existing actions and accessible labels. Keyboard focus is visible. Layouts collapse for narrow screens; wide evidence tables scroll inside their own containers. Color is paired with text for status. Motion respects prefers-reduced-motion.

## Review artifacts

- [Actual console](results/ui-redesign/console-desktop.png)
- [Mobile console](results/ui-redesign/console-mobile.png)
- [Browser flow results](results/ui-redesign/browser.json)
- [New console recording](results/ui-redesign/demo.webm)
- [Recording probe](results/ui-redesign/demo-probe.json)
- [Frontend build log](results/ui-redesign/frontend-build.log)

The saved [review-console.py](results/ui-redesign/review-console.py) is the existing real-service browser flow adapted to write into the UI review directory. Run it only against an isolated local demo stack with the normal operator environment configured. Historical performance is not rebenchmarked by this visual review.

Public evidence preview: [desktop](results/ui-redesign/site-desktop.png), [mobile](results/ui-redesign/site-mobile.png), [checks](results/ui-redesign/site-review.json). Publication is a separate approval step.

## Verification disposition

Final build, lint and existing test suites pass. The redesigned console was exercised against actual isolated local services, not mocked counters. The public-page previews use saved evidence and the new actual recording. Remote CI for these UI commits awaits publishing approval.

[The initial review-harness failure](results/ui-redesign/initial-console-review.log) came from an incorrect expectation that the existing attestation had expired. The actual valid bundle correctly blocked its High advisories. The original advisory assertion was restored and the full real-service browser flow passed; no verifier behavior was changed.
