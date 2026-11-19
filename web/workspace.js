import { connectVehicleCatalog } from './vehicle-catalog.js';

const icons = {
  car: 'M5 17H3v-5l2-2 2-5h10l2 5 2 2v5h-2M5 17h14M5 17v2H3v-2m16 0v2h2v-2M5 10h14M6 14h2m8 0h2',
  search: 'M21 21l-5-5m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
  calendar: 'M4 6h16v15H4zM4 10h16M8 3v5m8-5v5',
  bolt: 'M13 2 4 14h7l-1 8 10-12h-7z',
  doc: 'M6 3h8l4 4v14H6zM14 3v5h4M9 12h6m-6 4h6',
  link: 'M10 14l4-4m-6 6-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 10a4 4 0 0 0 6 0l4-4a4 4 0 0 0-6-6l-1 1',
  gear: 'M10 2h4l1 3 3 1 3 1v4l-2 2v2l1 3-3 3-3-1h-3l-3 1-3-3 1-3v-2l-3-2V7l3-1 3-1zM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 8-3 8h18s-3-1-3-8m-8 12h4',
  user: 'M20 21v-3a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v3zM16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  clock: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0M12 6v6l4 3',
  help: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01',
  cart: 'M2 3h3l3 13h11l3-10H6m3 14h.01m9 0h.01',
  pencil: 'M4 16 16 4l4 4L8 20H4zm10-10 4 4',
  swap: 'M3 7h18l-4-4m4 14H3l4 4',
  copy: 'M9 7h11v14H9zM15 7V3H4v14h5',
  plus: 'M12 4v16M4 12h16',
  trash: 'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15m-8 4v7m4-7v7',
  check: 'm4 12 5 5L20 6',
  filter: 'M3 4h18l-7 8v6l-4 2v-8z',
  close: 'm6 6 12 12M18 6 6 18',
  info: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0m-10-1v6m0-10h.01',
  refresh: 'M21 4v6h-6M3 20v-6h6m-6-3a9 9 0 0 1 15-6l3 5M3 14l3 5a9 9 0 0 0 15-6',
  more: 'M5 12h.01m7 0h.01m7 0h.01',
};
const svg = name => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[name]}"/></svg>`;
const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[ch]));
const e = escape;
const $ = selector => document.querySelector(selector);
const content = $('#content');
const modal = $('#modal');
const sections = [
  ['requests', 'Заявки и поиск', 'search'], ['garage', 'Гараж', 'car'],
  ['lots', 'Дневной лот', 'calendar'], ['urgent', 'Срочные позиции', 'bolt'],
  ['orders', 'История заказов', 'doc'], ['suppliers', 'Подключения', 'link'],
  ['settings', 'Настройки', 'gear'],
];
const sources = { rossko: 'Росско', partkom: 'ПартКом', emex: 'Emex', exist: 'Exist' };
const resultLabels = { OK: 'Есть предложения', NO_OFFERS: 'Нет предложений', NO_ACCESS: 'Источник отключён',
  TEMPORARY_ERROR: 'Временная ошибка', NOT_QUERIED: 'Не опрошен' };
const labels = {
  workspace_draft: 'Черновик', workspace_cancelled: 'Отменена', workspace_complete: 'Оформлена',
  workspace_in_progress: 'В работе', open: 'Открыт', empty: 'Нет позиций', closed: 'На подтверждении',
  sending: 'Отправляется', manual: 'Требуется оформление в кабинете', accepted: 'Принят поставщиком',
  manual_confirmed: 'Подтверждён сотрудником', error: 'Ошибка', unknown: 'Результат неизвестен',
  cancelled: 'Отменён', partial: 'Частичный результат', complete: 'Завершён',
};
const formats = {
  stamp: new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Yekaterinburg' }),
  time: new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Yekaterinburg' }),
  day: new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }),
};
const when = (value, type = 'stamp') => value ? formats[type].format(new Date(value)) : '—';
const money = (value, currency = 'RUB') => value == null ? '—' :
  new Intl.NumberFormat('ru-RU', { style: 'currency', currency }).format(value / 100);
const dateRange = offer => !offer?.date_from ? 'Срок не определён' :
  offer.date_from === offer.date_to ? when(offer.date_to, 'day') : `${when(offer.date_from, 'day')} – ${when(offer.date_to, 'day')}`;
const pillar = (text, tone = '') => `<span class="pill ${tone}">${e(text)}</span>`;
const badge = status => pillar(labels[status] || status,
  ['accepted', 'manual_confirmed', 'complete', 'open', 'workspace_complete'].includes(status) ? 'ok' :
  ['unknown', 'manual', 'closed', 'partial', 'sending'].includes(status) ? 'warn' : status === 'error' ? 'bad' : '');
const button = (action, label, opts = {}) => `<button type="button" data-action="${e(action)}"
  ${opts.value != null ? `data-value="${e(opts.value)}"` : ''} class="${opts.className || ''}"
  ${opts.disabled ? 'disabled' : ''} ${opts.title ? `title="${e(opts.title)}" aria-label="${e(opts.title)}"` : ''}>
  ${opts.icon ? svg(opts.icon) : ''}${e(label)}</button>`;
const iconButton = (action, title, icon, value, disabled) => button(action, '', {
  title, icon, value, disabled, className: 'quiet icon-button',
});
const staffCanBuy = () => ['buyer', 'admin'].includes(state.overview?.user.role);
const isAdmin = () => state.overview?.user.role === 'admin';
const link = (href, label) => `<a href="${e(href)}">${e(label)}</a>`;
const empty = message => `<div class="panel empty">${e(message)}</div>`;
const supplier = code => `<span class="nowrap"><span class="supplier-mark ${e(code)}">${e(sources[code]?.[0])}</span><b>${e(sources[code] || code)}</b></span>`;
const valued = (row, key) => row?.[key] || '—';
const options = (values, checked) => Object.entries(values).map(([key, label]) =>
  `<option value="${e(key)}" ${key === String(checked ?? '') ? 'selected' : ''}>${e(label)}</option>`).join('');
