# core/keyword_extractor.py
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from collections import Counter
import re
from utils.logger_config import setup_logger

logger = setup_logger(__name__)

class KeywordExtractor:
    def __init__(self, config):
        self.config = config
        self.default_lang = config.get('Keywords', 'Language', fallback='ar')
        self.num_keywords = config.getint('Keywords', 'NumKeywords', fallback=5)
        self._download_nltk_resources_if_needed()
        self.stopwords_cache = {}

    def _download_nltk_resources_if_needed(self):
        resources = [('corpora/stopwords', 'stopwords'), ('tokenizers/punkt', 'punkt')]
        for resource_path, resource_name in resources:
            try: nltk.data.find(resource_path); logger.debug(f"NLTK '{resource_name}' available.")
            except nltk.downloader.DownloadError:
                logger.info(f"NLTK '{resource_name}' not found. Downloading...")
                try: nltk.download(resource_name, quiet=True); logger.info(f"NLTK '{resource_name}' downloaded.")
                except Exception as e: logger.error(f"Failed to download NLTK '{resource_name}': {e}.")
            except AttributeError: logger.error("NLTK downloader not found.")

    def _get_stopwords(self, language_code):
        if language_code in self.stopwords_cache: return self.stopwords_cache[language_code]
        lang_map = {'ar': 'arabic', 'en': 'english', 'fr': 'french', 'es': 'spanish'}
        nltk_lang = lang_map.get(language_code.lower())
        if nltk_lang:
            try: sw = set(stopwords.words(nltk_lang)); self.stopwords_cache[language_code] = sw; return sw
            except Exception as e: logger.warning(f"Could not load NLTK stopwords for '{nltk_lang}': {e}.")
        else: logger.warning(f"Unsupported language '{language_code}' for NLTK stopwords.")
        self.stopwords_cache[language_code] = set(); return set()

    def extract_keywords(self, text_content, language=None):
        if not text_content or not isinstance(text_content, str): return []
        lang_to_use = language or self.default_lang
        logger.info(f"Extracting keywords (lang: {lang_to_use}, target: {self.num_keywords}). Snippet: '{text_content[:100].replace(chr(10),' ')}...'")
        text_alpha_space = re.sub(r'[^\w\s]', '', text_content, flags=re.UNICODE)
        text_alpha_space = re.sub(r'\d+', ' ', text_alpha_space, flags=re.UNICODE)
        text_alpha_space = re.sub(r'_+', ' ', text_alpha_space, flags=re.UNICODE)
        normalized_text = text_alpha_space.lower() if lang_to_use != 'ar' else text_alpha_space
        try:
            nltk_lang_for_tokenize = {'ar': 'arabic', 'en': 'english'}.get(lang_to_use, 'english')
            tokens = word_tokenize(normalized_text, language=nltk_lang_for_tokenize)
        except LookupError as e:
            logger.error(f"NLTK LookupError for word_tokenize ('{lang_to_use}'): {e}. Fallback tokenization.")
            tokens = normalized_text.split()
        except Exception as e: logger.error(f"NLTK word_tokenize failed ('{lang_to_use}'): {e}."); tokens = normalized_text.split()
        current_stopwords = self._get_stopwords(lang_to_use)
        min_word_len = 3 if lang_to_use == 'ar' else 2
        filtered_tokens = [word for word in tokens if word.isalpha() and len(word) >= min_word_len and word not in current_stopwords]
        if not filtered_tokens: logger.warning("No valid tokens after filtering."); return []
        word_counts = Counter(filtered_tokens)
        most_common_keywords = [word for word, count in word_counts.most_common(self.num_keywords)]
        logger.info(f"Keywords extracted ({lang_to_use}): {most_common_keywords}")
        return most_common_keywords