const $ = (id) => document.getElementById(id);

let state = null;
let recognizing = false;
let rec = null;
let replaceId = null;
let liveBuffer = "";
const selectedLotItems = new Set();
let manualPickMode = false;
let garageOpen = false;
let editingVin = null;
let carCatalog = { makes: [], tree: {} };
function isArchivePage() {
  return /\/archive\/?$/i.test(location.pathname);
}

function navigateTo(path) {
  const qs = location.search || "";
  const next = path === "/archive" ? `/archive${qs}` : `/classic${qs}`;
  history.pushState({ page: path }, "", next);
  applyPageView();
  if (path === "/archive") loadArchive($("archiveDate")?.value);
  else refresh();
}

function setupAppNavigation() {
  $("archiveOpen")?.addEventListener("click", (ev) => {
    ev.preventDefault();
    navigateTo("/archive");
  });
  $("homeBtn")?.addEventListener("click", (ev) => {
    ev.preventDefault();
    navigateTo("/");
  });
  window.addEventListener("popstate", () => {
    applyPageView();
    if (isArchivePage()) loadArchive($("archiveDate")?.value);
    else refresh();
  });
}

function llmLabel(data) {
  if (!data.llm_configured) return "локальный разбор";
  const names = {
    yandex: "Yandex",
    qwen: "Qwen",
    openai: "OpenAI",
    "yandex+qwen": "Yandex→Qwen",
  };
  const name = names[data.llm_provider] || (data.llm_provider || "LLM");
  return data.llm_mode === "nonstandard" ? `${name}: нестандарт` : `${name} LLM`;
}

function vehicleLabel(row) {
  return [row.make, row.model, row.year, row.engine || row.displacement].filter(Boolean).join(" ");
}

function vehicleTip(item) {
  const car = vehicleLabel({
    make: item.vehicle_make,
    model: item.vehicle_model,
    year: item.vehicle_year,
    engine: item.vehicle_engine,
  });
  const plate = formatPlate(item.vehicle_plate || "");
  const vin = item.request_vin || "";
  return [car, plate, vin].filter(Boolean).join(" · ") || "Марка не указана";
}

function setLive(text) {
  $("liveText").value = text || "";
}

function getLive() {
  return ($("liveText").value || "").trim();
}

function money(v) {
  if (v == null) return "—";
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(v);
}

function statusLabel(s) {
  return {
    collecting: "накопление",
    pending_approval: "ждёт подтверждения",
    sending: "отправка",
    sent: "отправлен",
    skipped_empty: "пустой, не отправляли",
    failed: "ошибка",
    pending_review: "на проверке",
    confirmed: "подтверждена",
    rejected: "исключена",
    supplier_unknown: "поставщик не определён",
  }[s] || s;
}

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path;
  const base = location.origin && location.origin !== "null" ? location.origin : "http://127.0.0.1:8080";
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

