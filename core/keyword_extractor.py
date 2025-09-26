# core/keyword_extractor.py
import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

# استيراد NLTK يتم الآن داخل كتلة try...except
try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("NLTK library not found. Falling back to basic keyword extraction.")

class KeywordExtractor:
    def __init__(self, config):
        self.config = config
        self.default_lang = config.get('Keywords', 'Language', fallback='ar')
        self.num_keywords = config.getint('Keywords', 'NumKeywords', fallback=5)
        # ✅ تم تعطيل التنزيل التلقائي لتجنب الأخطاء على السحابة
        # self._download_nltk_resources_if_needed() 
        self.stopwords_cache = {}

    def _download_nltk_resources_if_needed(self):
        """
        تم تعطيل هذه الدالة لتجنب مشاكل التنزيل في البيئات المقيدة.
        يجب تنزيل موارد NLTK باستخدام ملف nltk.txt في Streamlit Cloud.
        """
        pass # لا تفعل شيئًا

    def _get_stopwords(self, language_code):
        if not NLTK_AVAILABLE: return set() # إذا لم تكن NLTK متاحة، لا توجد كلمات متوقفة
        
        if language_code in self.stopwords_cache: return self.stopwords_cache[language_code]
        
        lang_map = {'ar': 'arabic', 'en': 'english', 'fr': 'french', 'es': 'spanish'}
        nltk_lang = lang_map.get(language_code.lower())
        
        if nltk_lang:
            try:
                sw = set(stopwords.words(nltk_lang))
                self.stopwords_cache[language_code] = sw
                return sw
            except Exception as e:
                logger.warning(f"Could not load NLTK stopwords for '{nltk_lang}': {e}. This might happen if the resource is not downloaded.")
        else:
            logger.warning(f"Unsupported language '{language_code}' for NLTK stopwords.")
        
        self.stopwords_cache[language_code] = set()
        return set()

    def _basic_fallback_extraction(self, text_content):
        """
        طريقة استخراج بديلة وبسيطة لا تعتمد على أي مكتبات خارجية.
        """
        logger.info("Using basic fallback method for keyword extraction.")
        text_alpha_space = re.sub(r'[^\w\s]', '', text_content, flags=re.UNICODE)
        text_alpha_space = re.sub(r'\d+', ' ', text_alpha_space)
        words = text_alpha_space.lower().split()
        
        long_words = [word for word in words if len(word) > 4]
        
        # استخدام Counter للحصول على الأكثر شيوعًا حتى في الطريقة البديلة
        if not long_words: return []
        word_counts = Counter(long_words)
        most_common = [word for word, count in word_counts.most_common(self.num_keywords)]
        return most_common

    def extract_keywords(self, text_content, language=None):
        if not text_content or not isinstance(text_content, str): return []
        
        lang_to_use = language or self.default_lang
        logger.info(f"Attempting to extract keywords (lang: {lang_to_use}). Snippet: '{text_content[:80].replace(chr(10),' ')}...'")

        # ✅ --- هذا هو التعديل الرئيسي ---
        # نحاول استخدام الطريقة الدقيقة، وإذا فشلت لأي سبب، نستخدم الطريقة البديلة
        if NLTK_AVAILABLE:
            try:
                text_alpha_space = re.sub(r'[^\w\s]', '', text_content, flags=re.UNICODE)
                text_alpha_space = re.sub(r'\d+', ' ', text_alpha_space)
                normalized_text = text_alpha_space.lower() if lang_to_use != 'ar' else text_alpha_space
                
                nltk_lang_for_tokenize = {'ar': 'arabic', 'en': 'english'}.get(lang_to_use, 'english')
                tokens = word_tokenize(normalized_text, language=nltk_lang_for_tokenize)
                
                current_stopwords = self._get_stopwords(lang_to_use)
                min_word_len = 3 if lang_to_use == 'ar' else 2
                filtered_tokens = [word for word in tokens if word.isalpha() and len(word) >= min_word_len and word not in current_stopwords]
                
                if not filtered_tokens: 
                    logger.warning("No valid tokens after NLTK filtering. Trying fallback.")
                    return self._basic_fallback_extraction(text_content)
                
                word_counts = Counter(filtered_tokens)
                most_common_keywords = [word for word, count in word_counts.most_common(self.num_keywords)]
                logger.info(f"Keywords extracted successfully with NLTK ({lang_to_use}): {most_common_keywords}")
                return most_common_keywords
            
            except Exception as e:
                logger.error(f"NLTK processing failed: {e}. Falling back to basic extraction.")
                # إذا حدث أي خطأ هنا (مثل عدم وجود بيانات punkt)، ننتقل للطريقة البديلة
                return self._basic_fallback_extraction(text_content)
        else:
            # إذا لم تكن NLTK مثبتة من الأساس
            return self._basic_fallback_extraction(text_content)
