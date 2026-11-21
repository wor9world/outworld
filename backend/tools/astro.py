from __future__ import annotations

import re
import sys
from collections import deque
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import swisseph as swe

# รองรับการรันไฟล์เดี่ยวๆ (python tools/astro.py) ให้ยัง import tools.registry ได้
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.registry import register_tool

# ==============================================================================
# 0. CONFIG & LOCATION RESOLVER (ไม่ใช้ LLM)
# ==============================================================================

# ฐานข้อมูลสถานที่แบบ Offline (เพิ่มจังหวัด/เมืองที่ใช้บ่อยได้เรื่อยๆ)
BUILTIN_LOCATIONS: dict[str, tuple[float, float, str]] = {
    # Thailand
    "bangkok": (13.7563, 100.5018, "Asia/Bangkok"),
    "กรุงเทพ": (13.7563, 100.5018, "Asia/Bangkok"),
    "กรุงเทพมหานคร": (13.7563, 100.5018, "Asia/Bangkok"),
    "กทม": (13.7563, 100.5018, "Asia/Bangkok"),
    "chiang mai": (18.7883, 98.9853, "Asia/Bangkok"),
    "เชียงใหม่": (18.7883, 98.9853, "Asia/Bangkok"),
    "chiang rai": (19.9105, 99.8406, "Asia/Bangkok"),
    "เชียงราย": (19.9105, 99.8406, "Asia/Bangkok"),
    "phuket": (7.8804, 98.3923, "Asia/Bangkok"),
    "ภูเก็ต": (7.8804, 98.3923, "Asia/Bangkok"),
    "khon kaen": (16.4322, 102.8236, "Asia/Bangkok"),
    "ขอนแก่น": (16.4322, 102.8236, "Asia/Bangkok"),
    "nakhon ratchasima": (14.9799, 102.0978, "Asia/Bangkok"),
    "นครราชสีมา": (14.9799, 102.0978, "Asia/Bangkok"),
    "โคราช": (14.9799, 102.0978, "Asia/Bangkok"),
    "chonburi": (13.3611, 100.9847, "Asia/Bangkok"),
    "ชลบุรี": (13.3611, 100.9847, "Asia/Bangkok"),
    "pattaya": (12.9236, 100.8825, "Asia/Bangkok"),
    "พัทยา": (12.9236, 100.8825, "Asia/Bangkok"),
    "hat yai": (7.0086, 100.4747, "Asia/Bangkok"),
    "หาดใหญ่": (7.0086, 100.4747, "Asia/Bangkok"),
    "songkhla": (7.1898, 100.5951, "Asia/Bangkok"),
    "สงขลา": (7.1898, 100.5951, "Asia/Bangkok"),
    "udon thani": (17.4138, 102.7872, "Asia/Bangkok"),
    "อุดรธานี": (17.4138, 102.7872, "Asia/Bangkok"),
    "ubon ratchathani": (15.2448, 104.8473, "Asia/Bangkok"),
    "อุบลราชธานี": (15.2448, 104.8473, "Asia/Bangkok"),
    "nonthaburi": (13.8621, 100.5144, "Asia/Bangkok"),
    "นนทบุรี": (13.8621, 100.5144, "Asia/Bangkok"),
    # Major World Cities
    "singapore": (1.3521, 103.8198, "Asia/Singapore"),
    "tokyo": (35.6762, 139.6503, "Asia/Tokyo"),
    "seoul": (37.5665, 126.9780, "Asia/Seoul"),
    "taipei": (25.0330, 121.5654, "Asia/Taipei"),
    "hong kong": (22.3193, 114.1694, "Asia/Hong_Kong"),
    "beijing": (39.9042, 116.4074, "Asia/Shanghai"),
    "shanghai": (31.2304, 121.4737, "Asia/Shanghai"),
    "mumbai": (19.0760, 72.8777, "Asia/Kolkata"),
    "new delhi": (28.6139, 77.2090, "Asia/Kolkata"),
    "london": (51.5074, -0.1278, "Europe/London"),
    "paris": (48.8566, 2.3522, "Europe/Paris"),
    "berlin": (52.5200, 13.4050, "Europe/Berlin"),
    "new york": (40.7128, -74.0060, "America/New_York"),
    "los angeles": (34.0522, -118.2437, "America/Los_Angeles"),
    "sydney": (-33.8688, 151.2093, "Australia/Sydney"),
}


def set_ephe_path(path: str | None = None) -> None:
    if path:
        swe.set_ephe_path(path)


