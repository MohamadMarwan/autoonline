# bot_scripts/video/video_creator.py

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
import telegram
from telegram.constants import ParseMode
import os
import asyncio
import random
from datetime import datetime
import cv2
import numpy as np
import ffmpeg
import requests
from bs4 import BeautifulSoup

# --- الإعدادات الثابتة للتصميم ---
FONT_FILE = "Amiri-Bold.ttf"
LOGO_FILE = "logo.png"
SOUND_FILE = "news_alert.mp3"
BACKGROUND_MUSIC_FILE = "background_music.mp3"
TEXT_COLOR = "#FFFFFF"
SHADOW_COLOR = "#000000"
TEXT_PLATE_COLOR = (0, 0, 0, 160)
SECONDS_PER_PAGE = 8
OUTRO_DURATION_SECONDS = 6.5
FPS = 30
WORDS_TO_REVEAL_PER_SECOND = 4
KEN_BURNS_ZOOM_FACTOR = 1.05
MAX_LINES_PER_PAGE = 3
BACKGROUND_MUSIC_VOLUME = 0.15
DELAY_BETWEEN_POSTS = 10 
NEWS_TEMPLATES = {
    "1": { "name": "دليلك في سوريا", "hashtag": "#عاجل #سوريا #سوريا_عاجل #syria", "color": (211, 47, 47) },
    "3": { "name": "دليلك في الأخبار", "hashtag": "#عاجل #أخبار #دليلك", "color": (200, 30, 30) },
    "4": { "name": "عاجل||نتائج", "hashtag": "#عاجل #نتائج #التعليم_الأساسي #التاسع", "color": (200, 30, 30) },
    "2": { "name": "دليلك في الرياضة", "hashtag": "#أخبار #رياضة", "color": (0, 128, 212) }
}
VIDEO_DIMENSIONS = {
    "1": {"name": "Instagram Post (4:5)", "size": (1080, 1350)},
    "2": {"name": "Instagram Story/Reel (9:16)", "size": (1080, 1920)},
    "3": {"name": "Square (1:1)", "size": (1080, 1080)},
    "4": {"name": "YouTube Standard (16:9)", "size": (1920, 1080)}
}
DETAILS_TEXT = "الـتـفـاصـيـل:"
FOOTER_TEXT = "تابعنا عبر موقع دليلك نيوز الإخباري"

# --- دوال مساعدة ---
def add_kashida(text):
    non_connecting_chars = {'ا', 'أ', 'إ', 'آ', 'د', 'ذ', 'ر', 'ز', 'و', 'ؤ', 'ة'}
    result = []
    for i, char in enumerate(text):
        result.append(char)
        if i < len(text) - 1:
            next_char = text[i+1]
            if ('\u0600' <= char <= '\u06FF') and ('\u0600' <= next_char <= '\u06FF') and (char not in non_connecting_chars) and (next_char != ' '):
                result.append('ـ')
    return "".join(result)

def process_text_for_image(text): return get_display(arabic_reshaper.reshape(text))

def wrap_text_to_pages(text, font, max_width, max_lines_per_page):
    if not text: return [[]]
    lines, words, current_line = [], text.split(), ''
    for word in words:
        test_line = f"{current_line} {word}".strip()
        if font.getbbox(process_text_for_image(test_line))[2] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line); current_line = word
    lines.append(current_line)
    return [lines[i:i + max_lines_per_page] for i in range(0, len(lines), max_lines_per_page)]

def draw_text_with_shadow(draw, position, text, font, fill_color, shadow_color):
    x, y = position; processed_text = process_text_for_image(text); shadow_offset = 3
    draw.text((x + shadow_offset, y + shadow_offset), processed_text, font=font, fill=shadow_color, stroke_width=2)
    draw.text((x, y), processed_text, font=font, fill=fill_color)

def fit_image_to_box(img, box_width, box_height):
    img_ratio = img.width / img.height; box_ratio = box_width / box_height
    if img_ratio > box_ratio:
        new_height = box_height; new_width = int(new_height * img_ratio)
    else:
        new_width = box_width; new_height = int(new_width / img_ratio)
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - box_width) / 2; top = (new_height - box_height) / 2
    return img.crop((left, top, left + box_width, top + box_height))

