/* Tiny dependency-free SVG charts, mobile-first. Every mark has a tap/hover tooltip. */
(function () {
  const SLOTS = ["var(--b-regular)", "var(--b-irregular)", "var(--b-everyday)", "var(--series-2)"];
  const BASKET = { "Fixed essentials": "var(--b-regular)", "Irregular essentials": "var(--b-irregular)", "Everyday spending": "var(--b-everyday)",
    regular: "var(--b-regular)", irregular: "var(--b-irregular)", everyday: "var(--b-everyday)" };
  const NS = "http://www.w3.org/2000/svg";
  const tip = () => document.getElementById("tip");

  function fmt(v, unit) {
    if (unit === "%") return `${(+v).toFixed(0)}%`;
    const a = Math.abs(v);
    const s = a >= 1000 ? Math.round(a).toLocaleString("en-US").replace(/,/g, " ") : a >= 100 ? a.toFixed(0) : a.toFixed(a % 1 ? 2 : 0);
    return `${v < 0 ? "−" : ""}€${s}`;
  }
  function el(name, attrs = {}, parent) {
    const n = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  }
  function bindTip(node, text) {
    const show = (e) => { const t = tip(); t.textContent = text; t.classList.add("on");
      const x = (e.touches ? e.touches[0].clientX : e.clientX), y = (e.touches ? e.touches[0].clientY : e.clientY);
      t.style.left = Math.min(x + 10, innerWidth - t.offsetWidth - 8) + "px"; t.style.top = (y - 34) + "px"; };
    node.addEventListener("pointerenter", show); node.addEventListener("pointermove", show);
    node.addEventListener("pointerleave", () => tip().classList.remove("on"));
    node.addEventListener("click", (e) => { show(e); setTimeout(() => tip().classList.remove("on"), 1600); });
  }
  const colorFor = (label, i) => BASKET[label] || SLOTS[i % SLOTS.length];
  function rounded(x, y, w, h, r, side) { // bar with rounded data-end only
    r = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
    if (side === "right") return `M${x},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 -${r},${r}h-${w - r}z`;
    return `M${x},${y + h}v-${h - r}a${r},${r} 0 0 1 ${r},-${r}h${w - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${h - r}z`;
  }

  // horizontal bars - best for category names on a phone
  function bar(c, root) {
    const n = c.labels.length, rowH = 30, W = 340, labelW = 118, valW = 58, pw = W - labelW - valW;
    const max = Math.max(...c.values.map(Math.abs), 1);
    const svg = el("svg", { class: "viz", viewBox: `0 0 ${W} ${n * rowH}`, role: "img", "aria-label": c.title }, root);
    c.labels.forEach((l, i) => {
      const y = i * rowH, w = Math.max(2, (Math.abs(c.values[i]) / max) * pw);
      const t = el("text", { x: 0, y: y + 19, class: "lbl" }, svg); t.textContent = l.length > 17 ? l.slice(0, 16) + "…" : l;
      el("path", { d: rounded(labelW, y + 7, w, 16, 4, "right"), fill: c.colors ? c.colors[i] : colorFor(l, 0) }, svg);
      const v = el("text", { x: labelW + w + 6, y: y + 19, class: "val" }, svg); v.textContent = fmt(c.values[i], c.unit);
      bindTip(el("rect", { x: 0, y, width: W, height: rowH, class: "hit" }, svg), `${l}: ${fmt(c.values[i], c.unit)}`);
    });
  }

  function compare(c, root) {
    const n = c.labels.length, rowH = 42, W = 340, labelW = 118, pw = W - labelW - 50;
    const max = Math.max(...c.values, ...(c.values2 || []), 1);
    const svg = el("svg", { class: "viz", viewBox: `0 0 ${W} ${n * rowH}`, role: "img", "aria-label": c.title }, root);
    c.labels.forEach((l, i) => {
      const y = i * rowH;
      const t = el("text", { x: 0, y: y + 22, class: "lbl" }, svg); t.textContent = l.length > 17 ? l.slice(0, 16) + "…" : l;
      [[c.values[i], "var(--b-regular)", 6], [(c.values2 || [])[i] || 0, "var(--series-2)", 21]].forEach(([v, col, dy]) => {
        const w = Math.max(2, v / max * pw);
        el("path", { d: rounded(labelW, y + dy, w, 12, 4, "right"), fill: col }, svg);
        const tv = el("text", { x: labelW + w + 5, y: y + dy + 10 }, svg); tv.textContent = fmt(v, c.unit);
      });
      bindTip(el("rect", { x: 0, y, width: W, height: rowH, class: "hit" }, svg),
        `${l}: ${(c.series || ["You"])[0]} ${fmt(c.values[i], c.unit)} · ${(c.series || [, "Avg"])[1]} ${fmt((c.values2 || [])[i] || 0, c.unit)}`);
    });
    legend(root, (c.series || ["You", "Average"]).map((s, i) => [s, i ? "var(--series-2)" : "var(--b-regular)"]));
  }

  function line(c, root) {
    const W = 340, H = 170, L = 44, B = 22, T = 10, n = c.values.length;
    const max = Math.max(...c.values, 1) * 1.1, min = Math.min(0, ...c.values);
    const x = (i) => L + (n === 1 ? 0 : i * (W - L - 8) / (n - 1)), y = (v) => T + (H - T - B) * (1 - (v - min) / (max - min));
    const svg = el("svg", { class: "viz", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": c.title }, root);
    for (let k = 0; k <= 3; k++) { const v = min + (max - min) * k / 3, yy = y(v);
      el("line", { x1: L, x2: W - 8, y1: yy, y2: yy, class: "grid" }, svg);
      const t = el("text", { x: L - 6, y: yy + 4, "text-anchor": "end" }, svg); t.textContent = fmt(v, c.unit); }
    const pts = c.values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
    el("polygon", { points: `${x(0)},${y(min)} ${pts} ${x(n - 1)},${y(min)}`, fill: "var(--b-regular)", opacity: .12 }, svg);
    el("polyline", { points: pts, fill: "none", stroke: "var(--b-regular)", "stroke-width": 2, "stroke-linejoin": "round" }, svg);
    const every = Math.ceil(n / 6);
    c.values.forEach((v, i) => {
      el("circle", { cx: x(i), cy: y(v), r: 4, fill: "var(--b-regular)", stroke: "var(--surface)", "stroke-width": 2 }, svg);
      if (i % every === 0 || i === n - 1) { const t = el("text", { x: x(i), y: H - 4, "text-anchor": "middle" }, svg); t.textContent = String(c.labels[i]).replace(/^20(\d\d)-/, "$1/"); }
      bindTip(el("rect", { x: x(i) - (W / n) / 2, y: 0, width: W / n, height: H, class: "hit" }, svg), `${c.labels[i]}: ${fmt(v, c.unit)}`);
    });
    const last = el("text", { x: x(n - 1), y: y(c.values[n - 1]) - 9, "text-anchor": "end", class: "val" }, svg);
    last.textContent = fmt(c.values[n - 1], c.unit);
  }

  function donut(c, root) {
    const W = 340, H = 150, cx = 75, cy = 75, R = 62, r = 40;
    const total = c.values.reduce((a, b) => a + b, 0) || 1;
    const svg = el("svg", { class: "viz", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": c.title }, root);
    let a0 = -Math.PI / 2;
    c.values.forEach((v, i) => {
      const a1 = a0 + v / total * Math.PI * 2, big = a1 - a0 > Math.PI ? 1 : 0;
      const p = (rad, ang) => `${cx + rad * Math.cos(ang)},${cy + rad * Math.sin(ang)}`;
      const path = el("path", { d: `M${p(R, a0)}A${R},${R} 0 ${big} 1 ${p(R, a1)}L${p(r, a1)}A${r},${r} 0 ${big} 0 ${p(r, a0)}z`,
        fill: colorFor(c.labels[i], i), stroke: "var(--surface)", "stroke-width": 2 }, svg);
      bindTip(path, `${c.labels[i]}: ${fmt(v, c.unit)} (${(v / total * 100).toFixed(0)}%)`);
      a0 = a1;
    });
    const t = el("text", { x: cx, y: cy + 5, "text-anchor": "middle", class: "val" }, svg); t.textContent = fmt(total, c.unit);
    c.labels.forEach((l, i) => {
      const y = 30 + i * 26;
      el("rect", { x: 165, y: y - 10, width: 10, height: 10, rx: 3, fill: colorFor(l, i) }, svg);
      const tl = el("text", { x: 182, y, class: "lbl" }, svg); tl.textContent = l;
      const tv = el("text", { x: 182, y: y + 14 }, svg); tv.textContent = `${fmt(c.values[i], c.unit)} · ${(c.values[i] / total * 100).toFixed(0)}%`;
    });
  }

  // waterfall as a list of horizontal steps (reads top-to-bottom like a receipt)
  function waterfall(c, root) {
    const n = c.labels.length, rowH = 28, W = 340, labelW = 128, pw = W - labelW - 62;
    const start = c.values[0] || 1;
    const svg = el("svg", { class: "viz", viewBox: `0 0 ${W} ${n * rowH}`, role: "img", "aria-label": c.title }, root);
    let run = 0;
    c.values.forEach((v, i) => {
      const y = i * rowH, last = i === n - 1, first = i === 0;
      let from, to;
      if (first) { from = 0; to = v; run = v; } else if (last) { from = 0; to = v; } else { from = run + v; to = run; run += v; }
      const sx = labelW + Math.max(0, Math.min(from, to)) / start * pw, w = Math.max(2, Math.abs(to - from) / start * pw);
      const col = first ? "var(--b-regular)" : last ? (v >= 0 ? "var(--b-everyday)" : "var(--bad)") : "var(--series-2)";
      const t = el("text", { x: 0, y: y + 18, class: "lbl" }, svg); t.textContent = c.labels[i];
      el("rect", { x: sx, y: y + 6, width: w, height: 16, rx: 4, fill: col, opacity: last || first ? 1 : .55 }, svg);
      const tv = el("text", { x: W, y: y + 18, "text-anchor": "end", class: last ? "val" : "" }, svg); tv.textContent = fmt(v, c.unit);
      bindTip(el("rect", { x: 0, y, width: W, height: rowH, class: "hit" }, svg), `${c.labels[i]}: ${fmt(v, c.unit)}`);
    });
  }

  // stacked monthly columns for the three baskets
  function stacked(c, root) {
    const W = 340, H = 180, L = 40, B = 22, T = 8, n = c.labels.length, keys = Object.keys(c.series);
    const totals = c.labels.map((_, i) => keys.reduce((s, k) => s + c.series[k][i], 0));
    const max = Math.max(...totals, 1) * 1.05, y = (v) => (H - T - B) * v / max;
    const svg = el("svg", { class: "viz", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": c.title || "Monthly baskets" }, root);
    for (let k = 0; k <= 3; k++) { const v = max * k / 3, yy = H - B - y(v);
      el("line", { x1: L, x2: W, y1: yy, y2: yy, class: "grid" }, svg);
      const t = el("text", { x: L - 6, y: yy + 4, "text-anchor": "end" }, svg); t.textContent = fmt(v); }
    const bw = (W - L) / n;
    c.labels.forEach((m, i) => {
      let base = H - B;
      keys.forEach((k) => {
        const h = y(c.series[k][i]);
        if (h > 0.5) el("rect", { x: L + i * bw + 2, y: base - h, width: bw - 4, height: Math.max(h - 2, 0.5), rx: 2, fill: BASKET[k] }, svg);
        base -= h;
      });
      if (i % 2 === 0) { const t = el("text", { x: L + i * bw + bw / 2, y: H - 6, "text-anchor": "middle" }, svg); t.textContent = m.slice(5) + "/" + m.slice(2, 4); }
      bindTip(el("rect", { x: L + i * bw, y: 0, width: bw, height: H, class: "hit" }, svg),
        `${m}: ` + keys.map((k) => `${c.names[k]} ${fmt(c.series[k][i])}`).join(" · "));
    });
    legend(root, keys.map((k) => [c.names[k], BASKET[k]]));
  }

  function legend(root, items) {
    const d = document.createElement("div"); d.className = "legend";
    d.innerHTML = items.map(([n, col]) => `<span><i style="background:${col}"></i>${n}</span>`).join("");
    root.appendChild(d);
  }

  window.Charts = {
    fmt,
    render(c, root) {
      root.innerHTML = "";
      if (!c || !c.labels || !c.labels.length) { root.innerHTML = '<p class="muted small">Nothing to show for this selection.</p>'; return; }
      if (c.title) { const h = document.createElement("p"); h.className = "chart-title"; h.textContent = c.title; root.appendChild(h); }
      ({ bar, line, donut, waterfall, compare, stacked }[c.type] || bar)(c, root);
    },
  };
})();