def _resolve_location(
    location: str,
    lat: float | None = None,
    lon: float | None = None,
    tz_offset: float | None = None,
    tz_name: str | None = None,
) -> tuple[float, float, str | None, float | None, str]:
    """คืนค่า (lat, lon, tz_name, tz_offset_override, display_name)"""
    if lat is not None and lon is not None:
        return float(lat), float(lon), tz_name, tz_offset, location or f"{lat},{lon}"

    loc_clean = (location or "Bangkok").strip()
    key = loc_clean.lower()

    # กรณีส่งพิกัดมาเป็น string เช่น "13.7563, 100.5018"
    coord_match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", loc_clean)
    if coord_match:
        c_lat = float(coord_match.group(1))
        c_lon = float(coord_match.group(2))
        return c_lat, c_lon, tz_name or "Asia/Bangkok", tz_offset, f"{c_lat},{c_lon}"

    # 1) ค้นหาในฐานข้อมูล Offline
    if key in BUILTIN_LOCATIONS:
        b_lat, b_lon, b_tz = BUILTIN_LOCATIONS[key]
        return b_lat, b_lon, tz_name or b_tz, tz_offset, loc_clean

    # ค้นหาแบบ substring เล็กน้อย (เช่น "อ.เมือง เชียงใหม่")
    for name_k, vals in BUILTIN_LOCATIONS.items():
        if name_k in key:
            b_lat, b_lon, b_tz = vals
            return b_lat, b_lon, tz_name or b_tz, tz_offset, loc_clean

    # 2) Fallback: ถ้าลง geopy + timezonefinder ไว้ จะค้นหาทั่วโลกอัตโนมัติ
    try:
        from geopy.geocoders import Nominatim
        from timezonefinder import TimezoneFinder

        # geopy/timezonefinder ส่ง type hint มาไม่ตรงกับ runtime (geocode() ถูกประกาศ
        # เป็น coroutine และ timeout เป็น object) จึงอ้างผ่าน Any แล้วตรวจค่าจริงเอง
        geolocator: Any = Nominatim(user_agent="astro_no_llm_tool")
        geo: Any = geolocator.geocode(loc_clean, timeout=5)
        if geo:
            tf = TimezoneFinder()
            found_tz = tz_name or tf.timezone_at(lat=geo.latitude, lng=geo.longitude) or "UTC"
            return float(geo.latitude), float(geo.longitude), found_tz, tz_offset, geo.address
    except Exception:
        pass

    raise ValueError(
        f"ไม่พบข้อมูลพิกัดของสถานที่ '{location}' กรุณาระบุชื่อจังหวัด/เมืองหลัก หรือส่งค่า lat, lon มาโดยตรง"
    )


def _parse_birth_datetime(
    birth_date: str,
    birth_time: str,
    tz_name: str | None,
    tz_offset: float | None,
) -> tuple[datetime, datetime, float, float]:
    """
    คืนค่า (local_dt, utc_dt, jd_ut, actual_tz_offset_hours)
    รองรับรูปแบบวันที่: YYYY-MM-DD, DD/MM/YYYY (รองรับพ.ศ. ถ้าปี > 2400)
    รองรับรูปแบบเวลา: HH:MM หรือ HH:MM:SS
    """
    d_str = birth_date.strip()
    t_str = birth_time.strip()

    # Parse date
    parsed_date = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            dt_d = datetime.strptime(d_str, fmt)
            y = dt_d.year
            if y > 2400:  # แปลง พ.ศ. -> ค.ศ. อัตโนมัติ
                y -= 543
            parsed_date = (y, dt_d.month, dt_d.day)
            break
        except ValueError:
            continue
    if parsed_date is None:
        raise ValueError(
            f"รูปแบบวันเกิดไม่ถูกต้อง: '{birth_date}' (ตัวอย่างที่รองรับ: '1995-08-17' หรือ '17/08/2538')"
        )

    # Parse time
    parsed_time = None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            dt_t = datetime.strptime(t_str, fmt)
            parsed_time = (dt_t.hour, dt_t.minute, dt_t.second)
            break
        except ValueError:
            continue
    if parsed_time is None:
        raise ValueError(f"รูปแบบเวลาเกิดไม่ถูกต้อง: '{birth_time}' (ตัวอย่าง: '14:30' หรือ '14:30:00')")

    naive = datetime(*parsed_date, *parsed_time)

    if tz_offset is not None:
        tz_obj = timezone(timedelta(hours=float(tz_offset)))
        local_dt = naive.replace(tzinfo=tz_obj)
    elif tz_name:
        local_dt = naive.replace(tzinfo=ZoneInfo(tz_name))
    else:
        local_dt = naive.replace(tzinfo=ZoneInfo("Asia/Bangkok"))

    utc_dt = local_dt.astimezone(UTC)
    offset_hours = (local_dt.utcoffset() or timedelta(0)).total_seconds() / 3600.0
    hour_float = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, hour_float, swe.GREG_CAL)
    return local_dt, utc_dt, jd_ut, offset_hours


def _fmt_dms(deg_in_sign: float) -> str:
    d = int(deg_in_sign)
    m_float = (deg_in_sign - d) * 60.0
    m = int(m_float)
    s = round((m_float - m) * 60.0)
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d:02d}°{m:02d}'{s:02d}\""


