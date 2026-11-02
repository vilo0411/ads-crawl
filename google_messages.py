"""Message, funnel stage, destination and idea key for every Google creative.

Inputs (all cached in the project folder): google_all_ads.csv, google_ocr.json (google_ocr.py),
google_dest.json (google_dest_check.py). Text = OCR of the preview + YouTube title. Rules are keyword based and
ordered: the first matching theme wins. The theme decides the stage; a Google Play label always means an
app-install ad (Chuyển đổi). Without readable text the format is the fallback and the row is flagged.
Output: projects/<project>/google_messages.json {creative_id: {...}} and a summary on stdout.
"""
import csv, hashlib, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# (theme, stage, patterns on lower-case text with diacritics); order matters.
THEMES = [
    ('Giới thiệu bạn / cộng tác viên', 'Chuyển đổi',
     [r'giới thiệu bạn', r'giới thiệu khách', r'cộng tác viên', r'\bctv\b', r'affiliate', r'hoa hồng', r'rủ bạn', r'mời bạn', r'đối tác']),
    ('Phí / margin', 'Chuyển đổi',
     [r'margin', r'lãi suất', r'lãi vay', r'phí giao dịch', r'phí 0', r'0 phí', r'(?<!\d)0\s?%', r'(?<!\d)0 đồng', r'ký quỹ']),
    ('Quà / tiền thưởng', 'Chuyển đổi',
     [r'tặng', r'\bquà', r'nhận ngay', r'nhận tới', r'nhận thưởng', r'\d+\s?k\b', r'\d+\s?triệu', r'tiền thưởng', r'voucher',
      r'hoàn tiền', r'cổ phiếu miễn phí', r'\btrúng', r'ưu đãi', r'khuyến mãi', r'miễn phí']),
    ('Kiến thức / tin tức', 'Nhận biết',
     [r'là gì', r'tin tức', r'báo cáo', r'tỷ giá', r'nhận định', r'phân tích', r'thị trường', r'webinar', r'hội thảo', r'khóa học']),
    ('Mở tài khoản', 'Chuyển đổi',
     [r'mở tài khoản', r'mở tk', r'mở ngay', r'đăng ký', r'ekyc', r'\d\s?phút']),
    ('Kiến thức / tin tức', 'Nhận biết',
     [r'hướng dẫn', r'cách đầu tư', r'\bhọc', r'kiến thức', r'người mới', r'bí quyết', r'chiến lược']),
    ('Sản phẩm / tính năng', 'Cân nhắc',
     [r'bảng giá', r'bảng điện', r'iboard', r'\bapp\b', r'ứng dụng', r'phái sinh', r'chứng chỉ quỹ', r'\bccq\b', r'trái phiếu',
      r'tích sản', r'tích lũy', r'nền tảng', r'công cụ', r'tính năng', r'giao dịch', r'đầu tư']),
    ('Thương hiệu / uy tín', 'Nhận biết',
     [r'uy tín', r'\btop\b', r'số 1', r'giải thưởng', r'hàng đầu', r'thương hiệu', r'đồng hành', r'liên hệ', r'chứng khoán']),
]
FORMAT_STAGE = {'Chữ (Search)': 'Cân nhắc', 'Ảnh': 'Nhận biết', 'Video': 'Nhận biết'}
APP_HINT = re.compile(r'tải app|tải ứng dụng|\bapp\b|ứng dụng|app store|google play|cài đặt')
OFFER = re.compile(r'\d+[.,]?\d*\s?(?:k\b|%|triệu|tr\b|cổ phiếu|cp\b)')
URL = re.compile(r'((?:[a-z0-9-]+\.)+(?:com\.vn|vn|com|net)(?:/[^\s›>]*)?)')


def is_app(r):
    return not r['format'].startswith('Chữ') and 'Play' in r['platforms'].split(',')


def classify(text):
    t = text.lower()
    for theme, stage, pats in THEMES:
        if any(re.search(p, t) for p in pats):
            return theme, stage
    return None, None


