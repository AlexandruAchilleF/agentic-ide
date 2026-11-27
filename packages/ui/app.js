// Logica paginii. Ia datele din mockData.js și le afișează pas cu pas,
// ca și cum ar veni de la agenți. Nu vorbește încă cu OpenCode.

const STEP_DELAY_MS = 1000; // cât așteaptă între doi pași (1 secundă)

const $ = (id) => document.getElementById(id);
const els = {
  project: $("project"),
  agent: $("agent"),
  status: $("status"),
  prompt: $("prompt"),
  sendBtn: $("sendBtn"),
  qaBtn: $("qaBtn"),
  timeline: $("timeline"),
  summary: $("summary"),
  emptyChanges: $("emptyChanges"),
  changes: $("changes"),
  changesCount: $("changesCount"),
  review: $("review"),
  reviewNote: $("reviewNote"),
  reviewActions: $("reviewActions"),
  acceptBtn: $("acceptBtn"),
  rejectBtn: $("rejectBtn"),
  context: $("context"),
  budget: $("budget"),
};

// Starea paginii
let busy = false; // un agent lucrează acum
let phase = "start"; // start → coder-done → reviewing → finished
let queue = []; // modificările, în ordinea în care le verifici
let current = 0; // a câta modificare e pe ecran acum
let accepted = []; // ce ai acceptat

// Protejează textul înainte să-l punem în pagină.
function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setStatus(kind, text) {
  els.status.className = "status " + kind;
  els.status.textContent = text;
}

function plural(n, one, many) {
  return n === 1 ? `1 ${one}` : `${n} ${many}`;
}

// ---------- Pașii agenților ----------