def _safe_calc_ut(jd_ut: float, body: int, flags: int) -> tuple[float, float] | None:
    """คำนวณตำแหน่งดาวโดยลองใช้ Swiss Ephemeris ก่อน หากขาดไฟล์ .se1 จะ fallback ไป Moshier

    หมายเหตุ: แพ็กเกจสองตัวคืนค่าไม่เท่ากัน — ``pysweph`` คืน ``(xx, retflags, warning)``
    ส่วน ``pyswisseph`` คืน ``(xx, retflags)`` จึงอ่านเฉพาะสมาชิกตัวแรกเพื่อให้ใช้ได้ทั้งคู่
    """
    try:
        xx = swe.calc_ut(jd_ut, body, flags)[0]
        return float(xx[0]) % 360.0, float(xx[3])
    except Exception:
        try:
            fallback_flags = (flags & ~swe.FLG_SWIEPH) | swe.FLG_MOSEPH
            xx = swe.calc_ut(jd_ut, body, fallback_flags)[0]
            return float(xx[0]) % 360.0, float(xx[3])
        except Exception:
            return None


def _safe_houses_ex(
    jd_ut: float, lat: float, lon: float, hsys: bytes, flags: int
) -> tuple[list[float], float, float]:
    """รองรับทั้ง pyswisseph (12 cusps) และ pysweph (13 cusps ที่ index 0 ว่าง)"""
    cusps_raw, ascmc = swe.houses_ex(jd_ut, lat, lon, hsys, flags)
    if len(cusps_raw) >= 13:
        cusps = [float(cusps_raw[i]) % 360.0 for i in range(1, 13)]
    else:
        cusps = [float(cusps_raw[i]) % 360.0 for i in range(12)]
    asc = float(ascmc[0]) % 360.0
    mc = float(ascmc[1]) % 360.0
    return cusps, asc, mc


# ==============================================================================
# 1. WESTERN ASTROLOGY (Tropical / Placidus)
# ==============================================================================

WESTERN_SIGNS = [
    ("Aries", "เมษ"),
    ("Taurus", "พฤษภ"),
    ("Gemini", "เมถุน"),
    ("Cancer", "กรกฎ"),
    ("Leo", "สิงห์"),
    ("Virgo", "กันย์"),
    ("Libra", "ตุลย์"),
    ("Scorpio", "พิจิก"),
    ("Sagittarius", "ธนู"),
    ("Capricorn", "มังกร"),
    ("Aquarius", "กุมภ์"),
    ("Pisces", "มีน"),
]


def _house_of_lon(lon: float, cusps: list[float]) -> int:
    for i in range(12):
        c1 = cusps[i]
        c2 = cusps[(i + 1) % 12]
        if c1 <= c2:
            if c1 <= lon < c2:
                return i + 1
        else:  # ข้าม 360° -> 0°
            if lon >= c1 or lon < c2:
                return i + 1
    return 1