const input = (label, name, value = '', attrs = '') => `<label class="field"><span>${e(label)}</span><input name="${name}" value="${e(value)}" ${attrs}></label>`;
const checkbox = (label, name, checked, attrs = '') => `<label><input type="checkbox" name="${name}" ${checked ? 'checked' : ''} ${attrs}> ${e(label)}</label>`;
const select = (label, name, values, checked) => `<label class="field"><span>${e(label)}</span><select name="${name}">${options(values, checked)}</select></label>`;
const table = (head, rows, cls = '') => `<div class="table-wrap"><table class="${cls}"><thead><tr>
  ${head.map(title => `<th scope="col">${typeof title === 'string' ? e(title) : title.html}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`;
const cells = values => values.map(value => `<td>${value}</td>`).join('');

const state = { overview: null, draft: null, active: null, checked: new Set(), data: null, filters: {},
  supplierFilters: new Set(Object.keys(sources)), epoch: 0, loading: false };
const route = () => {
  const [, path, key] = location.pathname.split('/');
  return { path: path || 'requests', key: key ? decodeURIComponent(key) : null };
};
const writableDraft = () => state.draft && state.draft.status !== 'workspace_cancelled';

async function api(path, method = 'GET', data) {
  const reply = await fetch('/api/workspace' + path, {
    method,
    headers: data === undefined ? {} : { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (reply.status === 401 && route().path !== 'login') {
    location.assign('/login');
    throw new Error('Войдите в систему');
  }
  if (!reply.ok) {
    const body = await reply.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map(row => `${row.loc?.at(-1)} · ${row.msg}`).join(', ') : body.detail;
    throw new Error(detail || `Сервер вернул ошибку ${reply.status}`);
  }
  return reply.json();
}

let toastTimeout;
function notify(message, bad = false) {
  const toast = $('#notice');
  toast.textContent = message;
  toast.classList.toggle('error', bad);
  toast.hidden = false;
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => { toast.hidden = true; }, bad ? 9000 : 4000);
}

function closeModal() { modal.close(); }
function dialog(title, html, confirmLabel, submit) {
  modal.innerHTML = `<form class="dialog-body"><div class="section-head"><h2 id="modal-title">${e(title)}</h2>
    <button type="button" class="quiet icon-button" data-close aria-label="Закрыть">${svg('close')}</button></div>
    ${html}<div class="hint warn" data-dialog-error role="alert" hidden></div>
    <div class="actions"><button type="button" class="quiet" data-close>${submit ? 'Отмена' : 'Закрыть'}</button>
    ${submit ? `<button class="primary" type="submit">${e(confirmLabel)}</button>` : ''}</div></form>`;
  const form = modal.querySelector('form');
  for (const control of modal.querySelectorAll('[data-close]')) control.onclick = closeModal;
  form.onsubmit = async event => {
    event.preventDefault();
    if (!submit || modal.dataset.busy) return;
    const error = form.querySelector('[data-dialog-error]');
    const submitButton = form.querySelector('[type=submit]');
    submitButton.disabled = true;
    modal.dataset.busy = 'true';
    error.hidden = true;
    for (const control of form.querySelectorAll('[data-close]')) control.disabled = true;
    try { await submit(new FormData(form), form); }
    catch (err) { error.textContent = err.message; error.hidden = false; }
    finally {
      delete modal.dataset.busy;
      submitButton.disabled = false;
      for (const control of form.querySelectorAll('[data-close]')) control.disabled = false;
    }
  };
  if (!modal.open) modal.showModal();
  return form;
}
modal.addEventListener('cancel', event => { if (modal.dataset.busy) event.preventDefault(); });

function go(path, replace = false) {
  if (location.pathname + location.search !== path) history[replace ? 'replaceState' : 'pushState']({}, '', path);
  return load();
}

function fitText(row, offer) {
  if (offer?.fit === 'catalogue') return pillar('Применимость подтверждена', 'ok');
  if (offer && row.manual_basis?.catalogue === offer.catalogue) return pillar('Ручная проверка', 'warn');
  return pillar('Требуется ручная проверка', 'warn');
}
const outdated = (offer, ttl = state.overview?.settings.ttl || 15) =>
  Date.now() - new Date(offer?.checked_at || 0).getTime() > ttl * 60_000 || (!state.overview?.sources[offer.supplier]?.enabled ||
    (offer.source_revision || 1) !== state.overview.sources[offer.supplier].revision);
const offerTotal = (offer, qty) => offer.price == null ? null : offer.price * qty + (offer.delivery ?? 0);

function lineState(row) {
  if (row.order) return badge(row.order.status);
  if (row.conditions_delta) return pillar('Условия изменились', 'warn');
  if (row.workspace_lot) return pillar('В дневном лоте', 'ok');
  if (row.urgent) return pillar('Срочная позиция', 'warn');
  if (row.selection) return pillar('Предложение выбрано', 'ok');
  if (!row.search_result) return pillar('Готово к подбору');
  if (row.search_result.needs_detail) return pillar('Требуется уточнение', 'warn');
  if (!row.search_result.offers.length) return pillar('Нет предложений', 'warn');
  return fitText(row, row.search_result.offers[0]);
}

function sumLines(rows) {
  const currencies = new Map();
  for (const row of rows) {
    const offer = row.selection || row.offer;
    if (!offer || offer.price == null) continue;
    const totals = currencies.get(offer.currency) || { products: 0, delivery: 0, preliminary: false };
    totals.products += offer.price * row.quantity;
    totals.delivery += offer.delivery ?? 0;
    totals.preliminary ||= offer.delivery == null;
    currencies.set(offer.currency, totals);
  }
  return currencies;
}

function totalsView(rows) {
  const values = Array.from(sumLines(rows));
  if (!values.length) return '<p class="muted">Сумма появится после выбора предложения.</p>';
  return values.map(([currency, s]) => `<div class="panel totals"><p><span>Товары</span><b>${money(s.products, currency)}</b></p>
    <p><span>Доставка</span><b>${s.preliminary ? 'Известная часть · ' : ''}${money(s.delivery, currency)}</b></p>
    <p class="total"><span>Итого к оформлению</span><span>${money(s.products + s.delivery, currency)}</span></p>
    ${s.preliminary ? '<small>Предварительно · часть доставки не рассчитана</small>' : ''}</div>`).join('');
}

function summarySum(rows) {
  return Array.from(sumLines(rows), ([currency, s]) =>
    money(s.products + s.delivery, currency) + (s.preliminary ? ' (предв.)' : '')).join(' · ') || '—';
}

function chrome() {
  const data = state.overview;
  const current = route().path;
  $('#title').textContent = sections.find(([path]) => path === current)?.[1] || 'Заявки и поиск';
  $('.brand-icon').innerHTML = svg('car');
  $('#nav').innerHTML = sections.map(([path, title, icon]) => {
    const count = data?.counts[path === 'lots' ? 'lot' : path];
    return `<a href="/${path}" class="nav-link" title="${title}" aria-label="${title}" ${current === path ? 'aria-current="page"' : ''}>
      ${svg(icon)}<span class="nav-label">${title}</span>${path === 'suppliers' ? sourceIndicator(data) : ''}${count ? `<span class="counter ${path === 'urgent' ? 'alert' : ''}">${count}</span>` : ''}</a>`;
  }).join('');
  $('#header-tools').innerHTML = `${data ? pillar('Демо-режим', 'warn') : ''}
    ${iconButton('notifications', 'Уведомления' + (data?.unread ? ` (${data.unread})` : ''), 'bell')}
    ${data?.unread ? `<span class="counter alert">${data.unread}</span>` : ''}
    ${data ? `<div class="profile">${svg('user')}<div><strong>${e(data.user.name)}</strong><small>${{
      employee: 'Сотрудник', buyer: 'Закупщик', admin: 'Администратор',
    }[data.user.role] || ''}</small></div></div>` : ''}
    <div class="clock">${svg('clock')}<div><strong>Екатеринбург (ЕКБ)</strong><small id="clock"></small></div></div>
    ${iconButton('help', 'Справка', 'help')}`;
  updateClock();
  statusbar();
}

function sourceIndicator(data) {
  const enabled = Object.values(data?.sources || {}).filter(source => source.enabled);
  const healthy = enabled.filter(source => ['OK','NO_OFFERS'].includes(source.last_status)).length;
  const good = enabled.length > 0 && healthy === enabled.length;
  const failed = !enabled.length || enabled.every(source => source.last_status === 'TEMPORARY_ERROR');
  const title = good ? 'Все включённые демо-источники проверены' :
    failed ? 'Демо-источники недоступны' : 'Демо-источники проверены частично';
  return `<span class="source-dot ${good ? 'ok' : failed ? 'bad' : ''}" title="${title}" aria-label="${title}"></span>`;
}

function updateClock() {
  const clock = $('#clock');
  if (clock) clock.textContent = when(new Date());
}
setInterval(updateClock, 15000);

function statusbar() {
  const data = state.overview;
  const result = route().path === 'requests' ? activeItem()?.search_result : null;
  const enabled = Object.keys(data?.sources || {}).filter(key => data.sources[key].enabled);
  const partial = result && enabled.some(key => !['OK', 'NO_OFFERS'].includes(result.sources[key]));
  const stale = result && result.offers.some(o => outdated(o));
  const fresh = result && result.offers.length && !partial && !stale;
  $('#statusbar').innerHTML = `<span class="${data ? 'ready' : 'muted'}">${svg(data ? 'check' : 'info')} ${data ? 'Система готова' : 'Нет данных сервера'}</span>
    <span class="status-sources"><b>Источники · демо</b>${Object.entries(sources).map(([key, name]) =>
      `<span title="${e(resultLabels[result?.sources[key] || data?.sources[key]?.last_status] || 'Не проверен')}">${name}
        ${data?.sources[key]?.enabled === 0 ? '—' : (result?.sources[key] || data?.sources[key]?.last_status) === 'OK' ? '✓' :
        (result?.sources[key] || data?.sources[key]?.last_status) === 'TEMPORARY_ERROR' ? '!' : '·'}</span>`).join('')}</span>
    <span>${result ? 'Проверка · ' + when(result.at, 'time') : 'Цены не проверялись'}</span>
    <span>${pillar(stale ? 'Данные устарели' : partial ? 'Частичная проверка' : fresh ? 'Данные актуальны' :
      result ? 'Предложений нет' : 'Проверка не запускалась', stale || partial ? 'warn' : fresh ? 'ok' : '')}</span>`;
}
setInterval(statusbar, 30000);

async function load({ quiet = false } = {}) {
  const epoch = ++state.epoch;
  const path = route();
  if (path.path === 'login') { renderLogin(); return; }
  if (!quiet) { content.scrollTop = 0; content.innerHTML = empty('Загрузка…'); }
  try {
    const overview = await api('/overview');
    let data;
    if (path.path === 'requests') {
      const list = await api('/requests');
      const identifier = path.key || list.find(row => row.status !== 'workspace_cancelled')?.id;
      data = { list, draft: identifier ? await api('/requests/' + identifier) : null };
    } else if (path.path === 'garage') {
      const query = new URLSearchParams(location.search);
      data = { vehicles: await api('/vehicles?' + query), car: path.key ? await api('/vehicles/' + encodeURIComponent(path.key)) : null };
    } else if (path.path === 'lots') {
      data = await api('/lots' + (path.key ? '?day=' + encodeURIComponent(path.key) : ''));
    } else if (path.path === 'orders') {
      data = path.key ? await api('/orders/' + encodeURIComponent(path.key)) : await api('/orders' + location.search);
    } else if (path.path === 'urgent' || path.path === 'suppliers') {
      data = await api('/' + path.path);
    }
    if (epoch !== state.epoch) return;
    const first = !state.overview;
    state.overview = overview;
    if (first) state.filters = { ...overview.settings };
    state.data = data;
    if (path.path === 'requests') {
      if (state.draft?.id !== data.draft?.id) {
        state.active = null;
        state.checked.clear();
      }
      state.draft = data.draft;
      if (!activeItem()) state.active = state.draft?.items[0]?.id;
    }
    chrome();
    render();
  } catch (err) {
    if (epoch !== state.epoch) return;
    chrome();
    content.innerHTML = `<div class="panel pad stack"><h2>Не удалось загрузить раздел</h2><p>${e(err.message)}</p>
      <div>${button('reload', 'Повторить', { icon: 'refresh' })}</div></div>`;
  }
}

function activeItem() { return state.draft?.items.find(row => row.id === state.active); }

function render() {
  const { path, key } = route();
  const views = { requests: dashboard, garage: garagePage, lots: lotPage, urgent: urgentPage,
    orders: key ? orderDetail : orderList, suppliers: suppliersPage, settings: settingsPage };
  content.innerHTML = (views[path] || dashboard)();
  statusbar();
}

function vehicleCard(car, { request = false, editable = true } = {}) {
  const name = [car?.make, car?.model, car?.generation].filter(Boolean).join(' ') || 'Автомобиль не выбран';
  return `<section class="panel vehicle-banner"><div class="car-art">${svg('car')}</div><div>
    <div class="section-head"><h2 class="vehicle-name">${e(name)}</h2><div class="actions">
      ${car && editable ? button('edit-car', 'Редактировать', { icon: 'pencil' }) : ''}
      ${request && editable ? button('switch-car', car ? 'Сменить авто' : 'Выбрать авто', { icon: 'swap' }) : ''}</div></div>
    ${car ? `<div class="vehicle-ids"><span>VIN: <b>${e(car.vin)}</b></span>${iconButton('copy', 'Копировать VIN', 'copy', car.vin)}
      <span>Госномер: <b>${e(valued(car, 'plate'))}</b></span>${car.plate ? iconButton('copy', 'Копировать госномер', 'copy', car.plate) : ''}</div>
      <div class="car-spec">${[['Марка','make'],['Модель','model'],['Год','year'],['Двигатель','engine'],['Кузов','body']]
        .map(([label, key]) => `<span><small>${label}</small><b>${e(valued(car, key))}</b></span>`).join('')}</div>` :
      '<p class="muted">Выберите автомобиль из гаража или добавьте новый. Черновик можно заполнить заранее.</p>'}
    </div></section>`;
}

function dashboard() {
  const draft = state.draft;
  const row = activeItem();
  const choices = draft?.items.filter(i => i.selection && !i.order) || [];
  return `<div class="dashboard"><div class="main-column">
    ${vehicleCard(draft?.vehicle, { request: true, editable: !draft || writableDraft() })}
    <section class="panel request-bar toolbar split">
      <div class="toolbar">${svg('doc')}
      <select id="draft-select" aria-label="Открыть заявку"><option value="">Выберите заявку</option>
        ${state.data.list.map(r => `<option value="${r.id}" ${r.id === draft?.id ? 'selected' : ''}>Заявка № ${r.id}${r.status === 'workspace_cancelled' ? ' · отменена' : ''}</option>`).join('')}</select>
      ${draft ? badge(draft.status) + '<small>' + when(draft.created_at) + '</small>' : ''}</div>
      <div class="actions">${button('new', 'Новая заявка', { icon: 'plus' })}
        ${button('parse', 'Разобрать заявку', { icon: 'doc', disabled: !!draft && !writableDraft() })}
        ${button('add-item', 'Добавить позицию', { icon: 'plus', disabled: !!draft && !writableDraft() })}
        ${draft ? iconButton('draft-menu', 'Действия с заявкой', 'more') : ''}</div>
    </section>
    ${draft?.items.length ? draftTable(draft.items) : empty('Добавьте позицию вручную или разберите текст заявки.')}
    ${!draft ? `<div class="toolbar">${button('example', 'Создать учебный пример', { icon: 'car' })}
      ${state.overview.shared ? '' : '<a class="button quiet" href="/classic">Голосовой помощник и прежние заявки</a>'}</div>` : ''}
    <form id="search-form" class="search-line"><div class="search-field">${svg('search')}
      <input name="query" aria-label="Описание или артикул детали" placeholder="Описание позиции или точный артикул"
        value="${e(row?.search_result?.query || row?.article || row?.description || '')}" ${row?.order ? 'readonly' : ''}>
      ${iconButton('clear-search', 'Очистить поиск', 'close', null, !row || !!row.order)}</div>
      <button class="primary" ${!row || row.order ? 'disabled' : ''}>${svg('search')} Найти предложения</button></form>
    ${offerFilters()}
    ${row ? offerTable(row) : empty('Выберите позицию заявки. Здесь появятся предложения поставщиков.')}
    ${draft?.items.filter(entry => entry.id !== row?.id && state.checked.has(entry.id) && entry.search_result).map(entry =>
      `<details class="panel pad"><summary>${e(entry.description)} · ${entry.search_result.offers.length} предложений</summary>
      ${offerTable(entry)}</details>`).join('') || ''}
    <div class="hint">${svg('info')} <b>Применимость</b> · Учебный каталог подтверждает только известную связку автомобиля и детали. Для других автомобилей укажите основание ручной проверки.</div>
    </div>${cart(choices)}</div>`;
}

function draftTable(rows) {
  const selected = state.checked;
  const editable = rows.filter(row => !row.order);
  const all = { html: checkbox('', 'all-marked', editable.length && editable.every(row => selected.has(row.id)),
    `aria-label="Выбрать все позиции" ${!editable.length ? 'disabled' : ''}`) };
  return table([all, '№', 'Описание позиции', 'Кол-во', 'Срочно', 'Оригинал', 'Статус подбора / закупки', ''],
    rows.map((row, index) => `<tr class="${state.active === row.id ? 'selected' : ''}">${cells([
      checkbox('', 'marked', selected.has(row.id), `value="${row.id}" aria-label="Отметить позицию ${index + 1}" ${row.order ? 'disabled' : ''}`),
      index + 1,
      `<button type="button" class="article" data-action="active" data-value="${row.id}"><b>${e(row.description)}</b></button>`,
      `<span class="nowrap">${row.quantity} шт.</span>`,
      checkbox('', 'urgent-flag', row.urgent, `data-item="${row.id}" aria-label="Срочно" ${row.order ? 'disabled' : ''}`),
      checkbox('', 'original-flag', row.original_required, `data-item="${row.id}" aria-label="Только оригинал" ${row.order ? 'disabled' : ''}`),
      lineState(row), row.order ? link('/orders/' + row.order.id, 'Заказ') : iconButton('edit-item', 'Редактировать позицию', 'pencil', row.id),
    ])}</tr>`).join(''), 'compact');
}

function offerFilters() {
  const f = state.filters;
  return `<div class="filters"><b>Поставщики:</b> ${Object.entries(sources).map(([key, name]) =>
    checkbox(name, 'supplier', state.supplierFilters.has(key), `value="${key}"`)).join('')}
    ${state.checked.size > 1 ? button('search-marked', 'Найти по выбранным', { icon: 'search' }) : ''}
    <label class="push"><b>Сортировка:</b> <select name="sort">${options({ price: 'По полной цене', date: 'По сроку получения' }, f.sort)}</select></label>
    ${button('offer-filters', 'Фильтры', { icon: 'filter' })}</div>`;
}

function offerTable(row) {
  const result = row.search_result;
  if (!result) return empty('Запустите поиск, чтобы сравнить условия поставщиков.');
  const f = state.filters;
  const offers = result.offers.filter(o => state.supplierFilters.has(o.supplier)
    && (!f.stock_only || o.stock >= row.quantity) && (!f.originals_only || o.original)
    && (!f.fit_only || o.fit === 'catalogue' || row.manual_basis?.catalogue === o.catalogue)
    && (!f.maxDays || (new Date(o.date_to) - new Date(state.overview.window.today)) / 86400000 <= f.maxDays)
    && (!f.maxPrice || (o.currency === 'RUB' && o.price != null && offerTotal(o, row.quantity) <= 100 * f.maxPrice)));
  const usable = o => !!(o.fit === 'catalogue' || row.manual_basis?.catalogue === o.catalogue)
    && o.price != null && o.stock >= row.quantity && !outdated(o);
  offers.sort((a, b) => Number(usable(b)) - Number(usable(a)) || a.currency.localeCompare(b.currency)
    || (f.sort === 'date' ? a.date_to.localeCompare(b.date_to) : 0)
    || Number(a.price == null || a.delivery == null) - Number(b.price == null || b.delivery == null)
    || (offerTotal(a, row.quantity) ?? Infinity) - (offerTotal(b, row.quantity) ?? Infinity)
    || a.date_to.localeCompare(b.date_to) || a.supplier.localeCompare(b.supplier));
  const comparable = {};
  for (const offer of offers.filter(o => usable(o) && o.delivery != null)) (comparable[offer.currency] ||= []).push(offer);
  const best = new Set(Object.values(comparable).filter(group => group.length > 1).map(group =>
    group.reduce((a,b) => offerTotal(a,row.quantity) <= offerTotal(b,row.quantity) ? a : b).id));
  const first = offers[0];
  return `<section class="stack"><div class="section-head"><h2>Предложения по позиции: ${e(row.description)} (${row.quantity} шт.)</h2>
    <div class="actions">${first ? fitText(row, first) : ''}
    ${result.catalogue ? `<small>OEM: ${e('DEMO-OEM-' + result.catalogue)}</small>` : ''}
    ${!row.order && first && first.fit !== 'catalogue' ? button('basis', 'Ручная проверка', { value: row.id }) : ''}</div></div>
    ${deltaView(row.conditions_delta)}
    ${result.needs_detail ? '<p class="hint warn">Уточните точное наименование или введите известный артикул. Попробуйте «масляный фильтр», «воздушный фильтр» или «передний амортизатор».</p>' : ''}
    ${offers.length ? table(['', 'Поставщик', 'Бренд / артикул', 'Тип', 'Цена за шт.', 'Остаток', 'Получение', 'Доставка', 'Итого', 'Проверка'],
      offers.map(o => `<tr class="${row.selection?.id === o.id ? 'selected' : ''}">${cells([
        `<input type="radio" name="offer-${row.id}" data-item="${row.id}" value="${e(o.id)}" aria-label="Выбрать предложение ${e(o.supplier_name)}" ${row.selection?.id === o.id ? 'checked' : ''}
          ${row.order || !usable(o) ? 'disabled' : ''}>`,
        supplier(o.supplier), `<div>${e(o.brand)}</div>${button('copy', o.article, { className: 'article', value: o.article, title: 'Копировать ' + o.article })}`,
        pillar(o.original ? 'Оригинал' : 'Аналог', o.original ? 'ok' : ''), `<b class="nowrap">${o.price == null ? 'Не указана' : money(o.price,o.currency)}</b>`,
        o.stock < row.quantity ? pillar(o.stock + ' шт. · мало', 'warn') : o.stock + ' шт.',
        `<span class="nowrap">${e(dateRange(o))}</span><details><summary>Пункт выдачи</summary><small>${e(o.pickup)} · ${e(o.name)} · ${e(o.id)} ${o.analog_basis ? '· ' + e(o.analog_basis) : ''}</small></details>`,
        o.delivery == null ? 'Не рассчитана' : money(o.delivery,o.currency),
        `<b class="nowrap">${money(offerTotal(o,row.quantity),o.currency)}</b>${o.delivery == null ? '<br><small>Предварительно</small>' : best.has(o.id) ? '<br><small class="ready">Лучшая цена</small>' : ''}`,
        outdated(o) ? pillar('Устарело', 'warn') : `<span class="ready">${when(o.checked_at,'time')}</span>`,
      ])}</tr>`).join(''), 'offers compact') : empty('Нет предложений по выбранным условиям.')}
    <div class="toolbar">${Object.entries(result.sources).filter(([, code]) => code !== 'OK').map(([key, code]) =>
      pillar(sources[key] + ' · ' + resultLabels[code], code === 'TEMPORARY_ERROR' ? 'warn' : '')).join('')}
      ${!row.order ? button('refresh-offers', 'Повторить поиск', { icon: 'refresh', value: row.id }) : ''}</div></section>`;
}

function cart(rows) {
  const collapsed = state.cartOpen == null ? matchMedia('(max-width: 1200px)').matches : !state.cartOpen;
  return `<details class="cart panel" ${collapsed ? '' : 'open'} id="cart"><summary class="panel-head"><h2>${svg('cart')} Выбранные позиции (${rows.length})</h2></summary>
    <div class="cart-body stack">${rows.length ? rows.map((row, index) => {
      const offer = row.selection;
      return `<article class="panel cart-card"><div class="section-head"><h3>${index + 1}. ${e(row.description)}</h3>
        ${iconButton('unselect', 'Убрать из выборки', 'trash', row.id)}</div><div class="toolbar"><small>${e(offer.brand)} / ${e(offer.article)}</small>
        ${pillar(offer.original ? 'Оригинал' : 'Аналог', offer.original ? 'ok' : '')}</div>
        <p>${supplier(offer.supplier)} · <small>${e(dateRange(offer))}</small></p>
        <p class="amount"><span>${money(offer.price, offer.currency)} ×</span><span class="stepper">
        ${button('minus', '−', { value: row.id, title: 'Уменьшить количество', disabled: row.quantity <= 1 })}<span>${row.quantity}</span>
        ${button('plus', '+', { value: row.id, title: 'Увеличить количество', disabled: row.quantity >= 99 })}</span>
        <b>${money(offer.price == null ? null : offer.price * row.quantity, offer.currency)}</b></p>
        ${outdated(offer) ? '<small class="muted">Требуется перепроверка</small>' :
          row.workspace_lot || row.urgent || row.conditions_delta ? '<div>' + lineState(row) + '</div>' :
            `<small class="ready">${offer.fit === 'catalogue' ? '✓ Применимость подтверждена' : 'Ручная проверка'}</small>`}</article>`;
    }).join('') : '<p class="empty">Выберите предложение в таблице.</p>'}
    ${totalsView(rows)}
    <div class="cart-actions">${button('checkout', 'Подтвердить заказ', { icon: 'check', className: 'primary', disabled: !rows.length })}
    ${button('save-lot', 'Сохранить в лот', { icon: 'calendar', disabled: !rows.some(r => !r.urgent) })}
    ${button('make-urgent', 'Оформить срочно', { icon: 'bolt', disabled: !rows.length })}</div></div></details>`;
}

function deltaView(delta) {
  if (!delta || !Object.keys(delta).length) return '';
  const names = { price:'Цена', currency:'Валюта', stock:'Остаток', delivery:'Доставка',
    date_from:'Дата от', date_to:'Дата до', pickup:'Пункт выдачи', channel:'Канал' };
  return `<div class="hint warn"><b>Условия изменились</b> · Проверьте значения и подтвердите заново.
    ${table(['Условие', 'Было', 'Стало'], Object.entries(delta).map(([key, value]) => {
      const print = (v, side) => v == null ? 'Не указано' : ['price','delivery'].includes(key) ?
        money(v, delta.currency?.[side] || 'RUB') : e(v);
      return '<tr>' + cells([names[key] || e(key), print(value.before, 'before'), print(value.after, 'after')]) + '</tr>';
    }).join(''))}</div>`;
}

function garagePage() {
  const { vehicles, car } = state.data;
  const query = new URLSearchParams(location.search);
  const list = table(['VIN', 'Госномер', 'Марка', 'Модель', 'Год', 'Двигатель', 'Кузов', 'Заявки'],
    vehicles.map(v => '<tr>' + cells([
      link('/garage/' + v.vin + location.search, v.vin), e(valued(v, 'plate')), e(v.make), e([v.model, v.generation].filter(Boolean).join(' ')),
      e(valued(v, 'year')), e(valued(v, 'engine')), e(valued(v, 'body')), v.request_count,
    ]) + '</tr>').join(''));
  return `<div class="stack"><div class="panel pad section-head"><form id="garage-filter" class="form-bar">
    ${input('Автомобиль', 'q', query.get('q'), 'placeholder="VIN, госномер, марка или модель"')}
    ${select('Показать', 'archived', { false: 'Активные', true: 'Архив' }, query.get('archived') || 'false')}
    <button>${svg('search')} Найти</button></form>${button('add-car', 'Добавить автомобиль', { icon: 'plus', className: 'primary' })}</div>
    ${vehicles.length ? list : empty('Автомобили не найдены. Измените поиск или добавьте автомобиль.')}
    ${car ? `<div class="side-layout"><div class="stack">${vehicleCard(car)}
      <section class="panel pad stack"><h2>Связанные заявки</h2>
      ${car.requests.length ? `<ul class="mini-list">${car.requests.map(r => `<li>${r.workspace ? link('/requests/' + r.id, 'Заявка № ' + r.id) :
          state.overview.shared ? 'Прежняя заявка № ' + r.id : link('/archive', 'Прежняя заявка № ' + r.id)} · ${when(r.created_at)}</li>`).join('')}</ul>` : '<p class="muted">Заявок пока нет.</p>'}
      <p><a href="/orders?q=${encodeURIComponent(car.vin)}">Заказы по автомобилю</a></p></section></div>
      <aside class="panel pad stack"><h2>Карточка автомобиля</h2><p>Добавлен · ${when(car.created_at)}</p><p>Обновлён · ${when(car.updated_at)}</p>
        <div class="actions">${car.archived ? '' : button('new-car-draft', 'Создать заявку', { icon: 'plus', className: 'primary' })}
        ${button('archive-car', car.archived ? 'Восстановить' : 'В архив', { icon: 'doc' })}</div>
        ${car.events.length ? eventList(car.events) : ''}</aside></div>` : ''}</div>`;
}

function itemRows(rows, context) {
  return table(['Заявка / автомобиль', 'Позиция / артикул', 'Кол-во', 'Поставщик', 'Цена', 'Доставка',
    'Итого', 'Срок', 'Проверка / статус', 'Действия'], rows.map(row => {
    const o = row.selection;
    return '<tr>' + cells([
      link('/requests/' + row.request_id, '№ ' + row.request_id) + ` <small>${e(row.vin || 'Без VIN')}</small>`,
      `<b>${e(row.description)}</b><br><small>${e(o?.article || '—')}</small>`, row.quantity,
      o ? supplier(o.supplier) : '—', o ? money(o.price, o.currency) : '—',
      o?.delivery == null ? '—' : money(o.delivery,o.currency),
      o ? money(offerTotal(o,row.quantity),o.currency) + (o.delivery == null ? '<br><small>Предварительно</small>' : '') : '—',
      o ? e(dateRange(o)) : '—', lineState(row) + (o ? `<br><small>${outdated(o) ? 'Устарело' : when(o.checked_at,'time')}</small>` : ''),
      row.order ? link('/orders/' + row.order.id, 'Заказ') : `<div class="actions">
        ${context === 'urgent' && o && staffCanBuy() ? button('review-urgent', 'Оформить', { value: row.id }) : ''}
        ${button('placement-menu', 'Действия', { value: row.id })}</div>`,
    ]) + '</tr>';
  }).join(''), 'compact offers');
}

function lotPage() {
  const data = state.data;
  const all = Object.values(data.groups).flat();
  const groups = Object.entries(data.groups);
  const filter = new URLSearchParams(location.search).get('q')?.toLowerCase() || '';
  const tab = state.lotTab || 'groups';
  const filtered = all.filter(r => [r.description,r.vin,r.request_id,r.selection?.supplier_name,r.selection?.date_to,
    labels[r.order?.status]].join(' ').toLowerCase().includes(filter));
  return `<div class="stack"><div class="panel pad section-head"><div class="stack">
    <h2>Лот от ${when(data.day,'day')} ${badge(data.status)}</h2>
    <p class="muted">Подготовка в ${when(data.cutoff,'time')} ЕКБ · ${groups.length} групп · ${all.length} позиций ·
      ${data.orders.length} заказов · ${link('/urgent', 'Срочные вне лота: ' + state.overview.counts.urgent)}</p></div>
    <form id="lot-date" class="form-bar">${input('Дата лота','day',data.day,'type="date" required')}
      ${data.dates.length ? select('История','history',{'':'Выбрать…', ...Object.fromEntries(data.dates.map(d => [d,when(d,'day')]))},'') : ''}
      <button class="quiet">${svg('refresh')} Открыть</button></form></div>
    <div class="side-layout lot-layout"><div class="stack"><div class="tabs">${Object.entries({groups:'Позиции по группам',all:'Все позиции',results:'Результаты отправки'}).map(([key,label]) =>
      button('lot-tab',label,{value:key,className:key === tab ? 'active' : 'quiet'})).join('')}</div>
    <div class="stack">${tab === 'results' ? (data.orders.length ? orderTable(data.orders) : empty('Отправок по этому лоту пока нет.')) :
      tab === 'all' ? `<form id="lot-filter" class="form-bar">${input('Позиция, заявка, VIN, поставщик или статус','q',filter)}
        <button>Фильтровать</button></form>${filtered.length ? itemRows(filtered,'lot') : empty('Позиции не найдены.')}` :
      !groups.length ? empty('В этот лот ещё не добавлены позиции.') : groups.map(([key,rows]) =>
        `<details class="panel" open><summary class="panel-head section-head"><strong>${e(dateRange(rows[0].selection))}</strong>
          <span>${rows.length} поз. · ${summarySum(rows)}</span></summary><div class="pad stack">
          ${rows.map(row => deltaView(row.conditions_delta)).join('')}${itemRows(rows,'lot')}
          ${rows.some(r => !r.order) && staffCanBuy() ? button('review-lot', 'Подтвердить группу',
            { value:key, icon:'check', className:'primary', disabled:!data.lot?.closed_at }) : ''}
        </div></details>`).join('')}</div></div>
    <aside class="panel pad stack"><h2>Сводка лота</h2>${totalsView(all)}
    <small>Рабочие дни в демо · понедельник — пятница. Срочные позиции оформляются отдельно.</small>
    ${data.lot && !data.lot.closed_at ? '<p class="hint">Подтверждение групп откроется после времени подготовки.</p>' : ''}</aside></div></div>`;
}

function urgentPage() {
  const raw = state.data;
  const tab = state.urgentTab || 'ready';
  const q = new URLSearchParams(location.search);
  const query = (q.get('q') || '').toLowerCase();
  const rows = raw.filter(r => (tab === 'ready' ? !r.order : tab === 'done' ?
    ['accepted','manual_confirmed','cancelled'].includes(r.order?.status) : r.order && !['accepted','manual_confirmed','cancelled'].includes(r.order.status))
    && [r.description,r.vin,r.request_id,r.selection?.supplier_name,labels[r.order?.status]].join(' ').toLowerCase().includes(query)
    && (!q.get('day') || when(r.created_at, 'stamp') && new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Yekaterinburg' }).format(new Date(r.created_at)) === q.get('day')));
  return `<div class="stack"><section class="panel pad stack"><div class="section-head"><div><h2>Срочные позиции</h2><p class="muted">Оформляются вне дневного лота после подтверждения сотрудником.</p></div>
    <div class="actions">${pillar('Ожидают: ' + raw.filter(r => !r.order).length)} ${pillar('Требуют действий: ' + raw.filter(r => ['manual','unknown','error','sending'].includes(r.order?.status)).length,'warn')}</div></div>
    <form id="urgent-filter" class="form-bar">${input('Позиция, VIN, заявка, поставщик или статус','q',query)}
      ${input('Дата','day',q.get('day'),'type="date"')}<button>Фильтровать</button></form></section>
    <div class="tabs">${Object.entries({ready:'К оформлению',active:'В процессе / требуют действий',done:'Завершённые'}).map(([key,label]) =>
      button('urgent-tab',label,{value:key,className:key === tab ? 'active' : 'quiet'})).join('')}</div>
    ${rows.length ? rows.map(row => deltaView(row.conditions_delta)).join('') + itemRows(rows,'urgent') : empty('В этой группе нет срочных позиций.')}</div>`;
}

function orderTable(rows) {
  return table(['Дата', 'Заказ', 'Номер поставщика', 'Поставщик', 'Вид', 'Автомобиль', 'Позиции', 'Сумма', 'Сотрудник', 'Статус'],
    rows.map(row => '<tr>' + cells([
      when(row.created_at), link('/orders/' + row.id, row.id.slice(0,8).toUpperCase()),
      e(row.supplier_ref || 'Не получен'), supplier(row.supplier), row.kind === 'lot' ? 'Дневной' : 'Срочный',
      e([...new Set((row.items || []).map(i => i.vehicle.vin))].join(', ') || '—'),
      row.items?.length ?? '—', summarySum(row.items || []), e(row.author), badge(row.status),
    ]) + '</tr>').join(''), 'offers');
}

function orderList() {
  const query = new URLSearchParams(location.search);
  const page = state.data.page;
  const pageLink = number => { const params = new URLSearchParams(query); params.set('page',number); return '/orders?' + params; };
  return `<div class="stack"><form id="order-filter" class="panel pad form-bar">
    ${input('VIN, госномер, артикул или номер','q',query.get('q'))}
    ${input('От','start',query.get('start'),'type="date"')}${input('До','end',query.get('end'),'type="date"')}
    ${select('Поставщик','supplier',{'':'Все', ...sources},query.get('supplier'))}
    ${select('Вид','kind',{'':'Все',lot:'Дневной',urgent:'Срочный'},query.get('kind'))}
    ${select('Статус','status',{'':'Все',...Object.fromEntries(['accepted','manual','manual_confirmed','unknown','error','sending','cancelled'].map(key => [key,labels[key]]))},query.get('status'))}
    <button class="primary">${svg('search')} Найти</button><a class="button quiet" href="/orders">Сбросить</a></form>
    ${state.data.orders.length ? orderTable(state.data.orders) : empty('Подходящих заказов пока нет.')}
    <div class="toolbar">${page > 1 ? link(pageLink(page-1),'← Предыдущая') : ''}<small>Всего: ${state.data.total}</small>
    ${page * 25 < state.data.total ? link(pageLink(page+1),'Следующая →') : ''}
    ${state.overview.shared ? '' : '<a class="button quiet" href="/archive">Архив прежних заявок</a>'}</div></div>`;
}

function eventList(rows, withLinks = false) {
  const targets = { request: 'requests', order: 'orders', lot: 'lots', vehicle: 'garage' };
  if (!rows.length) return '<p class="muted">Записей пока нет.</p>';
  return `<ul class="mini-list">${rows.map(row => `<li><b>${e(row.action)}</b> <small>${when(row.at)} · ${e(row.actor)}</small>
    ${withLinks && targets[row.entity] ? ' · ' + link('/' + targets[row.entity] + '/' + encodeURIComponent(row.entity_id),'Открыть') : ''}
    ${row.detail && !withLinks ? `<br><small>${e(row.detail)}</small>` : ''}</li>`).join('')}</ul>`;
}

function orderDetail() {
  const row = state.data;
  const grades = table(['Заявка', 'Автомобиль', 'Деталь / OEM', 'Количество', 'Цена', 'Доставка', 'Итого', 'Получение / применимость'],
    row.items.map(line => '<tr>' + cells([
      link('/requests/' + line.request_id, '№ ' + line.request_id), e([line.vehicle.make,line.vehicle.model,line.vehicle.vin].join(' ')),
      `<b>${e(line.description)}</b><br><small>${e(line.offer.brand)} · ${e(line.offer.article)} · ${e(line.offer.oem)}</small>`,
      line.quantity, money(line.offer.price,line.offer.currency), money(line.offer.delivery,line.offer.currency),
      money(offerTotal(line.offer,line.quantity),line.offer.currency),
      `${e(dateRange(line.offer))}<br><small>${e(line.offer.pickup)} · ${e(line.basis)}</small>`,
    ]) + '</tr>').join(''), 'offers');
  return `<div class="stack"><section class="panel pad stack"><div class="section-head">
    <h2>Учебный заказ ${e(row.id.slice(0,8).toUpperCase())} ${badge(row.status)}</h2>
    <a class="button quiet" href="${e(state.orderListPath || '/orders')}">К истории</a></div>
    <p>${supplier(row.supplier)} · ${row.channel === 'manual' ? 'Учебный кабинет' : 'Демо-адаптер'} ·
      ${e(row.supplier_ref || 'Номер поставщика не получен')}</p><small>${when(row.created_at)} · ${e(row.author)} ·
      ${row.lot_day ? link('/lots/' + row.lot_day, 'Лот ' + row.lot_day) : 'Срочный заказ'}</small>
    <div class="actions">${button('copy-order', 'Копировать в новую заявку', { icon: 'copy' })}
      ${row.status === 'manual' && staffCanBuy() ? button('manual', 'Открыть учебный кабинет', { className: 'primary' }) : ''}
      ${row.status === 'unknown' && staffCanBuy() ? button('reconcile', 'Сверить результат', { className: 'primary' }) : ''}
      ${row.status === 'error' && staffCanBuy() ? button('retry-order', 'Повторить обработку', { className: 'primary' }) : ''}
      ${['manual','error'].includes(row.status) && staffCanBuy() ? button('cancel-order', 'Отменить оформление') : ''}</div>
    ${row.status === 'unknown' ? '<p class="hint warn">Дождитесь результата сверки. Повторная отправка заблокирована.</p>' : ''}
    ${row.status === 'error' ? '<p class="hint warn">Отклонение зарегистрировано. Повтор доступен после перепроверки исхода и прежних условий.</p>' : ''}</section>
    ${grades}<div class="side-layout"><section class="panel pad stack"><h2>Хронология</h2>${eventList(row.journal)}</section>
      <aside class="panel pad stack"><h2>Согласованный расчёт</h2>${totalsView(row.items)}</aside></div></div>`;
}

function suppliersPage() {
  return `<div class="stack"><div class="panel pad stack"><h2>Подключения поставщиков</h2>
    <p class="muted">Учебные источники · Екатеринбург. Возможности реальных API и доступы поставщиков проверяются отдельно.</p></div>
    <div class="cards">${state.data.map(row => `<section class="panel pad stack">
      <div class="section-head"><h2>${supplier(row.name)}</h2>${pillar(row.enabled ? 'В поиске' : 'Отключён',row.enabled ? 'ok' : '')}</div>
      <p>Канал · ${row.capabilities.manual ? 'Учебный кабинет' : 'Демо-адаптер'}</p>
      <div>${pillar(resultLabels[row.last_status] || 'Не проверен', row.last_status === 'TEMPORARY_ERROR' ? 'warn' : '')}</div>
      <small>Последняя проверка · ${when(row.checked_at)}<br>Последнее успешное чтение · ${when(row.last_success)}</small>
      <div class="actions">${isAdmin() ? button('supplier-settings','Настроить',{value:row.name,icon:'gear'}) +
       button('supplier-check','Проверить',{value:row.name,icon:'refresh'}) : ''}</div>
      <details><summary>Возможности и журнал</summary><p class="muted">Цены, остаток, сроки, доставка; ${row.capabilities.reconcile ? 'демо-сверка' : 'ручная регистрация'}. Секреты для демо не требуются.</p>
       ${eventList(row.journal)}</details></section>`).join('')}</div></div>`;
}

function settingsPage() {
  const s = state.overview.settings;
  return `<div class="cards"><section class="panel pad stack"><h2>Общие</h2><p>AUTOSERVICE · Демо-режим</p>
    <p>Часы и расчёт лота · Asia/Yekaterinburg</p><p>Планирование · пн–пт</p></section>
    <section class="panel pad stack"><h2>Дневной лот</h2><p>Подготовка · ${e(s.cutoff)} ЕКБ</p>
    <small>Уже созданные лоты сохраняют назначенное время подготовки. Настройка применяется к новым лотам.</small>
    <div>${isAdmin() ? button('lot-settings','Изменить расписание') : ''}</div></section>
    <section class="panel pad stack"><h2>Поиск</h2><p>Предложения действуют ${s.ttl} мин.</p>
    <small>Перед каждым оформлением сервер заново проверяет условия.</small>
    <div>${button('search-settings','Настроить фильтры и сортировку')}</div></section>
    <section class="panel pad stack"><h2>Пользователи и доступ</h2><p>${e(state.overview.user.name)}</p>
    <small>${state.overview.shared ? 'Доступ настроен администратором развёртывания.' : 'Локальный сеанс · тестовый администратор.'}</small>
    <div>${state.overview.shared ? button('logout','Выйти') : ''}</div></section>
    <section class="panel pad stack"><h2>Обслуживание</h2><p>SQLite · схема рабочего пространства ${s.schema}</p>
    <div>${button('help','Резервирование и справка')}</div></section></div>`;
}

function renderLogin() {
  document.body.innerHTML = `<main class="login-shell"><form class="panel stack" id="login-form">
    <h1>AUTOSERVICE</h1><p>Вход в рабочее пространство</p>${input('Имя','name','','required autocomplete="username"')}
    ${input('Пароль','password','','type="password" required autocomplete="current-password"')}
    <button class="primary">Войти</button><p role="alert" id="login-error"></p></form></main>`;
  $('#login-form').onsubmit = async event => {
    event.preventDefault();
    try {
      await api('/login','POST',Object.fromEntries(new FormData(event.target)));
      location.assign('/requests');
    } catch (err) { $('#login-error').textContent = err.message; }
  };
}

async function ensureDraft() {
  if (state.draft) return state.draft;
  state.draft = await api('/requests','POST',{});
  history.replaceState({},'', '/requests/' + state.draft.id);
  return state.draft;
}

function itemPayload(row, changes = {}) {
  return { description: row.description, quantity: row.quantity, urgent: !!row.urgent,
    original_required: !!row.original_required, article: row.article, ...(row.revision ? { revision: row.revision } : {}), ...changes };
}

function itemFields(row = {}) {
  return `<div class="field-grid">${input('Описание детали','description',row.description,'required maxlength="300"')}
    ${input('Кол-во, шт.','quantity',row.quantity || 1,'type="number" min="1" max="99" required')}
    ${input('Точный артикул (если известен)','article',row.article,'maxlength="80"')}</div>
    <div class="toolbar">${checkbox('Срочно','urgent',row.urgent)} ${checkbox('Только оригинал','original_required',row.original_required)}</div>`;
}

function editItem(row) {
  dialog(row ? 'Редактировать позицию' : 'Добавить позицию', itemFields(row) +
    (row ? button('cancel-item', 'Отменить позицию', { value: row.id, icon: 'trash', disabled: !!row.workspace_lot }) : ''),
  'Сохранить позицию', async data => {
    const draft = await ensureDraft();
    const payload = { description: data.get('description'), quantity: Number(data.get('quantity')),
      article: data.get('article').trim() || null, urgent: data.has('urgent'), original_required: data.has('original_required') };
    const saved = await api(row ? '/items/' + row.id : '/requests/' + draft.id + '/items',row ? 'PATCH' : 'POST',
      row ? { ...payload, revision: row.revision } : payload);
    state.active = saved.id;
    closeModal();
    await load({quiet:true});
  });
}

function carForm(car, onSaved) {
  const fields = [
    ['VIN','vin','required maxlength="17"'], ['Госномер','plate','maxlength="20"'],
    ['Марка','make','required maxlength="80"'], ['Модель','model','required maxlength="100"'],
    ['Поколение (код)','generation','maxlength="32"'], ['Год','year','inputmode="numeric" maxlength="4"'],
    ['Кузов','body','maxlength="100"'], ['Двигатель','engine','maxlength="100"'],
  ];
  const controls = fields.map(([title, key, attrs]) => {
    if (['vin', 'plate'].includes(key)) {
      return input(title, key, car?.[key], attrs + (car && key === 'vin' ? ' readonly' : ''));
    }
    const list = 'catalog-' + key;
    return `<div class="catalog-field">${input(title,key,car?.[key],attrs +
      ` role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="${list}" autocomplete="off"`)}
      <div class="catalog-options" id="${list}" role="listbox" aria-label="${title}" hidden></div></div>`;
  });
  const form = dialog(car ? 'Редактировать автомобиль' : 'Добавить автомобиль',
    `<div class="field-grid">${controls.join('')}</div>
     <p class="muted">Варианты «По модели» и «По поколению» уточняйте для конкретного автомобиля.</p>
     ${car ? '<p class="hint">Изменение автомобиля сбрасывает текущий подбор. Заказы сохраняют свой снимок.</p>' : ''}`,
    'Сохранить автомобиль', async form => {
      const body = Object.fromEntries(form);
      if (car) body.revision = car.revision;
      const saved = await api('/vehicles','POST',body);
      closeModal();
      if (saved.warning) notify(saved.warning);
      await onSaved(saved.vehicle);
    });
  connectVehicleCatalog(form, () => api('/vehicle-catalog'));
}

async function pickCar() {
  const cars = await api('/vehicles');
  dialog('Выбрать автомобиль', `<label class="field">VIN, госномер или модель<input id="car-query" placeholder="Поиск в гараже"></label>
    <label class="field">Автомобиль<select id="car-options" name="vin" required></select></label>
    ${button('create-for-request','Добавить автомобиль',{icon:'plus'})}
    ${state.draft?.items.some(i => i.selection) ? '<p class="hint warn">Выбранные предложения будут сброшены. Позиции в лоте вернутся в заявку.</p>' : ''}`,
    'Выбрать автомобиль', async form => {
      if (!form.get('vin')) throw new Error('Добавьте автомобиль или выберите его из списка');
      await attachCar(form.get('vin'));
      closeModal();
      await load({quiet:true});
    });
  const update = () => {
    const query = $('#car-query').value.toLowerCase();
    const rows = cars.filter(c => [c.vin,c.plate,c.make,c.model,c.generation].join(' ').toLowerCase().includes(query));
    $('#car-options').innerHTML = '<option value="">Выберите автомобиль</option>' + rows.map(c =>
      `<option value="${e(c.vin)}">${e([c.make,[c.model,c.generation].filter(Boolean).join(' '),c.plate,c.vin].filter(Boolean).join(' · '))}</option>`).join('');
  };
  $('#car-query').addEventListener('input', update);
  update();
}

async function attachCar(vin) {
  const draft = await ensureDraft();
  await api('/requests/' + draft.id,'PATCH',{ vin, revision:draft.revision,
    accept_reset:draft.items.some(row => row.selection || row.workspace_lot) });
}

function parseDialog() {
  dialog('Разобрать заявку', `<label class="field">Исходный текст<textarea name="text" rows="5" maxlength="10000" required
    placeholder="Масляный фильтр 2 шт.&#10;Передний амортизатор срочно"></textarea></label>
    ${button('voice','Говорить',{icon:'doc'})}<p class="muted">Сначала проверьте список. Исходный текст сохранится после применения.</p>`,
  'Показать разбор', async form => {
    const text = form.get('text');
    const parsed = await api('/parse','POST',{ text });
    if (!parsed.items.length) throw new Error(parsed.question);
    closeModal();
    dialog('Проверьте позиции', `${parsed.question ? `<p class="hint warn">${e(parsed.question)}</p>` : ''}
      ${parsed.items.map((row,i) => `<fieldset class="stack"><legend>Позиция ${i+1}</legend>
      ${itemFields(row).replaceAll('name="',`name="${i}-`)}</fieldset>`).join('')}`, 'Добавить позиции в заявку', async edits => {
      const draft = await ensureDraft();
      const items = parsed.items.map((_,i) => ({ description:edits.get(i+'-description'), quantity:Number(edits.get(i+'-quantity')),
        article:edits.get(i+'-article').trim() || null, urgent:edits.has(i+'-urgent'), original_required:edits.has(i+'-original_required') }));
      await api('/requests/' + draft.id + '/apply-text','POST',{ text, items, revision:draft.revision });
      closeModal();
      await load({quiet:true});
    });
  });
}

