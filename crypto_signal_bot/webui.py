"""
Interactive Web UI for the Crypto Futures Signal Bot.

Runs a local Flask server that serves a full-featured, interactive dashboard
allowing users to:

  - Choose any supported trading pair from a searchable dropdown
  - Choose one or more timeframes (1m, 5m, 15m, 30m, 1h, 4h, 1d)
  - Trigger on-demand live analysis with a single click
  - Enable auto-refresh for continuous real-time monitoring

Usage
-----
    python -m crypto_signal_bot.webui            # default: http://localhost:5000
    python -m crypto_signal_bot.webui --port 8080
    python -m crypto_signal_bot.webui --host 0.0.0.0 --port 5000
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

from crypto_signal_bot.config.settings import ALL_PAIRS, ALL_TIMEFRAMES
from crypto_signal_bot.main import _serialise, run_analysis
from crypto_signal_bot.utils.logger import get_logger

logger = get_logger(__name__)

app = Flask(__name__, static_folder=None)
CORS(app)  # Allow cross-origin requests (useful for local dev)

# ---------------------------------------------------------------------------
# HTML dashboard (inline – no extra static files required)
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Crypto Signal Bot – Interactive Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg:        #0d1117;
      --surface:   #161b22;
      --surface2:  #1c2128;
      --border:    #30363d;
      --text:      #e6edf3;
      --muted:     #8b949e;
      --long:      #3fb950;
      --short:     #f85149;
      --notrade:   #8b949e;
      --accent:    #58a6ff;
      --warn:      #d29922;
      --radius:    10px;
    }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      min-height: 100vh;
    }

    /* ── Header ── */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex;
      align-items: center;
      gap: 1rem;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    header .logo { font-size: 1.6rem; }
    header h1   { font-size: 1.15rem; font-weight: 700; letter-spacing: -0.02em; }
    header .subtitle { font-size: 0.75rem; color: var(--muted); }
    header .spacer  { flex: 1; }
    .status-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: var(--muted);
      display: inline-block;
      margin-right: 4px;
    }
    .status-dot.live { background: var(--long); animation: pulse 2s infinite; }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.4; }
    }
    #status-text { font-size: 0.75rem; color: var(--muted); }

    /* ── Control panel ── */
    .control-panel {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 1.25rem 2rem;
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: flex-end;
    }
    .ctrl-group { display: flex; flex-direction: column; gap: 0.35rem; }
    .ctrl-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }

    /* search/select combo */
    .pair-search-wrap { position: relative; min-width: 200px; }
    #pair-search {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.5rem 0.75rem;
      color: var(--text);
      font-size: 0.875rem;
      outline: none;
    }
    #pair-search:focus { border-color: var(--accent); }
    #pair-dropdown {
      position: absolute;
      top: calc(100% + 4px);
      left: 0; right: 0;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 6px;
      max-height: 220px;
      overflow-y: auto;
      z-index: 200;
      display: none;
    }
    #pair-dropdown.open { display: block; }
    .dd-item {
      padding: 0.45rem 0.75rem;
      cursor: pointer;
      font-size: 0.85rem;
    }
    .dd-item:hover, .dd-item.selected { background: rgba(88,166,255,0.1); color: var(--accent); }

    /* timeframe chips */
    .tf-chips { display: flex; gap: 0.4rem; flex-wrap: wrap; }
    .tf-chip {
      padding: 0.3rem 0.7rem;
      border-radius: 99px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--muted);
      font-size: 0.75rem;
      cursor: pointer;
      transition: all 0.15s;
      user-select: none;
    }
    .tf-chip:hover  { border-color: var(--accent); color: var(--accent); }
    .tf-chip.active { border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,0.1); font-weight: 600; }

    /* buttons */
    .btn {
      padding: 0.5rem 1.2rem;
      border-radius: 6px;
      border: none;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s, transform 0.1s;
    }
    .btn:active { transform: scale(0.97); }
    .btn-primary { background: var(--accent); color: #0d1117; }
    .btn-primary:hover { opacity: 0.9; }
    .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
    .btn-secondary { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }
    .btn-secondary:hover { border-color: var(--accent); }
    .btn-secondary.active { border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,0.08); }

    /* auto-refresh toggle */
    .refresh-row { display: flex; gap: 0.5rem; align-items: center; }
    #auto-interval {
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.45rem 0.6rem;
      color: var(--text);
      font-size: 0.82rem;
      outline: none;
    }
    #auto-interval:focus { border-color: var(--accent); }

    /* filter chips (signal type) */
    .filter-bar {
      padding: 0.85rem 2rem;
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
      align-items: center;
      border-bottom: 1px solid var(--border);
    }
    .filter-label { font-size: 0.75rem; color: var(--muted); margin-right: 0.2rem; }
    .chip {
      padding: 0.3rem 0.85rem;
      border-radius: 99px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--muted);
      font-size: 0.75rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover, .chip.active { border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,0.08); }
    .chip.active { font-weight: 600; }

    /* ── Summary bar ── */
    .summary-bar {
      display: flex; gap: 1.5rem;
      padding: 0.65rem 2rem;
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
    }
    .summary-item { font-size: 0.8rem; }
    .summary-item .lbl { color: var(--muted); }
    .summary-item .val { font-weight: 700; margin-left: 0.35rem; }
    .val.long    { color: var(--long); }
    .val.short   { color: var(--short); }
    .val.notrade { color: var(--muted); }

    /* ── Grid ── */
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 1rem;
      padding: 1.25rem 2rem 2rem;
    }

    /* ── Card ── */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
      transition: transform 0.15s, box-shadow 0.15s;
    }
    .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.85rem 1rem;
      border-bottom: 1px solid var(--border);
    }
    .pair-name { font-size: 1rem; font-weight: 700; letter-spacing: 0.02em; }
    .timeframe-badge {
      font-size: 0.7rem; font-weight: 600;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      background: rgba(88,166,255,0.12);
      color: var(--accent);
    }
    .signal-badge {
      display: inline-flex; align-items: center; gap: 0.35rem;
      padding: 0.4rem 1rem;
      border-radius: 99px;
      font-size: 0.85rem; font-weight: 700; letter-spacing: 0.04em;
      margin: 0.85rem 1rem 0.5rem;
    }
    .signal-badge.LONG    { background: rgba(63,185,80,0.15);  color: var(--long);    border: 1px solid rgba(63,185,80,0.3); }
    .signal-badge.SHORT   { background: rgba(248,81,73,0.15);  color: var(--short);   border: 1px solid rgba(248,81,73,0.3); }
    .signal-badge.NOTRADE { background: rgba(139,148,158,0.12); color: var(--notrade); border: 1px solid rgba(139,148,158,0.25); }

    .prices {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 0.5rem;
      padding: 0.5rem 1rem 0.75rem;
    }
    .price-block { text-align: center; }
    .price-label { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
    .price-value { font-size: 0.9rem; font-weight: 600; margin-top: 0.15rem; }
    .price-value.entry { color: var(--accent); }
    .price-value.sl    { color: var(--short); }
    .price-value.tp    { color: var(--long); }

    .stats {
      display: grid; grid-template-columns: 1fr 1fr;
      gap: 0; border-top: 1px solid var(--border);
    }
    .stat {
      padding: 0.55rem 1rem;
      border-bottom: 1px solid var(--border);
      border-right: 1px solid var(--border);
    }
    .stat:nth-child(even) { border-right: none; }
    .stat-label { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .stat-value { font-size: 0.82rem; font-weight: 600; margin-top: 0.1rem; }
    .trend-UPTREND   { color: var(--long); }
    .trend-DOWNTREND { color: var(--short); }
    .trend-RANGE     { color: var(--warn); }

    .confidence-row { padding: 0.6rem 1rem 0.8rem; border-top: 1px solid var(--border); }
    .conf-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; }
    .conf-label  { font-size: 0.7rem; color: var(--muted); }
    .conf-pct    { font-size: 0.82rem; font-weight: 700; }
    .conf-bar-bg   { background: var(--border); border-radius: 99px; height: 5px; }
    .conf-bar-fill { height: 5px; border-radius: 99px; transition: width 0.6s ease; }

    .sr-row {
      padding: 0.5rem 1rem 0.75rem;
      border-top: 1px solid var(--border);
      font-size: 0.72rem;
      display: flex; gap: 1rem;
    }
    .sr-group { flex: 1; }
    .sr-title { color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.2rem; }
    .sr-val   { font-weight: 600; }
    .sr-val.res { color: var(--short); }
    .sr-val.sup { color: var(--long); }

    .score-details { padding: 0.5rem 1rem 0.75rem; border-top: 1px solid var(--border); }
    .score-title { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.35rem; }
    .score-items { display: flex; flex-wrap: wrap; gap: 0.3rem; }
    .score-item  { font-size: 0.65rem; padding: 0.15rem 0.5rem; border-radius: 4px; }
    .score-pos   { background: rgba(63,185,80,0.12); color: var(--long); }
    .score-neg   { background: rgba(248,81,73,0.12); color: var(--short); }

    /* ── Skeleton / Loading ── */
    .skeleton-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.5rem;
      display: flex; flex-direction: column; gap: 0.75rem;
    }
    .skel { background: var(--border); border-radius: 4px; animation: shimmer 1.2s linear infinite; }
    .skel-h  { height: 18px; }
    .skel-sm { height: 12px; }
    @keyframes shimmer {
      0%   { opacity: 1; }
      50%  { opacity: 0.4; }
      100% { opacity: 1; }
    }

    /* ── Empty / error ── */
    .empty {
      grid-column: 1 / -1; text-align: center;
      padding: 4rem 2rem; color: var(--muted);
    }
    .empty .icon { font-size: 3rem; display: block; margin-bottom: 1rem; }
    .empty p { font-size: 0.9rem; }

    #error-banner {
      display: none;
      background: rgba(248,81,73,0.1);
      border: 1px solid rgba(248,81,73,0.35);
      border-radius: var(--radius);
      margin: 1rem 2rem;
      padding: 1rem;
      color: var(--short);
      font-size: 0.85rem;
    }

    /* ── Responsive ── */
    @media (max-width: 640px) {
      header { flex-wrap: wrap; }
      .control-panel { flex-direction: column; padding: 1rem; }
      .grid { padding: 0.75rem 1rem 1.5rem; }
      .filter-bar, .summary-bar { padding: 0.65rem 1rem; }
    }
  </style>
</head>
<body>

<header>
  <span class="logo">📡</span>
  <div>
    <h1>Crypto Signal Bot</h1>
    <div class="subtitle">Interactive real-time analysis · Futures signals · No trades executed</div>
  </div>
  <div class="spacer"></div>
  <div>
    <span class="status-dot" id="status-dot"></span>
    <span id="status-text">Ready</span>
  </div>
</header>

<!-- ── Control panel ── -->
<div class="control-panel">

  <!-- Pair search -->
  <div class="ctrl-group">
    <span class="ctrl-label">Coin / Pair</span>
    <div class="pair-search-wrap">
      <input id="pair-search" type="text" placeholder="Search pair…" autocomplete="off" />
      <div id="pair-dropdown"></div>
    </div>
  </div>

  <!-- Timeframes -->
  <div class="ctrl-group">
    <span class="ctrl-label">Timeframes</span>
    <div class="tf-chips" id="tf-chips"></div>
  </div>

  <!-- Analyse button -->
  <div class="ctrl-group">
    <span class="ctrl-label">&nbsp;</span>
    <button class="btn btn-primary" id="btn-analyze" disabled>⚡ Analyse</button>
  </div>

  <!-- Auto-refresh -->
  <div class="ctrl-group">
    <span class="ctrl-label">Auto-refresh</span>
    <div class="refresh-row">
      <button class="btn btn-secondary" id="btn-auto" title="Toggle auto-refresh">🔁 Off</button>
      <select id="auto-interval">
        <option value="30">30 s</option>
        <option value="60" selected>1 min</option>
        <option value="300">5 min</option>
        <option value="900">15 min</option>
      </select>
    </div>
  </div>

</div>

<div id="error-banner"></div>

<!-- ── Signal filter ── -->
<div class="filter-bar" id="filter-bar" style="display:none">
  <span class="filter-label">Filter:</span>
  <button class="chip active" data-filter="ALL">All</button>
  <button class="chip" data-filter="LONG">🟢 Long</button>
  <button class="chip" data-filter="SHORT">🔴 Short</button>
  <button class="chip" data-filter="NO TRADE">⚪ No Trade</button>
</div>

<!-- ── Summary bar ── -->
<div class="summary-bar" id="summary-bar" style="display:none"></div>

<!-- ── Cards grid ── -->
<div class="grid" id="grid">
  <div class="empty">
    <span class="icon">🔍</span>
    <p>Select a pair and timeframes, then click <strong>Analyse</strong> to get live signals.</p>
  </div>
</div>

<script>
  // ── State ──────────────────────────────────────────────────────────────────
  let allPairs      = [];
  let allTimeframes = [];
  let selectedPair  = '';
  let selectedTFs   = new Set();
  let allSignals    = [];
  let activeFilter  = 'ALL';
  let autoTimer     = null;
  let isLoading     = false;

  // ── Boot ───────────────────────────────────────────────────────────────────
  async function boot() {
    try {
      const [pRes, tRes] = await Promise.all([
        fetch('/api/pairs'),
        fetch('/api/timeframes'),
      ]);
      allPairs      = await pRes.json();
      allTimeframes = await tRes.json();
    } catch(e) {
      showError('Failed to load configuration: ' + e.message);
      return;
    }
    buildPairDropdown();
    buildTfChips();
  }

  // ── Pair search / dropdown ─────────────────────────────────────────────────
  function buildPairDropdown() {
    renderDropdown(allPairs);

    const input = document.getElementById('pair-search');
    const dd    = document.getElementById('pair-dropdown');

    input.addEventListener('focus', () => {
      renderDropdown(filterPairs(input.value));
      dd.classList.add('open');
    });
    input.addEventListener('input', () => {
      renderDropdown(filterPairs(input.value));
      dd.classList.add('open');
    });
    document.addEventListener('click', e => {
      if (!e.target.closest('.pair-search-wrap')) dd.classList.remove('open');
    });
  }

  function filterPairs(q) {
    if (!q) return allPairs;
    const u = q.toUpperCase();
    return allPairs.filter(p => p.toUpperCase().includes(u));
  }

  function renderDropdown(pairs) {
    const dd = document.getElementById('pair-dropdown');
    dd.innerHTML = pairs.map(p => `
      <div class="dd-item${p === selectedPair ? ' selected' : ''}"
           data-pair="${p}">${p}</div>`).join('');
    dd.querySelectorAll('.dd-item').forEach(el => {
      el.addEventListener('click', () => {
        selectedPair = el.dataset.pair;
        document.getElementById('pair-search').value = selectedPair;
        dd.classList.remove('open');
        refreshAnalyzeBtn();
      });
    });
  }

  // ── Timeframe chips ────────────────────────────────────────────────────────
  function buildTfChips() {
    const container = document.getElementById('tf-chips');
    // Default: select 1m, 5m, 15m
    const defaults = new Set(['1m', '5m', '15m']);
    allTimeframes.forEach(tf => {
      if (defaults.has(tf)) selectedTFs.add(tf);
      const btn = document.createElement('button');
      btn.className = 'tf-chip' + (defaults.has(tf) ? ' active' : '');
      btn.textContent = tf;
      btn.dataset.tf  = tf;
      btn.addEventListener('click', () => {
        if (selectedTFs.has(tf)) {
          selectedTFs.delete(tf);
          btn.classList.remove('active');
        } else {
          selectedTFs.add(tf);
          btn.classList.add('active');
        }
        refreshAnalyzeBtn();
      });
      container.appendChild(btn);
    });
    refreshAnalyzeBtn();
  }

  function refreshAnalyzeBtn() {
    document.getElementById('btn-analyze').disabled = !(selectedPair && selectedTFs.size > 0);
  }

  // ── Analysis ───────────────────────────────────────────────────────────────
  document.getElementById('btn-analyze').addEventListener('click', runAnalysis);

  async function runAnalysis() {
    if (!selectedPair || selectedTFs.size === 0 || isLoading) return;
    isLoading = true;
    setStatus('live', 'Analysing…');
    hideError();

    // Show skeleton cards
    const tfs = [...selectedTFs];
    showSkeletons(tfs.length);

    try {
      const params = new URLSearchParams();
      params.set('pair', selectedPair);
      tfs.forEach(tf => params.append('timeframes', tf));

      const res  = await fetch('/api/analyze?' + params.toString());
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || res.statusText);
      }
      const data = await res.json();
      allSignals = data.signals || [];
      activeFilter = 'ALL';
      document.querySelectorAll('.chip').forEach(c => c.classList.toggle('active', c.dataset.filter === 'ALL'));
      render();
      setStatus('live', 'Updated ' + fmtNow());
    } catch(e) {
      showError(e.message);
      setStatus('', 'Error');
    } finally {
      isLoading = false;
    }
  }

  // ── Auto-refresh ───────────────────────────────────────────────────────────
  const btnAuto = document.getElementById('btn-auto');
  btnAuto.addEventListener('click', toggleAuto);

  function toggleAuto() {
    if (autoTimer) {
      clearInterval(autoTimer);
      autoTimer = null;
      btnAuto.textContent = '🔁 Off';
      btnAuto.classList.remove('active');
    } else {
      if (!selectedPair || selectedTFs.size === 0) {
        showError('Select a pair and at least one timeframe before enabling auto-refresh.');
        return;
      }
      const secs = parseInt(document.getElementById('auto-interval').value, 10);
      autoTimer = setInterval(runAnalysis, secs * 1000);
      btnAuto.textContent = '🔁 On';
      btnAuto.classList.add('active');
      runAnalysis(); // immediate first run
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  function render() {
    const filtered = activeFilter === 'ALL'
      ? allSignals
      : allSignals.filter(s => s.signal === activeFilter);

    document.getElementById('filter-bar').style.display  = 'flex';
    document.getElementById('summary-bar').style.display = 'flex';

    renderSummary();
    renderGrid(filtered);
  }

  function renderSummary() {
    const counts = { LONG: 0, SHORT: 0, 'NO TRADE': 0 };
    allSignals.forEach(s => { if (s.signal in counts) counts[s.signal]++; });
    document.getElementById('summary-bar').innerHTML = `
      <div class="summary-item"><span class="lbl">Total</span><span class="val">${allSignals.length}</span></div>
      <div class="summary-item"><span class="lbl">Long</span><span class="val long">${counts.LONG}</span></div>
      <div class="summary-item"><span class="lbl">Short</span><span class="val short">${counts.SHORT}</span></div>
      <div class="summary-item"><span class="lbl">No Trade</span><span class="val notrade">${counts['NO TRADE']}</span></div>
    `;
  }

  function renderGrid(signals) {
    const grid = document.getElementById('grid');
    if (!signals.length) {
      grid.innerHTML = `<div class="empty"><span class="icon">🔍</span><p>No signals match the current filter.</p></div>`;
      return;
    }
    grid.innerHTML = signals.map(buildCard).join('');
  }

  // ── Skeleton ───────────────────────────────────────────────────────────────
  function showSkeletons(n) {
    document.getElementById('filter-bar').style.display  = 'none';
    document.getElementById('summary-bar').style.display = 'none';
    document.getElementById('grid').innerHTML = Array.from({ length: n }, () => `
      <div class="skeleton-card">
        <div class="skel skel-h" style="width:60%"></div>
        <div class="skel skel-sm" style="width:40%"></div>
        <div class="skel skel-h" style="width:80%"></div>
        <div class="skel skel-sm" style="width:55%"></div>
        <div class="skel skel-sm" style="width:70%"></div>
      </div>`).join('');
  }

  // ── Card builder ───────────────────────────────────────────────────────────
  function buildCard(s) {
    const signal   = s.signal || 'NO TRADE';
    const badgeCls = signal === 'NO TRADE' ? 'NOTRADE' : signal;
    const emoji    = { LONG: '🟢', SHORT: '🔴', 'NO TRADE': '⚪' }[signal] || '';
    const confClr  = signal === 'LONG' ? '#3fb950' : signal === 'SHORT' ? '#f85149' : '#8b949e';

    const priceRow = s.stop_loss != null ? `
      <div class="prices">
        <div class="price-block">
          <div class="price-label">Entry</div>
          <div class="price-value entry">${fmt(s.entry)}</div>
        </div>
        <div class="price-block">
          <div class="price-label">Stop Loss</div>
          <div class="price-value sl">${fmt(s.stop_loss)}</div>
        </div>
        <div class="price-block">
          <div class="price-label">Take Profit</div>
          <div class="price-value tp">${fmt(s.take_profit)}</div>
        </div>
      </div>` : (s.entry != null ? `
      <div class="prices">
        <div class="price-block" style="grid-column:1/-1">
          <div class="price-label">Current Price</div>
          <div class="price-value entry">${fmt(s.entry)}</div>
        </div>
      </div>` : '');

    const trendCls = `trend-${(s.trend || 'RANGE').replace(/\s/g, '_')}`;
    const volLabel = s.vol_spike ? '🔥 Spike' : (s.vol_trend || 'flat');
    const stats = `
      <div class="stats">
        <div class="stat"><div class="stat-label">RSI</div><div class="stat-value">${s.rsi || '—'}</div></div>
        <div class="stat"><div class="stat-label">Trend</div><div class="stat-value ${trendCls}">${s.trend || '—'}</div></div>
        <div class="stat"><div class="stat-label">Pattern</div><div class="stat-value">${s.pattern || 'None'}</div></div>
        <div class="stat"><div class="stat-label">Volume</div><div class="stat-value">${volLabel}</div></div>
        <div class="stat"><div class="stat-label">BOS</div><div class="stat-value">${s.bos ? '✅ Yes' : 'No'}</div></div>
        <div class="stat"><div class="stat-label">CHOCH</div><div class="stat-value">${s.choch ? '⚠️ Yes' : 'No'}</div></div>
      </div>`;

    const res   = ((s.sr_levels && s.sr_levels.resistance) || []).slice(0, 3);
    const sup   = ((s.sr_levels && s.sr_levels.support)    || []).slice(0, 3);
    const srRow = (res.length || sup.length) ? `
      <div class="sr-row">
        ${res.length ? `<div class="sr-group"><div class="sr-title">Resistance</div>${res.map(r => `<div class="sr-val res">${fmt(r)}</div>`).join('')}</div>` : ''}
        ${sup.length ? `<div class="sr-group"><div class="sr-title">Support</div>${sup.map(r => `<div class="sr-val sup">${fmt(r)}</div>`).join('')}</div>` : ''}
      </div>` : '';

    const details   = s.signal_details || {};
    const scoreItems = Object.entries(details).map(([k, v]) => {
      const cls = v > 0 ? 'score-pos' : 'score-neg';
      return `<span class="score-item ${cls}">${v > 0 ? '+' : ''}${v} ${k}</span>`;
    }).join('');
    const scoreRow = scoreItems ? `
      <div class="score-details">
        <div class="score-title">Score breakdown (total: ${s.score > 0 ? '+' : ''}${s.score})</div>
        <div class="score-items">${scoreItems}</div>
      </div>` : '';

    const rrLabel = s.rr_ratio != null
      ? `<span style="font-size:0.7rem;color:var(--muted);margin-left:0.5rem">RR 1:${s.rr_ratio}</span>`
      : '';

    return `
    <div class="card" data-signal="${signal}">
      <div class="card-header">
        <span class="pair-name">${s.pair}</span>
        <span class="timeframe-badge">${s.timeframe}</span>
      </div>
      <div style="padding:0.2rem 1rem 0">
        <span class="signal-badge ${badgeCls}">${emoji} ${signal}</span>${rrLabel}
      </div>
      ${priceRow}
      ${stats}
      <div class="confidence-row">
        <div class="conf-header">
          <span class="conf-label">Confidence</span>
          <span class="conf-pct" style="color:${confClr}">${s.confidence}%</span>
        </div>
        <div class="conf-bar-bg">
          <div class="conf-bar-fill" style="width:${s.confidence}%;background:${confClr}"></div>
        </div>
      </div>
      ${srRow}
      ${scoreRow}
    </div>`;
  }

  // ── Filter chips ───────────────────────────────────────────────────────────
  document.getElementById('filter-bar').addEventListener('click', e => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    activeFilter = chip.dataset.filter;
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    render();
  });

  // ── Helpers ────────────────────────────────────────────────────────────────
  function fmt(v) {
    if (v == null) return '—';
    const n = parseFloat(v);
    return isNaN(n) ? v : n.toLocaleString(undefined, { maximumFractionDigits: 6 });
  }
  function fmtNow() {
    return new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  function setStatus(cls, text) {
    const dot = document.getElementById('status-dot');
    dot.className = 'status-dot' + (cls ? ' ' + cls : '');
    document.getElementById('status-text').textContent = text;
  }
  function showError(msg) {
    const b = document.getElementById('error-banner');
    b.style.display  = 'block';
    b.textContent    = '⚠️  ' + msg;
  }
  function hideError() {
    document.getElementById('error-banner').style.display = 'none';
  }

  // ── Init ───────────────────────────────────────────────────────────────────
  boot();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Serve the interactive dashboard."""
    return _DASHBOARD_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/pairs")
