from pathlib import Path
import re
import copy
import hashlib
import requests
import base64
import urllib.parse
import json
import os
import secrets

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ============================================================
# CONFIGURATION
# ============================================================

# IMPORTANT:
# Put your NEW BotFather token here.
BOT_TOKEN = "8869433889:AAGxCuFn-H7AieyrvZ8UTYVfSswzgkhT-Bk"

# Your Telegram ID
OWNER_ID = 8104305090

SECRET_KEY = "Telugumovies40SecretKey123"

# Put your Cloudflare Tunnel URL here
# Example:
# https://xxxx.trycloudflare.com
WEB_DOMAIN = "https://nyxen-playground-hidden-truth-2a5b.rolexoriginalstg.workers.dev"

CHANNEL_NAME = "eMpTy"

BANNER_IMAGE = "https://kotaku.com/app/uploads/2026/08/doom.jpg"


# ============================================================
# PREMIUM USER DATABASE
# ============================================================

PREMIUM_FILE = "premium_users.json"








def is_premium(user_id):
    """
    Owner always has premium access.
    Other users are checked against premium_users.
    """

    user_id = str(user_id)

    # --------------------------------------------------------
    # OWNER ALWAYS ALLOWED
    # --------------------------------------------------------

    try:
        if str(user_id) == str(OWNER_ID):
            return True
    except Exception:
        pass

    # --------------------------------------------------------
    # PREMIUM USERS
    # --------------------------------------------------------

    try:
        users = premium_users
    except NameError:
        return False

    if isinstance(users, dict):

        if user_id in users:
            return True

        try:
            if int(user_id) in users:
                return True
        except Exception:
            pass

        return False

    if isinstance(users, (list, tuple, set)):

        return user_id in {
            str(x)
            for x in users
        }

    return False

async def require_premium(update: Update):
    user = update.effective_user

    if not user:
        return False

    if is_premium(user.id):
        return True

    await update.effective_message.reply_text(
        "🔒 Premium Access Required\n\n"
        "You are not authorized to use this bot.\n\n"
        "💎 Only premium users can generate links."
    )

    return False

def register_bot_user(user_id):
    user_id = str(user_id)

    try:
        users = {}

        path = Path("bot_users.json")

        if path.exists():
            try:
                data = json.loads(path.read_text())
                if isinstance(data, dict):
                    users = data
            except Exception:
                users = {}

        if user_id not in users:
            users[user_id] = {
                "id": int(user_id)
            }

            path.write_text(
                json.dumps(users, indent=4)
            )

        return True

    except Exception as e:
        print("Error registering bot user:", e)
        return False


def load_premium_users():
    if not os.path.exists(PREMIUM_FILE):
        return []

    try:
        with open(PREMIUM_FILE, "r") as f:
            data = json.load(f)

        if isinstance(data, list):
            return [int(user_id) for user_id in data]

    except Exception as e:
        print("Error loading premium users:", e)

    return []


def save_premium_users(users):
    try:
        users = sorted(set(int(user_id) for user_id in users))

        with open(PREMIUM_FILE, "w") as f:
            json.dump(users, f, indent=4)

        return True

    except Exception as e:
        print("Error saving premium users:", e)
        return False


premium_users = load_premium_users()
# ============================================================
# SHORTENER MANAGER
# ============================================================
SHORTENERS_FILE = "shorteners.json"


def load_shorteners():
    if not os.path.exists(SHORTENERS_FILE):
        return {"users": {}}

    try:
        with open(SHORTENERS_FILE, "r") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return {"users": {}}

        if "users" not in data:
            data = {
                "users": {
                    str(OWNER_ID): data
                }
            }

        if not isinstance(data.get("users"), dict):
            data["users"] = {}

        return data

    except Exception as e:
        print("Error loading shorteners:", e)
        return {"users": {}}


def save_shorteners(data):
    try:
        with open(SHORTENERS_FILE, "w") as f:
            json.dump(data, f, indent=4)
        return True

    except Exception as e:
        print("Error saving shorteners:", e)
        return False


shorteners = load_shorteners()


def get_user_shortener(user_id):
    user_id = str(user_id)

    users = shorteners.setdefault("users", {})

    config = users.get(user_id, {})

    if not isinstance(config, dict):
        return {}

    return config

def get_user_shorteners(user_id):
    """
    Compatibility wrapper for the old link-processing code.

    The current system allows exactly ONE shortener per user.
    The old processing code expects get_user_shorteners(),
    so return the current user's single configuration in
    dictionary form.
    """

    config = get_user_shortener(user_id)

    if not config:
        return {}

    domain = str(
        config.get("domain", "")
    ).strip()

    if not domain:
        return {}

    return {
        domain: config
    }


def normalize_shortener_domain(domain):
    domain = str(domain).strip().lower()
    domain = domain.replace("https://", "")
    domain = domain.replace("http://", "")
    return domain.rstrip("/")



def _get_shortened_url_impl(target_url, user_id=None):

    if user_id is None:
        user_id = OWNER_ID

    config = get_user_shortener(user_id)

    if not config:
        print("No shortener configured for user:", user_id)
        return target_url, "No shortener configured"

    if not config.get("enabled", True):
        return target_url, "Shortener disabled"

    domain = str(config.get("domain", "")).strip()
    api_key = str(config.get("api_key", "")).strip()

    if not domain or not api_key:
        return target_url, "Invalid shortener configuration"

    try:

        endpoint = (
            f"https://{domain}/api"
            f"?api={urllib.parse.quote(api_key)}"
            f"&url={urllib.parse.quote(target_url, safe='')}"
        )

        print("Trying shortener:", domain)

        response = requests.get(
            endpoint,
            timeout=15
        )

        print(
            domain,
            "HTTP status:",
            response.status_code
        )

        response.raise_for_status()

        data = response.json()

        shortened_url = (
            data.get("shortenedUrl")
            or data.get("shortened_url")
            or data.get("shorturl")
            or data.get("url")
        )

        if shortened_url:

            print(
                "Shortener succeeded:",
                domain
            )

            return shortened_url, domain

        return target_url, "Shortener returned no URL"

    except Exception as e:

        print(
            "Shortener failed:",
            domain,
            e
        )

        return target_url, "Shortener request failed"



