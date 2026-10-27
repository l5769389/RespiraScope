# Project Structure Refactoring Implementation Plan

> **For agentic workers:** Execute these tasks sequentially in the current checkout. Preserve all existing uncommitted work; do not create commits as part of this task.

**Goal:** Organize RespiraScope by responsibility, with consistent source, static-resource, test, tooling and documentation paths.

**Architecture:** Keep `ct_breath.main`, `ct_breath.app`, `ct_breath.asgi` and `python -m ct_breath` as entry points. Move implementation into core, models, acquisition, processing, binning, recording, streaming, application, api and runtime packages. Shared models must not depend on HTTP or runtime startup.

**Tech Stack:** Python 3.13, uv, FastAPI, Socket.IO, plain JavaScript/ECharts, PyInstaller and Playwright.

**Spec:** This document records the user's requested structure refactor; no product behavior or protocol changes are included.

## Global Constraints

- Preserve current filter/binning behavior and v6 records with v4 binning data.
- Preserve CLI commands, desktop startup, browser routes and external configuration locations.
- No new frontend build tool or mandatory runtime dependency.
- Move current working files; never replace them with Git versions.
- Keep real data, generated reports and screenshots intact when relocating them.

## Review Focus

- A wheel installed outside the checkout must include every UI resource.
- Frozen Windows/macOS builds must resolve the same static-resource tree.
- Tests and report tools must not depend on the previous directory depths.
- Preserve root/subpath HTTP routing, UI imports and vendor paths.
- All existing acquisition, shutdown, padding, editing and storage regressions must still pass.

## Tasks

- [x] Move Python implementations to responsibility-based packages; split shared models and update imports.
- [x] Consolidate `web/{console,monitor,lab,guide,api-docs,shared,assets,vendor}`; update resource resolution and packaging together.
- [x] Organize `tests/{unit,integration,ui,fixtures,support}` and `scripts/{packaging,reports}`; update tools, launch wrappers and test paths.
- [x] Organize developer/API/deployment/technical documentation, reports and screenshots; add a directory guide and correct links.
- [x] Add architecture/resource checks and run backend, browser, wheel and packaging-command validation.

## Verification

- Backend/unit/integration: 223 tests passed.
- Browser interactions using Chrome: 84 tests passed.
- Wheel built successfully; extracted into a temporary install directory and launched outside the checkout. Verified package import location, API health/schema and 11 static/runtime routes.
- Frozen resource destination checked against the PyInstaller command; Windows executable build is not performed on macOS.
- Extracted model definitions are AST-identical; moved processing and binning behavior is unchanged (imports and resource documentation updated).
- Local Markdown links checked; Python sources compile; macOS wrapper passes shell syntax check.
- Existing reports, measurement data and demo assets preserved; report results were not recomputed during this structure refactor.
