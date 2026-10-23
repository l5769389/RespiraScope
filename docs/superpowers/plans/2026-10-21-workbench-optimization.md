# Workbench and API Optimization Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with focused review before completion.

**Goal:** Improve offline analysis usability, record transport efficiency, invalid-input feedback, and startup isolation.

**Architecture:** Keep existing signal processing and export algorithms. Reuse the version 5 record serializer for opt-in compact HTTP transport; retain legacy responses. Improve the existing vanilla JS controls and shared styles without replacing the app.

**Tech Stack:** uv, FastAPI/Pydantic, vanilla JS/ECharts, pytest/Playwright.

**Spec:** User request in this conversation: optimize UI and API together; preserve existing capture/filter/binning behavior.

## Global Constraints
- Preserve uncommitted project work and existing record import compatibility.
- Do not restart or modify the user's active acquisition instance without preserving its state.
- Keep frequency controls and binning offline; no new realtime settings.
- Existing endpoints remain compatible unless requests explicitly negotiate compact records.

## Review Focus
- Non-default filter settings must survive record end and import.
- Invalid/nonfinite/unordered sample pairs return 422 rather than 500.
- Legacy clients and old backend fallback continue to work.
- Pending edits, errors, and undo must not change committed waveforms.
- Concurrent wildcard/loopback listeners must not shadow another instance.

## Tasks
- [x] API: test compact record negotiation, retained timestamps/filter config, payload reduction, legacy format, gzip and invalid input. Implement schema validation, compact response, shared error reader and frontend import of the response. Run targeted backend/UI tests.
- [x] Offline interaction: add tests for discard, pending/processing/applied/error states, readable API errors, preserving failures through redraw. Implement transactional feedback and local discard.
- [x] UI: group binning/filter controls, compact help, improve responsive action/status layout and translated labels. Validate actual mouse/keyboard flows at desktop/mobile widths with screenshots outside the repo.
- [x] Startup: reproduce wildcard/loopback port shadowing; strengthen availability check and test occupied/free ports.
- [x] Verification: run backend and UI regressions; review the scoped change; document measured payload savings and remaining deployment requirements. Do not commit automatically.

## Verification Results
- Backend regression suite: 78 passed. Browser regression suite: 26 passed, including desktop/mobile layout, pending/discard/error feedback, import/export, custom bands and record lifecycle.
- Review fixes: nonfinite inputs return small 422 responses; compact negotiation honors quality weights and rejects q=0.
- One-minute simulated record (3,000 points): legacy 321,939 bytes, compact 85,919 bytes (73.3% smaller), gzip 16,446 bytes. Raw/filter values, existing timestamps, filter settings and bins retained.
- Existing user-owned acquisition process was not restarted. Backend changes take effect after the current record is saved/finished and the uv service is restarted.
