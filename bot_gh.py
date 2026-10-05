import asyncio, base64, hashlib, json, os, random, re, time
import aiohttp
from pyrogram import Client
from pyrogram.errors import FloodWait

API_ID   = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
SOURCE   = os.environ.get("SOURCE", "").strip()
DESTS    = [d.strip() for d in os.environ.get("DESTS", "").split(",") if d.strip()]
TAG_TEXT = os.environ.get("TAG_TEXT") or "tel:@star_shop_vpn"
HEADER   = os.environ.get("HEADER")  or "🔥 NEW SERVER\n\n⚡ Ultra Ping\n🚀 Fresh Config Pack"
QUOTE    = os.environ.get("QUOTE")   or "اینترنت آزاد حق مردم است ✌️\n\nفرزند ایران و جان‌فدای میهن 🖤❤️‍🩹"
CHANNEL  = os.environ.get("CHANNEL") or "📡 @star_shop_vpn"

GH_REPO   = os.environ.get("GH_REPO")   or "Argh94/V2RayAutoConfig"
GH_BRANCH = os.environ.get("GH_BRANCH") or "main"
GH_FOLDER = os.environ.get("GH_FOLDER") or "configs"
GH_TAIL   = int(os.environ.get("GH_TAIL", "40"))
GH_FILES  = int(os.environ.get("GH_FILES", "40"))
TEST_ON      = os.environ.get("TEST_ENABLED", "1") == "1"
TEST_TIMEOUT = float(os.environ.get("TEST_TIMEOUT", "3"))
TEST_CONC    = int(os.environ.get("TEST_CONC", "40"))
TEST_BUDGET  = int(os.environ.get("TEST_BUDGET", "45"))
TEST_LIMIT   = int(os.environ.get("TEST_LIMIT", "300"))

PACK_SIZE   = int(os.environ.get("PACK_SIZE", "3"))
PACK_EVERY  = int(os.environ.get("PACK_EVERY", "600"))
MAX_MINUTES = int(os.environ.get("MAX_MINUTES", "50"))
REPORT = os.environ.get("REPORT", "1") == "1"

HOURLY_CAPACITY = (MAX_MINUTES * 60) // PACK_EVERY * PACK_SIZE if PACK_EVERY else MAX_MINUTES
POOL_CAP, STATE_FILE = 5000, "state.json"
SEP = "━━━━━━━━━━━━━━━━━━"
PROTO_RE = re.compile(r"(?:ss|vless|trojan|vmess|hysteria2?|hy2|tuic|ssr)://[^\s\"']+)", re.I)

_ISO = {"afghanistan":"AF","albania":"AL","algeria":"DZ","argentina":"AR","armenia":"AM",
"australia":"AU","austria":"AT","azerbaijan":"AZ","bahrain":"BH","bangladesh":"BD",
"belarus":"BY","belgium":"BE","belize":"BZ","bolivia":"BO","bosniaandherzegovina":"BA",
"botswana":"BW","brazil":"BR","brunei":"BN","bulgaria":"BG","cambodia":"KH",
"cameroon":"CM","canada":"CA","chile":"CL","china":"CN","colombia":"CO",
"costarica":"CR","croatia":"HR","cuba":"CU","cyprus":"CY","czech":"CZ","czechia":"CZ",
"denmark":"DK","ecuador":"EC","egypt":"EG","estonia":"EE","finland":"FI","france":"FR",
"georgia":"GE","germany":"DE","ghana":"GH","greece":"GR","hongkong":"HK","hungary":"HU",
"iceland":"IS","india":"IN","indonesia":"ID","iran":"IR","iraq":"IQ","ireland":"IE",
"israel":"IL","italy":"IT","japan":"JP","jordan":"JO","kazakhstan":"KZ","kenya":"KE",
"kuwait":"KW","kyrgyzstan":"KG","laos":"LA","latvia":"LV","lebanon":"LB","lithuania":"LT",
"luxembourg":"LU","macau":"MO","malaysia":"MY","maldives":"MV","malta":"MT","mexico":"MX",
"moldova":"MD","mongolia":"MN","montenegro":"ME","morocco":"MA","myanmar":"MM","nepal":"NP",
"netherlands":"NL","newzealand":"NZ","nigeria":"NG","norway":"NO","oman":"OM",
"pakistan":"PK","palestine":"PS","panama":"PA","peru":"PE","philippines":"PH",
"poland":"PL","portugal":"PT","qatar":"QA","romania":"RO","russia":"RU",
"saudiarabia":"SA","serbia":"RS","singapore":"SG","slovakia":"SK","slovenia":"SI",
"southafrica":"ZA","southkorea":"KR","spain":"ES","srilanka":"LK","sweden":"SE",
"switzerland":"CH","syria":"SY","taiwan":"TW","tajikistan":"TJ","thailand":"TH",
"tunisia":"TN","turkey":"TR","turkmenistan":"TM","uae":"AE","ukraine":"UA",
"unitedstates":"US","unitedstatesofamerica":"US","usa":"US","unitedkingdom":"GB","uk":"GB",
"uzbekistan":"UZ","venezuela":"VE","vietnam":"VN","yemen":"YE"}

