# # core/image_processor.py (نسخة محدثة تدعم طرق وضع شعار مختلفة)
# import io
# import os
# import requests
# from PIL import Image, ImageEnhance
# from utils.logger_config import setup_logger
# import configparser

# logger = setup_logger(__name__)

# class ImageProcessor:
#     def __init__(self, config):
#         self.config = config
#         self.user_agent = config.get('DEFAULT', 'UserAgent', fallback='ImageProcessorBot/1.0')
#         self.request_timeout = config.getint('Scraping', 'RequestTimeout', fallback=20)
#         self.output_format = config.get('ImageProcessing', 'OutputFormat', fallback='JPEG').upper()
        
#         try:
#             quality_str = self.config.get('ImageProcessing', 'OutputQuality', fallback='85')
#             self.output_quality = int(quality_str.split('#')[0].strip())
#         except (ValueError, IndexError):
#             self.output_quality = 85
        
#         logger.info("ImageProcessor initialized.")

#     def _apply_logo(self, image_obj, logo_section_name):
#         """
#         دالة مساعدة ذكية لتطبيق شعار بناءً على طريقة الوضع المحددة في الإعدادات.
#         """
#         if not self.config.getboolean(logo_section_name, 'Enabled', fallback=False):
#             logger.debug(f"Logo section '{logo_section_name}' is disabled. Skipping.")
#             return image_obj

#         logo_path = self.config.get(logo_section_name, 'LogoFile', fallback=None)
#         if not logo_path or not os.path.exists(logo_path):
#             logger.error(f"Logo file for '{logo_section_name}' not found at: {logo_path}. Skipping.")
#             return image_obj

#         try:
#             placement_mode = self.config.get(logo_section_name, 'PlacementMode', fallback='scale').lower()
#             logo_pil = Image.open(logo_path).convert("RGBA")
            
#             logo_resized = None
#             pos = (0, 0)

#             # --- A. وضع الشعار كشريط ممتد (stretch_bar) ---
#             if placement_mode == 'stretch_bar':
#                 logger.info(f"Applying '{logo_section_name}' in 'stretch_bar' mode.")
#                 fixed_height = self.config.getint(logo_section_name, 'FixedHeight')
#                 target_w = image_obj.width # العرض هو عرض الصورة بالكامل
#                 target_h = fixed_height
                
#                 logo_resized = logo_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
#                 pos = (0, image_obj.height - target_h) # الموضع: أقصى اليسار، وفي الأسفل

#             # --- B. وضع الشعار كأيقونة بحجم متغير (scale) ---
#             elif placement_mode == 'scale':
#                 logger.info(f"Applying '{logo_section_name}' in 'scale' mode.")
#                 scale = self.config.getfloat(logo_section_name, 'LogoScaleFactor')
#                 min_w = self.config.getint(logo_section_name, 'MinLogoPixelWidth')
#                 max_w = self.config.getint(logo_section_name, 'MaxLogoPixelWidth')
#                 margin = self.config.getfloat(logo_section_name, 'LogoMarginFactor')
#                 position = self.config.get(logo_section_name, 'LogoPosition').lower()
                
#                 target_w = int(image_obj.width * scale)
#                 target_w = max(min_w, min(target_w, max_w))
#                 aspect_ratio = logo_pil.height / logo_pil.width
#                 target_h = int(target_w * aspect_ratio)

#                 logo_resized = logo_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
                
#                 margin_x = int(image_obj.width * margin)
#                 margin_y = int(image_obj.height * margin)

#                 if position == "top_left": pos = (margin_x, margin_y)
#                 elif position == "top_right": pos = (image_obj.width - target_w - margin_x, margin_y)
#                 elif position == "bottom_left": pos = (margin_x, image_obj.height - target_h - margin_y)
#                 elif position == "bottom_right": pos = (image_obj.width - target_w - margin_x, image_obj.height - target_h - margin_y)
#                 elif position == "bottom_center": pos = ((image_obj.width - target_w) // 2, image_obj.height - target_h - margin_y)
#                 else: pos = (margin_x, margin_y) # الافتراضي هو top_left

#             else:
#                 logger.warning(f"Unknown PlacementMode '{placement_mode}' for '{logo_section_name}'. Skipping.")
#                 return image_obj

#             # لصق الشعار بعد تحديد حجمه ومكانه
#             image_obj.paste(logo_resized, pos, logo_resized)
#             logger.info(f"Logo from '{logo_section_name}' applied successfully.")
#             return image_obj

