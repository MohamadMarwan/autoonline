import streamlit as st
import json
import subprocess
import shlex
import time
import os
import tempfile
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
import sys

# استيراد السكربتات المساعدة
from bot_scripts.extractor import links_extractor
from bot_scripts.creator import image_creator
import toml

# --- الإعدادات الأساسية ---
LOG_DIR = 'logs'
IS_CLOUD_ENVIRONMENT = hasattr(st, 'secrets')

# --- دوال مساعدة لإدارة الإعدادات والسجلات ---
def load_config():
    if IS_CLOUD_ENVIRONMENT:
        try:
            return st.secrets["app_config"].to_dict()
        except KeyError:
            st.error("خطأ فادح: قسم [app_config] غير موجود في Streamlit Secrets.")
            return None
    else:
        secrets_path = os.path.join(".streamlit", "secrets.toml")
        try:
            if not os.path.exists(secrets_path):
                if os.path.exists('app_config.json'):
                    with open('app_config.json', 'r', encoding='utf-8') as f:
                        return json.load(f)
                st.error(f"ملف الإعدادات '{secrets_path}' غير موجود.")
                return None
            
            parsed_toml = toml.load(secrets_path)
            return parsed_toml.get("app_config", {})
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الإعدادات المحلي: {e}")
            return None

def save_config(config_data):
    if IS_CLOUD_ENVIRONMENT:
        st.warning("لا يمكن حفظ التغييرات تلقائيًا في بيئة النشر السحابية."); return False
    
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    try:
        full_config = toml.load(secrets_path)
        # دمج التغييرات بدلاً من الكتابة فوق كل شيء
        if 'app_config' not in full_config:
            full_config['app_config'] = {}
        full_config['app_config'].update(config_data)
        
        with open(secrets_path, 'w', encoding='utf-8') as f:
            toml.dump(full_config, f)
        st.success("تم حفظ التغييرات بنجاح في secrets.toml!"); return True
    except Exception as e:
        st.error(f"فشل حفظ الإعدادات في secrets.toml: {e}"); return False

def run_script_and_show_output(command, username, task_name):
    os.makedirs(LOG_DIR, exist_ok=True); timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(LOG_DIR, f"{username}_{task_name}_{timestamp}.log")
    log_placeholder = st.empty(); log_output = f"--- بدء السجل في {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n"
    log_placeholder.code(log_output, language='bash')
    try:
        with open(log_filename, 'w', encoding='utf-8') as log_file:
            log_file.write(log_output); args = shlex.split(command); my_env = os.environ.copy()
            my_env['PYTHONIOENCODING'] = 'utf-8'
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', env=my_env)
            for line in iter(process.stdout.readline, ''):
                log_output += line; log_file.write(line); log_placeholder.code(log_output, language='bash')
            process.wait(); return process.returncode
    except Exception as e:
        error_message = f"\n!!! خطأ فادح: {e} !!!\n"; st.error(error_message)
        with open(log_filename, 'a', encoding='utf-8') as log_file: log_file.write(error_message)
        return 1

# --- صفحات الواجهة ---
def login_page():
    st.header("🔑 تسجيل الدخول إلى لوحة التحكم")
    username = st.text_input("اسم المستخدم").lower()
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        config = load_config()
        users = config.get('users', {})
        if username in users and users[username].get('password') == password:
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.success("تم تسجيل الدخول بنجاح!"); time.sleep(1); st.rerun()
        else:
            st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")

def admin_dashboard():
    st.title("👑 لوحة تحكم المشرف")
    config = load_config()
    if not config: return
    
    st.subheader("👥 إدارة أداء المستخدمين")
    users_data = config.get('users', {})
    for username, data in users_data.items():
        if username == 'admin': continue
        with st.expander(f"المستخدم: {username} | المقالات: {data.get('post_count', 0)}"):
            st.write(f"**الأرباح:** ${data.get('earnings', 0.0):.2f} | **التقييم:** {data.get('rating', 'N/A')}")
            st.markdown("---")
            new_earnings = st.number_input("تحديد/تعديل الأرباح:", value=float(data.get('earnings', 0.0)), step=0.01, format="%.2f", key=f"earn_{username}")
            new_rating = st.text_input("تحديد/تعديل التقييم:", value=data.get('rating', ''), key=f"rate_{username}")
            if st.button("💾 حفظ التغييرات لهذا المستخدم", key=f"save_{username}"):
                users_data[username]['earnings'] = new_earnings
                users_data[username]['rating'] = new_rating
                if save_config({'users': users_data}):
                    st.success(f"تم تحديث بيانات {username} بنجاح!"); time.sleep(1); st.rerun()

    st.markdown("---")
    st.subheader("🛠️ إدارة الحسابات")
    with st.expander("إضافة أو حذف مستخدم"):
        st.write("قسم إدارة المستخدمين الكامل يأتي هنا.")

