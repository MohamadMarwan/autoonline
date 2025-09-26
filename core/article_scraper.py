# core/article_scraper.py
import requests
from bs4 import BeautifulSoup, NavigableString, Tag 
from urllib.parse import urljoin, urlparse
import cloudscraper
import re
import json
from utils.logger_config import setup_logger

logger = setup_logger(__name__)

class ArticleScraper:
    def __init__(self, config):
        self.config = config
        self.default_user_agent = config.get('DEFAULT', 'UserAgent', fallback='ArticleScraperBot/1.0')
        self.request_timeout = config.getint('Scraping', 'RequestTimeout', fallback=35)
        self.title_selectors = [s.strip() for s in config.get('Scraping', 'TitleSelector', fallback='h1').split(',')]
        self.content_selectors = [s.strip() for s in config.get('Scraping', 'ContentSelector', fallback='article').split(',')]
        self.content_exclude_selectors = [s.strip() for s in config.get('Scraping', 'ContentExcludeSelectors', fallback='').split(',') if s.strip()]
        try:
            self.scraper = cloudscraper.create_scraper(browser={'custom': self.default_user_agent}, delay=5)
            logger.info(f"ArticleScraper initialized with CloudScraper UA: {self.default_user_agent}")
        except Exception as e:
            logger.error(f"Failed to init cloudscraper: {e}. Fallback to requests.")
            self.scraper = requests.Session(); self.scraper.headers.update({'User-Agent': self.default_user_agent})

    def _select_first_found(self, soup, selectors, purpose="element", article_url_for_log=""):
        for idx, selector in enumerate(selectors):
            try:
                element = soup.select_one(selector)
                if element: logger.info(f"SUCCESS: Found {purpose} for '{article_url_for_log}' using selector #{idx+1}: '{selector}'."); return element
                else: logger.debug(f"ATTEMPT: Selector #{idx+1} '{selector}' for {purpose} did NOT match on '{article_url_for_log}'.")
            except Exception as e: logger.error(f"Error with selector #{idx+1} '{selector}' for {purpose} on '{article_url_for_log}': {e}"); continue
        logger.warning(f"FAILURE: Could not find {purpose} for '{article_url_for_log}' using: {selectors}")
        return None

    def _remove_site_specific_junk(self, content_element, article_url):
        if not content_element: return content_element
        
        site_key_to_clean = None
        # تحديد الموقع بناءً على الرابط لتطبيق القواعد الصحيحة
        if "b2b-sy.com" in article_url: site_key_to_clean = "b2b-sy.com"
        elif "ajel.sa" in article_url: site_key_to_clean = "ajel.sa"
        # أضف المزيد من شروط elif هنا لمواقع أخرى

        if not site_key_to_clean: return content_element # لا توجد قواعد تنظيف معرفة لهذا الموقع

        logger.debug(f"Applying specific text cleaning rules for {site_key_to_clean} on {article_url}")
        
        # تعريف القواعد داخل الدالة أو تحميلها من ملف تكوين أكثر تقدمًا إذا لزم الأمر
        site_rules = {
            "b2b-sy.com": {
                "decompose_parent_if_text_matches": [
                    (re.compile(r"^\s*خاص\s+B2B-SY\s*$", re.I | re.M), 20), 
                    (re.compile(r"^\s*(الاثنين|الثلاثاء|الاربعاء|الخميس|الجمعة|السبت|الأحد)\s+\d{1,2}/\d{1,2}/\d{4}\s*$", re.M), 10)
                ],
                "remove_text_inline": [
                    re.compile(r"خاص\s+B2B-SY", re.I),
                    re.compile(r"(?:الاثنين|الثلاثاء|الاربعاء|الخميس|الجمعة|السبت|الأحد)\s+\d{1,2}/\d{1,2}/\d{4}", re.M)
                ]
            },
            "ajel.sa": {
                "decompose_parent_if_text_matches": [
                    (re.compile(r"^\s*فريق\s+التحرير\s*$", re.I | re.M), 5), # تطابق "فريق التحرير" فقط
                    (re.compile(r"^\s*تم\s+النشر\s+في\s*:\s*\d{1,2}\s+\w+\s+\d{4}.*?(?:صباحاً|مساءً|م|ص|AM|PM)\s*$", re.I | re.S), 60),
                    (re.compile(r"^\s*اقرأ أيضا(?:ً)?:.*$", re.I | re.S), 0), 
                    (re.compile(r"^\s*لمتابعة\s+أخبار\s+عاجل\s+عبر\s+تطبيق\s+نبض\s*$", re.I | re.M), 0),
                    (re.compile(r"^\s*اضغط\s+هنا\s*$", re.I | re.M), 0),
                    (re.compile(r"^\s*ضيوف\s+الرحمن.*أهم\s+الأخبار\s*$", re.I | re.M), 30) # تعديل التساهل في الطول
                ],
                "remove_text_inline": [ # هذه ستزيل النص حتى لو كان جزءًا من فقرة أكبر
                    re.compile(r"فريق\s+التحرير\s+تم\s+النشر\s+في\s*:\s*\d{1,2}\s+\w+\s+\d{4}[^<]*?(?:صباحاً|مساءً|م|ص|AM|PM)", re.I | re.S),
                    re.compile(r"فريق\s+التحرير", re.I), # إزالة "فريق التحرير" بمفردها إذا ظهرت
                    re.compile(r"ضيوف\s+الرحمن\s+المفتي\s+العام\s+للمملكة\s+أخبار\s+السعودية\s+أهم\s+الآخبار\s+الحج\s+بدون\s+تصريح\s+أهم\s+الأخبار", re.I),
                    re.compile(r"اقرأ أيضا(?:ً)?:", re.I), # إزالة بداية السطر فقط
                    re.compile(r"لمتابعة\s+أخبار\s+عاجل\s+عبر\s+تطبيق\s+نبض", re.I) # إزالة السطر فقط
                ]
            }
        }

        rules_for_current_site = site_rules.get(site_key_to_clean, {})
        patterns_to_decompose_parent = rules_for_current_site.get("decompose_parent_if_text_matches", [])
        patterns_to_remove_inline = rules_for_current_site.get("remove_text_inline", [])

        # المرحلة 1: محاولة إزالة الوسوم الأصل
        if patterns_to_decompose_parent:
            for tag in list(content_element.find_all(['p', 'div', 'span', 'font', 'time', 'td', 'li', 'dt', 'dd', 'header', 'footer', 'aside', 'section', 'article'])):
                if not tag.parent: continue
                tag_text_stripped = tag.get_text(strip=True)
                if not tag_text_stripped: continue
                for pattern, length_tol in patterns_to_decompose_parent:
                    core_pattern_len = len(re.sub(r'[\s\W_]+', '', pattern.pattern)) # Approximate length of meaningful chars in pattern
                    if pattern.fullmatch(tag_text_stripped) or \
                       (length_tol >= 0 and pattern.search(tag_text_stripped) and \
                        len(tag_text_stripped) < (core_pattern_len + length_tol + 30)): # Heuristic length check
                        logger.debug(f"Decomposing tag <{tag.name}> (text: '{tag_text_stripped[:70]}...') matching pattern '{pattern.pattern}' for {site_key_to_clean}.")
                        tag.decompose()
                        break 
                else: # إذا لم يتم إزالة الوسم في الحلقة الداخلية، استمر للحلقة الخارجية
                    continue
                break # إذا تم إزالة الوسم، لا داعي للتحقق من بقية الأنماط عليه، ابدأ من جديد find_all

        # المرحلة 2: إزالة النصوص المضمنة من العقد النصية المتبقية
        if patterns_to_remove_inline:
            for text_node in list(content_element.find_all(string=True)):
                if not text_node.parent or not isinstance(text_node, NavigableString) or text_node.parent.name in ['script','style','textarea','pre','code','title']:
                    continue
                original_text = str(text_node)
                modified_text = original_text
                for pattern in patterns_to_remove_inline:
                    modified_text = pattern.sub("", modified_text)
                
                # إزالة الأسطر الفارغة الناتجة
                lines = modified_text.splitlines()
                non_empty_lines = [line for line in lines if line.strip()]
                modified_text = "\n".join(non_empty_lines).strip() # .strip() في النهاية لإزالة أي مسافات بادئة/لاحقة

                if modified_text != original_text.strip(): # قارن مع الأصلي بعد strip أيضًا
                    if not modified_text: # إذا أصبح النص فارغًا تمامًا
                        parent = text_node.parent
                        if parent and parent.name in ['p','div','span','strong','em','b','i','font','time','li','dt','dd'] and \
                           not parent.get_text(strip=True).replace(original_text,"").strip() and \
                           not parent.find(['img','br','hr','iframe','table','ul','ol','dl']) and \
                           parent.name != 'body':
                            logger.debug(f"Decomposing parent <{parent.name}> as it became empty after inline text removal.")
                            parent.decompose()
                        elif parent and parent.name != 'body':
                            logger.debug(f"Extracting empty NavigableString node (original: '{original_text[:50]}...').")
                            text_node.extract()
                    else:
                        logger.debug(f"Cleaned text node (inline removal): '{original_text[:50]}...' -> '{modified_text[:50]}...'")
                        text_node.replace_with(modified_text)
        return content_element

    def scrape_article_details(self, article_url):
        try:
            is_cs = isinstance(self.scraper, cloudscraper.CloudScraper)
            logger.info(f"Scraping {article_url} (via {'cloudscraper' if is_cs else 'requests'})")
            response = self.scraper.get(article_url, timeout=self.request_timeout)
            logger.debug(f"Resp for {article_url}: {response.status_code}, CT {response.headers.get('Content-Type')}")
            if response.status_code == 403: logger.error(f"403 Forbidden for {article_url}."); return None
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            title_el = self._select_first_found(soup, self.title_selectors, "title", article_url)
            title = title_el.get_text(strip=True) if title_el else ""
            if not title.strip():
                logger.warning(f"Title empty for {article_url} via selectors. Fallbacks...")
                og_title = soup.find('meta', property='og:title'); json_ld_title = None
                for script_tag in soup.find_all('script',type='application/ld+json'):
                    try:
                        if script_tag.string: data = json.loads(script_tag.string); data = data[0] if isinstance(data, list) else data
                        if isinstance(data, dict) and data.get('@type') in ['NewsArticle','Article','BlogPosting'] and data.get('headline'): json_ld_title = data['headline']; break
                    except: continue
                if json_ld_title: title = json_ld_title.strip(); logger.info(f"Using JSON-LD title: '{title}'")
                elif og_title and og_title.get('content'): title = og_title['content'].strip(); logger.info(f"Using OG title: '{title}'")
                else: logger.error(f"No title found (selectors/JSON-LD/OG) for {article_url}. Skipping."); return None
            
            content_container = self._select_first_found(soup, self.content_selectors, "content container", article_url)
            raw_html = ""; images_in_content = []
            if content_container:
                self._remove_site_specific_junk(content_container, article_url) # <--- تطبيق التنظيف
                if self.content_exclude_selectors: # تطبيق التنظيف العام
                    for ex_sel in self.content_exclude_selectors:
                        for unwanted in content_container.select(ex_sel): unwanted.decompose()
                for img_tag in content_container.find_all('img'):
                    src = img_tag.get('src') or img_tag.get('data-src'); alt = img_tag.get('alt', title)
                    if src:
                        full_url = urljoin(article_url, urlparse(src)._replace(query='').geturl())
                        if full_url.startswith('http') and not full_url.startswith('data:image'):
                            images_in_content.append({"original_tag_src": src, "full_url": full_url, "alt_text": alt})
                raw_html = str(content_container)
            else: raw_html = f"<p><i>[Content for '{title}' could not be extracted. Source: {article_url}]</i></p>"

            main_img_url = None
            for script_tag in soup.find_all('script', type='application/ld+json'):
                try:
                    if script_tag.string: data = json.loads(script_tag.string); data = data[0] if isinstance(data,list) else data
                    if isinstance(data,dict) and data.get('@type') in ['NewsArticle','Article','BlogPosting']:
                        img_obj = data.get('image'); img_obj = img_obj[0] if isinstance(img_obj,list) and img_obj else img_obj
                        if isinstance(img_obj,dict) and img_obj.get('url'): main_img_url = urljoin(article_url, img_obj['url'])
                        elif isinstance(img_obj,str) and img_obj.strip(): main_img_url = urljoin(article_url, img_obj.strip())
                        if main_img_url: logger.info(f"Found main image via JSON-LD: {main_img_url}"); break
                except: continue
            if not main_img_url: og_img = soup.find('meta', property='og:image')
            if not main_img_url and og_img and og_img.get('content'): og_c = og_img['content'].strip(); main_img_url=urljoin(article_url,og_c) if og_c else None; logger.info(f"Found OG image: {main_img_url}")
            if not main_img_url: tw_img = soup.find('meta', attrs={'name':['twitter:image','twitter:image:src']})
            if not main_img_url and tw_img and tw_img.get('content'): tw_c = tw_img['content'].strip(); main_img_url=urljoin(article_url,tw_c) if tw_c else None; logger.info(f"Found Twitter image: {main_img_url}")
            if not main_img_url and images_in_content and images_in_content[0].get('full_url'): main_img_url = images_in_content[0]['full_url']; logger.info(f"Using first content image as main: {main_img_url}")
            if not main_img_url: logger.warning(f"No main feature image determined for {article_url}")
            
            return {"source_url": article_url, "title": title, "raw_html_content": raw_html, "main_feature_image_original_url": main_img_url, "images_in_content_details": images_in_content}
        except Exception as e: logger.error(f"Major error in scrape_article_details for {article_url}: {e}", exc_info=True); return None