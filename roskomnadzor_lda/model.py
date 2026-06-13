import json
import re
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import pymorphy3
from collections import Counter
import warnings
from pathlib import Path
warnings.filterwarnings('ignore')

# Загрузка необходимых данных для NLTK (выполните один раз)
# nltk.download('punkt')
# nltk.download('punkt_tab')
# nltk.download('stopwords')

current_dir = Path(__file__).parent
DATA_PATH = current_dir / "data/rkn_news_13_06_2026_16_52.json"

class RKNTextProcessor:
    """Класс для предобработки текстов статей Роскомнадзора"""
    
    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer()
        self.stop_words = set(stopwords.words('russian'))
        # Добавляем лемматизированные формы (именно их будет проверять код)
        self.stop_words.update([
            'россия', 'рф', 'москва', 'год', 'также', 'данный', 'более',
            'роскомнадзор', 'российский', 'федерация', 'федеральный',
            'рф', 'россиянин', 'новый', 'заседание', 'сообщение',
            'страна', "это", "который", "свой", "мочь", 'работа',
            'организация', 'деятельность', 'мероприятие',
            'провести', 'отметить', 'развитие', 'весь', 'ооо', 'оао', 'пао',
            'жаров', 'александр', 'наш', 'всё', 'человек',
            'сказать', 'время', 'работать',
            'стать', 'первый', 'иметь', 'должный'
        ])
        
    def clean_text(self, text):
        """Очистка и нормализация текста"""
        if not text or text == "":
            return ""
        
        # Удаляем символы новой строки и лишние пробелы
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        # Удаляем специальные символы и цифры (оставляем только буквы и пробелы)
        text = re.sub(r'[^а-яА-ЯёЁ\s]', ' ', text)
        
        # Приводим к нижнему регистру
        text = text.lower()
        
        return text.strip()
    
    def lemmatize_text(self, text):
        """Лемматизация текста (приведение к нормальной форме)"""
        if not text:
            return ""
        
        # Токенизация
        words = word_tokenize(text, language='russian')
        
        # Лемматизация и удаление стоп-слов
        lemmatized_words = []
        for word in words:
            if len(word) > 2:  # сначала проверяем длину
                lemma = self.morph.parse(word)[0].normal_form
                # ПОСЛЕ лемматизации проверяем стоп-слова
                if lemma not in self.stop_words:
                    lemmatized_words.append(lemma)
        
        return ' '.join(lemmatized_words)
    
    def process_articles(self, articles_data):
        """Основной метод обработки всех статей"""
        processed_texts = []
        titles_only_count = 0
        full_texts_count = 0
        
        for article in articles_data:
            # Проверяем наличие полного текста
            if article.get('full_text') and article['full_text'].strip():
                text = article['full_text']
                full_texts_count += 1
            else:
                # Используем заголовок, если текст отсутствует
                text = article.get('title', '')
                titles_only_count += 1
            
            # Предобработка текста
            cleaned_text = self.clean_text(text)
            if cleaned_text:  # Только непустые тексты
                lemmatized_text = self.lemmatize_text(cleaned_text)
                processed_texts.append(lemmatized_text)
            else:
                processed_texts.append("")  # Пустая строка для исключения
        
        print(f"Обработано статей: {len(articles_data)}")
        print(f"  - С полным текстом: {full_texts_count}")
        print(f"  - Только заголовок: {titles_only_count}")
        print(f"  - Пропущено (пустые): {len(articles_data) - len([t for t in processed_texts if t])}")
        
        return processed_texts