def get_shortened_url(target_url, user_id=None):
    """
    Safe public shortener wrapper.

    Correct order:
        target_url, user_id

    Also protects against the old broken call order.
    """

    # --------------------------------------------------------
    # Defensive correction for the OLD broken order:
    #
    # get_shortened_url(user_id, verification_url)
    #
    # If target_url looks like a Telegram user ID and
    # user_id looks like a URL, swap them.
    # --------------------------------------------------------

    if (
        user_id is not None
        and str(target_url).strip().isdigit()
        and str(user_id).strip().startswith(
            ("http://", "https://")
        )
    ):
        target_url, user_id = user_id, target_url

    if user_id is None:
        try:
            print(
                "❌ Shortener called without user ID"
            )
        except Exception:
            pass

        return (
            target_url,
            "No shortener configured"
        )

    try:
        user_id = int(user_id)
    except Exception:
        return (
            target_url,
            "No shortener configured"
        )

    # --------------------------------------------------------
    # Call the existing implementation.
    # --------------------------------------------------------

    result = _get_shortened_url_impl(
        target_url,
        user_id
    )

    if not isinstance(result, tuple):
        return (
            target_url,
            "No shortener configured"
        )

    if len(result) < 2:
        return (
            target_url,
            "No shortener configured"
        )

    short_url = result[0]
    domain = result[1]

    short_url = (
        str(short_url).strip()
        if short_url is not None
        else ""
    )

    domain = (
        str(domain).strip().rstrip("/")
        if domain is not None
        else ""
    )

    # --------------------------------------------------------
    # Reject empty/error values.
    # --------------------------------------------------------

    if not short_url:
        return (
            target_url,
            "No shortener configured"
        )

    bad_values = {
        "none",
        "null",
        "false",
        "no shortener configured",
        "error",
    }

    if short_url.lower() in bad_values:
        return (
            target_url,
            "No shortener configured"
        )

    # --------------------------------------------------------
    # If API returns a complete URL, use it.
    # --------------------------------------------------------

    if short_url.startswith(
        ("http://", "https://")
    ):
        return short_url, domain

    # --------------------------------------------------------
    # VPLink sometimes returns an ID/slug.
    #
    # NEVER display OWNER_ID as if it were the URL.
    # Turn a numeric/slug response into:
    #
    # https://domain/response
    # --------------------------------------------------------

    if domain:

        short_url = (
            "https://"
            + domain
            + "/"
            + short_url.lstrip("/")
        )

        return short_url, domain

    return (
        target_url,
        "No shortener configured"
    )


# ============================================================
# GENERATE VERIFIED LINK
# ============================================================

async def process_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    raw_link
):

    if not await require_premium(update):
        return

    # User must configure at least one shortener before generating links.
    user_id = str(update.effective_user.id)
    user_shortener = get_user_shortener(user_id)

    if not user_shortener:
        await update.effective_message.reply_text(
            "❌ No shortener configured on your account.\n\n"
            "Use:\n"
            "/setshortner DOMAIN API_KEY"
        )
        return

    user_shorteners = {
        str(user_shortener.get("domain", "")): user_shortener
    }

    if not user_shorteners:
        await update.effective_message.reply_text(
            "⚠️ Please set or configure a Shortner first to generate links.\n\n"
            "Use /setshortner DOMAIN API_KEY"
        )
        return

    if not raw_link.startswith(("http://", "https://")):

        await update.effective_message.reply_text(
            "❌ Please send a valid HTTP/HTTPS link."
        )

        return

    if WEB_DOMAIN.startswith("PASTE_"):

        await update.effective_message.reply_text(
            "❌ WEB_DOMAIN is not configured.\n\n"
            "Set your Cloudflare Tunnel URL in bot.py."
        )

        return

    try:

        # ----------------------------------------------------
        # Strong token system (sid + nonce + hash)
        # ----------------------------------------------------

        encoded_target = base64.b64encode(
            raw_link.encode("utf-8")
        ).decode("utf-8")

        sid = secrets.token_hex(16)      # 32 chars
        nonce = secrets.token_hex(8)     # 16 chars

        raw_hash = f"{encoded_target}:{sid}:{nonce}:{SECRET_KEY}"
        hash_code = hashlib.sha256(
            raw_hash.encode("utf-8")
        ).hexdigest()[:16]

        verify_url = (
            f"{WEB_DOMAIN.rstrip('/')}/verify"
            f"?sid={sid}"
            f"&hash={hash_code}"
            f"&nonce={nonce}"
            f"&t={urllib.parse.quote(encoded_target)}"
        )

        print("Verification URL:")
        print(verify_url)

        # ----------------------------------------------------
        # VPLink
        # ----------------------------------------------------

        short_url, shortener_used = get_shortened_url(verify_url, str(update.effective_user.id))

        # ----------------------------------------------------
        # Send result
        # ----------------------------------------------------

        await update.effective_message.reply_photo(
    photo=BANNER_IMAGE,
    caption=(
        "🎬 *eMpTy | Premium Security Link*\n\n"
        "🔗 *Original Link:*\n"
        f"{raw_link}\n\n"
        "🔐 *Protected Short Link:*\n"
        f"{short_url}\n\n"
        f"⚡ *Shortener:* {shortener_used}\n\n"
        "🛡️ *Security:* Verified & Protected\n\n"
        "✨ Complete the verification process "
        "to securely unlock your destination.\n\n"
        "🤖 *Powered by RoL3X*"
    ),
    parse_mode=None
)

    except Exception as e:

        print("Link processing error:", e)

        await update.effective_message.reply_text(
            "❌ Error while generating the link.\n\n"
            "Please try again."
        )


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if user:
        register_bot_user(user.id)

    if not await require_premium(update):
        return

    if context.args:

        raw_link = context.args[0]

        await process_and_reply(
            update,
            context,
            raw_link
        )

        return

    await update.effective_message.reply_photo(
        photo=BANNER_IMAGE,
        caption=(
            f"🔐 WELCOME TO {CHANNEL_NAME} PREMIUM BOT\n\n"
            "🛡️ Premium Security • Anti-Bypass Protection\n\n"
            "Your links are protected through our Secure Shortner Verification System.\n\n"
            "💎 Premium Access: ENABLED\n\n"
            "🔗 Send any HTTP/HTTPS movie or file link to generate a secure verified link using your configured Shortners.\n\n"
            "⚡ Fast • Secure • Multi-Shortner\n"
            "🛡️ Anti-Bypass Protection\n"
            "🔒 Verified Access System\n\n"
            "📚 Use /help to explore available commands.\n\n"
            "❤️‍🔥 eMpTy — Secure. Verified. Protected."
        )
    )