def build(project='chung-khoan'):
    proj = ROOT/'projects'/project
    rows = list(csv.DictReader(open(proj/'google_all_ads.csv', encoding='utf-8-sig')))
    ocr = json.loads((proj/'google_ocr.json').read_text(encoding='utf-8'))
    dest_file = proj/'google_dest.json'
    dest = json.loads(dest_file.read_text(encoding='utf-8'))['creatives'] if dest_file.exists() else {}
    out = {}
    for r in rows:
        cid = r['creative_id']
        title = r['video_title'] if r['video_title'] and not r['video_title'].endswith('.mp4') else ''
        text = ' '.join(x for x in [title, ocr.get(cid, {}).get('text', '')] if x)
        # Search previews also print the advertiser line ("CTCP Chứng khoán X"): drop it before classifying
        body = re.sub(r'(ctcp|công ty)[^.›]{0,60}?(chứng khoán|securities)\s*\S*', ' ', text, flags=re.I)
        # Search: the headline (right after the display URL) carries the message; descriptions and
        # sitelinks repeat generic offers, so they only decide when the headline matches nothing.
        head = ''
        if r['format'].startswith('Chữ'):
            u = URL.search(body.lower())
            head = body[u.end():u.end() + 70] if u else body[:120]
        theme, stage = classify(head) if head else (None, None)
        if not theme and len(body.strip()) >= 8:
            theme, stage = classify(body)
        source = 'Chữ trên quảng cáo' if theme else 'Định dạng (không đọc được chữ)'
        if not theme:
            theme, stage = 'Chưa đọc được nội dung', FORMAT_STAGE.get(r['format'], 'Nhận biết')
        if is_app(r):
            stage, source = 'Chuyển đổi', 'Nhãn Google Play (kéo cài app)'
        domains = dest.get(cid, [])
        if is_app(r):
            target = 'App (nhãn Google Play)' + (' · cũng gắn web' if domains else '')
        elif domains:
            target = 'Web công ty'
        else:
            target = 'Chưa xác định'
        m = URL.search(text.lower())
        path = m.group(1).rstrip('.,') if m and r['format'].startswith('Chữ') else ''
        offers = sorted(set(x.replace(' ', '') for x in OFFER.findall(text.lower())))
        # Idea key: one video = one YouTube ID; Search = theme + landing path; banner = theme + offer figures.
        if r['youtube_id']:
            idea = 'yt:' + r['youtube_id'].rsplit('/', 1)[-1]
        elif r['format'].startswith('Chữ') and theme != 'Chưa đọc được nội dung':
            idea = f"search:{theme}|{re.sub(r'^[^/]*', '', path) or '/'}"
        elif r['format'] == 'Ảnh' and theme != 'Chưa đọc được nội dung':
            idea = f"img:{theme}|{','.join(offers)}"
        else:
            idea = 'cr:' + cid
        out[cid] = dict(competitor=r['competitor'], format=r['format'], app=is_app(r), theme=theme, stage=stage,
                        stage_source=source, target=target, domains=domains, display_path=path, offers=offers,
                        app_hint=bool(APP_HINT.search(text.lower())) and not is_app(r), idea=idea,
                        text=text[:400])
    (proj/'google_messages.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return rows, out


def summary(rows, out):
    by = defaultdict(list)
    for r in rows:
        by[r['competitor']].append(out[r['creative_id']])
    print(f"{'công ty':20s} {'QC':>4s} {'ý tưởng':>7s} {'đọc được':>8s}  giai đoạn (NB/CN/CĐ)   đích web/app/chưa rõ")
    for c, ms in sorted(by.items(), key=lambda x: -len(x[1])):
        st = Counter(m['stage'] for m in ms); tg = Counter(m['target'].split(' ·')[0] for m in ms)
        print(f"{c:20s} {len(ms):4d} {len({m['idea'] for m in ms}):7d} {sum(m['theme'] != 'Chưa đọc được nội dung' for m in ms):8d}  "
              f"{st['Nhận biết']:3d}/{st['Cân nhắc']:3d}/{st['Chuyển đổi']:3d}           "
              f"{tg['Web công ty']}/{tg['App (nhãn Google Play)']}/{tg['Chưa xác định']}")
    print(Counter(m['theme'] for m in out.values()))


if __name__ == '__main__':
    summary(*build(*sys.argv[1:]))
