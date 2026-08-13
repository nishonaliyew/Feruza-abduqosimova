import asyncio
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="Feruza Abduqosimova Telegram Bot", version="2.6.0")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()

def parse_admin_ids(raw: str) -> set[int]:
    """ADMIN_ID bir yoki bir nechta ID qabul qiladi: 111,222 yoki 111 222."""
    cleaned = raw.replace(";", ",").replace(" ", ",")
    result: set[int] = set()
    for part in cleaned.split(","):
        value = part.strip()
        if value and value.lstrip("-").isdigit():
            result.add(int(value))
    return result

ADMIN_IDS = parse_admin_ids(ADMIN_ID_RAW)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
SETUP_SECRET = os.getenv("SETUP_SECRET", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

TG_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
_http: Optional[httpx.AsyncClient] = None
_bot_id: Optional[int] = None

SECTION_NAMES = {
    "admin": "👨‍💼 Admin",
    "manager": "🧑‍💼 Manager",
    "rahbar": "👔 Rahbar",
    "hamma": "👥 Hamma",
}

PANEL_TEXT = (
    "👋 Assalomu alaykum!\n\n"
    "🤖 FERUZA ABDUQOSIMOVA BOT\n\n"
    "📌 Boshqaruv paneli:"
)


def http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
        )
    return _http