def flag_of(filename):
    base = filename.rsplit(".", 1)[0].lower()
    code = _ISO.get(base)
    if not code:
        for k, v in _ISO.items():
            if k in base:
                code = v
                break
    if not code:
        return "🌐"
    return "".join(chr(ord(c) - 0x41 + 0x1F1E6) for c in code.upper())

def e(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def fix_tag(cfg, flag):
    m = re.search(r"#\S*$", cfg)
    tag = f"#[{flag}]{TAG_TEXT}"
    return cfg[:m.start()] + tag if m else cfg + tag

def proto_of(raw):
    p = raw.split("://", 1)[0].upper()
    return "HYSTERIA2" if p == "HY2" else p

def parse_endpoint(raw):
    try:
        if raw.lower().startswith("vmess://"):
            b = raw[8:].strip()
            b += "=" * (-len(b) % 4)
            j = json.loads(base64.urlsafe_b64decode(b).decode("utf-8", "ignore"))
            host, port = (j.get("add") or "").strip(), int(j.get("port") or 0)
        else:
            PROTO_RE = re.compile(r"(?:ss|vless|trojan|vmess|hysteria2?|hy2|tuic|ssr)://[^\s\"']+", re.I)
            if not m:
                return None
            host, port = m.group(1).strip("[]"), int(m.group(2))
        if host and 0 < port < 65536:
            return host, port
    except Exception:
        pass
    return None

def extract(text):
    out = []
    if not text:
        return out
    for raw in PROTO_RE.findall(text):
        raw = raw.strip().rstrip(").,;")
        ep = parse_endpoint(raw)
        if ep:
            out.append({"raw": raw, "host": ep[0], "port": ep[1]})
    return out

S = {"pack_no": 0, "seen": [], "pool": [],
     "stats": {"total_packs": 0, "total_configs": 0, "VLESS": 0, "TROJAN": 0, "SS": 0, "VMESS": 0},
     "daily": {}, "countries": {}}

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
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
        p += [f"🇻🇵 Server {i} {c['flag']}", "", f"<code>{e(c['text'])}</code>", "", SEP, ""]
    types = " / ".join(dict.fromkeys(c["type"] for c in batch))
    flags = [f for f in dict.fromkeys(c["flag"] for c in batch) if f != "🌐"] or ["🌐"]
    p += [f"✦ Type: {types}", "✦ Speed: Boost Server", "✦ Country: " + " / ".join(flags),
          "", SEP, "", f"<blockquote>{e(QUOTE)}</blockquote>", "",
          e(CHANNEL), "", f"🆔 Config Pack #{number}"]
    return "\n".join(p)

async def http_get(session, url, want_json=False):
    for attempt in (1, 2, 3):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as r:
                if r.status == 200:
                    if want_json:
                        return await r.json(content_type=None)
                    return await r.text()
                if r.status == 403:
                    print(f"⚠️ 403 (rate limit?) : {url[:60]}")
                    await asyncio.sleep(3)
                elif r.status == 404:
                    return None
        except Exception:
            pass
        await asyncio.sleep(1)
    return None

async def test_alive(candidates):
    if not TEST_ON or not candidates:
        return candidates
    random.shuffle(candidates)
    if len(candidates) > TEST_LIMIT:
        candidates = candidates[:TEST_LIMIT]
    alive, t0 = [], time.time()

    async def one(c, sem):
        if time.time() - t0 > TEST_BUDGET:
            return
        async with sem:
            try:
                w = await asyncio.wait_for(
                    asyncio.open_connection(c["host"], c["port"]), timeout=TEST_TIMEOUT)
                w.close()
                try:
                    await w.wait_closed()
                except Exception:
                    pass
                alive.append(c)
            except Exception:
                pass

    sem = asyncio.Semaphore(TEST_CONC)
    await asyncio.gather(*(one(c, sem) for c in candidates))
    print(f"🧪 تست اتصال: {len(alive)} از {len(candidates)} زنده")
    return alive

async def gather_from_github(session, need):
    if need <= 0:
        print("📁 ریپو لازم نبود — چنل کافی بود")
        return 0
    print(f"📁 ریپوی منبع: {GH_REPO}/{GH_FOLDER} (آخرین {GH_TAIL} خط هر کشور)")

    listing = await http_get(session,
        f"https://api.github.com/repos/{GH_REPO}/contents/{GH_FOLDER}?ref={GH_BRANCH}",
        want_json=True)
    if not listing or not isinstance(listing, list):
        print("❌ لیست پوشه گرفته نشد (ریپو/مسیر چک شود)")
        return 0

    files = [x["name"] for x in listing
             if isinstance(x, dict) and str(x.get("name", "")).lower().endswith(".txt")]
    if not files:
        print("❌ فایل .txt در پوشه نبود")
        return 0
    random.shuffle(files)
    files = files[:GH_FILES]
    print(f"📄 {len(files)} فایل کشور انتخاب شد")

    seen_set = set(S["seen"])
    pool_keys = {p["key"] for p in S["pool"]}
    candidates, shown = [], 0

    for fname in files:
        if len(candidates) >= need * 4:
            break
        raw = await http_get(session,
            f"https://raw.githubusercontent.com/{GH_REPO}/{GH_BRANCH}/{GH_FOLDER}/{fname}")
        if not raw:
            print(f"⚠️ خوانده نشد: {fname}")
            continue
        items = extract(raw)
        if items and shown < 2:
            print(f"🔍 نمونه {fname}: {items[0]['raw'][:80]}...")
            shown += 1
        flag = flag_of(fname)
        for it in items:
            key = hashlib.md5(it["raw"].encode()).hexdigest()
            if key in seen_set or key in pool_keys:
                continue
            candidates.append({"key": key, "text": fix_tag(it["raw"], flag),
                               "flag": flag, "type": proto_of(it["raw"]),
                               "host": it["host"], "port": it["port"]})

    print(f"🔍 {len(candidates)} کاندید جدید")
    alive = await test_alive(candidates)

    added = 0
    for c in alive:
        if added >= need or len(S["pool"]) >= POOL_CAP:
            break
        S["pool"].append({"key": c["key"], "text": c["text"],
                          "flag": c["flag"], "type": c["type"]})
        pool_keys.add(c["key"])
        added += 1
    save()
    print(f"📁 از ریپو: {added} کانفیگ اضافه شد")
    return added

TG_LAST = {}

async def gather_from_telegram(c):
    if not SOURCE:
        return 0
    last = TG_LAST.get(SOURCE, 0)
    if last == 0:
        async for m in c.get_chat_history(SOURCE, limit=1):
            TG_LAST[SOURCE] = m.id
        print(f"📍 چنل: خط پایه {TG_LAST[SOURCE]}")
        return 0
    fresh = []
    async for m in c.get_chat_history(SOURCE, limit=200):
        if m.id <= last:
            break
        fresh.append(m)
    if not fresh:
        print("📭 چنل: پیام جدید نبود")
        return 0
    TG_LAST[SOURCE] = fresh[0].id
    seen_set = set(S["seen"])
    pool_keys = {p["key"] for p in S["pool"]}
    added = 0
    for m in reversed(fresh):
        for raw in PROTO_RE.findall(m.text or m.caption or ""):
            raw = raw.strip().rstrip(").,;")
            key = hashlib.md5(raw.encode()).hexdigest()
            if key in seen_set or key in pool_keys:
                continue
            fm = re.search(r"#\[([^\]]+)\]", raw)
            flag = fm.group(1) if fm else "🌐"
            S["pool"].append({"key": key, "text": fix_tag(raw, flag),
                              "flag": flag, "type": proto_of(raw)})
            pool_keys.add(key)
            added += 1
    print(f"📺 از چنل: {added} کانفیگ جدید")
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
                    await asyncio.sleep(min(fw.value, 300) + 2)
                except Exception as ex:
                    print(f"❌ ارسال به {d}: {ex}")
        if not any_ok:
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
        print(f"✅ Config Pack #{S['pack_no']-1} ارسال شد ({sent} در این اجرا)")
        if len(S["pool"]) >= PACK_SIZE and time.time() - t0 < MAX_MINUTES * 60:
            await asyncio.sleep(PACK_EVERY)
    return sent, packs

async def main():
    load_state()
    print(f"▶️ شروع | پک بعدی: #{S['pack_no']} | مخزن: {len(S['pool'])} | ظرفیت: {HOURLY_CAPACITY}")
    async with Client("gh", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING) as c:
        n_ch = await gather_from_telegram(c)
        need = max(0, HOURLY_CAPACITY - n_ch - len(S["pool"]))
        print(f"🧮 چنل: {n_ch} | نیاز از ریپو: {need}")
        async with aiohttp.ClientSession() as http:
            n_gh = await gather_from_github(http, need)
        print(f"📥 مجموع جدید: {n_ch + n_gh} | مخزن: {len(S['pool'])}")
        if len(S["pool"]) >= PACK_SIZE:
            sent, packs = await send(c)
            print(f"🏁 تمام: {packs} پک / {sent} کانفیگ | باقی‌مانده: {len(S['pool'])}")
            if REPORT:
                txt = (f"📊 <b>گزارش اجرا</b>\n\n⏰ {time.strftime('%H:%M')}\n"
                       f"📺 چنل: {n_ch} | 📁 ریپو: {n_gh}\n"
                       f"📤 ارسال: {packs} پک / {sent} کانفیگ\n"
                       f"📦 پک بعدی: #{S['pack_no']} | 💾 باقی‌مانده: {len(S['pool'])}")
                try:
                    await c.send_message("me", txt, parse_mode="html")
                except Exception as ex:
                    print("⚠️ گزارش: " + str(ex)[:80])
        else:
            print("😴 مخزن به اندازه یک پک پر نشد")

asyncio.run(main())