# ============================================================
# NORMAL URL MESSAGE
# ============================================================



URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+',
    re.IGNORECASE
)


def find_message_urls(text):

    results = []

    if not text:
        return results

    trailing = ".,!?;:)]}>\"'”’"

    for match in URL_PATTERN.finditer(text):

        url = match.group(0).rstrip(trailing)

        if not url:
            continue

        start = match.start()
        end = start + len(url)

        results.append(
            (start, end, url)
        )

    return results


def replace_urls_in_text(
    text,
    replacements
):

    if not replacements:
        return text

    output = []
    position = 0

    for start, end, old_url, new_url in replacements:

        output.append(
            text[position:start]
        )

        output.append(new_url)

        position = end

    output.append(
        text[position:]
    )

    return "".join(output)


async def send_bulk_result(
    update,
    original_text,
    replacements
):

    message = update.effective_message

    new_text = replace_urls_in_text(
        original_text,
        replacements
    )

    entities = (
        list(message.entities or [])
        if message.text is not None
        else list(message.caption_entities or [])
    )

    # For bulk mode we deliberately preserve
    # the original visible formatting by sending
    # the transformed text with Telegram entities.
    #
    # If an entity becomes invalid because a URL
    # changed length, Telegram may reject it.
    # In that case we safely send the transformed
    # text without entities rather than crashing.

    try:

        if message.text is not None:

            await message.reply_text(
                new_text,
                entities=entities
            )

            return

        if message.photo:

            await message.reply_photo(
                photo=message.photo[-1].file_id,
                caption=new_text,
                caption_entities=entities
            )

            return

        if message.document:

            await message.reply_document(
                document=message.document.file_id,
                caption=new_text,
                caption_entities=entities
            )

            return

        if message.video:

            await message.reply_video(
                video=message.video.file_id,
                caption=new_text,
                caption_entities=entities
            )

            return

        if message.animation:

            await message.reply_animation(
                animation=message.animation.file_id,
                caption=new_text,
                caption_entities=entities
            )

            return

        if message.audio:

            await message.reply_audio(
                audio=message.audio.file_id,
                caption=new_text,
                caption_entities=entities
            )

            return

        await message.reply_text(
            new_text,
            entities=entities
        )

    except Exception as e:

        print(
            "Formatting-preservation fallback:",
            e
        )

        if message.text is not None:

            await message.reply_text(
                new_text
            )

        elif message.photo:

            await message.reply_photo(
                photo=message.photo[-1].file_id
            )

            await message.reply_text(
                new_text
            )

        elif message.document:

            await message.reply_document(
                document=message.document.file_id
            )

            await message.reply_text(
                new_text
            )

        elif message.video:

            await message.reply_video(
                video=message.video.file_id
            )

            await message.reply_text(
                new_text
            )

        else:

            await message.reply_text(
                new_text
            )




URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+',
    re.IGNORECASE
)


def _find_urls(text):
    """
    Find HTTP/HTTPS URLs in a Telegram message.

    Returns:
        [
            (start_position, end_position, clean_url),
            ...
        ]
    """

    results = []

    if not text:
        return results

    trailing = ".,!?;:)]}>\"'”’"

    for match in URL_PATTERN.finditer(text):

        raw_url = match.group(0)

        clean_url = raw_url.rstrip(trailing)

        if not clean_url:
            continue

        start = match.start()
        end = start + len(clean_url)

        results.append(
            (
                start,
                end,
                clean_url
            )
        )

    return results





