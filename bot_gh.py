import asyncio, hashlib, json, os, random, re, time
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
PROTO_RE = re.compile(r"(?:ss|vless|trojan|vmess|hysteria2?|hy2|tuic|ssr)://\S+", re.I)

_CC = ("Afghanistan:AF Albania:AL Algeria:DZ Argentina:AR Armenia:AM Australia:AU Austria:AT Azerbaijan:AZ "
       "Bahrain:BH Bangladesh:BD Belarus:BY Belgium:BE Belize:BZ Bolivia:BO BosniaAndHerzegovina:BA "
       "Botswana:BW Brazil:BR Brunei:BN Bulgaria:BG Cambodia:KH Cameroon:CM Canada:CA Chile:CL China:CN "
       "Colombia:CO CostaRica:CR Croatia:HR Cuba:CU Cyprus:CY Czech:CZ Denmark:DK Ecuador:EC Egypt:EG "
       "Estonia:EE Finland:FI France:FR Georgia:GE Germany:DE Ghana:GH Greece:GR HongKong:HK Hungary:HU "
       "Iceland:IS India:IN Indonesia:ID Iran:IR Iraq:IQ Ireland:IE Israel:IL Italy:IT Japan:JP "
       "Jordan:JO Kazakhstan:KZ Kenya:KE Kuwait:KW Kyrgyzstan:KG Laos:LA Latvia:LV Lebanon:LB "
       "Lithuania:LT Luxembourg:LU Macau:MO Malaysia:MY Maldives:MV Malta:MT Mexico:MX Moldova:MD "
       "Mongolia:MN Montenegro:ME Morocco:MA Myanmar:MM Nepal:NP Netherlands:NL NewZealand:NZ "
       "Nigeria:NG Norway:NO Oman:OM Pakistan:PK Palestine:PS Panama:PA Peru:PE Philippines:PH "
       "Poland:PL Portugal:PT Qatar:QA Romania:RO Russia:RU SaudiArabia:SA Serbia:RS Singapore:SG "
       "Slovakia:SK Slovenia:SI SouthAfrica:ZA SouthKorea:KR Spain:ES SriLanka:LK Sweden:SE "
       "Switzerland:CH Syria:SY Taiwan:TW Tajikistan:TJ Thailand:TH Tunisia:TN Turkey:TR "
       "Turkmenistan:TM UAE:AE Ukraine:UA UnitedStates:US UnitedTurkmenistan:TM UAE:AE Ukraine:UA UnitedStates:US UnitedKingdom:GB Uzbekistan:UZ "
       "Venezuela:VE Vietnam:VN Yemen:YE")

import base64

ISO = {}
for pair in _CC.split():
    name, code = pair.split(":")
    ISO[name.lower()] = code

def flag_of(filename: str) -> str:
    base = filename.rsplit(".", 1)[0].lower()
    for name, code in ISO.items():
        if base == name:
            return "".join(chr(ord(c) - 0x41 + 0x1F1E6) for c in code.upper())
    return "🌐"

def e(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def fix_tag(cfg: str, flag: str) -> str:
    m = re.search(r"#\S*$", cfg)
    tag = f"#[{flag}]{TAG_TEXT}"
    return cfg[:m.start()] + tag if m else cfg + tag

def proto_of(raw: str) -> str:
    p = raw.split("://", 1)[0].upper()
    return "HYSTERIA2" if p == "HY2" else p

def extract(text: str):
    out = []
    if not text:
        return out
    for raw in PROTO_RE.findall(text):
        raw = raw.strip().rstrip(").,;")
        try:
            if raw.lower().startswith("vmess://"):
                b = raw[8:].strip()
                b += "=" * (-len(b) % 4)
                j = json.loads(base64.urlsafe_b64decode(b).decode("utf-8", "ignore"))
                host, port = j.get("add") or "", int(j.get("port") or 0)
            else:
                m = re.match(r"[a-z0-9]+://[^@/]+@(\[[^\]]+\]|[^:/]+):(\d+)", raw, re.I)
                if not m:
                    continue
                host, port = m.group(1).strip("[]"), int(m.group(2))
            if host and 0 < port < 65536:
                out.append({"raw": raw, "host": host, "port": port})
        except Exception:
            continue
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

async def gh_fetch(session, url):
    for attempt in (1, 2, 3):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status == 200:
                    return await r.text()
        except Exception:
            if attempt == 3:
                print(f"⚠️ GET ناموفق: {url[:70]}")
        await asyncio.sleep(1)
    return None

async def test_alive(candidates) -> list:
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

async def gather_from_github(session, need: int) -> int:
    if need <= 0:
        print("📁 ریپو لازم نبود — چنل کافی بود")
        return 0
    print(f"📁 ریپوی منبع: {GH_REPO}/{GH_FOLDER} (برداشت از انتهای فایل‌ها)")
    tree = await gh_fetch(session,
        f"https://api.github.com/repos/{GH_REPO}/git/trees/{GH_BRANCH}?recursive=1")
    if not tree or '"tree"' not in tree:
        print("❌ لیست فایل‌ها گرفته نشد")
        return 0

    paths = [p for p in re.findall(r'"path":"([^"]+?)\.txt"', tree) if GH_FOLDER in p]
    if not paths:
        print("❌ فایل .txt پیدا نشد")
        return 0
    random.shuffle(paths)
    print(f"📄 {len(paths)} فایل کشور موجود")

    seen_set = set(S["seen"])
    pool_keys = {p["key"] for p in S["pool"]}
    candidates = []

    for path in paths:
        if len(candidates) >= need * 3:
            break
        raw = await gh_fetch(session,
            f"https://raw.githubusercontent.com/{GH_REPO}/{GH_BRANCH}/{path}")
        if not raw:
            continue
        lines = [l for l in raw.strip().splitlines() if l.strip()]
        tail = lines[-GH_TAIL:]
        fname = path.rsplit("/", 1)[-1]
        flag = flag_of(fname)
        for line in tail:
            for item in extract(line):
                key = hashlib.md5(item["raw"].encode()).hexdigest()
                if key in seen_set or key in pool_keys:
                    continue
                candidates.append({
                    "key": key, "text": fix_tag(item["raw"], flag),
                    "flag": flag, "type": proto_of(item["raw"]),
                    "host": item["host"], "port": item["port"]})

    print(f"🔍 {len(candidates)} کاندید — تست اتصال...")
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

async def gather_from_telegram(c: Client) -> int:
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

async def send(c: Client) -> tuple:
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
