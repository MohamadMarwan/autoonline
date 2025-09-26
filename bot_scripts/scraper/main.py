import sys
import os
import time
import configparser
import logging
import argparse
import json # <-- استيراد JSON

# --- الحل الديناميكي لمسارات الاستيراد ---
try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except NameError:
    pass
# ---------------------------------------------

from bs4 import BeautifulSoup
from utils.logger_config import setup_logger
from core.sitemap_fetcher import fetch_urls_from_sitemap
from core.article_scraper import ArticleScraper
from core.image_processor import ImageProcessor
from core.content_formatter import ContentFormatter
from core.permalink_generator import PermalinkGenerator
from core.keyword_extractor import KeywordExtractor
from core.blogger_client import BloggerClient

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.ini')
config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
main_logger = None 

def load_app_config():
    global main_logger
    if not config.read(CONFIG_FILE, encoding='utf-8'):
        print(f"CRITICAL: Config file {CONFIG_FILE} not found.")
        raise FileNotFoundError(f"{CONFIG_FILE} not found.")
    log_fp = config.get('Paths', 'LogFile', fallback='bot_activity.log')
    log_lvl_str = config.get('Logging', 'Level', fallback='INFO').upper()
    log_lvl = getattr(logging, log_lvl_str, logging.INFO)
    main_logger = setup_logger("BotRunner", log_file=log_fp, level=log_lvl)
    main_logger.info(f"Config loaded from {CONFIG_FILE}")

def load_published_source_urls():
    fp = config.get('Paths', 'PublishedUrlsFile')
    try:
        with open(fp, 'r', encoding='utf-8') as f: return set(l.strip() for l in f if l.strip())
    except FileNotFoundError: 
        main_logger.warning(f"File '{fp}' not found. A new one will be created.")
        return set()
    except Exception as e: 
        main_logger.error(f"Error loading URLs from '{fp}': {e}")
        return set()

def save_published_source_url(url, published_set):
    fp = config.get('Paths', 'PublishedUrlsFile')
    published_set.add(url)
    try:
        with open(fp, 'a', encoding='utf-8') as f: f.write(url + "\n")
        main_logger.debug(f"Saved published URL to file: {url}")
    except IOError as e: main_logger.error(f"Failed to save URL {url} to '{fp}': {e}")