#         except Exception as e:
#             logger.error(f"Failed to apply logo from '{logo_section_name}': {e}", exc_info=True)
#             return image_obj

#     def process_image_with_logo(self, image_url):
#         # هذه الدالة لا تحتاج لتغييرات كبيرة لأن المنطق تم عزله في _apply_logo
#         try:
#             logger.info(f"Downloading image: {image_url[:100]}...")
#             # ... (بقية كود التحميل والقص يبقى كما هو) ...
#             response = requests.get(image_url, headers={'User-Agent': self.user_agent}, stream=True, timeout=self.request_timeout)
#             response.raise_for_status()
#             processed_image = Image.open(io.BytesIO(response.content))

#             if self.config.has_section('Cropping') and self.config.getboolean('Cropping', 'CropEnabled', fallback=False):
#                 try:
#                     x, y, w, h = (self.config.getint('Cropping', k) for k in ['CropX', 'CropY', 'CropWidth', 'CropHeight'])
#                     if (x + w) <= processed_image.width and (y + h) <= processed_image.height:
#                         processed_image = processed_image.crop((x, y, x + w, y + h))
#                         logger.info(f"Image cropped. New dimensions: {processed_image.width}x{processed_image.height}")
#                     else:
#                         logger.warning("Crop dimensions exceed image size. Skipping crop.")
#                 except Exception as e: logger.error(f"Cropping failed: {e}")

#             if self.output_format == 'JPEG' and processed_image.mode != 'RGB':
#                 processed_image = processed_image.convert('RGB')
#             elif self.output_format == 'PNG' and processed_image.mode != 'RGBA':
#                 processed_image = processed_image.convert('RGBA')

#             # تطبيق الشعارات بالترتيب
#             processed_image = self._apply_logo(processed_image, 'Logo1') # الشريط السفلي
#             processed_image = self._apply_logo(processed_image, 'Logo2') # الأيقونة العلوية

#             buffer = io.BytesIO()
#             save_opts = {'quality': self.output_quality, 'optimize': True} if self.output_format == 'JPEG' else {'optimize': True}
#             processed_image.save(buffer, format=self.output_format, **save_opts)
            
#             final_bytes = buffer.getvalue()
#             logger.info(f"Image fully processed. Final Size: {len(final_bytes)/1024:.2f}KB.")
#             return final_bytes

#         except Exception as e:
#             logger.error(f"Major error processing image {image_url}: {e}", exc_info=True)
#             return None

#     def upload_image_to_hosting(self, image_bytes, suggested_filename="processed_image.png"):
#         # لا حاجة لتعديل هذه الدالة
#         # ... (الكود يبقى كما هو) ...
#         if not image_bytes: logger.error("No image bytes to upload."); return None
#         service_name_key = "ImgBB" 
#         api_key = self.config.get(f'ImageHosting_{service_name_key}', 'ApiKey', fallback=None)
#         if not api_key or api_key.strip() == '' or 'YOUR_API_KEY' in api_key: logger.error(f"{service_name_key} API key not configured. Cannot upload."); return None
#         upload_url = self.config.get(f'ImageHosting_{service_name_key}', 'UploadUrl', fallback='https://api.imgbb.com/1/upload')
#         upload_timeout = self.config.getint(f'ImageHosting_{service_name_key}', 'UploadTimeout', fallback=70)
#         filename_lower = suggested_filename.lower()
#         if filename_lower.endswith('.png'): mime_type = 'image/png'
#         elif filename_lower.endswith(('.jpg', '.jpeg')): mime_type = 'image/jpeg'
#         else: mime_type = 'image/png'
#         clean_filename = os.path.basename(suggested_filename)
#         try:
#             logger.info(f"Uploading '{clean_filename}' ({len(image_bytes)/1024:.2f}KB) to {service_name_key}...")
#             files = {'image': (clean_filename, image_bytes, mime_type)}; payload = {'key': api_key}
#             response = requests.post(upload_url, files=files, data=payload, timeout=upload_timeout)
#             response.raise_for_status(); response_data = response.json()
#             if response_data.get('success') and response_data.get('data') and response_data['data'].get('url'):
#                 hosted_image_url = response_data['data']['url']
#                 logger.info(f"Image '{clean_filename}' uploaded to {service_name_key}: {hosted_image_url}")
#                 return hosted_image_url
#             else:
#                 error_message = response_data.get('error', {}).get('message', 'Unknown error from ImgBB')
#                 logger.error(f"Failed to upload to {service_name_key}. Msg: {error_message}. Resp: {response.text[:200]}")
#                 return None
#         except Exception as e: logger.error(f"Error uploading '{clean_filename}': {e}", exc_info=True); return None










