"""Static CSS and JavaScript for observability HTML renderers."""

from __future__ import annotations

DASHBOARD_STYLE = """    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1d2430;
      --muted: #606b7a;
      --line: #d9dee7;
      --accent: #147d75;
      --accent-2: #945f00;
      --accent-3: #8d3c61;
      --table: #fbfcfd;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 15px;
      line-height: 1.45;
      letter-spacing: 0;
      color: var(--text);
      background: var(--bg);
    }
    .shell {
      width: min(1280px, calc(100% - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }
    header {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: end;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0;
      font-size: 28px;
      font-weight: 720;
      line-height: 1.1;
    }
    .meta {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      margin: 18px 0;
      border: 1px solid var(--line);
      background: var(--line);
    }
    .summary-cell {
      min-height: 84px;
      padding: 14px 16px;
      background: var(--panel);
    }
    .summary-cell span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .summary-cell strong {
      display: block;
      margin-top: 8px;
      font-size: 26px;
      line-height: 1.1;
    }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(240px, 1fr) 180px;
      gap: 12px;
      margin: 18px 0 12px;
    }
    input,
    select {
      min-height: 40px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      color: var(--text);
      background: var(--panel);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
    }
    th,
    td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: middle;
    }
    th {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0;
      background: var(--table);
      white-space: nowrap;
    }
    td.numeric,
    th.numeric {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    tr:last-child td { border-bottom: 0; }
    a {
      color: var(--accent);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }
    .kind {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f7faf9;
      color: #145f59;
      font-size: 12px;
      white-space: nowrap;
    }
    .bars {
      display: grid;
      gap: 6px;
      min-width: 150px;
    }
    .bar-track {
      height: 8px;
      background: #edf0f4;
      border-radius: 999px;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      background: var(--accent);
    }
    .bar-fill.runs { background: var(--accent-2); }
    .bar-label {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }
    .links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
    }
    .section-heading {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
      margin: 28px 0 10px;
    }
    h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
    }
    .section-heading span {
      color: var(--muted);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }
    .empty {
      display: none;
      padding: 24px;
      color: var(--muted);
      background: var(--panel);
      border: 1px solid var(--line);
      border-top: 0;
    }
    @media (max-width: 820px) {
      .shell { width: min(100% - 20px, 1280px); padding-top: 14px; }
      header { grid-template-columns: 1fr; align-items: start; }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .toolbar { grid-template-columns: 1fr; }
      table { display: block; overflow-x: auto; white-space: nowrap; }
    }
"""

DASHBOARD_SCRIPT = """    const search = document.getElementById("search");
    const kind = document.getElementById("kind");
    const experimentRows = Array.from(document.querySelectorAll("#experiments tr"));
    const metricRows = Array.from(document.querySelectorAll("#metrics tr"));
    const empty = document.getElementById("empty");
    const metricsEmpty = document.getElementById("metrics-empty");
    function filterRows(rows, emptyElement, needle, selectedKind) {
      let visible = 0;
      for (const row of rows) {
        const matchesText = !needle || row.dataset.name.includes(needle);
        const matchesKind = !selectedKind || row.dataset.kind === selectedKind;
        const show = matchesText && matchesKind;
        row.hidden = !show;
        if (show) visible += 1;
      }
      emptyElement.style.display = visible ? "none" : "block";
    }
    function applyFilters() {
      const needle = search.value.trim().toLowerCase();
      const selectedKind = kind.value;
      filterRows(metricRows, metricsEmpty, needle, selectedKind);
      filterRows(experimentRows, empty, needle, selectedKind);
    }
    search.addEventListener("input", applyFilters);
    kind.addEventListener("change", applyFilters);
"""

RUN_DETAIL_STYLE = """    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #1d2430;
      --muted: #606b7a;
      --line: #d9dee7;
      --accent: #147d75;
      --warn: #945f00;
      --bad: #a53d47;
      --code: #f1f4f8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 15px;
      line-height: 1.45;
      letter-spacing: 0;
      color: var(--text);
      background: var(--bg);
    }
    .shell {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }
    header {
      display: grid;
      gap: 10px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0;
      font-size: 26px;
      line-height: 1.15;
      font-weight: 720;
      overflow-wrap: anywhere;
    }
    h2 {
      margin: 26px 0 10px;
      font-size: 18px;
      line-height: 1.2;
    }
    .meta,
    .links {
      color: var(--muted);
      overflow-wrap: anywhere;
    }
    .links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
    }
    a {
      color: var(--accent);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      margin: 18px 0;
      border: 1px solid var(--line);
      background: var(--line);
    }
    .summary-cell {
      min-height: 80px;
      padding: 14px 16px;
      background: var(--panel);
    }
    .summary-cell span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .summary-cell strong {
      display: block;
      margin-top: 8px;
      font-size: 24px;
      line-height: 1.1;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
    }
    th,
    td {
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    th {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      white-space: nowrap;
    }
    td.numeric { text-align: right; font-variant-numeric: tabular-nums; }
    .status {
      display: inline-flex;
      min-height: 23px;
      align-items: center;
      padding: 2px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: #145f59;
      background: #f7faf9;
      font-size: 12px;
      white-space: nowrap;
    }
    .status.failed,
    .status.error {
      color: var(--bad);
      background: #fff5f5;
    }
    .empty {
      padding: 16px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--muted);
    }
    pre {
      margin: 0;
      padding: 14px;
      overflow: auto;
      border: 1px solid var(--line);
      background: var(--code);
      font-size: 13px;
      line-height: 1.45;
      max-height: 560px;
    }
    @media (max-width: 820px) {
      .shell { width: min(100% - 20px, 1180px); padding-top: 14px; }
      .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      table { display: block; overflow-x: auto; white-space: nowrap; }
    }
"""