# ✅ 1. تمت إضافة وسيط "rules_file_path" هنا
def run_bot_cycle(creds_path, article_urls_to_process=None, custom_labels=None, rules_file_path=None):
    main_logger.info("===== BOT CYCLE STARTED =====")
    published_urls = load_published_source_urls()
    main_logger.info(f"Loaded {len(published_urls)} previously published URLs.")
    
    # ✅ 2. تمت إضافة هذا الجزء لقراءة ملف القواعد
    publishing_rules = {}
    if rules_file_path and os.path.exists(rules_file_path):
        try:
            with open(rules_file_path, 'r', encoding='utf-8') as f:
                publishing_rules = json.load(f)
            main_logger.info(f"Successfully loaded publishing rules from {rules_file_path}")
        except Exception as e:
            main_logger.error(f"Could not load publishing rules file: {e}")

    if not creds_path:
        main_logger.critical("Credential path not provided. Aborting.")
        return

    try:
        article_tool = ArticleScraper(config)
        image_tool = ImageProcessor(config) 
        content_formatter = ContentFormatter(config, config_filepath=CONFIG_FILE)
        permalink_suggester = PermalinkGenerator(config)
        keyword_tool = KeywordExtractor(config)
        blogger_bot_client = BloggerClient(config, creds_path=creds_path) 
        if not blogger_bot_client.service: 
            main_logger.critical("Blogger client initialization failed.")
            return
    except Exception as e: 
        main_logger.critical(f"Tool initialization error: {e}", exc_info=True)
        return

    final_urls_to_process = []
    is_specific_mode = bool(article_urls_to_process)
    if is_specific_mode:
        main_logger.info(f"Processing {len(article_urls_to_process)} specific URLs provided.")
        final_urls_to_process = [u for u in article_urls_to_process if u not in published_urls]
    else:
        main_logger.info("No specific URLs provided. Fetching from sitemap...")
        sitemap_url_conf = config.get('Scraping', 'SitemapURL', fallback=None)
        if not sitemap_url_conf: main_logger.error("SitemapURL is not configured."); return
        all_potential_urls = fetch_urls_from_sitemap(sitemap_url_conf, config.get('DEFAULT', 'UserAgent'))
        final_urls_to_process = [u for u in all_potential_urls if u not in published_urls]

    if not final_urls_to_process: 
        main_logger.info("No new articles to process."); return

    published_count = 0
    max_run = len(final_urls_to_process) if is_specific_mode else config.getint('BotSettings', 'MaxArticlesPerRun', fallback=5)
    post_delay = config.getint('BotSettings', 'DelayBetweenPostsSec', fallback=30)

    for i, src_url in enumerate(final_urls_to_process):
        if published_count >= max_run: 
            main_logger.info(f"Reached MaxArticlesPerRun limit ({max_run}). Stopping.")
            break
        
        main_logger.info(f"--- Processing Article ({i+1}/{len(final_urls_to_process)}): {src_url} ---")
        scraped = article_tool.scrape_article_details(src_url)
        if not scraped: main_logger.warning(f"Scraping failed for {src_url}. Skipping."); continue
        orig_title = scraped.get("title", "")
        if not orig_title.strip(): main_logger.warning(f"Empty title for {src_url}. Skipping."); continue
        raw_html = scraped.get("raw_html_content", "")
        if not raw_html.strip(): main_logger.warning(f"Inadequate content for {src_url}. Skipping."); continue

        img_map = {}; main_hosted_img = None; img_ext = config.get('ImageProcessing','OutputFormat',fallback='jpg').lower()
        title_sugg_dict = permalink_suggester.generate_english_title_suggestion(orig_title, source_lang_hint=config.get('Keywords','Language',fallback='ar'))
        eng_title_internal = title_sugg_dict.get('suggested_title',''); slug_fname_base = title_sugg_dict.get('slug_base','image')

        if scraped.get("main_feature_image_original_url"):
            img_proc_url = scraped["main_feature_image_original_url"]
            proc_bytes = image_tool.process_image_with_logo(img_proc_url)
            if proc_bytes:
                safe_slug = "".join(c if c.isalnum() else "_" for c in slug_fname_base[:30]).strip('_')
                fname = f"main_{safe_slug}_{int(time.time())}.{img_ext}"
                h_url = image_tool.upload_image_to_hosting(proc_bytes, fname)
                if h_url: img_map[img_proc_url] = h_url; main_hosted_img = h_url; main_logger.info(f"Main image hosted: {h_url}")
                else: main_logger.warning(f"Main image UPLOAD FAILED for: {img_proc_url}")
            else: main_logger.warning(f"Main image PROCESSING FAILED for: {img_proc_url}")
        
        for img_data in scraped.get("images_in_content_details",[]):
            orig_tag_src = img_data["original_tag_src"]; full_proc_url = img_data["full_url"]
            if orig_tag_src not in img_map:
                if full_proc_url == scraped.get("main_feature_image_original_url") and main_hosted_img:
                    img_map[orig_tag_src] = main_hosted_img; continue
                proc_bytes = image_tool.process_image_with_logo(full_proc_url)
                if proc_bytes:
                    safe_slug="".join(c if c.isalnum() else "_" for c in slug_fname_base[:20]).strip('_')
                    fname=f"content_{safe_slug}_{int(time.time())}_{len(img_map)}.{img_ext}"
                    h_url=image_tool.upload_image_to_hosting(proc_bytes,fname)
                    if h_url:img_map[orig_tag_src]=h_url
                    else:main_logger.warning(f"Content image UPLOAD FAILED: {orig_tag_src}")
                else:main_logger.warning(f"Content image PROCESSING FAILED: {orig_tag_src}")

        # ✅ 3. تم تمرير القواعد التي تم تحميلها إلى الدالة
        final_html = content_formatter.format_for_blogger(
            raw_html_content=raw_html,
            processed_images_map=img_map,
            main_hosted_image_url_for_prepend=main_hosted_img,
            article_title_for_alt=orig_title,
            dynamic_rules=publishing_rules # <-- الإضافة هنا
        )
        
        if eng_title_internal and eng_title_internal.strip():
            final_title = f"{orig_title} ({eng_title_internal})"
        else: final_title = orig_title

        final_lbls = []
        if custom_labels:
            main_logger.info(f"Using custom labels provided by user: {custom_labels}")
            final_lbls = custom_labels
        else:
            main_logger.info("No custom labels provided, extracting automatically...")
            txt_src_kw = raw_html
            kw_txt = BeautifulSoup(txt_src_kw,'html.parser').get_text(separator=' ',strip=True)
            labels = keyword_tool.extract_keywords(kw_txt)
            def_lbl_str = config.get('BloggerAPI','DefaultLabels',fallback=''); def_lbls = [l.strip() for l in def_lbl_str.split(',') if l.strip()]
            combo_lbls = def_lbls + labels; uniq_lbls = list(dict.fromkeys(combo_lbls))
            final_lbls = uniq_lbls[:config.getint('BloggerAPI','MaxLabelsPerPost',fallback=10)]

        main_logger.info(f"Publishing to Blogger. Title: '{final_title}', Labels: {final_lbls}")
        is_drft = config.getboolean('BloggerAPI','PostAsDraft',fallback=False)
        
        pub_url = blogger_bot_client.create_post(
            title=final_title, content_html=final_html, labels=final_lbls, is_draft=is_drft
        )

        if pub_url:
            main_logger.info(f"Successfully published '{src_url}' to Blogger: {pub_url}")
            if not is_specific_mode: save_published_source_url(src_url, published_urls)
            published_count += 1
            if not is_specific_mode and published_count < max_run and i < len(final_urls_to_process)-1:
                main_logger.info(f"Waiting {post_delay}s before next post...")
                time.sleep(post_delay)
        else: 
            main_logger.error(f"Failed to publish {src_url} to Blogger.")

    main_logger.info(f"Published {published_count} new articles in this cycle.")
    main_logger.info("===== BOT CYCLE FINISHED =====")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Blogger Auto Post Bot")
    parser.add_argument("--urls", type=str, nargs='+', help="List of specific article URLs to process.")
    parser.add_argument("--creds-path", type=str, required=True, help="Path to the Google credential directory.")
    parser.add_argument("--labels", type=str, nargs='*', help="List of custom labels to apply to the posts.")
    # ✅ 4. تمت إضافة الوسيط الجديد هنا ليتمكن السكربت من استقباله
    parser.add_argument("--rules-file", type=str, help="Path to the JSON file with publishing rules.")
    args = parser.parse_args()

    try:
        load_app_config()
        run_bot_cycle(
            creds_path=args.creds_path, 
            article_urls_to_process=args.urls,
            custom_labels=args.labels,
            rules_file_path=args.rules_file # <-- تمرير المسار هنا
        )
    except FileNotFoundError as e:
        print(f"CRITICAL - A required file was not found: {e}")
        if main_logger: main_logger.critical(f"A required file was not found: {e}", exc_info=True)
        exit(1)
    except Exception as e:
        error_msg = f"An unhandled critical error occurred: {e}"
        print(f"CRITICAL UNHANDLED ERROR: {e}")
        if main_logger: main_logger.critical(error_msg, exc_info=True)
        exit(1)