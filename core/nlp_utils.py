import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from collections import Counter
from utils.logger_config import setup_logger
import re

logger = setup_logger(__name__)

# تأكد من تحميل الموارد اللازمة لـ NLTK مرة واحدة
try:
    nltk.data.find('corpora/stopwords')
except nltk.downloader.DownloadError:
    logger.info("NLTK 'stopwords' not found. Downloading...")
    nltk.download('stopwords')

try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    logger.info("NLTK 'punkt' not found. Downloading...")
    nltk.download('punkt')

# يمكنك إضافة لغات أخرى إذا لزم الأمر
STOPWORDS_AR = set(stopwords.words('arabic'))
STOPWORDS_EN = set(stopwords.words('english'))

def extract_keywords_from_text(text, language='ar', num_keywords=5):
    """
    Extracts simple keywords from text by frequency, after removing stopwords.
    """
    if not text:
        return []

    # تنظيف أساسي للنص
    text = re.sub(r'<[^>]+>', '', text) # إزالة وسوم HTML
    text = re.sub(r'[^\w\s]', '', text) # إزالة علامات الترقيم (قد ترغب في الاحتفاظ ببعضها)
    text = text.lower() # توحيد حالة الأحرف

    tokens = word_tokenize(text)
    
    current_stopwords = []
    if language == 'ar':
        current_stopwords = STOPWORDS_AR
    elif language == 'en':
        current_stopwords = STOPWORDS_EN
    # يمكنك إضافة المزيد من اللغات
    
    filtered_tokens = [word for word in tokens if word.isalnum() and word not in current_stopwords and len(word) > 2]
    
    if not filtered_tokens:
        return []
        
    word_counts = Counter(filtered_tokens)
    keywords = [word for word, count in word_counts.most_common(num_keywords)]
    
    logger.info(f"Extracted keywords ({language}): {keywords} from text snippet: '{text[:50]}...'")
    return keywords