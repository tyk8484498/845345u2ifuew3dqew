import ctypes
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import requests
import telebot
from PIL import Image

TELEGRAM_TOKEN = "8204897259:AAFtGl7OsWCPoPV6ys0c0drC19yjjvYEVIw"
OWNER_ID = -233629370
ADMIN_IDS = [1661627681, 1904861420, 2063478233]
ADMIN_PASSWORD_HASH = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
POSTS_FILE = "parsing/posts.json"
LIKES_FILE = "parsing/likes.json"
TOKEN_FILE = "token.txt"
TOKEN_TIME_FILE = "token_time.txt"
MEDIA_DIR = "parsing/media"
THUMBNAIL_DIR = "parsing/thumbnails"
USER_MESSAGES_FILE = "user_messages.json"
BUTTONS_FILE = "custom_buttons.json"
CONFIG_FILE = "config.json"
QR_DIR = "qr"

def launch_edge_simple():
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    subprocess.Popen([
        edge_path,
        "--edge-kiosk-type=fullscreen",
        "--disable-pinch",
        "--disable-features=msEdgePreload",
        "--no-first-run",
        "--kiosk",
        "http://localhost:8000"
    ])

# Конфигурация по умолчанию
DEFAULT_CONFIG = {
    "theme": "winter",
    "timer_date": "01.01.2026",
    "timer_title": "До Нового Года",
    "news_visible": True,
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)
parsing_lock = threading.Lock()
is_parsing = False
parsing_enabled = True  # По умолчанию парсинг включен
user_states = {}

# Переменная для управления браузером
browser_process = None
browser_opened_site = None
last_opened_window = None


def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Обновляем конфиг, если добавлены новые поля
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
    except Exception:
        pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def sanitize_filename(filename):
    return "".join(c for c in filename if c.isalnum() or c in "._-")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password):
    return hash_password(password) == ADMIN_PASSWORD_HASH


def send_to_admins(message):
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, message)
        except Exception:
            pass


def get_seasonal_elements(theme):
    elements = {
        "winter": {
            "background": "linear-gradient(135deg, #0d47a1 0%, #1976d2 50%, #bbdefb 100%)",
            "decorations": """
                <!-- Снежинки -->
                <div class="snowflakes" id="snowflakes"></div>
                </div>
            """,
            "button_theme": {
                "background": "linear-gradient(135deg, #1565c0 0%, #bbdefb 100%)",
                "border": "2px solid #bbdefb",
                "icon": "❄️",
            },
            "timer_icon": "⛄",
        },
        "spring": {
            "background": "linear-gradient(135deg, #4caf50 0%, #8bc34a 50%, #cddc39 100%)",
            "decorations": """
                <!-- Весенние элементы -->
                <div class="spring-decorations">
                    <div class="flower flower-1">🌸</div>
                    <div class="flower flower-2">🌷</div>
                    <div class="flower flower-3">💮</div>
                    <div class="butterfly">🦋</div>
                </div>
                <!-- Весенние деревья -->
                <div class="spring-trees">
                    <div class="tree tree-left"></div>
                    <div class="tree tree-right"></div>
                </div>
            """,
            "button_theme": {
                "background": "linear-gradient(135deg, #66bb6a 0%, #cddc39 100%)",
                "border": "2px solid #8bc34a",
                "icon": "🌱",
            },
            "timer_icon": "🌱",
        },
        "summer": {
            "background": "linear-gradient(135deg, #ff9800 0%, #ffc107 50%, #ffeb3b 100%)",
            "decorations": """
                <!-- Летние элементы -->
                <div class="summer-decorations">
                    <div class="sun" id="movable-sun">☀️</div>
                    <div class="palm-tree">🌴</div>
                    <div class="ice-crem">🍦</div>
                </div>
                <!-- Летние деревья -->
                <div class="summer-trees">
                    <div class="tree tree-1"></div>
                    <div class="tree tree-2"></div>
                </div>
            """,
            "button_theme": {
                "background": "linear-gradient(135deg, #ff9800 0%, #ffeb3b 100%)",
                "border": "2px solid #ffc107",
                "icon": "☀️",
            },
            "timer_icon": "🌞",
        },
        "autumn": {
            "background": "linear-gradient(135deg, #795548 0%, #ff5722 50%, #ff9800 100%)",
            "decorations": """
                <!-- Осенние элементы -->
                <div class="autumn-decorations">
                    <div class="leaf leaf-1">🍂</div>
                    <div class="leaf leaf-2">🍁</div>
                    <div class="leaf leaf-3">🍃</div>
                    <div class="mushroom">🍄</div>
                </div>
                <!-- Осенние деревья -->
                <div class="autumn-trees">
                    <div class="tree tree-1"></div>
                    <div class="tree tree-2"></div>
                </div>
            """,
            "button_theme": {
                "background": "linear-gradient(135deg, #ff5722 0%, #ff9800 100%)",
                "border": "2px solid #ff9800",
                "icon": "🍂",
            },
            "timer_icon": "🍁",
        },
    }
    return elements.get(theme, elements["winter"])