async function api(path, opts = {}) {
  const res = await fetch(apiUrl(path), {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.error || res.statusText);
  return data;
}

function applyHeaderSnapshot(data) {
  state = data;
  const s = data.settings;
  $("trainingToggle").checked = !!s.training_mode;
  syncTrainingUi(!!s.training_mode);
  $("sendTime").value = `${String(s.send_hour).padStart(2, "0")}:${String(s.send_minute).padStart(2, "0")}`;
  $("supplierMeta").textContent = `${data.city || "Тюмень"} · ${(data.suppliers || []).map((x) => x.name).join(" · ") || data.supplier} · ${llmLabel(data)}`;
}

function applySnapshot(data) {
  applyHeaderSnapshot(data);
  const s = data.settings;
  $("lotStatus").textContent = statusLabel(data.lot.status);
  $("lotHint").textContent = s.training_mode
    ? "Обучение: лот в назначенное время сам не уйдёт — нужна кнопка подтверждения."
    : "Авторежим: в назначенное время лот уйдёт сам, если в нём есть позиции.";

  if (data.question) {
    $("question").classList.remove("hidden");
    $("question").textContent = data.question;
  } else {
    $("question").classList.add("hidden");
  }

  renderGarage(data.vehicles || []);

  syncLotSelection(data.lot_items || []);
  renderLotTable(data.lot_items || []);
  updateManualSendButton();

  const urgent = $("urgentList");
  const urgentPanel = $("urgentPanel");
  urgent.innerHTML = "";
  const urgentItems = data.urgent || [];
  if (!urgentItems.length) {
    urgentPanel.classList.add("hidden");
    $("homeMain")?.classList.remove("has-urgent");
  } else {
    urgentPanel.classList.remove("hidden");
    $("homeMain")?.classList.add("has-urgent");
    for (const item of urgentItems) urgent.appendChild(urgentCard(item));
  }

  const log = $("eventList");
  log.innerHTML = "";
  for (const ev of data.events) {
    const li = document.createElement("li");
    li.className = ev.level === "error" ? "error" : ev.level === "warn" ? "warn" : "";
    li.textContent = `${ev.created_at.slice(11, 19)}  ${ev.message}`;
    log.appendChild(li);
  }
  requestAnimationFrame(fitEventList);
}

function canPickForManualSend(item) {
  return ["pending_review", "confirmed", "failed"].includes(item.status) && !!(item.supplier || "").trim();
}

function hasPickableLotItems(items) {
  return (items || []).some(canPickForManualSend);
}

function syncLotSelection(items) {
  const valid = new Set(items.filter(canPickForManualSend).map((item) => item.id));
  for (const id of [...selectedLotItems]) {
    if (!valid.has(id)) selectedLotItems.delete(id);
  }
  if (manualPickMode && !hasPickableLotItems(items)) setManualPickMode(false);
}

function setManualPickMode(on) {
  manualPickMode = on;
  if (!on) selectedLotItems.clear();
  $("lotTable")?.classList.toggle("manual-pick-mode", on);
  if (state?.lot_items) renderLotTable(state.lot_items);
  updateManualSendButton();
}

function renderLotTable(items) {
  $("lotTable")?.classList.toggle("manual-pick-mode", manualPickMode);
  const tbody = $("lotBody");
  if (!tbody) return;
  tbody.innerHTML = "";
  for (const item of items) tbody.appendChild(itemRow(item, false));
}

function updateManualSendButton() {
  const btn = $("manualSend");
  if (!btn) return;
  const count = selectedLotItems.size;
  const pickable = hasPickableLotItems(state?.lot_items);
  if (!manualPickMode) {
    btn.textContent = "Отправить вручную";
    btn.disabled = !pickable;
    btn.classList.remove("primary");
    return;
  }
  btn.textContent = count ? `Сохранить и отправить (${count})` : "Сохранить и отправить";
  btn.disabled = count === 0;
  btn.classList.toggle("primary", count > 0);
}

function toggleLotPick(id, checked) {
  if (checked) selectedLotItems.add(id);
  else selectedLotItems.delete(id);
  updateManualSendButton();
}

function itemRow(item, urgent) {
  const tr = document.createElement("tr");
  tr.title = vehicleTip(item);
  const pickable = !urgent && manualPickMode && canPickForManualSend(item);
  const pickCell = urgent
    ? ""
    : `<td class="pick-col">${pickable ? `<input type="checkbox" class="lot-pick" title="Выбрать для отправки" />` : ""}</td>`;
  tr.innerHTML = `${pickCell}
    <td>
      <strong>${item.name || item.description}</strong>
      <div class="hint">${item.description}${item.original_required ? " · оригинал" : ""}</div>
      ${item.warning ? `<span class="warn">${item.warning}</span>` : ""}
    </td>
    <td>${item.supplier || (item.status === "supplier_unknown" ? "не определён" : "—")}</td>
    <td>${item.article || "—"}</td>
    <td class="qty-cell"></td>
    <td>${item.delivery_days ?? "—"} дн.</td>
    <td>${money(item.price)}${item.quantity > 1 ? `<div class="hint">× ${item.quantity}</div>` : ""}</td>
    <td class="status-${item.status}">${statusLabel(item.status)}${item.order_ref ? `<div class="hint">${item.order_ref}</div>` : ""}</td>
    <td></td>
  `;
  const pick = tr.querySelector(".lot-pick");
  if (pick) {
    pick.checked = selectedLotItems.has(item.id);
    pick.addEventListener("change", () => toggleLotPick(item.id, pick.checked));
  }
  const qtyCell = tr.querySelector(".qty-cell");
  const qty = Math.max(1, Number(item.quantity) || 1);
  if (item.status === "pending_review") {
    const qtyInput = document.createElement("input");
    qtyInput.type = "number";
    qtyInput.min = "1";
    qtyInput.max = "99";
    qtyInput.value = String(qty);
    qtyInput.className = "qty-input";
    qtyInput.title = "Количество в заказе";
    qtyInput.addEventListener("change", () => {
      const next = Math.max(1, Math.min(99, Number(qtyInput.value) || 1));
      qtyInput.value = String(next);
      post(`/api/items/${item.id}/quantity`, { quantity: next });
    });
    qtyCell.appendChild(qtyInput);
  } else {
    qtyCell.textContent = qty > 1 ? `${qty} шт.` : "1";
  }
  const actions = document.createElement("div");
  actions.className = "item-actions";
  if (item.status === "failed") {
    actions.appendChild(btn("Повторить", () => {
      const lotId = state?.lot?.id;
      if (lotId) post(`/api/lots/${lotId}/send-selected`, { item_ids: [item.id] });
    }, true));
    actions.appendChild(btn("Убрать", () => post(`/api/items/${item.id}/reject`)));
    actions.appendChild(btn("Заменить", () => openReplace(item.id, item.description)));
  } else if (item.status === "pending_review" || item.status === "confirmed" || item.status === "supplier_unknown") {
    if (item.status === "pending_review") {
      actions.appendChild(btn("ОК", () => post(`/api/items/${item.id}/confirm`)));
    }
    actions.appendChild(btn("Убрать", () => post(`/api/items/${item.id}/reject`)));
    actions.appendChild(btn("Заменить", () => openReplace(item.id, item.description)));
    if (urgent) actions.appendChild(btn("Отправить", () => post(`/api/items/${item.id}/send-urgent`), true));
  }
  tr.lastElementChild.appendChild(actions);
  return tr;
}

function urgentCard(item) {
  const wrap = document.createElement("div");
  wrap.className = "card";
  wrap.innerHTML = `<h3>${item.name || item.description}</h3>
    <p class="hint">${item.supplier || ""} · ${item.article || ""} · ${Math.max(1, Number(item.quantity) || 1)} шт. · ${item.delivery_days} дн. · ${money(item.price)}</p>
    <p class="status-${item.status}">${statusLabel(item.status)}</p>`;
  const actions = document.createElement("div");
  actions.className = "item-actions";
  if (item.status !== "sent" && item.status !== "rejected") {
    actions.appendChild(btn("ОК", () => post(`/api/items/${item.id}/confirm`)));
    actions.appendChild(btn("Убрать", () => post(`/api/items/${item.id}/reject`)));
    actions.appendChild(btn("Отправить сейчас", () => post(`/api/items/${item.id}/send-urgent`), true));
  }
  wrap.appendChild(actions);
  return wrap;
}

function btn(label, fn, primary = false) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  if (primary) b.className = "primary";
  b.addEventListener("click", fn);
  return b;
}

