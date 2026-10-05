import asyncio
import hashlib
import json
import os
import re
import time

from pyrogram import Client
from pyrogram.errors import FloodWait

# ─── همه‌ی تنظیمات از Secrets می‌آیند ───
API_ID         = int(os.environ["API_ID"])
API_HASH       = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
SOURCE         = os.environ["SOURCE"]
DESTS          = [d.strip() for d in os.environ.get("DESTS", "").split(",") if d.strip()]
TAG_TEXT       = os.environ.get("TAG_TEXT") or "tel:@star_shop_vpn"
HEADER         = os.environ.get("HEADER")  or "🔥 NEW SERVER\n\n⚡ Ultra Ping\n🚀 Fresh Config Pack"
QUOTE          = os.environ.get("QUOTE")   or "اینترنت آزاد حق مردم است ✌️\n\nفرزند ایران و جان‌فدای میهن 🖤❤️‍🩹"
CHANNEL        = os.environ.get("CHANNEL") or "📡 @star_shop_vpn"

PACK_SIZE    = int(os.environ.get("PACK_SIZE", "3"))
PACK_EVERY   = int(os.environ.get("PACK_EVERY", "600"))   # ⏱ ۶۰۰ ثانیه = هر ۱۰ دقیقه یک پک
MAX_MINUTES  = int(os.environ.get("MAX_MINUTES", "50"))
INITIAL_SCAN = int(os.environ.get("INITIAL_SCAN", "0"))
REPORT       = os.environ.get("REPORT", "1") == "1"       # تیکت گزارش به Saved Messages

POOL_CAP   = 5000
STATE_FILE = "state.json"

SEP = "━━━━━━━━━━━━━━━━━━"

def e(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def fix_tag(cfg):
    m = re.search(r"#\S+$", cfg)
    if not m:
        return cfg
    fm = re.match(r"#\[([^\]]*)\]", m.group(0))
    flag = fm.group(1) if fm else ""
    return cfg[:m.start()] + (f"#[{flag}]{TAG_TEXT}" if flag else f"#{TAG_TEXT}")

def get_flag(cfg):
    m = re.search(r"#\[([^\]]+)\]", cfg)
    return m.group(1) if m else "🌐"

def extract(text):
    out = []
    if not text:
        return out
    for raw in re.findall(r"(?:vless|trojan)://\S+", text, re.IGNORECASE):
        cfg = fix_tag(raw.strip())
        out.append({"key": hashlib.md5(cfg.encode()).hexdigest(), "text": cfg,
                    "flag": get_flag(cfg), "type": raw.split("://")[0].upper()})
    return out

S = {"pack_no": 0, "seen": [], "pool": [], "last_msg_id": 0,
     "daily": {}, "countries": {},
     "stats": {"total_packs": 0, "total_configs": 0, "VLESS": 0, "TROJAN": 0}}

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            j = json.load(f)
        for k in S:
            if k in j:
                S[k] = {**S[k], **j[k]} if isinstance(S[k], dict) else j[k]
    except FileNotFoundError:
        pass

def save():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False)

def build_pack(batch, number):
    p = [HEADER, ""]
    for i, c in enumerate(batch, 1):
        p += [f"🇻🇵 Server {i} {e(c['flag'])}", "", f"<code>{e(c['text'])}</code>", "", SEP, ""]
    types = " / ".join(dict.fromkeys(c["type"] for c in batch))
    flags = [f for f in dict.fromkeys(c["flag"] for c in batch) if f != "🌐"] or ["🌐"]
    p += [f"✦ Type: {types}", "✦ Speed: Boost Server", "✦ Country: " + " / ".join(flags),
          "", SEP, "", f"<blockquote>{e(QUOTE)}</blockquote>", "",
          e(CHANNEL), "", f"🆔 Config Pack #{number}"]
    return "\n".join(p)

async def gather(c):
    added = 0
    pool_keys = {p["key"] for p in S["pool"]}

    if not S["last_msg_id"]:
        newest = None
        async for m in c.get_chat_history(SOURCE, limit=1):
            newest = m
        if newest is None:
            print("⚠️ چنل مبدا خالی یا در دسترس نیست")
            return 0
        S["last_msg_id"] = newest.id
        print(f"📍 خط پایه ثبت شد: پیام {newest.id} — از این به بعد فقط پیام‌های جدید جمع می‌شود")
        if INITIAL_SCAN > 0:
            print(f"📥 اسکن {INITIAL_SCAN} پیام آخر ...")
            async for m in c.get_chat_history(SOURCE, limit=INITIAL_SCAN):
                for item in extract(m.text or m.caption):
                    if item["key"] in S["seen"] or item["key"] in pool_keys or len(S["pool"]) >= POOL_CAP:
                        continue
                    S["pool"].append(item)
                    pool_keys.add(item["key"])
                    added += 1
        save()
        return added

    fresh = []
    async for m in c.get_chat_history(SOURCE, limit=2000):
        if m.id <= S["last_msg_id"]:
            break
        fresh.append(m)
    if not fresh:
        print("📭 پیام جدیدی از اجرای قبل نبود")
        return 0

    S["last_msg_id"] = fresh[0].id
    for m in reversed(fresh):
        for item in extract(m.text or m.caption):
            if item["key"] in S["seen"] or item["key"] in pool_keys or len(S["pool"]) >= POOL_CAP:
                continue
            S["pool"].append(item)
            pool_keys.add(item["key"])
            added += 1
    save()
    return added