async function searchItems(rows, query) {
  if (!state.supplierFilters.size) throw new Error('Выберите хотя бы одного поставщика');
  const failures = [];
  for (const row of rows) {
    try { await api('/items/' + row.id + '/search','POST',{ revision:row.revision, query:query || '', suppliers:[...state.supplierFilters] }); }
    catch (err) { failures.push(err.message); }
  }
  await load({quiet:true});
  if (failures.length) notify([...new Set(failures)].join(' · '),true);
}

function selectedLines() { return state.draft.items.filter(row => row.selection && !row.order); }
const refs = rows => rows.map(({id,revision}) => ({id,revision}));
function lotPicker(rows) {
  const window = state.overview.window;
  const dates = Object.fromEntries([window.open,window.next].filter(Boolean).map(d => [d,when(d,'day')]));
  dialog('Сохранить в дневной лот', `<p>${rows.length} поз. · ${summarySum(rows)}</p>
    ${!window.open ? '<p class="hint warn">Сегодняшний лот закрыт. Подтвердите перенос на следующую рабочую дату.</p>' : ''}
    ${select('Дата лота','day',dates,window.open || window.next)}`,
    window.open ? 'Сохранить в лот' : 'Подтвердить перенос', async data => {
      await api('/placement','POST',{ items:refs(rows), action:'lot', day:data.get('day') });
      closeModal();
      notify('Позиции сохранены в лот');
      await load({quiet:true});
    });
}