async function post(url, body) {
  try {
    const data = await api(url, { method: "POST", body: body ? JSON.stringify(body) : "{}" });
    applySnapshot(data);
    if (data.question) setLive(data.question);
    return data;
  } catch (err) {
    setLive(err.message);
    return null;
  }
}

function fillList(el, items, emptyHidden = true) {
  el.innerHTML = "";
  if (!items || !items.length) {
    if (emptyHidden) el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
  for (const item of items) {
    const p = document.createElement("p");
    p.textContent = item;
    el.appendChild(p);
  }
}

function openStatusBusy(preview) {
  const title = $("statusTitle");
  title.textContent = "Обработка заявки…";
  title.classList.remove("status-ok", "status-bad");
  $("statusSubtitle").textContent = preview || "";
  $("statusSteps").innerHTML = ["Разбор заявки", "Поиск машины в гараже", "Подбор у поставщиков", "Сохранение в лот"]
    .map((label, i) => `<li class="${i === 0 ? "run" : ""}">${label}</li>`)
    .join("");
  fillList($("statusErrors"), []);
  fillList($("statusWarnings"), []);
  $("statusModal").classList.remove("hidden");
}

function showRequestStatus(st) {
  const status = st || {};
  const title = $("statusTitle");
  const ok = !!status.ok && !(status.errors || []).length;
  title.textContent = status.title || (ok ? "Заявка принята" : "Статус заявки");
  title.classList.toggle("status-ok", ok);
  title.classList.toggle("status-bad", !ok);
  const steps = status.steps || [];
  $("statusSteps").innerHTML = steps.map((step) => {
    const label = typeof step === "string" ? step : (step.label || "");
    const state = typeof step === "string" ? "done" : (step.state || "done");
    return `<li class="${state}">${label}</li>`;
  }).join("");
  fillList($("statusErrors"), status.errors || []);
  fillList($("statusWarnings"), status.warnings || []);
  $("statusModal").classList.remove("hidden");
}

async function submitIngest(text) {
  openStatusBusy(text);
  try {
    const data = await api("/api/ingest", { method: "POST", body: JSON.stringify({ text }) });
    applySnapshot(data);
    if (data.question) setLive(data.question);
    const st = data.status || {
      ok: !!data.ok,
      title: data.ok ? "Заявка принята" : "Нужно уточнение",
      steps: [],
      errors: data.ok ? [] : [data.question || "Заявка не принята"],
      warnings: [],
    };
    showRequestStatus(st);
    if (isArchivePage()) loadArchive($("archiveDate")?.value);
  } catch (err) {
    setLive(err.message);
    showRequestStatus({
      ok: false,
      title: "Ошибка отправки",
      steps: [{ label: "Отправка на сервер", state: "error" }],
      errors: [err.message],
      warnings: [],
    });
  }
}

async function refresh() {
  try {
    const data = await api("/api/state");
    if (isArchivePage()) applyHeaderSnapshot(data);
    else applySnapshot(data);
  } catch (err) {
    if (isArchivePage()) {
      const list = $("archiveList");
      if (list && !list.querySelector(".archive-error")) {
        showArchiveError(list, "Сервер недоступен. Запустите run.bat и нажмите «Повторить».");
      }
    } else {
      setLive("Сервер недоступен: " + err.message);
    }
  }
}

function formatPlate(p) {
  if (!p) return "";
  if (p.length >= 8) return `${p[0]} ${p.slice(1, 4)} ${p.slice(4, 6)} ${p.slice(6)}`;
  return p;
}

function applyPageView() {
  const archive = isArchivePage();
  $("homeMain")?.classList.toggle("hidden", archive);
  $("archiveMain")?.classList.toggle("hidden", !archive);
  $("homeBtn")?.classList.toggle("hidden", !archive);
  $("archiveOpen")?.classList.toggle("hidden", archive);
  document.title = archive ? "Архив заявок" : "Агент запчастей";
}

function isIdlePrompt(text) {
  const t = (text || "").trim();
  return !t || /^(жду голос|слушаю|ничего не распознано|нет доступа|сначала нажмите|сервер недоступен|введите заявку)/i.test(t);
}

function sendRequest() {
  if (recognizing) stopMic(false);
  const spoken = getLive() || liveBuffer.trim();
  if (isIdlePrompt(spoken)) {
    setLive("Введите заявку в поле или нажмите «Говорить», затем «Отправить заявку».");
    $("liveText")?.focus();
    return;
  }
  submitIngest(spoken);
}

function fitEventList() {
  const list = $("eventList");
  const panel = list?.closest(".log");
  if (!list || !panel || isArchivePage()) return;
  const head = panel.querySelector("h2");
  const used = (head?.offsetHeight || 0) + 20;
  const height = Math.max(120, panel.clientHeight - used);
  list.style.maxHeight = `${height}px`;
  list.style.height = `${height}px`;
}

function syncTrainingUi(on) {
  const box = $("kitBox");
  if (box) box.classList.toggle("hidden", !on);
}

function fillDatalist(id, values) {
  const el = $(id);
  if (!el) return;
  const uniq = [...new Set((values || []).filter(Boolean))];
  el.innerHTML = uniq.map((v) => `<option value="${String(v).replace(/"/g, "&quot;")}"></option>`).join("");
}

function matchCatalogMake(value) {
  const q = (value || "").trim().toLowerCase();
  if (!q) return "";
  return (carCatalog.makes || []).find((m) => m.toLowerCase() === q) || "";
}

function matchCatalogModel(make, value) {
  const models = Object.keys((carCatalog.tree || {})[make] || {});
  const q = (value || "").trim().toLowerCase();
  if (!q) return "";
  return models.find((m) => m.toLowerCase() === q) || "";
}

function unionField(make, field) {
  const models = (carCatalog.tree || {})[make] || {};
  const out = [];
  for (const node of Object.values(models)) {
    for (const value of node[field] || []) {
      if (value && !out.includes(value)) out.push(value);
    }
  }
  return out;
}

function refreshCatalogLists() {
  const make = matchCatalogMake($("gMake")?.value || "");
  fillDatalist("makeList", carCatalog.makes || []);
  if (!make) {
    fillDatalist("modelList", []);
    fillDatalist("yearList", []);
    fillDatalist("engineList", []);
    fillDatalist("bodyList", []);
    return;
  }
  const models = Object.keys(carCatalog.tree[make] || {});
  fillDatalist("modelList", models);
  const model = matchCatalogModel(make, $("gModel")?.value || "");
  const node = model ? (carCatalog.tree[make] || {})[model] : null;
  fillDatalist("yearList", node ? node.years : unionField(make, "years"));
  fillDatalist("engineList", node ? node.engines : unionField(make, "engines"));
  fillDatalist("bodyList", node ? node.bodies : unionField(make, "bodies"));
}

async function loadCatalog() {
  try {
    carCatalog = await api("/api/catalog");
    refreshCatalogLists();
  } catch {
    carCatalog = { makes: [], tree: {} };
  }
}

function setGarageOpen(open) {
  garageOpen = !!open;
  $("gToggle").textContent = garageOpen ? "Скрыть список" : "Показать список";
  $("gSearch").classList.toggle("hidden", !garageOpen);
  $("garageList").classList.toggle("hidden", !garageOpen);
}

function renderGarage(rows) {
  const list = $("garageList");
  if (!list) return;
  setGarageOpen(garageOpen);
  const q = ($("gSearch")?.value || "").trim().toLowerCase();
  const qDigits = q.replace(/\D/g, "");
  list.innerHTML = "";
  const filtered = rows.filter((row) => {
    if (!q) return true;
    const plateDigits = (row.plate_digits || row.plate || "").replace(/\D/g, "");
    if (/^\d+$/.test(q) && qDigits.length >= 3) {
      return plateDigits.includes(qDigits);
    }
    const hay = `${row.make} ${row.model} ${row.year} ${row.engine} ${row.plate} ${row.vin}`.toLowerCase();
    return hay.includes(q) || (qDigits.length >= 3 && plateDigits.includes(qDigits));
  });
  if (!filtered.length) {
    list.innerHTML = "<li class='hint'>Пока пусто — сохраните VIN, марку и номер</li>";
    return;
  }
  for (const row of filtered) {
    const li = document.createElement("li");
    const info = document.createElement("div");
    info.className = "car";
    info.innerHTML = `<strong>${vehicleLabel(row) || "Авто"}</strong> · ${formatPlate(row.plate) || "без номера"}<div class="hint">${row.vin}${row.spec_key ? " · " + row.spec_key : ""}</div>`;
    info.title = "Подставить в заявку";
    info.addEventListener("click", () => {
      const prefix = `${formatPlate(row.plate) || row.vin}, `;
      setLive(prefix);
      liveBuffer = prefix;
      $("liveText")?.focus();
    });
    const actions = document.createElement("div");
    actions.className = "row-actions";
    const editing = editingVin === row.vin;
    const editBtn = btn(editing ? "Сохранить" : "Редактировать", () => {
      if (editingVin === row.vin) {
        saveVehicle().then(() => {
          editingVin = null;
          renderGarage(state?.vehicles || []);
        });
        return;
      }
      editingVin = row.vin;
      $("gVin").value = row.vin || "";
      $("gMake").value = row.make || "";
      $("gPlate").value = row.plate || "";
      $("gModel").value = row.model || "";
      $("gYear").value = row.year || "";
      $("gEngine").value = row.engine || "";
      $("gBody").value = row.body || "";
      refreshCatalogLists();
      renderGarage(state?.vehicles || []);
      fillKitForm();
    });
    if (editing) editBtn.className = "primary";
    const del = btn("В архив", () => api(`/api/vehicles/${row.vin}`, { method: "DELETE" }).then((data) => {
      if (editingVin === row.vin) editingVin = null;
      applySnapshot(data);
    }));
    actions.appendChild(editBtn);
    actions.appendChild(del);
    li.appendChild(info);
    li.appendChild(actions);
    list.appendChild(li);
  }
}

function kitPayload() {
  return {
    kit_key: $("kitName")?.value.trim() || "Комплект ГРМ",
    vin: $("gVin")?.value.trim() || "",
    make: $("gMake")?.value.trim() || "",
    model: $("gModel")?.value.trim() || "",
    engine: $("gEngine")?.value.trim() || "",
  };
}

async function fillKitForm() {
  const status = $("kitStatus");
  const payload = kitPayload();
  if (!payload.vin && !payload.make) return;
  try {
    const query = new URLSearchParams(payload);
    const data = await api("/api/kits?" + query.toString());
    if ($("kitText") && data.stored) $("kitText").value = data.text || "";
    if (status) {
      status.textContent = data.stored
        ? `${data.title} для ${data.label}: ${(data.parts || []).length} позиций`
        : `Для ${data.label || "этой марки"} пока названия без артикулов. Вставьте номера.`;
    }
  } catch (err) {
    if (status) status.textContent = err.message;
  }
}

function saveVehicle() {
  return post("/api/vehicles", {
    vin: $("gVin").value.trim(),
    make: $("gMake").value.trim(),
    plate: $("gPlate").value.trim(),
    model: $("gModel").value.trim(),
    year: $("gYear").value.trim(),
    engine: $("gEngine").value.trim(),
    body: $("gBody").value.trim(),
  });
}

function showArchiveError(list, message) {
  list.innerHTML = "";
  const li = document.createElement("li");
  li.className = "hint error";
  li.textContent = message || "Сервер недоступен. Запустите run.bat.";
  const retry = btn("Повторить", () => loadArchive($("archiveDate")?.value));
  retry.className = "primary";
  const wrap = document.createElement("div");
  wrap.className = "archive-error";
  wrap.appendChild(li);
  wrap.appendChild(retry);
  list.appendChild(wrap);
}

async function loadArchive(day, errorMessage = "") {
  const picker = $("archiveDate");
  const list = $("archiveList");
  if (!picker || !list) return;
  const query = day || picker.value || "";
  list.innerHTML = "<li class='hint'>Загрузка архива…</li>";
  try {
    const data = await api(`/api/archive${query ? `?date=${encodeURIComponent(query)}` : ""}`);
    if (data.date) picker.value = data.date;
    list.innerHTML = "";
    if (!data.requests || !data.requests.length) {
      list.innerHTML = "<li class='hint'>Заявок на эту дату нет</li>";
      return;
    }
    for (const req of data.requests) {
      const li = document.createElement("li");
      const head = document.createElement("div");
      head.className = "arch-head";
      const info = document.createElement("div");
      const when = (req.created_at || "").slice(11, 19);
      const car = [req.vehicle_make, formatPlate(req.vehicle_plate), req.vin].filter(Boolean).join(" · ") || "машина не указана";
      info.innerHTML = `<strong>${when}</strong> · ${car}<div class="hint">${req.raw_text || ""}</div>`;
      const parts = document.createElement("p");
      parts.className = "parts";
      const items = req.items || [];
      parts.textContent = items.length
        ? items.map((it) => `${it.name || it.description}${it.supplier ? " (" + it.supplier + ")" : ""}`).join(" · ")
        : (req.clarifying_question || req.status);
      const send = btn("Отправить снова", () => {
        submitIngest(req.raw_text);
      }, true);
      head.appendChild(info);
      head.appendChild(send);
      li.appendChild(head);
      li.appendChild(parts);
      list.appendChild(li);
    }
  } catch (err) {
    const msg = errorMessage || err.message || "Сервер недоступен";
    const hint = /failed to fetch|networkerror|load failed/i.test(msg)
      ? "Сервер недоступен. Запустите run.bat и нажмите «Повторить»."
      : msg;
    showArchiveError(list, hint);
  }
}

function openReplace(id, current) {
  replaceId = id;
  $("replaceText").value = current || "";
  $("replaceModal").classList.remove("hidden");
}

function setupMic() {
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  const btn = $("micBtn");
  if (!btn) return;
  if (!Speech) {
    btn.textContent = "Голос: откройте Chrome или Edge";
    setLive("Распознавание речи есть в Chrome и Edge. Можно ввести заявку текстом.");
    return;
  }
  rec = new Speech();
  rec.lang = "ru-RU";
  rec.interimResults = true;
  rec.continuous = true;
  rec.maxAlternatives = 1;
  rec.onresult = (ev) => {
    let finalText = "";
    let interim = "";
    for (let i = ev.resultIndex; i < ev.results.length; i += 1) {
      const chunk = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finalText += chunk;
      else interim += chunk;
    }
    if (finalText) liveBuffer += (liveBuffer ? " " : "") + finalText.trim();
    setLive((liveBuffer + " " + interim).trim() || "Слушаю…");
  };
  rec.onerror = (ev) => {
    const map = {
      "not-allowed": "Нет доступа к микрофону. Разрешите его в замке слева от адреса.",
      "service-not-allowed": "Браузер запретил распознавание речи.",
      "audio-capture": "Микрофон не найден.",
      "network": "Нужен интернет для распознавания в браузере.",
      "no-speech": "Речь не услышана. Нажмите «Говорить» и повторите.",
      "aborted": "",
    };
    const msg = map[ev.error];
    if (ev.error !== "aborted" && ev.error !== "no-speech") {
      setLive(msg || `Ошибка микрофона: ${ev.error}`);
    }
    if (ev.error !== "no-speech") stopMic(false);
  };
  rec.onend = () => {
    if (recognizing) {
      try { rec.start(); } catch { /* restart while toggled on */ }
    }
  };

  btn.addEventListener("click", async () => {
    if (recognizing) {
      stopMic(false);
      return;
    }
    try {
      if (navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop());
      }
    } catch (err) {
      setLive("Нет доступа к микрофону. Разрешите его для этого сайта.");
      return;
    }
    liveBuffer = "";
    recognizing = true;
    btn.classList.add("hot");
    btn.textContent = "Слушаю… нажмите ещё раз";
    setLive("");
    $("liveText").placeholder = "Слушаю. Назовите госномер или VIN и детали, затем нажмите кнопку снова.";
    try {
      rec.start();
    } catch (err) {
      setLive("Не удалось запустить голос: " + err.message);
      recognizing = false;
      btn.classList.remove("hot");
      btn.textContent = "Говорить";
    }
  });
}

