from datetime import datetime, timezone, timedelta

# IST = UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))


# =========================
# 🌍 UTC → IST CONVERSION
# =========================
def utc_to_ist(utc_str: str):
    """
    Convert Strava UTC timestamp string to IST datetime
    Example input: "2024-01-01T05:30:00Z"
    """
    if not utc_str:
        return None

    try:
        # Handle 'Z' (Zulu time)
        if utc_str.endswith("Z"):
            utc_str = utc_str.replace("Z", "+00:00")

        dt = datetime.fromisoformat(utc_str)
        return dt.astimezone(IST)

    except Exception:
        return None


# =========================
# ⏰ GET CURRENT IST TIME
# =========================
def get_ist_now():
    """
    Returns current IST datetime
    """
    return datetime.now(IST)


# =========================
# 🕒 GET CURRENT UTC TIME
# =========================
def get_utc_now():
    """
    Returns current UTC datetime
    """
    return datetime.now(timezone.utc)


# =========================
# 📅 FORMAT DATETIME
# =========================
def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S"):
    """
    Format datetime safely
    """
    if not dt:
        return None

    try:
        return dt.strftime(fmt)
    except Exception:
        return None


# =========================
# 🔁 IST → UTC (OPTIONAL)
# =========================
def ist_to_utc(dt: datetime):
    """
    Convert IST datetime to UTC
    """
    if not dt:
        return None

    try:
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


# =========================
# ⏳ TIME DIFFERENCE (MINUTES)
# =========================
def minutes_between(dt1: datetime, dt2: datetime):
    """
    Returns difference in minutes between two datetimes
    """
    if not dt1 or not dt2:
        return None

    try:
        delta = dt2 - dt1
        return int(delta.total_seconds() / 60)
    except Exception:
        return None