async def send(c):
    t0 = time.time()
    sent, packs = 0, 0
    while time.time() - t0 < MAX_MINUTES * 60 and len(S["pool"]) >= PACK_SIZE:
        batch = S["pool"][:PACK_SIZE]
        del S["pool"][:PACK_SIZE]
        text = build_pack(batch, S["pack_no"])

        any_ok = False
        for d in DESTS:
            for attempt in (1, 2):
                try:
                    await c.send_message(d, text, disable_web_page_preview=True)
                    any_ok = True
                    break
                except FloodWait as fw:
                    print(f"⏳ FloodWait {fw.value}s ...")
                    await asyncio.sleep(min(fw.value, 300) + 2)
                except Exception as ex:
                    print(f"❌ ارسال به {d}: {ex}")
        if not any_ok:
            print("⚠️ هیچ مقصدی جواب نداد — کانفیگ‌ها برگشتند به مخزن")
            S["pool"][0:0] = batch
            save()
            return sent, packs

        for it in batch:
            S["seen"].append(it["key"])
            S["countries"][it["flag"]] = S["countries"].get(it["flag"], 0) + 1
        if len(S["seen"]) > 20000:
            S["seen"] = S["seen"][-15000:]
        S["pack_no"] += 1
        st = S["stats"]
        st["total_packs"] += 1
        st["total_configs"] += PACK_SIZE
        for it in batch:
            st[it["type"]] = st.get(it["type"], 0) + 1
        day = time.strftime("%Y-%m-%d")
        S["daily"].setdefault(day, {"packs": 0, "configs": 0})
        S["daily"][day]["packs"] += 1
        S["daily"][day]["configs"] += PACK_SIZE
        sent += PACK_SIZE
        packs += 1
        save()
        print(f"✅ Config Pack #{S['pack_no']-1} ارسال شد ({sent} کانفیگ در این اجرا)")

        if len(S["pool"]) >= PACK_SIZE and time.time() - t0 < MAX_MINUTES * 60:
            print(f"⏱ {PACK_EVERY // 60} دقیقه صبر تا پک بعدی ...")
            await asyncio.sleep(PACK_EVERY)
    return sent, packs

async def main():
    load_state()
    print(f"▶️ شروع | پک بعدی: #{S['pack_no']} | مخزن: {len(S['pool'])} کانفیگ")
    async with Client("gh", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING) as c:
        me = await c.get_me()
        print(f"👤 اکانت: {me.first_name} ({me.id})")
        n = await gather(c)
        print(f"📥 {n} کانفیگ جدید جمع شد | مخزن: {len(S['pool'])}")
        if len(S["pool"]) >= PACK_SIZE:
            sent, packs = await send(c)
            print(f"🏁 تمام: {packs} پک / {sent} کانفیگ ارسال شد | باقی‌مانده: {len(S['pool'])}")
            if REPORT:
                day = time.strftime("%Y-%m-%d")
                txt = (f"📊 <b>گزارش اجرا</b>\n\n"
                       f"⏰ {time.strftime('%H:%M')}\n"
                       f"🆕 جمع‌آوری: {n} کانفیگ جدید\n"
                       f"📤 ارسال: {packs} پک / {sent} کانفیگ\n"
                       f"📦 پک بعدی: #{S['pack_no']}\n"
                       f"💾 باقی‌مانده در مخزن: {len(S['pool'])}\n"
                       f"🧮 کل: {S['stats']['total_packs']} پک / {S['stats']['total_configs']} کانفیگ\n"
                       f"📅 امروز: {S['daily'].get(day, {}).get('packs', 0)} پک")
                try:
                    await c.send_message("me", txt, parse_mode="html")
                except Exception as ex:
                    print("⚠️ گزارش: " + str(ex)[:80])
        else:
            print("😴 مخزن هنوز به اندازه یک پک پر نیست — برای دفعه بعد ذخیره شد")

asyncio.run(main())