function makeUrgent(rows) {
  dialog('Перевести в срочные', `<p>Срочные позиции оформляются отдельно. Позиции в дневном лоте будут из него сняты.</p>
    <ul class="mini-list">${rows.map(r => `<li>${e(r.description)} · ${e(dateRange(r.selection))}</li>`).join('')}</ul>`,
  'Перевести и открыть срочные', async () => {
    await api('/placement','POST',{ items:refs(rows), action:'urgent' });
    closeModal();
    await go('/urgent');
  });
}

async function checkoutReview(args, orderId) {
  const review = orderId ? await api('/orders/' + orderId + '/retry-review','POST') : await api('/review','POST',args);
  const grouped = {};
  for (const row of review.rows) (grouped[row.offer.supplier] ||= []).push(row);
  const tentative = review.rows.some(row => row.offer.delivery == null);
  dialog(orderId ? 'Подтвердить повтор обработки' : args.kind === 'lot' ? 'Подтвердить группу лота' : 'Подтвердить срочную закупку',
    `<p>Учебное оформление. Перед отправкой сервер перепроверит цену, остаток и срок.</p>
      ${Object.entries(grouped).map(([key,rows]) => `<div class="panel pad stack"><h3>${supplier(key)}</h3>
        <ul class="mini-list">${rows.map(row => `<li><b>${e(row.description)} · ${row.quantity} шт.</b><br>
        ${e(row.vehicle.make)} ${e(row.vehicle.model)} · ${e(row.vehicle.vin)} · ${e(row.offer.article)}<br>
        ${e(dateRange(row.offer))} · ${e(row.offer.pickup)} · ${e(row.basis)}<br>
        Цена ${money(row.offer.price,row.offer.currency)} · доставка ${money(row.offer.delivery,row.offer.currency)} ·
        ${row.offer.channel === 'manual' ? 'Учебный кабинет' : 'Демо-адаптер'}</li>`).join('')}</ul>${totalsView(rows)}</div>`).join('')}
      ${tentative ? checkbox('Согласен на предварительную стоимость доставки','tentative',false,'required') : ''}`,
    'Подтвердить учебное оформление', async data => {
      let result;
      try { result = await api('/review/' + review.id + '/confirm','POST',{ allow_unknown_delivery:data.has('tentative') }); }
      catch (err) { throw new Error(err.message + '. Если ответ потерялся, проверьте историю заказов.'); }
      closeModal();
      if (result.issues.length) {
        await load({quiet:true});
        dialog('Требуется повторное подтверждение',
          (result.requires_new_request ? '<p>Для изменившихся условий скопируйте заказ в новую заявку и заново подберите предложение.</p>' : '') +
          result.issues.map(issue => issue.changes ?
          deltaView(issue.changes) : `<p class="hint warn">Позиция № ${issue.id}: ${e(resultLabels[issue.status])}. Повторите проверку.</p>`).join(''));
      } else if (result.orders.length === 1) {
        await go('/orders/' + result.orders[0].id);
      } else {
        state.lotTab = 'results';
        await load({quiet:true});
      }
    });
}

