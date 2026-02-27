from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

def utc_now() -> datetime:
    """DB 저장 및 시스템 내부 계산용 (UTC)"""
    return datetime.now(timezone.utc)

def utc_kst() -> datetime:
    """외부 API(한투, 네이버) 요청 및 한국 장 시간 판별용 (KST)"""
    return datetime.now(KST)

def to_utc(dt: datetime) -> datetime:
    """기존 datetime 객체를 안전하게 UTC로 변환"""
    if dt is None:
        return None
    # 타임존 정보가 없는 naive 객체면 UTC로 간주
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    # 이미 타임존이 있다면 UTC로 변환
    return dt.astimezone(timezone.utc)