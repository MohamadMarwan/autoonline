# bot_scripts/cleaner/clean_posts.py

import os
import re
import time
import logging
import argparse
import sys
import json  # <-- ✅ استيراد مكتبة JSON
from bs4 import BeautifulSoup, NavigableString
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- الإعدادات العامة ---
SCOPES = ['https://www.googleapis.com/auth/blogger']
LOG_FILE = 'edited_posts.log'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

# ✅ تم حذف CUSTOM_REMOVE_LIST من هنا. سيتم الآن قراءتها من ملف.

def get_blogger_service(creds_path):
    # (هذه الدالة تبقى كما هي)
    creds = None; token_file = os.path.join(creds_path, 'token.json'); secret_file = os.path.join(creds_path, 'client_secret.json')
    if os.path.exists(token_file): creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
        else:
            if not os.path.exists(secret_file):
                print(f"خطأ فادح: ملف client_secret.json غير موجود في: {secret_file}"); sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as token: token.write(creds.to_json())
    return build('blogger', 'v3', credentials=creds)

# --- ✅ تم تعديل دوال التنظيف لتقبل القواعد كـ "وسيط" ---
def clean_title(title, rules):
    remove_symbols = rules.get('remove_symbols', [])
    title = re.sub(r'\s*\(.*?\)', '', title).strip()
    for symbol in remove_symbols:
        title = title.replace(symbol, '')
    return title

def extract_keywords(title):
    STOPWORDS = {"عاجل", "تفاصيل", "خبر", "اليوم", "كامل", "فيديو", "شاهد", "بالصور", "بالفيديو", "خاص"}
    words = re.findall(r'\w+', title)
    return ' '.join([w for w in words if w not in STOPWORDS and len(w) > 2][:6])

def add_smart_alt_to_images(soup, post_title):
    alt_text = extract_keywords(post_title)
    for img in soup.find_all("img"):
        if not img.get("alt"): img["alt"] = alt_text
        if not img.get("title"): img["title"] = alt_text
    return soup

def clean_content(content, post_title, rules):
    soup = BeautifulSoup(content, 'html.parser')
    soup = add_smart_alt_to_images(soup, post_title)
    
    # ... (حذف "تم النشر في" و وسوم time/component يبقى كما هو) ...
    for el in soup.find_all(string=re.compile(r'تم النشر في:')):
        if el.parent: el.extract()
    for time_tag in soup.find_all('time'): time_tag.decompose()
    for comp in soup.find_all('component'):
        if 'googletag.cmd.push' in str(comp): comp.decompose()

    # استخدام القواعد الديناميكية من الملف
    remove_symbols = rules.get('remove_symbols', [])
    replacements = rules.get('replacements', [])

    for text_node in soup.find_all(string=True):
        if isinstance(text_node, NavigableString):
            text_str = str(text_node)
            for rep in replacements:
                text_str = text_str.replace(rep.get('find', ''), rep.get('replace_with', ''))
            for symbol in remove_symbols:
                text_str = text_str.replace(symbol, '')
            if text_str != text_node:
                text_node.replace_with(text_str)
    return str(soup)

# ✅ تم تعديل الدالة الرئيسية لتقبل القواعد
def clean_post_titles_and_content(blog_id, creds_path, limit, rules):
    service = get_blogger_service(creds_path)
    print(f"🔄 جاري جلب آخر {limit} مقال من المدونة: {blog_id}...")
    
    try:
        posts = service.posts().list(blogId=blog_id, maxResults=limit, fetchBodies=True).execute()
    except Exception as e:
        print(f"❌ فشل في جلب المقالات: {e}"); sys.exit(1)

    for post in posts.get('items', []):
        original_title = post.get('title', '')
        original_content = post.get('content', '')
        if not original_title or not original_content: continue

        cleaned_title = clean_title(original_title, rules)
        cleaned_content = clean_content(original_content, original_title, rules)
        
        has_changed = (original_title != cleaned_title) or (original_content != cleaned_content)
        if has_changed:
            print(f"\n✏️ تعديل مقال: {original_title}")
            post_body = {'title': cleaned_title, 'content': cleaned_content}
            try:
                service.posts().patch(blogId=blog_id, postId=post['id'], body=post_body).execute()
                print(f"✅ تم تعديل: {original_title}")
                time.sleep(1.5)
            except Exception as e:
                print(f"❌ فشل في تحديث المقال '{original_title}': {e}")
        else:
            print(f"✅ بدون تعديل: {original_title}")

# ✅ --- تم تعديل نقطة انطلاق السكربت لقبول ملف القواعد ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Blogger Post Cleaner")
    parser.add_argument("--blog-id", type=str, required=True, help="ID of the Blogger blog.")
    parser.add_argument("--creds-path", type=str, required=True, help="Path to the credential directory.")
    parser.add_argument("--limit", type=int, default=12, help="Number of recent posts to clean.")
    # إضافة الوسيط الجديد
    parser.add_argument("--rules-file", type=str, required=True, help="Path to the JSON file with cleaning rules.")
    args = parser.parse_args()
    
    # تحميل القواعد من الملف الذي تم تمريره
    try:
        with open(args.rules_file, 'r', encoding='utf-8') as f:
            cleaning_rules = json.load(f)
    except Exception as e:
        print(f"❌ فشل في تحميل ملف القواعد من المسار: {args.rules_file}. الخطأ: {e}")
        sys.exit(1)
    
    print("--- بدء عملية تنظيف المقالات ---")
    # تمرير القواعد التي تم تحميلها إلى الدالة الرئيسية
    clean_post_titles_and_content(args.blog_id, args.creds_path, args.limit, cleaning_rules)
    print("--- انتهت عملية التنظيف ---")