function locateItem(id) {
  const rows = route().path === 'urgent' ? state.data : route().path === 'lots' ?
    Object.values(state.data.groups).flat() : state.draft.items;
  return rows.find(row => row.id === Number(id));
}

function confirmation(title, text, label, action) {
  dialog(title, `<p>${e(text)}</p>`, label, async () => {
    await action();
    closeModal();
    await load({quiet:true});
  });
}

function browserSpeech(control) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    throw new Error('Браузер не поддерживает диктовку. Введите текст вручную.');
  }
  const recognition = new Recognition();
  recognition.lang = 'ru-RU';
  recognition.onresult = event => {
    const field = modal.querySelector('textarea[name=text]');
    if (field) field.value = [field.value,event.results[0][0].transcript].filter(Boolean).join('\n');
  };
  recognition.onerror = () => notify('Не удалось распознать речь. Проверьте доступ к микрофону.',true);
  recognition.onend = () => { control.disabled = false; };
  recognition.start();
}

const actions = {
  reload: () => load(),
  help: () => dialog('Справка AUTOSERVICE', `<ol class="mini-list"><li>Выберите автомобиль, создайте заявку и добавьте детали.</li>
    <li>Сравните предложения и сохраните обычные позиции в дневной лот. Срочные оформляются отдельно.</li>
    <li>После времени подготовки откройте лот и подтвердите группу. Итог проверьте в истории заказов.</li></ol>
    <p>Суммы учебные. При неизвестном результате сначала выполняется сверка. Оплата производится вне программы.</p>
    <p>Резервирование и восстановление описаны в README проекта. Схема рабочего пространства: ${state.overview?.settings.schema || '—'}.</p>
    ${state.overview?.shared ? '' : '<a href="/classic">Открыть прежний голосовой интерфейс</a>'}`),
  notifications: () => dialog('Уведомления', eventList(state.overview?.events || [],true),
    'Отметить прочитанными', async () => {
      await api('/notifications/read','POST'); closeModal(); await load({quiet:true});
    }),
  logout: async () => { await api('/logout','POST'); location.assign('/login'); },
  new: async () => { const draft = await api('/requests','POST',{}); await go('/requests/' + draft.id); },
  example: async () => { const draft = await api('/example','POST'); await go('/requests/' + draft.id); },
  'draft-menu': () => dialog('Заявка № ' + state.draft.id, `<p>Сохранённые изменения доступны после обновления страницы.</p>
    ${state.draft.raw_text ? `<details><summary>Исходный текст</summary><p>${e(state.draft.raw_text)}</p></details>` : ''}
    <div class="actions">${button('copy-draft','Копировать в новую',{icon:'copy'})}${button('cancel-draft','Отменить черновик',{icon:'trash',
      disabled:!writableDraft() || state.draft.items.some(i => i.order || i.workspace_lot)})}</div>`),
  'copy-draft': async () => {
    const draft = await api('/requests/' + state.draft.id + '/copy','POST');
    closeModal(); await go('/requests/' + draft.id);
  },
  'cancel-draft': () => confirmation('Отменить черновик', 'Заявка останется в истории как отменённая.', 'Отменить заявку',
    () => api('/requests/' + state.draft.id + '/cancel','POST',{ revision:state.draft.revision })),
  'add-item': () => editItem(),
  'edit-item': id => editItem(locateItem(id)),
  'cancel-item': id => confirmation('Отменить позицию', 'Позиция будет снята с подбора и останется в журнале.', 'Отменить позицию',
    () => api('/items/' + id + '/cancel','POST',{ revision:locateItem(id).revision })),
  parse: parseDialog,
  voice: (_, control) => { browserSpeech(control); return 'keep-disabled'; },
  'clear-search': () => { const field = $('#search-form input'); field.value = ''; field.focus(); },
  active: id => { state.active = Number(id); render(); },
  'search-marked': () => searchItems(state.draft.items.filter(i => state.checked.has(i.id) && !i.order)),
  'refresh-offers': id => {
    const row = locateItem(id);
    return searchItems([row],row.search_result.query);
  },
  'offer-filters': () => {
    const f = state.filters;
    dialog('Фильтры предложений', `<div class="stack">${checkbox('В достаточном количестве','stock_only',f.stock_only)}
      ${checkbox('Только оригинал','originals_only',f.originals_only)}${checkbox('Только проверенная применимость','fit_only',f.fit_only)}
      ${input('Максимальный срок, дней','maxDays',f.maxDays,'type="number" min="1"')}${input('Максимальная полная цена, ₽','maxPrice',f.maxPrice,'type="number" min="1"')}</div>`,
    'Применить фильтры', data => {
      state.filters = { ...f, stock_only:data.has('stock_only'), originals_only:data.has('originals_only'), fit_only:data.has('fit_only'),
        maxDays:Number(data.get('maxDays')), maxPrice:Number(data.get('maxPrice')) };
      closeModal(); render();
    });
  },
  basis: id => {
    const row = locateItem(id);
    dialog('Ручная проверка применимости', `<p>Сопоставьте ${e('DEMO-OEM-' + row.search_result.catalogue)} с автомобилем
      ${e(row.vin)}. Укажите источник проверки и её результат.</p>
      <label class="field">Основание<textarea name="comment" rows="3" minlength="10" maxlength="500" required></textarea></label>`,
    'Сохранить основание', async data => {
      await api('/items/' + id + '/basis','POST',{ revision:row.revision, comment:data.get('comment') });
      closeModal(); await load({quiet:true});
    });
  },
  unselect: async id => {
    const row = locateItem(id);
    await api('/items/' + id + '/choice','POST',{revision:row.revision,offer:null});
    await load({quiet:true});
  },
  minus: id => quantity(id,-1),
  plus: id => quantity(id,1),
  'save-lot': () => lotPicker(selectedLines().filter(r => !r.urgent)),
  'make-urgent': () => makeUrgent(selectedLines()),
  checkout: () => {
    const rows = selectedLines();
    const urgent = rows.filter(r => r.urgent);
    const regular = rows.filter(r => !r.urgent);
    dialog('Обзор выбранных позиций', `${totalsView(rows)}
      <p>Дневной лот · ${regular.length} поз. Срочно · ${urgent.length} поз.</p>
      <div class="actions">${regular.length ? button('save-lot','Сохранить обычные в лот',{icon:'calendar'}) : ''}
      ${urgent.length ? button('open-urgent','К срочному оформлению',{icon:'bolt'}) : ''}</div>`);
  },
  'open-urgent': async () => { closeModal(); state.urgentTab='ready'; await go('/urgent'); },
  'switch-car': pickCar,
  'add-car': () => carForm(null, car => go('/garage/' + car.vin)),
  'create-for-request': () => carForm(null, async car => { await attachCar(car.vin); await load({quiet:true}); }),
  'edit-car': () => carForm(route().path === 'garage' ? state.data.car : state.draft.vehicle, () => load({quiet:true})),
  'new-car-draft': async () => { const draft = await api('/requests','POST',{vin:state.data.car.vin}); await go('/requests/' + draft.id); },
  'archive-car': () => {
    const car = state.data.car;
    confirmation(car.archived ? 'Восстановить автомобиль' : 'Архивировать автомобиль',
      car.archived ? 'Автомобиль появится в списке активных.' : 'Автомобиль будет скрыт из новых заявок. История сохранится.',
      car.archived ? 'Восстановить' : 'В архив',
      () => api('/vehicles/' + car.vin + '/archive?archived=' + !car.archived,'POST',{revision:car.revision}));
  },
  'lot-tab': tab => { state.lotTab = tab; render(); },
  'urgent-tab': tab => { state.urgentTab = tab; render(); },
  'review-lot': group => checkoutReview({kind:'lot',day:state.data.day,group}),
  'review-urgent': id => checkoutReview({kind:'urgent',ids:[Number(id)]}),
  'placement-menu': id => {
    const row = locateItem(id);
    dialog(row.description, `<p>${e(row.vin || 'Автомобиль не выбран')} · ${row.quantity} шт. · ${e(dateRange(row.selection))}</p>
      ${row.selection ? `<p>${fitText(row,row.selection)} · ${e(row.manual_basis?.comment || row.selection.basis)} · ${summarySum([row])}</p>` : ''}
      <div class="actions">${link('/requests/' + row.request_id,'К заявке и предложениям')}
        ${row.selection ? button('row-to-lot',row.urgent ? 'Выбрать дневной лот' : 'Перенести в лот',{value:id}) : ''}
        ${row.workspace_lot && row.selection ? button('row-to-urgent','Оформить срочно',{value:id}) : ''}
        ${button('row-to-draft',row.urgent ? 'Снять срочность' : 'Снять с лота',{value:id})}
        ${row.selection ? button('row-refresh','Обновить условия',{value:id}) : ''}
        ${row.urgent ? button('cancel-item','Отменить позицию',{value:id}) : ''}
      </div>`);
  },
  'row-to-lot': id => lotPicker([locateItem(id)]),
  'row-to-urgent': id => makeUrgent([locateItem(id)]),
  'row-refresh': async id => {
    const row = locateItem(id);
    await api('/items/' + id + '/search','POST',{revision:row.revision,query:row.search_result.query,suppliers:[row.selection.supplier]});
    closeModal(); await load({quiet:true});
  },
  'row-to-draft': id => confirmation('Вернуть в черновик','Позиция будет снята с текущего размещения. Предложение сохранится.',
    'Вернуть в черновик',() => api('/placement','POST',{items:refs([locateItem(id)]),action:'draft'})),
  'retry-order': () => checkoutReview(null,state.data.id),
  'cancel-order': () => confirmation('Отменить оформление', 'Подтвердите, что заказ ещё не оформлен в учебном кабинете.',
    'Отменить оформление', () => api('/orders/' + state.data.id + '/cancel','POST')),
  'copy-order': async () => {
    const draft = await api('/orders/' + state.data.id + '/copy','POST');
    await go('/requests/' + draft.id);
  },
  manual: () => {
    const order = state.data;
    dialog('Учебный кабинет · ' + sources[order.supplier], `<p>Учебное ручное оформление по согласованным позициям.
      Для упражнения введите учебный номер вида DEMO-12345.</p>
      ${input('Номер заказа поставщика','number','','required pattern="DEMO-[0-9A-Za-z\\-]{2,75}"')}
      ${checkbox('Подтверждаю регистрацию учебного заказа','confirmed',false,'required')}`, 'Записать номер', async data => {
      await api('/orders/' + order.id + '/manual','POST',{number:data.get('number')}); closeModal(); await load({quiet:true});
    });
  },
  reconcile: () => confirmation('Сверить результат','Будет выполнен поиск учебной квитанции по номеру операции.',
    'Выполнить сверку', async () => {
      const order = await api('/orders/' + state.data.id + '/reconcile','POST');
      notify(order.status === 'accepted' ? 'Учебный заказ найден' : 'Квитанция не найдена. Повтор заблокирован.',order.status !== 'accepted');
    }),
  'supplier-settings': key => {
    const row = state.data.find(r => r.name === key);
    dialog('Настройки · ' + row.title, `${checkbox('Включить в поиск','enabled',row.enabled)}
      ${select('Учебный сценарий','scenario',state.overview.settings.scenarios,row.scenario)}
      <p class="muted">Регион демо · Екатеринбург. Управление реальным доступом выполняется отдельно.</p>`,
    'Сохранить настройки', async data => {
      await api('/suppliers/' + key,'PATCH',{enabled:data.has('enabled'),scenario:data.get('scenario')});
      closeModal(); await load({quiet:true});
    });
  },
  'supplier-check': key => {
    dialog('Проверить источник · ' + sources[key], input('Тестовый артикул','text','FLT-OIL-118','required'),
      'Проверить чтение', async data => {
        const result = await api('/suppliers/' + key + '/check','POST',{text:data.get('text')});
        closeModal(); await load({quiet:true});
        dialog('Диагностика · ' + sources[key], `<p>${pillar(resultLabels[result.status],result.status === 'OK' ? 'ok' : 'warn')}</p>
          ${result.offer ? `<p>Артикул ${e(result.offer.article)} · Цена ${money(result.offer.price,result.offer.currency)} ·
            Остаток ${result.offer.stock} шт. · ${e(dateRange(result.offer))}</p>` : ''}`);
      });
  },
  'lot-settings': () => {
    dialog('Расписание дневного лота', input('Время подготовки новых лотов, ЕКБ','cutoff',state.overview.settings.cutoff,'type="time" required') +
      '<p class="muted">Существующие лоты сохранят своё время закрытия.</p>', 'Подтвердить расписание', async data => {
        await api('/settings','PATCH',{cutoff:data.get('cutoff')}); closeModal(); await load({quiet:true});
      });
  },
  'search-settings': () => {
    const s = state.overview.settings;
    dialog('Настройки поиска', `${select('Сортировка','sort',{price:'По полной цене',date:'По сроку'},s.sort)}
      ${checkbox('В достаточном количестве','stock_only',s.stock_only)}${checkbox('Только оригинал','originals_only',s.originals_only)}
      ${checkbox('Только проверенная применимость','fit_only',s.fit_only)}
      ${isAdmin() ? input('Актуальность цен, мин.','ttl',s.ttl,'type="number" min="1" max="120" required') : ''}`,
    'Сохранить настройки', async data => {
      const update = { sort:data.get('sort'), stock_only:data.has('stock_only'), originals_only:data.has('originals_only'), fit_only:data.has('fit_only') };
      if (data.has('ttl')) update.ttl = Number(data.get('ttl'));
      state.filters = await api('/settings','PATCH',update);
      closeModal(); await load({quiet:true});
    });
  },
  copy: async value => {
    if (navigator.clipboard) await navigator.clipboard.writeText(value);
    else {
      const element = document.createElement('textarea');
      element.value = value; document.body.append(element); element.select();
      const copied = document.execCommand('copy'); element.remove();
      if (!copied) throw new Error('Копирование недоступно в браузере');
    }
    notify('Скопировано');
  },
};

