# Mock Signal Setup frontend

Lightweight static setup UI for the `RespiraScope` mock signal source.

Start the backend first:

```bash
uv run RespiraScope
```

The setup tab is available only when mock signal mode is enabled in
`D:/ct/breath-config/breath.toml`:

```toml
[mock]
enabled = true
```

In normal dev/prod runs this page is hosted inside the combined Breath Console.
For manual static serving of this folder only:

```bash
uv run python -m http.server 5174 -d frontend-lab
```

Open:

```text
http://localhost:5174
```

This page can switch mock patient scenarios, preview generated raw data, call
the backend filter API, and draw raw/filtered/peak/valley results on canvas.

This page is not the user-facing realtime monitor. The Monitor tab lives in
`frontend-monitor` and does not expose mock signal settings.
