# bot_scripts/extractor/links_extractor.py

import requests
import json
import os
import logging
from datetime import datetime
from tqdm import tqdm

def get_all_categories(blog_id, api_key):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts?key={api_key}&maxResults=500"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            posts_data = response.json()
            all_posts = posts_data.get("items", [])
            all_categories = set()
            for post in all_posts:
                if 'labels' in post:
                    all_categories.update(post['labels'])
            return sorted(list(all_categories))
        return []
    except Exception as e:
        logging.error(f"خطأ في جلب التصنيفات: {str(e)}")
        return []

# ✅ --- تم تعديل هذه الدالة بالكامل لتحسين الأداء ---
def get_blogger_posts(blog_id, api_key, category=None, max_results=None, latest_first=True):
    """
    يجلب المقالات من بلوجر بكفاءة عالية.
    - يستخدم orderBy=published لجلب الأحدث أولاً.
    - يرسل maxResults إلى API مباشرة.
    - لا يجلب جميع الصفحات إذا لم يكن ذلك ضروريًا.
    """
    all_posts = []
    
    # بناء عنوان URL الأساسي
    base_url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts?key={api_key}"
    
    # إضافة الفلاتر والترتيب
    if latest_first:
        base_url += "&orderBy=published"
    
    # إذا كان العدد المطلوب صغيرًا، لا نحتاج لصفحات متعددة
    # Blogger API يسمح بـ 500 كحد أقصى لكل طلب
    if max_results and max_results <= 500: 
        base_url += f"&maxResults={max_results}"
    else:
        base_url += "&maxResults=500"
        
    url = base_url
    
    try:
        # سنقوم بجلب جميع الصفحات فقط إذا لم نحدد عددًا معينًا (أو إذا كان العدد أكبر من 500)
        should_fetch_all_pages = not (max_results and max_results <= 500)

        with tqdm(desc="جلب المقالات", unit="مقال", disable=True) as pbar:
            while url:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    posts_data = response.json()
                    batch_posts = posts_data.get("items", [])
                    all_posts.extend(batch_posts)
                    pbar.update(len(batch_posts))
                    
                    # إذا كنا نحتاج فقط لعدد معين ووصلنا إليه، نتوقف
                    if max_results and len(all_posts) >= max_results:
                        break
                    
                    # التوقف عن جلب المزيد من الصفحات إذا لم يكن مطلوبًا
                    if not should_fetch_all_pages:
                        break
                    
                    next_page_token = posts_data.get('nextPageToken')
                    if next_page_token:
                        # نستخدم base_url لضمان الحفاظ على الفلاتر
                        # نزيل أي pageToken قديم ونضيف الجديد
                        url_without_token = base_url.split('&pageToken=')[0]
                        url = f"{url_without_token}&pageToken={next_page_token}"
                    else:
                        url = None
                else:
                    logging.error(f"فشل في جلب المقالات: {response.status_code}")
                    break
        
        # الفلترة حسب التصنيف تتم بعد الجلب لأن الـ API لا يدعمها مباشرة
        if category:
            all_posts = [p for p in all_posts if 'labels' in p and category in p['labels']]
        
        # الترتيب اليدوي ضروري فقط إذا قمنا بالفلترة (لأن الترتيب الأصلي قد يختل)
        if category and latest_first:
            all_posts.sort(key=lambda x: datetime.strptime(x['published'], '%Y-%m-%dT%H:%M:%S%z'), reverse=True)
        
        # قص القائمة النهائية للتأكد من العدد الصحيح بعد الفلترة
        if max_results and max_results > 0:
            all_posts = all_posts[:max_results]
        
        return all_posts
    except Exception as e:
        logging.error(f"حدث خطأ غير متوقع: {e}")
        return []

def save_links_to_file(category, links):
    if not os.path.exists('روابط'):
        os.makedirs('روابط')
    clean_category = ''.join(c for c in category if c.isalnum() or c in (' ', '_')).rstrip()
    filename = f"روابط/روابط_{clean_category}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("\n".join(links))
    logging.info(f"تم حفظ {len(links)} رابط في ملف {filename}")
    return filename

def extract_all_categories_links(blog_id, api_key, max_results=None):
    categories = get_all_categories(blog_id, api_key)
    if not categories: return "لم يتم العثور على أي تصنيفات."
    
    summary = []
    for category in categories:
        posts = get_blogger_posts(blog_id, api_key, category, max_results=max_results, latest_first=True)
        links = [p.get("url", "").replace("http://", "https://") for p in posts if p.get("url")]
        if links:
            filename = save_links_to_file(category, links)
            summary.append(f"قسم '{category}': تم حفظ {len(links)} رابط في '{filename}'")
    return "\n".join(summary) if summary else "لم يتم العثور على أي روابط."

def extract_specific_category_links(blog_id, api_key, category_name, max_results=None):
    posts = get_blogger_posts(blog_id, api_key, category_name, max_results=max_results, latest_first=True)
    if not posts: return f"لم يتم العثور على مقالات في قسم '{category_name}'."
    
    links = [p.get("url", "").replace("http://", "https://") for p in posts if p.get("url")]
    if links:
        filename = save_links_to_file(category_name, links)
        return (f"تم حفظ {len(links)} رابط في '{filename}'.\n\n" + "\n".join(links))
    return "لم يتم العثور على روابط صالحة."

def extract_latest_links(blog_id, api_key, max_results):
    # هذه الدالة الآن ستكون سريعة جدًا
    posts = get_blogger_posts(blog_id, api_key, latest_first=True, max_results=max_results)
    if not posts: return "لم يتم العثور على أي مقالات."
    
    links = [p.get("url", "").replace("http://", "https://") for p in posts if p.get("url")]
    if links:
        filename = save_links_to_file("أحدث_المقالات", links)
        return (f"تم حفظ {len(links)} رابط في '{filename}'.\n\n" + "\n".join(links))
    return "لم يتم العثور على روابط صالحة."