async function quantity(id, delta) {
  const row = locateItem(id);
  const saved = await api('/items/' + id,'PATCH',itemPayload(row,{ quantity:row.quantity + delta }));
  if (row.selection && !saved.selection) notify('Остатка недостаточно. Выберите другое предложение.',true);
  await load({quiet:true});
}

document.addEventListener('click', async event => {
  if (modal.dataset.busy && event.target.closest('dialog') && event.target.closest('a, [data-action]')) {
    event.preventDefault();
    return;
  }
  const anchor = event.target.closest('a[href]');
  if (anchor && anchor.origin === location.origin && !anchor.hash &&
      sections.some(([section]) => anchor.pathname.split('/')[1] === section) &&
      !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && event.button === 0) {
    event.preventDefault();
    if (route().path === 'orders' && !route().key) state.orderListPath = location.pathname + location.search;
    if (modal.open) closeModal();
    await go(anchor.pathname + anchor.search);
    return;
  }
  const control = event.target.closest('[data-action]');
  if (!control || control.disabled) return;
  control.disabled = true;
  let keep = false;
  try { keep = await actions[control.dataset.action]?.(control.dataset.value,control) === 'keep-disabled'; }
  catch (err) { notify(err.message,true); }
  finally { if (!keep) control.disabled = false; }
});