def _replace_urls_preserve_entities(
    source_text,
    source_entities,
    replacements,
):
    """
    Replace URLs while preserving Telegram formatting.

    Telegram entity offsets/lengths use UTF-16 units.
    Python string indexes do not.
    This function converts correctly between both.
    """

    if not source_text:
        return source_text, []

    replacements = sorted(
        replacements or [],
        key=lambda x: x[0]
    )

    # --------------------------------------------------------
    # Keep only valid URL replacements.
    # --------------------------------------------------------

    valid = []

    for item in replacements:

        if len(item) != 4:
            continue

        start, end, old_url, new_url = item

        try:
            start = int(start)
            end = int(end)
        except Exception:
            continue

        new_url = str(new_url or "").strip()

        if start < 0:
            continue

        if end <= start:
            continue

        if end > len(source_text):
            continue

        if not new_url.startswith(("http://", "https://")):
            continue

        valid.append(
            (start, end, str(old_url), new_url)
        )

    # --------------------------------------------------------
    # Build new text.
    # --------------------------------------------------------

    pieces = []
    cursor = 0
    final_replacements = []

    for start, end, old_url, new_url in valid:

        if start < cursor:
            continue

        # Make sure the source actually contains the URL.
        if source_text[start:end] != old_url:
            # Still allow it if the supplied old URL differs
            # only because of Telegram entity representation.
            old_url = source_text[start:end]

        pieces.append(source_text[cursor:start])
        pieces.append(new_url)

        final_replacements.append(
            (start, end, old_url, new_url)
        )

        cursor = end

    pieces.append(source_text[cursor:])

    result = "".join(pieces)

    # --------------------------------------------------------
    # UTF-16 helpers.
    # --------------------------------------------------------

    def u16_len(value):
        return len(value.encode("utf-16-le")) // 2

    def python_index_from_u16(text, wanted):
        current = 0

        for index, char in enumerate(text):

            if current == wanted:
                return index

            current += u16_len(char)

        if current == wanted:
            return len(text)

        return None

    # --------------------------------------------------------
    # Map an old Python position to a new Python position.
    #
    # Positions at the beginning of a replacement map to the
    # beginning of the new URL.
    #
    # Positions at/after the end map after the new URL.
    # --------------------------------------------------------

    def map_position(position):

        shift = 0

        for start, end, old_url, new_url in final_replacements:

            if position < start:
                break

            if position >= end:
                shift += len(new_url) - (end - start)
                continue

            # Position lies inside replaced URL.
            return start + shift

        return position + shift

    # --------------------------------------------------------
    # Rebuild entities.
    # --------------------------------------------------------

    rebuilt = []

    try:
        from telegram import MessageEntity
    except Exception:
        return result, []

    for entity in source_entities or []:

        try:

            old_u16_start = int(entity.offset)
            old_u16_end = (
                old_u16_start
                + int(entity.length)
            )

            old_start = python_index_from_u16(
                source_text,
                old_u16_start
            )

            old_end = python_index_from_u16(
                source_text,
                old_u16_end
            )

            if old_start is None or old_end is None:
                continue

            if old_end <= old_start:
                continue

            # ------------------------------------------------
            # Map both boundaries.
            # ------------------------------------------------

            new_start = map_position(old_start)
            new_end = map_position(old_end)

            if new_start is None or new_end is None:
                continue

            if new_end <= new_start:
                continue

            if new_start < 0 or new_end > len(result):
                continue

            # ------------------------------------------------
            # Preserve entity attributes.
            # ------------------------------------------------

            kwargs = {
                "type": entity.type,
                "offset": u16_len(
                    result[:new_start]
                ),
                "length": u16_len(
                    result[new_start:new_end]
                ),
            }

            for attr in (
                "url",
                "user",
                "language",
                "custom_emoji_id",
            ):

                value = getattr(
                    entity,
                    attr,
                    None
                )

                if value is not None:
                    kwargs[attr] = value

            # ------------------------------------------------
            # If the original entity was TEXT_LINK and its
            # destination itself was replaced, point it at the
            # new URL.
            # ------------------------------------------------

            if entity.type == MessageEntity.TEXT_LINK:

                for r_start, r_end, old_url, new_url in final_replacements:

                    if (
                        old_start <= r_start
                        and old_end >= r_end
                    ):
                        kwargs["url"] = new_url
                        break

            # ------------------------------------------------
            # Telegram only accepts valid UTF-16 ranges.
            # ------------------------------------------------

            final_offset = kwargs["offset"]
            final_length = kwargs["length"]

            total_u16 = u16_len(result)

            if final_offset < 0:
                continue

            if final_length <= 0:
                continue

            if final_offset + final_length > total_u16:
                continue

            try:
                rebuilt.append(
                    MessageEntity(**kwargs)
                )
            except Exception as exc:
                print(
                    "Entity reconstruction warning:",
                    repr(exc)
                )

        except Exception as exc:
            print(
                "Entity processing warning:",
                repr(exc)
            )

    return result, rebuilt






async def _send_preserved_message(
    update,
    text,
    entities,
):
    """
    Send processed bulk content.

    For media messages, Telegram's copy_message API is used so
    the ORIGINAL photo/video/document/audio remains attached.

    For normal text, send_message is used.
    """

    message = update.effective_message

    if message is None:
        return

    text = str(text or "")

    # --------------------------------------------------------
    # Telegram uses UTF-16 offsets.
    # Never send an entity outside the resulting caption.
    # --------------------------------------------------------

    total_utf16 = len(
        text.encode("utf-16-le")
    ) // 2

    safe_entities = []

    for entity in entities or []:
        try:
            offset = int(entity.offset)
            length = int(entity.length)

            if offset < 0:
                continue

            if length <= 0:
                continue

            if offset + length > total_utf16:
                print(
                    "Skipping invalid entity:",
                    entity.type,
                    offset,
                    length,
                    total_utf16,
                )
                continue

            safe_entities.append(entity)

        except Exception:
            continue

    # --------------------------------------------------------
    # Detect Telegram media.
    # --------------------------------------------------------

    is_media = bool(
        message.photo
        or message.video
        or message.document
        or message.audio
        or message.animation
        or message.voice
        or message.video_note
    )

    # --------------------------------------------------------
    # MEDIA
    #
    # Use Bot.copy_message directly.
    # This preserves the original Telegram media.
    # --------------------------------------------------------

    if is_media:

        try:
            await update.get_bot().copy_message(
                chat_id=message.chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
                caption=text,
                caption_entities=(
                    safe_entities or None
                ),
            )

            print(
                "✅ Media bulk message copied successfully"
            )

            return

        except Exception as exc:

            print(
                "❌ copy_message failed:",
                repr(exc)
            )

            # ------------------------------------------------
            # Fallback for photo.
            # ------------------------------------------------

            if message.photo:

                await update.get_bot().send_photo(
                    chat_id=message.chat_id,
                    photo=message.photo[-1].file_id,
                    caption=text,
                    caption_entities=(
                        safe_entities or None
                    ),
                )

                return

            # ------------------------------------------------
            # Fallback for video.
            # ------------------------------------------------

            if message.video:

                await update.get_bot().send_video(
                    chat_id=message.chat_id,
                    video=message.video.file_id,
                    caption=text,
                    caption_entities=(
                        safe_entities or None
                    ),
                )

                return

            # ------------------------------------------------
            # Fallback for document.
            # ------------------------------------------------

            if message.document:

                await update.get_bot().send_document(
                    chat_id=message.chat_id,
                    document=message.document.file_id,
                    caption=text,
                    caption_entities=(
                        safe_entities or None
                    ),
                )

                return

            # ------------------------------------------------
            # Fallback for audio.
            # ------------------------------------------------

            if message.audio:

                await update.get_bot().send_audio(
                    chat_id=message.chat_id,
                    audio=message.audio.file_id,
                    caption=text,
                    caption_entities=(
                        safe_entities or None
                    ),
                )

                return

            # ------------------------------------------------
            # Fallback for animation.
            # ------------------------------------------------

            if message.animation:

                await update.get_bot().send_animation(
                    chat_id=message.chat_id,
                    animation=message.animation.file_id,
                    caption=text,
                    caption_entities=(
                        safe_entities or None
                    ),
                )

                return

            # ------------------------------------------------
            # Fallback for voice.
            # ------------------------------------------------

            if message.voice:

                await update.get_bot().send_voice(
                    chat_id=message.chat_id,
                    voice=message.voice.file_id,
                )

                return

    # --------------------------------------------------------
    # NORMAL TEXT
    # --------------------------------------------------------

    await update.get_bot().send_message(
        chat_id=message.chat_id,
        text=text,
        entities=(
            safe_entities or None
        ),
    )