class LDATopicModeler:
    """Класс для построения и анализа LDA модели"""
    
    def __init__(self, n_topics=12, max_features=1000):
        self.n_topics = n_topics
        self.max_features = max_features
        self.vectorizer = None
        self.lda_model = None
        
    def create_document_term_matrix(self, texts):
        """Создание матрицы документ-термин"""
        # Фильтруем пустые тексты
        non_empty_texts = [text for text in texts if text]
        empty_indices = [i for i, text in enumerate(texts) if not text]
        
        # Создаем векторизатор
        self.vectorizer = CountVectorizer(
            max_features=self.max_features,
            min_df=250,  # термин должен встречаться минимум в 250 документах
            max_df=0.8,  # игнорируем слишком частотные термины
            ngram_range=(1, 2)  # униграммы и биграммы
        )
        
        doc_term_matrix = self.vectorizer.fit_transform(non_empty_texts)
        print(f"Создана матрица документ-термин: {doc_term_matrix.shape}")
        print(f"Количество уникальных терминов: {len(self.vectorizer.get_feature_names_out())}")
        
        return doc_term_matrix, non_empty_texts, empty_indices
    
    def fit_lda(self, doc_term_matrix):
        """Обучение LDA модели"""
        self.lda_model = LatentDirichletAllocation(
            n_components=self.n_topics,
            random_state=42,
            learning_method='batch',
            max_iter=100,
            n_jobs=-1
        )
        
        topic_distribution = self.lda_model.fit_transform(doc_term_matrix)
        print(f"LDA модель обучена. Перплексия: {self.lda_model.perplexity(doc_term_matrix):.2f}")
        
        return topic_distribution
    
    def display_topics(self, n_words=5):
        """Вывод топ-слов для каждой темы"""
        feature_names = self.vectorizer.get_feature_names_out()
        
        topics_dict = {}
        for topic_idx, topic in enumerate(self.lda_model.components_):
            top_features_ind = topic.argsort()[:-n_words-1:-1]
            top_features = [feature_names[i] for i in top_features_ind]
            top_weights = [topic[i] for i in top_features_ind]
            
            topics_dict[f"Тема {topic_idx+1}"] = {
                "слова": top_features,
                "веса": [round(w, 3) for w in top_weights]
            }
            
            print(f"\n📚 Тема {topic_idx+1}:")
            print(f"   Слова: {', '.join(top_features)}")
        
        return topics_dict
    
    def assign_dominant_topic(self, topic_distribution):
        """Определение доминирующей темы для каждого документа"""
        dominant_topics = np.argmax(topic_distribution, axis=1)
        topic_weights = np.max(topic_distribution, axis=1)
        
        return dominant_topics, topic_weights