def user_dashboard():
    username = st.session_state['username']
    config = load_config()
    if not config: return
    user_data = config.get('users', {}).get(username, {})

    st.sidebar.title(f"👋 أهلاً بك، {username}")
    st.sidebar.markdown("---"); st.sidebar.subheader("📊 نظرة عامة")
    st.sidebar.metric(label="إجمالي المقالات", value=user_data.get('post_count', 0))
    st.sidebar.metric(label="إجمالي الأرباح", value=f"${user_data.get('earnings', 0.0):.2f}")
    st.sidebar.markdown(f"**التقييم الحالي:** {user_data.get('rating', 'N/A')}")
    st.sidebar.markdown("---")
    
    page_options = ["🖼️ صانع الصور الإخبارية", "📝 نشر مقالات", "🔗 استخراج الروابط", "✨ تنظيف المقالات"]
    if not IS_CLOUD_ENVIRONMENT:
        page_options.extend(["⚙️ إعدادات النشر", "⚙️ إعدادات التنظيف"])
    page_options.append("💰 الأرباح والتقييم")
    
    page = st.sidebar.radio("اختر المهمة", page_options)

    st.sidebar.markdown("---")
    if st.sidebar.button("تسجيل الخروج"):
        del st.session_state['logged_in']; del st.session_state['username']; st.rerun()

    credential_path = user_data.get('credential_path')
    blogger_settings = user_data.get('blogger_settings')
    telegram_settings = user_data.get('telegram_settings')
    
    page_error = None
    if page in ["📝 نشر مقالات", "✨ تنظيف المقالات"] and not credential_path: page_error = "خطأ: لم يتم تعيين مسار المصادقة لهذا المستخدم."
    elif page == "🔗 استخراج الروابط" and (not blogger_settings or not blogger_settings.get('blog_id') or not blogger_settings.get('api_key')): page_error = "خطأ: إعدادات بلوجر (BLOG_ID و API_KEY) غير معينة لحسابك."
    elif page == "🖼️ صانع الصور الإخبارية" and (not telegram_settings or not telegram_settings.get('bot_token') or not telegram_settings.get('channel_id')): page_error = "خطأ: إعدادات تليجرام (bot_token و channel_id) غير معينة لحسابك."
    
    if page_error: st.error(f"{page_error} يرجى مراجعة المشرف."); return

    if page == "🖼️ صانع الصور الإخبارية":
        st.title("🖼️ صانع الصور الإخبارية")
        st.info("حوّل الأخبار إلى صور احترافية وانشرها مباشرة إلى تليجرام.")
        with st.form("image_creator_form"):
            st.subheader("الخطوة 1: اختر التصميم والقالب")
            design_choice = st.selectbox("اختر نوع التصميم:", [("تصميم كلاسيكي", "classic"), ("تصميم سينمائي", "cinematic")], format_func=lambda x: x[0])
            template_options = {key: value["name"] for key, value in image_creator.NEWS_TEMPLATES.items()}
            template_key = st.selectbox("اختر نوع الخبر:", options=template_options.keys(), format_func=lambda k: template_options[k])
            st.subheader("الخطوة 2: أدخل المحتوى")
            content_type = st.radio("اختر طريقة الإدخال:", [("إدخال روابط", "link"), ("إدخال نصوص", "text")], format_func=lambda x: x[0], horizontal=True)
            prompt = "روابط الأخبار" if content_type[1] == 'link' else "نصوص الأخبار"
            news_items_text = st.text_area(f"أدخل {prompt} (كل عنصر في سطر):", height=200)
            submitted = st.form_submit_button("🚀 ابدأ الإنشاء والإرسال")
        if submitted:
            news_items = [line.strip() for line in news_items_text.splitlines() if line.strip()]
            if not news_items: st.warning("الرجاء إدخال رابط أو نص واحد على الأقل.")
            else:
                st.subheader("سجل المعالجة"); log_placeholder = st.empty(); log_output = ""
                def status_callback(message, level="info"):
                    nonlocal log_output
                    timestamp = datetime.now().strftime("%H:%M:%S"); formatted_message = f"[{timestamp}] {message}"
                    log_output += formatted_message + "\n"; log_placeholder.code(log_output, language='bash')
                with st.spinner(f"جاري معالجة {len(news_items)} عنصر..."):
                    asyncio.run(image_creator.process_and_send_batch(
                        bot_token=telegram_settings['bot_token'], channel_id=telegram_settings['channel_id'],
                        design_choice=design_choice[1], template_key=template_key,
                        news_items=news_items, content_type=content_type[1], status_callback=status_callback))

    elif page == "📝 نشر مقالات":
        st.title("📝 نشر مقالات جديدة عبر الروابط")
        urls_text = st.text_area("الروابط:", height=200)
        st.subheader("🏷️ التصنيفات (Labels)")
        st.info("أدخل التصنيفات مفصولة بفاصلة ( , ). اترك الحقل فارغًا للاستخراج التلقائي.")
        labels_text = st.text_input("تصنيفات مخصصة:", placeholder="أخبار, سوريا, رياضة")
        if st.button("🚀 ابدأ النشر"):
            if urls_text.strip():
                urls = [url.strip() for url in urls_text.splitlines() if url.strip()]
                labels_command_part = ""
                if labels_text.strip():
                    custom_labels = [label.strip() for label in labels_text.split(',') if label.strip()]
                    if custom_labels: labels_command_part = f"--labels {' '.join(shlex.quote(lbl) for lbl in custom_labels)}"
                user_pub_rules_raw = user_data.get('publishing_rules', {})
                user_pub_rules_dict = json.loads(json.dumps(user_pub_rules_raw))
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as tmp:
                    json.dump(user_pub_rules_dict, tmp, ensure_ascii=False); rules_file_path = tmp.name
                command = (f"python bot_scripts/scraper/main.py --creds-path {credential_path} --urls {' '.join(shlex.quote(u) for u in urls)} {labels_command_part} --rules-file \"{rules_file_path}\"")
                return_code = run_script_and_show_output(command, username, "publish")
                os.remove(rules_file_path)
                if return_code == 0:
                    st.success("🎉 انتهت عملية النشر بنجاح!")
                    if not IS_CLOUD_ENVIRONMENT:
                        current_config = load_config(); users_data = current_config.get('users', {})
                        users_data[username]['post_count'] += len(urls)
                        save_config({'users': users_data})
                else: st.error("حدث خطأ أثناء النشر.")
            else: st.warning("الرجاء إدخال رابط واحد على الأقل.")
            
    elif page == "🔗 استخراج الروابط":
        st.title("🔗 استخراج روابط المقالات")
        blog_id = blogger_settings['blog_id']; api_key = blogger_settings['api_key']
        st.info("استخدم الخيارات أدناه لسحب الروابط من مدونتك وحفظها في ملفات نصية.")
        extraction_type = st.selectbox("اختر نوع الاستخراج:", ["اختر...", "استخراج روابط قسم معين", "استخراج روابط جميع الأقسام", "استخراج أحدث الروابط"])
        if extraction_type == "استخراج روابط قسم معين":
            with st.spinner("جاري جلب قائمة الأقسام..."): categories = links_extractor.get_all_categories(blog_id, api_key)
            if categories:
                selected_category = st.selectbox("اختر القسم:", categories)
                max_links = st.number_input("أقصى عدد (0 للكل):", min_value=0, value=0)
                if st.button("🚀 ابدأ الاستخراج"):
                    with st.spinner(f"جاري استخراج روابط قسم '{selected_category}'..."):
                        result = links_extractor.extract_specific_category_links(blog_id, api_key, selected_category, max_links if max_links > 0 else None)
                        st.success("انتهت العملية!"); st.code(result, language='bash')
            else: st.warning("لم يتم العثور على أي أقسام في المدونة.")
        elif extraction_type == "استخراج روابط جميع الأقسام":
            max_links = st.number_input("أقصى عدد لكل قسم (0 للكل):", min_value=0, value=10)
            if st.button("🚀 ابدأ استخراج الكل"):
                with st.spinner("جاري استخراج الروابط من جميع الأقسام..."):
                    result = links_extractor.extract_all_categories_links(blog_id, api_key, max_links if max_links > 0 else None)
                    st.success("انتهت العملية!"); st.markdown(result.replace("\n", "\n\n"))
        elif extraction_type == "استخراج أحدث الروابط":
            max_links = st.number_input("أدخل عدد أحدث الروابط:", min_value=1, value=20)
            if st.button("🚀 ابدأ الاستخراج"):
                with st.spinner(f"جاري استخراج أحدث {max_links} رابط..."):
                    result = links_extractor.extract_latest_links(blog_id, api_key, max_links)
                    st.success("انتهت العملية!"); st.code(result, language='bash')

    elif page == "✨ تنظيف المقالات":
        st.title("✨ تنظيف وتنسيق المقالات الأخيرة")
        user_blogs = user_data.get('blogs', [])
        if not user_blogs: st.warning("لا توجد مدونات مخصصة لك."); return
        blog_options = {f"{b.get('name', 'N/A')} ({b.get('id', 'N/A')})": b.get('id') for b in user_blogs}
        selected_blog_display = st.selectbox("اختر المدونة:", options=blog_options.keys())
        selected_blog_id = blog_options[selected_blog_display]
        post_limit = st.number_input("كم عدد المقالات؟", 1, 50, 12)
        if st.button("🧹 ابدأ التنظيف"):
            user_rules_raw = user_data.get('cleaning_rules', {}); user_rules_dict = json.loads(json.dumps(user_rules_raw))
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as tmp:
                json.dump(user_rules_dict, tmp, ensure_ascii=False); rules_file_path = tmp.name
            command = (f'python bot_scripts/cleaner/clean_posts.py --blog-id "{selected_blog_id}" --creds-path "{credential_path}" --limit {post_limit} --rules-file "{rules_file_path}"')
            return_code = run_script_and_show_output(command, username, "clean")
            os.remove(rules_file_path)
            if return_code == 0: st.success("🎉 انتهت عملية التنظيف بنجاح!")
            else: st.error("حدث خطأ أثناء التنظيف.")

    elif page == "⚙️ إعدادات النشر":
        st.title("⚙️ إعدادات النشر المخصصة")
        st.info("القواعد هنا سيتم تطبيقها على محتوى المقال **أثناء عملية النشر**.")
        users_data = config.get('users', {})
        pub_rules_raw = users_data.get(username, {}).get('publishing_rules', {"replacements": []})
        pub_rules = json.loads(json.dumps(pub_rules_raw))
        st.subheader("🔄 عبارات البحث والاستبدال للنشر")
        replacements_list = pub_rules.get('replacements', [])
        replacements_text = "\n".join([f"{item['find']} >> {item['replace_with']}" for item in replacements_list])
        new_replacements_text = st.text_area("قائمة الاستبدال:", value=replacements_text, height=250, key="pub_replace")
        if st.button("💾 حفظ إعدادات النشر"):
            updated_replacements = []
            for line in new_replacements_text.splitlines():
                if '>>' in line:
                    find_phrase, replace_phrase = line.split('>>', 1)
                    updated_replacements.append({"find": find_phrase.strip(), "replace_with": replace_phrase.strip()})
            users_data[username]['publishing_rules'] = {"replacements": updated_replacements}
            if save_config({'users': users_data}): st.rerun()

    elif page == "⚙️ إعدادات التنظيف":
        st.title("⚙️ إعدادات التنظيف المخصصة")
        users_data = config.get('users', {})
        cleaning_rules_raw = users_data.get(username, {}).get('cleaning_rules', {"remove_symbols": [], "replacements": []})
        user_rules = json.loads(json.dumps(cleaning_rules_raw))
        st.subheader("🗑️ الرموز والكلمات المراد حذفها")
        remove_text = "\n".join(user_rules.get('remove_symbols', []))
        new_remove_text = st.text_area("قائمة الحذف:", value=remove_text, height=150)
        st.subheader("🔄 عبارات البحث والاستبدال")
        replacements_list = user_rules.get('replacements', [])
        replacements_text = "\n".join([f"{item['find']} >> {item['replace_with']}" for item in replacements_list])
        new_replacements_text = st.text_area("قائمة الاستبدال:", value=replacements_text, height=250)
        if st.button("💾 حفظ إعدادات التنظيف"):
            updated_remove_list = [line.strip() for line in new_remove_text.splitlines() if line.strip()]
            updated_replacements = []
            for line in new_replacements_text.splitlines():
                if '>>' in line:
                    find_phrase, replace_phrase = line.split('>>', 1)
                    updated_replacements.append({"find": find_phrase.strip(), "replace_with": replace_phrase.strip()})
            users_data[username]['cleaning_rules'] = {"remove_symbols": updated_remove_list, "replacements": updated_replacements}
            if save_config({'users': users_data}): st.rerun()

    elif page == "💰 الأرباح والتقييم":
        st.title("💰 الأرباح والتقييم")
        st.info("هذه الصفحة تعرض ملخصًا لأدائك كما حدده المشرف.")
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي المقالات", user_data.get('post_count', 0))
        col2.metric("إجمالي الأرباح", f"${user_data.get('earnings', 0.0):.2f}")
        col3.metric("التقييم", user_data.get('rating', 'N/A'))

# --- المنطق الرئيسي للتطبيق ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if st.session_state.get('logged_in'):
    username = st.session_state.get('username')
    if username == 'admin':
        admin_dashboard()
    else:
        user_dashboard()
else:
    login_page()