def save_token(token):
    try:
        os.makedirs(os.path.dirname(TOKEN_FILE) or ".", exist_ok=True)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(token)
        with open(TOKEN_TIME_FILE, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        if os.path.exists(TOKEN_TIME_FILE):
            with open(TOKEN_TIME_FILE, "r", encoding="utf-8") as f:
                token_time = float(f.read().strip())
                if time.time() - token_time > 23 * 3600:
                    os.remove(TOKEN_FILE)
                    os.remove(TOKEN_TIME_FILE)
                    return None
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def get_vk_token_via_browser():
    auth_url = "https://oauth.vk.com/authorize?client_id=54287856&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=wall,photos&response_type=token&v=5.199"
    print(f"""
🔗 Откройте эту ссылку в браузере:
{auth_url}""")
    print("""
📋 После авторизации скопируйте URL из адресной строки браузера и вставьте сюда:""")
    try:
        token_url = input("Введите URL: ").strip()
        if not token_url:
            print("❌ URL не был введен")
            return None
        if "access_token=" in token_url:
            if "#" in token_url:
                fragment = token_url.split("#", 1)[-1]
                params = parse_qs(fragment)
                if "access_token" in params:
                    token = params["access_token"][0]
                    print(f"✅ Токен получен успешно (длина: {len(token)})")
                    return token
            else:
                parsed = urlparse(token_url)
                params = parse_qs(parsed.query)
                if "access_token" in params:
                    token = params["access_token"][0]
                    print(f"✅ Токен получен успешно (длина: {len(token)})")
                    return token
        print("❌ Не удалось извлечь токен из URL")
        return None
    except KeyboardInterrupt:
        print("""
❌ Ввод прерван пользователем""")
        return None
    except Exception as e:
        print(f"❌ Ошибка при получении токена: {e}")
        return None


def ensure_token():
    token = load_token()
    if token:
        print("✅ Токен загружен из файла")
        return token
    print("🔑 Токен не найден, запуск процесса получения...")
    token = get_vk_token_via_browser()
    if token:
        save_token(token)
        print("✅ Токен сохранен в файл")
        return token
    else:
        print("❌ Не удалось получить VK токен")
        return None


def download_file(url, filepath):
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки файла {url}: {e}")
        return False


def create_thumbnail(input_path, output_path, size=(200, 150)):
    try:
        with Image.open(input_path) as img:
            img.thumbnail(size)
            img.save(output_path, "JPEG", quality=70)
        return True
    except Exception as e:
        print(f"❌ Ошибка создания превью {input_path}: {e}")
        return False


def truncate_text(text, max_length=20):
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def load_likes():
    try:
        if os.path.exists(LIKES_FILE):
            with open(LIKES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_likes(likes_data):
    try:
        os.makedirs("parsing", exist_ok=True)
        with open(LIKES_FILE, "w", encoding="utf-8") as f:
            json.dump(likes_data, f, ensure_ascii=False)
        return True
    except Exception:
        return False


def load_custom_buttons():
    try:
        if os.path.exists(BUTTONS_FILE):
            with open(BUTTONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_custom_buttons(buttons_data):
    try:
        with open(BUTTONS_FILE, "w", encoding="utf-8") as f:
            json.dump(buttons_data, f, ensure_ascii=False)
        return True
    except Exception:
        return False


@bot.message_handler(func=lambda message: message.text == "📰 Скрыть новости")
def handle_hide_news_button(message):
    global parsing_enabled  # Добавляем в начало функции
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    config = load_config()
    config["news_visible"] = False
    if save_config(config):
        # При скрытии новостей автоматически выключаем парсинг
        parsing_enabled = False
        bot.reply_to(message, "✅ Новости скрыты и парсинг отключен")
    else:
        bot.reply_to(message, "❌ Ошибка сохранения конфигурации")


@bot.message_handler(func=lambda message: message.text == "📰 Показать новости")
def handle_show_news_button(message):
    global parsing_enabled  # Добавляем в начало функции
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    config = load_config()
    config["news_visible"] = True
    if save_config(config):
        # При показе новостей автоматически включаем парсинг
        parsing_enabled = True
        bot.reply_to(message, "✅ Новости показаны и парсинг включен")
    else:
        bot.reply_to(message, "❌ Ошибка сохранения конфигурации")


def fetch_vk_posts():
    try:
        print("🚀 Начало парсинга...")
        existing_likes = load_likes()
        os.makedirs("parsing", exist_ok=True)
        for dir_path in [MEDIA_DIR, THUMBNAIL_DIR]:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
            os.makedirs(dir_path)
        token = ensure_token()
        if not token:
            print("❌ Токен не доступен")
            return False
        print("📡 Запрос к VK API...")
        url = "https://api.vk.com/method/wall.get"
        params = {
            "owner_id": OWNER_ID,
            "count": 30,
            "access_token": token.strip(),
            "v": "5.199",
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            error_msg = data["error"].get("error_msg", "Unknown error")
            print(f"❌ Ошибка VK API: {error_msg}")
            return False
        posts = data["response"]["items"]
        print(f"📝 Получено {len(posts)} постов")
        processed = []
        for post in posts[:15]:
            post_id = f"{post['owner_id']}_{post['id']}"
            date = datetime.fromtimestamp(post["date"]).strftime("%d %B %Y")
            text = post.get("text", "").replace("<br>", "\n")
            truncated_text = truncate_text(text, 20)
            photos = []
            for att in post.get("attachments", []):
                if att["type"] == "photo":
                    sizes = att["photo"]["sizes"]
                    largest = max(sizes, key=lambda s: s["width"] * s["height"])
                    photos.append(largest["url"])
            local_photos = []
            local_thumbnails = []
            for index, photo_url in enumerate(photos[:3]):
                safe_filename = sanitize_filename(f"photo_{post_id}_{index}.jpg")
                filepath = os.path.join(MEDIA_DIR, safe_filename)
                thumb_path = os.path.join(THUMBNAIL_DIR, safe_filename)
                if download_file(photo_url, filepath):
                    local_photos.append(f"/parsing/media/{safe_filename}")
                    if create_thumbnail(filepath, thumb_path):
                        local_thumbnails.append(f"/parsing/thumbnails/{safe_filename}")
            post_likes = existing_likes.get(post_id, 0)
            processed.append(
                {
                    "id": post_id,
                    "date": date,
                    "text": truncated_text,
                    "photos": local_photos,
                    "thumbnails": local_thumbnails,
                    "likes": post_likes,
                    "vk_url": f"https://vk.com/wall{post_id}",
                }
            )
        with open(POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(processed, f, ensure_ascii=False)
        print(f"✅ Новости обновлены: {len(processed)} постов")
        send_to_admins(f"✅ News updated: {len(processed)} posts")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка сети: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка парсинга: {str(e)}")
        return False


def fetch_vk_posts_with_retry(max_retries=3):
    global is_parsing, parsing_enabled  # Объявляем глобальные переменные в начале
    with parsing_lock:
        if is_parsing:
            print("⚠️ Парсинг уже выполняется")
            return False
        is_parsing = True

    try:
        config = load_config()
        # Если новости скрыты, парсинг выключается автоматически
        if not config.get("news_visible", True):
            parsing_enabled = False  # Теперь это работает, так как parsing_enabled объявлена как глобальная
            print("⚠️ Парсинг отключен, так как новости скрыты")
        else:
            parsing_enabled = True

        # Если парсинг отключен, просто проверяем наличие файла
        if not parsing_enabled:
            print("⚠️ Парсинг отключен, проверяем наличие файла с новостями")
            if os.path.exists(POSTS_FILE):
                try:
                    with open(POSTS_FILE, "r", encoding="utf-8") as f:
                        posts = json.load(f)
                    print(f"✅ Загружено {len(posts)} существующих постов")
                    return True
                except Exception as e:
                    print(f"❌ Ошибка загрузки существующих новостей: {e}")
            else:
                print("📝 Файл с новостями не найден, создаем пустой")
                try:
                    os.makedirs(os.path.dirname(POSTS_FILE) or ".", exist_ok=True)
                    with open(POSTS_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False)
                    print("✅ Создан пустой файл новостей")
                    return True
                except Exception as e:
                    print(f"❌ Ошибка создания файла: {e}")
            return False

        # Если парсинг включен, пытаемся обновить новости
        for attempt in range(max_retries):
            try:
                print(f"🔄 Попытка парсинга {attempt + 1}/{max_retries}")
                result = fetch_vk_posts()
                if result:
                    return True
                if attempt < max_retries - 1:
                    print(f"⏳ Повтор через 5 секунд...")
                    time.sleep(5)
            except Exception as e:
                print(f"❌ Ошибка при парсинге: {e}")
                if attempt < max_retries - 1:
                    print(f"⏳ Повтор через 5 секунд...")
                    time.sleep(5)
        return False
    finally:
        with parsing_lock:
            is_parsing = False


def simulate_button_press(button_id):
    try:
        custom_buttons = load_custom_buttons()
        if button_id in custom_buttons:
            url = custom_buttons[button_id]
            webbrowser.open(url)
            return f"🌐 Custom button {button_id}: {url}"
        buttons = {
            "1": ("https://www.school303.spb.ru/", "🌐 School website"),
            "2": ("https://edu.gov.ru/", "🏛️ Ministry of Education"),
            "3": ("https://k-obr.spb.ru/", "🏙️ Education Committee"),
            "4": ("https://it-cube.school303.spb.ru/", "💻 IT-Cube"),
            "5": ("https://vk.com/shillerpublic", "👥 VK group"),
        }
        if button_id in buttons:
            webbrowser.open(buttons[button_id][0])
            return buttons[button_id][1]
        else:
            return f"❌ Button {button_id} not found"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def add_custom_button(button_id, url):
    try:
        if not url.startswith(("http://", "https://")):
            return "❌ Invalid URL format"
        custom_buttons = load_custom_buttons()
        custom_buttons[button_id] = url
        if save_custom_buttons(custom_buttons):
            return f"✅ Custom button {button_id} added: {url}"
        return "❌ Save error"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def remove_custom_button(button_id):
    try:
        custom_buttons = load_custom_buttons()
        if button_id in custom_buttons:
            del custom_buttons[button_id]
            if save_custom_buttons(custom_buttons):
                return f"✅ Custom button {button_id} removed"
            return "❌ Save error"
        return f"❌ Button {button_id} not found"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def list_custom_buttons():
    try:
        custom_buttons = load_custom_buttons()
        if not custom_buttons:
            return "ℹ️ No custom buttons"
        result = "🎮 Custom buttons:\n"
        for btn_id, url in custom_buttons.items():
            result += f"{btn_id} - {url}\n"
        return result
    except Exception as e:
        return f"❌ Error: {str(e)}"


def safe_path_join(base_path, user_path):
    full_path = os.path.abspath(os.path.join(base_path, user_path))
    base_path_abs = os.path.abspath(base_path)
    if not full_path.startswith(base_path_abs):
        return None
    return full_path


def view_project_files(path="."):
    try:
        base_dir = os.path.abspath(".")
        safe_path = safe_path_join(base_dir, path)
        if not safe_path or not os.path.exists(safe_path):
            return f"❌ Path not exists: {path}"
        if os.path.isfile(safe_path):
            try:
                with open(safe_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    return f"📄 {path}:\n{content[:1000]}"
            except UnicodeDecodeError:
                return f"📄 {path}:\n[Binary file content not displayed]"
        result = f"📁 {path}:\n"
        items = os.listdir(safe_path)
        for item in items:
            item_path = os.path.join(safe_path, item)
            if os.path.isdir(item_path):
                result += f"📁 {item}/\n"
            else:
                size = os.path.getsize(item_path)
                result += f"📄 {item} ({size} bytes)\n"
        return result
    except Exception as e:
        return f"❌ Error: {str(e)}"


def modify_project_file(filepath, content, mode="w"):
    try:
        if mode not in ["w", "a"]:
            return "❌ Invalid mode"
        base_dir = os.path.abspath(".")
        safe_path = safe_path_join(base_dir, filepath)
        if not safe_path:
            return "❌ Invalid file path"
        os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
        with open(safe_path, mode, encoding="utf-8") as f:
            f.write(content)
        return f"✅ File {filepath} modified"
    except Exception as e:
        return f"❌ Error: {str(e)}"


def save_user_message(user_id, username, message):
    try:
        os.makedirs(os.path.dirname(USER_MESSAGES_FILE) or ".", exist_ok=True)
        messages = []
        if os.path.exists(USER_MESSAGES_FILE):
            with open(USER_MESSAGES_FILE, "r", encoding="utf-8") as f:
                messages = json.load(f)
        messages.append(
            {
                "user_id": user_id,
                "username": username[:50] if username else "Unknown",
                "message": message[:1000],
                "timestamp": datetime.now().isoformat(),
            }
        )
        with open(USER_MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False)
        return True
    except Exception:
        return False


def load_user_messages():
    try:
        if os.path.exists(USER_MESSAGES_FILE):
            with open(USER_MESSAGES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception:
        return []


def clear_user_messages():
    try:
        if os.path.exists(USER_MESSAGES_FILE):
            os.remove(USER_MESSAGES_FILE)
        return True
    except Exception:
        return False


def close_browser_tab():
    global browser_process, browser_opened_site

    print("🔧 Пытаемся закрыть вкладку браузера...")

    # Способ 1: Закрыть через subprocess
    if browser_process and browser_process.poll() is None:
        try:
            print("🔄 Закрываем через subprocess...")
            browser_process.terminate()
            browser_process.wait(timeout=2)
            browser_process = None
            browser_opened_site = None
            print("✅ Браузер закрыт через terminate")
            return True
        except Exception as e:
            print(f"❌ Ошибка при закрытии браузера: {e}")

    # Способ 2: Для Windows - закрыть через taskkill
    if sys.platform == "win64":
        try:
            print("🔄 Закрываем через taskkill...")
            subprocess.run(
                ["taskkill", "/F", "/IM", "chrome.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["taskkill", "/F", "/IM", "msedge.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["taskkill", "/F", "/IM", "firefox.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("✅ Браузеры закрыты через taskkill")
            return True
        except Exception as e:
            print(f"❌ Ошибка taskkill: {e}")


def open_site_with_control(url):
    global browser_process, browser_opened_site

    try:
        # Закрываем предыдущий браузер если он открыт
        if browser_process and browser_process.poll() is None:
            close_browser_tab()

        print(f"🌐 Открываем сайт: {url}")

        # Открываем новый браузер
        if sys.platform == "win32":
            # Для Windows используем start для открытия в новом окне
            browser_process = subprocess.Popen(
                f'start chrome --new-window "{url}"', shell=True
            )
        elif sys.platform == "darwin":
            # Для macOS
            browser_process = subprocess.Popen(["open", "-a", "Google Chrome", url])
        else:
            # Для Linux
            browser_process = subprocess.Popen(["google-chrome", "--new-window", url])

        browser_opened_site = url
        print(f"✅ Сайт открыт в контролируемом окне: {url}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при открытии сайта: {e}")
        # Пробуем обычный способ
        try:
            webbrowser.open(url)
            print(f"✅ Сайт открыт через webbrowser.open: {url}")
            return True
        except Exception as e2:
            print(f"❌ Ошибка webbrowser.open: {e2}")
            return False


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8"/>
  <title>Школа №303</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {
      --primary: #0d47a1;
      --primary-light: #1976d2;
      --white: #ffffff;
      --text: #f5f5f5;
      --glass-bg: rgba(255, 255, 255, 0.1);
      --glass-border: rgba(255, 255, 255, 0.2);
      --shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
      --shadow-hover: 0 12px 40px rgba(0, 0, 0, 0.3);
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: {{BACKGROUND}};
      background-attachment: fixed;
      color: var(--text);
      font-family: 'Segoe UI', sans-serif;
      overflow-x: hidden;
      min-height: 100vh;
    }
    .school-title {
      text-align: center;
      font-size: clamp(32px, 8vw, 56px);
      font-weight: 800;
      color: var(--white);
      text-shadow: 0 4px 12px rgba(0,0,0,0.4);
      padding-top: 40px;
      margin-bottom: 20px;
    }
    .buttons-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 25px;
      padding: 0 20px;
      margin-bottom: 30px;
      max-width: 1400px;
      margin: 0 auto 40px auto;
    }
    .row-wrapper {
      width: 100%;
      display: flex;
      justify-content: center;
      margin: 15px 0;
    }
    .row {
      display: flex;
      justify-content: center;
      gap: 20px;
      width: 100%;
    }
    .top-row .tile {
      width: min(320px, 90vw);
      min-height: 120px;
    }
    .middle-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      max-width: 1200px;
    }
    .middle-row .tile {
      width: min(320px, 90vw);
      min-height: 120px;
    }
    /* Нижний ряд с кнопками со сдвигом */
    .bottom-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      max-width: 1200px;
      position: relative;
    }
    .bottom-row .left-shift {
      transform: translateX(-30%);
      position: relative;
      z-index: 2;
    }
    .bottom-row .right-shift {
      transform: translateX(30%);
      position: relative;
      z-index: 2;
    }
    .center-circle {
      width: 200px;
      height: 200px;
      border-radius: 50%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background: rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(12px);
      box-shadow: var(--shadow);
      overflow: hidden;
      position: relative;
      z-index: 10;
    }
    .clock-time {
      font-size: 24px;
      font-weight: bold;
      color: white;
      text-shadow: 0 2px 8px rgba(0,0,0,0.3);
      line-height: 1.2;
      text-align: center;
    }
    .clock-date {
      font-size: 14px;
      color: #bbdefb;
      margin-top: 8px;
      text-align: center;
    }
    .tile {
  	background: var(--glass-bg);
  	border: 1px solid var(--glass-border);
  	border-radius: 16px;
  	padding: 20px 15px;
  	text-align: center;
  	cursor: pointer;
  	transition: all 0.4s;
  	backdrop-filter: blur(12px);
  	box-shadow: var(--shadow);
  	min-height: 120px;
  	display: flex;
  align-items: center;
  	justify-content: center;
  	width: min(320px, 90vw);
    }
    .tile:hover {
      background: rgba(255, 255, 255, 0.2);
      transform: translateY(-8px) scale(1.03);
      box-shadow: var(--shadow-hover);
    }
    .tile h3 {
      font-size: clamp(18px, 4vw, 22px);
      margin: 0;
      color: white;
    }
    .author-link-container {
      width: 100%;
      display: flex;
      justify-content: center;
      margin-top: 30px;
      padding: 20px;
    }
    .author-link {
      color: var(--white);
      text-decoration: none;
      font-size: 18px;
      font-weight: 600;
      padding: 15px 35px;
      border: 2px solid var(--white);
      border-radius: 50px;
      background: rgba(255,255,255,0.1);
      transition: all 0.3s ease;
      display: inline-block;
      backdrop-filter: blur(10px);
      box-shadow: var(--shadow);
    }
    .author-link:hover {
      background: rgba(255,255,255,0.3);
      transform: translateY(-3px);
      box-shadow: var(--shadow-hover);
    }
    /* Таймер */
    .custom-timer {
      position: fixed;
      bottom: 20px;
      left: 20px;
      background: rgba(255, 255, 255, 0.15);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 16px;
      padding: 15px;
      color: white;
      font-family: 'Segoe UI', sans-serif;
      z-index: 1000;
      cursor: move;
      user-select: none;
      min-width: 200px;
      min-height: 100px;
      max-width: 400px;
      max-height: 300px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
      resize: both;
      overflow: hidden;
    }
    .custom-timer h3 {
      font-size: 16px;
      margin-bottom: 10px;
      color: #ffeb3b;
      text-align: center;
    }
    .timer-display {
      font-size: 18px;
      font-weight: bold;
      text-align: center;
      color: #bbdefb;
      line-height: 1.4;
    }
    .timer-progress {
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 3px;
      margin-top: 10px;
      overflow: hidden;
    }
    .timer-progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #ff4081, #ffeb3b);
      border-radius: 3px;
      transition: width 0.3s ease;
    }
    /* Сезонные декорации */
    .seasonal-decorations {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 50;
    }
    /* Зимние элементы */
    .snowflakes {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 100;
    }
    .snowflake {
      position: absolute;
      top: -10px;
      color: white;
      font-size: 1em;
      text-shadow: 0 0 5px rgba(255,255,255,0.5);
      animation: fall linear forwards;
    }
    .winter-trees {
      position: fixed;
      bottom: 0;
      width: 100%;
      display: flex;
      justify-content: space-between;
      padding: 0 10%;
      z-index: 99;
      pointer-events: none;
    }
    .tree {
      width: 80px;
      height: 150px;
      position: relative;
    }
    .tree::before {
      content: '';
      position: absolute;
      bottom: 0;
      left: 50%;
      transform: translateX(-50%);
      width: 20px;
      height: 40px;
      background: #5d4037;
      border-radius: 3px;
    }
    .tree::after {
      content: '';
      position: absolute;
      bottom: 40px;
      left: 50%;
      transform: translateX(-50%);
      width: 0;
      height: 0;
      border-left: 40px solid transparent;
      border-right: 40px solid transparent;
      border-bottom: 100px solid #2e7d32;
      border-radius: 50% 50% 0 0;
    }
    .winter-trees .tree {
      transform: scale(0.8);
    }
    .autumn-trees .tree::after {
      border-bottom-color: #ff5722;
    }
    .summer-trees .tree::after {
      border-bottom-color: #388e3c;
    }
    .spring-trees .tree::after {
      border-bottom-color: #66bb6a;
    }
    /* Зимние огни */
    .winter-lights {
      position: fixed;
      top: 20px;
      width: 100%;
      display: flex;
      justify-content: center;
      gap: 40px;
      z-index: 101;
      pointer-events: none;
    }
    .light {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #ffeb3b;
      box-shadow: 0 0 10px #ffeb3b;
      animation: twinkle 2s infinite alternate;
    }
    .light-2 { animation-delay: 0.2s; background: #ff4081; box-shadow: 0 0 10px #ff4081; }
    .light-3 { animation-delay: 0.4s; background: #2196f3; box-shadow: 0 0 10px #2196f3; }
    .light-4 { animation-delay: 0.6s; background: #4caf50; box-shadow: 0 0 10px #4caf50; }
    .light-5 { animation-delay: 0.8s; background: #ff9800; box-shadow: 0 0 10px #ff9800; }
    .light-6 { animation-delay: 1s; background: #9c27b0; box-shadow: 0 0 10px #9c27b0; }
    @keyframes twinkle {
      0% { opacity: 0.7; transform: scale(0.9); }
      100% { opacity: 1; transform: scale(1.1); }
    }
    /* Весенние элементы */
    .spring-decorations .flower {
      position: fixed;
      font-size: 2em;
      animation: float 3s ease-in-out infinite;
    }
    .flower-1 { top: 20%; left: 10%; animation-delay: 0s; }
    .flower-2 { top: 60%; left: 80%; animation-delay: 1s; }
    .flower-3 { top: 30%; left: 70%; animation-delay: 2s; }
    .butterfly {
      position: fixed;
      top: 40%;
      right: 20%;
      font-size: 1.5em;
      animation: butterfly-flight 4s ease-in-out infinite;
    }
    /* Летние элементы */
    .summer-decorations {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 102;
    }
    .sun {
      position: fixed;
      top: 10%;
      right: 10%;
      font-size: 3em;
      z-index: 200;
      cursor: grab;
      text-shadow: 0 0 20px rgba(255, 215, 0, 0.8);
      user-select: none;
    }
    .sun.dragging {
      cursor: grabbing;
    }
    .palm-tree {
      position: fixed;
      bottom: 100px;
      left: 10%;
      font-size: 2em;
    }
    .ice-crem {
      position: fixed;
      bottom: 150px;
      left: 15%;
      font-size: 1.5em;
      animation: bounce 2s ease-in-out infinite;
    }
    /* Осенние элементы */
    .autumn-decorations .leaf {
      position: fixed;
      font-size: 1.5em;
      animation: leaf-fall linear forwards;
    }
    .leaf-1 { top: -10px; left: 10%; animation-duration: 8s; animation-delay: 0s; }
    .leaf-2 { top: -10px; left: 30%; animation-duration: 6s; animation-delay: 2s; }
    .leaf-3 { top: -10px; left: 70%; animation-duration: 7s; animation-delay: 1s; }
    .mushroom {
      position: fixed;
      bottom: 100px;
      right: 20%;
      font-size: 1.5em;
    }
    /* Анимации */
    @keyframes fall {
      0% {
        transform: translateY(-10px) rotate(0deg);
        opacity: 1;
      }
      100% {
        transform: translateY(100vh) rotate(360deg);
        opacity: 0;
      }
    }
    @keyframes float {
      0%, 100% { transform: translateY(0) rotate(0deg); }
      50% { transform: translateY(-20px) rotate(5deg); }
    }
    @keyframes butterfly-flight {
      0%, 100% { transform: translate(0, 0) rotate(0deg); }
      25% { transform: translate(20px, -15px) rotate(5deg); }
      50% { transform: translate(15px, 10px) rotate(-5deg); }
      75% { transform: translate(-10px, -5px) rotate(3deg); }
    }
    @keyframes sun-glow {
      0% { transform: scale(1); filter: brightness(1); }
      100% { transform: scale(1.1); filter: brightness(1.2); }
    }
    @keyframes bounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-10px); }
    }
    @keyframes leaf-fall {
      0% {
        transform: translateY(-10px) rotate(0deg);
        opacity: 1;
      }
      100% {
        transform: translateY(100vh) rotate(360deg);
        opacity: 0;
      }
    }
    /* Динамические тени от солнца */
    .dynamic-shadow {
      position: fixed;
      background: rgba(0,0,0,0.3);
      border-radius: 50%;
      pointer-events: none;
      z-index: 90;
    }
    .modal {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(13, 71, 161, 0.95);
      display: flex;
      justify-content: center;
      align-items: center;
      z-index: 2000;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.4s ease;
    }
    .modal.show {
      opacity: 1;
      pointer-events: all;
    }
    .modal-content {
      background: white;
      border-radius: 20px;
      padding: 30px;
      text-align: center;
      max-width: min(500px, 90vw);
      box-shadow: 0 20px 60px rgba(0,0,0,0.4);
      position: relative;
      margin: 20px;
    }
    .close-modal {
      position: absolute;
      top: 15px;
      right: 15px;
      font-size: 32px;
      cursor: pointer;
      color: #666;
      background: none;
      border: none;
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    #qr-image {
      max-width: min(380px, 80vw);
      max-height: min(380px, 80vh);
      margin: 0 auto 20px;
      border-radius: 16px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.2);
      display: block;
    }
    .qr-go-link {
      display: inline-block;
      padding: 12px 24px;
      background: #0d47a1;
      color: white;
      text-decoration: none;
      border-radius: 50px;
      font-weight: 600;
      font-size: 16px;
      transition: all 0.3s ease;
      border: none;
      cursor: pointer;
    }
    .qr-go-link:hover {
      background: #1976d2;
      transform: scale(1.05);
    }
    /* Модальное окно при переходе на внешний сайт */
    .transition-modal {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.95);
      display: flex;
      justify-content: center;
      align-items: center;
      z-index: 9999;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.4s ease;
      backdrop-filter: blur(10px);
    }
    .transition-modal.show {
      opacity: 1;
      pointer-events: all;
    }
    .transition-content {
      background: linear-gradient(135deg, #0d47a1 0%, #1976d2 100%);
      border-radius: 20px;
      padding: 30px;
      text-align: center;
      max-width: min(400px, 90vw);
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
      position: relative;
      margin: 20px;
      border: 2px solid rgba(255, 255, 255, 0.2);
      color: white;
    }
    .transition-icon {
      font-size: 48px;
      margin-bottom: 20px;
      animation: bounce 2s infinite;
    }
    .transition-text {
      font-size: 18px;
      margin-bottom: 25px;
      line-height: 1.5;
      text-align: center;
    }
    .transition-buttons {
      display: flex;
      justify-content: center;
      gap: 15px;
    }
    .transition-btn {
      padding: 12px 25px;
      border-radius: 50px;
      font-weight: 600;
      font-size: 16px;
      cursor: pointer;
      transition: all 0.3s ease;
      border: none;
      min-width: 120px;
    }
    .transition-confirm {
      background: #4CAF50;
      color: white;
    }
    .transition-cancel {
      background: rgba(255, 255, 255, 0.15);
      color: white;
      border: 1px solid rgba(255, 255, 255, 0.3);
    }
    .transition-btn:hover {
      transform: translateY(-3px);
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
    }
    .transition-countdown {
      margin-top: 15px;
      font-size: 14px;
      color: #bbdefb;
      text-align: center;
    }
    .transition-note {
      margin-top: 10px;
      font-size: 12px;
      color: #ffcc80;
      font-style: italic;
    }
    /* Плавающий виджет погоды */
    .weather-widget {
      position: fixed;
      width: 150px;
      height: 150px;
      background: rgba(25, 118, 210, 0.95);
      backdrop-filter: blur(10px);
      border-radius: 16px;
      padding: 15px;
      color: white;
      font-family: 'Segoe UI', sans-serif;
      z-index: 1001;
      cursor: move;
      user-select: none;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.2);
      top: 50px;
      right: 20px;
      resize: both;
      overflow: hidden;
      min-width: 150px;
      min-height: 150px;
      max-width: 300px;
      max-height: 300px;
    }
    .weather-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .weather-title {
      font-size: 14px;
      font-weight: 600;
      color: #bbdefb;
    }
    .weather-location {
      font-size: 12px;
      color: #bbdefb;
      margin-bottom: 10px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .weather-main {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
    }
    .weather-temp {
      font-size: 28px;
      font-weight: 700;
    }
    .weather-icon {
      font-size: 36px;
    }
    .weather-details {
      font-size: 11px;
      color: rgba(255, 255, 255, 0.9);
      line-height: 1.4;
    }
    .weather-details div {
      display: flex;
      justify-content: space-between;
      margin-bottom: 2px;
    }
    .weather-refresh {
      position: absolute;
      bottom: 30px;
      right: 8px;
      background: rgba(255, 255, 255, 0.1);
      border: none;
      color: white;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      transition: all 0.3s;
    }
    .weather-refresh:hover {
      background: rgba(255, 255, 255, 0.2);
      transform: rotate(180deg);
    }
    .weather-refresh.loading {
      animation: spin 1s linear infinite;
    }
    .weather-update {
      position: absolute;
      bottom: 8px;
      left: 8px;
      font-size: 9px;
      color: rgba(255, 255, 255, 0.7);
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    .news-section {
      padding: 40px 20px;
      background: rgba(0, 0, 0, 0.2);
    }
    .news-title {
      color: white;
      text-align: center;
      margin-bottom: 30px;
      font-size: clamp(28px, 6vw, 42px);
      text-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    .news-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(500px, 90vw), 1fr));
      gap: 20px;
    }
    .news-post {
      background: rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      padding: 20px;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
      transition: all 0.3s ease;
    }
    .news-post:hover {
      transform: translateY(-5px);
      background: rgba(255, 255, 255, 0.12);
    }
    .news-date { color: #bbdefb; font-size: 16px; margin-bottom: 10px; }
    .news-text {
      font-size: 16px;
      line-height: 1.4;
      margin-bottom: 15px;
      max-height: 120px;
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 5;
      -webkit-box-orient: vertical;
    }
    .post-stats {
      color: #90caf9;
      font-size: 14px;
      margin-bottom: 15px;
      display: flex;
      gap: 15px;
      align-items: center;
    }
    .like-btn {
      background: none;
      border: none;
      color: #90caf9;
      font-size: 14px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 5px;
      transition: all 0.3s ease;
      padding: 6px 12px;
      border-radius: 20px;
      border: 1px solid #90caf9;
    }
    .like-btn:hover {
      color: #ff4081;
      border-color: #ff4081;
      transform: scale(1.1);
    }
    .like-btn.liked {
      color: #ff4081;
      border-color: #ff4081;
      background: rgba(255, 64, 129, 0.1);
    }
    .media-container {
      position: relative;
      margin: 15px 0;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .media-thumb {
      width: 100px;
      height: 75px;
      border-radius: 8px;
      object-fit: cover;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      transition: all 0.3s ease;
    }
    .media-thumb:hover {
      transform: scale(1.05);
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .news-link {
      color: #bbdefb;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 10px;
      font-weight: 500;
      padding: 8px 16px;
      border: 1px solid #bbdefb;
      border-radius: 20px;
      font-size: 14px;
    }
    .news-link:hover {
      background: #bbdefb;
      color: var(--primary);
      transform: translateY(-2px);
    }
    .media-gallery {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.95);
      z-index: 3000;
      justify-content: center;
      align-items: center;
      flex-direction: column;
    }
    .media-gallery.active { display: flex; }
    .gallery-image {
      max-width: 95%;
      max-height: 80vh;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .gallery-close {
      position: absolute;
      top: 20px;
      right: 20px;
      font-size: 36px;
      color: white;
      cursor: pointer;
      background: rgba(0,0,0,0.5);
      width: 50px;
      height: 50px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 3001;
      border: none;
    }
    .gallery-btn {
      background: rgba(255, 255, 255, 0.2);
      border: none;
      color: white;
      font-size: 24px;
      width: 50px;
      height: 50px;
      border-radius: 50%;
      cursor: pointer;
      margin: 0 10px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .media-count {
      color: white;
      margin-top: 15px;
      font-size: 16px;
      background: rgba(0,0,0,0.5);
      padding: 8px 16px;
      border-radius: 20px;
    }
    footer {
      padding: 30px 0;
      text-align: center;
      margin-top: 40px;
    }
    @media (max-width: 768px) {
      .row {
        flex-direction: column;
        align-items: center;
      }
      .middle-row, .bottom-row {
        flex-direction: column;
        gap: 20px;
      }
      .bottom-row .left-shift,
      .bottom-row .right-shift {
        transform: none;
      }
      .weather-widget {
        width: 140px;
        height: 140px;
        font-size: 12px;
      }
      .weather-temp {
        font-size: 24px;
      }
      .weather-icon {
        font-size: 28px;
      }
    }
  </style>
</head>
<body data-timer-date="{{TIMER_DATE}}" data-timer-title="{{TIMER_TITLE}}" data-timer-icon="{{TIMER_ICON}}">
  {{DECORATIONS}}
  <div class="school-title">ГБОУ Школа №303<br>Фрунзенского района</div>
  <div class="buttons-container">
    <div class="row-wrapper">
      <div class="row top-row">
        <div class="tile" data-id="3"><h3>Комитет образования СПб</h3></div>
        <div class="tile" data-id="1"><h3>Официальный сайт</h3></div>
        <div class="tile" data-id="4"><h3>IT-Куб</h3></div>
      </div>
    </div>
    <div class="row-wrapper">
      <div class="row middle-row">
        <div class="tile" data-id="2"><h3>Минпросвещения РФ</h3></div>
        <div class="center-circle">
          <div class="clock-time" id="clock-time">00:00:00</div>
          <div class="clock-date" id="clock-date">Загрузка...</div>
        </div>
        <div class="tile" data-id="5"><h3>Группа ВКонтакте</h3></div>
      </div>
    </div>
    <!-- Нижний ряд со сдвигом -->
    <div class="row-wrapper">
    </div>
  </div>
  <!-- Таймер -->
  <div class="custom-timer" id="custom-timer">
    <h3 id="timer-title">{{TIMER_TITLE}}</h3>
    <div class="timer-display" id="timer-display">Загрузка...</div>
    <div class="timer-progress">
      <div class="timer-progress-bar" id="timer-progress-bar"></div>
    </div>
  </div>
  <!-- Модальное окно при переходе на внешний сайт -->
  <div class="transition-modal" id="transition-modal">
    <div class="transition-content">
      <div class="transition-icon">🚀</div>
      <div class="transition-text" id="transition-text">
        Вы переходите на внешний сайт.<br>
        <strong>Сайт будет открыт 1 минуту, после чего закроется.</strong><br>
        Нажмите "Перейти" для продолжения.
      </div>
      <div class="transition-buttons">
        <button class="transition-btn transition-cancel" id="transition-cancel">Отмена</button>
        <button class="transition-btn transition-confirm" id="transition-confirm">Перейти →</button>
      </div>
      <div class="transition-countdown" id="transition-countdown">
        <!-- Автоматический переход убран -->
      </div>
      <div class="transition-note">
        * После перехода у вас есть 60 секунд для просмотра сайта
      </div>
    </div>
  </div>
  <!-- Модальное окно с QR кодом -->
  <div id="qr-modal" class="modal">
    <div class="modal-content">
      <span id="close-modal" class="close-modal">&times;</span>
      <img id="qr-image" src="" alt="QR-код для перехода" style="width: 300px; height: 300px; margin: 0 auto 20px; display: block; border-radius: 12px;">
      <div id="qr-description" style="color: #666; font-size: 14px; margin-bottom: 15px; text-align: center;">
        Отсканируйте QR-код для быстрого перехода
      </div>
      <!-- Кнопка "Перейти" удалена -->
    </div>
  </div>
  <!-- Плавающий виджет погоды (без кнопки закрытия) -->
  <div class="weather-widget" id="weather-widget">
    <div class="weather-header">
      <div class="weather-title">Погода</div>
      <!-- Кнопка закрытия удалена -->
    </div>
    <div class="weather-location">72 МО Фрунзенский район, СПб</div>
    <div class="weather-main">
      <div class="weather-temp" id="weather-temp">--°</div>
      <div class="weather-icon" id="weather-icon">⛅</div>
    </div>
    <div class="weather-details">
      <div> <span id="weather-feels"></span></div>
      <div> <span id="weather-humidity"></span></div>
      <div> <span id="weather-wind"></span></div>
      <div> <span id="weather-pressure"></span></div>
    </div>
    <button class="weather-refresh" id="weather-refresh" title="Обновить">↻</button>
    <div class="weather-update" id="weather-update">Обновлено: --:--</div>
  </div>
  {{NEWS_SECTION}}
  <div class="media-gallery" id="media-gallery">
    <div class="gallery-close" id="gallery-close">&times;</div>
    <div class="gallery-content">
      <img class="gallery-image" id="gallery-image" src="" alt="Галерея изображений" />
    </div>
    <div class="gallery-nav">
      <button class="gallery-btn" id="gallery-prev">‹</button>
      <button class="gallery-btn" id="gallery-next">›</button>
    </div>
    <div class="media-count" id="media-count"></div>
  </div>
  <footer>
    <div class="author-link-container">
      <a href="/authors.html" class="author-link">Авторы</a>
    </div>
  </footer>
  <script>
    let currentMediaIndex = 0;
    let currentMediaList = [];
    let inactivityTimer;
    let postsData = [];
    let snowflakeCount = 0;
    let leafCount = 0;
    let maxParticles = 90;
    let sunPosition = { x: 0, y: 0 };
    let isDraggingSun = false;
    let dragOffset = { x: 0, y: 0 };
    let dynamicShadows = [];
    let transitionUrl = null;
    let transitionCountdown = null;
    let countdownSeconds = 5;
    let isDraggingWeather = false;
    let weatherDragOffset = { x: 0, y: 0 };
    let isDraggingTimer = false;
    let timerDragOffset = { x: 0, y: 0 };
    let weatherUpdateInterval;
    let siteCloseTimer = null;

    // QR коды для кнопок 1-5
    const qrCodes = {
        "1": "/qr/1.png",
        "2": "/qr/2.png",
        "3": "/qr/3.png",
        "4": "/qr/4.png",
        "5": "/qr/5.png"
    };

    // Ссылки для кнопок
    const buttonLinks = {
        "1": {
            url: "https://www.school303.spb.ru/",
            name: "Официальный сайт школы 303",
            description: "Официальный сайт ГБОУ Школы №303 Фрунзенского района"
        },
        "2": {
            url: "https://edu.gov.ru/",
            name: "Минпросвещения РФ",
            description: "Министерство просвещения Российской Федерации"
        },
        "3": {
            url: "https://k-obr.spb.ru/",
            name: "Комитет образования СПб",
            description: "Комитет по образованию Санкт-Петербурга"
        },
        "4": {
            url: "https://it-cube.school303.spb.ru/",
            name: "IT-Куб школы 303",
            description: "Центр цифрового образования IT-Куб"
        },
        "5": {
            url: "https://vk.com/shillerpublic",
            name: "Группа ВК школы 303",
            description: "Официальная группа ВКонтакте"
        },
        "8": {
            url: "https://school.mosreg.ru/",
            name: "Школьный портал",
            description: "Электронный школьный портал"
        },
        "9": {
            url: "https://dnevnik.mos.ru/",
            name: "Электронный дневник",
            description: "Электронный дневник и журнал"
        }
    };

    // Функция для плавного выталкивания виджета обратно на экран
    function enforceBoundaries(element, dragType) {
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        const elementWidth = element.offsetWidth;
        const elementHeight = element.offsetHeight;

        // Получаем текущую позицию
        const rect = element.getBoundingClientRect();
        let left = rect.left;
        let top = rect.top;

        // Границы экрана с запасом 20px
        const maxLeft = windowWidth - elementWidth + 20;
        const maxTop = windowHeight - elementHeight + 20;
        const minLeft = -20;
        const minTop = -20;

        let newLeft = left;
        let newTop = top;

        // Проверяем и корректируем границы
        if (left < minLeft) {
            newLeft = minLeft;
        } else if (left > maxLeft) {
            newLeft = maxLeft;
        }

        if (top < minTop) {
            newTop = minTop;
        } else if (top > maxTop) {
            newTop = maxTop;
        }

        // Если позиция изменилась, плавно возвращаем на экран
        if (newLeft !== left || newTop !== top) {
            element.style.transition = 'left 0.3s ease, top 0.3s ease';
            element.style.left = newLeft + 'px';
            element.style.top = newTop + 'px';

            // Убираем transition после анимации
            setTimeout(() => {
                element.style.transition = '';
            }, 300);

            // Сохраняем новую позицию
            if (dragType === 'weather') {
                saveWidgetPosition('weatherWidgetPosition', newLeft, newTop);
            } else if (dragType === 'timer') {
                saveWidgetPosition('timerWidgetPosition', newLeft, newTop);
            }
        }
    }

    // Инициализация солнца для летней темы
    function initSummerElements() {
      const sun = document.getElementById('movable-sun');
      if (!sun) return;

      // Получаем начальную позицию солнца
      const rect = sun.getBoundingClientRect();
      sunPosition = {
        x: rect.left + window.scrollX + rect.width/2,
        y: rect.top + window.scrollY + rect.height/2
      };

      // Обработчики событий для перетаскивания
      sun.addEventListener('mousedown', startDragSun);
      sun.addEventListener('touchstart', startDragSun, { passive: false });

      document.addEventListener('mousemove', dragSun);
      document.addEventListener('touchmove', dragSun, { passive: false });
      document.addEventListener('mouseup', stopDragSun);
      document.addEventListener('touchend', stopDragSun);

      // Создаем начальные тени
      createDynamicShadows();
    }

    function startDragSun(e) {
      e.preventDefault();
      const sun = document.getElementById('movable-sun');
      if (!sun) return;

      sun.classList.add('dragging');
      isDraggingSun = true;

      const clientX = e.clientX || e.touches[0].clientX;
      const clientY = e.clientY || e.touches[0].clientY;

      const rect = sun.getBoundingClientRect();
      dragOffset.x = clientX - (rect.left + rect.width/2);
      dragOffset.y = clientY - (rect.top + rect.height/2);
    }

    function dragSun(e) {
      if (!isDraggingSun) return;
      e.preventDefault();

      const clientX = e.clientX || e.touches[0].clientX;
      const clientY = e.clientY || e.touches[0].clientY;

      let newX = clientX - dragOffset.x;
      let newY = clientY - dragOffset.y;

      // Ограничиваем перемещение в пределах экрана
      newX = Math.max(50, Math.min(window.innerWidth - 50, newX));
      newY = Math.max(50, Math.min(window.innerHeight - 50, newY));

      sunPosition = { x: newX, y: newY };

      const sun = document.getElementById('movable-sun');
      if (sun) {
        sun.style.left = `${newX}px`;
        sun.style.top = `${newY}px`;
        sun.style.right = 'auto';
        sun.style.bottom = 'auto';
        sun.style.transform = 'translate(-50%, -50%)';
      }

      // Обновляем тени в реальном времени
      updateDynamicShadows();
    }

    function stopDragSun() {
      if (!isDraggingSun) return;

      const sun = document.getElementById('movable-sun');
      if (sun) {
        sun.classList.remove('dragging');
      }

      isDraggingSun = false;
    }

    function createDynamicShadows() {
      // Создаем несколько теней разных размеров
      const shadowCount = 5;
      dynamicShadows = [];

      for (let i = 0; i < shadowCount; i++) {
        const shadow = document.createElement('div');
        shadow.className = 'dynamic-shadow';

        // Разные размеры для разных теней
        const size = 100 + i * 50;
        shadow.style.width = `${size}px`;
        shadow.style.height = `${size}px`;

        // Начальная позиция
        shadow.style.left = `${sunPosition.x - size/2}px`;
        shadow.style.top = `${sunPosition.y - size/2}px`;

        // Разная прозрачность
        shadow.style.opacity = `${0.1 + i * 0.05}`;

        document.body.appendChild(shadow);
        dynamicShadows.push(shadow);
      }
    }

    function updateDynamicShadows() {
      dynamicShadows.forEach((shadow, index) => {
        const size = 100 + index * 50;

        // Позиция тени определяется положением солнца
        const shadowX = sunPosition.x - size/2;
        const shadowY = sunPosition.y - size/2;

        shadow.style.left = `${shadowX}px`;
        shadow.style.top = `${shadowY}px`;

        // Обновляем прозрачность на основе расстояния от центра
        const distanceFromCenter = Math.sqrt(
          Math.pow(sunPosition.x - window.innerWidth/2, 2) +
          Math.pow(sunPosition.y - window.innerHeight/2, 2)
        );

        const maxDistance = Math.sqrt(
          Math.pow(window.innerWidth/2, 2) +
          Math.pow(window.innerHeight/2, 2)
        );

        // Меняем прозрачность в зависимости от расстояния до центра
        const opacity = 0.1 + index * 0.05 - (distanceFromCenter / maxDistance) * 0.05;
        shadow.style.opacity = Math.max(0.05, Math.min(0.3, opacity));
      });
    }

    // Оптимизированное создание снежинок (только для зимы)
    function createOptimizedSnowflakes() {
      const snowflakesContainer = document.getElementById('snowflakes');
      if (!snowflakesContainer) return;

      // Ограничиваем количество снежинок
      if (snowflakeCount >= maxParticles) return;

      const snowflake = document.createElement('div');
      snowflake.className = 'snowflake';

      // Случайный символ снежинки
      const snowflakes = ['❄', '❅', '❆', '❃', '✻'];
      snowflake.innerHTML = snowflakes[Math.floor(Math.random() * snowflakes.length)];

      const size = Math.random() * 1.5 + 0.5;
      const left = Math.random() * 100;
      const animationDuration = Math.random() * 5 + 5;

      snowflake.style.left = left + 'vw';
      snowflake.style.fontSize = size + 'em';
      snowflake.style.animationDuration = animationDuration + 's';

      snowflakesContainer.appendChild(snowflake);
      snowflakeCount++;

      // Удаляем снежинку после завершения анимации
      setTimeout(() => {
        if (snowflake.parentNode) {
          snowflake.parentNode.removeChild(snowflake);
          snowflakeCount--;
        }
      }, animationDuration * 1000);

      // Планируем следующую снежинку
      setTimeout(createOptimizedSnowflakes, 150);
    }

    // Оптимизированное создание листьев для осени
    function createOptimizedLeaves() {
      const autumnDecor = document.querySelector('.autumn-decorations');
      if (!autumnDecor) return;

      // Ограничиваем количество листьев
      if (leafCount >= maxParticles) return;

      const leaf = document.createElement('div');
      leaf.className = 'leaf';

      // Случайный тип листа
      const leaves = ['🍂', '🍁', '🍃'];
      leaf.innerHTML = leaves[Math.floor(Math.random() * leaves.length)];

      const size = Math.random() * 1 + 0.5;
      const left = Math.random() * 100;
      const animationDuration = Math.random() * 8 + 4;

      leaf.style.left = left + 'vw';
      leaf.style.fontSize = size + 'em';
      leaf.style.animationDuration = animationDuration + 's';
      leaf.style.top = '-10px';
      leaf.style.animationName = 'leaf-fall';

      document.body.appendChild(leaf);
      leafCount++;

      // Удаляем лист после завершения анимации
      setTimeout(() => {
        if (leaf.parentNode) {
          leaf.parentNode.removeChild(leaf);
          leafCount--;
        }
      }, animationDuration * 1000);

      // Планируем следующий лист
      setTimeout(createOptimizedLeaves, 200);
    }

    // Часы в реальном времени
    function updateClock() {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const seconds = String(now.getSeconds()).padStart(2, '0');
      const timeString = `${hours}:${minutes}:${seconds}`;
      const options = {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        weekday: 'long'
      };
      const dateString = now.toLocaleDateString('ru-RU', options);
      document.getElementById('clock-time').textContent = timeString;
      document.getElementById('clock-date').textContent = dateString;
    }

    // Кастомный таймер
    function updateCustomTimer() {
      const timerDateStr = document.body.getAttribute('data-timer-date');
      const timerTitle = document.body.getAttribute('data-timer-title');
      const timerIcon = document.body.getAttribute('data-timer-icon');
      const [day, month, year] = timerDateStr.split('.');
      const targetDate = new Date(year, month - 1, day, 0, 0, 0);
      const now = new Date();
      // Обновляем заголовок таймера
      document.getElementById('timer-title').textContent = `${timerIcon} ${timerTitle}`;
      const diff = targetDate - now;
      if (diff <= 0) {
        document.getElementById('timer-display').innerHTML = '🎉 Время пришло! 🎉';
        document.getElementById('timer-progress-bar').style.width = '100%';
        return;
      }
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      const display = `${days}д ${hours}ч ${minutes}м ${seconds}с`;
      document.getElementById('timer-display').textContent = display;
      // Прогресс (от текущей даты до целевой)
      const startDate = new Date(now.getFullYear(), 0, 1); // Начало года
      const totalMs = targetDate - startDate;
      const elapsedMs = now - startDate;
      const progress = Math.min((elapsedMs / totalMs) * 100, 100);
      document.getElementById('timer-progress-bar').style.width = `${progress}%`;
    }

    // Функция для перетаскивания элементов с плавным выталкиванием
    function makeDraggable(element, dragType) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

        element.onmousedown = dragMouseDown;
        element.ontouchstart = dragTouchStart;

        function dragMouseDown(e) {
            e = e || window.event;
            e.preventDefault();
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;

            if (dragType === 'weather') {
                isDraggingWeather = true;
                element.style.cursor = 'grabbing';
            } else if (dragType === 'timer') {
                isDraggingTimer = true;
                element.style.cursor = 'grabbing';
            }
        }

        function dragTouchStart(e) {
            e.preventDefault();
            const touch = e.touches[0];
            pos3 = touch.clientX;
            pos4 = touch.clientY;
            document.ontouchend = closeDragElement;
            document.ontouchmove = elementDrag;

            if (dragType === 'weather') {
                isDraggingWeather = true;
            } else if (dragType === 'timer') {
                isDraggingTimer = true;
            }
        }

        function elementDrag(e) {
            e = e || window.event;
            e.preventDefault();

            let clientX, clientY;
            if (e.type === 'touchmove') {
                clientX = e.touches[0].clientX;
                clientY = e.touches[0].clientY;
            } else {
                clientX = e.clientX;
                clientY = e.clientY;
            }

            pos1 = pos3 - clientX;
            pos2 = pos4 - clientY;
            pos3 = clientX;
            pos4 = clientY;

            // Получаем текущую позицию
            let newTop = element.offsetTop - pos2;
            let newLeft = element.offsetLeft - pos1;

            // Получаем размеры элемента и окна
            const elementWidth = element.offsetWidth;
            const elementHeight = element.offsetHeight;
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;

            // Разрешаем выходить за границы экрана на 50%
            const maxLeft = windowWidth - (elementWidth * 0.5);
            const maxTop = windowHeight - (elementHeight * 0.5);
            const minLeft = -(elementWidth * 0.5);
            const minTop = -(elementHeight * 0.5);

            // Ограничиваем позицию
            newLeft = Math.max(minLeft, Math.min(newLeft, maxLeft));
            newTop = Math.max(minTop, Math.min(newTop, maxTop));

            // Применяем новую позицию
            element.style.top = newTop + "px";
            element.style.left = newLeft + "px";
            element.style.right = "auto";
            element.style.bottom = "auto";

            // Сохраняем позицию
            if (dragType === 'weather') {
                saveWidgetPosition('weatherWidgetPosition', newLeft, newTop);
            } else if (dragType === 'timer') {
                saveWidgetPosition('timerWidgetPosition', newLeft, newTop);
            }
        }

        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
            document.ontouchend = null;
            document.ontouchmove = null;

            if (dragType === 'weather') {
                isDraggingWeather = false;
                element.style.cursor = 'move';
                // Проверяем границы и плавно выталкиваем обратно
                enforceBoundaries(element, 'weather');
            } else if (dragType === 'timer') {
                isDraggingTimer = false;
                element.style.cursor = 'move';
                // Проверяем границы и плавно выталкиваем обратно
                enforceBoundaries(element, 'timer');
            }
        }
    }

    // Сохранение позиции виджета
    function saveWidgetPosition(key, x, y) {
        localStorage.setItem(key, JSON.stringify({ x, y }));
    }

    // Загрузка позиции виджета
    function loadWidgetPosition(key, element) {
        const saved = localStorage.getItem(key);
        if (saved) {
            try {
                const position = JSON.parse(saved);
                const windowWidth = window.innerWidth;
                const windowHeight = window.innerHeight;
                const elementWidth = element.offsetWidth;
                const elementHeight = element.offsetHeight;

                // Разрешаем выходить за границы экрана на 50%
                const maxX = windowWidth - (elementWidth * 0.5);
                const maxY = windowHeight - (elementHeight * 0.5);
                const minX = -(elementWidth * 0.5);
                const minY = -(elementHeight * 0.5);

                // Ограничиваем позицию
                const x = Math.max(minX, Math.min(position.x, maxX));
                const y = Math.max(minY, Math.min(position.y, maxY));

                element.style.left = `${x}px`;
                element.style.top = `${y}px`;
                element.style.right = 'auto';
                element.style.bottom = 'auto';
            } catch (e) {
                console.error('Error loading widget position:', e);
            }
        }
    }

async function fetchWeather() {
    const refreshBtn = document.getElementById('weather-refresh');
    refreshBtn.classList.add('loading');

    try {
        const apiKey = '1d6043ac2f367bbb6dd8c72a011b51a4';
        const city = 'Saint Petersburg,RU';

        const response = await fetch(
            `https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${apiKey}&units=metric&lang=ru`
        );

        if (!response.ok) throw new Error('Weather fetch failed');

        const data = await response.json();

        // Обновляем данные в виджете
        document.getElementById('weather-temp').textContent = Math.round(data.main.temp) + '°';
        document.getElementById('weather-feels').textContent = Math.round(data.main.feels_like) + '°';
        document.getElementById('weather-humidity').textContent = data.main.humidity + '%';
        document.getElementById('weather-wind').textContent = Math.round(data.wind.speed) + ' м/с';
        document.getElementById('weather-pressure').textContent = Math.round(data.main.pressure * 0.750062) + ' мм';

        // Иконка погоды
        const iconMap = {
            '01d': '☀️', '01n': '🌙',
            '02d': '⛅', '02n': '⛅',
            '03d': '☁️', '03n': '☁️',
            '04d': '☁️', '04n': '☁️',
            '09d': '🌧️', '09n': '🌧️',
            '10d': '🌦️', '10n': '🌦️',
            '11d': '⛈️', '11n': '⛈️',
            '13d': '❄️', '13n': '❄️',
            '50d': '🌫️', '50n': '🌫️'
        };

        document.getElementById('weather-icon').textContent =
            iconMap[data.weather[0].icon] || '⛅';

        // Время обновления
        const now = new Date();
        const timeString = now.toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
        document.getElementById('weather-update').textContent = `Обновлено: ${timeString}`;

    } catch (error) {
        console.error('Weather fetch error:', error);
        // Показываем данные по умолчанию (СПб)
        document.getElementById('weather-temp').textContent = '24°';
        document.getElementById('weather-feels').textContent = '26°';
        document.getElementById('weather-humidity').textContent = '65%';
        document.getElementById('weather-wind').textContent = '3 м/с';
        document.getElementById('weather-pressure').textContent = '755 мм';
        document.getElementById('weather-icon').textContent = '⛅';

        const now = new Date();
        const timeString = now.toLocaleTimeString('ru-RU', {
            hour: '2-digit',
            minute: '2-digit'
        });
        document.getElementById('weather-update').textContent = `Обновлено: ${timeString}`;
    } finally {
        refreshBtn.classList.remove('loading');
    }
}
    // Функция для показа модального окна при переходе
    function showTransitionModal(url, siteName) {
        transitionUrl = url;

        const modal = document.getElementById('transition-modal');
        const text = document.getElementById('transition-text');

        if (siteName) {
            text.innerHTML = `Вы переходите на сайт:<br><strong>${siteName}</strong><br><strong>Сайт будет открыт 1 минуту, после чего закроется.</strong><br>Нажмите "Перейти" для продолжения.`;
        }

        modal.classList.add('show');

        // Убираем автоматический отсчет
        clearInterval(transitionCountdown);
    }

    // Подтверждение перехода
    function confirmTransition() {
        clearInterval(transitionCountdown);
        document.getElementById('transition-modal').classList.remove('show');

        if (transitionUrl) {
            // Открываем сайт в новом окне
            const newWindow = window.open(transitionUrl, '_blank', 'noopener,noreferrer');

            // Запускаем таймер на 60 секунд для закрытия окна
            siteCloseTimer = setTimeout(() => {
                try {
                    if (newWindow && !newWindow.closed) {
                        newWindow.close();
                        console.log('Окно закрыто через 60 секунд');
                    }
                } catch (e) {
                    console.log('Не удалось закрыть окно автоматически:', e);
                }
            }, 60000); // 60 секунд

            // Сохраняем ссылку на окно для возможности ручного закрытия
            window.lastOpenedWindow = newWindow;
        }
    }

    // Отмена перехода
    function cancelTransition() {
        clearInterval(transitionCountdown);
        document.getElementById('transition-modal').classList.remove('show');
        transitionUrl = null;
    }

    // Функция для закрытия вкладки (будет вызываться извне)
    function closeCurrentTab() {
        if (window.lastOpenedWindow && !window.lastOpenedWindow.closed) {
            try {
                window.lastOpenedWindow.close();
                console.log('Окно закрыто вручную');
                if (siteCloseTimer) {
                    clearTimeout(siteCloseTimer);
                    siteCloseTimer = null;
                }
                return true;
            } catch (e) {
                console.log('Не удалось закрыть окно:', e);
                return false;
            }
        }
        return false;
    }

    // Экспортируем функцию для использования из Python
    window.closeCurrentTab = closeCurrentTab;

    function showQRCode(buttonId) {
        const linkInfo = buttonLinks[buttonId];
        if (!linkInfo) return;

        const qrImage = document.getElementById('qr-image');
        const qrDescription = document.getElementById('qr-description');

        // Устанавливаем QR код
        qrImage.src = qrCodes[buttonId];
        qrImage.alt = `QR-код для перехода на ${linkInfo.name}`;

        // Устанавливаем описание
        qrDescription.textContent = linkInfo.description;

        // Показываем модальное окно (без кнопки "Перейти")
        document.getElementById('qr-modal').classList.add('show');
    }

    class SchoolApp {
        constructor() {
            this.init();
        }

        init() {
            this.loadNews();
            this.setupEventListeners();
            this.resetInactivityTimer();

            // Запуск анимаций и таймеров
            const bodyStyle = getComputedStyle(document.body);
            const bg = bodyStyle.background || bodyStyle.backgroundColor;

            // Определяем тему по цвету фона
            let theme = 'winter';
            if (bg.includes('#4caf50') || bg.includes('green')) theme = 'spring';
            else if (bg.includes('#ff9800') || bg.includes('orange') || bg.includes('yellow')) theme = 'summer';
            else if (bg.includes('#795548') || bg.includes('brown')) theme = 'autumn';

            // Применяем класс темы к body для стилизации кнопок
            document.body.className = `${theme}-theme`;

            // Инициализация сезонных элементов
            if (theme === 'winter') {
                // Создаем снежинки с ограничением по количеству
                setInterval(createOptimizedSnowflakes, 300);
            } else if (theme === 'autumn') {
                // Создаем листья с ограничением по количеству
                setInterval(createOptimizedLeaves, 400);
            } else if (theme === 'summer') {
                // Инициализация перетаскиваемого солнца
                initSummerElements();
            }

            updateClock();
            updateCustomTimer();
            setInterval(updateClock, 1000);
            setInterval(updateCustomTimer, 1000);

            // Инициализация виджетов
            this.initWidgets();
        }

        initWidgets() {
            // Делаем виджет погоды перетаскиваемым
            const weatherWidget = document.getElementById('weather-widget');
            makeDraggable(weatherWidget, 'weather');
            loadWidgetPosition('weatherWidgetPosition', weatherWidget);

            // Делаем таймер перетаскиваемым
            const timerWidget = document.getElementById('custom-timer');
            makeDraggable(timerWidget, 'timer');
            loadWidgetPosition('timerWidgetPosition', timerWidget);

            // Загружаем погоду и устанавливаем интервал обновления (30 минут)
            fetchWeather();
            weatherUpdateInterval = setInterval(fetchWeather, 30 * 60 * 1000); // 30 минут

            // Обработчик обновления погоды
            document.getElementById('weather-refresh').addEventListener('click', fetchWeather);
        }

        loadNews() {
            fetch('/api/news')
                .then(response => {
                    if (!response.ok) throw new Error('Network error');
                    return response.json();
                })
                .then(posts => {
                    postsData = posts;
                    this.renderNews(posts);
                })
                .catch(error => {
                    console.error('News load error:', error);
                    document.getElementById('news-container').innerHTML = '<div class="news-post">Ошибка загрузки новостей</div>';
                });
        }

        renderNews(posts) {
            const container = document.getElementById('news-container');
            if (!posts || posts.length === 0) {
                container.innerHTML = '<div class="news-post">Новостей пока нет</div>';
                return;
            }
            container.innerHTML = posts.map((post, postIndex) => {
                const allMedia = post.photos || [];
                const allThumbs = post.thumbnails || [];
                const escapedText = this.escapeHtml(post.text || "Без текста");
                const escapedDate = this.escapeHtml(post.date);
                const escapedId = this.escapeHtml(post.id);
                return `
                    <div class="news-post" data-post-id="${escapedId}">
                        <div class="news-date">${escapedDate}</div>
                        <div class="news-text">${escapedText}</div>
                        <div class="post-stats">
                            <button class="like-btn" onclick="app.likePost('${escapedId}', ${postIndex})">
                                ❤️ <span class="like-count">${post.likes || 0}</span>
                            </button>
                        </div>
                        ${allThumbs.length > 0 ? `
                            <div class="media-container">
                                ${allThumbs.map((thumb, index) => `
                                    <img src="${thumb}" class="media-thumb"
                                         onclick="app.openGallery(${postIndex}, ${index})"
                                         alt="Превью ${index + 1}"
                                         loading="lazy" />
                                `).join('')}
                            </div>
                        ` : ''}
                        <a href="${post.vk_url}" target="_blank" rel="noopener noreferrer" class="news-link">Подробнее в ВК →</a>
                    </div>
                `;
            }).join('');
        }

        escapeHtml(unsafe) {
            return unsafe
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        likePost(postId, postIndex) {
            fetch('/api/like', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ postId: postId })
            })
            .then(response => {
                if (!response.ok) throw new Error('Network error');
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    const post = postsData[postIndex];
                    post.likes = data.likes;
                    const likeBtn = document.querySelectorAll('.like-btn')[postIndex];
                    const likeCount = likeBtn.querySelector('.like-count');
                    likeCount.textContent = post.likes;
                    likeBtn.classList.add('liked');
                    setTimeout(() => {
                        likeBtn.classList.remove('liked');
                    }, 300);
                }
            })
            .catch(error => console.error('Like error:', error));
        }

        openGallery(postIndex, startIndex) {
            const post = postsData[postIndex];
            currentMediaList = post.photos || [];
            currentMediaIndex = startIndex;
            this.updateGallery();
            document.getElementById('media-gallery').classList.add('active');
            this.resetInactivityTimer();
        }

        closeGallery() {
            document.getElementById('media-gallery').classList.remove('active');
        }

        updateGallery() {
            const image = document.getElementById('gallery-image');
            if (currentMediaList.length > 0 && currentMediaIndex < currentMediaList.length) {
                image.src = currentMediaList[currentMediaIndex];
                document.getElementById('media-count').textContent = `${currentMediaIndex + 1} / ${currentMediaList.length}`;
            }
        }

        nextMedia() {
            if (currentMediaList.length > 0) {
                currentMediaIndex = (currentMediaIndex + 1) % currentMediaList.length;
                this.updateGallery();
            }
        }

        prevMedia() {
            if (currentMediaList.length > 0) {
                currentMediaIndex = (currentMediaIndex - 1 + currentMediaList.length) % currentMediaList.length;
                this.updateGallery();
            }
        }

        setupEventListeners() {
            // Обработчики для кнопок
            document.querySelectorAll('.tile').forEach(tile => {
                tile.addEventListener('click', (e) => {
                    e.preventDefault();
                    const id = tile.dataset.id;

                    // Для кнопок 1-5 показываем QR код
                    if (['1', '2', '3', '4', '5'].includes(id)) {
                        showQRCode(id);
                    }

                    this.resetInactivityTimer();
                });
            });

            // Обработчики для модального окна перехода
            document.getElementById('transition-confirm').addEventListener('click', confirmTransition);
            document.getElementById('transition-cancel').addEventListener('click', cancelTransition);

            // Обработчики для QR модального окна
            document.getElementById('close-modal').addEventListener('click', () => {
                document.getElementById('qr-modal').classList.remove('show');
            });

            // Обработчики для галереи
            document.getElementById('gallery-close').addEventListener('click', () => this.closeGallery());
            document.getElementById('gallery-prev').addEventListener('click', () => this.prevMedia());
            document.getElementById('gallery-next').addEventListener('click', () => this.nextMedia());

            // Обработчики клавиатуры
            document.addEventListener('keydown', (e) => {
                if (document.getElementById('media-gallery').classList.contains('active')) {
                    if (e.key === 'Escape') this.closeGallery();
                    else if (e.key === 'ArrowLeft') this.prevMedia();
                    else if (e.key === 'ArrowRight') this.nextMedia();
                }
                if (document.getElementById('qr-modal').classList.contains('show')) {
                    if (e.key === 'Escape') document.getElementById('qr-modal').classList.remove('show');
                }
                if (document.getElementById('transition-modal').classList.contains('show')) {
                    if (e.key === 'Escape') cancelTransition();
                    else if (e.key === 'Enter') confirmTransition();
                }
            });

            // Таймер неактивности
            ['click', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(ev => {
                document.addEventListener(ev, () => this.resetInactivityTimer(), true);
            });
        }

        resetInactivityTimer() {
            clearTimeout(inactivityTimer);
            inactivityTimer = setTimeout(() => {
                document.getElementById('qr-modal').classList.remove('show');
                document.getElementById('transition-modal').classList.remove('show');
                this.closeGallery();
            }, 60000);
        }
    }

    // Инициализация при загрузке страницы
    document.addEventListener('DOMContentLoaded', () => {
        window.app = new SchoolApp();
    });

    // Сохранение позиции виджетов при изменении размера окна
    window.addEventListener('resize', () => {
        const weatherWidget = document.getElementById('weather-widget');
        const timerWidget = document.getElementById('custom-timer');

        if (weatherWidget.style.display !== 'none') {
            loadWidgetPosition('weatherWidgetPosition', weatherWidget);
        }

        loadWidgetPosition('timerWidgetPosition', timerWidget);
    });
  </script>
</body>
</html>
"""

AUTHORS_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Авторы проекта - Школа №303</title>
  <style>
    :root {
      --primary: #0d47a1;
      --primary-light: #1976d2;
      --secondary: #2196f3;
      --white: #ffffff;
      --text: #f5f5f5;
      --glass-bg: rgba(255, 255, 255, 0.1);
      --glass-border: rgba(255, 255, 255, 0.2);
      --shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
      --shadow-hover: 0 12px 40px rgba(0, 0, 0, 0.3);
    }
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      background: linear-gradient(135deg, #0d47a1 0%, #1976d2 50%, #bbdefb 100%);
      background-attachment: fixed;
      color: var(--text);
      font-family: 'Segoe UI', 'Trebuchet MS', Arial, sans-serif;
      line-height: 1.6;
      min-height: 100vh;
      overflow-x: hidden;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }
    header {
      text-align: center;
      padding: 40px 20px;
    }
    .school-title {
      font-size: clamp(28px, 6vw, 48px);
      font-weight: 800;
      color: var(--white);
      text-shadow: 0 4px 12px rgba(0,0,0,0.4);
      margin-bottom: 15px;
    }
    .subtitle {
      font-size: clamp(18px, 4vw, 24px);
      color: rgba(255, 255, 255, 0.85);
      margin-bottom: 30px;
    }
    .authors-section {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 30px;
      margin: 40px 0;
    }
    .author-card {
      background: var(--glass-bg);
      border: 1px solid var(--glass-border);
      border-radius: 16px;
      padding: 25px;
      text-align: center;
      backdrop-filter: blur(12px);
      box-shadow: var(--shadow);
      transition: all 0.4s ease;
      position: relative;
      overflow: hidden;
    }
    .author-card:hover {
      transform: translateY(-10px);
      background: rgba(255, 255, 255, 0.2);
      box-shadow: var(--shadow-hover);
    }
    .author-card::before {
      content: '';
      position: absolute;
      top: -50%;
      left: -50%;
      width: 200%;
      height: 200%;
      background: linear-gradient(45deg, transparent 0%, rgba(255,255,255,0.1) 50%, transparent 100%);
      transform: rotate(30deg);
      transition: all 0.8s ease;
      opacity: 0;
      z-index: 1;
    }
    .author-card:hover::before {
      opacity: 1;
      animation: shine 1.5s;
    }
    @keyframes shine {
      0% { transform: rotate(30deg) translateX(-150%); }
      100% { transform: rotate(30deg) translateX(150%); }
    }
    .author-avatar {
      width: 120px;
      height: 120px;
      border-radius: 50%;
      margin: 0 auto 20px;
      background: linear-gradient(45deg, #1565c0, #64b5f6);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 48px;
      color: white;
      box-shadow: 0 6px 16px rgba(0,0,0,0.25);
      position: relative;
      overflow: hidden;
    }
    .author-avatar::after {
      content: '';
      position: absolute;
      width: 200%;
      height: 200%;
      background: radial-gradient(circle, rgba(255,255,255,0.3) 0%, transparent 70%);
      top: -50%;
      left: -50%;
      opacity: 0;
      transition: opacity 0.3s;
    }
    .author-card:hover .author-avatar::after {
      opacity: 1;
    }
    .author-name {
      font-size: 22px;
      font-weight: 700;
      color: white;
      margin-bottom: 8px;
      position: relative;
      z-index: 2;
    }
    .author-role {
      font-size: 16px;
      color: #bbdefb;
      margin-bottom: 15px;
      position: relative;
      z-index: 2;
    }
    .author-desc {
      font-size: 14px;
      color: rgba(255, 255, 255, 0.85);
      margin-bottom: 20px;
      position: relative;
      z-index: 2;
    }
    .social-links {
      display: flex;
      justify-content: center;
      gap: 15px;
      position: relative;
      z-index: 2;
    }
    .social-link {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.15);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 18px;
      text-decoration: none;
      transition: all 0.3s ease;
      border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .social-link:hover {
      background: #1976d2;
      transform: translateY(-3px);
    }
    .team-section {
      background: rgba(0, 30, 80, 0.4);
      border-radius: 24px;
      padding: 30px;
      margin: 40px 0;
      backdrop-filter: blur(12px);
      border: 1px solid var(--glass-border);
      box-shadow: var(--shadow);
    }
    .team-title {
      text-align: center;
      font-size: 28px;
      font-weight: 700;
      color: white;
      margin-bottom: 25px;
      text-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .team-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
      gap: 20px;
    }
    .team-member {
      background: var(--glass-bg);
      border-radius: 16px;
      padding: 20px;
      text-align: center;
      transition: all 0.3s ease;
    }
    .team-member:hover {
      background: rgba(255, 255, 255, 0.1);
      transform: scale(1.03);
    }
    .member-name {
      font-weight: 600;
      color: white;
      font-size: 18px;
      margin-bottom: 5px;
    }
    .member-role {
      font-size: 14px;
      color: #bbdefb;
    }
    .back-button {
      display: flex;
      justify-content: center;
      margin: 40px 0 20px;
    }
    .back-link {
      padding: 12px 30px;
      background: rgba(255, 255, 255, 0.15);
      color: white;
      text-decoration: none;
      border-radius: 50px;
      font-weight: 600;
      font-size: 16px;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      border: 1px solid rgba(255, 255, 255, 0.3);
      transition: all 0.3s ease;
      backdrop-filter: blur(8px);
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
    .back-link:hover {
      background: rgba(255, 255, 255, 0.25);
      transform: translateY(-3px);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
    }
    .back-link svg {
      width: 20px;
      height: 20px;
    }
    footer {
      text-align: center;
      padding: 30px 0;
      color: rgba(255, 255, 255, 0.7);
      font-size: 14px;
      margin-top: 20px;
    }
    .watermark {
      position: fixed;
      bottom: 20px;
      right: 20px;
      font-size: 12px;
      color: rgba(255, 255, 255, 0.3);
      z-index: 100;
    }
    @media (max-width: 768px) {
      .authors-section, .team-grid {
        grid-template-columns: 1fr;
      }
      .school-title {
        font-size: clamp(24px, 8vw, 36px);
      }
      .author-avatar {
        width: 100px;
        height: 100px;
        font-size: 36px;
      }
      .author-name {
        font-size: 20px;
      }
      .back-button {
        margin-top: 30px;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1 class="school-title">ГБОУ Школа №303</h1>
      <div class="subtitle">Фрунзенского района Санкт-Петербурга</div>
    </header>

    <section class="authors-section">
      <div class="author-card">
        <div class="author-avatar">АИ</div>
        <h2 class="author-name">Андрей Иванович</h2>
        <div class="author-role">Руководитель проекта</div>
        <p class="author-desc">Координирует разработку сайта, управляет командой и взаимодействует с администрацией школы.</p>
      </div>

      <div class="author-card">
        <div class="author-avatar">КИ</div>
        <h2 class="author-name">Константин Ионцев</h2>
        <div class="author-role">Frontend, Backend-разработчик</div>
        <p class="author-desc">Создал видимую часть сайта и внутренности сайта.</p>
      </div>

      <div class="author-card">
        <div class="author-avatar">МД</div>
        <h2 class="author-name">Михаил Демидов</h2>
        <div class="author-role">Дизайнер</div>
        <p class="author-desc">Фронтенд разработчик. Способствовал скорейшему выходу итогового проекта</p>
      </div>
    </section>

    <div class="back-button">
      <a href="/" class="back-link">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"></path>
        </svg>
        Вернуться на главную
      </a>
    </div>


  </div>
  <script>
    // Простая анимация при загрузке
    document.addEventListener('DOMContentLoaded', () => {
      const authorCards = document.querySelectorAll('.author-card');
      authorCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';

        setTimeout(() => {
          card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
          card.style.opacity = '1';
          card.style.transform = 'translateY(0)';
        }, 300 + index * 200);
      });
    });
  </script>
</body>
</html>
"""


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            config = load_config()
            seasonal = get_seasonal_elements(config["theme"])

            # Получаем тему для кнопок
            button_theme = seasonal["button_theme"]

            # Добавляем класс для темы
            theme_class = "winter"
            if "spring" in seasonal["background"]:
                theme_class = "spring"
            elif "summer" in seasonal["background"]:
                theme_class = "summer"
            elif "autumn" in seasonal["background"]:
                theme_class = "autumn"

            if self.path == "/authors.html":
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(AUTHORS_HTML.encode("utf-8"))
                return
            elif self.path.startswith("/parsing/"):
                filename = os.path.basename(self.path)
                safe_filename = sanitize_filename(filename)
                if "/media/" in self.path:
                    filepath = os.path.join(MEDIA_DIR, safe_filename)
                elif "/thumbnails/" in self.path:
                    filepath = os.path.join(THUMBNAIL_DIR, safe_filename)
                else:
                    filepath = None
                if filepath and os.path.exists(filepath) and safe_filename:
                    self.send_response(200)
                    self.send_header("Content-type", "image/jpeg")
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    with open(filepath, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.send_response(404)
                    self.end_headers()
                return
            elif self.path.startswith("/qr/"):
                filename = os.path.basename(self.path)
                safe_filename = sanitize_filename(filename)
                filepath = os.path.join(QR_DIR, safe_filename)
                if os.path.exists(filepath) and safe_filename:
                    self.send_response(200)
                    if filename.endswith(".png"):
                        self.send_header("Content-type", "image/png")
                    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
                        self.send_header("Content-type", "image/jpeg")
                    else:
                        self.send_header("Content-type", "application/octet-stream")
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    with open(filepath, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.send_response(404)
                    self.end_headers()
                return
            elif self.path == "/api/news":
                try:
                    if os.path.exists(POSTS_FILE):
                        with open(POSTS_FILE, "r", encoding="utf-8") as f:
                            posts = json.load(f)
                        self.send_response(200)
                        self.send_header(
                            "Content-type", "application/json; charset=utf-8"
                        )
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                        self.wfile.write(
                            json.dumps(posts, ensure_ascii=False).encode("utf-8")
                        )
                    else:
                        self.send_response(404)
                        self.end_headers()
                except Exception:
                    self.send_response(500)
                    self.end_headers()
                return
            else:
                # Генерируем секцию новостей в зависимости от конфигурации
                news_section = (
                    """
                  <section class="news-section">
                    <h2 class="news-title">Новости школы</h2>
                    <div class="news-grid" id="news-container">Загрузка...</div>
                  </section>
                """
                    if config.get("news_visible", True)
                    else ""
                )

                # Генерируем HTML с текущей темой
                html_content = HTML_TEMPLATE.replace(
                    "{{BACKGROUND}}", seasonal["background"]
                )
                html_content = html_content.replace(
                    "{{DECORATIONS}}", seasonal["decorations"]
                )
                html_content = html_content.replace(
                    "{{TIMER_DATE}}", config["timer_date"]
                )
                html_content = html_content.replace(
                    "{{TIMER_TITLE}}", config["timer_title"]
                )
                html_content = html_content.replace(
                    "{{TIMER_ICON}}", seasonal["timer_icon"]
                )
                html_content = html_content.replace("{{NEWS_SECTION}}", news_section)

                # Добавляем стили для тематических кнопок
                html_content = html_content.replace(
                    "{{BUTTON_BACKGROUND}}", button_theme["background"]
                )
                html_content = html_content.replace(
                    "{{BUTTON_BORDER}}", button_theme["border"]
                )
                html_content = html_content.replace("{{THEME_CLASS}}", theme_class)

                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))
                return
        except Exception:
            try:
                self.send_response(500)
                self.end_headers()
            except:
                pass

    def do_POST(self):
        try:
            if self.path == "/api/like":
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > 1024:
                    self.send_response(413)
                    self.end_headers()
                    return
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode("utf-8"))
                post_id = data.get("postId")
                if post_id and isinstance(post_id, str) and len(post_id) < 100:
                    likes_data = load_likes()
                    current_likes = likes_data.get(post_id, 0)
                    likes_data[post_id] = current_likes + 1
                    if save_likes(likes_data):
                        try:
                            if os.path.exists(POSTS_FILE):
                                with open(POSTS_FILE, "r", encoding="utf-8") as f:
                                    posts = json.load(f)
                                for post in posts:
                                    if post["id"] == post_id:
                                        post["likes"] = likes_data[post_id]
                                        break
                                with open(POSTS_FILE, "w", encoding="utf-8") as f:
                                    json.dump(posts, f, ensure_ascii=False)
                        except Exception:
                            pass
                        response = {"success": True, "likes": likes_data[post_id]}
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(response).encode("utf-8"))
                    else:
                        self.send_response(500)
                        self.end_headers()
                else:
                    self.send_response(400)
                    self.end_headers()
                return
        except Exception:
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def is_admin(user_id):
    return user_id in ADMIN_IDS


@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    if is_admin(message.from_user.id):
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            telebot.types.KeyboardButton("🔄 Обновить новости"),
            telebot.types.KeyboardButton("📊 Статистика"),
            telebot.types.KeyboardButton("🎨 Панель администратора"),
            telebot.types.KeyboardButton("🚪 Закрыть вкладку"),
            telebot.types.KeyboardButton("⏸️ Выключить парсинг"),
            telebot.types.KeyboardButton("▶️ Включить парсинг"),
            telebot.types.KeyboardButton("📰 Скрыть новости"),
            telebot.types.KeyboardButton("📰 Показать новости"),
        )
        bot.reply_to(
            message,
            "👑 *Admin Panel*\n"
            "Commands:\n"
            "🔄 /reload - Update news\n"
            "📊 /stats - Statistics\n"
            "🗑️ /delete - Clear data\n"
            "🔑 /token - Token info\n"
            "🎮 /button - Stand buttons\n"
            "🆕 /newbutton - New button\n"
            "🗑️ /delbutton - Remove button\n"
            "📋 /listbuttons - Button list\n"
            "📁 /files - Project files\n"
            "✏️ /edit - Edit files\n"
            "📨 /messages - User messages\n"
            "🎨 /admin-panel - Admin settings\n"
            "⏸️ /toggle_parsing - Включить/выключить парсинг\n"
            "🚪 /close_tab - Закрыть вкладку\n"
            "📰 /toggle_news - Показать/скрыть новости\n"
            "🔐 Password: admin",
            parse_mode="Markdown",
            reply_markup=markup,
        )
    else:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(telebot.types.KeyboardButton("📨 Message to admins"))
        bot.reply_to(message, "👋 Hello! I'm school 303 bot.", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "⏸️ Выключить парсинг")
def handle_disable_parsing_button(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    handle_toggle_parsing_command(message)


@bot.message_handler(func=lambda message: message.text == "▶️ Включить парсинг")
def handle_enable_parsing_button(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    handle_toggle_parsing_command(message)


@bot.message_handler(func=lambda message: message.text == "📰 Скрыть новости")
def handle_hide_news_button(message):
    global parsing_enabled  # Добавляем в начало функции
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    config = load_config()
    config["news_visible"] = False
    if save_config(config):
        # При скрытии новостей автоматически выключаем парсинг
        parsing_enabled = False
        bot.reply_to(message, "✅ Новости скрыты и парсинг отключен")
    else:
        bot.reply_to(message, "❌ Ошибка сохранения конфигурации")


@bot.message_handler(func=lambda message: message.text == "📰 Показать новости")
def handle_show_news_button(message):
    global parsing_enabled  # Добавляем в начало функции
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    config = load_config()
    config["news_visible"] = True
    if save_config(config):
        # При показе новостей автоматически включаем парсинг
        parsing_enabled = True
        bot.reply_to(message, "✅ Новости показаны и парсинг включен")
    else:
        bot.reply_to(message, "❌ Ошибка сохранения конфигурации")


@bot.message_handler(func=lambda message: message.text == "🚪 Закрыть вкладку")
def handle_close_tab_button(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    handle_close_tab_command(message)


@bot.message_handler(func=lambda message: message.text == "🔄 Обновить новости")
def handle_reload_button(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    handle_reload_command(message)


@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def handle_stats_button(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    handle_stats_command(message)


@bot.message_handler(func=lambda message: message.text == "🎨 Панель администратора")
def handle_admin_panel_button(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    handle_admin_panel(message)


@bot.message_handler(commands=["admin-panel"])
def handle_admin_panel(message):
    global parsing_enabled
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    config = load_config()
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("❄️ Зима", callback_data="theme_winter"),
        telebot.types.InlineKeyboardButton("🌱 Весна", callback_data="theme_spring"),
    )
    markup.row(
        telebot.types.InlineKeyboardButton("🌞 Лето", callback_data="theme_summer"),
        telebot.types.InlineKeyboardButton("🍁 Осень", callback_data="theme_autumn"),
    )
    markup.row(
        telebot.types.InlineKeyboardButton(
            "⏰ Изменить таймер", callback_data="change_timer"
        )
    )
    markup.row(
        telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        telebot.types.InlineKeyboardButton("🔄 Обновить", callback_data="reload"),
    )
    markup.row(
        telebot.types.InlineKeyboardButton(
            f"📰 {'Скрыть' if config.get('news_visible', True) else 'Показать'} новости",
            callback_data="toggle_news",
        )
    )
    bot.send_message(
        message.chat.id,
        f"🎨 *Панель администратора*\n"
        f"📅 Текущая тема: *{config['theme']}*\n"
        f"⏰ Таймер: *{config['timer_title']}*\n"
        f"📅 Дата: *{config['timer_date']}*\n"
        f"📰 Новости: *{'ВКЛ' if config.get('news_visible', True) else 'ВЫКЛ'}*\n"
        f"🔄 Парсинг: *{'ВКЛ' if parsing_enabled else 'ВЫКЛ'}*",
        reply_markup=markup,
        parse_mode="Markdown",
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    config = load_config()
    if call.data.startswith("theme_"):
        theme = call.data.split("_")[1]
        config["theme"] = theme
        if save_config(config):
            bot.answer_callback_query(call.id, f"✅ Тема изменена на {theme}")
            # Обновляем сообщение
            markup = telebot.types.InlineKeyboardMarkup()
            markup.row(
                telebot.types.InlineKeyboardButton(
                    "❄️ Зима", callback_data="theme_winter"
                ),
                telebot.types.InlineKeyboardButton(
                    "🌱 Весна", callback_data="theme_spring"
                ),
            )
            markup.row(
                telebot.types.InlineKeyboardButton(
                    "🌞 Лето", callback_data="theme_summer"
                ),
                telebot.types.InlineKeyboardButton(
                    "🍁 Осень", callback_data="theme_autumn"
                ),
            )
            markup.row(
                telebot.types.InlineKeyboardButton(
                    "⏰ Изменить таймер", callback_data="change_timer"
                )
            )
            markup.row(
                telebot.types.InlineKeyboardButton(
                    "📊 Статистика", callback_data="stats"
                ),
                telebot.types.InlineKeyboardButton(
                    "🔄 Обновить", callback_data="reload"
                ),
            )
            markup.row(
                telebot.types.InlineKeyboardButton(
                    f"📰 {'Скрыть' if config.get('news_visible', True) else 'Показать'} новости",
                    callback_data="toggle_news",
                )
            )
            bot.edit_message_text(
                f"🎨 *Панель администратора*\n"
                f"📅 Текущая тема: *{config['theme']}*\n"
                f"⏰ Таймер: *{config['timer_title']}*\n"
                f"📅 Дата: *{config['timer_date']}*\n"
                f"📰 Новости: *{'ВКЛ' if config.get('news_visible', True) else 'ВЫКЛ'}*\n"
                f"🔄 Парсинг: *{'ВКЛ' if parsing_enabled else 'ВЫКЛ'}*",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown",
            )
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка сохранения")
    elif call.data == "change_timer":
        user_states[call.from_user.id] = "waiting_timer_date"
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📅 Введите новую дату для таймера в формате *DD.MM.YYYY*\n"
            "Например: *19.12.2025*\n"
            "✏️ Вы также можете добавить заголовок через |:\n"
            "*19.12.2025|До зимних каникул*",
            parse_mode="Markdown",
        )
    elif call.data == "stats":
        handle_stats_command(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "reload":
        handle_reload_command(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == "toggle_news":  # Объявляем global в начале этого блока
        config["news_visible"] = not config.get("news_visible", True)
        if save_config(config):
            # Автоматически включаем/выключаем парсинг в зависимости от видимости новостей
            parsing_enabled = config["news_visible"]
            status = "скрыты" if not config["news_visible"] else "показаны"
            status_parsing = "отключен" if not config["news_visible"] else "включен"
            bot.answer_callback_query(
                call.id, f"✅ Новости {status} и парсинг {status_parsing}"
            )
            # Обновляем сообщение
            markup = telebot.types.InlineKeyboardMarkup()
            markup.row(
                telebot.types.InlineKeyboardButton(
                    "❄️ Зима", callback_data="theme_winter"
                ),
                telebot.types.InlineKeyboardButton(
                    "🌱 Весна", callback_data="theme_spring"
                ),
            )
            markup.row(
                telebot.types.InlineKeyboardButton(
                    "🌞 Лето", callback_data="theme_summer"
                ),
                telebot.types.InlineKeyboardButton(
                    "🍁 Осень", callback_data="theme_autumn"
                ),
            )
            markup.row(
                telebot.types.InlineKeyboardButton(
                    "⏰ Изменить таймер", callback_data="change_timer"
                )
            )
            markup.row(
                telebot.types.InlineKeyboardButton(
                    "📊 Статистика", callback_data="stats"
                ),
                telebot.types.InlineKeyboardButton(
                    "🔄 Обновить", callback_data="reload"
                ),
            )
            markup.row(
                telebot.types.InlineKeyboardButton(
                    f"📰 {'Скрыть' if config.get('news_visible', True) else 'Показать'} новости",
                    callback_data="toggle_news",
                )
            )
            bot.edit_message_text(
                f"🎨 *Панель администратора*\n"
                f"📅 Текущая тема: *{config['theme']}*\n"
                f"⏰ Таймер: *{config['timer_title']}*\n"
                f"📅 Дата: *{config['timer_date']}*\n"
                f"📰 Новости: *{'ВКЛ' if config.get('news_visible', True) else 'ВЫКЛ'}*\n"
                f"🔄 Парсинг: *{'ВКЛ' if parsing_enabled else 'ВЫКЛ'}*",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown",
            )
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка сохранения")


@bot.message_handler(
    func=lambda message: user_states.get(message.from_user.id) == "waiting_timer_date"
)
def handle_timer_date(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        parts = message.text.split("|")
        date_str = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else "До события"
        # Проверяем формат даты
        day, month, year = map(int, date_str.split("."))
        datetime(year, month, day)
        config = load_config()
        config["timer_date"] = date_str
        config["timer_title"] = title
        if save_config(config):
            user_states.pop(message.from_user.id, None)
            bot.reply_to(message, f"✅ Таймер обновлен!\n📅 {date_str}\n📝 {title}")
        else:
            bot.reply_to(message, "❌ Ошибка сохранения конфигурации")
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат даты. Используйте DD.MM.YYYY")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=["toggle_news"])
def handle_toggle_news_command(message):
    global parsing_enabled  # Добавляем в начало функции
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    config = load_config()
    config["news_visible"] = not config.get("news_visible", True)
    if save_config(config):
        # Автоматически включаем/выключаем парсинг
        parsing_enabled = config["news_visible"]
        status = "скрыты" if not config["news_visible"] else "показаны"
        status_parsing = "отключен" if not config["news_visible"] else "включен"
        bot.reply_to(message, f"✅ Новости {status} и парсинг {status_parsing}")
    else:
        bot.reply_to(message, "❌ Ошибка сохранения конфигурации")


@bot.message_handler(commands=["reload"])
def handle_reload_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    msg = bot.reply_to(message, "🔄 Updating...")

    def parsing_task():
        try:
            success = fetch_vk_posts_with_retry(max_retries=2)
            if success:
                bot.edit_message_text(
                    "✅ News updated", message.chat.id, msg.message_id
                )
            else:
                bot.edit_message_text(
                    "❌ Update error", message.chat.id, msg.message_id
                )
        except Exception as e:
            bot.edit_message_text(
                f"❌ Error: {str(e)}", message.chat.id, msg.message_id
            )

    threading.Thread(target=parsing_task).start()


@bot.message_handler(commands=["toggle_parsing"])
def handle_toggle_parsing_command(message):
    global parsing_enabled  # Добавляем в начало функции
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    with parsing_lock:
        parsing_enabled = not parsing_enabled
        status = "включен" if parsing_enabled else "отключен"
        bot.reply_to(message, f"✅ Парсинг {status}")


@bot.message_handler(commands=["close_tab"])
def handle_close_tab_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        # Закрываем вкладку браузера
        if close_browser_tab():
            bot.reply_to(message, "✅ Вкладка закрыта")
        else:
            bot.reply_to(
                message,
                "⚠️ Не удалось закрыть вкладку. Возможно, браузер не открыт или вкладка уже закрыта.",
            )
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=["stats"])
def handle_stats_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        config = load_config()
        stats_text = "📊 *Statistics*\n"
        if os.path.exists(POSTS_FILE):
            with open(POSTS_FILE, "r", encoding="utf-8") as f:
                posts = json.load(f)
            total_posts = len(posts)
            total_photos = sum(len(post.get("photos", [])) for post in posts)
            total_likes = sum(post.get("likes", 0) for post in posts)
            stats_text += f"📝 Posts: {total_posts}\n🖼️ Photos: {total_photos}\n❤️ Likes: {total_likes}\n"
        else:
            stats_text += "📝 Posts: 0\n"
        token = load_token()
        stats_text += f"🔑 Token: {'✅' if token else '❌'}\n"
        custom_buttons = load_custom_buttons()
        stats_text += f"🎮 Custom buttons: {len(custom_buttons)}\n"
        stats_text += f"🎨 Theme: {config['theme']}\n"
        stats_text += f"⏰ Timer: {config['timer_date']} - {config['timer_title']}\n"
        stats_text += (
            f"🔄 Парсинг: {'✅ Включен' if parsing_enabled else '❌ Выключен'}\n"
        )
        stats_text += f"📰 Новости: {'✅ ВКЛ' if config.get('news_visible', True) else '❌ ВЫКЛ'}\n"
        bot.reply_to(message, stats_text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["delete"])
def handle_delete_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Use: /delete password")
            return
        if not verify_password(parts[1]):
            bot.reply_to(message, "❌ Wrong password")
            return
        if os.path.exists("parsing"):
            shutil.rmtree("parsing")
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        if os.path.exists(TOKEN_TIME_FILE):
            os.remove(TOKEN_TIME_FILE)
        if os.path.exists(BUTTONS_FILE):
            os.remove(BUTTONS_FILE)
        if os.path.exists(USER_MESSAGES_FILE):
            os.remove(USER_MESSAGES_FILE)
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        if os.path.exists(QR_DIR):
            shutil.rmtree(QR_DIR)
        os.makedirs("parsing", exist_ok=True)
        bot.reply_to(message, "✅ All data cleared\n🔄 Use /reload for new parsing")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["token"])
def handle_token_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        token = load_token()
        if token:
            token_preview = token[:6] + "..." + token[-4:]
            bot.reply_to(
                message,
                f"🔑 *VK Token*\nStatus: ✅ Active\nPrefix: {token_preview}\nLength: {len(token)} chars",
                parse_mode="Markdown",
            )
        else:
            bot.reply_to(
                message, "🔑 *VK Token*\nStatus: ❌ Missing", parse_mode="Markdown"
            )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["button"])
def handle_button_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(
                message,
                "🎮 *Stand Buttons*\nUse: /button <number>\n1-5 - Standard\n6+ - Custom",
                parse_mode="Markdown",
            )
            return
        # Используем контролируемое открытие сайта
        button_id = parts[1]
        if button_id in ["1", "2", "3", "4", "5"]:
            urls = {
                "1": "https://www.school303.spb.ru/",
                "2": "https://edu.gov.ru/",
                "3": "https://k-obr.spb.ru/",
                "4": "https://it-cube.school303.spb.ru/",
                "5": "https://vk.com/shillerpublic",
            }
            if button_id in urls:
                if open_site_with_control(urls[button_id]):
                    bot.reply_to(
                        message,
                        f"🌐 Сайт открыт в контролируемом окне. Закроется через 60 секунд или командой /close_tab",
                    )
                else:
                    bot.reply_to(message, f"🌐 Сайт открыт в обычном режиме")
        else:
            result = simulate_button_press(button_id)
            bot.reply_to(message, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["newbutton"])
def handle_newbutton_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            bot.reply_to(
                message,
                "🆕 *New Button*\nUse: /newbutton password number URL",
                parse_mode="Markdown",
            )
            return
        if not verify_password(parts[1]):
            bot.reply_to(message, "❌ Wrong password")
            return
        result = add_custom_button(parts[2], parts[3])
        bot.reply_to(message, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["delbutton"])
def handle_delbutton_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(
                message,
                "🗑️ *Remove Button*\nUse: /delbutton number",
                parse_mode="Markdown",
            )
            return
        result = remove_custom_button(parts[1])
        bot.reply_to(message, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["listbuttons"])
def handle_listbuttons_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        result = list_custom_buttons()
        bot.reply_to(message, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["files"])
def handle_files_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        parts = message.text.split(maxsplit=1)
        path = parts[1] if len(parts) > 1 else "."
        result = view_project_files(path)
        bot.reply_to(message, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["edit"])
def handle_edit_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            bot.reply_to(
                message,
                "✏️ *Edit*\nUse: /edit <file> <mode> <text>",
                parse_mode="Markdown",
            )
            return
        result = modify_project_file(parts[1], parts[3], parts[2])
        bot.reply_to(message, result)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(commands=["messages"])
def handle_messages_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Access denied")
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            messages = load_user_messages()
            if not messages:
                bot.reply_to(message, "📨 No messages")
                return
            result = "📨 *Messages:*\n"
            for msg in messages[-5:]:
                username = msg.get("username", "Unknown")
                user_msg = msg.get("message", "")
                result += f"👤 {username}\n💬 {user_msg}\n"
            result += "/messages clear - Clear"
            bot.reply_to(message, result, parse_mode="Markdown")
            return
        if parts[1] == "clear":
            if clear_user_messages():
                bot.reply_to(message, "✅ Messages cleared")
            else:
                bot.reply_to(message, "❌ Clear error")
        else:
            bot.reply_to(message, "❌ Unknown action")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_user_messages(message):
    if message.text == "📨 Message to admins":
        bot.reply_to(message, "💬 Write message:")
        return
    if not is_admin(message.from_user.id):
        if save_user_message(
            message.from_user.id, message.from_user.username, message.text
        ):
            for admin_id in ADMIN_IDS:
                try:
                    bot.send_message(
                        admin_id,
                        f"📨 *Message:*\n👤 @{message.from_user.username or 'Unknown'}\n💬 {message.text}",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
            bot.reply_to(message, "✅ Message sent!")
        else:
            bot.reply_to(message, "❌ Send error")


def start_bot_polling():
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"❌ Bot polling error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    # Инициализация конфигурации
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
    os.makedirs("parsing", exist_ok=True)

    send_to_admins("✅ App started!")
    print("🚀 Starting application...")

    # Загружаем конфиг и устанавливаем начальное состояние парсинга
    config = load_config()
    # Убираем global отсюда, так как мы находимся в глобальной области видимости
    # global parsing_enabled
    # Парсинг включен, если новости видны
    parsing_enabled = config.get("news_visible", True)

    print(f"📰 Новости: {'ВКЛ' if config.get('news_visible', True) else 'ВЫКЛ'}")
    print(f"🔄 Парсинг: {'ВКЛ' if parsing_enabled else 'ВЫКЛ'}")

    # Проверяем наличие файла с новостями
    if os.path.exists(POSTS_FILE):
        try:
            with open(POSTS_FILE, "r", encoding="utf-8") as f:
                posts = json.load(f)
            print(f"✅ Загружено {len(posts)} постов из файла")
        except Exception as e:
            print(f"❌ Ошибка загрузки новостей: {e}")
            # Если файл есть, но не читается, запускаем парсинг (если включен)
            if parsing_enabled:
                print("🔄 Запуск парсинга...")
                success = fetch_vk_posts_with_retry(max_retries=2)
                print("✅ Парсинг выполнен" if success else "❌ Парсинг не удался")
    else:
        print("📝 Файл новостей не найден")
        if parsing_enabled:
            print("🔄 Запуск парсинга...")
            success = fetch_vk_posts_with_retry(max_retries=2)
            print("✅ Парсинг выполнен" if success else "❌ Парсинг не удался")
        else:
            print("⚠️ Создаем пустой файл новостей")
            try:
                os.makedirs(os.path.dirname(POSTS_FILE) or ".", exist_ok=True)
                with open(POSTS_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False)
                print("✅ Создан пустой файл новостей")
            except Exception as e:
                print(f"❌ Ошибка создания файла: {e}")

    print("🤖 Starting Telegram bot...")
    threading.Thread(target=start_bot_polling, daemon=True).start()

    print("🌐 Starting web server...")
    server = HTTPServer(("localhost", 8000), Handler)
    print("🌐 Server: http://localhost:8000")

    try:
        launch_edge_simple()
    except:
        print("⚠️ Could not open browser automatically")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⚠️ Server stopped")
        send_to_admins("⚠️ Server stopped")
