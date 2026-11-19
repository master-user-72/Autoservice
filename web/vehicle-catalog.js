const fields = ['make', 'model', 'generation', 'year', 'body', 'engine'];
const collator = new Intl.Collator('ru', { numeric: true, sensitivity: 'base' });
const normalized = value => value.trim().toLocaleLowerCase('ru');

function yearRange(text, latest) {
  const match = text.match(/^(\d{4})(?:\s*[-–—]\s*(\d{4})?)?$/);
  if (!match) return null;
  const from = Number(match[1]);
  const to = match[2] ? Number(match[2]) : /[-–—]\s*$/.test(text) ? latest : from;
  return [from, Math.min(to, latest)];
}

function suggestions(rows, field, values, query, latest) {
  const previous = fields.slice(0, fields.indexOf(field));
  const options = new Map();

  for (const row of rows) {
    if (!row[field]) continue;
    let scope = '';
    const eligible = previous.every(key => {
      if (!values[key]) return true;
      if (!row[key] && (field === 'body' || field === 'engine') &&
          ['generation', 'year', 'body'].includes(key)) {
        scope = row.generation ? 'По поколению' : 'По модели';
        return true;
      }
      if (key !== 'year') return normalized(row[key]) === normalized(values[key]);
      const range = yearRange(row.year, latest);
      const year = Number(values.year);
      return range && year >= range[0] && year <= range[1];
    });
    if (!eligible) continue;

    const add = value => {
      const key = normalized(value);
      if (!key.includes(normalized(query))) return;
      const known = options.get(key);
      if (!known || (known.scope && !scope)) options.set(key, { value, scope });
    };
    if (field === 'year') {
      const range = yearRange(row.year, latest);
      if (!range) continue;
      for (let year = range[0]; year <= range[1]; year++) add(String(year));
    } else {
      add(row[field]);
    }
  }

  return [...options.values()].sort((a, b) => Number(!!a.scope) - Number(!!b.scope) ||
    (field === 'year' ? Number(b.value) - Number(a.value) : collator.compare(a.value, b.value)));
}

export function connectVehicleCatalog(form, loadRows) {
  const inputs = Object.fromEntries(fields.map(field => [field, form.elements.namedItem(field)]));
  const latest = new Date().getFullYear() + 1;
  let active = null;
  let highlight = -1;
  let results = [];
  let rows = null;
  let loadFailed = false;
  let query = '';

  function close() {
    if (!active) return;
    active.list.hidden = true;
    active.input.setAttribute('aria-expanded', 'false');
    active.input.removeAttribute('aria-activedescendant');
    active = null;
  }

  function render() {
    if (!active) return;
    const { field, list, input } = active;
    list.replaceChildren();
    highlight = -1;
    input.removeAttribute('aria-activedescendant');
    const values = Object.fromEntries(fields.map(name => [name, inputs[name].value.trim()]));
    results = rows ? suggestions(rows, field, values, query, latest) : [];
    if (!results.length) {
      const message = document.createElement('div');
      message.className = 'catalog-message';
      message.setAttribute('role', 'status');
      message.textContent = loadFailed ? 'Справочник недоступен. Можно ввести значение вручную.'
        : rows ? 'Совпадений нет. Можно ввести значение вручную.' : 'Загрузка справочника…';
      list.append(message);
    }
    for (const [index, { value, scope }] of results.entries()) {
      const option = document.createElement('div');
      option.id = list.id + '-' + index;
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', 'false');
      option.textContent = value;
      if (scope) {
        const detail = document.createElement('small');
        detail.textContent = scope;
        option.append(detail);
      }
      option.addEventListener('pointerdown', event => event.preventDefault());
      option.addEventListener('click', () => choose(index));
      list.append(option);
    }
    const dialog = form.closest('dialog');
    list.classList.toggle('above', dialog.getBoundingClientRect().bottom -
      input.getBoundingClientRect().bottom < Math.min(208, list.scrollHeight) + 5 &&
      input.getBoundingClientRect().top - dialog.getBoundingClientRect().top >
      dialog.getBoundingClientRect().bottom - input.getBoundingClientRect().bottom);
    list.scrollTop = 0;
  }

  function open(field, queryText = '') {
    if (active?.field !== field) close();
    const input = inputs[field];
    const list = form.querySelector('#catalog-' + field);
    active = { field, list, input };
    query = queryText;
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    render();
  }

  function choose(index) {
    if (!active || !results[index]) return;
    const { input } = active;
    input.value = results[index].value;
    close();
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function move(step) {
    if (!results.length) return;
    active.list.children[highlight]?.setAttribute('aria-selected', 'false');
    const next = highlight < 0 && step < 0 ? results.length - 1 : (highlight + step + results.length) % results.length;
    highlight = next;
    const option = active.list.children[highlight];
    option.setAttribute('aria-selected', 'true');
    active.input.setAttribute('aria-activedescendant', option.id);
    option.scrollIntoView({ block: 'nearest' });
  }

  for (const [field, input] of Object.entries(inputs)) {
    input.addEventListener('focus', () => open(field));
    input.addEventListener('click', () => { if (!active) open(field); });
    input.addEventListener('input', () => open(field, input.value));
    input.addEventListener('blur', () => { if (active?.input === input) close(); });
    input.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (!active) open(field);
        move(event.key === 'ArrowDown' ? 1 : -1);
      } else if (active && event.key === 'Enter' && highlight >= 0) {
        event.preventDefault();
        choose(highlight);
      } else if (active && event.key === 'Escape') {
        event.preventDefault();
        close();
      }
    });
  }

  loadRows().then(data => {
    rows = data;
    if (form.isConnected) render();
  }).catch(() => {
    loadFailed = true;
    if (form.isConnected) render();
  });
}
