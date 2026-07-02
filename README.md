# 📡 Roskomnadzor Topic Modeling

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Active](https://img.shields.io/badge/Status-Active-brightgreen)]()

> Тематическое моделирование новостной колонки сайта [Роскомнадзора](https://rkn.gov.ru) с помощью LDA.
> Анализируем более 20 лет пресс-релизов — с февраля 2005 года по настоящее время.

## 🎯 О проекте

Роскомнадзор — ключевой регулятор российского интернета и СМИ. Его пресс-служба публикует новости, отражающие priorities ведомства: от блокировок сайтов до регулирования персональных данных.

Этот проект автоматически:
1. **Собирает** все новости с сайта rkn.gov.ru
2. **Обрабатывает** русскоязычные тексты (очистка, лемматизация, удаление стоп-слов)
3. **Строит** тематическую LDA-модель для выявления скрытых тем
4. **Анализирует** распределение тем по документам и во времени

---

## ✨ Возможности

### 🕷️ Безопасный асинхронный парсер
- Асинхронная загрузка с `asyncio` + `aiohttp`
- Ротация User-Agent через `fake_useragent`
- Поддержка прокси (round-robin)
- Экспоненциальный backoff при ошибках (403, 429, timeout)
- Контроль параллельности через семафоры
- **Чекпоинты** — возможность возобновить парсинг после сбоя

### 🧹 Предобработка текстов
- Очистка от HTML, спецсимволов и чисел
- Токенизация через `NLTK`
- Лемматизация через `pymorphy3`
- Кастомный словарь стоп-слов (отфильтрованы «роскомнадзор», «россия», «рф» и т.д.)

### 📊 LDA-моделирование
- Матрица «документ-термин» с униграммами и биграммами
- Фильтрация слишком редких и частых терминов (`min_df`, `max_df`)
- Автоматический подбор доминирующей темы для каждого документа
- Экспорт результатов в JSON

---

## 🏗️ Архитектура

```
Roskomnadzor-topic-modeling/
├── roskomnadzor_lda/
│   ├── parser.py          # 🕷️ Асинхронный парсер rkn.gov.ru
│   ├── model.py           # 🧠 LDA-моделирование и предобработка
│   ├── main.ipynb         # 📓 Основной ноутбук с пайплайном
│   └── data/              # 📁 Данные (парсинг + результаты LDA)
│       ├── *.json         #    Спарсенные новости
│       └── LDA_analys/    #    Результаты тематического моделирования
├── tests/                 # 🧪 Тесты
├── .gitignore
└── README.md
```

### Поток данных

```
rkn.gov.ru ──→ parser.py ──→ raw JSON ──→ model.py ──→ LDA topics
   (HTML)      (async)       (статьи)     (NLP)        (JSON)
```

---

## 🚀 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/sguschonka/Roskomnadzor-topic-modeling.git
cd Roskomnadzor-topic-modeling
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate     # Windows
```

<details>
<summary>📦 Список зависимостей</summary>

```
aiohttp
beautifulsoup4
lxml
cloudscraper
fake-useragent
nltk
pymorphy3
scikit-learn
numpy
pandas
jupyter
```

</details>

### 3. Загрузка данных NLTK

```python
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('stopwords')
```

---

## 📖 Использование

### Шаг 1: Парсинг новостей

```bash
cd roskomnadzor_lda
python parser.py
```

Парсер:
- Соберёт все ссылки на новости с пагинацией
- Загрузит полный текст и дату каждой статьи
- Сохранит результат в `data/rkn_news_DD_MM_YYYY_HH_MM.json`
- Создаст чекпоинт `data/checkpoint.pkl` для возобновления

> ⚙️ **Настройки** можно изменить в `parser.py`:
> - `max_concurrent` — кол-во параллельных запросов (по умолчанию 25)
> - `request_delay` — задержка между запросами (по умолчанию 2–5 сек)
> - `use_proxies` — включить ротацию прокси

### Шаг 2: Тематическое моделирование

Откройте `main.ipynb` в Jupyter и выполните все ячейки, или:

```bash
python model.py
```

Модель:
- Загрузит спарсенные данные
- Проведёт предобработку (очистка → лемматизация)
- Обучит LDA с 12 темами
- Выводит топ-слова каждой темы
- Сохранит темы и распределение в `data/LDA_analys/`

---

## 📈 Результаты

После выполнения пайплайна вы получите:

| Файл | Описание |
|------|----------|
| `LDA_topics.json` | Топ-слова по каждой теме + параметры модели (перплексия) |
| `doc_topic_distribution.json` | Для каждой статьи: доминирующая тема, вес темы, метаданные |

### Пример вывода

```
📚 Тема 1:
   Слова: закон, проект, рассмотрение, принятие, regulation, ...

📚 Тема 2:
   Слова: персональный, данные, оператор, обработка, согласие, ...

📊 РАСПРЕДЕЛЕНИЕ ТЕМ
Тема 1: 342 документов (18.2%)
Тема 2: 287 документов (15.3%)
...
```

---

## 🛠️ Технологии

| Компонент | Инструмент |
|-----------|-----------|
| Парсинг | `asyncio`, `aiohttp`, `BeautifulSoup4`, `lxml`, `cloudscraper` |
| NLP | `NLTK`, `pymorphy3` |
| ML | `scikit-learn` (LDA, CountVectorizer) |
| Данные | `pandas`, `numpy`, `json` |
| Среда | `Jupyter Notebook` |

## 📄 Лицензия

MIT License — используйте свободно. См. [LICENSE](LICENSE).

---

## 🤝 Contributing

Pull requests приветствуются! Для серьёзных изменений сначала откройте issue, чтобы обсудить идею.

---

<div align="center">

**Сделано с ☕ и Python для анализа государственного регулирования интернета**

[⬆ Наверх](#-roskomnadzor-topic-modeling)

</div>
```