document.addEventListener('change', async event => {
  const control = event.target;
  const name = control.name;
  try {
    if (control.id === 'draft-select' && control.value) return await go('/requests/' + control.value);
    if (name === 'history' && control.value) return await go('/lots/' + control.value);
    if (name === 'marked') {
      const id = Number(control.value);
      if (control.checked) state.checked.add(id); else state.checked.delete(id);
      render();
    } else if (name === 'all-marked') {
      state.checked = new Set(control.checked ? state.draft.items.filter(r => !r.order).map(r => r.id) : []);
      render();
    } else if (name === 'supplier') {
      if (control.checked) state.supplierFilters.add(control.value); else state.supplierFilters.delete(control.value);
      render();
    } else if (name === 'sort') {
      state.filters.sort = control.value;
      render();
    } else if (name === 'urgent-flag' || name === 'original-flag') {
      control.disabled = true;
      const row = locateItem(control.dataset.item);
      if (row.workspace_lot && control.checked && !row.urgent && name === 'urgent-flag') {
        control.checked = false;
        makeUrgent([row]);
        return;
      }
      await api('/items/' + row.id,'PATCH',itemPayload(row,{ [name === 'urgent-flag' ? 'urgent' : 'original_required']:control.checked }));
      await load({quiet:true});
    } else if (name?.startsWith('offer-')) {
      control.disabled = true;
      const row = locateItem(control.dataset.item);
      await api('/items/' + row.id + '/choice','POST',{offer:control.value,revision:row.revision});
      await load({quiet:true});
    }
  } catch (err) { notify(err.message,true); await load({quiet:true}); }
  finally { control.disabled = false; }
});

