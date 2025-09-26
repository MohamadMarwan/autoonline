# core/blogger_client.py

import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from utils.logger_config import setup_logger

logger = setup_logger(__name__)
SCOPES = ['https://www.googleapis.com/auth/blogger']

class BloggerClient:
    """
    عميل للتفاعل مع Blogger API، مهيأ للعمل مع نظام متعدد المستخدمين.
    """
    # ✅ --- التعديل الرئيسي هنا: تغيير دالة __init__ ---
    # تم تغيير الدالة لتقبل creds_path كوسيط إلزامي.
    def __init__(self, config, creds_path):
        self.config = config
        
        # ✅ يتم الآن بناء مسارات المصادقة ديناميكيًا بناءً على المستخدم
        # بدلاً من قراءتها بشكل ثابت من ملف config.ini.
        self.credentials_file = os.path.join(creds_path, 'client_secret.json')
        self.token_file = os.path.join(creds_path, 'token.json')
        
        # إعدادات المدونة العامة تبقى كما هي من ملف config.ini
        blog_id_raw = self.config.get('BloggerAPI', 'BlogID', fallback=None)
        if not blog_id_raw:
            msg = "BlogID is not configured in config.ini under [BloggerAPI]."
            logger.critical(msg)
            raise ValueError(msg)
        
        self.blog_id = blog_id_raw.strip()
        if not self.blog_id.isdigit():
            msg = f"Configured BlogID '{self.blog_id}' is not a valid number."
            logger.critical(msg)
            raise ValueError(msg)
        logger.info(f"Using BlogID: {self.blog_id} for Blogger operations.")
            
        self.service = self._get_blogger_service()

    def _get_blogger_service(self):
        """
        يقوم بإنشاء أو تحديث المصادقة باستخدام المسارات الديناميكية.
        """
        creds = None
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            except Exception as e:
                logger.warning(f"Error loading token from {self.token_file}: {e}. Re-authenticating.")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Credentials expired. Refreshing token...")
                    creds.refresh(Request())
                    logger.info("Token refreshed successfully.")
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}. Removing invalid token and re-authenticating.")
                    try: 
                        os.remove(self.token_file)
                    except OSError as ose:
                        logger.warning(f"Could not remove invalid token file {self.token_file}: {ose}")
                    creds = None
            
            # إذا لم نتمكن من تحديث الرمز، أو لم يكن موجودًا من الأساس
            if not creds:
                logger.info(f"Starting new authentication flow using {self.credentials_file}.")
                if not os.path.exists(self.credentials_file):
                    msg = f"Client secrets file '{self.credentials_file}' not found."
                    logger.critical(msg)
                    raise FileNotFoundError(msg)
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)
            
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
                logger.info(f"Credentials saved to {self.token_file}")
            except Exception as e:
                logger.error(f"Error saving token to {self.token_file}: {e}")
        
        if not creds:
            logger.critical("Failed to obtain valid credentials for Blogger API.")
            return None

        try:
            service = build('blogger', 'v3', credentials=creds, cache_discovery=False)
            logger.info("Blogger service client initialized successfully.")
            return service
        except Exception as e:
            logger.critical(f"Failed to build Blogger service: {e}", exc_info=True)
            return None

    def create_post(self, title, content_html, labels=None, is_draft=False):
        """
        إنشاء تدوينة جديدة في المدونة المحددة.
        """
        if not self.service:
            logger.error("Blogger service not available. Cannot create post.")
            return None

        body = {
            'blog': {'id': self.blog_id},
            'title': title,
            'content': content_html
        }
        if labels:
            body['labels'] = [str(lbl).strip() for lbl in labels if str(lbl).strip()]
        
        try:
            logger.info(f"Creating post: '{title[:60]}...' (Draft: {is_draft})")
            posts_service = self.service.posts()
            request = posts_service.insert(
                blogId=self.blog_id, 
                body=body, 
                isDraft=is_draft,
                fetchImages=True
            )
            created_post = request.execute()
            post_url = created_post.get('url')
            logger.info(f"Post created successfully: {post_url}")
            return post_url
        except Exception as e:
            logger.error(f"Failed to create post on Blogger: {e}", exc_info=True)
            if hasattr(e, 'content'):
                try:
                    error_details = e.content.decode()
                    logger.error(f"Blogger API error details: {error_details}")
                except: pass
            return None

    # ... بقية الدوال مثل get_blog_info يمكن أن تبقى كما هي ...