import io
import os
import requests
import configparser
import logging

from PIL import Image

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ImageProcessor:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.user_agent = config.get('DEFAULT', 'UserAgent', fallback='ImageProcessorBot/1.0')
        self.request_timeout = config.getint('Scraping', 'RequestTimeout', fallback=30)
        self.output_format = config.get('ImageProcessing', 'OutputFormat', fallback='JPEG').upper()
        self.output_quality = config.getint('ImageProcessing', 'OutputQuality', fallback=85)
        self.logger.info("ImageProcessor initialized for hosting via ImgBB bridge (HTTP mode).")

    def _apply_logo(self, image_obj, logo_section_name):
        if not self.config.getboolean(logo_section_name, 'Enabled', fallback=False):
            return image_obj
        logo_path = self.config.get(logo_section_name, 'LogoFile', fallback=None)
        if not logo_path or not os.path.exists(logo_path):
            self.logger.error(f"Logo file for '{logo_section_name}' not found: {logo_path}. Skipping.")
            return image_obj
        try:
            placement_mode = self.config.get(logo_section_name, 'PlacementMode', fallback='scale').lower()
            logo_pil = Image.open(logo_path).convert("RGBA")
            logo_resized, pos = None, (0, 0)
            if placement_mode == 'stretch_bar':
                fixed_height = self.config.getint(logo_section_name, 'FixedHeight')
                logo_resized = logo_pil.resize((image_obj.width, fixed_height), Image.Resampling.LANCZOS)
                pos = (0, image_obj.height - fixed_height)
            elif placement_mode == 'scale':
                scale = self.config.getfloat(logo_section_name, 'LogoScaleFactor')
                min_w = self.config.getint(logo_section_name, 'MinLogoPixelWidth')
                max_w = self.config.getint(logo_section_name, 'MaxLogoPixelWidth')
                target_w = max(min_w, min(int(image_obj.width * scale), max_w))
                target_h = int(target_w * (logo_pil.height / logo_pil.width))
                logo_resized = logo_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
                margin = self.config.getfloat(logo_section_name, 'LogoMarginFactor')
                position = self.config.get(logo_section_name, 'LogoPosition').lower()
                margin_x, margin_y = int(image_obj.width * margin), int(image_obj.height * margin)
                if position == "top_right": pos = (image_obj.width - target_w - margin_x, margin_y)
                elif position == "bottom_left": pos = (margin_x, image_obj.height - target_h - margin_y)
                elif position == "bottom_right": pos = (image_obj.width - target_w - margin_x, image_obj.height - target_h - margin_y)
                else: pos = (margin_x, margin_y)
            image_obj.paste(logo_resized, pos, logo_resized)
            return image_obj
        except Exception as e:
            self.logger.error(f"Failed to apply logo from '{logo_section_name}': {e}", exc_info=True)
            return image_obj

    # --- دالة القص الجديدة ---
    def _apply_cropping(self, image_obj):
        if not self.config.getboolean('Cropping', 'Enabled', fallback=False):
            return image_obj

        try:
            img_width, img_height = image_obj.size

            # 1. القص بالنسبة المئوية (اختياري، يتم أولاً)
            pc_left = self.config.getfloat('Cropping', 'PercentageCropLeft', fallback=0.0)
            pc_top = self.config.getfloat('Cropping', 'PercentageCropTop', fallback=0.0)
            pc_right = self.config.getfloat('Cropping', 'PercentageCropRight', fallback=0.0)
            pc_bottom = self.config.getfloat('Cropping', 'PercentageCropBottom', fallback=0.0)

            crop_box_left = int(img_width * pc_left)
            crop_box_top = int(img_height * pc_top)
            crop_box_right = img_width - int(img_width * pc_right)
            crop_box_bottom = img_height - int(img_height * pc_bottom)

            # إذا تم تحديد أي قص بالنسبة المئوية، نقوم بالقص الآن
            if any([pc_left, pc_top, pc_right, pc_bottom]):
                if crop_box_right <= crop_box_left or crop_box_bottom <= crop_box_top:
                    self.logger.warning(f"Percentage crop results in invalid dimensions for image {img_width}x{img_height}. Skipping percentage crop.")
                else:
                    image_obj = image_obj.crop((crop_box_left, crop_box_top, crop_box_right, crop_box_bottom))
                    self.logger.info(f"Applied percentage crop. New dimensions: {image_obj.size[0]}x{image_obj.size[1]}.")
                    # تحديث أبعاد الصورة بعد القص المئوي
                    img_width, img_height = image_obj.size

            # 2. القص بالإحداثيات الثابتة (يتم بعد القص المئوي إذا وجد)
            crop_x = self.config.getint('Cropping', 'CropFromX', fallback=0)
            crop_y = self.config.getint('Cropping', 'CropFromY', fallback=0)
            crop_width = self.config.getint('Cropping', 'CropWidth', fallback=img_width)
            crop_height = self.config.getint('Cropping', 'CropHeight', fallback=img_height)

            # ضمان ألا تتجاوز قيم القص أبعاد الصورة الحالية
            crop_x = min(crop_x, img_width)
            crop_y = min(crop_y, img_height)
            crop_width = min(crop_width, img_width - crop_x)
            crop_height = min(crop_height, img_height - crop_y)

            # التأكد من أن الأبعاد ليست سالبة
            crop_width = max(0, crop_width)
            crop_height = max(0, crop_height)

            # حساب الصندوق (left, upper, right, lower)
            left = crop_x
            upper = crop_y
            right = crop_x + crop_width
            lower = crop_y + crop_height

            # التأكد من أن منطقة القص صالحة
            if right <= left or lower <= upper:
                self.logger.warning(f"Defined crop area ({left},{upper},{right},{lower}) is invalid for image {img_width}x{img_height}. Skipping fixed crop.")
                return image_obj

            image_obj = image_obj.crop((left, upper, right, lower))
            self.logger.info(f"Applied fixed crop. New dimensions: {image_obj.size[0]}x{image_obj.size[1]}.")
            return image_obj

        except Exception as e:
            self.logger.error(f"Failed to apply cropping: {e}", exc_info=True)
            return image_obj

    def process_image_with_logo(self, image_url):
        try:
            self.logger.info(f"Downloading image: {image_url[:100]}...")
            response = requests.get(image_url, headers={'User-Agent': self.user_agent}, stream=True, timeout=self.request_timeout, verify=False)
            response.raise_for_status()
            processed_image = Image.open(io.BytesIO(response.content))
            
            # --- تطبيق القص هنا قبل تحويل RGB أو الشعارات ---
            processed_image = self._apply_cropping(processed_image)

            if self.output_format == 'JPEG' and processed_image.mode != 'RGB':
                processed_image = processed_image.convert('RGB')
            processed_image = self._apply_logo(processed_image, 'Logo1')
            processed_image = self._apply_logo(processed_image, 'Logo2')
            buffer = io.BytesIO()
            save_opts = {'quality': self.output_quality, 'optimize': True} if self.output_format == 'JPEG' else {}
            processed_image.save(buffer, format=self.output_format, **save_opts)
            final_bytes = buffer.getvalue()
            self.logger.info(f"Image processed. Final size: {len(final_bytes)/1024:.2f}KB.")
            return final_bytes
        except requests.exceptions.SSLError as e:
            self.logger.error(f"SSL Error downloading image {image_url}. Skipping image. Error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error processing image {image_url}: {e}", exc_info=True)
            return None

    def upload_image_to_hosting(self, image_bytes, suggested_filename="image.jpg"):
        if not image_bytes:
            self.logger.error("No image bytes to upload.")
            return None
        api_key = self.config.get('ImageHosting_ImgBB', 'ApiKey', fallback=None)
        if not api_key or 'YOUR_IMGBB_API_KEY' in api_key:
            self.logger.critical("ImgBB API key is not configured in config.ini. Cannot upload images.")
            return None
        upload_url = self.config.get('ImageHosting_ImgBB', 'UploadUrl')
        upload_timeout = self.config.getint('ImageHosting_ImgBB', 'UploadTimeout')
        try:
            self.logger.info(f"Uploading image to ImgBB ({upload_url}) to get temporary link for Blogger...")
            files = {'image': (os.path.basename(suggested_filename), image_bytes)}
            payload = {'key': api_key}
            response = requests.post(
                upload_url, 
                files=files, 
                data=payload, 
                timeout=upload_timeout,
                verify=False
            )
            response.raise_for_status()
            response_data = response.json()
            if response_data.get('success'):
                hosted_url = response_data['data']['url'].replace('https://', 'http://')
                self.logger.info(f"Image temporarily available at: {hosted_url}. Blogger will now fetch it.")
                return hosted_url
            else:
                error_msg = response_data.get('error', {}).get('message', 'Unknown ImgBB error')
                self.logger.error(f"Failed to upload to ImgBB: {error_msg}")
                return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error connecting to ImgBB: {e}", exc_info=True)
            return None