def main():
    # 1. Загрузка данных из JSON файла
    print("=" * 60)
    print("📥 ЗАГРУЗКА ДАННЫХ")
    print("=" * 60)
    
    # Укажите путь к вашему JSON файлу
    json_file_path = DATA_PATH  # ЗАМЕНИТЕ НА ВАШ ФАЙЛ
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            articles = json.load(f)
        print(f"Загружено статей: {len(articles)}")
    except FileNotFoundError:
        print(f"❌ Файл {json_file_path} не найден!")
        print("Пожалуйста, укажите правильный путь к JSON файлу с результатами парсинга")
        return
    
    # 2. Предобработка текстов
    print("\n" + "=" * 60)
    print("🛠️ ПРЕДОБРАБОТКА ТЕКСТОВ")
    print("=" * 60)
    
    processor = RKNTextProcessor()
    processed_texts = processor.process_articles(articles)
    
    # Статистика по длинам текстов
    text_lengths = [len(text.split()) for text in processed_texts if text]
    if text_lengths:
        print(f"\nСтатистика по длине текстов (в словах):")
        print(f"  - Средняя: {np.mean(text_lengths):.1f}")
        print(f"  - Медиана: {np.median(text_lengths):.1f}")
        print(f"  - Минимум: {np.min(text_lengths)}")
        print(f"  - Максимум: {np.max(text_lengths)}")
    
    # 3. LDA моделирование
    print("\n" + "=" * 60)
    print("🎯 LDA ТЕМАТИЧЕСКОЕ МОДЕЛИРОВАНИЕ")
    print("=" * 60)
    
    topic_modeler = LDATopicModeler()
    
    # Создание матрицы документ-термин
    doc_term_matrix, valid_texts, empty_indices = topic_modeler.create_document_term_matrix(processed_texts)
    
    if doc_term_matrix.shape[0] == 0:
        print("❌ Нет валидных текстов для анализа!")
        return
    
    # Обучение LDA
    topic_distribution = topic_modeler.fit_lda(doc_term_matrix)
    
    # Отображение результатов
    topics = topic_modeler.display_topics(n_words=12)
    
    # 4. Распределение тем по документам
    dominant_topics, topic_weights = topic_modeler.assign_dominant_topic(topic_distribution)
    
    print("\n" + "=" * 60)
    print("📊 РАСПРЕДЕЛЕНИЕ ТЕМ")
    print("=" * 60)
    
    topic_counts = Counter(dominant_topics)
    for topic_idx in range(topic_modeler.n_topics):
        count = topic_counts.get(topic_idx, 0)
        percentage = (count / len(dominant_topics)) * 100
        print(f"Тема {topic_idx+1}: {count} документов ({percentage:.1f}%)")
    
    # 5. Сохранение результатов
    print("\n" + "=" * 60)
    print("💾 СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
    print("=" * 60)
    
    # Сохраняем темы в отдельный файл
    topics_export = {
        "параметры_модели": {
            "количество_тем": topic_modeler.n_topics,
            "максимум_слов": topic_modeler.max_features,
            "перплексия": float(topic_modeler.lda_model.perplexity(doc_term_matrix))
        },
        "темы": topics
    }
    
    topics_filename = current_dir / "data/LDA_analys/LDA_topics.json"
    with open(topics_filename, 'w', encoding='utf-8') as f:
        json.dump(topics_export, f, ensure_ascii=False, indent=4)
    print(f"✓ Сохранены темы в файл: {topics_filename}")
    
    # Сохраняем распределение тем по документам
    # Для этого нужно сопоставить темы с исходными документами
    doc_topics = []
    valid_idx = 0
    
    for i, article in enumerate(articles):
        if i in empty_indices:
            doc_topics.append({
                "id": article.get('id', i),
                "title": article.get('title', 'Без заголовка'),
                "url": article.get('url', ''),
                "dominant_topic": None,
                "topic_weight": None,
                "note": "Документ исключен из анализа (пустой текст)"
            })
        else:
            doc_topics.append({
                "id": article.get('id', i),
                "title": article.get('title', 'Без заголовка'),
                "url": article.get('url', ''),
                "dominant_topic": int(dominant_topics[valid_idx]) + 1,
                "topic_weight": float(topic_weights[valid_idx]),
                "note": "Анализ выполнен"
            })
            valid_idx += 1
    
    distribution_filename = current_dir / "data/LDA_analys/doc_topic_distribution.json"
    with open(distribution_filename, 'w', encoding='utf-8') as f:
        json.dump(doc_topics, f, ensure_ascii=False, indent=4)
    print(f"✓ Сохранено распределение тем в файл: {distribution_filename}")
    
    # 6. Примеры документов по каждой теме
    print("\n" + "=" * 60)
    print("📄 ПРИМЕРЫ ДОКУМЕНТОВ ПО ТЕМАМ")
    print("=" * 60)
    
    for topic_num in range(topic_modeler.n_topics):
        print(f"\n🔹 Тема {topic_num+1}:")
        seen_titles = set()
        count = 0
        for doc in doc_topics:
            if doc.get('dominant_topic') == topic_num + 1:
                title = doc['title'][:250]
                if title not in seen_titles and count < 3:
                    seen_titles.add(title)
                    print(f"   {count+1}. {title}...")
                    count += 1
    
    print("\n" + "=" * 60)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 60)

if __name__ == "__main__":
    main()