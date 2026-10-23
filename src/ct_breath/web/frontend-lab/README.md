# Mock Signal Setup frontend

Lightweight static setup UI for the `RespiraScope` mock signal source.

Start the backend and UI together from the project root:

```bash
uv run respirascope
```

The setup tab is available only when mock signal mode is enabled in the configuration file printed at startup:

```toml
[mock]
enabled = true
```

This page is hosted inside the combined Breath Console. Open the Mock Lab address printed at startup (default):

```text
http://localhost:5175/#lab
```

This page can switch mock patient scenarios, preview generated raw data, call
the backend filter API, and compare raw/filtered/peak/valley results in an interactive chart.

The first scene is previewed on load. Edit the visible signal and filter settings,
then choose Generate Preview; this does not change the live signal. Apply to Live
Monitor sends only signal parameters and opens the realtime monitor. Filter
settings in this page affect previews only.

Offline previews use the same baseline-preserving, forward-backward low-pass
filter as record analysis, regardless of binning mode. A single-handle slider
sets the upper cutoff (0.01–20 Hz, strictly below half the sampling rate), with
Hz and BPM displayed to two decimal places. Defaults are 2.00 Hz, order 4 and
Gaussian sigma 1.00. Peak sensitivity uses the same Conservative, Standard and
Sensitive options as record analysis. Time, fixed-amplitude and relative-amplitude
binning share the filtered curve; switching binning does not re-filter it.

The chart has a time axis in seconds, hover values, clickable legend and a zoom
slider. Scenario thumbnails load once, on demand when expanded. Pending changes,
processing and request failures are visible; failed previews retain the last
successful chart. Preview duration is 6–300 seconds, and input limits match the
API's filter constraints.

This page is not the user-facing realtime monitor. The Monitor tab lives in
`frontend-monitor` and does not expose mock signal settings.