async def tg(method: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    """Telegram API call with one short retry for transient rate limits."""
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN kiritilmagan")

    body = payload or {}
    for attempt in range(2):
        response = await http().post(f"{TG_BASE}/{method}", json=body)
        try:
            data = response.json()
        except Exception:
            data = {"ok": False, "description": response.text[:500]}

        if response.is_success and data.get("ok"):
            return data.get("result")

        retry_after = (data.get("parameters") or {}).get("retry_after")
        if attempt == 0 and response.status_code == 429 and isinstance(retry_after, int) and retry_after <= 3:
            await asyncio.sleep(max(1, retry_after))
            continue

        raise RuntimeError(f"Telegram {method}: {data}")

    raise RuntimeError(f"Telegram {method}: noma'lum xato")


def inline_keyboard(rows: List[List[Dict[str, str]]]) -> Dict[str, Any]:
    return {"inline_keyboard": rows}


def main_menu() -> Dict[str, Any]:
    return inline_keyboard([
        [
            {"text": "👨‍💼 Admin", "callback_data": "send_admin"},
            {"text": "🧑‍💼 Manager", "callback_data": "send_manager"},
        ],
        [
            {"text": "👔 Rahbar", "callback_data": "send_rahbar"},
            {"text": "👥 Hamma", "callback_data": "send_hamma"},
        ],
        [{"text": "📢 Kanal qo‘shish", "callback_data": "channel_add"}],
        [{"text": "📊 Statistika", "callback_data": "show_stats"}],
    ])


def cancel_keyboard() -> Dict[str, Any]:
    return inline_keyboard([[{"text": "⬅️ Bosh menyu", "callback_data": "back_main"}]])


async def sb_request(
    method: str,
    table: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
    prefer: Optional[str] = None,
    allow_conflict: bool = False,
) -> httpx.Response:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL yoki SUPABASE_KEY kiritilmagan")

    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer

    response = await http().request(
        method,
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
        params=params,
        json=json_body,
        headers=headers,
    )
    if allow_conflict and response.status_code == 409:
        return response
    if not response.is_success:
        raise RuntimeError(f"Supabase {table}: {response.status_code} {response.text}")
    return response


async def claim_update(update_id: int) -> bool:
    response = await sb_request(
        "POST",
        "bot_updates",
        json_body={"update_id": update_id},
        prefer="return=minimal",
        allow_conflict=True,
    )
    return response.status_code != 409


async def get_session(user_id: int) -> Dict[str, Any]:
    response = await sb_request(
        "GET",
        "bot_sessions",
        params={"select": "*", "user_id": f"eq.{user_id}", "limit": "1"},
    )
    rows = response.json()
    return rows[0] if rows else {}


async def set_session(user_id: int, **values: Any) -> None:
    row: Dict[str, Any] = {"user_id": user_id}
    allowed = {
        "mode",
        "target",
        "channel_id",
        "channel_title",
        "ui_chat_id",
        "ui_message_id",
    }
    for key in allowed:
        if key in values:
            row[key] = values[key]

    await sb_request(
        "POST",
        "bot_sessions",
        params={"on_conflict": "user_id"},
        json_body=row,
        prefer="resolution=merge-duplicates,return=minimal",
    )


async def reset_session(
    user_id: int,
    *,
    ui_chat_id: Optional[int] = None,
    ui_message_id: Optional[int] = None,
    clear_channel: bool = False,
) -> None:
    """Sessiya rejimini tozalaydi, lekin oxirgi admin qilingan kanalni eslab qoladi.

    Bu private t.me/+... linklar uchun kerak: Bot API private invite linkni
    bevosita chat_id ga aylantirmaydi, shuning uchun my_chat_member orqali olingan
    oxirgi kanal ID sini saqlab turamiz.
    """
    row: Dict[str, Any] = {
        "user_id": user_id,
        "mode": None,
        "target": None,
    }
    if clear_channel:
        row["channel_id"] = None
        row["channel_title"] = None
    if ui_chat_id is not None:
        row["ui_chat_id"] = ui_chat_id
    if ui_message_id is not None:
        row["ui_message_id"] = ui_message_id

    await sb_request(
        "POST",
        "bot_sessions",
        params={"on_conflict": "user_id"},
        json_body=row,
        prefer="resolution=merge-duplicates,return=minimal",
    )


async def upsert_target(chat_id: int, title: str, chat_type: str, section: str) -> None:
    # chat_id primary key bo‘lgani uchun bir chat bir vaqtning o‘zida faqat bitta bo‘limda turadi.
    await sb_request(
        "POST",
        "bot_targets",
        params={"on_conflict": "chat_id"},
        json_body={
            "chat_id": chat_id,
            "title": title,
            "chat_type": chat_type,
            "section": section,
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


async def get_targets(section: Optional[str] = None) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "select": "chat_id,title,chat_type,section,created_at",
        "order": "created_at.asc",
    }
    if section and section != "hamma":
        params["section"] = f"eq.{section}"
    response = await sb_request("GET", "bot_targets", params=params)
    return response.json() or []


def effective_user(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if update.get("callback_query"):
        return update["callback_query"].get("from")
    if update.get("message"):
        return update["message"].get("from")
    return None


def effective_chat(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if update.get("callback_query"):
        message = update["callback_query"].get("message") or {}
        return message.get("chat")
    if update.get("message"):
        return update["message"].get("chat")
    return None


def is_main_admin(update: Dict[str, Any]) -> bool:
    user = effective_user(update)
    return bool(user and user.get("id") in ADMIN_IDS)


async def send_message(chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return await tg("sendMessage", payload)


async def safe_delete(chat_id: int, message_id: int) -> None:
    try:
        await tg("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except Exception:
        pass


async def safe_edit(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "reply_markup": reply_markup or {"inline_keyboard": []},
    }
    try:
        result = await tg("editMessageText", payload)
        return result if isinstance(result, dict) else None
    except Exception as exc:
        # "message is not modified" kabi holat chatni buzmasin.
        if "message is not modified" in str(exc).lower():
            return None
        return None


async def answer_callback(callback_id: str, text: Optional[str] = None, show_alert: bool = False) -> None:
    payload: Dict[str, Any] = {"callback_query_id": callback_id, "show_alert": show_alert}
    if text:
        payload["text"] = text
    try:
        await tg("answerCallbackQuery", payload)
    except Exception:
        pass


async def show_or_replace_panel(
    user_id: int,
    chat_id: int,
    text: str,
    markup: Dict[str, Any],
    *,
    preferred_message_id: Optional[int] = None,
) -> int:
    """Bitta shaxsiy panelni qayta ishlatadi; eski xabarlar ko‘payib ketmaydi."""
    message_id = preferred_message_id
    if message_id is None:
        try:
            session = await get_session(user_id)
            if session.get("ui_chat_id") == chat_id and session.get("ui_message_id"):
                message_id = int(session["ui_message_id"])
        except Exception:
            message_id = None

    if message_id:
        try:
            result = await tg("editMessageText", {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": markup,
            })
            if isinstance(result, dict):
                message_id = int(result.get("message_id", message_id))
            await set_session(user_id, ui_chat_id=chat_id, ui_message_id=message_id)
            return message_id
        except Exception as exc:
            if "message is not modified" in str(exc).lower():
                await set_session(user_id, ui_chat_id=chat_id, ui_message_id=message_id)
                return message_id

    sent = await send_message(chat_id, text, markup)
    new_id = int(sent["message_id"])
    await set_session(user_id, ui_chat_id=chat_id, ui_message_id=new_id)
    return new_id


async def is_group_admin(update: Dict[str, Any]) -> bool:
    chat = effective_chat(update)
    user = effective_user(update)
    if not chat or not user or chat.get("type") not in ("group", "supergroup"):
        return False
    try:
        member = await tg("getChatMember", {"chat_id": chat["id"], "user_id": user["id"]})
        return member.get("status") in ("administrator", "creator")
    except Exception:
        return False


async def get_bot_id() -> int:
    global _bot_id
    if _bot_id is None:
        me = await tg("getMe")
        _bot_id = int(me["id"])
    return _bot_id


async def bot_is_channel_admin(chat_id: int) -> bool:
    try:
        member = await tg("getChatMember", {
            "chat_id": chat_id,
            "user_id": await get_bot_id(),
        })
        return member.get("status") in ("administrator", "creator")
    except Exception:
        return False


def parse_channel_link(text: str) -> Optional[Dict[str, str]]:
    """Public @username va private t.me/+hash / joinchat linklarini taniydi."""
    value = (text or "").strip()
    if not value:
        return None

    if re.fullmatch(r"@[A-Za-z0-9_]{5,32}", value):
        username = value[1:]
        return {"kind": "public", "username": username, "display": f"https://t.me/{username}"}

    # Protokolsiz t.me/... ham qabul qilinsin.
    normalized = value
    if normalized.lower().startswith(("t.me/", "telegram.me/", "www.t.me/", "www.telegram.me/")):
        normalized = "https://" + normalized

    private_match = re.fullmatch(
        r"https?://(?:www\.)?(?:t|telegram)\.me/(?:\+|joinchat/)([A-Za-z0-9_-]+)(?:[/?#].*)?",
        normalized,
        flags=re.IGNORECASE,
    )
    if private_match:
        invite_hash = private_match.group(1)
        return {
            "kind": "private",
            "hash": invite_hash,
            "display": f"https://t.me/+{invite_hash}",
        }

    public_match = re.fullmatch(
        r"https?://(?:www\.)?(?:t|telegram)\.me/([A-Za-z0-9_]{5,32})(?:[/?#].*)?",
        normalized,
        flags=re.IGNORECASE,
    )
    if public_match:
        username = public_match.group(1)
        # Telegramning xizmat yo'llarini kanal username deb qabul qilmaymiz.
        if username.lower() in {"joinchat", "share", "addstickers", "proxy", "socks", "login"}:
            return None
        return {"kind": "public", "username": username, "display": f"https://t.me/{username}"}

    return None


def private_invite_hash(link: Optional[str]) -> Optional[str]:
    parsed = parse_channel_link(link or "")
    if parsed and parsed.get("kind") == "private":
        return parsed.get("hash")
    return None


def channel_section_keyboard() -> Dict[str, Any]:
    return inline_keyboard([
        [{"text": "👨‍💼 Admin", "callback_data": "channel_admin"}],
        [{"text": "🧑‍💼 Manager", "callback_data": "channel_manager"}],
        [{"text": "👔 Rahbar", "callback_data": "channel_rahbar"}],
        [{"text": "⬅️ Bosh menyu", "callback_data": "back_main"}],
    ])


async def show_channel_section_choice(
    user_id: int,
    ui_chat_id: int,
    ui_message_id: Optional[int],
    channel: Dict[str, Any],
) -> None:
    channel_id = int(channel["id"])
    channel_title = channel.get("title") or channel.get("username") or "Kanal"
    await set_session(
        user_id,
        mode="channel_select",
        target=None,
        channel_id=channel_id,
        channel_title=channel_title,
        ui_chat_id=ui_chat_id,
        ui_message_id=ui_message_id,
    )
    await show_or_replace_panel(
        user_id,
        ui_chat_id,
        f"✅ KANAL QABUL QILINDI!\n\n📢 {channel_title}\n\n📌 Qaysi bo‘limga qo‘shamiz?",
        channel_section_keyboard(),
        preferred_message_id=ui_message_id,
    )


async def resolve_channel_from_link(
    parsed: Dict[str, str],
    session: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Linkdan kanalni topadi va bot adminligini tekshiradi.

    Public kanal: @username orqali to'g'ridan-to'g'ri getChat.
    Private kanal: Bot API invite hashni chat_id ga resolve qilmaydi. Shuning uchun
    my_chat_member orqali oldindan eslab qolingan oxirgi admin-kanal ishlatiladi.
    Exact invite hash mos kelsa ustuvor; boshqa admin yaratgan link bo'lsa ham,
    botning o'zi shu kanalda adminligi tasdiqlansa oxirgi kanal qabul qilinadi.
    """
    if parsed.get("kind") == "public":
        username = parsed["username"]
        try:
            chat = await tg("getChat", {"chat_id": f"@{username}"})
        except Exception:
            return None
        if chat.get("type") != "channel":
            return None
        if not await bot_is_channel_admin(int(chat["id"])):
            return None
        return chat

    if parsed.get("kind") != "private":
        return None

    pasted_hash = parsed.get("hash")
    candidate_id = session.get("channel_id")
    candidate_chat: Optional[Dict[str, Any]] = None

    # 1) Avval adminning oxirgi my_chat_member orqali eslab qolingan kanalini tekshiramiz.
    if candidate_id:
        try:
            chat = await tg("getChat", {"chat_id": int(candidate_id)})
            if chat.get("type") == "channel" and await bot_is_channel_admin(int(chat["id"])):
                candidate_chat = chat
                bot_hash = private_invite_hash(chat.get("invite_link"))
                if bot_hash and pasted_hash and bot_hash == pasted_hash:
                    return chat
        except Exception:
            candidate_chat = None

    # 2) Avval qo'shilgan kanallar orasida invite_link aynan mos keladimi tekshiramiz.
    #    Bu kanal qayta bo'limga o'tkazilayotgan holatni ham qo'llaydi.
    try:
        existing = await get_targets()
    except Exception:
        existing = []

    seen: set[int] = set()
    for item in existing:
        if item.get("chat_type") != "channel":
            continue
        try:
            cid = int(item["chat_id"])
        except Exception:
            continue
        if cid in seen or (candidate_id and cid == int(candidate_id)):
            continue
        seen.add(cid)
        try:
            chat = await tg("getChat", {"chat_id": cid})
            if chat.get("type") != "channel" or not await bot_is_channel_admin(cid):
                continue
            bot_hash = private_invite_hash(chat.get("invite_link"))
            if bot_hash and pasted_hash and bot_hash == pasted_hash:
                return chat
        except Exception:
            continue

    # Telegram Bot API boshqa administrator yaratgan private invite linkni resolve qila olmaydi.
    # Foydalanuvchi aynan oldin botni admin qilgan bo'lsa, eslab qolingan kanal — kerakli kanal.
    return candidate_chat


async def handle_channel_link_message(
    update: Dict[str, Any],
    session: Dict[str, Any],
) -> None:
    message = update["message"]
    user_id = int(message["from"]["id"])
    chat_id = int(message["chat"]["id"])
    text = message.get("text") or ""
    ui_message_id = int(session.get("ui_message_id") or 0) or None

    parsed = parse_channel_link(text)
    if not parsed:
        await show_or_replace_panel(
            user_id,
            chat_id,
            "❌ Kanal silkasi noto‘g‘ri.\n\n"
            "Public: https://t.me/kanal_nomi\n"
            "Yopiq: https://t.me/+XXXXXXXX\n\n"
            "🔁 To‘g‘ri silkani yuboring.",
            cancel_keyboard(),
            preferred_message_id=ui_message_id,
        )
        return

    channel = await resolve_channel_from_link(parsed, session)
    if not channel:
        if parsed.get("kind") == "private":
            error_text = (
                "❌ Yopiq kanal topilmadi.\n\n"
                "1️⃣ Shu botni o‘sha kanalga Administrator qiling.\n"
                "2️⃣ Agar bot avvaldan admin bo‘lsa, uni bir marta adminlikdan olib, qayta Administrator qiling.\n"
                "3️⃣ So‘ng shu private silkani yana yuboring.\n\n"
                "⚠️ Bot kanalda admin bo‘lmasa private kanalni aniqlab bo‘lmaydi."
            )
        else:
            error_text = (
                "❌ Kanal topilmadi yoki bot bu kanalda Administrator emas.\n\n"
                "Avval botni kanalga Administrator qiling, keyin silkani yana yuboring."
            )
        await show_or_replace_panel(
            user_id,
            chat_id,
            error_text,
            cancel_keyboard(),
            preferred_message_id=ui_message_id,
        )
        return

    await show_channel_section_choice(user_id, chat_id, ui_message_id, channel)


async def handle_start(update: Dict[str, Any]) -> None:
    message = update["message"]
    chat = message["chat"]
    user_id = message["from"]["id"]

    if chat.get("type") != "private":
        # Guruhda /start kerak emas. Foydalanuvchi yozgan komandani o‘chirmaymiz.
        return

    if not is_main_admin(update):
        await send_message(chat["id"], "🔒 Bu bot faqat administrator tomonidan boshqariladi.")
        return

    # /start foydalanuvchi xabari — o‘chirilmaydi.
    # Har /start bosilganda panelni chatning eng pastiga YANGI xabar qilib yuboramiz.
    # Eski panelni edit qilish foydalanuvchiga "bot javob bermadi"dek ko‘rinishi mumkin edi.
    sent = await send_message(chat["id"], PANEL_TEXT, main_menu())
    panel_id = int(sent["message_id"])
    await reset_session(user_id, ui_chat_id=chat["id"], ui_message_id=panel_id)


async def handle_qoshish(update: Dict[str, Any]) -> None:
    message = update["message"]
    chat = message["chat"]

    if chat.get("type") not in ("group", "supergroup"):
        return

    if not await is_group_admin(update):
        return

    keyboard = inline_keyboard([
        [{"text": "👨‍💼 Admin", "callback_data": "group_admin"}],
        [{"text": "🧑‍💼 Manager", "callback_data": "group_manager"}],
        [{"text": "👔 Rahbar", "callback_data": "group_rahbar"}],
    ])
    await send_message(chat["id"], "📌 Ushbu guruhni qaysi bo‘limga qo‘shamiz?", keyboard)
    # /qoshish — foydalanuvchi xabari. Uni bot o‘chirmaydi.


async def save_group(update: Dict[str, Any], target: str) -> None:
    query = update["callback_query"]
    chat = effective_chat(update) or {}

    # Callback spinneri qotib qolmasin.
    await answer_callback(query["id"])

    if not await is_group_admin(update):
        await answer_callback(query["id"], "🔒 Faqat guruh administratori!", True)
        return

    title = chat.get("title") or "Noma’lum guruh"
    await upsert_target(int(chat["id"]), title, chat.get("type", "group"), target)

    # Guruh chatini clean saqlaymiz: tanlash xabari ham yo‘qoladi.
    await safe_delete(int(chat["id"]), int(query["message"]["message_id"]))


async def channel_add(update: Dict[str, Any]) -> None:
    query = update["callback_query"]
    user_id = int(query["from"]["id"])
    chat_id = int(query["message"]["chat"]["id"])
    message_id = int(query["message"]["message_id"])

    if not is_main_admin(update):
        await answer_callback(query["id"], "🔒 Sizda ruxsat yo‘q!", True)
        return

    await answer_callback(query["id"])
    # Oxirgi my_chat_member kanalini O'CHIRMAYMIZ — private linkni shundan taniymiz.
    await set_session(
        user_id,
        mode="channel_wait_link",
        target=None,
        ui_chat_id=chat_id,
        ui_message_id=message_id,
    )

    await show_or_replace_panel(
        user_id,
        chat_id,
        (
            "📢 KANAL QO‘SHISH\n\n"
            "🔗 Kanal silkasini yuboring.\n\n"
            "✅ Ochiq kanal: https://t.me/kanal_nomi\n"
            "✅ Yopiq kanal: https://t.me/+XXXXXXXX\n\n"
            "⚠️ Silka yuborishdan OLDIN bot shu kanalda Administrator bo‘lishi kerak."
        ),
        cancel_keyboard(),
        preferred_message_id=message_id,
    )


async def handle_my_chat_member(update: Dict[str, Any]) -> None:
    """Bot kanalga admin qilinganda kanal ID sini eslab qoladi, lekin avtomatik qo'shmaydi."""
    event = update.get("my_chat_member") or {}
    chat = event.get("chat") or {}
    new_member = event.get("new_chat_member") or {}

    if chat.get("type") != "channel":
        return
    if new_member.get("status") not in ("administrator", "creator"):
        return

    channel_id = int(chat["id"])
    channel_title = chat.get("title") or "Yopiq kanal"
    try:
        full_chat = await tg("getChat", {"chat_id": channel_id})
        channel_title = full_chat.get("title") or channel_title
    except Exception:
        pass

    # Qaysi configured admin keyin link yuborishini oldindan bilmaymiz.
    # Shuning uchun oxirgi admin qilingan kanalni barcha bot-adminlar sessiyasida eslab qolamiz.
    for admin_id in ADMIN_IDS:
        try:
            await set_session(
                int(admin_id),
                channel_id=channel_id,
                channel_title=channel_title,
            )
        except Exception as exc:
            print(f"CHANNEL CACHE ERROR {admin_id}: {exc}")


async def save_channel(update: Dict[str, Any], target: str) -> None:
    query = update["callback_query"]
    user_id = query["from"]["id"]
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]

    if not is_main_admin(update):
        await answer_callback(query["id"], "🔒 Sizda ruxsat yo‘q!", True)
        return

    await answer_callback(query["id"])
    session = await get_session(user_id)
    channel_id = session.get("channel_id")
    channel_title = session.get("channel_title") or "Kanal"

    if not channel_id:
        await reset_session(user_id, ui_chat_id=chat_id, ui_message_id=message_id)
        await show_or_replace_panel(
            user_id,
            chat_id,
            "❌ Kanal ma’lumoti topilmadi. Qayta urinib ko‘ring.\n\n" + PANEL_TEXT,
            main_menu(),
            preferred_message_id=message_id,
        )
        return

    await upsert_target(int(channel_id), channel_title, "channel", target)
    await reset_session(user_id, ui_chat_id=chat_id, ui_message_id=message_id)
    await show_or_replace_panel(
        user_id,
        chat_id,
        f"✅ KANAL QO‘SHILDI!\n\n📢 {channel_title}\n📌 Bo‘lim: {SECTION_NAMES[target]}\n\n📌 Boshqaruv paneli:",
        main_menu(),
        preferred_message_id=message_id,
    )


async def show_stats(update: Dict[str, Any]) -> None:
    query = update["callback_query"]
    user_id = query["from"]["id"]
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]

    if not is_main_admin(update):
        await answer_callback(query["id"], "🔒 Sizda ruxsat yo‘q!", True)
        return

    await answer_callback(query["id"])
    items = await get_targets()
    stats = {s: {"channels": 0, "groups": 0} for s in ("admin", "manager", "rahbar")}
    for item in items:
        section = item.get("section")
        if section not in stats:
            continue
        if item.get("chat_type") == "channel":
            stats[section]["channels"] += 1
        else:
            stats[section]["groups"] += 1

    total_channels = sum(v["channels"] for v in stats.values())
    total_groups = sum(v["groups"] for v in stats.values())
    text = (
        "📊 BOT STATISTIKASI\n\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📢 Jami kanallar: {total_channels} ta\n"
        f"👥 Jami guruhlar: {total_groups} ta\n"
        f"📌 Jami obyektlar: {total_channels + total_groups} ta\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"👨‍💼 ADMIN\n📢 Kanallar: {stats['admin']['channels']} ta\n👥 Guruhlar: {stats['admin']['groups']} ta\n\n"
        f"🧑‍💼 MANAGER\n📢 Kanallar: {stats['manager']['channels']} ta\n👥 Guruhlar: {stats['manager']['groups']} ta\n\n"
        f"👔 RAHBAR\n📢 Kanallar: {stats['rahbar']['channels']} ta\n👥 Guruhlar: {stats['rahbar']['groups']} ta"
    )

    await reset_session(user_id, ui_chat_id=chat_id, ui_message_id=message_id)
    await show_or_replace_panel(user_id, chat_id, text, main_menu(), preferred_message_id=message_id)


async def select_send_target(update: Dict[str, Any], target: str) -> None:
    query = update["callback_query"]
    user_id = query["from"]["id"]
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]

    if not is_main_admin(update):
        await answer_callback(query["id"], "🔒 Sizda ruxsat yo‘q!", True)
        return

    await answer_callback(query["id"])
    await set_session(
        user_id,
        mode="send",
        target=target,
        ui_chat_id=chat_id,
        ui_message_id=message_id,
    )
    await show_or_replace_panel(
        user_id,
        chat_id,
        f"✅ {SECTION_NAMES[target]} tanlandi!\n\n"
        "📨 Endi yubormoqchi bo‘lgan xabaringizni jo‘nating.\n\n"
        "✍️ Matn  🖼 Rasm  🎥 Video\n📄 Fayl  🎵 Audio  📹 Boshqa xabar",
        cancel_keyboard(),
        preferred_message_id=message_id,
    )


async def distribute_message(update: Dict[str, Any], target: str, session: Dict[str, Any]) -> None:
    message = update["message"]
    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]
    input_message_id = message["message_id"]
    ui_message_id = int(session.get("ui_message_id") or 0) or None

    targets = await get_targets(target)
    if not targets:
        # Admin yuborgan original xabar saqlanadi.
        panel_id = await show_or_replace_panel(
            user_id,
            chat_id,
            "⚠️ Bu bo‘limga hali kanal yoki guruh qo‘shilmagan.\n\n" + PANEL_TEXT,
            main_menu(),
            preferred_message_id=ui_message_id,
        )
        await reset_session(user_id, ui_chat_id=chat_id, ui_message_id=panel_id)
        return

    semaphore = asyncio.Semaphore(8)

    async def copy_one(item: Dict[str, Any]) -> bool:
        async with semaphore:
            try:
                await tg("copyMessage", {
                    "chat_id": item["chat_id"],
                    "from_chat_id": chat_id,
                    "message_id": input_message_id,
                })
                return True
            except Exception as exc:
                print(f"COPY ERROR {item.get('chat_id')}: {exc}")
                return False

    results = await asyncio.gather(*(copy_one(item) for item in targets))
    success = sum(1 for ok in results if ok)
    failed = len(results) - success

    # Tarqatish tugagach ham admin yuborgan original xabarni o‘chirmaymiz.
    panel_id = await show_or_replace_panel(
        user_id,
        chat_id,
        f"📤 XABAR TARQATILDI!\n\n✅ Yuborildi: {success}\n❌ Xatolik: {failed}\n\n📌 Boshqaruv paneli:",
        main_menu(),
        preferred_message_id=ui_message_id,
    )
    await reset_session(user_id, ui_chat_id=chat_id, ui_message_id=panel_id)


async def back_main(update: Dict[str, Any]) -> None:
    query = update["callback_query"]
    user_id = query["from"]["id"]
    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]

    if not is_main_admin(update):
        await answer_callback(query["id"], "🔒 Sizda ruxsat yo‘q!", True)
        return

    await answer_callback(query["id"])
    await reset_session(user_id, ui_chat_id=chat_id, ui_message_id=message_id)
    await show_or_replace_panel(user_id, chat_id, PANEL_TEXT, main_menu(), preferred_message_id=message_id)


async def handle_callback(update: Dict[str, Any]) -> None:
    query = update["callback_query"]
    data = query.get("data", "")

    if data == "back_main":
        await back_main(update)
    elif data == "channel_add":
        await channel_add(update)
    elif data.startswith("channel_") and data.split("_", 1)[1] in ("admin", "manager", "rahbar"):
        await save_channel(update, data.split("_", 1)[1])
    elif data.startswith("group_") and data.split("_", 1)[1] in ("admin", "manager", "rahbar"):
        await save_group(update, data.split("_", 1)[1])
    elif data.startswith("send_") and data.split("_", 1)[1] in ("admin", "manager", "rahbar", "hamma"):
        await select_send_target(update, data.split("_", 1)[1])
    elif data == "show_stats":
        await show_stats(update)
    else:
        await answer_callback(query["id"])


async def handle_private_message(update: Dict[str, Any]) -> None:
    message = update["message"]
    if not is_main_admin(update):
        return

    user_id = message["from"]["id"]
    chat_id = message["chat"]["id"]
    session = await get_session(user_id)
    mode = session.get("mode")

    if mode == "channel_wait_link":
        await handle_channel_link_message(update, session)
        return

    if mode == "send" and session.get("target"):
        await distribute_message(update, session["target"], session)
        return

    # Rejim tanlanmagan bo‘lsa ham foydalanuvchi xabarini o‘chirmaymiz.
    # Faqat mavjud bot panelini yangilaymiz.
    preferred = int(session.get("ui_message_id") or 0) or None
    panel_id = await show_or_replace_panel(
        user_id,
        chat_id,
        "⚠️ Avval boshqaruv panelidan kerakli bo‘limni tanlang.\n\n" + PANEL_TEXT,
        main_menu(),
        preferred_message_id=preferred,
    )
    await reset_session(user_id, ui_chat_id=chat_id, ui_message_id=panel_id)


async def process_update(update: Dict[str, Any]) -> None:
    if update.get("my_chat_member"):
        await handle_my_chat_member(update)
        return

    if update.get("callback_query"):
        await handle_callback(update)
        return

    message = update.get("message")
    if not message:
        return

    text = message.get("text") or ""
    command = text.split()[0].split("@", 1)[0].lower() if text.startswith("/") else ""

    if command == "/start":
        await handle_start(update)
    elif command == "/qoshish":
        await handle_qoshish(update)
    elif message.get("chat", {}).get("type") == "private":
        await handle_private_message(update)


@app.get("/")
async def root():
    return {
        "ok": True,
        "service": "feruza-abduqosimova-bot",
        "version": "2.6.0",
        "mode": "telegram-webhook",
        "database": "supabase",
    }


@app.get("/health")
async def health():
    missing = [
        name
        for name, value in {
            "BOT_TOKEN": BOT_TOKEN,
            "ADMIN_ID": ADMIN_IDS,
            "SUPABASE_URL": SUPABASE_URL,
            "SUPABASE_KEY": SUPABASE_KEY,
            "SETUP_SECRET": SETUP_SECRET,
            "WEBHOOK_SECRET": WEBHOOK_SECRET,
        }.items()
        if not value
    ]
    return {"ok": not missing, "missing_env": missing}


@app.get("/setup")
async def setup(request: Request, secret: str):
    if not SETUP_SECRET or secret != SETUP_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    domain = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
    if domain:
        webhook_url = f"https://{domain}/webhook"
    else:
        webhook_url = str(request.base_url).rstrip("/") + "/webhook"

    result = await tg("setWebhook", {
        "url": webhook_url,
        "secret_token": WEBHOOK_SECRET,
        "allowed_updates": ["message", "callback_query", "my_chat_member"],
        "drop_pending_updates": True,
    })
    info = await tg("getWebhookInfo")
    return {"ok": True, "setWebhook": result, "webhook": info}


@app.get("/status")
async def status(secret: str):
    if not SETUP_SECRET or secret != SETUP_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    info = await tg("getWebhookInfo")
    return {"ok": True, "webhook": info}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    update = await request.json()
    update_id = update.get("update_id")
    if isinstance(update_id, int):
        try:
            if not await claim_update(update_id):
                return {"ok": True, "duplicate": True}
        except Exception as exc:
            print(f"UPDATE CLAIM ERROR: {exc}")

    try:
        await process_update(update)
    except Exception as exc:
        print(f"UPDATE ERROR: {exc}")
        # 200 qaytaramiz: Telegram aynan shu update'ni qayta-qayta yuborib qolmasin.
        return {"ok": False, "error": "processing_failed"}

    return {"ok": True}
