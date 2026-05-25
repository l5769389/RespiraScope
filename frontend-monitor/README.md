# Breath Monitor

User-facing realtime monitor for the `RespiraScope` backend.

This project is intentionally separate from `frontend-lab`:

- `frontend-lab` is for backend debugging and mock signal setup.
- `frontend-monitor` is for users to watch realtime raw data, filtered data,
  detected peaks/valleys, BPM, and breathing stability.

It does not expose mock patient or simulated signal controls.

## Features

- Realtime raw and filtered waveform display.
- Visible peak and valley markers.
- Optional delayed peak/valley confirmation for better realtime marker accuracy.
- Live follow mode with a fixed-width moving window, plus data-zoom review for
  recent realtime data.
- Local segment capture with `Record Start` and `Record End`; captured raw data
  is re-filtered through the backend offline filter when the segment ends.
- Configurable pre/post record padding. Saved files distinguish auxiliary
  `pre` / `post` samples from the true `record` range.
- Display-only smoothing modes for the filtered waveform.
- Start-time no-data detection through `/stream/status`, with disabled recording
  until raw breath data actually arrives.

## Start

Start the backend first:

```bash
uv run RespiraScope
```

Serve this folder:

```bash
uv run python -m http.server 5175 -d frontend-monitor
```

Or start the full dev environment from the project root:

```powershell
.\scripts\dev.ps1
```

Open:

```text
http://localhost:5175
```

The monitor uses local vendored copies of ECharts and Socket.IO client, so it
does not require CDN access.