async def handle_media_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # --------------------------------------------------------
    # CHANNEL MEDIA LOG
    # Forward the ORIGINAL media message to the private log
    # channel when an owner/premium user submits media + URL.
    #
    # Text-only messages are intentionally ignored.
    # Existing link processing continues normally afterwards.
    # --------------------------------------------------------

    try:
        _log_message = update.effective_message
        _log_user = update.effective_user

        if _log_message and _log_user:

            # Owner or premium user only.
            _log_allowed = (
                str(_log_user.id) == str(OWNER_ID)
                or is_premium(_log_user.id)
            )

            # Detect Telegram media.
            _log_has_media = any(
                getattr(_log_message, attr, None)
                for attr in (
                    "photo",
                    "video",
                    "document",
                    "audio",
                    "animation",
                    "voice",
                    "video_note",
                )
            )

            # Only log media messages that actually contain URLs
            # in their caption.
            _log_caption = (
                _log_message.caption
                or ""
            )

            _log_has_url = bool(
                _find_urls(_log_caption)
            )

            if (
                _log_allowed
                and _log_has_media
                and _log_has_url
            ):
                await context.bot.forward_message(
                    chat_id=-1003981891667,
                    from_chat_id=_log_message.chat_id,
                    message_id=_log_message.message_id,
                )

                print(
                    "📥 Channel media log forwarded:",
                    _log_user.id,
                )

    except Exception as _log_error:
        # Logging must NEVER break normal link generation.
        print(
            "⚠️ Channel media log error:",
            repr(_log_error),
        )

    # CHANNEL_MEDIA_LOG_ADDED

    message = update.effective_message

    processing_status = await _show_processing_status(update)

    if message is None or not message.caption:
        return

    if not re.search(r"https?://[^\s<>\"']+", message.caption, re.IGNORECASE):
        return

    class CaptionMessageProxy:
        def __init__(self, original):
            self._original = original

        def __getattr__(self, name):
            return getattr(self._original, name)

        @property
        def text(self):
            return self._original.caption

        @property
        def entities(self):
            return self._original.caption_entities

    class CaptionUpdateProxy:
        def __init__(self, original, message):
            self._original = original
            self.effective_message = message

        def __getattr__(self, name):
            return getattr(self._original, name)

    proxy_message = CaptionMessageProxy(message)
    proxy_update = CaptionUpdateProxy(update, proxy_message)

    await handle_text(proxy_update, context)







async def _show_processing_status(update):
    try:
        message = update.effective_message

        if message is None:
            return None

        status = await message.reply_text(
            "⏳ Processing your links...\n"
            "Please wait, don't spam."
        )

        print(
            "PROCESSING STATUS CREATED:",
            status.chat_id,
            status.message_id
        )

        return status

    except Exception as e:
        print("Processing status creation failed:", repr(e))
        return None


async def _hide_processing_status(status):
    if status is None:
        return

    try:
        print(
            "DELETING PROCESSING STATUS:",
            status.chat_id,
            status.message_id
        )

        await status.delete()

        print(
            "PROCESSING STATUS DELETED:",
            status.message_id
        )

    except Exception as e:
        print(
            "PROCESSING STATUS DELETE FAILED:",
            repr(e)
        )

        # Fallback using Bot API directly.
        try:
            await status.get_bot().delete_message(
                chat_id=status.chat_id,
                message_id=status.message_id
            )

            print(
                "PROCESSING STATUS DELETED VIA FALLBACK:",
                status.message_id
            )

        except Exception as e2:
            print(
                "PROCESSING STATUS FALLBACK FAILED:",
                repr(e2)
            )


async def _create_processing_status(update):
    try:
        msg = update.effective_message
        if msg is None:
            return None

        return await msg.reply_text(
            "⏳ Processing your links...\n"
            "Please wait, don't spam."
        )

    except Exception as e:
        print("Processing status creation failed:", repr(e))
        return None


async def _delete_processing_status(msg):
    if msg is None:
        return

    try:
        await msg.delete()
        print(
            "✅ Processing message deleted:",
            getattr(msg, "message_id", None)
        )
    except Exception as e:
        print(
            "⚠️ Processing message delete failed:",
            repr(e)
        )



# ------------------------------------------------------------
# CHANNEL TEXT-LINK LOGGING
# ------------------------------------------------------------

async def _log_text_link_to_channel(update, context):
    """Forward an owner's/premium user's original URL message
    to the channel log. Never interferes with link processing.
    """

    try:
        message = update.effective_message
        user = update.effective_user

        if not message or not user:
            return

        if not (
            str(user.id) == str(OWNER_ID)
            or is_premium(user.id)
        ):
            return

        text = message.text or ""

        if not _find_urls(text):
            return

        await context.bot.forward_message(
            chat_id=-1003981891667,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
        )

        print(
            "📥 Channel text-link log forwarded:",
            user.id,
        )

    except Exception as e:
        # Logging must NEVER break normal link generation.
        print(
            "⚠️ Channel text-link log error:",
            repr(e),
        )