function stopMic(submit) {
  const btn = $("micBtn");
  recognizing = false;
  btn.classList.remove("hot");
  btn.textContent = "Говорить";
  $("liveText").placeholder = "Голос или текст: госномер или VIN и список деталей. Ctrl+Enter — отправить.";
  try { rec && rec.stop(); } catch { /* ignore */ }
  const text = liveBuffer.trim() || getLive();
  if (text && !text.startsWith("Слушаю")) {
    setLive(text);
    liveBuffer = text;
    $("liveText").focus();
  } else if (submit && !text) {
    setLive("Ничего не распознано. Нажмите «Говорить», скажите заявку, нажмите ещё раз.");
  }
}

$("trainingToggle").addEventListener("change", () => {
  syncTrainingUi($("trainingToggle").checked);
  post("/api/settings", { training_mode: $("trainingToggle").checked });
});
$("sendTime").addEventListener("change", () => {
  const [h, m] = $("sendTime").value.split(":");
  post("/api/settings", { send_hour: Number(h), send_minute: Number(m) });
});
$("confirmAll").addEventListener("click", () => {
  if (state?.lot?.id) post(`/api/lots/${state.lot.id}/confirm-all`);
});
$("approveSend").addEventListener("click", () => {
  if (state?.lot?.id) post(`/api/lots/${state.lot.id}/approve-send`);
});
$("manualSend").addEventListener("click", async () => {
  if (!manualPickMode) {
    setManualPickMode(true);
    return;
  }
  const lotId = state?.lot?.id;
  const ids = [...selectedLotItems];
  if (!lotId || !ids.length) return;
  const data = await post(`/api/lots/${lotId}/send-selected`, { item_ids: ids });
  if (data) setManualPickMode(false);
});
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && manualPickMode) setManualPickMode(false);
});
$("runDue").addEventListener("click", () => post("/api/lots/run-due"));
$("sendVoice").addEventListener("click", sendRequest);
$("liveText").addEventListener("input", () => {
  liveBuffer = getLive();
});
$("liveText").addEventListener("keydown", (ev) => {
  if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") {
    ev.preventDefault();
    sendRequest();
  }
});
$("gSave").addEventListener("click", () => {
  saveVehicle().then(async () => {
    editingVin = null;
    await loadCatalog();
    refreshCatalogLists();
    renderGarage(state?.vehicles || []);
    fillKitForm();
  });
});
$("kitLoad")?.addEventListener("click", async () => {
  const status = $("kitStatus");
  const text = ($("kitText")?.value || "").trim();
  if (!text) {
    if (status) status.textContent = "Вставьте артикулы, по одному на строку.";
    return;
  }
  try {
    const data = await api("/api/kits", { method: "POST", body: JSON.stringify({ ...kitPayload(), text }) });
    applySnapshot(data);
    if (status) {
      status.textContent = data.kit
        ? `Сохранено: ${data.kit.parts.length} позиций для ${data.kit.label}`
        : "Сохранено";
    }
  } catch (err) {
    if (status) status.textContent = err.message;
  }
});
$("gToggle").addEventListener("click", () => {
  setGarageOpen(!garageOpen);
});
$("gMake")?.addEventListener("input", refreshCatalogLists);
$("gMake")?.addEventListener("change", refreshCatalogLists);
$("gModel")?.addEventListener("input", refreshCatalogLists);
$("gModel")?.addEventListener("change", refreshCatalogLists);
$("gSearch").addEventListener("input", () => renderGarage(state?.vehicles || []));
function openArchiveCalendar() {
  const picker = $("archiveDate");
  if (!picker) return;
  picker.focus();
  if (typeof picker.showPicker === "function") {
    try {
      picker.showPicker();
    } catch {
      picker.click();
    }
  }
}

function setupArchiveDatePicker() {
  const picker = $("archiveDate");
  if (!picker) return;
  picker.closest("label")?.addEventListener("click", (ev) => {
    if (ev.target !== picker) {
      ev.preventDefault();
      openArchiveCalendar();
    }
  });
  picker.addEventListener("click", openArchiveCalendar);
  picker.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      openArchiveCalendar();
    }
  });
  picker.addEventListener("change", () => loadArchive(picker.value));
}
$("statusClose").addEventListener("click", () => $("statusModal").classList.add("hidden"));
$("statusModal").addEventListener("click", (ev) => {
  if (ev.target === $("statusModal")) $("statusModal").classList.add("hidden");
});
$("replaceCancel").addEventListener("click", () => $("replaceModal").classList.add("hidden"));
$("replaceOk").addEventListener("click", () => {
  const description = $("replaceText").value.trim();
  $("replaceModal").classList.add("hidden");
  if (replaceId && description) post(`/api/items/${replaceId}/replace`, { description });
});

applyPageView();
setupAppNavigation();
setupArchiveDatePicker();
setupMic();
loadCatalog();
refresh();
if (isArchivePage()) loadArchive();
setInterval(refresh, 4000);
window.addEventListener("resize", fitEventList);