def api_pairs():
    """Return the list of all supported trading pairs."""
    return jsonify(ALL_PAIRS)


@app.route("/api/timeframes")
def api_timeframes():
    """Return the list of all supported timeframes."""
    return jsonify(ALL_TIMEFRAMES)


@app.route("/api/analyze")
def api_analyze():
    """Run live analysis for the requested pair and timeframes.

    Query parameters
    ----------------
    pair        : str  – e.g. ``BTC/USDT``  (required)
    timeframes  : str  – repeatable; e.g. ``?timeframes=1m&timeframes=5m&timeframes=15m``
                         Falls back to the configured default timeframes when omitted.

    Returns
    -------
    JSON object with ``generated_at`` and ``signals`` list.
    """
    pair = request.args.get("pair", "").strip()
    if not pair:
        return jsonify({"error": "Missing required query parameter: pair"}), 400

    requested_tfs = request.args.getlist("timeframes")
    timeframes = requested_tfs if requested_tfs else ALL_TIMEFRAMES

    # Validate timeframes
    invalid = [tf for tf in timeframes if tf not in ALL_TIMEFRAMES]
    if invalid:
        return jsonify({"error": f"Unsupported timeframe(s): {invalid}. "
                                  f"Supported: {ALL_TIMEFRAMES}"}), 400

    logger.info("API /analyze  pair=%s  timeframes=%s", pair, timeframes)

    results: list[dict] = []
    errors: list[str] = []

    for tf in timeframes:
        try:
            result = run_analysis(pair, tf)
            if result:
                results.append(_serialise(result))
        except (ValueError, RuntimeError, OSError) as exc:
            logger.exception("Error analysing %s %s", pair, tf)
            errors.append(f"{tf}: {exc}")

    payload: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pair": pair,
        "timeframes": timeframes,
        "signals": results,
    }
    if errors:
        payload["errors"] = errors

    return jsonify(payload)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crypto Futures Signal Bot – Interactive Web UI"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1). Use 0.0.0.0 to expose on LAN.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to listen on (default: 5000).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode.",
    )
    args = parser.parse_args()

    logger.info("📡  Crypto Signal Bot – Interactive Web UI  →  http://%s:%d/", args.host, args.port)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
