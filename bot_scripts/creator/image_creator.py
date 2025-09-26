# bot_scripts/creator/image_creator.py

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
import telegram
from telegram.constants import ParseMode
import os
import random
import requests
from bs4 import BeautifulSoup
import asyncio

# --- الإعدادات الثابتة للتصميم ---
FONT_FILE = "Amiri-Bold.ttf"
LOGO_FILE = "logo.png"
TEXT_COLOR = "#FFFFFF"
SHADOW_COLOR = "#000000"
BACKGROUND_BLUR_RADIUS = 25
TEXT_PLATE_COLOR = (0, 0, 0, 160)
NEWS_TEMPLATES = {
    "1": {"name": "عاجل", "hashtag": "#عاجل", "color": (211, 47, 47)},
    "4": {"name": "رياضة", "hashtag": "#رياضة #مباريات", "color": (0, 128, 0)},
    "3": {"name": "سوريا عاجل", "hashtag": "#سوريا_عاجل #عاجل", "color": (211, 47, 47)},
    "5": {"name": "دليلك في أوروبا", "hashtag": "#دليلك #أخبار", "color": (211, 47, 47)},
    "2": {"name": "دليلك في الأخبار", "hashtag": "#أخبار", "color": (0, 128, 212)}
}
DETAILS_TEXT = "التفاصيل:"
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

def process_text_for_image(text):
    return get_display(arabic_reshaper.reshape(text))

def wrap_text(text, font, max_width):
    if not text: return []
    lines, words, current_line = [], text.split(), ''
    for word in words:
        test_line = f"{current_line} {word}".strip()
        if font.getbbox(process_text_for_image(test_line))[2] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line); current_line = word
    lines.append(current_line)
    return lines

def draw_text_with_shadow(draw, position, text, font, fill_color, shadow_color):
    x, y = position; processed_text = process_text_for_image(text); shadow_offset = 3
    draw.text((x + shadow_offset, y + shadow_offset), processed_text, font=font, fill=shadow_color, stroke_width=2)
    draw.text((x, y), processed_text, font=font, fill=fill_color)

def fit_image_to_box(img, box_width, box_height):
    img_ratio = img.width / img.height; box_ratio = box_width / box_height
    if img_ratio > box_ratio: new_height = box_height; new_width = int(new_height * img_ratio)
    else: new_width = box_width; new_height = int(new_width / img_ratio)
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - box_width) / 2; top = (new_height - box_height) / 2
    return img.crop((left, top, left + box_width, top + box_height))