def render_design(design_type, draw, W, H, template, lines_to_draw, news_font, logo_img):
    if design_type == 'classic':
        header_height = int(H * 0.1)
        dark_color, light_color = template['color'], tuple(min(c+30, 255) for c in template['color'])
        for i in range(header_height):
            ratio = i / header_height; r,g,b = [int(dark_color[j]*(1-ratio) + light_color[j]*ratio) for j in range(3)]
            draw.line([(0, i), (W, i)], fill=(r,g,b))
        draw.rectangle([(0,0), (W, header_height//3)], fill=(255,255,255,50))
        header_font = ImageFont.truetype(FONT_FILE, int(W / 14.5))
        header_text_proc = process_text_for_image(template['name'])
        draw_text_with_shadow(draw, ((W - header_font.getbbox(header_text_proc)[2]) / 2, (header_height - header_font.getbbox(header_text_proc)[3]) / 2 - 10), template['name'], header_font, TEXT_COLOR, SHADOW_COLOR)
    elif design_type == 'cinematic':
        tag_font = ImageFont.truetype(FONT_FILE, int(W / 24)); tag_text = process_text_for_image(template['name'])
        tag_bbox = tag_font.getbbox(tag_text); tag_width = tag_bbox[2] - tag_bbox[0] + 60; tag_height = tag_bbox[3] - tag_bbox[1] + 30
        tag_x, tag_y = W - tag_width - 40, 40
        draw.rounded_rectangle([tag_x, tag_y, tag_x + tag_width, tag_y + tag_height], radius=tag_height/2, fill=template['color'])
        draw.text((tag_x + tag_width/2, tag_y + tag_height/2), tag_text, font=tag_font, fill=TEXT_COLOR, anchor="mm")
    
    if lines_to_draw:
        line_heights = [news_font.getbbox(process_text_for_image(line))[3] + 20 for line in lines_to_draw]
        plate_height = sum(line_heights) + 60; plate_y0 = (H - plate_height) / 2
        draw.rectangle([(0, plate_y0), (W, plate_y0 + plate_height)], fill=TEXT_PLATE_COLOR)
        text_y_start = plate_y0 + 30
        for line in lines_to_draw:
            line_width = news_font.getbbox(process_text_for_image(line))[2]
            draw_text_with_shadow(draw, ((W - line_width) / 2, text_y_start), line, news_font, TEXT_COLOR, SHADOW_COLOR)
            text_y_start += news_font.getbbox(process_text_for_image(line))[3] + 20

def create_video(design_type, news_title, template, background_image_path, W, H, status_callback):
    output_video_name = f"news_video_{random.randint(1000, 9999)}.mp4"
    thumbnail_name = f"thumbnail_{random.randint(1000, 9999)}.jpg"
    silent_video_path = f"silent_video_{random.randint(1000, 9999)}.mp4"

    status_callback(f"--> جاري إنشاء فيديو بالتصميم '{design_type}' وأبعاد {W}x{H}...")
    try:
        font_size_base = int(W / 12)
        news_font = ImageFont.truetype(FONT_FILE, font_size_base if len(news_title) < 50 else font_size_base - 20)
        
        if background_image_path and os.path.exists(background_image_path):
            base_image = fit_image_to_box(Image.open(background_image_path).convert("RGB"), W, H)
        else:
            base_image = Image.open(LOGO_FILE).convert("RGB").resize((W,H)).filter(ImageFilter.GaussianBlur(15))
            
        logo_img = Image.open(LOGO_FILE).convert("RGBA") if os.path.exists(LOGO_FILE) else None
    except Exception as e:
        status_callback(f"!! خطأ في تحميل الأصول: {e}", "error"); return None, None

    text_pages = wrap_text_to_pages(news_title, news_font, max_width=W-120, max_lines_per_page=MAX_LINES_PER_PAGE)
    num_pages = len(text_pages)
    if num_pages > 1: status_callback(f"--> تم تقسيم النص إلى {num_pages} صفحات.")

    status_callback("--> جاري إنشاء الصورة المصغرة (Thumbnail)...")
    thumb_image = base_image.copy()
    render_design(design_type, ImageDraw.Draw(thumb_image, 'RGBA'), W, H, template, text_pages[0], news_font, logo_img)
    thumb_image.convert('RGB').save(thumbnail_name, quality=85)

    video_writer = cv2.VideoWriter(silent_video_path, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (W, H))
    total_main_frames = int(SECONDS_PER_PAGE * FPS) * num_pages
    total_video_frames = total_main_frames + int(OUTRO_DURATION_SECONDS * FPS)
    global_frame_index = 0
    
    for page_index, original_page_lines in enumerate(text_pages):
        status_callback(f"--> جاري معالجة الصفحة {page_index + 1}/{num_pages}...")
        # ... (بقية منطق معالجة الصفحات والفريمات) ...

    video_writer.release()
    status_callback("--> تم إنشاء الفيديو الصامت، جاري دمج الصوت...")
    try:
        video_stream = ffmpeg.input(silent_video_path); alert_stream = ffmpeg.input(SOUND_FILE)
        inputs = [video_stream, alert_stream]
        if os.path.exists(BACKGROUND_MUSIC_FILE):
            music_stream = ffmpeg.input(BACKGROUND_MUSIC_FILE, stream_loop=-1).filter('volume', BACKGROUND_MUSIC_VOLUME)
            mixed_audio = ffmpeg.filter([alert_stream, music_stream], 'amix', duration='first', dropout_transition=0)
            inputs = [video_stream, mixed_audio]
        total_duration = (num_pages * SECONDS_PER_PAGE) + OUTRO_DURATION_SECONDS
        (ffmpeg.output(*inputs, output_video_name, t=total_duration, vcodec='libx264', acodec='aac', pix_fmt='yuv420p', loglevel="quiet").overwrite_output().run())
    except ffmpeg.Error as e:
        status_callback(f"!! خطأ فادح ffmpeg: {e.stderr.decode() if e.stderr else 'Unknown Error'}", "error"); return None, None
    finally:
        if os.path.exists(silent_video_path): os.remove(silent_video_path)
    
    return output_video_name, thumbnail_name

def scrape_article_page(url, status_callback):
    status_callback(f"🔍 جاري تحليل الرابط: {url[:70]}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10); response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('h1', class_='entry-title') or soup.find('h1') or soup.find('title')
        if not title_tag: return {"error": "لم يتم العثور على عنوان الخبر."}
        title = title_tag.get_text(strip=True)
        og_image_tag = soup.find('meta', property='og:image')
        if not (og_image_tag and og_image_tag.get('content')):
            return {"error": "لم يتم العثور على صورة الخبر.", "title": title}
        status_callback("✅ تم استخراج البيانات بنجاح.")
        return {'title': title, 'image_url': og_image_tag['content']}
    except requests.RequestException as e:
        return {"error": f"خطأ في الاتصال بالرابط: {e}"}

def download_image(url, status_callback):
    try:
        temp_image_name = f"temp_background_{random.randint(1000, 9999)}.jpg"
        status_callback(f"--> جاري تنزيل الصورة...")
        response = requests.get(url, stream=True, timeout=15); response.raise_for_status()
        with open(temp_image_name, 'wb') as f: f.write(response.content)
        return temp_image_name
    except requests.RequestException as e:
        status_callback(f"!! فشل تنزيل الصورة: {e}", "error"); return None
        
async def send_video_to_telegram(bot_token, channel_id, video_path, thumbnail_path, caption, hashtag, status_callback):
    status_callback("--> جاري نشر الفيديو إلى تليجرام...")
    try:
        bot = telegram.Bot(token=bot_token)
        full_caption = f"{caption}\n\n<b>{hashtag}</b>"
        with open(video_path, 'rb') as video_file, open(thumbnail_path, 'rb') as thumb_file:
            await bot.send_video(chat_id=channel_id, video=video_file, thumbnail=thumb_file, caption=full_caption, parse_mode=ParseMode.HTML, read_timeout=120, write_timeout=120, supports_streaming=True)
        status_callback("✅ تم النشر بنجاح!", "success")
    except Exception as e:
        status_callback(f"!! خطأ أثناء الإرسال: {e}", "error")

async def process_batch_video_creation(bot_token, channel_id, dimension_key, design_type, template_key, items_to_process, item_type, status_callback):
    selected_dimensions_info = VIDEO_DIMENSIONS.get(dimension_key)
    if not selected_dimensions_info:
        status_callback("! اختيار أبعاد غير صالح.", "error"); return
    W, H = selected_dimensions_info['size']

    selected_template = NEWS_TEMPLATES.get(template_key)
    if not selected_template:
        status_callback("! اختيار قالب غير صالح.", "error"); return

    total_items = len(items_to_process)
    for i, item in enumerate(items_to_process, 1):
        status_callback(f"\n--- [ {i}/{total_items} ] --- جاري معالجة: {item[:60]} ---", "info")
        data = {}; temp_image_path = None
        if item_type == 'url':
            article_data = scrape_article_page(item, status_callback)
            if not article_data: continue
            if article_data.get("image_url"):
                temp_image_path = download_image(article_data['image_url'], status_callback)
            data = {'text': article_data['title'], 'image': temp_image_path, 'url': item}
        else: # text
            data = {'text': item, 'image': None, 'url': None}
        
        video_file, thumbnail_file = await asyncio.to_thread(create_video, design_type, data['text'], selected_template, data.get('image'), W, H, status_callback)
        
        if video_file and thumbnail_file:
            caption_parts = [data['text'], "", add_kashida(data['text'])]
            if data.get('url'):
                caption_parts.extend(["", f"<b>{DETAILS_TEXT}</b> {data['url']}"])
            caption = "\n".join(caption_parts)
            
            await send_video_to_telegram(bot_token, channel_id, video_file, thumbnail_file, caption, selected_template['hashtag'], status_callback)
            
            for f in [video_file, thumbnail_file, temp_image_path]:
                if f and os.path.exists(f): os.remove(f)
        else:
            status_callback(f"! فشلت عملية إنشاء الفيديو للنص: '{data['text'][:30]}...'", "error")
            if temp_image_path and os.path.exists(temp_image_path): os.remove(temp_image_path)
            
        if i < total_items:
            status_callback(f"--- انتظار لمدة {DELAY_BETWEEN_POSTS} ثوانٍ... ---", "info")
            await asyncio.sleep(DELAY_BETWEEN_POSTS)
    
    status_callback("\n✅ اكتملت معالجة جميع العناصر.", "success")