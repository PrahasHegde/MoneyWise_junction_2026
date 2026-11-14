(function () {
  const $ = (s) => document.querySelector(s);
  const state = { cid: null, session: null, ai: false, overview: null, loaded: {} };
  const fmt = Charts.fmt;
  const BK = { regular: "Fixed essentials", irregular: "Irregular essentials", everyday: "Everyday spending" };
  const icon = (id, cls = "ic") => `<svg class="${cls}"><use href="#i-${id}"/></svg>`;
  const LS = { theme: "tv-theme", cid: "tv-customer" };
  const BKC = { regular: "var(--b-regular)", irregular: "var(--b-irregular)", everyday: "var(--b-everyday)" };
  const STARTERS = ["How much did I spend on taxis last month?", "What kind of spender am I?",
    "What is safe for me to spend this week?", "How much could I save if I reduced dining out by 20%?",
    "Where does my money really go?", "How do I compare to other Finns?"];

  async function api(path, opts = {}, timeoutMs = 20000) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeoutMs);
    try {
      const r = await fetch(path, { ...opts, signal: ctl.signal });
      if (!r.ok) {
        let msg = r.statusText;
        try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : "Please check your input."; } catch (e) {}
        throw new Error(msg);
      }
      return await r.json();
    } catch (e) {
      if (e.name === "AbortError") throw new Error("The request took too long. Please try again.");
      if (e instanceof TypeError) throw new Error("No connection to the service. Check your network and try again.");
      throw e;
    } finally { clearTimeout(timer); }
  }
  function failCard(el, err, retry) {
    el.innerHTML = `<article class="card error-card"><b>Could not load this view</b><p class="muted small">${esc(err.message)}</p>
      <button class="primary" type="button">Try again</button></article>`;
    el.querySelector("button").addEventListener("click", retry);
  }
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function md(text) { // small, safe markdown subset
    const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|[\s(])[*_](.+?)[*_](?=[\s).,!?:]|$)/g, "$1<i>$2</i>");
    const out = []; let list = null;
    for (const raw of text.split("\n")) {
      const line = raw.trim();
      const m = line.match(/^(?:[-*•]|\d+\.)\s+(.*)/);
      if (m) { if (!list) { list = []; } list.push(`<li>${inline(m[1])}</li>`); continue; }
      if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; }
      if (line) out.push(`<p>${inline(line.replace(/^#+\s*/, ""))}</p>`);
    }
    if (list) out.push(`<ul>${list.join("")}</ul>`);
    return out.join("");
  }

  // ------------------------------------------------------------ tabs
  function go(tab) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + tab));
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    scrollTo(0, tab === "coach" ? document.body.scrollHeight : 0);
    if (!state.loaded[tab]) { state.loaded[tab] = true; loadTab(tab); }
    if (tab === "coach") setTimeout(() => $("#msg").focus(), 50);
  }
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => go(b.dataset.tab)));
  document.addEventListener("click", (e) => { const g = e.target.closest("[data-goto]"); if (g) go(g.dataset.goto); });

  // ------------------------------------------------------------ theme
  (function theme() {
    let t = null; try { t = localStorage.getItem(LS.theme); } catch (e) {}
    if (t) document.documentElement.dataset.theme = t;
    $("#theme").addEventListener("click", () => {
      const dark = document.documentElement.dataset.theme === "dark" ||
        (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.dataset.theme = dark ? "light" : "dark";
      try { localStorage.setItem(LS.theme, document.documentElement.dataset.theme); } catch (e) {}
    });
  })();

  // ------------------------------------------------------------ home
  async function loadHome() {
    const o = await api(`/api/${state.cid}/overview`);
    state.overview = o;
    const s = o.safe_to_spend, b = o.baskets, p = o.profile;
    const cust = state.customers.find((c) => c.id === state.cid);
    const days = s.days_left;
    $("#hello").innerHTML = `Hello ${esc(cust.name)}. Your next payday is ${days <= 1 ? "<b>tomorrow</b>" : `in <b>${days} days</b>`}.`;
    $("#sts-week").textContent = fmt(s.safe_this_week);
    const st = { comfortable: ["On track", "var(--mint)"], tight: ["Tight", "#f0b429"], over: ["Over budget", "#ff8a80"] }[s.status];
    $("#sts-status").innerHTML = `<span class="status"><i style="background:${st[1]}"></i>${st[0]}</span>`;
    $("#sts-sub").innerHTML = `${fmt(Math.max(s.safe_per_day, 0))} per day until payday` +
      (s.week_includes_days_after_payday ? `, then approx. ${fmt(s.next_cycle_daily_estimate)} per day` : "");
    const typical = s.typical_weekly_everyday_spend, maxv = Math.max(s.safe_this_week, typical) * 1.15 || 1;
    $("#sts-meter").style.width = (Math.max(s.safe_this_week, 0) / maxv * 100) + "%";
    $("#sts-mark").style.left = (typical / maxv * 100) + "%";
    $("#sts-meter-l").textContent = "Available this week";
    $("#sts-meter-r").textContent = `Typical week: ${fmt(typical)}`;
    const steps = [["Income since payday", s.cycle_income], ["Already spent", -s.spent_so_far], ["Bills still due", -s.upcoming_bills],
      ["Food & essentials reserve", -s.essentials_reserve], ["Surprise buffer (irregular basket)", -s.irregular_buffer],
      [`Savings goal (${Math.round(s.savings_rate * 100)}%)`, -s.savings_goal_left], ["Safe until payday", s.safe_until_payday]];
    $("#sts-detail").innerHTML = `<ul class="steps">${steps.map(([l, v]) => `<li><span>${l}</span><span>${fmt(v)}</span></li>`).join("")}</ul>
      <p class="explain"><b>Safe-to-spend</b> is the amount left for discretionary spending once essential costs and your savings goal have been set aside. ${s.week_includes_days_after_payday ? `This week includes ${s.week_includes_days_after_payday} day(s) after payday, estimated from your usual daily allowance.` : ""}</p>`;

    $("#bk-period").textContent = `Average month, ${b.period} · income ${fmt(b.income_monthly_avg)}`;
    $("#bk-bar").innerHTML = b.baskets.map((x) => `<div style="flex:${x.total};background:${BKC[x.id]}" title="${esc(x.label)}"></div>`).join("") +
      (b.left_over_monthly_avg > 0 ? `<div style="flex:${b.left_over_monthly_avg * b.months};background:var(--surface-2)" title="Left over"></div>` : "");
    $("#bk-list").innerHTML = b.baskets.map((x) => `<li><span class="dot" style="background:${BKC[x.id]}"></span>
      <span>${esc(x.label)}<small>${x.top_categories.slice(0, 3).map((c) => esc(c.name)).join(", ")}</small></span>
      <b>${fmt(x.monthly_avg)}</b></li>`).join("") +
      `<li><span class="dot" style="background:var(--surface-2);border:1px solid var(--line)"></span><span>Remaining<small>Available to save or carry forward</small></span><b>${fmt(b.left_over_monthly_avg)}</b></li>`;

    $("#persona-card").innerHTML = `<div class="card-head"><h2>Spending profile</h2></div>
      <div class="p-row"><span class="badge-ic">${icon("spark")}</span><div><h3>${esc(p.archetype.replace(/^The /, ""))}</h3><small class="muted">Secondary trait: ${esc(p.secondary.replace(/^The /, ""))}</small></div></div>
      <p class="muted small" style="margin:10px 0 0">${esc(p.description)}</p>
      <ul>${p.traits.slice(0, 4).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
      <button class="link" data-ask="What kind of spender am I, and what's one habit I could change?">Discuss with your coach${icon("arrow", "ic sm")}</button>`;
    $("#nudges").innerHTML = o.nudges.length ? o.nudges.map((n) => `<li>${icon("info", "ic sm")}<span>${esc(n)}</span></li>`).join("")
      : `<li>${icon("shield", "ic sm")}<span>No unusual activity this month.</span></li>`;
    $("#home-chips").innerHTML = STARTERS.slice(0, 4).map((q) => `<button class="chip" data-ask="${esc(q)}">${esc(q)}</button>`).join("");
  }
  $("#sts-how").addEventListener("click", () => {
    const d = $("#sts-detail"); d.classList.toggle("hidden");
    const open = !d.classList.contains("hidden");
    $("#sts-how").textContent = open ? "Hide calculation" : "How is this calculated?";
    $("#sts-how").setAttribute("aria-expanded", open);
  });
  document.addEventListener("click", (e) => { const a = e.target.closest("[data-ask]"); if (a) { go("coach"); send(a.dataset.ask); } });

  // ------------------------------------------------------------ coach
  function bubble(role, html) {
    const d = document.createElement("div"); d.className = "msg " + role; d.innerHTML = html;
    $("#chat").appendChild(d); scrollTo(0, document.body.scrollHeight); return d;
  }
  function greet() {
    $("#chat").innerHTML = "";
    const cust = state.customers.find((c) => c.id === state.cid);
    bubble("bot", md(`Hello ${cust.name}. I'm your personal finance coach. I can analyse your transactions and answer questions in Finnish, Swedish or English.\n\nChoose a question or type your own:`) +
      `<div class="chips">${STARTERS.map((q) => `<button class="chip" data-ask="${esc(q)}">${esc(q)}</button>`).join("")}</div>` +
      `<div class="meta">${icon("shield", "ic sm")}${state.ai ? `AI coach (${state.provider === "gemini" ? "Gemini" : "Claude"}) · figures calculated from your data`
        : "Offline mode · set GEMINI_API_KEY for the full AI coach"}</div>`);
  }
  async function send(text) {
    text = (text || "").trim().slice(0, 1000); if (!text || state.sending) return;
    state.sending = true; $("#composer button").disabled = true;
    bubble("user", esc(text));
    const wait = bubble("bot", '<span class="typing"><span></span><span></span><span></span></span>');
    try {
      const r = await api("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_id: state.cid, message: text, session_id: state.session, include_other_banks: true }) }, 90000);
      state.session = r.session_id;
      wait.innerHTML = md(r.text);
      (r.charts || []).forEach((c) => { const w = document.createElement("div"); w.className = "chart-wrap"; wait.appendChild(w); Charts.render(c, w); });
      if (r.followups && r.followups.length) {
        const ch = document.createElement("div"); ch.className = "chips"; ch.style.marginTop = "10px";
        ch.innerHTML = r.followups.map((q) => `<button class="chip" data-ask="${esc(q)}">${esc(q)}</button>`).join("");
        wait.appendChild(ch);
      }
      const tools = [...new Set(r.tools || [])].filter((t) => t !== "show_chart");
      const meta = document.createElement("div"); meta.className = "meta";
      const label = r.engine !== "offline" ? (tools.length ? `Based on: ${tools.join(", ").replace(/_/g, " ")}` : "") : "Offline answer";
      meta.innerHTML = label ? icon("shield", "ic sm") + esc(label) : "";
      wait.appendChild(meta);
    } catch (e) {
      wait.innerHTML = `<p>Sorry, I couldn't answer that just now. ${esc(e.message)}</p><div class="chips"><button class="chip" data-ask="${esc(text)}">Try again</button></div>`;
    } finally { state.sending = false; $("#composer button").disabled = false; }
    scrollTo(0, document.body.scrollHeight);
  }
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); const v = $("#msg").value; $("#msg").value = ""; send(v); });

  // ------------------------------------------------------------ baskets
  async function loadBaskets() {
    const [b, t, cats] = await Promise.all([api(`/api/${state.cid}/baskets`), api(`/api/${state.cid}/trend`), api(`/api/${state.cid}/categories`)]);
    $("#basket-cards").innerHTML = b.baskets.map((x) => `<article class="card bk-card" style="--c:${BKC[x.id]}">
      <div class="card-head"><h2>${esc(x.label)}</h2><span class="share">${x.share_of_spending.toFixed(0)} % of spending</span></div>
      <div class="big">${fmt(x.monthly_avg)}<span class="muted small"> / month</span></div>
      <p class="teach">${esc(x.teach)}</p>
      <p class="sub-h">Categories</p>
      <ul class="mini">${x.top_categories.map((c) => `<li><span>${esc(c.name)}</span><span>${fmt(c.monthly_avg)} / mo</span></li>`).join("")}</ul>
      ${x.examples.length ? `<p class="sub-h">Largest recent payments</p><ul class="mini">${x.examples.map((e) =>
        `<li><span>${esc(e.merchant)}<span class="why">${esc(e.why)}</span></span><span>${fmt(e.amount)}</span></li>`).join("")}</ul>` : ""}
      <button class="link" style="margin-top:10px" data-ask="Explain my ${esc(x.label.toLowerCase())}. What should I know?">Discuss with your coach${icon("arrow", "ic sm")}</button>
    </article>`).join("");
    Charts.render({ type: "stacked", title: "Spending per month by basket", labels: t.months, series: t.series, names: BK }, $("#trend-chart"));
    const seen = new Set();
    $("#reclass").innerHTML = cats.filter((c) => !seen.has(c.category) && seen.add(c.category)).map((c) => `<li><span>${esc(c.category)}</span>
      <select data-cat="${esc(c.category)}">${Object.entries(BK).map(([k, v]) => `<option value="${k}" ${k === c.basket ? "selected" : ""}>${v}</option>`).join("")}</select></li>`).join("");
    $("#reclass").querySelectorAll("select").forEach((s) => s.addEventListener("change", async () => {
      await api(`/api/${state.cid}/reclassify`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ basket: s.value, category: s.dataset.cat }) });
      state.loaded = { baskets: true }; loadHome(); loadBaskets();
    }));
  }

  // ------------------------------------------------------------ explore
  async function loadExplore() {
    const q = $("#ex-q").value.trim();
    const params = new URLSearchParams({ period: $("#ex-period").value, group_by: $("#ex-group").value, other_banks: $("#ex-banks").checked });
    if ($("#ex-basket").value) params.set("basket", $("#ex-basket").value);
    let r;
    if (q) {
      params.set("merchant", q);
      r = await api(`/api/${state.cid}/explore?${params}`);
      if (!r.count) { params.delete("merchant"); params.set("category", q); r = await api(`/api/${state.cid}/explore?${params}`); }
    } else r = await api(`/api/${state.cid}/explore?${params}`);
    $("#ex-total").innerHTML = `<b>${fmt(r.total)}</b> · ${r.count} purchases · avg ${fmt(r.avg_ticket)} · ${esc(r.period)}`;
    if (r.chart && $("#ex-group").value === "basket") r.chart.labels = r.chart.labels.map((l) => BK[l] || l);
    Charts.render(r.chart, $("#ex-chart"));
    const tx = await api(`/api/${state.cid}/transactions?limit=40${$("#ex-basket").value ? "&basket=" + $("#ex-basket").value : ""}${q ? "&q=" + encodeURIComponent(q) : ""}`);
    $("#ex-txns").innerHTML = tx.map((t) => `<li><span class="dot" style="background:${BKC[t.basket]}"></span>
      <span>${esc(t.merchant)}${t.bank !== "S-Pankki" ? `<span class="badge">${esc(t.bank)}</span>` : ""}<small>${t.date} · ${esc(t.category)}${/is usually|Matched/.test(t.why) ? "" : " · " + esc(t.why)}</small></span>
      <span class="amt">${fmt(-t.amount)}</span></li>`).join("") || '<li class="muted">No transactions.</li>';
  }
  ["#ex-period", "#ex-group", "#ex-basket", "#ex-banks"].forEach((s) => $(s).addEventListener("change", loadExplore));
  let deb; $("#ex-q").addEventListener("input", () => { clearTimeout(deb); deb = setTimeout(loadExplore, 300); });

  // ------------------------------------------------------------ what-if
  async function loadWhatIf() {
    const cats = await api(`/api/${state.cid}/categories`);
    const opts = [...new Set(cats.filter((c) => c.basket === "everyday").map((c) => c.category))];
    $("#wi-cat").innerHTML = `<option value="basket:everyday">All everyday slips</option>` + opts.map((c) => `<option ${c === "Restaurants" ? "selected" : ""}>${esc(c)}</option>`).join("");
    runWhatIf();
  }
  async function runWhatIf() {
    const pct = $("#wi-pct").value, v = $("#wi-cat").value, ret = $("#wi-ret").value;
    $("#wi-pct-l").textContent = pct + " %";
    const p = new URLSearchParams({ reduce_pct: pct, annual_return: ret });
    if (v.startsWith("basket:")) p.set("basket", v.slice(7)); else p.set("category", v);
    const r = await api(`/api/${state.cid}/whatif?${p}`);
    const five = r.projection.find((x) => x.years === 5), ten = r.projection.find((x) => x.years === 10);
    $("#wi-result").innerHTML = `<span class="eyebrow">Annual saving</span><div class="hero-num">${fmt(r.yearly_saving)}<small> / year</small></div>
      <div class="hero-sub">${fmt(r.monthly_saving)} per month, roughly ${r.fewer_purchases_per_month ?? 0} fewer purchases a month. Equivalent to ${esc(r.that_buys_per_year)}.</div>
      <div class="kpis"><div><small>Now</small><b>${fmt(r.monthly_now)}</b><small>${r.times_per_month}× a month, avg ${fmt(r.avg_ticket)}</small></div>
      <div><small>In 5 years</small><b>${fmt(five.with_interest)}</b><small>10 years: ${fmt(ten.with_interest)}</small></div></div>`;
    Charts.render(r.chart, $("#wi-chart"));
    const gain = ten.with_interest - ten.saved;
    $("#wi-note").innerHTML = icon("info", "ic sm") + "<span>" + (+ret > 0 ? `<b>Compound interest:</b> after 10 years, ${fmt(gain)} of the total is return earned on earlier returns.${+ret >= 0.06 ? " Fund values can also fall; funds suit money you won't need for at least five years." : ""}`
      : "Without interest, savings grow only by the amounts you deposit. Select a savings account to compare.") + "</span>";
    state.whatif = r;
  }
  ["#wi-cat", "#wi-ret"].forEach((s) => $(s).addEventListener("change", runWhatIf));
  $("#wi-pct").addEventListener("input", () => { clearTimeout(deb); deb = setTimeout(runWhatIf, 120); });
  $("#wi-ask").addEventListener("click", () => {
    const r = state.whatif; if (!r) return;
    go("coach"); send(`If I cut ${r.target} by ${r.reduce_pct}%, how would that change my week, and is that realistic for me?`);
  });

  // ------------------------------------------------------------ boot
  async function selectCustomer(cid) {
    state.cid = cid; state.session = null; state.loaded = { home: true };
    try { localStorage.setItem(LS.cid, cid); } catch (e) {}
    greet(); await loadTab("home");
    const active = document.querySelector(".tabs button.active").dataset.tab;
    if (active !== "home" && active !== "coach") { state.loaded[active] = true; loadTab(active); }
  }
  async function loadTab(tab) {
    const fn = { home: loadHome, baskets: loadBaskets, explore: loadExplore, whatif: loadWhatIf }[tab];
    if (!fn) return;
    const host = $("#tab-" + tab);
    host.querySelectorAll(".error-card").forEach((n) => n.remove());
    try { await fn(); } catch (e) {
      state.loaded[tab] = false;
      const box = document.createElement("div"); host.prepend(box);
      failCard(box, e, () => { box.remove(); state.loaded[tab] = true; loadTab(tab); });
    }
  }
  (async function boot() {
    let cs, st;
    try { [cs, st] = await Promise.all([api("/api/customers"), api("/api/status")]); }
    catch (e) { const box = document.createElement("div"); $("#tab-home").prepend(box); failCard(box, e, () => location.reload()); return; }
    state.customers = cs; state.ai = st.ai; state.provider = st.provider;
    $("#customer").innerHTML = cs.map((c) => `<option value="${c.id}">${esc(c.name)}${c.age ? ", " + c.age : ""}</option>`).join("");
    let saved = null; try { saved = localStorage.getItem(LS.cid); } catch (e) {}
    const cid = cs.some((c) => c.id === saved) ? saved : cs[0].id;
    $("#customer").value = cid;
    $("#customer").addEventListener("change", (e) => selectCustomer(e.target.value));
    await selectCustomer(cid);
    // Deep links for embedding in a host app, e.g. #coach?ask=Why%20was%20this%20so%20expensive
    const [tab, qs] = location.hash.slice(1).split("?");
    if (["home", "coach", "baskets", "explore", "whatif"].includes(tab)) {
      go(tab);
      const ask = new URLSearchParams(qs || "").get("ask");
      if (ask) send(ask);
    }
  })();
})();
