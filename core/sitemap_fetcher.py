# core/sitemap_fetcher.py
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote
import re
import time
import cloudscraper
from datetime import datetime, timezone
from utils.logger_config import setup_logger

logger = setup_logger(__name__)

def is_potential_article_url(url_string, base_domain):
    try:
        decoded_url = unquote(url_string)
        parsed_url = urlparse(decoded_url)
        if parsed_url.scheme not in ['http', 'https']: return False
        if parsed_url.netloc != base_domain: return False
        path = parsed_url.path.lower(); query = parsed_url.query.lower()
        excluded_path_segments = ['/category/', '/tag/', '/tags/', '/author/', '/user/', '/search/', '/portfolio', '/gallery','/wp-admin/', '/wp-content/', '/wp-includes/', '/admin/', '/login', '/register', '/profile','/feed/', '/rss/', '/atom/', '/comments/feed/', '/trackback/','/sitemap','/page/','/cart/', '/checkout/', '/my-account/', '/wishlist/', '/shop/', '/product/','/privacy-policy', '/terms-of-service', '/contact', '/about', '/faq', '/documentation','/amp/']
        if any(segment in path for segment in excluded_path_segments): return False
        excluded_filename_patterns = ['sitemap.xml', 'sitemap_index.xml', 'robots.txt', 'ads.txt', 'wp-cron.php', 'xmlrpc.php', 'favicon.ico']
        path_filename = path.split('/')[-1]
        if any(pattern == path_filename for pattern in excluded_filename_patterns): return False
        excluded_extensions = ['.xml', '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx','.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico','.css', '.js', '.json', '.zip', '.rar', '.tar.gz', '.exe', '.dmg', '.pkg','.mp3', '.wav', '.ogg', '.mp4', '.avi', '.mov', '.wmv', '.flv','.php', '.asp', '.aspx', '.cgi', '.pl']
        if path and any(path.endswith(ext) for ext in excluded_extensions): return False
        excluded_query_params_exact = ['replytocom', 'add-to-cart', 'preview', 'format=pdf', 'action=edit', 'action=delete','ical', 'subscribe', 'unsubscribe', 'share', 'print', 'download', 'amp', 'feed']
        excluded_query_params_contains = ['utm_', 'gclid', 'fbclid', 'msclkid','attachment_id=', 'paged=', 'page_id=','s=', 'search=', 'query=']
        query_parts = query.split('&')
        for q_part in query_parts:
            param_name = q_part.split('=')[0]
            if param_name in excluded_query_params_exact: return False
            for excluded_contain in excluded_query_params_contains:
                if excluded_contain in param_name: return False
        if (not path or path == '/') and not query: return False
        return True
    except Exception as e: logger.error(f"Error filtering URL {url_string}: {e}", exc_info=True); return False

def fetch_urls_from_sitemap(sitemap_url, user_agent="SitemapFetcherBot/1.0 (Default)", sitemap_fetch_delay_sec=1):
    urls_with_dates = []; sitemaps_to_process = [sitemap_url]; processed_sitemap_urls = set()
    try: base_domain = urlparse(sitemap_url).netloc
    except Exception: logger.error(f"Invalid sitemap URL: {sitemap_url}"); return []
    if not base_domain: logger.error(f"Could not get base domain from: {sitemap_url}"); return []
    
    scraper = cloudscraper.create_scraper(browser={'custom': user_agent}, delay=5)
    request_timeout = 45 
    headers_for_scraper = {'Accept': 'application/xml,text/xml;q=0.9', 'Accept-Language': 'en-US,en;q=0.8,ar;q=0.7', 'Accept-Encoding': 'gzip, deflate, br'}

    while sitemaps_to_process:
        current_sitemap_file_url = sitemaps_to_process.pop(0)
        if current_sitemap_file_url in processed_sitemap_urls: continue
        logger.info(f"Fetching sitemap (cloudscraper): {current_sitemap_file_url}")
        try:
            response = scraper.get(current_sitemap_file_url, headers=headers_for_scraper, timeout=request_timeout, allow_redirects=True)
            if response.status_code == 403: logger.error(f"403 Forbidden for {current_sitemap_file_url} with cloudscraper."); processed_sitemap_urls.add(current_sitemap_file_url); continue 
            response.raise_for_status()
            xml_content = response.text
            if not xml_content: logger.warning(f"Empty content for {current_sitemap_file_url}"); processed_sitemap_urls.add(current_sitemap_file_url); continue
            try: root = ET.fromstring(xml_content)
            except ET.ParseError as e: logger.error(f"XML ParseError for {current_sitemap_file_url}: {e}. Content: {xml_content[:200]}"); processed_sitemap_urls.add(current_sitemap_file_url); continue
            namespace_match = re.match(r'({[^}]+})', root.tag); namespace = namespace_match.group(1) if namespace_match else ''
            sitemap_nodes = root.findall(f'{namespace}sitemap'); url_nodes = root.findall(f'{namespace}url')
            if sitemap_nodes:
                for s_node in sitemap_nodes:
                    loc_n = s_node.find(f'{namespace}loc')
                    if loc_n is not None and loc_n.text: s_url = loc_n.text.strip(); sitemaps_to_process.append(s_url)
            elif url_nodes:
                for u_node in url_nodes:
                    loc_n = u_node.find(f'{namespace}loc'); lastmod_n = u_node.find(f'{namespace}lastmod'); url_s = None
                    if loc_n is not None and loc_n.text: url_s = loc_n.text.strip()
                    if url_s and is_potential_article_url(url_s, base_domain):
                        lm_dt = datetime.min.replace(tzinfo=timezone.utc)
                        if lastmod_n is not None and lastmod_n.text:
                            try:
                                dt_s = lastmod_n.text.strip().replace('Z', '+00:00')
                                common_fmts = ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d"]
                                parsed_ok = False
                                for fmt_str in common_fmts:
                                    try: lm_dt = datetime.strptime(dt_s, fmt_str); parsed_ok = True; break
                                    except ValueError: continue
                                if not parsed_ok: lm_dt = datetime.fromisoformat(dt_s)
                                if lm_dt.tzinfo is None: lm_dt = lm_dt.replace(tzinfo=timezone.utc)
                            except: pass # Keep default lm_dt
                        urls_with_dates.append((lm_dt, url_s))
            else: logger.warning(f"Sitemap {current_sitemap_file_url} has no <sitemap> or <url> tags.")
        except Exception as e: logger.error(f"Error processing {current_sitemap_file_url}: {e}", exc_info=True)
        processed_sitemap_urls.add(current_sitemap_file_url)
        if sitemaps_to_process: time.sleep(sitemap_fetch_delay_sec)
    if not urls_with_dates: return []
    urls_with_dates.sort(key=lambda item: item[0], reverse=True)
    sorted_urls = [url for date, url in urls_with_dates]
    logger.info(f"Fetched {len(sorted_urls)} URLs, sorted by lastmod.")
    return sorted_urls