# --- دوال التصميم (تمت استعادتها بالكامل) ---
def create_classic_design(news_title, template, background_image_path):
    print("--> جاري إنشاء الصورة بالتصميم الكلاسيكي...")
    W, H = 1080, 1080
    output_image_name = f"news_image_{random.randint(1000, 9999)}.png"
    try:
        base_image = Image.open(background_image_path).convert("RGB") if background_image_path and os.path.exists(background_image_path) else Image.open(LOGO_FILE).convert("RGB").resize((W,H))
    except Exception: base_image = Image.new('RGB', (W, H), (20, 20, 20))
    blurred_bg = base_image.resize((int(W*1.2), int(H*1.2)), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(BACKGROUND_BLUR_RADIUS))
    b_left, b_top = (blurred_bg.width - W)/2, (blurred_bg.height - H)/2
    final_image = blurred_bg.crop((b_left, b_top, b_left + W, b_top + H))
    content_margin = 40
    clear_image = fit_image_to_box(base_image, W - 2 * content_margin, H - 2 * content_margin)
    final_image.paste(clear_image, (content_margin, content_margin))
    draw = ImageDraw.Draw(final_image, 'RGBA')
    header_height = 120
    dark_color, light_color = template['color'], tuple(min(c+30, 255) for c in template['color'])
    for i in range(header_height):
        ratio = i / header_height; r,g,b = [int(dark_color[j]*(1-ratio) + light_color[j]*ratio) for j in range(3)]
        draw.line([(0, i), (W, i)], fill=(r,g,b))
    draw.rectangle([(0,0), (W, header_height//3)], fill=(255,255,255,50))
    header_font = ImageFont.truetype(FONT_FILE, 75)
    header_text_proc = process_text_for_image(template['name'])
    draw_text_with_shadow(draw, ((W - header_font.getbbox(header_text_proc)[2]) / 2, (header_height - header_font.getbbox(header_text_proc)[3]) / 2 - 10), template['name'], header_font, TEXT_COLOR, SHADOW_COLOR)
    news_font = ImageFont.truetype(FONT_FILE, 90 if len(news_title) < 50 else 70)
    wrapped_lines = wrap_text(news_title, news_font, max_width=W - (2 * (content_margin + 50)))
    if wrapped_lines:
        line_heights = [news_font.getbbox(process_text_for_image(line))[3] + 20 for line in wrapped_lines]
        total_text_height = sum(line_heights); plate_height = total_text_height + 60
        plate_y0 = (H - plate_height) / 2
        draw.rectangle([(0, plate_y0), (W, plate_y0 + plate_height)], fill=TEXT_PLATE_COLOR)
        text_y_start = plate_y0 + 30
        for i, line in enumerate(wrapped_lines):
            line_width = news_font.getbbox(process_text_for_image(line))[2]
            draw_text_with_shadow(draw, ((W - line_width) / 2, text_y_start), line, news_font, TEXT_COLOR, SHADOW_COLOR)
            text_y_start += line_heights[i]
    footer_height = 80; footer_y_start = H - footer_height
    draw.rectangle([(0, footer_y_start), (W, H)], fill=(0,0,0,180))
    footer_font = ImageFont.truetype(FONT_FILE, 40)
    footer_text_proc = process_text_for_image(FOOTER_TEXT)
    try:
        logo = Image.open(LOGO_FILE).convert("RGBA").resize((60, 60))
        total_footer_width = footer_font.getbbox(footer_text_proc)[2] + 20 + logo.width
        footer_x_start = (W - total_footer_width) / 2
        text_y_pos = footer_y_start + (footer_height - footer_font.getbbox(footer_text_proc)[3]) / 2
        draw.text((footer_x_start, text_y_pos), footer_text_proc, font=footer_font, fill="#E0E0E0")
        logo_x_pos = int(footer_x_start + footer_font.getbbox(footer_text_proc)[2] + 20)
        logo_y_pos = footer_y_start + (footer_height - logo.height) // 2
        final_image.paste(logo, (logo_x_pos, logo_y_pos), logo)
    except FileNotFoundError:
        draw.text(((W - footer_font.getbbox(footer_text_proc)[2])/2, footer_y_start + 15), footer_text_proc, font=footer_font, fill="#E0E0E0")
    final_image = final_image.convert('RGB'); final_image.save(output_image_name, quality=90)
    print(f"✅ تم إنشاء الصورة وحفظها كـ {output_image_name}"); 
    return output_image_name

def create_cinematic_design(news_title, template, background_image_path):
    print("--> جاري إنشاء الصورة بالتصميم السينمائي...")
    W, H = 1080, 1080
    output_image_name = f"news_image_{random.randint(1000, 9999)}.png"
    try:
        base_image = Image.open(background_image_path).convert("RGB") if background_image_path and os.path.exists(background_image_path) else Image.open(LOGO_FILE).convert("RGB").resize((W,H)).filter(ImageFilter.GaussianBlur(15))
    except Exception: base_image = Image.new('RGB', (W, H), (20, 20, 20))
    final_image = fit_image_to_box(base_image, W, H)
    draw = ImageDraw.Draw(final_image, 'RGBA')
    tag_font = ImageFont.truetype(FONT_FILE, 45)
    tag_text = process_text_for_image(template['name'])
    tag_bbox = tag_font.getbbox(tag_text); tag_width = tag_bbox[2] - tag_bbox[0] + 60; tag_height = tag_bbox[3] - tag_bbox[1] + 30
    tag_x, tag_y = W - tag_width - 40, 40
    draw.rounded_rectangle([tag_x, tag_y, tag_x + tag_width, tag_y + tag_height], radius=tag_height/2, fill=template['color'])
    draw.text((tag_x + tag_width/2, tag_y + tag_height/2), tag_text, font=tag_font, fill=TEXT_COLOR, anchor="mm")
    news_font = ImageFont.truetype(FONT_FILE, 100 if len(news_title) < 40 else 80)
    wrapped_lines = wrap_text(news_title, news_font, max_width=W - 120)
    if wrapped_lines:
        line_heights = [news_font.getbbox(process_text_for_image(line))[3] + 20 for line in wrapped_lines]
        total_text_height = sum(line_heights)
        plate_height = total_text_height + 60
        plate_y_start = H - plate_height - 120
        draw.rectangle([(0, plate_y_start), (W, plate_y_start + plate_height)], fill=TEXT_PLATE_COLOR)
        text_y_start = plate_y_start + 30
        for i, line in enumerate(wrapped_lines):
            line_width = news_font.getbbox(process_text_for_image(line))[2]
            draw_text_with_shadow(draw, ((W - line_width) / 2, text_y_start), line, news_font, TEXT_COLOR, SHADOW_COLOR)
            text_y_start += line_heights[i]
    footer_font = ImageFont.truetype(FONT_FILE, 40)
    footer_text_proc = process_text_for_image(FOOTER_TEXT)
    try:
        logo = Image.open(LOGO_FILE).convert("RGBA").resize((60, 60))
        total_footer_width = footer_font.getbbox(footer_text_proc)[2] + 20 + logo.width
        footer_x_start = (W - total_footer_width) / 2
        text_y_pos = H - 80 + (80 - footer_font.getbbox(footer_text_proc)[3]) / 2 - 20
        draw_text_with_shadow(draw, (footer_x_start, text_y_pos), FOOTER_TEXT, footer_font, "#E0E0E0", SHADOW_COLOR)
        logo_x_pos = int(footer_x_start + footer_font.getbbox(footer_text_proc)[2] + 20)
        logo_y_pos = H - 80 + (80 - logo.height) // 2
        final_image.paste(logo, (logo_x_pos, logo_y_pos), logo)
    except FileNotFoundError:
        draw_text_with_shadow(draw, ((W - footer_font.getbbox(footer_text_proc)[2])/2, H - 80), FOOTER_TEXT, footer_font, "#E0E0E0", SHADOW_COLOR)
    final_image = final_image.convert('RGB'); final_image.save(output_image_name, quality=90)
    print(f"✅ تم إنشاء الصورة وحفظها كـ {output_image_name}");
    return output_image_name

# --- دوال رئيسية قابلة للاستدعاء ---
def scrape_article_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title_tag = soup.find('h1', class_='entry-title') or soup.find('h1') or soup.find('title')
        if not title_tag: return {"error": "لم يتم العثور على عنوان الخبر."}
        title = title_tag.get_text(strip=True)
        og_image_tag = soup.find('meta', property='og:image')
        if not (og_image_tag and og_image_tag.get('content')):
            return {"error": "لم يتم العثور على صورة الخبر.", "title": title}
        return {'title': title, 'image_url': og_image_tag['content']}
    except requests.RequestException as e:
        return {"error": f"خطأ في الاتصال بالرابط: {e}"}

def download_image(url):
    try:
        temp_image_name = f"temp_background_{random.randint(1000, 9999)}.jpg"
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()
        with open(temp_image_name, 'wb') as f:
            f.write(response.content)
        return temp_image_name
    except requests.RequestException as e:
        print(f"!! فشل تنزيل الصورة: {e}"); return None

async def send_to_telegram(bot_token, channel_id, image_path, caption):
    try:
        bot = telegram.Bot(token=bot_token)
        with open(image_path, 'rb') as photo_file:
            await bot.send_photo(chat_id=channel_id, photo=photo_file, caption=caption, parse_mode=ParseMode.HTML, read_timeout=60, write_timeout=60)
        return True, "تم الإرسال بنجاح!"
    except Exception as e:
        return False, f"حدث خطأ أثناء الإرسال إلى تليجرام: {e}"

async def process_and_send_batch(bot_token, channel_id, design_choice, template_key, news_items, content_type, status_callback):
    if not bot_token or not channel_id:
        status_callback("خطأ: لم يتم تعيين إعدادات تليجرام.", "error"); return

    selected_template = NEWS_TEMPLATES.get(template_key)
    if not selected_template:
        status_callback("خطأ: اختيار قالب غير صالح.", "error"); return

    total_items = len(news_items)
    for i, item in enumerate(news_items, 1):
        status_callback(f"--- جاري معالجة الخبر {i}/{total_items}: \"{item[:50].strip()}...\" ---", "info")
        
        news_text, image_path, article_url = None, None, None

        if content_type == 'link':
            article_url = item
            article_data = scrape_article_page(article_url)
            if article_data.get("error"):
                status_callback(f"! فشل سحب البيانات للرابط {article_url}: {article_data['error']}", "warning")
                if not article_data.get("title"): continue
                news_text = article_data.get("title")
            else:
                news_text = article_data['title']
                image_url = article_data['image_url']
                status_callback(f"--> جاري تنزيل الصورة من: {image_url[:70]}...")
                image_path = download_image(image_url)
        else:
            news_text = item
        
        final_image_file = None
        try:
            status_callback("--> جاري إنشاء الصورة...")
            if design_choice == 'classic':
                final_image_file = create_classic_design(news_text, selected_template, image_path)
            else:
                final_image_file = create_cinematic_design(news_text, selected_template, image_path)
        except Exception as e:
            status_callback(f"!! حدث خطأ أثناء إنشاء الصورة: {e}", "error"); continue

        if final_image_file:
            stretched_news_text = add_kashida(news_text)
            caption_parts = [
                f"<b>{selected_template['hashtag']}</b>", "",
                stretched_news_text, news_text
            ]
            if article_url:
                stretched_details_text = add_kashida(DETAILS_TEXT)
                caption_parts.extend(["", f"<b>{stretched_details_text}</b> {article_url}"])
            
            caption = "\n".join(caption_parts)
            status_callback("--> جاري الإرسال إلى تليجرام...")
            success, message = await send_to_telegram(bot_token, channel_id, final_image_file, caption)
            status_callback(message, "success" if success else "error")
            
            if os.path.exists(final_image_file): os.remove(final_image_file)
            if image_path and os.path.exists(image_path): os.remove(image_path)
            
            if i < total_items:
                status_callback("... انتظار ثانيتين لتجنب الحظر ...", "info")
                await asyncio.sleep(2)
    
    status_callback("🎉 انتهت معالجة الدفعة بالكامل.", "success")