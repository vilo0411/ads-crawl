"""Build the Vietnamese executive report from the frozen securities snapshot.

Run with python-docx, reportlab, Pillow and pypdf installed. No network calls.
The source cache and previous reports are read-only inputs.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image,
    KeepTogether,
)

ROOT = Path(__file__).resolve().parent
PROJ = ROOT / 'projects/chung-khoan'
OUT = PROJ / 'bao-cao-lanh-dao'
STEM = 'Bao_cao_quang_cao_doi_thu_29-10-2026'
REFERENCE = '2026-10-29T14:29:00+07:00'

# Explicit identity mapping: never fuzzy-match similar financial company names.
BRANDS = [
    ('VPS', '108015722146379', 'VPS'),
    ('SSI', '132771703438783', 'SSI'),
    ('TCBS', '1504697249783367', 'TCBS'),
    ('Vietcap', '343028851058', 'Vietcap'),
    ('HSC', '1517153298580277', 'HSC'),
    ('MBS', '349312325177779', 'MBS'),
    ('VNDirect', '123434971018658', 'VNDirect'),
    ('KIS', '561500030387546', 'KIS'),
    ('Mirae Asset', '303619527172219', 'Mirae Asset'),
    ('VPBankS', '107578535212906', 'VPBankS'),
    ('LPS', '197779796755847', 'LPS'),
    ('VFS', '273872576046675', 'Nhất Việt - VFS'),
    ('Shinhan / SSV', '101384519398514', 'Shinhan - SSV'),
    ('ABS', '390676534851790', 'An Bình - ABS'),
    ('Yuanta', '131656534155296', 'Yuanta'),
    ('DNSE', '2033102266712313', 'DNSE'),
    ('AAS', '1197026010336908', 'Smart Invest - AAS'),
    ('KBSV', '458482900870297', 'KB Securities'),
    ('ACBS', '107317735256838', 'ACBS'),
    ('Rồng Việt', '134188476770555', 'Rồng Việt'),
    ('TPS', '2070825876552556', 'TPS'),
    ('KIRIN', '106218628765203', 'KIRIN'),
    ('TVSI', '171970319483394', 'Tân Việt'),
    ('HD Securities', '1112132331974304', 'HD Securities'),
    ('VCBS', '151091451760284', 'VCBS'),
]

# Editorial interpretation. Quantities, states, URLs and asset formats are derived
# separately from the snapshot. Theme presence is restricted to Meta captions
# explicitly selected below; it is not extrapolated from Google platform labels.
NOTES = {
 'VPS': ('Giáo dục trước, tạo nhu cầu tìm hiểu sau',
   'Dùng series Direct Indexing để giải thích khái niệm và lợi ích tích sản dài hạn; bổ sung quảng cáo webinar. Cách tiếp cận quan sát được thiên về kiến thức và xây dựng niềm tin.',
   [('Kiến thức / phân tích', 'Direct Indexing'), ('Kiến thức / phân tích', 'GỬI TIẾT KIỆM')]),
 'SSI': ('Ưu đãi mở tài khoản, có cả lối vào app và web',
   'Kết hợp quà cổ phiếu, ưu đãi và trải nghiệm số. Có quảng cáo trỏ thẳng kho ứng dụng, có quảng cáo đưa về trang mở tài khoản; vì vậy không nên gộp tất cả thành một luồng cài app.',
   [('Ưu đãi / chi phí', '2 cổ phiếu PAN'), ('Tính năng / sản phẩm', 'ProfitX'), ('Tò mò / cá nhân hóa', '8 câu hỏi')]),
 'TCBS': ('Chưa đủ dữ liệu trong phạm vi Facebook và Google App',
   'Không ghi nhận quảng cáo Facebook trong cache đã chọn. Google chỉ có một bản ghi chữ Search lịch sử, không thuộc nhóm quảng bá app của báo cáo này.', []),
 'Vietcap': ('Google có dấu hiệu quảng bá app, thiếu nội dung để phân tích sâu',
   'Có một bản ghi video mang nhãn Play hiển thị gần đây nhưng chưa lấy được YouTube ID. Video Vietcap IQ đã khảo sát nằm ở nhóm YouTube ngoài phạm vi App; không dùng video đó để mô tả mẫu App.', []),
 'HSC': ('Dùng sự kiện để kéo sự quan tâm đến phân tích doanh nghiệp',
   'Quảng cáo Facebook giới thiệu buổi phân tích IDC cùng chuyên gia và đại diện doanh nghiệp; nút đích là sự kiện Facebook, còn nội dung có nhắc đăng ký Zoom. Chưa có mẫu Google App.',
   [('Kiến thức / phân tích', 'IDICO')]),
 'MBS': ('Nội dung đa dạng, điểm đến nhất quán về app',
   'Dùng ưu đãi phí, margin và quà cho hành vi mở tài khoản/nạp tiền; song song là video chuyên viên chia sẻ kiến thức rồi giới thiệu ưu đãi. Toàn bộ URL đích đã phân loại dẫn tới kho ứng dụng hoặc mở app.',
   [('Ưu đãi / chi phí', 'MARGIN'), ('Kiến thức / phân tích', 'breakout')]),
 'VNDirect': ('Lấy tính năng DTRADE làm lý do trải nghiệm',
   'Giới thiệu không gian giao dịch có thể tùy biến, đặt lệnh một chạm và thao tác trên cùng màn hình. Carousel/nhiều ảnh phù hợp để trình bày nhiều góc của sản phẩm; điểm đến là website DTRADE.',
   [('Tính năng / sản phẩm', 'MỘT CHẠM'), ('Tính năng / sản phẩm', 'KHÔNG GIAN GIAO DỊCH')]),
 'KIS': ('Mở tài khoản và giới thiệu bạn bè bằng ưu đãi',
   'Caption tập trung vào quà mở tài khoản, cổ phiếu và thưởng giới thiệu iKIS. Phần lớn mẫu dẫn về trang chương trình, một phần dùng Messenger. DCO chiếm nhiều bản ghi nhưng chưa đủ bằng chứng gọi tất cả là cùng một video.',
   [('Ưu đãi / chi phí', 'THÊM BẠN'), ('Ưu đãi / chi phí', 'CHỨNG SĨ MÃ ĐÁO')]),
 'Mirae Asset': ('Chưa thấy bằng chứng quảng cáo trong bộ dữ liệu đã chọn',
   'Fanpage đã có trong danh sách kiểm tra nhưng không ghi nhận quảng cáo. Chưa tìm thấy tài khoản Google trong danh sách nguồn đã lưu. Chưa có cơ sở mô tả asset, nội dung hoặc điểm đến.', []),
 'VPBankS': ('Chi phí giao dịch và tiền nhàn rỗi là hai góc nội dung',
   'Facebook giới thiệu Zero Fee và eMax trên NEO Invest. Mẫu Zero Fee có URL cuối về onboarding web; mẫu eMax có redirect Facebook chưa xác minh được điểm đến sản phẩm. Google App chỉ được ghi nhận ở dữ liệu lịch sử.',
   [('Ưu đãi / chi phí', '0 phí giao dịch'), ('Tính năng / sản phẩm', 'eMax')]),
 'LPS': ('Chồng nhiều quyền lợi vào một lời mời tải app',
   'LOOP by LPS gắn tải app/mở tài khoản với quà cổ phiếu, miễn phí, ưu đãi margin và khóa học. Số bản quảng cáo lớn nhưng chỉ có ít nhóm thiết kế; nhiều bản không đồng nghĩa nhiều ý tưởng.',
   [('Ưu đãi / chi phí', 'TẢI 1 APP'), ('Ưu đãi / chi phí', '0 PHÍ, 0 LÃI')]),
 'VFS': ('Combo mở tài khoản kết hợp lợi ích sử dụng vốn',
   'Có quà cổ phiếu, ưu đãi phí/margin và nội dung về sản phẩm cho tiền nhàn rỗi. Điểm đến gồm App Store, web có form và trang Facebook; cách đi tới sản phẩm không đồng nhất.',
   [('Ưu đãi / chi phí', 'COMBO'), ('Tính năng / sản phẩm', 'TIỀN NHÀN RỖI')]),
 'Shinhan / SSV': ('Bán trải nghiệm nền tảng cùng ưu đãi',
   'Giới thiệu VinaStalk như nơi đọc thông tin, phân tích, giao dịch và kết nối; đồng thời quảng bá S-Era trên San Xin Ha. Nội dung khác dùng phí, lãi và quà để thúc đẩy trải nghiệm. Google App được ghi nhận trong lịch sử, chưa thấy hiển thị gần đây.',
   [('Tính năng / sản phẩm', 'VINASTALK CHÍNH THỨC'), ('Tính năng / sản phẩm', 'SAN XIN HA'), ('Ưu đãi / chi phí', '300k')]),
 'ABS': ('Kết hợp chi phí vốn, tiện ích tài khoản và uy tín',
   'Facebook dùng margin, số tài khoản theo ý muốn, giải thưởng và kết quả kinh doanh. Google có video giải thưởng mang nhãn Play; đây là thông điệp uy tín xuất hiện trong nhóm có dấu hiệu quảng bá app.',
   [('Ưu đãi / chi phí', 'MARGIN 6.9'), ('Tính năng / sản phẩm', 'CHỌN SỐ'), ('Uy tín / cộng đồng', 'APEA')]),
 'Yuanta': ('Gắn bối cảnh thị trường với nhu cầu đầu tư',
   'Ảnh đơn khai thác tích sản, margin, tài chính gia đình; ngoài ra có nội dung cộng đồng và tuyển chương trình cố vấn. Đây là ví dụ cho thấy quảng cáo của một công ty không phải mẫu nào cũng nhằm mở tài khoản.',
   [('Ưu đãi / chi phí', 'MARGIN 6.8'), ('Kiến thức / phân tích', 'BỐ MẸ'), ('Uy tín / cộng đồng', 'BƯỚC CHÂN')]),
 'DNSE': ('Lợi ích tính năng được diễn giải bằng tình huống sử dụng',
   'Facebook giới thiệu Lightspeed API và DNSE MCP cho tự động hóa, dữ liệu và AI. Video Google App “Tài khoản không ngủ” đi từ vấn đề tiền nhàn rỗi đến lợi ích, giao diện và lời mời tải Entrade X.',
   [('Tính năng / sản phẩm', 'LIGHTSPEED API'), ('Tính năng / sản phẩm', 'DNSE MCP')]),
 'AAS': ('Dùng công cụ đọc thị trường để kéo người dùng về web',
   'Ảnh quảng bá AAS Market Insights nhấn mạnh tiết kiệm thời gian, tổng hợp dữ liệu và góc nhìn chuyên gia; dẫn về trang insights. Google App có tư liệu lịch sử về thưởng giới thiệu nhưng phần lớn bản ghi thiếu ID video.',
   [('Tính năng / sản phẩm', 'MARKET INSIGHTS')]),
 'KBSV': ('Đặt tính năng lọc cổ phiếu cạnh lợi ích về phí',
   'KB Buddy được giới thiệu qua bộ lọc cổ phiếu, 0 phí và các gói margin; có chương trình quà cho khách mở mới. Google App có hiển thị gần đây nhưng đa số video thiếu ID nên mức phân tích nội dung bị giới hạn.',
   [('Tính năng / sản phẩm', 'LỌC MÃ'), ('Ưu đãi / chi phí', 'MARGIN')]),
 'ACBS': ('Kích hoạt lại người dùng bằng ưu đãi phí',
   'Facebook có mẫu mời theo dõi trang và mẫu miễn phí cho khách không giao dịch 90 ngày. Google App lịch sử có tiêu đề ACBS SMART và AI SMARTY; tiêu đề chỉ hỗ trợ nhận diện chủ đề, chưa thay thế việc xem video.',
   [('Ưu đãi / chi phí', 'PHÍ VỀ 0')]),
 'Rồng Việt': ('Đổi mới giao diện app để tạo lý do quay lại',
   'Nội dung iDragon giải thích trang chủ mới và khả năng cá nhân hóa. URL cuối là bài giới thiệu tính năng; dù cache gán nhãn “Landing có form”, báo cáo không đồng nhất mẫu này với trang mở tài khoản.',
   [('Tính năng / sản phẩm', 'MỚI GIAO DIỆN')]),
 'TPS': ('Nội dung doanh nghiệp và kiến thức danh mục',
   'Hai mẫu ảnh nói về kết quả kinh doanh và vai trò trái phiếu trong danh mục. Không ghi nhận URL đích của nút CTA; có thể mô tả chủ đề nhưng chưa xác nhận hành trình chuyển đổi.',
   [('Uy tín / cộng đồng', 'KẾT QUẢ KINH DOANH'), ('Kiến thức / phân tích', 'TRÁI PHIẾU')]),
 'KIRIN': ('Mời theo dõi để tiếp cận kiến thức tài chính',
   'Một mẫu ảnh giới thiệu nội dung tài chính cá nhân, chứng khoán và xây dựng tài sản; CTA thích trang. Đây là mẫu xây dựng tập người theo dõi trong phạm vi quan sát.',
   [('Kiến thức / phân tích', 'tài chính cá nhân')]),
 'TVSI': ('Chương trình gắn hoạt động giao dịch với cộng đồng',
   'Mẫu nhiều ảnh nói về Điểm Kết Nối và chương trình kỷ niệm 20 năm; dẫn về bài chương trình. Chưa thấy Google App trong bộ dữ liệu.',
   [('Uy tín / cộng đồng', 'Điểm Kết Nối')]),
 'HD Securities': ('Gỡ hiểu lầm của người mới bằng video kiến thức',
   'Video giải thích cần bao nhiêu tiền để đầu tư và vì sao chỉ số tăng nhưng tài khoản vẫn giảm. Dùng câu hỏi gần với vấn đề của người mới, kết hợp chữ/hoạt hình và giọng đọc; phần lớn mẫu chưa có URL đích CTA.',
   [('Kiến thức / phân tích', 'nhiều tiền'), ('Kiến thức / phân tích', 'Xanh vỏ')]),
 'VCBS': ('Dữ liệu nghiên cứu và công cụ AI là nội dung tiếp cận',
   'Ảnh giới thiệu báo cáo doanh nghiệp, báo cáo vĩ mô và VCBS MCP. Điểm đến có trang Facebook và trang hướng dẫn kết nối công cụ; chưa thấy nhóm Google App.',
   [('Kiến thức / phân tích', 'BÁO CÁO'), ('Tính năng / sản phẩm', 'VCBS MCP')]),
}


def read_csv(name):
    with (PROJ / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def fold(s):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower().replace('đ', 'd'))
                   if unicodedata.category(c) != 'Mn')


def app_row(r):
    return not r['format'].startswith('Chữ') and 'Play' in r['platforms'].split(',')


def counts(rows, key):
    return ', '.join(f'{k or "Chưa rõ"}: {v}' for k, v in Counter(r[key] for r in rows).most_common()) or 'Chưa có dữ liệu'


def dest(r):
    if r['dest'] == 'Messenger':
        return 'Messenger'
    t = r['landing_type']
    if t in ('App Store', 'Google Play', 'Mở app (deep link)'):
        return 'Kho ứng dụng / mở app'
    if t == 'Trang Facebook':
        return 'Facebook / sự kiện'
    if t == 'Landing có form':
        # A form detector alone does not establish account-opening intent.
        return 'Web có form (chưa xác nhận mục đích)'
    if t:
        return 'Web nội dung / sản phẩm / sự kiện'
    return 'Chưa có URL đích xác minh'


def build_data():
    snapshot = json.loads((PROJ/'report_snapshot.json').read_text())
    assert snapshot['reference_at'] == REFERENCE
    fb, google = read_csv('all_ads.csv'), read_csv('google_all_ads.csv')
    assert len(fb) == snapshot['meta']['ads']
    raw = {}
    for _, pid, _ in BRANDS:
        path = PROJ/'pages'/f'{pid}.json'
        if not path.exists():
            raise ValueError(f'Missing fanpage cache: {path}')
        for row in json.loads(path.read_text()):
            raw[str(row['ad_archive_id'])] = row
    assert set(raw) == {r['ad_archive_id'] for r in fb}
    meta_packs = [dict(json.loads(f.read_text()), folder=str(f.parent.relative_to(ROOT)))
                  for f in (PROJ/'winners').glob('*/meta.json')]
    google_packs = [dict(json.loads(f.read_text()), folder=str(f.parent.relative_to(ROOT)))
                    for f in (PROJ/'winners_google').glob('*/meta.json')]
    profiles = []
    for i, (name, pid, gn) in enumerate(BRANDS):
        ids = {str(r['ad_archive_id']) for r in raw.values() if str(r['page_id']) == pid}
        fr = [r for r in fb if r['ad_archive_id'] in ids]
        gr = [r for r in google if r['competitor'] == gn]
        ar = [r for r in gr if app_row(r)]
        recent = [r for r in ar if r['active'] == 'True']
        selected, themes = [], {}
        for theme, needle in NOTES[name][2]:
            found = next((r for r in fr if fold(needle) in fold(r['body'])), None)
            if found is None:
                raise ValueError(f'Editorial evidence missing: {name}: {needle}')
            themes.setdefault(theme, []).append(found['ad_archive_id'])
            if found['ad_archive_id'] not in {r['ad_archive_id'] for r in selected}:
                selected.append(found)
        if not selected and fr:
            selected = fr[:1]
        mp = [p for p in meta_packs if p['page_id'] == pid and p['media_evidence'] == 'video_url_present']
        gp = []
        for pack in google_packs:
            matches = [r for r in ar if r['youtube_id'] and
                       r['youtube_id'].rsplit('/', 1)[-1] == pack['youtube'].rsplit('/', 1)[-1]]
            if pack['competitor'] == gn and matches:
                verified = dict(pack)
                verified['transparency_links'] = [r['link'] for r in matches]
                gp.append(verified)
        for r in selected:
            rawrow = raw[r['ad_archive_id']]
            thumb = PROJ/'thumbs'/f'{rawrow.get("collation_id", "")}.jpg'
            if not thumb.exists():
                thumb = PROJ/'thumbs'/f'{r["asset_id"]}.jpg'
            r['image_local'] = str(thumb.relative_to(ROOT)) if thumb.exists() else ''
            r['destination_group'] = dest(r)
        profiles.append(dict(name=name, page_id=pid, google_name=gn,
            group='Top 10' if i < 10 else 'Xu hướng', fb=fr, google=gr, app=ar,
            recent=recent, selected=selected, themes=themes,
            designs=len({r['asset_id'] or r['ad_archive_id'] for r in fr}),
            title=NOTES[name][0], analysis=NOTES[name][1], meta_packs=mp, google_packs=gp))
    scoped = [r for p in profiles for r in p['app']]
    return dict(reference_at=REFERENCE, profiles=profiles,
                totals=dict(fb=len(fb), google_app=len(scoped),
                    google_app_recent=sum(r['active']=='True' for r in scoped),
                    google_app_missing_id=sum(r['format']=='Video' and not r['youtube_id'] for r in scoped)),
                outside_google_group='Chỉ thấy trên Google: không đưa vào mẫu số của báo cáo này')


def p(text): return ('p', text)
def h(text): return ('h', text)
def table(headers, rows, widths=None): return ('table', headers, rows, widths)
def link(label, url): return ('link', label, url)
def image(path, caption, width=145, max_height=62): return ('image', path, caption, width, max_height)


def status_app(b):
    if b['recent']: return f"Gần đây: {len(b['recent'])}"
    if b['app']: return f"Chỉ lịch sử: {len(b['app'])}"
    if b['google']: return 'Chưa thấy mẫu App'
    return 'Chưa có tài khoản nguồn'


def ratio(n, d): return f'{n}/{d}'


def display_text(text):
    # Source captions retain emojis in evidence.json. Arial cannot render these
    # reliably in a portable PDF, so omit decorative pictograms in both exports.
    return re.sub(r'[\U0001f000-\U0001ffff\u2600-\u27bf\ufe0f\u200d]', '', str(text))


def make_pages(data):
    bs = data['profiles']; top, trend = bs[:10], bs[10:]
    pages = []
    recent_names = lambda seq: ', '.join(b['name'] for b in seq if b['recent'])
    nfb = lambda seq: sum(bool(b['fb']) for b in seq)
    napp = lambda seq: sum(bool(b['app']) for b in seq)
    nrecent = lambda seq: sum(bool(b['recent']) for b in seq)
    pages.append([
      ('cover', 'ĐỐI THỦ ĐANG\nQUẢNG CÁO NHƯ THẾ NÀO?'),
      p('Ngành chứng khoán | Top 10 và nhóm xu hướng | Dữ liệu tham chiếu 29/10/2026'),
      h('1. Những điều cần nắm trước'),
      table(['Câu hỏi', 'Trả lời từ dữ liệu'],[
        ['Top 10 có ai chạy Facebook?', f"{nfb(top)}/10 công ty: "+', '.join(b['name'] for b in top if b['fb'])+'.'],
        ['Top 10 có ai quảng bá app trên Google?', f"{napp(top)}/10 từng có mẫu mang nhãn Play; {nrecent(top)}/10 có hiển thị trong 3 ngày gần mốc tham chiếu: {recent_names(top)}."],
        ['Nhóm xu hướng có gì đáng chú ý?', f"{nfb(trend)}/15 có Facebook; {napp(trend)}/15 có Google App trong lịch sử; {nrecent(trend)}/15 hiển thị gần đây: {recent_names(trend)}."],
      ], [46, 125]),
      h('Ba cách tiếp cận nổi bật'),
      p('Ưu đãi để thúc đẩy hành động: SSI, MBS, KIS và LPS dùng quà, phí hoặc margin làm lý do mở tài khoản/trải nghiệm. Điểm đến có thể là app hoặc trang chương trình.'),
      p('Tính năng để tạo lý do lựa chọn: VNDirect giới thiệu thao tác DTRADE; DNSE dùng API/MCP và lợi ích tiền nhàn rỗi; Shinhan giới thiệu VinaStalk và AI.'),
      p('Kiến thức để mở đầu quan hệ: VPS dùng series Direct Indexing, MBS có chuyên viên chia sẻ, HSC quảng bá sự kiện, HD Securities giải thích vấn đề của người mới.'),
      p('Hàm ý: khi xem đối thủ, cần đọc cả chuỗi nội dung → CTA → điểm đến. Chỉ đếm video hoặc số quảng cáo sẽ bỏ qua cách họ dẫn người xem đến bước tiếp theo.'),
      ('note', 'Google App trong tài liệu = mẫu ảnh/video có nhãn Play, là dấu hiệu quảng bá app. Chưa xác nhận campaign type hay mục tiêu tối ưu. Số liệu này phản ánh bộ dữ liệu đã lưu, không phải toàn bộ thị trường.'),
    ])
    pages.append([
      h('2. Top 10: ai có mặt trên từng kênh?'),
      table(['Công ty', 'Facebook\nSố QC / mẫu', 'Google App', 'Cách làm nổi bật'], [
        [b['name'], f"{len(b['fb'])} / {b['designs']}" if b['fb'] else 'Chưa thấy', status_app(b), b['title']] for b in top
      ], [24, 29, 43, 75]),
      p('“Mẫu” trên Facebook là nhóm thiết kế theo asset_id, có thể gồm nhiều biến thể; “QC” là ad ID. DCO là cách đóng gói nội dung động, chưa đủ để gọi là ảnh hay video.'),
      h('Đọc đúng các trạng thái'),
      p('Facebook: quảng cáo được ghi nhận hoạt động trong cache. Google “gần đây”: lần hiển thị cuối cách mốc 29/10/2026 14:29 dưới 3 ngày. “Chỉ lịch sử”: có bằng chứng cũ nhưng không đạt điều kiện gần đây; không kết luận công ty đã dừng kênh.'),
      p('TCBS có dữ liệu Google Search, HSC và VNDirect có quảng cáo Google khác nhưng chưa thấy mẫu App. VPS cũng có Google ngoài App. MBS và Mirae Asset chưa có tài khoản Google trong danh sách nguồn đã lưu.'),
      p('Phần đọc nhanh: trang 1–4. Hồ sơ Top 10: trang 5–14. Nhóm xu hướng và phương pháp nằm ở phần sau. Các liên kết dưới mỗi mẫu mở bằng chứng gốc.'),
    ])

    # Format and destination prevalence is exhaustive for exported Meta rows.
    fmt_categories = [
       ('Ảnh đơn', lambda r:r['format']=='Ảnh đơn'),
       ('Video xác định trong CSV', lambda r:r['format']=='Video'),
       ('Carousel / nhiều ảnh', lambda r:r['format'] in ('Carousel','Nhiều ảnh')),
       ('DCO — chưa tách loại media', lambda r:r['format']=='Dynamic (DCO)'),
    ]
    def prevalence(seq, fn):
        active = [b for b in seq if b['fb']]
        return f"{sum(any(fn(r) for r in b['fb']) for b in active)}/{len(active)}"
    format_rows = [[label, prevalence(top, fn), prevalence(trend, fn),
                   str(sum(fn(r) for b in bs for r in b['fb']))] for label, fn in fmt_categories]
    destination_rows=[]
    for label in ['Kho ứng dụng / mở app','Web có form (chưa xác nhận mục đích)',
                  'Web nội dung / sản phẩm / sự kiện','Facebook / sự kiện','Messenger']:
        fn=lambda r, label=label: dest(r)==label
        destination_rows.append([label,prevalence(top,fn),prevalence(trend,fn)])
    app_formats=Counter(r['format'] for b in bs for r in b['app'])
    pages.append([
      h('3. Quy luật về format, kênh và điểm đến'),
      p('Mẫu số dưới đây là số công ty có Facebook: 7 Top 10 và 15 nhóm xu hướng. Một công ty có thể dùng nhiều loại nên các dòng không cộng thành 100%.'),
      table(['Dạng asset Facebook', 'Top 10', 'Xu hướng', 'Số QC\nhai nhóm'],format_rows,[70,29,32,40]),
      p('Ảnh và video cùng xuất hiện; DCO phải được giữ riêng. Không dùng nhãn DCO để khẳng định một công ty chủ yếu chạy video. Tỷ lệ khung và độ dài chỉ được nêu khi có file hoặc metadata đã xác minh.'),
      table(['Đường đi từ Facebook', 'Top 10', 'Xu hướng'],destination_rows,[109,31,31]),
      p('Đây là điểm đến của URL/nút CTA được lưu, không phải toàn bộ đường đi của người dùng. Web có form có thể là form đăng ký hoặc thành phần phụ; cần đọc nội dung từng trang trước khi gọi là mở tài khoản.'),
      h('Google App: có phân phối, chưa chắc xem được nội dung'),
      p(f"Trong hai nhóm có {data['totals']['google_app']} bản ghi có dấu hiệu quảng bá app, {data['totals']['google_app_recent']} hiển thị gần đây. Định dạng ghi nhận: {', '.join(f'{k}: {v}' for k,v in app_formats.items())}. Có {data['totals']['google_app_missing_id']} bản ghi video chưa lấy được YouTube ID; không dùng số còn lại để đại diện toàn bộ nội dung Google App."),
      p('Ví dụ cần phân biệt: LPS có 12 bản ghi Google App gần đây nhưng đều thiếu ID video. Có thể xác nhận sự hiện diện từ metadata; chưa thể khẳng định Google dùng lại video tải app đã xem trên Facebook.'),
    ])
    themes=['Ưu đãi / chi phí','Tính năng / sản phẩm','Kiến thức / phân tích','Uy tín / cộng đồng','Tò mò / cá nhân hóa']
    theme_rows=[]
    for theme in themes:
        names=[b['name'] for b in bs if theme in b['themes']]
        theme_rows.append([theme, f"{sum(theme in b['themes'] for b in top)}/7",
                           f"{sum(theme in b['themes'] for b in trend)}/15", ', '.join(names)])
    pages.append([
      h('4. Quy luật nội dung và tổ hợp triển khai'),
      p('Đếm số công ty có ít nhất một caption đại diện đã đối chiếu trong hồ sơ; đây là mức hiện diện tối thiểu, không phải tỷ trọng toàn bộ quảng cáo. Chủ đề có thể chồng lấp; một mẫu được gắn tối đa các chủ đề có bằng chứng rõ.'),
      table(['Góc nội dung', 'Top 10', 'Xu hướng', 'Công ty có ví dụ xác nhận'],theme_rows,[38,20,23,90]),
      h('Các tổ hợp cụ thể đã quan sát'),
      table(['Tổ hợp', 'Ví dụ / ý nghĩa'],[
        ['Ưu đãi → kho ứng dụng', 'LPS, MBS: lời mời nhận lợi ích kết thúc ở kho ứng dụng hoặc mở app.'],
        ['Ưu đãi → web chương trình / onboarding', 'KIS, SSI, VPBankS: người xem được dẫn qua trang giải thích hoặc đăng ký.'],
        ['Tính năng → web sản phẩm', 'VNDirect, DNSE, AAS: giải thích lý do sử dụng rồi dẫn về sản phẩm/tài liệu.'],
        ['Kiến thức → theo dõi / sự kiện', 'VPS, HSC, HD Securities: dùng nội dung giải thích hoặc chuyên gia để mở đầu quan hệ.'],
        ['Video Google App → lợi ích / uy tín / ưu đãi', 'DNSE: demo lợi ích; ABS: giải thưởng; SSI: quà cổ phiếu. Nhãn App không quyết định góc nội dung.'],
      ],[66,105]),
      p('Riêng nội dung quy trình: video DNSE có minh họa thao tác trong app. Video hướng dẫn mở tài khoản SSI iBoard Pro đã khảo sát nằm ở nhóm YouTube không mang nhãn Play, nên chỉ dùng làm bối cảnh và không tính vào Google App. Chưa đủ video được xem để xếp hạng mức phổ biến của hướng dẫn từng bước.'),
      p('Quy luật có cơ sở: ưu đãi, tính năng và kiến thức là ba nhóm cách tiếp cận lặp lại ở nhiều công ty; điểm đến thay đổi theo nội dung. Giả thuyết nên thử: cùng một lợi ích, so demo thao tác với thông điệp ưu đãi ngắn. Bộ dữ liệu chưa cho biết cách nào có CPA hoặc chất lượng khách tốt hơn.'),
    ])

    def profile_blocks(b, compact=False):
        fr, ar=b['fb'],b['app']
        blocks=[h(f"{b['name']} | {b['title']}"),
          p(f"Facebook: {len(fr)} QC / {b['designs']} nhóm thiết kế. Google App: {len(ar)} bản ghi; {len(b['recent'])} gần đây."),
          p(b['analysis'])]
        if fr:
            blocks += [p('Asset Facebook: '+counts(fr,'format')+'.'),
              p('Điểm đến Facebook: '+', '.join(f'{k}: {v}' for k,v in Counter(dest(r) for r in fr).most_common())+'.')]
        if ar:
            missing=sum(r['format']=='Video' and not r['youtube_id'] for r in ar)
            last=max(r['last_shown'] for r in ar)
            blocks.append(p(f"Google App: {counts(ar,'format')}; {missing}/{len(ar)} bản ghi thiếu ID video. Lần hiển thị cuối trong dữ liệu: {last}. URL đích click không có trong bộ xuất Google; chưa xác minh app store hay landing."))
        selected=b['selected'][:1 if compact else 2]
        for i,r in enumerate(selected):
            body=r['body'].replace('\\n',' ').replace('\n',' ')
            excerpt=body[:175].rsplit(' ',1)[0]+'…' if len(body)>175 else body
            blocks.append(p(f"Mẫu Facebook {i+1} | {r['format']} | {excerpt}"))
            blocks.append(link('Bằng chứng quảng cáo Facebook · '+r['ad_archive_id'],r['library_link']))
            url=r['final_url'] or r['link_url']
            if url.startswith(('http://','https://')):
                label='URL cuối đã lưu' if r['final_url'] else 'URL quảng cáo (chưa có URL cuối)'
                blocks.append(link(label,url))
        if len(b['selected']) > len(selected):
            for r in b['selected'][len(selected):]:
                blocks.append(link('Ví dụ Facebook bổ sung · '+r['ad_archive_id'],r['library_link']))
        # Use verified storyboard only; otherwise the snapshot thumbnail is an
        # ad preview, explicitly not evidence of video choreography.
        if not compact:
            pack=next((x for x in b['meta_packs'] if x['rank'] in (2,3,9,10,11)),None)
            if pack:
                path=ROOT/pack['folder']/'storyboard.jpg'
                if path.exists():
                    blocks.append(image(str(path.relative_to(ROOT)),
                        f"Storyboard video đã đối chiếu · {pack.get('video_duration','?')} giây · {pack.get('aspect','chưa rõ tỷ lệ')} · gói #{pack['rank']}",145,90))
            elif selected and selected[0]['image_local']:
                blocks.append(image(selected[0]['image_local'],'Ảnh xem trước mẫu Facebook 1; không xác nhận đây là toàn bộ asset.',70))
        # Google examples must belong to this profile AND the App subset.
        gp=next((x for x in b['google_packs'] if x['rank'] in (3,4,6,9)),None)
        if gp and not compact:
            descriptions={3:'Video giải thưởng: cúp và chữ giải thưởng, kết bằng QR “Trải nghiệm ngay”.',
               4:'Video “hạt giống tích sản”: bối cảnh đồi chè, ba quyền lợi, CTA mở tài khoản; không phải demo quy trình.',
               6:'Video “Tài khoản không ngủ”: hỏi về tiền nhàn rỗi → lợi ích → giao diện → end card tải Entrade X.',
               9:'Video ưu đãi iKIS: liệt kê lý do lựa chọn, kết bằng lời mời mở app. Đây là tư liệu lịch sử.'}
            blocks.append(p('Mẫu Google App đã khảo sát: '+descriptions[gp['rank']]))
            blocks.append(link('Bằng chứng Google App · '+gp['video_title'],gp['transparency_links'][0]))
        elif ar:
            example=(b['recent'] or ar)[0]
            blocks.append(link('Bằng chứng Google App · '+example['creative_id'],example['link']))
        if not fr and not ar:
            blocks.append(link('Fanpage đã kiểm tra',f"https://www.facebook.com/{b['page_id']}"))
        return blocks

    for b in top:
        pages.append(profile_blocks(b))
    # Two short profiles per page; keep trend group compact for executive readers.
    for i in range(0,len(trend),2):
        page=[h('Nhóm xu hướng | Các cách làm bổ sung')]
        for b in trend[i:i+2]:
            page += profile_blocks(b,compact=True)
            # Add one verified Google storyboard to the DNSE/ABS spread only
            # through textual evidence to retain a concise, stable page layout.
        pages.append(page)

    for name,rank,desc in [
        ('SSI',4,'Ưu đãi cổ phiếu và lời mời mở tài khoản; chữ/motion thay cho hướng dẫn từng bước.'),
        ('DNSE',6,'Nỗi đau tiền nhàn rỗi → lợi ích → minh họa giao diện → tải app.'),
        ('ABS',3,'Giải thưởng → thông điệp uy tín → QR trải nghiệm. Không phải mọi mẫu quảng bá app đều nói về quà.'),
    ]:
        b=next(b for b in bs if b['name']==name)
        pack=next(x for x in b['google_packs'] if x['rank']==rank)
        path=ROOT/pack['folder']/'storyboard.jpg'
        pages.append([h('Phụ lục | Mẫu Google App đã xem: '+name),p(desc),
           p('Video có liên hệ xác minh với creative mang nhãn Play. Hình dưới là các khung hình theo thứ tự, không phải nhiều quảng cáo riêng.'),
           image(str(path.relative_to(ROOT)),f"{pack['video_duration']} giây · {pack['aspect']} · lần cuối {pack['last_shown']}",165,180),
           link('Xem quảng cáo trên Google Transparency',pack['transparency_links'][0])])

    pages.append([
      h('Phương pháp, nguồn và giới hạn'),
      p('Phạm vi: danh sách Top 10 và 15 công ty nhóm xu hướng trong competitors.txt. Đối chiếu google_competitors.txt để gộp nhiều advertiser ID của cùng công ty. Nhóm “Chỉ thấy trên Google” được loại khỏi các mẫu số; không tự bổ sung hoặc xếp hạng lại Top 10.'),
      p('Nguồn chính: all_ads.csv; pages/*.json; google_all_ads.csv; google/AR*.json; landing/landings.json; report_snapshot.json. Bộ winners và winners_google cung cấp storyboard, transcript, metadata và ghi chép xem nội dung. Dữ liệu gốc và các báo cáo trước giữ nguyên.'),
      p('Mốc tham chiếu: 29/10/2026 14:29, múi giờ Việt Nam. Đây là mốc tính trạng thái, không xác nhận tất cả tài khoản được crawl cùng thời điểm. Không truy cập lại nền tảng hoặc cập nhật ưu đãi trong lần lập báo cáo này.'),
      p('Đếm Facebook: một ad_archive_id là một quảng cáo; một asset_id là một nhóm thiết kế theo bộ xuất hiện có. Không lấy collation_count làm số bản thực tế; không gộp các DCO khác hình chỉ vì caption placeholder trùng nhau. Số nhóm không xác nhận số concept hoặc số video hoàn toàn khác nhau.'),
      p('Google App: định dạng không phải chữ và nhãn nền tảng có Play. Một creative_id dưới một advertiser là một bản ghi. Nhãn Play không cho biết mục tiêu cài app, tương tác lại hay campaign type. Các nền tảng đi kèm cũng không cho biết tỷ trọng ngân sách từng kênh.'),
      p('Nội dung: bảng chủ đề là mã hóa thủ công ở cấp công ty, dựa trên caption đại diện có ad ID lưu trong evidence.json. Chỉ thể hiện sự có mặt của chủ đề trong các ví dụ, không phải một phân loại bao phủ toàn bộ caption. Quy trình thao tác app chỉ mô tả khi đã xem được bước thực tế; CTA “mở tài khoản” tự nó chưa phải hướng dẫn quy trình.'),
      p('Giới hạn media: loại khỏi diễn giải video các gói Meta DCO #1, #5, #7, #8 có trạng thái unresolved_dynamic_media. Thiếu YouTube ID không có nghĩa quảng cáo không có video. Không dùng mẫu đã xem để tuyên bố thị trường chưa có một cách làm nào.'),
      p('Điểm đến: ưu tiên URL cuối đã lưu; nếu chỉ có URL đầu thì ghi rõ. Redirect về Facebook hoặc lỗi truy cập chưa xác nhận đích sản phẩm. CTA/QR trong video và đường dẫn click là hai loại bằng chứng khác nhau. Google không có URL đích click trong bộ xuất, nên không tự gán là app store.'),
      p('Diễn giải: không có ngân sách, impressions, click, CPA hoặc chuyển đổi. “Phổ biến” là hiện diện trong mẫu quan sát, không có nghĩa hiệu quả. Thời gian xuất hiện và số bản không chứng minh chạy liên tục, tăng ngân sách hoặc thắng thử nghiệm. Mọi ưu đãi được trích là nội dung lịch sử của quảng cáo, không xác nhận còn hiệu lực.'),
      p('Tệp kiểm chứng đi kèm: evidence.json chứa số liệu và ad ID; source_manifest.json chứa SHA-256 nguồn đầu vào. Tái tạo bằng build_executive_report.py với python-docx, reportlab, Pillow và pypdf.'),
    ])
    return pages


def docx_link(paragraph,label,url):
    hyperlink=OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'),paragraph.part.relate_to(url,RT.HYPERLINK,is_external=True))
    run=OxmlElement('w:r'); prop=OxmlElement('w:rPr')
    color=OxmlElement('w:color');color.set(qn('w:val'),'136A80');prop.append(color)
    sz=OxmlElement('w:sz');sz.set(qn('w:val'),'18');prop.append(sz)
    run.append(prop);t=OxmlElement('w:t');t.text=label;run.append(t)
    hyperlink.append(run);paragraph._p.append(hyperlink)


def render_docx(pages,path):
    doc=Document(); sec=doc.sections[0]
    sec.page_width=Mm(210);sec.page_height=Mm(297)
    sec.top_margin=Mm(16);sec.bottom_margin=Mm(17)
    sec.left_margin=Mm(19);sec.right_margin=Mm(19)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(10)
    normal.paragraph_format.space_after=Pt(6)
    normal.paragraph_format.line_spacing=1.12
    for name,size in [('Title',26),('Heading 1',16),('Heading 2',12)]:
        style=doc.styles[name];style.font.name='Arial';style.font.size=Pt(size)
        style.font.color.rgb=RGBColor.from_string('123D50')
    sec.header.paragraphs[0].text='CHỨNG KHOÁN  /  QUẢNG CÁO ĐỐI THỦ  /  29.10.2026'
    sec.header.paragraphs[0].style=doc.styles['Caption']
    footer=sec.footer.paragraphs[0];footer.text='Dữ liệu quan sát · Không phải xếp hạng hiệu quả     |     '
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
    for pi,page in enumerate(pages):
        if pi:doc.add_page_break()
        for item in page:
            kind=item[0]
            if kind=='cover':doc.add_paragraph(display_text(item[1]),style='Title')
            elif kind=='h':doc.add_heading(display_text(item[1]),level=2 if ' | ' in item[1] else 1)
            elif kind in ('p','note'):
                para=doc.add_paragraph(display_text(item[1]));
                if kind=='note':
                    for r in para.runs:r.italic=True;r.font.size=Pt(9)
            elif kind=='link':
                para=doc.add_paragraph();para.paragraph_format.space_after=Pt(3)
                docx_link(para,item[1],item[2])
            elif kind=='image':
                file=ROOT/item[1]
                if not file.exists():raise ValueError(f'Missing image: {file}')
                with PILImage.open(file) as im: iw, ih = im.size
                picture_width = min(item[3], item[4] * iw / ih)
                doc.add_picture(str(file),width=Mm(picture_width))
                doc.add_paragraph(item[2],style='Caption')
            elif kind=='table':
                _,headers,rows,widths=item
                tab=doc.add_table(rows=1,cols=len(headers));tab.style='Light Shading Accent 1'
                tab.autofit=False
                for row,values in [(tab.rows[0],headers)]+[(tab.add_row(),values) for values in rows]:
                    trpr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
                    for j,(cell,value) in enumerate(zip(row.cells,values)):
                        cell.text=display_text(value)
                        if widths:cell.width=Mm(widths[j])
                        for para in cell.paragraphs:
                            para.paragraph_format.space_after=Pt(4)
                            for run in para.runs:run.font.size=Pt(9)
                if widths:
                    for col,w in zip(tab.columns,widths):col.width=Mm(w)
                prop=tab.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');prop.append(repeat)
                doc.add_paragraph().paragraph_format.space_after=Pt(1)
    doc.core_properties.title='Báo cáo quảng cáo đối thủ chứng khoán – 29/10/2026'
    doc.core_properties.subject='Top 10 và nhóm xu hướng; Facebook và Google quảng bá app'
    doc.save(path)


def render_pdf(pages,path):
    fontdir=Path('/System/Library/Fonts/Supplemental')
    pdfmetrics.registerFont(TTFont('ArialVN',str(fontdir/'Arial.ttf')))
    pdfmetrics.registerFont(TTFont('ArialVNBold',str(fontdir/'Arial Bold.ttf')))
    pdfmetrics.registerFontFamily('ArialVN',normal='ArialVN',bold='ArialVNBold',italic='ArialVN',boldItalic='ArialVNBold')
    styles={
      'p':ParagraphStyle('body',fontName='ArialVN',fontSize=9.5,leading=13.6,spaceAfter=6,textColor=colors.HexColor('#223945')),
      'h':ParagraphStyle('heading',fontName='ArialVNBold',fontSize=14,leading=18,spaceBefore=8,spaceAfter=8,textColor=colors.HexColor('#123D50')),
      'cover':ParagraphStyle('cover',fontName='ArialVNBold',fontSize=25,leading=30,spaceBefore=15,spaceAfter=18,textColor=colors.HexColor('#123D50')),
      'cell':ParagraphStyle('cell',fontName='ArialVN',fontSize=8.5,leading=11,spaceAfter=0),
      'th':ParagraphStyle('th',fontName='ArialVNBold',fontSize=8.5,leading=11,textColor=colors.white),
      'caption':ParagraphStyle('caption',fontName='ArialVN',fontSize=8,leading=10,spaceAfter=7,textColor=colors.HexColor('#59727C')),
    }
    def para(s,style='p'):return Paragraph(escape(display_text(s)).replace('\n','<br/>'),styles[style])
    story=[]
    for pi,page in enumerate(pages):
        if pi:story.append(PageBreak())
        for item in page:
            kind=item[0]
            if kind in ('p','h','cover'):story.append(para(item[1],kind))
            elif kind=='note':story.append(para(item[1],'caption'))
            elif kind=='link':
                story.append(Paragraph(f'<link href="{escape(item[2], {chr(34): "&quot;"})}" color="#136A80">{escape(item[1])}</link>',styles['caption']))
            elif kind=='image':
                file=ROOT/item[1]
                with PILImage.open(file) as im:w,hg=im.size
                width=min(item[3]*mm,171*mm);height=width*hg/w
                # Contact sheets can be tall: cap and preserve aspect ratio.
                if height>item[4]*mm:width*=item[4]*mm/height;height=item[4]*mm
                img=Image(str(file),width=width,height=height);img.hAlign='LEFT'
                story.append(KeepTogether([img,para(item[2],'caption')]))
            elif kind=='table':
                _,headers,rows,widths=item
                vals=[[para(v,'th') for v in headers]]+[[para(v,'cell') for v in row] for row in rows]
                tab=Table(vals,colWidths=[w*mm for w in widths] if widths else None,repeatRows=1,hAlign='LEFT')
                tab.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#123D50')),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#EDF3F5'),colors.white]),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),
                    ('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),
                    ('BOTTOMPADDING',(0,0),(-1,-1),6),
                    ('LINEBELOW',(0,0),(-1,0),0.5,colors.HexColor('#123D50')),
                ]));story += [tab,Spacer(1,7)]
    def decorate(canvas,doc):
        canvas.setFont('ArialVN',8);canvas.setFillColor(colors.HexColor('#59727C'))
        canvas.drawString(19*mm,286*mm,'CHỨNG KHOÁN  /  QUẢNG CÁO ĐỐI THỦ  /  29.10.2026')
        canvas.drawString(19*mm,10*mm,'Dữ liệu quan sát · Không phải xếp hạng hiệu quả')
        canvas.drawRightString(191*mm,10*mm,str(doc.page))
    pdf=SimpleDocTemplate(str(path),pagesize=(210*mm,297*mm),rightMargin=19*mm,leftMargin=19*mm,
        topMargin=19*mm,bottomMargin=18*mm,title='Báo cáo quảng cáo đối thủ chứng khoán – 29/10/2026',author='')
    pdf.build(story,onFirstPage=decorate,onLaterPages=decorate)


def validate(data,pages,pdf_path,docx_path):
    from pypdf import PdfReader
    bs=data['profiles']
    assert len(bs)==25 and len({b['page_id'] for b in bs})==25
    assert sum(len(b['fb']) for b in bs)==844
    assert sum(bool(b['fb']) for b in bs[:10])==7
    assert sum(bool(b['recent']) for b in bs[:10])==2
    assert sum(bool(b['app']) for b in bs[:10])==4
    assert all(app_row(r) for b in bs for r in b['app'])
    raw_google = {}
    for path in (PROJ/'google').glob('AR*.json'):
        for r in json.loads(path.read_text()):
            key=(r['advertiser_id'],r['creative_id'])
            raw_google[key]=r
    seen=set()
    for b in bs:
        for r in b['google']:
            key=(r['advertiser_id'],r['creative_id'])
            assert key not in seen,('Duplicate Google creative',key)
            seen.add(key)
            original=raw_google[key]
            assert r['platforms']==original['platforms']
            assert r['format']==original['format']
            recent=dt.datetime.fromisoformat(REFERENCE).timestamp()-original['last_ts']<3*86400
            assert (r['active']=='True')==recent,('Google status differs from reference clock',key)
    for b in bs:
        ids={r['ad_archive_id'] for r in b['fb']}
        assert all(aid in ids for aids in b['themes'].values() for aid in aids)
        for pack in b['google_packs']:
            assert any(r['youtube_id'].rsplit('/',1)[-1]==pack['youtube'].rsplit('/',1)[-1] for r in b['app'])
    pdf=PdfReader(str(pdf_path))
    text='\n'.join(page.extract_text() for page in pdf.pages)
    assert all(b['name'] in text for b in bs)
    assert len(pdf.pages)==len(pages),(len(pdf.pages),len(pages),'Unplanned PDF page overflow')
    assert 'ĐỐI THỦ ĐANG' in text and '\ufffd' not in text and '\x00' not in text
    import zipfile
    with zipfile.ZipFile(docx_path) as z:
        xml=z.read('word/document.xml').decode()
        assert all(escape(b['name']) in xml for b in bs)
    return dict(profiles=len(bs),totals=data['totals'],
                pdf_pages=len(pdf.pages),planned_pages=len(pages),
                pdf_external_links=sum(len(page.get('/Annots',[])) for page in pdf.pages),
                checks='All evidence, identity, scope, PDF pagination and Vietnamese text checks passed')


def main():
    OUT.mkdir(exist_ok=True)
    # No user writing samples were suitable for verified authorship in the
    # connected recent-document metadata; use the requested direct report style.
    data=build_data();pages=make_pages(data)
    pdf=OUT/f'{STEM}.pdf';docx=OUT/f'{STEM}.docx'
    render_docx(pages,docx);render_pdf(pages,pdf)
    result=validate(data,pages,pdf,docx)
    (OUT/'evidence.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    sources=[PROJ/'all_ads.csv',PROJ/'google_all_ads.csv',PROJ/'report_snapshot.json',
        PROJ/'competitors.txt',PROJ/'google_competitors.txt',PROJ/'landing/landings.json']
    sources += list((PROJ/'pages').glob('*.json'))+list((PROJ/'google').glob('AR*.json'))
    sources += list((PROJ/'winners').glob('*/meta.json'))+list((PROJ/'winners_google').glob('*/meta.json'))
    sources += [PROJ/'winners/observations.md',PROJ/'winners_google/observations.md',Path(__file__).resolve()]
    sources += [ROOT/item[1] for page in pages for item in page if item[0]=='image']
    manifest={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(set(sources))}
    (OUT/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
