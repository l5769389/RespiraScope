# Breath simulation and detection upgrade plan

## Goal

Build a repeatable local workflow for testing breath filtering and peak/valley detection:

1. Keep the backend runnable as a pure uv project.
2. Add a backend-local test UI that can preview simulated patient states and filtering results.
3. Expose mock-sensor controls through HTTP APIs so the backend lab can switch patient states.
4. Make peak/valley detection less dependent on hand-tuned BPM and prominence values.
5. Extend the mock breath generator to cover common signal conditions seen in real patient data.

## Current State

- The backend mock sensor currently emits a synthetic sine-like signal over TCP.
- The backend filters data with a Butterworth band-pass filter and Gaussian smoothing.
- Peak detection already uses `scipy.signal.find_peaks`.
- Realtime frontend page displays raw, filtered, peak, and valley series.
- Record page can reload saved records and apply a new filter config.

## Backend Changes

- Add configurable mock patient scenarios:
  - `normal`: stable adult breathing.
  - `tachypnea`: fast shallow breathing.
  - `bradypnea`: slow deep breathing.
  - `shallow`: low-amplitude breathing.
  - `irregular`: variable breath interval and amplitude.
  - `apnea`: repeating pause windows.
  - `noisy`: high sensor noise.
  - `motion_artifact`: transient baseline spikes.
- Add HTTP APIs:
  - `GET /mock/scenarios`
  - `GET /mock/config`
  - `POST /mock/config`
  - `POST /mock/preview`
- Add adaptive peak/valley detection:
  - derive minimum peak distance from `sampling_rate` and `high_bpm`.
  - derive prominence from recent filtered signal amplitude when auto mode is enabled.
  - calculate BPM from sequence numbers instead of wall-clock callback time.

## Frontend Changes

- Breath Filter Lab:
  - backend-local internal lab for setting mock patient scenarios.
  - preview the whole generated mock signal.
  - preview the filtered signal and detected peaks/valleys.
- User realtime monitor:
  - lives in this backend project as `frontend-monitor/`.
  - does not expose mock patient controls.
  - subscribes to realtime filtered data, peaks, valleys, and metrics.
- Runtime config:
  - `D:/ct/breath-config/breath.toml` is the primary external runtime config.
  - `[mock].enabled = true` starts the mock TCP signal server and registers `/mock/*`.
  - `[mock].enabled = false` expects an external sensor stream and keeps the lab/mock APIs disabled.
  - `[sensor]` configures the breath device host and port.
  - `[backend]`, `[lab]`, and `[monitor]` configure local service ports.
- Realtime breath page:
  - add auto peak detection toggle.
  - display current BPM and signal quality from backend metrics.
- Breath record page:
  - allow re-filtering with auto peak detection.
  - show returned detection metrics when available.

## Backend-local Test UI

Create `frontend-lab/` inside this backend project. It is a lightweight static page that talks to the backend APIs and can be opened directly or served with:

```bash
uv run python -m http.server 5174 -d frontend-lab
```

It is intentionally independent from `ct-mock-ui`, so filtering and simulation work can be debugged even when the main frontend is not running.

## Backend-local Realtime Monitor

Create `frontend-monitor/` inside this backend project. It is a lightweight
user-facing monitor that subscribes to the backend Socket.IO namespace and
renders raw data, filtered data, detected peaks/valleys, BPM, and breathing
stability with ECharts.

```bash
uv run python -m http.server 5175 -d frontend-monitor
```

It is intentionally separate from `frontend-lab`: the monitor observes realtime
data only, while the lab owns mock scenario setup and filter debugging.

## Validation

- `uv lock --check`
- `uv run --frozen python -m compileall src`
- `uv run --frozen python -c "from ct_breath.app import create_app; print(create_app().title)"`
- Syntax check for the static monitor JavaScript.
- Manual check:
  - switch mock scenarios.
  - preview filtered data.
  - observe raw/filtered/peak/valley markers.