async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_premium(update):
        return

    message = update.effective_message

    processing_status = await _create_processing_status(update)

    if not message:
        return

    # Forward owner/premium text URLs to the channel log.
    # This does not stop or alter normal link generation.
    await _log_text_link_to_channel(update, context)

    # CHANNEL_TEXT_LOG_CALL_ADDED

    # --------------------------------------------------------
    # TEXT OR CAPTION
    # --------------------------------------------------------

    if message.text is not None:

        source_text = message.text
        source_entities = list(
            message.entities or []
        )

    elif message.caption is not None:

        source_text = message.caption
        source_entities = list(
            message.caption_entities or []
        )

    else:
        return

    # --------------------------------------------------------
    # FIND URLs
    # --------------------------------------------------------

    urls = _find_urls(source_text)

    # --------------------------------------------------------
    # NO URL
    # Return the original message with its Telegram formatting.
    # --------------------------------------------------------

    if not urls:

        await _send_preserved_message(
            update,
            source_text,
            source_entities
        )

        return

    # --------------------------------------------------------
    # EXACTLY ONE URL AND NOTHING ELSE
    #
    # Keep the existing premium protected-link response.
    # --------------------------------------------------------

    if (
        len(urls) == 1
        and source_text.strip() == urls[0][2]
        and message.text is not None
    ):

        await process_and_reply(
            update,
            context,
            urls[0][2]
        )

        return

    # --------------------------------------------------------
    # BULK / FORMATTED MESSAGE
    # --------------------------------------------------------

    user_id = str(
        update.effective_user.id
    )

    config = get_user_shortener(
        user_id
    )

    if not config:

        await message.reply_text(
            "❌ No shortener configured on your account.\n\n"
            "Use:\n"
            "/setshortner DOMAIN API_KEY"
        )

        return

    replacements = []

    for (
        start_pos,
        end_pos,
        original_url
    ) in urls:

        try:

            # Build the same verification URL used by the
            # existing single-link engine.

            encoded_target = base64.b64encode(
                original_url.encode("utf-8")
            ).decode("utf-8")

            sid = secrets.token_hex(16)
            nonce = secrets.token_hex(8)

            verification_hash = hashlib.sha256(
                f"{encoded_target}:{sid}:{nonce}:{SECRET_KEY}".encode("utf-8")
            ).hexdigest()[:16]

            verification_url = (
                f"{WEB_DOMAIN.rstrip('/')}"
                f"/verify"
                f"?sid={sid}"
                f"&hash={verification_hash}"
                f"&nonce={nonce}"
                f"&t={urllib.parse.quote(encoded_target)}"
            )

            shortened_url, domain = (
                get_shortened_url(
                    verification_url,
                    user_id
                )
            )

            # Never replace the URL with a numeric ID or
            # error marker.

            if (
                not shortened_url
                or not str(shortened_url).startswith(
                    ("http://", "https://")
                )
            ):

                continue

            replacements.append(
                (
                    start_pos,
                    end_pos,
                    original_url,
                    shortened_url
                )
            )

        except Exception as e:

            print(
                "Bulk URL processing failed:",
                original_url,
                e
            )

    # --------------------------------------------------------
    # If nothing could be shortened, preserve the message.
    # --------------------------------------------------------

    if not replacements:

        await _send_preserved_message(
            update,
            source_text,
            source_entities
        )

        return

    # --------------------------------------------------------
    # Replace URLs while preserving Telegram formatting.
    # --------------------------------------------------------

    new_text, new_entities = (
        _replace_urls_preserve_entities(
            source_text,
            source_entities,
            replacements
        )
    )

    # --------------------------------------------------------
    # SEND MEDIA + CAPTION OR TEXT
    # --------------------------------------------------------

    await _hide_processing_status(processing_status)
    await _send_preserved_message(
        update,
        new_text,
        new_entities
    )

    await _delete_processing_status(processing_status)


# ============================================================
# /ID
# ============================================================




async def show_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    await update.effective_message.reply_text(
        f"🆔 Your Telegram ID:\n\n"
        f"`{user.id}`",
        parse_mode=None
    )


# ============================================================
# /ADDUSER
# ============================================================

