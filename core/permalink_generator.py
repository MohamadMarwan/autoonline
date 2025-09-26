# core/permalink_generator.py
import re
import time 
from unidecode import unidecode
from deep_translator import GoogleTranslator
from utils.logger_config import setup_logger

logger = setup_logger(__name__)

class PermalinkGenerator:
    def __init__(self, config):
        self.config = config
        self.translate_slugs = self.config.getboolean('Translation', 'TranslateSlugs', fallback=True)
        self.translator_instance = None
        if self.translate_slugs:
            try:
                self.translator_instance = GoogleTranslator(source='auto', target='en')
                logger.info("DeepL Translator (Google engine) initialized for permalink/title suggestion.")
            except Exception as e:
                logger.error(f"Failed to initialize Translator: {e}. Translation will be skipped.")
                self.translate_slugs = False

    def generate_english_title_suggestion(self, original_title, source_lang_hint=None):
        if not original_title: return {'suggested_title': "Untitled Post", 'slug_base': "untitled-post"}
        english_suggested_title = original_title
        if self.translate_slugs and self.translator_instance:
            try:
                current_translator = GoogleTranslator(source=source_lang_hint if source_lang_hint else 'auto', target='en')
                logger.debug(f"Translating for title suggestion: '{original_title[:50]}...' (Hint: {source_lang_hint})")
                translated_text = current_translator.translate(text=original_title)
                if translated_text and isinstance(translated_text, str): english_suggested_title = translated_text
                else: logger.warning(f"Translation empty for '{original_title[:30]}...'. Using transliteration."); english_suggested_title = unidecode(original_title)
            except Exception as e: logger.warning(f"Translation for title '{original_title[:30]}...' failed: {e}. Using transliteration."); english_suggested_title = unidecode(original_title)
        elif not self.translate_slugs: logger.debug(f"Translation disabled. Using transliteration for title: '{original_title[:30]}...'"); english_suggested_title = unidecode(original_title)
        else: logger.debug(f"Translator not available. Using transliteration for title: '{original_title[:30]}...'"); english_suggested_title = unidecode(original_title)
        
        slug_base = english_suggested_title.lower(); slug_base = unidecode(slug_base)
        slug_base = re.sub(r'\s+', '-', slug_base); slug_base = re.sub(r'[^a-z0-9-]', '', slug_base)
        slug_base = re.sub(r'-+', '-', slug_base).strip('-')
        max_slug_length = self.config.getint('Permalink', 'MaxSlugLength', fallback=75)
        slug_base = slug_base[:max_slug_length].strip('-')
        if not slug_base:
            fallback_base = unidecode(original_title.lower()); fallback_base = re.sub(r'\s+', '-', fallback_base)
            fallback_base = re.sub(r'[^a-z0-9-]', '', fallback_base)[:30].strip('-')
            if fallback_base: slug_base = fallback_base
            else: slug_base = "post-" + str(int(time.time()))
        logger.info(f"Original: '{original_title[:30]}...' -> Suggested Title: '{english_suggested_title[:50]}...', Slug base: '{slug_base}'")
        return {'suggested_title': english_suggested_title, 'slug_base': slug_base}