function addStep(step, isQa) {
  const li = document.createElement("li");
  const classes = ["step", step.kind];
  if (step.status) classes.push(step.status);
  if (isQa) classes.push("qa");
  li.className = classes.join(" ");

  const tag = step.server ? `<div class="tag">MCP · ${escapeHtml(step.server)}</div>` : "";
  li.innerHTML = `
    ${tag}
    <div class="title">${escapeHtml(step.title)}</div>
    <div class="detail">${escapeHtml(step.detail)}</div>
  `;
  els.timeline.appendChild(li);
  li.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------- Modificările propuse ----------

function diffRows(lines) {
  return lines
    .map((line) => {
      const sign = line.type === "add" ? "+" : line.type === "del" ? "−" : " ";
      return `
        <div class="diff-row ${line.type}">
          <span class="no">${line.oldNo ?? ""}</span>
          <span class="no">${line.newNo ?? ""}</span>
          <span class="sign">${sign}</span>
          <span class="code">${escapeHtml(line.text)}</span>
        </div>`;
    })
    .join("");
}

function cardFor(id) {
  return els.changes.querySelector(`.change[data-id="${id}"]`);
}

// Pune o modificare în coloana din mijloc. Cele propuse de QA stau ascunse până le vine rândul.
function addChange(id, visible) {
  const change = MOCK.changes.find((c) => c.id === id);
  if (!change) return;

  const card = document.createElement("div");
  card.className = "change";
  card.dataset.id = change.id;
  card.hidden = !visible;
  card.innerHTML = `
    <div class="change-head">
      <span class="change-no">${change.id}.</span>
      <span class="change-title">${escapeHtml(change.title)}</span>
      <span class="change-author ${change.author.toLowerCase()}">${escapeHtml(change.author)}</span>
      <span class="change-state"></span>
    </div>
    <div class="change-path">${escapeHtml(change.path)}</div>
    <div class="diff">${diffRows(change.lines)}</div>
  `;
  // După ce ai decis, un click pe titlu ascunde sau arată din nou codul.
  card.querySelector(".change-head").addEventListener("click", () => {
    if (card.classList.contains("decided")) card.classList.toggle("collapsed");
  });

  els.changes.appendChild(card);
  queue.push(change.id);
  updateReview();
}

// Arată modificarea la care ai ajuns și o evidențiază.
function focusCurrent() {
  const id = queue[current];
  const card = cardFor(id);
  card.hidden = false;
  card.classList.add("current");
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  updateReview();
}

// Actualizează bara de jos și numărul de modificări din capul coloanei.
function updateReview() {
  const visible = [...els.changes.querySelectorAll(".change")].filter((c) => !c.hidden).length;
  els.emptyChanges.hidden = visible > 0;
  els.changesCount.textContent = visible ? plural(visible, "propusă", "propuse") : "";

  if (phase === "coder-done") {
    els.review.hidden = false;
    els.reviewActions.hidden = true;
    els.reviewNote.textContent = "Modificarea e încă în sandbox. Apasă „Rulează QA”, apoi le verifici una câte una.";
  } else if (phase === "reviewing") {
    const change = MOCK.changes.find((c) => c.id === queue[current]);
    els.review.hidden = false;
    els.reviewActions.hidden = false;
    els.reviewNote.innerHTML = `<b>Modificarea ${current + 1} din ${queue.length}</b> · ${escapeHtml(change.title)}`;
  } else {
    els.review.hidden = true;
  }

  els.acceptBtn.disabled = busy;
  els.rejectBtn.disabled = busy;
}

// Ce teste trec după ce aplici doar modificările acceptate.
function testResult(ids) {
  const has = (id) => ids.includes(id);
  const failed = [];
  let total = MOCK.testsBase;

  if (!has(1)) failed.push("test_total_with_discount");
  if (has(3)) {
    total += 1; // modificarea 3 adaugă un test nou
    if (!has(2)) failed.push("test_discount_peste_100"); // testul nou are nevoie de modificarea 2
  }

  const passed = total - failed.length;
  if (failed.length === 0) {
    return { ok: true, detail: `${passed} teste trecute, 0 picate.` };
  }
  return {
    ok: false,
    detail: `${passed} teste trecute, ${plural(failed.length, "picat", "picate")}: ${failed.join(", ")}.`,
  };
}

// ---------- Rezumatul QA ----------

function renderSummary(summary) {
  const group = (cls, title, items) => `
    <div class="sum-group ${cls}">
      <h4>${title}</h4>
      <ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>`;

  els.summary.innerHTML = `
    <div class="summary-title">Rezumat QA</div>
    ${group("good", "✓ Bun", summary.good)}
    ${group("bad", "✗ Probleme", summary.bad)}
    ${group("improve", "↑ De îmbunătățit", summary.improve)}
  `;
  els.summary.hidden = false;
}

// ---------- Contextul ales ----------

function renderContext(ctx) {
  els.budget.textContent = `${ctx.used} / ${ctx.budget} tokeni${ctx.truncated ? " · tăiat" : ""}`;
  els.context.innerHTML = ctx.items
    .map(
      (item) => `
      <div class="ctx-item">
        <div class="ctx-head">
          <span class="ctx-path">${escapeHtml(item.path)}:${item.start_line}–${item.end_line}</span>
          <span class="ctx-score">scor ${item.score.toFixed(2)}</span>
        </div>
        <div class="ctx-reason">${escapeHtml(item.reason)}</div>
        <div class="ctx-bar"><span style="width:${Math.round(item.score * 100)}%"></span></div>
        <pre class="ctx-code">${escapeHtml(item.content)}</pre>
      </div>`
    )
    .join("");
}

// ---------- Resetare ----------

function resetPanels() {
  phase = "start";
  queue = [];
  current = 0;
  accepted = [];
  els.timeline.innerHTML = "";
  els.summary.hidden = true;
  els.summary.innerHTML = "";
  els.changes.innerHTML = "";
  els.budget.textContent = "";
  els.context.innerHTML = '<div class="empty">Motorul de context n-a ales încă nimic.</div>';
  updateReview();
}

function setBusy(value) {
  busy = value;
  els.sendBtn.disabled = value;
  updateReview();
}

// ---------- Butoanele ----------

async function runAgent() {
  els.qaBtn.disabled = true;
  resetPanels();
  setBusy(true);
  setStatus("running", "Lucrează…");

  addStep({ kind: "agent", title: "Cererea ta", detail: els.prompt.value.trim() || MOCK.prompt });

  for (const step of MOCK.steps) {
    await wait(STEP_DELAY_MS);
    addStep(step, false);
    if (step.showContext) renderContext(MOCK.context);
    if (step.showChange) addChange(step.showChange, true);
  }

  phase = "coder-done";
  els.sendBtn.textContent = "Rulează din nou";
  setBusy(false);
  setStatus("done", "Gata");
  els.qaBtn.disabled = false;
}

async function runQa() {
  els.qaBtn.disabled = true;
  setBusy(true);
  setStatus("running", "QA lucrează…");

  for (const step of MOCK.qa) {
    await wait(STEP_DELAY_MS);
    addStep(step, true);
    if (step.addsChanges) step.addsChanges.forEach((id) => addChange(id, false));
    if (step.showSummary) renderSummary(MOCK.summary);
  }

  phase = "reviewing";
  current = 0;
  setBusy(false);
  setStatus("running", "Aștept decizia ta");
  focusCurrent();
}

// Acceptă sau respinge modificarea de pe ecran, apoi trece la următoarea.
function decide(accept) {
  if (busy || phase !== "reviewing") return;

  const id = queue[current];
  const card = cardFor(id);
  card.classList.remove("current");
  card.classList.add("decided", "collapsed", accept ? "applied" : "rejected");
  card.querySelector(".change-state").textContent = accept ? "Acceptată" : "Respinsă";
  if (accept) accepted.push(id);

  current += 1;
  if (current < queue.length) {
    focusCurrent();
  } else {
    finishReview();
  }
}

async function finishReview() {
  phase = "finished";
  setBusy(true);
  setStatus("running", "Aplic…");

  const rejected = queue.length - accepted.length;

  await wait(STEP_DELAY_MS);
  addStep({
    kind: "edit",
    title:
      accepted.length === 0
        ? "Nu am aplicat nicio modificare"
        : `Am aplicat ${plural(accepted.length, "modificare", "modificări")} în proiect`,
    detail: rejected === 0 ? "Ai acceptat toate modificările propuse." : `${plural(rejected, "respinsă", "respinse")} de tine.`,
  });

  if (accepted.length === 0) {
    await wait(STEP_DELAY_MS);
    addStep({ kind: "done", title: "Gata", detail: "Proiectul a rămas exact cum era." });
    setStatus("idle", "Nimic aplicat");
    setBusy(false);
    return;
  }

  await wait(STEP_DELAY_MS);
  const result = testResult(accepted);
  addStep({
    kind: "tool",
    server: "sandbox",
    title: "run_tests()",
    detail: result.detail,
    status: result.ok ? "ok" : "fail",
  });

  await wait(STEP_DELAY_MS);
  if (result.ok) {
    addStep({ kind: "done", title: "Gata", detail: "Modificările acceptate sunt acum în proiect." });
    setStatus("done", "Aplicat");
  } else {
    addStep({
      kind: "agent",
      status: "fail",
      title: "Atenție",
      detail: "Un test pică după alegerile tale. Apasă „Rulează din nou” și alege altfel.",
    });
    setStatus("warn", "Un test pică");
  }
  setBusy(false);
}

// ---------- Pornire ----------

els.project.textContent = MOCK.project;
els.agent.textContent = MOCK.agent;
els.prompt.value = MOCK.prompt;
els.sendBtn.addEventListener("click", runAgent);
els.qaBtn.addEventListener("click", runQa);
els.acceptBtn.addEventListener("click", () => decide(true));
els.rejectBtn.addEventListener("click", () => decide(false));
