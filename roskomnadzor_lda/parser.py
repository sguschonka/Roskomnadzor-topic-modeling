import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pickle

import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import cloudscraper  # альтернативный подход для сложных случаев

class SafeRKNParser:
    """Безопасный асинхронный парсер с защитой от блокировок"""
    
    def __init__(self, 
                 max_concurrent: int = 25,
                 request_delay: Tuple[float, float] = (2.0, 5.0),
                 use_proxies: bool = False):
        """
        Args:
            max_concurrent: максимальное количество параллельных запросов
            request_delay: диапазон задержек между запросами (мин, макс) в секундах
            use_proxies: использовать ли ротацию прокси
        """
        self.max_concurrent = max_concurrent
        self.min_delay, self.max_delay = request_delay
        self.use_proxies = use_proxies
        
        self.ua = UserAgent()
        self.session = None
        self.proxy_list = []
        self.current_proxy_index = 0
        self.failed_requests = 0
        self.successful_requests = 0
        
        # Загрузка прокси (если нужно)
        if use_proxies:
            self._load_proxies()
    
    def _load_proxies(self):
        """Загружает список прокси из файла"""
        proxy_file = Path(__file__).parent / "data/proxies.txt"
        if proxy_file.exists():
            with open(proxy_file, 'r') as f:
                self.proxy_list = [line.strip() for line in f if line.strip()]
            print(f"✅ Загружено прокси: {len(self.proxy_list)}")
        else:
            print("⚠️ Файл proxies.txt не найден, работа без прокси")
            self.use_proxies = False
    
    def _get_next_proxy(self) -> Optional[str]:
        """Возвращает следующий прокси (round-robin)"""
        if not self.proxy_list:
            return None
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return proxy
    
    def _get_headers(self) -> Dict[str, str]:
        """Генерирует случайные заголовки, имитирующие реальный браузер"""
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
    
    async def _smart_delay(self):
        """Умная задержка с добавлением случайного джиттера"""
        delay = random.uniform(self.min_delay, self.max_delay)
        # Добавляем небольшой случайный шум, чтобы не быть детектированным
        jitter = random.uniform(-0.5, 0.5)
        delay = max(0.5, delay + jitter)
        await asyncio.sleep(delay)
    
    async def _fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        """
        Загружает страницу с автоматическими повторными попытками
        и экспоненциальной задержкой
        """
        for attempt in range(max_retries):
            try:
                # Получаем прокси для этого запроса
                proxy = self._get_next_proxy() if self.use_proxies else None
                
                async with self.session.get(
                    url, 
                    headers=self._get_headers(),
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        self.successful_requests += 1
                        content = await response.text()
                        return content
                    
                    elif response.status == 403:
                        print(f"🚫 403 Forbidden для {url} (попытка {attempt+1}/{max_retries})")
                        # Увеличиваем задержку после 403
                        await asyncio.sleep(30 * (attempt + 1))
                    
                    elif response.status == 429:
                        print(f"⏱️ Rate limit для {url} (попытка {attempt+1}/{max_retries})")
                        # Ждём значительно дольше
                        await asyncio.sleep(60 * (attempt + 1))
                    
                    else:
                        print(f"⚠️ HTTP {response.status} для {url}")
                        await self._smart_delay()
                        
            except asyncio.TimeoutError:
                print(f"⏰ Таймаут для {url} (попытка {attempt+1}/{max_retries})")
            except aiohttp.ClientError as e:
                print(f"🔌 Ошибка соединения для {url}: {e}")
            except Exception as e:
                print(f"❌ Неизвестная ошибка для {url}: {e}")
            
            # Экспоненциальная задержка перед повтором
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * random.uniform(5, 10)
                print(f"⏳ Ожидание {wait_time:.1f} сек перед повтором...")
                await asyncio.sleep(wait_time)
        
        self.failed_requests += 1
        print(f"❌ Не удалось загрузить {url} после {max_retries} попыток")
        return None
    
    async def parse_news_list(self, page_offset: int) -> List[Dict]:
        """Парсит список новостей на странице"""
        url = f"https://rkn.gov.ru/press/news/p{page_offset}/"
        
        html = await self._fetch_with_retry(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "lxml")
        news_blocks = soup.find_all("li", {"class": "press-service-cardItem"})
        
        news_items = []
        for block in news_blocks:
            # Заголовок
            title_tag = block.find("h3", {"class": "press-service-cardTitle"})
            title = title_tag.get_text(strip=True) if title_tag else ""
            
            # Ссылка
            link_tag = block.find("a")
            if link_tag and link_tag.get('href'):
                relative_link = link_tag.get('href')
                full_link = relative_link if relative_link.startswith('http') else f"https://rkn.gov.ru{relative_link}"
            else:
                full_link = ""
            
            if title and full_link:
                news_items.append({
                    "title": title,
                    "url": full_link,
                    "news_id": full_link.split('/')[-1].replace('news', '').replace('.htm', '')
                })
        
        return news_items
    
    async def parse_article(self, article_url: str) -> Optional[Dict]:
        """Парсит отдельную статью с извлечением даты"""
        html = await self._fetch_with_retry(article_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        
        # 1. ИЗВЛЕЧЕНИЕ ЗАГОЛОВКА
        title = ""
        parent_div = soup.find("div", class_="inner-page-body-content widthMenu")
        if parent_div:
            h1_tag = parent_div.find("h1")
            if h1_tag:
                title = h1_tag.get_text(strip=True)
        
        if not title:
            h1_tag = soup.find("h1")
            if h1_tag:
                title = h1_tag.get_text(strip=True)
        
        # 2. ИЗВЛЕЧЕНИЕ ДАТЫ И ТЕКСТА
        content_div = soup.find("div", class_="text_content bordernone")
        
        full_text = ""
        publish_date = None
        
        if content_div:
            # Извлекаем дату из <h3>
            date_h3 = content_div.find("h3")
            if date_h3:
                date_text = date_h3.get_text(strip=True)
                import re
                # Формат: "2 июня 2026 года" или "2 июня 2026 г."
                match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_text)
                if match:
                    day, month_ru, year = match.groups()
                    months = {
                        'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
                        'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
                        'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
                    }
                    month = months.get(month_ru.lower(), '01')
                    publish_date = f"{day.zfill(2)}.{month}.{year}"
            
            # Извлекаем текст статьи (все параграфы)
            paragraphs = content_div.find_all("p")
            full_text = "\n".join(p.get_text(strip=True) for p in paragraphs)
        
        # Запасной вариант для даты
        if not publish_date:
            import re
            small_tags = soup.find_all("small")
            for tag in small_tags:
                text = tag.get_text(strip=True)
                match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
                if match:
                    publish_date = match.group(1)
                    break
        
        return {
            "full_text": full_text,
            "title": title,
            "publish_date": publish_date
        }
    
    async def collect_all_links(self, start_offset: int = 0, max_pages: int = 100) -> List[Dict]:
        """Собирает все ссылки на новости, начиная с указанного смещения"""
        all_news = []
        current_offset = start_offset
        empty_pages = 0
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_parse(offset):
            async with semaphore:
                return await self.parse_news_list(offset)
        
        for page in range(max_pages):
            print(f"\n📄 Страница с offset={current_offset}")
            
            # Проверяем не перегружаем ли сервер
            await self._smart_delay()
            
            news_items = await bounded_parse(current_offset)
            
            if not news_items:
                empty_pages += 1
                if empty_pages >= 3:  # Три пустые страницы подряд = конец
                    print(f"📭 Пустые страницы: {empty_pages}, завершаем сбор ссылок")
                    break
            else:
                empty_pages = 0
                all_news.extend(news_items)
                print(f"📊 Найдено новостей: {len(all_news)}")
            
            current_offset += 20  # Шаг пагинации
        
        return all_news
    
    async def parse_all_articles(self, news_list: List[Dict]) -> List[Dict]:
        """Массовый парсинг всех статей с контролем параллельности"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def safe_parse_article(news_item):
            async with semaphore:
                article_data = await self.parse_article(news_item["url"])
                if article_data:
                    news_item["full_text"] = article_data.get("full_text", "")
                    news_item["publish_date"] = article_data.get("publish_date")  # ✅ ДОБАВИТЬ
                    if article_data.get("title"):
                        news_item["title"] = article_data["title"]
                else:
                    news_item["full_text"] = ""
                    news_item["publish_date"] = None  # ✅ ДОБАВИТЬ
                
                await self._smart_delay()
                return news_item
        
        tasks = [safe_parse_article(item) for item in news_list]
        results = await asyncio.gather(*tasks)
        
        return results
    
    def save_checkpoint(self, data: List[Dict], checkpoint_file: Path):
        """Сохраняет промежуточный результат для возобновления"""
        with open(checkpoint_file, 'wb') as f:
            pickle.dump({
                'timestamp': datetime.now(),
                'data': data,
                'stats': {
                    'successful': self.successful_requests,
                    'failed': self.failed_requests
                }
            }, f)
        print(f"💾 Сохранён чекпоинт: {checkpoint_file}")
    
    def load_checkpoint(self, checkpoint_file: Path) -> Optional[List[Dict]]:
        """Загружает сохранённый чекпоинт"""
        try:
            with open(checkpoint_file, 'rb') as f:
                checkpoint = pickle.load(f)
            print(f"🔄 Загружен чекпоинт от {checkpoint['timestamp']}")
            print(f"   Статистика: успешно={checkpoint['stats']['successful']}, ошибок={checkpoint['stats']['failed']}")
            return checkpoint['data']
        except Exception as e:
            print(f"⚠️ Не удалось загрузить чекпоинт: {e}")
            return None
    
    def print_statistics(self):
        """Выводит статистику работы парсера"""
        print("\n" + "="*50)
        print("📊 СТАТИСТИКА ПАРСЕРА")
        print("="*50)
        print(f"✅ Успешных запросов: {self.successful_requests}")
        print(f"❌ Неудачных запросов: {self.failed_requests}")
        print(f"🎯 Успешность: {(self.successful_requests/(self.successful_requests+self.failed_requests)*100 if self.successful_requests+self.failed_requests > 0 else 0):.1f}%")
        print("="*50)

async def main():
    parser = SafeRKNParser(
        max_concurrent=25,
        request_delay=(3.0, 7.0),
        use_proxies=False
    )
    
    # ЯВНО СОЗДАЁМ СЕССИЮ В КОНТЕКСТНОМ МЕНЕДЖЕРЕ
    async with aiohttp.ClientSession() as session:
        parser.session = session
        
        checkpoint_file = Path(__file__).parent / "data/checkpoint.pkl"
        result_file = Path(__file__).parent / f"data/rkn_news_{datetime.now().strftime('%d_%m_%Y_%H_%M')}.json"
        
        news_data = parser.load_checkpoint(checkpoint_file)
        
        if not news_data:
            print("🔍 Начинаем сбор ссылок...")
            news_data = await parser.collect_all_links(start_offset=0, max_pages=200)
            if not news_data:
                print("❌ Не удалось собрать ссылки!")
                return
            parser.save_checkpoint(news_data, checkpoint_file)
        
        print(f"\n📑 Собрано ссылок: {len(news_data)}")
        print("📖 Начинаем парсинг статей...")
        articles = await parser.parse_all_articles(news_data)
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=4)
        
        parser.print_statistics()
        print(f"\n✅ Результат сохранён в {result_file}")
        
if __name__ == "__main__":
    asyncio.run(main())