import calendar
from datetime import datetime

def get_days_in_month(year, month):
    """Trả về số ngày trong tháng của một năm cụ thể"""
    return calendar.monthrange(year, month)[1]

def get_weekday_name(year, month, day):
    """Trả về tên thứ trong tuần bằng tiếng Việt"""
    weekdays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    wd = calendar.weekday(year, month, day)
    return weekdays[wd]

def is_weekend(year, month, day):
    """Kiểm tra xem ngày đó có phải là thứ 7 hoặc Chủ Nhật không"""
    wd = calendar.weekday(year, month, day)
    return wd >= 5 # 5 là T7, 6 là CN