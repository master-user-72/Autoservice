# Памятка LLM (Yandex / Qwen / отключение)

Агент разбирает заявки **локально**. Облако (YandexGPT, при сбое — Qwen) вызывается только на **нестандартные** формулировки. В базу попадают только **подтверждённые** случаи. Лот, гараж и кабинеты поставщиков от провайдера не зависят.

Точка вызова: `app/llm.py`. Смена провайдера — `.env`, без переписывания лота.

## Быстро выключить всё облако

В `.env`:

```
LLM_PROVIDER=off
```

или очистить `LLM_API_KEY` и `QWEN_API_KEY`.

Перезапустить агент (`run.bat`). Разбор снова только локальный. Записи в `learned_phrases` и `learned_kits` остаются и продолжают работать.

## Быстро отключить только Qwen (запасной)

Оставить Yandex, убрать резерв:

```
QWEN_FALLBACK=0
```

или очистить `QWEN_API_KEY`.

Перезапуск. При недоступности Yandex агент вернётся к локальному разбору, Qwen не вызовется.

## Быстро перейти только на Qwen

```
LLM_PROVIDER=qwen
QWEN_API_KEY=<ключ DashScope>
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
QWEN_FALLBACK=0
```

Yandex-ключи можно не трогать — при `LLM_PROVIDER=qwen` они не используются.

## Yandex + Qwen (основной + запасной)

По умолчанию: сначала Yandex, при ошибке или таймауте — Qwen.

```
LLM_PROVIDER=yandex
LLM_API_KEY=<ключ сервисного аккаунта Yandex Cloud>
LLM_FOLDER_ID=<id каталога>
LLM_BASE_URL=https://ai.api.cloud.yandex.net/v1
LLM_MODEL=yandexgpt

QWEN_API_KEY=<ключ DashScope / Qwen Cloud>
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
QWEN_FALLBACK=1
```

Ключ Yandex: консоль Yandex Cloud → сервисный аккаунт → API-ключ с правом `yc.ai.languageModels.execute`.  
`LLM_FOLDER_ID` — каталог, где включён AI Studio. Модель собирается как `gpt://<folder>/yandexgpt/latest`. Для Lite: `LLM_MODEL=yandexgpt-lite`.

Ключ Qwen: [DashScope / Qwen Cloud](https://dashscope.console.aliyun.com/) → API Keys.  
Регионы URL не смешивать с ключом:

| Регион | `QWEN_BASE_URL` |
|---|---|
| Китай (Пекин) | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Международный (Сингапур) | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| США (Вирджиния) | `https://dashscope-us.aliyuncs.com/compatible-mode/v1` |

Модели: `qwen-plus`, `qwen-turbo`, `qwen-max`, `qwen-plus-latest`.

## OpenAI или совместимый шлюз

```
LLM_PROVIDER=openai
LLM_API_KEY=<ключ>
LLM_FOLDER_ID=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_NONSTANDARD_ONLY=1
QWEN_FALLBACK=0
```

После любой смены — перезапуск сервера. Код лота не трогать.

## Как работает B + C

1. Локальный разбор (госномер, VIN, типовые детали, комплект ГРМ).
2. Если фраза уже есть в `learned_phrases` — облако не зовётся.
3. Если формулировка редкая (неясная деталь, «подобрать всё», длинная фраза, нет списка запчастей) и ключ задан — вызывается облако (Yandex, при сбое — Qwen).
4. В SQLite фраза пишется **только после подтверждения** в режиме обучения (кнопка ОК / «Подтвердить все»). Без обучения — сразу при успешной заявке, потому что позиции уже confirmed.
5. Следующая такая же формулировка идёт из базы, без облака.

Типовые заявки вроде «А123АА72 фильтр масляный» в облако не уходят.

## Где лежат знания

| Таблица | Что |
|---|---|
| `learned_phrases` | подтверждённая фраза → список позиций / комплект |
| `learned_kits` | состав комплекта по машине (как раньше) |

Файл базы: `data/agent.db`. От провайдера не зависит. Отказ от облака эти таблицы не чистит.

## Если что-то чинить в коде

| Задача | Файл |
|---|---|
| Другой HTTP-заголовок / URL / fallback | только `app/llm.py` и `.env` |
| Когда считать заявку нестандартной | `is_nonstandard()` в `app/nlu.py` |
| Что писать после ОК | `app/learn.py` |
| Выключить облако без `.env` | `LLM_PROVIDER=off` всё равно предпочтительнее |

Не вшивать имя провайдера в `lot_service` и поставщиков.

## Проверка

В шапке: «Yandex→Qwen: нестандарт», если настроены оба; «Yandex: нестандарт» — только Яндекс; «Qwen: нестандарт» — только Qwen; «локальный разбор» — если выключено.  
В статусе заявки: «Разбор заявки (нестандарт, LLM)» или «из базы формулировок».