document.addEventListener('submit', async event => {
  const form = event.target;
  if (form.closest('dialog') || form.id === 'login-form') return;
  event.preventDefault();
  const submit = form.querySelector('button:not([type])');
  if (submit) submit.disabled = true;
  try {
    const data = new FormData(form);
    if (form.id === 'search-form' && activeItem()) {
      submit.textContent = 'Поиск…';
      await searchItems([activeItem()],data.get('query'));
    } else if (form.id === 'lot-date') {
      await go('/lots/' + data.get('day'));
    } else {
      const routes = { 'garage-filter':'/garage', 'order-filter':'/orders',
        'lot-filter':'/lots/' + state.data?.day, 'urgent-filter':'/urgent' };
      if (!routes[form.id]) return;
      const params = new URLSearchParams([...data].filter(([, value]) => value));
      await go(routes[form.id] + (params.size ? '?' + params : ''));
    }
  } catch (err) { notify(err.message,true); }
  finally {
    if (submit) {
      submit.disabled = false;
      if (form.id === 'search-form') submit.innerHTML = svg('search') + ' Найти предложения';
    }
  }
});

document.addEventListener('toggle', event => {
  if (event.target.id === 'cart' && event.target.isConnected) state.cartOpen = event.target.open;
},true);
window.addEventListener('popstate', () => { if (modal.open) closeModal(); load(); });
load();
