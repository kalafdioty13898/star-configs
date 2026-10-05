import asyncio
import base64
import hashlib
import json
import os
import random
import re
import time

import aiohttp
from pyrogram import Client
from pyrogram.errors import FloodWait

# ─── تنظیمات از Secrets ───
API_ID         = int(os.environ["API_ID"])
API_HASH       = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
SOURCE         = os.environ.get("SOURCE", "").strip()      # چنل تلگرام مبدا (اختیاری)
DESTS          = [d.strip() for d in os.environ.get("DESTS", "").split(",") if d.strip()]
TAG_TEXT       = os.environ.get("TAG_TEXT") or "tel:@star_shop_vpn"
HEADER         = os.environ.get("HEADER")  or "🔥 NEW SERVER\n\n⚡ Ultra Ping\n🚀 Fresh Config Pack"
QUOTE          = os.environ.get("QUOTE")   or "اینترنت آزاد حق مردم است ✌️\n\nفرزند ایران و جان‌فدای میهن 🖤❤️‍🩹"
CHANNEL        = os.environ.get("CHANNEL") or "📡 @star_shop_vpn"

# ─── منبع گیت‌هابی (ریپوی رفیقت) ───
GH_REPO      = os.environ.get("GH_REPO") or "Argh94/V2RayAutoConfig"
GH_BRANCH    = os.environ.get("GH_BRANCH") or "main"
GH_FOLDER    = os.environ.get("GH_FOLDER") or "configs"
GH_MAX       = int(os.environ.get("GH_MAX", "150"))      # سقف برداشت جدید در هر اجرا
TEST_ENABLED = os.environ.get("TEST_ENABLED", "1") == "1"  # 0 = بدون تست اتصال
TEST_TIMEOUT = float(os.environ.get("TEST_TIMEOUT", "3"))  # ثانیه timeout هر تست
TEST_CONC    = int(os.environ.get("TEST_CONC", "40"))      # چند تست همزمان
TEST_BUDGET  = int(os.environ.get("TEST_BUDGET", "45"))    # سقف کل ثانیه تست در هر اجرا

PACK_SIZE    = int(os.environ.get("PACK_SIZE", "3"))
PACK_EVERY   = int(os.environ.get("PACK_EVERY", "600"))
MAX_MINUTES  = int(os.environ.get("MAX_MINUTES", "50"))
INITIAL_SCAN = int(os.environ.get("INITIAL_SCAN", "0"))
REPORT       = os.environ.get("REPORT", "1") == "1"

POOL_CAP   = 5000
STATE_FILE = "state.json"
SEP = "━━━━━━━━━━━━━━━━━━"

PROTO_RE = re.compile(r"(?:ss|vless|trojan|vmess|hysteria2?|hy2|tuic|ssr)://\S+", re.I)

# ─── اسم فایل کشور → کد ISO → پرچم ───
COUNTRY_ISO = {
    "Afghanistan":"AF","Albania":"AL","Algeria":"DZ","Argentina":"AR","Armenia":"AM",
    "Australia":"AU","Austria":"AT","Azerbaijan":"AZ","Bahrain":"BH","Bangladesh":"BD",
    "Belarus":"BY","Belgium":"BE","Belize":"BZ","Bolivia":"BO","BosniaAndHerzegovina":"BA",
    "Botswana":"BW","Brazil":"BR","Brunei":"BN","Bulgaria":"BG","Cambodia":"KH",
    "Cameroon":"CM","Canada":"CA","Chile":"CL","China":"CN","Colombia":"CO",
    "CostaRica":"CR","Croatia":"HR","Cuba":"CU","Cyprus":"CY","Czech":"CZ","Czechia":"CZ",
    "Denmark":"DK","Ecuador":"EC","Egypt":"EG","Estonia":"EE","Finland":"FI","France":"FR",
    "Georgia":"GE","Germany":"DE","Ghana":"GH","Greece":"GR","HongKong":"HK","Hungary":"HU",
    "Iceland":"IS","India":"IN","Indonesia":"ID","Iran":"IR","Iraq":"IQ","Ireland":"IE",
    "Israel":"IL","Italy":"IT","Japan":"JP","Jordan":"JO","Kazakhstan":"KZ","Kenya":"KE",
    "Kuwait":"KW","Kyrgyzstan":"KG","Laos":"LA","Latvia":"LV","Lebanon":"LB","Lithuania":"LT",
    "Luxembourg":"LU","Macau":"MO","Malaysia":"MY","Maldives":"MV","Malta":"MT","Mexico":"MX",
    "Moldova":"MD","Mongolia":"MN","Montenegro":"ME","Morocco":"MA","Myanmar":"MM",
    "Nepal":"NP","Netherlands":"NL","NewZealand":"NZ","Nigeria":"NG","NorthKorea":"KP",
    "NorthMacedonia":"MK","Norway":"NO","Oman":"OM","Pakistan":"PK","Palestine":"PS",
    "Panama":"PA","Peru":"PE","Philippines":"PH","Poland":"PL","Portugal":"PT","Qatar":"QA",
    "Romania":"RO","Russia":"RU","SaudiArabia":"SA","Serbia":"RS","Singapore":"SG",
    "Slovakia":"SK","Slovenia":"SI","SouthAfrica":"ZA","SouthKorea":"KR","Spain":"ES",
    "SriLanka":"LK","Sweden":"SE","Switzerland":"CH","Syria":"SY","Taiwan":"TW",
    "Tajikistan":"TJ","Thailand":"TH","Tunisia":"TN","Turkey":"TR","Turkmenistan":"TM",
    "UAE":"AE","Ukraine":"UA","United
