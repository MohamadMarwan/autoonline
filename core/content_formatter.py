# core/content_formatter.py
from bs4 import BeautifulSoup, Comment, Tag, NavigableString
from utils.logger_config import setup_logger
import re 
import json
import os
import sys
from io import StringIO

logger = setup_logger(__name__)

class ContentFormatter:
    # ✅ 1. تم تعديل __init__ ليتوقف عن الاعتماد على ملف ثابت
    def __init__(self, config, config_filepath=None):
        self.config = config
        self.prefix_html = self.config.get('ContentFormatting', 'PrefixContentHTML', fallback='')
        self.suffix_html = self.config.get('ContentFormatting', 'SuffixContentHTML', fallback='')
        self.extra_br_after_p = self.config.getboolean('ContentFormatting', 'ExtraBreakAfterParagraph', fallback=False)
        self.remove_internal_links = self.config.getboolean('ContentFormatting', 'RemoveInternalLinks', fallback=True)
        # لم نعد نحمل أي قواعد ثابتة هنا
        self.twitter_pattern = re.compile(r"(https?://(?:www\.)?(?:twitter\.com|x\.com)/(\w+)/status/(\d+))(?:\?[^\s]*)?", re.I)
        self.youtube_pattern_watch = re.compile(r"https?://(?:www\.)?youtube\.com/watch\?v=([\w-]+)(?:&[^\s]*)?", re.I)
        self.youtube_pattern_short = re.compile(r"https?://youtu\.be/([\w-]+)(?:\?[^\s]*)?", re.I)

    def _handle_embeds(self, soup):
        # (الكود الكامل لهذه الدالة)
        nodes_to_process = [tn for tn in soup.find_all(string=True) if isinstance(tn, NavigableString) and tn.parent and tn.parent.name not in ['script','style','a','pre','code','textarea','title']]
        for tn in nodes_to_process:
            orig_txt_content = str(tn); modified = False
            temp_io = StringIO(); last_end = 0
            all_matches = []
            for p_type, pattern in [("yt_watch", self.youtube_pattern_watch), ("yt_short", self.youtube_pattern_short), ("twitter", self.twitter_pattern)]:
                for m in pattern.finditer(orig_txt_content): all_matches.append({'start':m.start(),'end':m.end(),'match':m,'type':p_type})
            all_matches.sort(key=lambda x: x['start'])
            if not all_matches: continue
            for item in all_matches:
                m_start, m_end, match, p_type = item['start'], item['end'], item['match'], item['type']
                if m_start < last_end: continue
                if m_start > last_end: temp_io.write(orig_txt_content[last_end:m_start])
                embed_html = ""
                if p_type in ["yt_watch", "yt_short"]:
                    vid = match.group(1)
                    embed_html = (f'<div style="position:relative;padding-bottom:56.25%;padding-top:30px;height:0;overflow:hidden;max-width:100%;margin:10px 0;"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid}" title="YouTube video player" frameborder="0" allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" allowfullscreen></iframe></div>')
                elif p_type == "twitter":
                    url, handle, tweet_id = match.group(1), match.group(2), match.group(3)
                    embed_html = (f'<blockquote class="twitter-tweet" data-dnt="true" data-theme="light" data-align="center"><p lang="und" dir="auto"> </p>— @{handle} <a href="{url}" target="_blank" rel="noopener noreferrer ugc">Loading Tweet ({tweet_id})...</a></blockquote>')
                if embed_html: temp_io.write(embed_html); modified = True
                last_end = m_end
            if last_end < len(orig_txt_content): temp_io.write(orig_txt_content[last_end:])
            if modified:
                new_soup_frag = BeautifulSoup(temp_io.getvalue(), 'html.parser')
                new_elements = list(new_soup_frag.body.children) if new_soup_frag.body else list(new_soup_frag.children)
                current_insertion = tn
                for new_el in reversed(new_elements): current_insertion.insert_after(new_el)
                tn.extract()
            temp_io.close()

    # ✅ 2. تم تعديل format_for_blogger لتقبل واستخدام القواعد الديناميكية
    def format_for_blogger(self, raw_html_content, processed_images_map, main_hosted_image_url_for_prepend=None, article_title_for_alt="", dynamic_rules=None):
        if not raw_html_content or not isinstance(raw_html_content,str):
            if main_hosted_image_url_for_prepend:
                img_s=BeautifulSoup("","html.parser"); p_w=img_s.new_tag("p"); n_img=img_s.new_tag("img",src=main_hosted_image_url_for_prepend)
                n_img['alt']=article_title_for_alt or "Main Image"; n_img['style']="max-width:100%;height:auto;display:block;margin:10px auto;border:0;"
                p_w.append(n_img); clean_html=str(p_w)
                if self.prefix_html: clean_html=self.prefix_html+clean_html
                if self.suffix_html: clean_html=clean_html+self.suffix_html
                return clean_html.strip()
            return ""
        try:
            soup = BeautifulSoup(raw_html_content, 'html.parser')
            
            # --- هذا هو التعديل الرئيسي: تطبيق القواعد الديناميكية أولاً ---
            if dynamic_rules and 'replacements' in dynamic_rules:
                replacements = dynamic_rules.get('replacements', [])
                if replacements:
                    logger.info(f"Applying {len(replacements)} dynamic replacement rules.")
                    for text_node in soup.find_all(string=True):
                        if text_node.parent and text_node.parent.name in ['script', 'style']: continue
                        original_text = str(text_node)
                        modified_text = original_text
                        for rule in replacements:
                            find_str = rule.get('find')
                            replace_str = rule.get('replace_with', '')
                            if find_str:
                                modified_text = modified_text.replace(find_str, replace_str)
                        if original_text != modified_text:
                            text_node.replace_with(modified_text)
            
            self._handle_embeds(soup)

            # --- استعادة منطق التنظيف الكامل من الكود الأصلي ---
            for unwanted in ['script','style','form','link','meta','noscript','embed','object','applet','header','footer','nav','aside','figure','figcaption','title']:
                for tag in soup.find_all(unwanted): tag.decompose()
            for iframe_tag in soup.find_all('iframe'):
                iframe_src = iframe_tag.get('src','').lower()
                if not ('youtube.com/embed' in iframe_src or 'youtu.be/' in iframe_src): iframe_tag.decompose()
            for comment in soup.find_all(string=lambda t:isinstance(t,Comment)): comment.extract()
            if self.remove_internal_links:
                for a in soup.find_all('a', href=True): 
                    is_embed_link = False
                    if a.find_parent('blockquote', class_='twitter-tweet') or a.find_parent('iframe', src=re.compile("youtube.com/embed")):
                        is_embed_link = True
                    if not is_embed_link: del a['href']
            
            first_img_src_in_content = None 
            image_tags_in_soup = soup.find_all('img') 
            for idx, img_tag_from_soup in enumerate(image_tags_in_soup):
                orig_s=img_tag_from_soup.get('src') or img_tag_from_soup.get('data-src'); hosted_url=None
                if orig_s:
                    if orig_s in processed_images_map: hosted_url=processed_images_map[orig_s]
                    else:
                        for mk,up_url in processed_images_map.items():
                            if orig_s in mk or mk in orig_s: hosted_url=up_url;break
                if hosted_url:
                    img_tag_from_soup.attrs={};img_tag_from_soup['src']=hosted_url
                    alt=(img_tag_from_soup.get('alt') or article_title_for_alt or "Image").strip() or (article_title_for_alt or "Image")
                    img_tag_from_soup['alt']=alt;img_tag_from_soup['style']="max-width:100%;height:auto;display:block;margin:10px auto;border:0;"
                    if idx==0:first_img_src_in_content=hosted_url
                else:logger.warning(f"Image '{orig_s}' not in map. Decomposing.");img_tag_from_soup.decompose()
            
            allowed_tags_attrs = {
                'a':['title','name','href','target','rel'],'img':['src','alt','title','style','width','height','border'], 'p':[],'br':[],'hr':[],'strong':[],'b':[],'em':[],'i':[],'u':[],'s':[],'strike':[],'del':[],
                'sup':[],'sub':[],'code':[],'pre':[],'ul':['type'],'ol':['type','start','reversed'],'li':['value'], 'h1':[],'h2':[],'h3':[],'h4':[],'h5':[],'h6':[],
                'blockquote':['style','cite','class','data-dnt','data-theme','data-align'], 'q':['cite'], 'iframe':['src','width','height','frameborder','allowfullscreen','style','title','allow'],
                'table':['border','cellpadding','cellspacing','width','style','summary'],'div':['style'] 
            }
            for tag in soup.find_all(True):
                if tag.name in allowed_tags_attrs:
                    allowed_attrs = set(allowed_tags_attrs[tag.name])
                    for attr in dict(tag.attrs):
                        if attr.lower() not in allowed_attrs: del tag[attr]
                else:
                    tag.unwrap()
            
            for p in soup.find_all('p'):
                if not p.get_text(strip=True) and not p.find(['img','br','hr','iframe','blockquote']):p.decompose()
                elif self.extra_br_after_p and p.next_sibling and p.next_sibling.name!='br':p.append(soup.new_tag('br'))
            for h_num in range(1,7):
                for h in soup.find_all(f'h{h_num}'):
                    if not h.get_text(strip=True):h.decompose()
                    elif h_num==1:h.name='h2'
            
            prepend_html=""
            if main_hosted_image_url_for_prepend and main_hosted_image_url_for_prepend!=first_img_src_in_content:
                img_s=BeautifulSoup("","html.parser");p_w=img_s.new_tag("p")
                n_img=img_s.new_tag("img",src=main_hosted_image_url_for_prepend)
                alt_main=(article_title_for_alt or "Featured Image").strip() or "Featured Image"
                n_img['alt']=alt_main;n_img['style']="max-width:100%;height:auto;display:block;margin:10px auto;border:0;"
                p_w.append(n_img);prepend_html=str(p_w)
            
            body_html="".join(str(c) for c in soup.contents)
            final_html=prepend_html+body_html
            if self.prefix_html:final_html=self.prefix_html+final_html
            if self.suffix_html:final_html=final_html+self.suffix_html
            
            logger.info("HTML content formatted for Blogger.")
            return final_html.strip()
        except Exception as e:
            logger.error(f"Error formatting content: {e}",exc_info=True)
            return raw_html_content