def calc_western(jd_ut: float, lat: float, lon: float) -> dict[str, Any]:
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    cusps, asc, mc = _safe_houses_ex(jd_ut, lat, lon, b"P", 0)

    bodies = [
        ("Sun", swe.SUN),
        ("Moon", swe.MOON),
        ("Mercury", swe.MERCURY),
        ("Venus", swe.VENUS),
        ("Mars", swe.MARS),
        ("Jupiter", swe.JUPITER),
        ("Saturn", swe.SATURN),
        ("Uranus", swe.URANUS),
        ("Neptune", swe.NEPTUNE),
        ("Pluto", swe.PLUTO),
        ("North Node", swe.TRUE_NODE),
        ("Chiron", swe.CHIRON),
    ]

    planets: dict[str, Any] = {}
    for name, pid in bodies:
        res = _safe_calc_ut(jd_ut, pid, flags)
        if res is None:
            continue
        p_lon, speed = res
        sign_idx = int(p_lon // 30)
        deg_in_sign = p_lon % 30.0
        en_sign, th_sign = WESTERN_SIGNS[sign_idx]
        planets[name] = {
            "lon": round(p_lon, 4),
            "sign": en_sign,
            "sign_th": th_sign,
            "degree": _fmt_dms(deg_in_sign),
            "house": _house_of_lon(p_lon, cusps),
            "retrograde": speed < 0,
        }

    if "North Node" in planets:
        sn_lon = (planets["North Node"]["lon"] + 180.0) % 360.0
        sn_idx = int(sn_lon // 30)
        en_sign, th_sign = WESTERN_SIGNS[sn_idx]
        planets["South Node"] = {
            "lon": round(sn_lon, 4),
            "sign": en_sign,
            "sign_th": th_sign,
            "degree": _fmt_dms(sn_lon % 30.0),
            "house": _house_of_lon(sn_lon, cusps),
            "retrograde": planets["North Node"]["retrograde"],
        }

    asc_idx = int(asc // 30)
    mc_idx = int(mc // 30)
    return {
        "zodiac_system": "Tropical",
        "house_system": "Placidus",
        "ascendant": {
            "lon": round(asc, 4),
            "sign": WESTERN_SIGNS[asc_idx][0],
            "sign_th": WESTERN_SIGNS[asc_idx][1],
            "degree": _fmt_dms(asc % 30.0),
        },
        "midheaven": {
            "lon": round(mc, 4),
            "sign": WESTERN_SIGNS[mc_idx][0],
            "sign_th": WESTERN_SIGNS[mc_idx][1],
            "degree": _fmt_dms(mc % 30.0),
        },
        "houses": {
            f"House_{i + 1}": {
                "cusp_lon": round(cusps[i], 4),
                "sign": WESTERN_SIGNS[int(cusps[i] // 30)][0],
                "degree": _fmt_dms(cusps[i] % 30.0),
            }
            for i in range(12)
        },
        "planets": planets,
    }


# ==============================================================================
# 2. INDIA / VEDIC ASTROLOGY (Sidereal Lahiri + Whole Sign + Nakshatra)
# ==============================================================================

RASHIS = [
    ("Mesha", "เมษ", "Aries"),
    ("Vrishabha", "พฤษภ", "Taurus"),
    ("Mithuna", "เมถุน", "Gemini"),
    ("Karka", "กรกฎ", "Cancer"),
    ("Simha", "สิงห์", "Leo"),
    ("Kanya", "กันย์", "Virgo"),
    ("Tula", "ตุลย์", "Libra"),
    ("Vrishchika", "พิจิก", "Scorpio"),
    ("Dhanu", "ธนู", "Sagittarius"),
    ("Makara", "มังกร", "Capricorn"),
    ("Kumbha", "กุมภ์", "Aquarius"),
    ("Meena", "มีน", "Pisces"),
]

NAKSHATRAS = [
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
]

VIMSHOTTARI_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]


def _nakshatra_info(sid_lon: float) -> dict[str, Any]:
    nak_span = 360.0 / 27.0  # 13°20'
    pada_span = nak_span / 4.0  # 3°20'
    idx = int(sid_lon // nak_span) % 27
    rem = sid_lon - idx * nak_span
    pada = int(rem // pada_span) + 1
    return {
        "nakshatra": NAKSHATRAS[idx],
        "pada": min(pada, 4),
        "lord": VIMSHOTTARI_LORDS[idx % 9],
    }


def calc_india(jd_ut: float, lat: float, lon: float) -> dict[str, Any]:
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
    ayanamsa = float(swe.get_ayanamsa_ut(jd_ut))

    _, lagna_lon, _ = _safe_houses_ex(jd_ut, lat, lon, b"W", swe.FLG_SIDEREAL)
    lagna_rashi_idx = int(lagna_lon // 30)

    graha_list = [
        ("Surya (Sun)", swe.SUN),
        ("Chandra (Moon)", swe.MOON),
        ("Mangala (Mars)", swe.MARS),
        ("Budha (Mercury)", swe.MERCURY),
        ("Guru (Jupiter)", swe.JUPITER),
        ("Shukra (Venus)", swe.VENUS),
        ("Shani (Saturn)", swe.SATURN),
        ("Rahu", swe.MEAN_NODE),
    ]

    grahas: dict[str, Any] = {}
    for name, pid in graha_list:
        res = _safe_calc_ut(jd_ut, pid, flags)
        if res is None:
            continue
        g_lon, speed = res
        r_idx = int(g_lon // 30)
        house_num = ((r_idx - lagna_rashi_idx) % 12) + 1
        nak = _nakshatra_info(g_lon)
        grahas[name] = {
            "lon": round(g_lon, 4),
            "rashi": RASHIS[r_idx][0],
            "rashi_th": RASHIS[r_idx][1],
            "rashi_num": r_idx + 1,
            "degree": _fmt_dms(g_lon % 30.0),
            "house_whole_sign": house_num,
            "retrograde": speed < 0,
            **nak,
        }

    if "Rahu" in grahas:
        ketu_lon = (grahas["Rahu"]["lon"] + 180.0) % 360.0
        k_idx = int(ketu_lon // 30)
        grahas["Ketu"] = {
            "lon": round(ketu_lon, 4),
            "rashi": RASHIS[k_idx][0],
            "rashi_th": RASHIS[k_idx][1],
            "rashi_num": k_idx + 1,
            "degree": _fmt_dms(ketu_lon % 30.0),
            "house_whole_sign": ((k_idx - lagna_rashi_idx) % 12) + 1,
            "retrograde": grahas["Rahu"]["retrograde"],
            **_nakshatra_info(ketu_lon),
        }

    moon_nak = grahas.get("Chandra (Moon)", {})
    return {
        "system": "Sidereal (Lahiri / Chitrapaksha)",
        "ayanamsa_deg": round(ayanamsa, 4),
        "house_system": "Whole Sign (Rashi D-1)",
        "lagna": {
            "lon": round(lagna_lon, 4),
            "rashi": RASHIS[lagna_rashi_idx][0],
            "rashi_th": RASHIS[lagna_rashi_idx][1],
            "rashi_num": lagna_rashi_idx + 1,
            "degree": _fmt_dms(lagna_lon % 30.0),
            **_nakshatra_info(lagna_lon),
        },
        "janma_nakshatra": moon_nak.get("nakshatra"),
        "janma_pada": moon_nak.get("pada"),
        "starting_mahadasha": moon_nak.get("lord"),
        "grahas": grahas,
    }


# ==============================================================================
# 3. BAZI / FOUR PILLARS OF DESTINY (Solar Terms + True Solar Time)
# ==============================================================================

STEMS = [
    ("甲", "Jia", "Wood", "Yang", "ไม้หยาง"),
    ("乙", "Yi", "Wood", "Yin", "ไม้หยิน"),
    ("丙", "Bing", "Fire", "Yang", "ไฟหยาง"),
    ("丁", "Ding", "Fire", "Yin", "ไฟหยิน"),
    ("戊", "Wu", "Earth", "Yang", "ดินหยาง"),
    ("己", "Ji", "Earth", "Yin", "ดินหยิน"),
    ("庚", "Geng", "Metal", "Yang", "ทองหยาง"),
    ("辛", "Xin", "Metal", "Yin", "ทองหยิน"),
    ("壬", "Ren", "Water", "Yang", "น้ำหยาง"),
    ("癸", "Gui", "Water", "Yin", "น้ำหยิน"),
]

BRANCHES = [
    ("子", "Zi", "Rat", "Water", "ชวด"),
    ("丑", "Chou", "Ox", "Earth", "ฉลู"),
    ("寅", "Yin", "Tiger", "Wood", "ขาล"),
    ("卯", "Mao", "Rabbit", "Wood", "เถาะ"),
    ("辰", "Chen", "Dragon", "Earth", "มะโรง"),
    ("巳", "Si", "Snake", "Fire", "มะเส็ง"),
    ("午", "Wu", "Horse", "Fire", "มะเมีย"),
    ("未", "Wei", "Goat", "Earth", "มะแม"),
    ("申", "Shen", "Monkey", "Metal", "วอก"),
    ("酉", "You", "Rooster", "Metal", "ระกา"),
    ("戌", "Xu", "Dog", "Earth", "จอ"),
    ("亥", "Hai", "Pig", "Water", "กุน"),
]


def _signed_angle_diff(a: float, b: float) -> float:
    return ((a - b + 180.0) % 360.0) - 180.0


def _find_sun_crossing_jd(target_lon: float, jd_start: float, jd_end: float) -> float:
    flags = swe.FLG_SWIEPH
    lo, hi = jd_start, jd_end
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        sun_res = _safe_calc_ut(mid, swe.SUN, flags)
        assert sun_res is not None
        diff = _signed_angle_diff(sun_res[0], target_lon)
        if diff < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _jdn_gregorian(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    y2 = y + 4800 - a
    m2 = m + 12 * a - 3
    return d + (153 * m2 + 2) // 5 + 365 * y2 + y2 // 4 - y2 // 100 + y2 // 400 - 32045


def _format_pillar(stem_idx: int, branch_idx: int) -> dict[str, Any]:
    s = STEMS[stem_idx % 10]
    b = BRANCHES[branch_idx % 12]
    return {
        "chinese": f"{s[0]}{b[0]}",
        "pinyin": f"{s[1]} {b[1]}",
        "stem": {"char": s[0], "pinyin": s[1], "element": s[2], "polarity": s[3], "th": s[4]},
        "branch": {"char": b[0], "pinyin": b[1], "animal": b[2], "element": b[3], "th": b[4]},
    }


def calc_bazi(
    local_dt: datetime,
    jd_ut: float,
    lon: float,
    tz_offset_hours: float,
    late_zi_next_day: bool = True,
) -> dict[str, Any]:
    # 1) คำนวณ True Solar Time (ปรับลองจิจูด + Equation of Time)
    lon_offset_min = (lon - tz_offset_hours * 15.0) * 4.0
    eot_min = 0.0
    try:
        eot_days = swe.time_equ(jd_ut)
        eot_min = float(eot_days) * 24.0 * 60.0
    except Exception:
        eot_min = 0.0

    true_solar_dt = local_dt + timedelta(minutes=lon_offset_min + eot_min)

    # 2) หาตำแหน่งอาทิตย์จริง (Tropical) เพื่อแบ่งปีและเดือนตาม 24 Jieqi
    sun_res = _safe_calc_ut(jd_ut, swe.SUN, swe.FLG_SWIEPH)
    assert sun_res is not None
    sun_lon = sun_res[0]

    # ปี BaZi เปลี่ยนที่ Lichun (立春 = 315° Tropical ~ 4 ก.พ.)
    civ_y = local_dt.year
    if local_dt.month == 1:
        bazi_year = civ_y - 1
    elif local_dt.month == 2:
        jd_lichun = _find_sun_crossing_jd(
            315.0,
            swe.julday(civ_y, 2, 1, 0.0, swe.GREG_CAL),
            swe.julday(civ_y, 2, 7, 0.0, swe.GREG_CAL),
        )
        bazi_year = civ_y if jd_ut >= jd_lichun else civ_y - 1
    else:
        bazi_year = civ_y

    y_stem = (bazi_year - 4) % 10
    y_branch = (bazi_year - 4) % 12

    # เดือน BaZi: เริ่มที่ 寅 (index 2) เมื่อ Sun = 315° (เพิ่มขึ้นทีละ 30°)
    solar_month_offset = int(((sun_lon - 315.0) % 360.0) // 30.0)
    m_branch = (2 + solar_month_offset) % 12
    # Wu Hu Dun (五虎遁)
    m_stem = ((y_stem % 5) * 2 + 2 + solar_month_offset) % 10

    # วัน BaZi (60-day continuous cycle) + จัดการยามจื่อดึก 23:00-23:59
    eff_dt = true_solar_dt
    if late_zi_next_day and true_solar_dt.hour >= 23:
        eff_dt = true_solar_dt + timedelta(days=1)

    jdn = _jdn_gregorian(eff_dt.year, eff_dt.month, eff_dt.day)
    day_cycle_idx = (jdn + 49) % 60
    d_stem = day_cycle_idx % 10
    d_branch = day_cycle_idx % 12

    # ยาม BaZi ตาม True Solar Time: 23:00-00:59 = 子(0), 01:00-02:59 = 丑(1), ...
    h_branch = ((true_solar_dt.hour + 1) // 2) % 12
    # Wu Shu Dun (五鼠遁)
    h_stem = ((d_stem % 5) * 2 + h_branch) % 10

    dm = STEMS[d_stem]
    return {
        "true_solar_time": true_solar_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "day_master": {
            "char": dm[0],
            "pinyin": dm[1],
            "element": dm[2],
            "polarity": dm[3],
            "th": dm[4],
        },
        "pillars": {
            "year": _format_pillar(y_stem, y_branch),
            "month": _format_pillar(m_stem, m_branch),
            "day": _format_pillar(d_stem, d_branch),
            "hour": _format_pillar(h_stem, h_branch),
        },
        "sun_tropical_lon": round(sun_lon, 4),
    }


# ==============================================================================
# 4. HUMAN DESIGN (Rave Mandala - 88° Solar Arc, 64 Gates, 36 Channels, 9 Centers)
# ==============================================================================

HD_WHEEL = [
    41,
    19,
    13,
    49,
    30,
    55,
    37,
    63,
    22,
    36,
    25,
    17,
    21,
    51,
    42,
    3,
    27,
    24,
    2,
    23,
    8,
    20,
    16,
    35,
    45,
    12,
    15,
    52,
    39,
    53,
    62,
    56,
    31,
    33,
    7,
    4,
    29,
    59,
    40,
    64,
    47,
    6,
    46,
    18,
    48,
    57,
    32,
    50,
    28,
    44,
    1,
    43,
    14,
    34,
    9,
    5,
    26,
    11,
    10,
    58,
    38,
    54,
    61,
    60,
]

HD_CENTERS: dict[str, set[int]] = {
    "Head": {64, 61, 63},
    "Ajna": {47, 24, 4, 17, 43, 11},
    "Throat": {62, 23, 56, 35, 12, 45, 33, 8, 31, 20, 16},
    "G": {7, 1, 13, 25, 46, 2, 15, 10},
    "Heart": {21, 51, 26, 40},
    "Sacral": {5, 14, 29, 59, 9, 3, 42, 27, 34},
    "SolarPlexus": {36, 22, 37, 6, 49, 55, 30},
    "Spleen": {48, 57, 44, 50, 32, 28, 18},
    "Root": {53, 60, 52, 19, 39, 41, 58, 38, 54},
}

HD_CHANNELS: list[tuple[int, int]] = [
    (64, 47),
    (61, 24),
    (63, 4),
    (17, 62),
    (43, 23),
    (11, 56),
    (35, 36),
    (12, 22),
    (45, 21),
    (1, 8),
    (7, 31),
    (13, 33),
    (10, 20),
    (10, 57),
    (10, 34),
    (20, 57),
    (20, 34),
    (34, 57),
    (25, 51),
    (26, 44),
    (40, 37),
    (2, 14),
    (5, 15),
    (29, 46),
    (59, 6),
    (27, 50),
    (3, 60),
    (42, 53),
    (9, 52),
    (48, 16),
    (18, 58),
    (28, 38),
    (32, 54),
    (49, 19),
    (55, 39),
    (30, 41),
]

GATE_TO_CENTER = {g: c for c, gates in HD_CENTERS.items() for g in gates}
MOTORS = {"Sacral", "Heart", "SolarPlexus", "Root"}


def _lon_to_gate_line(lon: float) -> dict[str, Any]:
    angle = (lon - 302.0) % 360.0  # Gate 41 เริ่มที่ 302° (2° Aquarius)
    gate_idx = int(angle // 5.625) % 64
    rem = angle - gate_idx * 5.625
    line = min(int(rem // 0.9375) + 1, 6)
    gate = HD_WHEEL[gate_idx]
    return {
        "gate": gate,
        "line": line,
        "code": f"{gate}.{line}",
        "lon": round(lon % 360.0, 4),
    }


def _calc_hd_activations(jd_ut: float) -> dict[str, dict[str, Any]]:
    flags = swe.FLG_SWIEPH
    bodies = [
        ("Sun", swe.SUN),
        ("Moon", swe.MOON),
        ("North Node", swe.TRUE_NODE),
        ("Mercury", swe.MERCURY),
        ("Venus", swe.VENUS),
        ("Mars", swe.MARS),
        ("Jupiter", swe.JUPITER),
        ("Saturn", swe.SATURN),
        ("Uranus", swe.URANUS),
        ("Neptune", swe.NEPTUNE),
        ("Pluto", swe.PLUTO),
    ]
    raw: dict[str, float] = {}
    for name, pid in bodies:
        res = _safe_calc_ut(jd_ut, pid, flags)
        if res is not None:
            raw[name] = res[0]

    ordered = [
        ("Sun", raw["Sun"]),
        ("Earth", (raw["Sun"] + 180.0) % 360.0),
        ("North Node", raw["North Node"]),
        ("South Node", (raw["North Node"] + 180.0) % 360.0),
        ("Moon", raw["Moon"]),
        ("Mercury", raw["Mercury"]),
        ("Venus", raw["Venus"]),
        ("Mars", raw["Mars"]),
        ("Jupiter", raw["Jupiter"]),
        ("Saturn", raw["Saturn"]),
        ("Uranus", raw["Uranus"]),
        ("Neptune", raw["Neptune"]),
        ("Pluto", raw["Pluto"]),
    ]
    return {name: _lon_to_gate_line(lon) for name, lon in ordered}


def calc_humandesign(jd_ut: float) -> dict[str, Any]:
    # 1) Personality (เวลาเกิดจริง)
    personality = _calc_hd_activations(jd_ut)
    sun_birth_lon = personality["Sun"]["lon"]

    # 2) Design (จุดที่อาทิตย์ย้อนหลังไป 88° เป๊ะๆ)
    target_design_sun = (sun_birth_lon - 88.0) % 360.0
    jd_design = _find_sun_crossing_jd(target_design_sun, jd_ut - 96.0, jd_ut - 80.0)
    design = _calc_hd_activations(jd_design)

    # 3) รวม Gates และหา Defined Channels / Centers
    active_gates = {v["gate"] for v in personality.values()} | {v["gate"] for v in design.values()}
    defined_channels: list[str] = []
    adj: dict[str, set[str]] = {c: set() for c in HD_CENTERS}
    defined_centers: set[str] = set()

    for g1, g2 in HD_CHANNELS:
        if g1 in active_gates and g2 in active_gates:
            c1, c2 = GATE_TO_CENTER[g1], GATE_TO_CENTER[g2]
            defined_channels.append(f"{min(g1, g2)}-{max(g1, g2)}")
            defined_centers.add(c1)
            defined_centers.add(c2)
            adj[c1].add(c2)
            adj[c2].add(c1)

    # 4) คำนวณ Connected Components เพื่อเช็ก Definition & Motor-to-Throat
    visited: set[str] = set()
    components: list[set[str]] = []
    for c in defined_centers:
        if c not in visited:
            comp: set[str] = set()
            q = deque([c])
            visited.add(c)
            while q:
                curr = q.popleft()
                comp.add(curr)
                for nxt in adj[curr]:
                    if nxt not in visited:
                        visited.add(nxt)
                        q.append(nxt)
            components.append(comp)

    def _motor_connected_to_throat() -> bool:
        return any("Throat" in comp and any(m in comp for m in MOTORS) for comp in components)

    # 5) Type, Strategy, Signature, Not-Self
    if not defined_centers:
        hd_type = "Reflector"
        strategy = "Wait a Lunar Cycle (28 days)"
        signature, not_self = "Surprise", "Disappointment"
    elif "Sacral" in defined_centers:
        if _motor_connected_to_throat():
            hd_type = "Manifesting Generator"
            strategy = "To Respond & Inform"
        else:
            hd_type = "Generator"
            strategy = "To Respond"
        signature, not_self = "Satisfaction", "Frustration"
    elif _motor_connected_to_throat():
        hd_type = "Manifestor"
        strategy = "To Inform"
        signature, not_self = "Peace", "Anger"
    else:
        hd_type = "Projector"
        strategy = "Wait for the Invitation"
        signature, not_self = "Success", "Bitterness"

    # 6) Inner Authority
    if not defined_centers:
        authority = "Lunar (Outer)"
    elif "SolarPlexus" in defined_centers:
        authority = "Emotional (Solar Plexus)"
    elif "Sacral" in defined_centers:
        authority = "Sacral"
    elif "Spleen" in defined_centers:
        authority = "Splenic"
    elif "Heart" in defined_centers:
        authority = "Ego / Heart"
    elif "G" in defined_centers:
        authority = "Self-Projected"
    else:
        authority = "Mental / Environmental (No Inner Authority)"

    split_map = {
        0: "No Definition",
        1: "Single Definition",
        2: "Split Definition",
        3: "Triple Split Definition",
        4: "Quadruple Split Definition",
    }
    definition = split_map.get(len(components), f"{len(components)}-Split Definition")

    profile = f"{personality['Sun']['line']}/{design['Sun']['line']}"
    cross_gates = (
        f"({personality['Sun']['gate']}/{personality['Earth']['gate']} | "
        f"{design['Sun']['gate']}/{design['Earth']['gate']})"
    )

    design_utc_tuple = swe.revjul(jd_design, swe.GREG_CAL)
    d_hr = int(design_utc_tuple[3])
    d_min = int((design_utc_tuple[3] - d_hr) * 60)

    return {
        "type": hd_type,
        "strategy": strategy,
        "authority": authority,
        "profile": profile,
        "definition": definition,
        "signature": signature,
        "not_self_theme": not_self,
        "incarnation_cross_gates": cross_gates,
        "design_utc": f"{design_utc_tuple[0]:04d}-{design_utc_tuple[1]:02d}-{design_utc_tuple[2]:02d} {d_hr:02d}:{d_min:02d} UTC",
        "defined_centers": sorted(defined_centers),
        "open_centers": sorted(set(HD_CENTERS.keys()) - defined_centers),
        "defined_channels": sorted(defined_channels),
        "active_gates": sorted(active_gates),
        "personality": personality,
        "design": design,
    }


# ==============================================================================
# 5. UNIFIED ENTRYPOINT FOR PIPELINE & STANDALONE
# ==============================================================================

ALL_SYSTEMS = ("bazi", "india", "western", "humandesign")


@register_tool(
    name="astro_all",
    description="คำนวณดวง 4 ศาสตร์ (BaZi, India/Vedic, Western, Human Design) จากวันเวลาและสถานที่เกิด",
)
def run(
    birth_date: str,
    birth_time: str = "12:00",
    location: str = "Bangkok",
    lat: float | None = None,
    lon: float | None = None,
    tz_offset: float | None = None,
    tz_name: str | None = None,
    systems: list[str] | tuple[str, ...] | None = None,
    ephe_path: str | None = None,
) -> dict[str, Any]:
    """
    Default: คำนวณครบทั้ง 4 ศาสตร์ (bazi, india, western, humandesign)
    """
    try:
        set_ephe_path(ephe_path)
        r_lat, r_lon, r_tz_name, r_tz_offset, loc_label = _resolve_location(
            location=location, lat=lat, lon=lon, tz_offset=tz_offset, tz_name=tz_name
        )
        local_dt, utc_dt, jd_ut, actual_offset = _parse_birth_datetime(
            birth_date=birth_date, birth_time=birth_time, tz_name=r_tz_name, tz_offset=r_tz_offset
        )

        selected = [s.lower().strip() for s in systems] if systems else list(ALL_SYSTEMS)
        output: dict[str, Any] = {
            "input_resolved": {
                "local_time": local_dt.isoformat(),
                "utc_time": utc_dt.isoformat(),
                "jd_ut": round(jd_ut, 6),
                "location": loc_label,
                "lat": r_lat,
                "lon": r_lon,
                "tz_offset_hours": actual_offset,
            }
        }

        if "bazi" in selected:
            output["bazi"] = calc_bazi(local_dt, jd_ut, r_lon, actual_offset)
        if "india" in selected:
            output["india"] = calc_india(jd_ut, r_lat, r_lon)
        if "western" in selected:
            output["western"] = calc_western(jd_ut, r_lat, r_lon)
        if "humandesign" in selected:
            output["humandesign"] = calc_humandesign(jd_ut)

        return {
            "ok": True,
            "data": output,
            "meta": {
                "systems": selected,
                "engine": "pysweph / Swiss Ephemeris",
            },
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "meta": {"systems": systems or list(ALL_SYSTEMS)},
            "error": str(exc),
        }


if __name__ == "__main__":
    import json

    # ทดสอบรัน 4 ศาสตร์พร้อมกันด้วยข้อมูลแค่ วัน-เวลา-สถานที่
    res = run(
        birth_date="1992-08-08",
        birth_time="16:49",
        location="ยะลา",
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