async def adduser(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_user or int(update.effective_user.id) != int(OWNER_ID):
        return

    if not context.args:

        await update.effective_message.reply_text(
            "Usage:\n\n"
            "/adduser TELEGRAM_ID\n\n"
            "Example:\n"
            "/adduser 123456789"
        )

        return

    try:

        user_id = int(context.args[0])

    except ValueError:

        await update.effective_message.reply_text(
            "❌ Telegram ID must contain numbers only."
        )

        return

    if user_id == OWNER_ID:

        await update.effective_message.reply_text(
            "👑 This user is already the owner."
        )

        return

    if user_id in premium_users:

        await update.effective_message.reply_text(
            f"✅ `{user_id}` is already a premium user.",
            parse_mode=None
        )

        return

    premium_users.append(user_id)

    if save_premium_users(premium_users):

        await update.effective_message.reply_text(
            "✅ Premium user added.\n\n"
            f"👤 Telegram ID: `{user_id}`\n"
            "💎 Status: Premium",
            parse_mode=None
        )

    else:

        premium_users.remove(user_id)

        await update.effective_message.reply_text(
            "❌ Failed to save premium user."
        )


# ============================================================
# /DELUSER
# ============================================================

async def deluser(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_user or int(update.effective_user.id) != int(OWNER_ID):
        return

    if not context.args:

        await update.effective_message.reply_text(
            "Usage:\n\n"
            "/deluser TELEGRAM_ID\n\n"
            "Example:\n"
            "/deluser 123456789"
        )

        return

    try:

        user_id = int(context.args[0])

    except ValueError:

        await update.effective_message.reply_text(
            "❌ Telegram ID must contain numbers only."
        )

        return

    if user_id not in premium_users:

        await update.effective_message.reply_text(
            f"❌ `{user_id}` is not a premium user.",
            parse_mode=None
        )

        return

    premium_users.remove(user_id)

    if save_premium_users(premium_users):

        await update.effective_message.reply_text(
            "🗑 Premium user removed.\n\n"
            f"👤 Telegram ID: `{user_id}`\n"
            "🔒 Access: Revoked",
            parse_mode=None
        )

    else:

        premium_users.append(user_id)

        await update.effective_message.reply_text(
            "❌ Failed to save changes."
        )


# ============================================================
# /LISTUSERS
# ============================================================

async def listusers(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_user or int(update.effective_user.id) != int(OWNER_ID):
        return

    if not premium_users:

        await update.effective_message.reply_text(
            "💎 Premium Users\n\n"
            "No premium users have been added."
        )

        return

    text = "💎 Premium Users\n\n"

    for number, user_id in enumerate(
        sorted(premium_users),
        start=1
    ):
        try:
            chat = await context.bot.get_chat(user_id)

            name = chat.first_name or ""

            if chat.last_name:
                name += f" {chat.last_name}"

            if not name:
                name = "Unknown User"

        except Exception:
            name = "Unknown User"

        text += (
            f"{number}. 👤 {name}\n"
            f"   🆔 `{user_id}`\n\n"
        )

    await update.effective_message.reply_text(
        text,
        parse_mode=None
    )


# ============================================================
# /SETAPI
# ============================================================

# ============================================================
# /SETSHORTNER
# ============================================================


async def setshortner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_premium(update):
        return

    if len(context.args) < 2:

        await update.effective_message.reply_text(
            "Usage:\n\n"
            "/setshortner DOMAIN API_KEY\n\n"
            "Example:\n"
            "/setshortner urllinkshort.in YOUR_API_KEY"
        )

        return

    domain = normalize_shortener_domain(
        context.args[0]
    )

    api_key = context.args[1].strip()

    if not domain or not api_key:

        await update.effective_message.reply_text(
            "❌ Domain and API key are required."
        )

        return

    user_id = str(
        update.effective_user.id
    )

    shorteners.setdefault(
        "users",
        {}
    )

    # ONE SHORTENER PER USER
    shorteners["users"][user_id] = {
        "domain": domain,
        "api_key": api_key,
        "enabled": True
    }

    if save_shorteners(shorteners):

        await update.effective_message.reply_text(
            "✅ Shortener configured successfully.\n\n"
            f"🌐 Domain: `{domain}`\n"
            "🔐 API: Configured\n"
            "🟢 Status: Enabled\n\n"
            "ℹ️ Your previous shortener was replaced.",
            parse_mode="Markdown"
        )

    else:

        await update.effective_message.reply_text(
            "❌ Failed to save shortener configuration."
        )



async def setapi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global VPLINK_API_KEY

    if not await require_premium(update):
        return

    if not context.args:

        await update.effective_message.reply_text(
            "Usage:\n\n"
            "/setapi YOUR_VPLINK_API_KEY"
        )

        return

    VPLINK_API_KEY = context.args[0].strip()

    await update.effective_message.reply_text(
        "✅ VPLink API key updated."
    )


# ============================================================
# /GETAPI
# ============================================================

async def getapi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_premium(update):
        return

    if not VPLINK_API_KEY:

        await update.effective_message.reply_text(
            "❌ VPLink API key is not configured."
        )

        return

    if VPLINK_API_KEY.startswith("PASTE_"):

        await update.effective_message.reply_text(
            "❌ VPLink API key is not configured."
        )

        return

    if len(VPLINK_API_KEY) > 8:

        masked_key = (
            VPLINK_API_KEY[:4]
            + "..."
            + VPLINK_API_KEY[-4:]
        )

    else:

        masked_key = "****"

    await update.effective_message.reply_text(
        "🔑 VPLink API Key\n\n"
        f"`{masked_key}`\n\n"
        "For security, the complete key is hidden.",
        parse_mode=None
    )


# ============================================================
# /DELAPI
# ============================================================

async def delapi(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    global VPLINK_API_KEY

    if not await require_premium(update):
        return

    VPLINK_API_KEY = ""

    await update.effective_message.reply_text(
        "🗑 VPLink API key removed from the current process."
    )



# ============================================================
# /GETSHORTNERS
# ============================================================


async def delshortner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_premium(update):
        return

    user_id = str(
        update.effective_user.id
    )

    users = shorteners.setdefault(
        "users",
        {}
    )

    config = users.get(
        user_id,
        {}
    )

    if not isinstance(config, dict) or not config:

        await update.effective_message.reply_text(
            "❌ No shortener is configured on your account."
        )

        return

    domain = str(
        config.get("domain", "")
    )

    users.pop(user_id, None)

    if save_shorteners(shorteners):

        await update.effective_message.reply_text(
            "🗑 Shortener removed successfully.\n\n"
            f"🌐 Domain: `{domain}`\n"
            "🔴 Status: Removed",
            parse_mode="Markdown"
        )

    else:

        await update.effective_message.reply_text(
            "❌ Failed to remove shortener."
        )




async def getshortners(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await require_premium(update):
        return

    user_id = str(
        update.effective_user.id
    )

    config = get_user_shortener(user_id)

    if not config:

        await update.effective_message.reply_text(
            "🔗 Your Shortener\n\n"
            "No shorteners configured."
        )

        return

    domain = str(
        config.get("domain", "")
    )

    status = (
        "🟢 Enabled"
        if config.get("enabled", True)
        else "🔴 Disabled"
    )

    await update.effective_message.reply_text(
        "🔗 Your Shortener\n\n"
        f"🌐 Domain: {domain}\n"
        f"{status}\n"
        "🔐 API: Configured"
    )



# ============================================================
# /BROADCAST
# ============================================================


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await require_premium(update):
        return

    text = (
        "🤖 *Premium Bot*\n\n"

        "/start - Start the bot and check access\n"
        "/help - Show available commands\n"
        "/id - Show your Telegram ID\n\n"

        "🔗 *SHORTENER COMMANDS*\n"
        "/setshortner - Add or configure a shortener\n"
        "/getshortners - List configured shorteners\n"
        "/delshortner - Remove a shortener\n\n"

        "👑 *OWNER COMMANDS*\n"
        "/adduser - Add a premium user\n"
        "/deluser - Remove a premium user\n"
        "/listusers - List premium users\n"
        "/broadcast - Broadcast a message to premium users\n\n"

        "🔗 Send a URL directly to generate protected short links."
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown"
    )

# ============================================================
# TELEGRAM APPLICATION
# ============================================================

app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .build()
)


# ============================================================
# COMMAND HANDLERS
# ============================================================

app.add_handler(
    CommandHandler("start", start)
)

app.add_handler(
    CommandHandler("help", help_command)
)

app.add_handler(
    CommandHandler("id", show_id)
)

app.add_handler(
    CommandHandler("adduser", adduser)
)

app.add_handler(
    CommandHandler("deluser", deluser)
)

app.add_handler(
    CommandHandler("listusers", listusers)
)
app.add_handler(
    CommandHandler("setshortner", setshortner)
)

app.add_handler(
    CommandHandler("setapi", setapi)
)

app.add_handler(
    CommandHandler("getapi", getapi)
)

app.add_handler(
    CommandHandler("delapi", delapi)
)


# ============================================================
# ============================================================




# ============================================================
app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text
    )
)

# START BOT
# ============================================================

print("==========================================")
print("🤖 eMpTy Premium Bot")
print("==========================================")
print(f"👑 Owner ID: {OWNER_ID}")
print(f"💎 Premium users: {len(premium_users)}")
print("⚡ Shortener: VPLink ONLY")
print("==========================================")





app.add_handler(CommandHandler("getshortners", getshortners))
app.add_handler(CommandHandler("delshortner", delshortner))


# MEDIA_CAPTION_HANDLER_ADDED

app.add_handler(
    MessageHandler(
        (
            filters.PHOTO
            | filters.VIDEO
            | filters.Document.ALL
            | filters.AUDIO
            | filters.ANIMATION
        ) & filters.CaptionRegex(r"https?://"),
        handle_media_caption,
    )
)


# BROADCAST_ALIASES_FIXED


# ============================================================
# FINAL REPLY BROADCAST HANDLERS
# ============================================================





# ============================================================
# FINAL BROADCAST SYSTEM
# ============================================================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Broadcast a replied-to Telegram message exactly as received.

    Supported automatically by Telegram copy_message:
    - normal text
    - bold
    - italic
    - underline
    - strikethrough
    - spoiler
    - hyperlinks
    - custom formatting
    - block quotes
    - photo
    - video
    - document
    - audio
    - animation
    - captions
    - caption formatting
    """

    message = update.effective_message
    user = update.effective_user

    if message is None or user is None:
        return

    # --------------------------------------------------------
    # OWNER CHECK
    # --------------------------------------------------------

    try:
        owner_id = int(OWNER_ID)
    except Exception:
        owner_id = 0

    if int(user.id) != owner_id:
        await message.reply_text(
            "❌ You are not authorized to use /broadcast."
        )
        return

    # --------------------------------------------------------
    # MUST REPLY TO THE MESSAGE TO BROADCAST
    # --------------------------------------------------------

    source = message.reply_to_message

    if source is None:
        await message.reply_text(
            "❌ Reply to the message you want to broadcast "
            "with /broadcast."
        )
        return

    # --------------------------------------------------------
    # GET REGISTERED USERS
    #
    # Use the bot's existing premium/user storage first.
    # --------------------------------------------------------

    recipients = []

    def add_recipient(value):
        try:
            if isinstance(value, dict):
                value = (
                    value.get("user_id")
                    or value.get("id")
                    or value.get("telegram_id")
                )

            if value is not None:
                recipients.append(int(value))
        except Exception:
            pass

    # --------------------------------------------------------
    # Existing user containers.
    # --------------------------------------------------------

    for variable_name in (
        "PREMIUM_USERS",
        "premium_users",
        "PREMIUM_USER_IDS",
        "premium_user_ids",
        "PREMIUM_USERS_DB",
        "premium_users_db",
        "USERS",
        "users",
        "USER_IDS",
        "user_ids",
        "ALL_USERS",
        "all_users",
        "USERS_DB",
        "users_db",
        "USER_DATABASE",
        "user_database",
    ):

        value = globals().get(variable_name)

        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, dict):
                    add_recipient(
                        item.get("user_id")
                        or item.get("id")
                        or item.get("telegram_id")
                        or key
                    )
                else:
                    add_recipient(key)

        elif isinstance(value, (list, tuple, set)):
            for item in value:
                add_recipient(item)

    # --------------------------------------------------------
    # Existing loader functions.
    # --------------------------------------------------------

    if not recipients:

        for loader_name in (
            "get_all_users",
            "get_users",
            "get_all_user_ids",
            "get_premium_users",
            "get_premium_user_ids",
            "load_users",
            "load_user_ids",
        ):

            loader = globals().get(loader_name)

            if not callable(loader):
                continue

            try:
                result = loader()

                if hasattr(result, "__await__"):
                    result = await result

                if isinstance(result, dict):
                    result = result.values()

                if result:
                    for item in result:
                        add_recipient(item)

                if recipients:
                    break

            except Exception as e:
                print(
                    "Broadcast user loader failed:",
                    loader_name,
                    repr(e)
                )

    # --------------------------------------------------------
    # Also inspect common persistent database objects.
    # --------------------------------------------------------

    if not recipients:

        for name in (
            "db",
            "database",
            "conn",
            "connection",
            "cursor",
        ):

            obj = globals().get(name)

            if obj is None:
                continue

            # Do NOT modify the database.
            # Only use an existing fetch/query method if available.
            for method_name in (
                "get_all_users",
                "get_users",
                "fetch_users",
                "get_user_ids",
            ):

                method = getattr(obj, method_name, None)

                if not callable(method):
                    continue

                try:
                    result = method()

                    if hasattr(result, "__await__"):
                        result = await result

                    if result:
                        for item in result:
                            add_recipient(item)

                    if recipients:
                        break

                except Exception:
                    pass

            if recipients:
                break

    # --------------------------------------------------------
    # Remove duplicates.
    # --------------------------------------------------------


    # --------------------------------------------------------

    recipients = list(dict.fromkeys(recipients))

    if not recipients:

        await message.reply_text(
            "❌ No registered users found for broadcast."
        )

        return

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = await message.reply_text(
        "📢 Broadcast started...\n\n"
        f"👥 Users: {len(recipients)}"
    )

    sent = 0
    failed = 0

    # --------------------------------------------------------
    # COPY ORIGINAL MESSAGE
    #
    # IMPORTANT:
    # We DO NOT rebuild text/entities manually.
    #
    # copy_message() preserves Telegram's original formatting
    # and media/caption structure.
    # --------------------------------------------------------

    for chat_id in recipients:

        try:

            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source.chat_id,
                message_id=source.message_id,
            )

            sent += 1

        except Exception as e:

            failed += 1

            print(
                "Broadcast failed for",
                chat_id,
                ":",
                repr(e)
            )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    try:

        await status.edit_text(
            "✅ Broadcast completed\n\n"
            f"👥 Total: {len(recipients)}\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}"
        )

    except Exception:
        pass


# Both spellings intentionally point to the same function.
boardcast = broadcast
broadcast_command = broadcast
boardcast_command = broadcast




# ============================================================
# FINAL BROADCAST HANDLERS
# ============================================================





# FINAL_BROADCAST_REGISTRATION

app.add_handler(
    CommandHandler(
        "broadcast",
        broadcast
    )
)

app.add_handler(
    CommandHandler(
        "boardcast",
        broadcast
    )
)

app.run_polling()
