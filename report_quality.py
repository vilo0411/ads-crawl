"""Evidence coverage and a shared reference clock for reproducible cached reports."""
import datetime as dt
import time
from collections import defaultdict

_REFERENCE = None


def set_reference(value):
    global _REFERENCE
    _REFERENCE = dt.datetime.fromisoformat(value) if value else None


def now():
    return _REFERENCE.timestamp() if _REFERENCE is not None else time.time()


def today():
    return _REFERENCE.date() if _REFERENCE is not None else dt.date.fromtimestamp(now())


def stamp(fmt='%d/%m/%Y %H:%M'):
    return _REFERENCE.strftime(fmt) if _REFERENCE is not None else time.strftime(fmt)


def coverage(rows, platform):
    """Return counts without treating missing content or unknown accounts as absence."""
    if platform == 'google':
        videos = [r for r in rows if r['format'] == 'Video']
        active = [r for r in videos if r['active']]
        return dict(videos=len(videos), unresolved=sum(not r['youtube_id'] for r in videos),
                    active_videos=len(active), active_unresolved=sum(not r['youtube_id'] for r in active))
    by = defaultdict(list)
    for r in rows:
        by[r['page_id']].append(r)
    return dict(ads=len(rows), assets=len({r['asset_id'] for r in rows}), brands=len(by))


def coverage_box(rows, platform):
    c = coverage(rows, platform)
    if platform == 'google':
        detail = (f"{c['unresolved']}/{c['videos']} bản ghi video chưa lấy được YouTube ID; "
                  f"trong nhóm hiển thị gần đây: {c['active_unresolved']}/{c['active_videos']}. "
                  "Thiếu ID không có nghĩa là quảng cáo không có video. Không dùng nhóm đã xem để kết luận ‘chưa ai làm’ trên toàn thị trường.")
    else:
        detail = (f"{c['ads']} quảng cáo · {c['assets']} nhóm mẫu thiết kế · {c['brands']} fanpage có dữ liệu. "
                  "Mẫu được gộp bằng hình ảnh, có thể gồm biến thể và cần kiểm tra thủ công. "
                  "Tỷ lệ theo số quảng cáo chịu ảnh hưởng của việc triển khai nhiều bản; hãy đối chiếu số mẫu và từng công ty.")
    return ("<div class='box note'><h3>Độ phủ & cách đọc bằng chứng</h3><p>" + detail + "</p>"
            "<p>Ngày tham chiếu: " + stamp() + ". Đây là thời điểm tính trạng thái và cửa sổ thời gian, không xác nhận thời điểm crawl từng tài khoản. "
            "Không thấy trong dữ liệu ≠ không chạy quảng cáo. Phạm vi phụ thuộc danh sách tài khoản đã chọn; có thể thiếu agency, tài khoản phụ và nội dung không tải được.</p>"
            "<p>Quan sát: nội dung, CTA, điểm đến, thời gian và số bản. Suy luận: mục tiêu chiến dịch, vai trò phễu. "
            "Giả thuyết cần thử: tác động đến eKYC, nạp tiền và giao dịch. Không có dữ liệu để xác nhận CPA, ngân sách hoặc hiệu quả.</p></div>")
