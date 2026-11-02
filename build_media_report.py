"""Create the illustrated report, editable deck and portable media bundle.

Uses the frozen 29 October snapshot only. Existing source reports are untouched.
Dependencies: build_executive_report dependencies, matplotlib, python-pptx,
PyMuPDF (verification), and ffprobe (video validation).
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import build_executive_report as base

ROOT, PROJ = base.ROOT, base.PROJ
OUT = PROJ/'bao-cao-media'
ASSETS = OUT/'media'
CHARTS = OUT/'charts'
STEM = 'Doi_thu_chung_khoan_media_29-10-2026'
# DSC design system (https://claude.ai/artifact/22k27xbh7rBryUcMrDZoH4): Plus Jakarta Sans,
# Gunmetal ink on white, square blocks, hairline dividers. Brand green only for accents/charts;
# text on Lime/Emerald is always Gunmetal; brand-coloured text uses Pine Teal (accent-text).
FONT = ROOT/'fonts/PlusJakartaSans-Regular.ttf'
SEMI = ROOT/'fonts/PlusJakartaSans-SemiBold.ttf'
BOLD = ROOT/'fonts/PlusJakartaSans-Bold.ttf'
FAMILY = 'Plus Jakarta Sans'
GUNMETAL, PINE, LIME, EMERALD, MINT = '#272D2B', '#1D4130', '#2AD03D', '#1BBE72', '#8CFFCC'
SURFACE_ALT, MUTED, LINE, ON_DARK_MUTED, MINT_50 = '#F3F4F4', '#5B6260', '#DFE0E0', '#B3B9B7', '#EAFFF4'
INK, ACCENT = GUNMETAL, PINE
SERIES_A, SERIES_B = PINE, EMERALD   # differ in lightness, not hue only
STRIP = [(GUNMETAL, 3), (PINE, 2), (LIME, 4.5), (EMERALD, 2.5), (MINT, 2.5)]
TITLE = 'Quảng cáo đối thủ chứng khoán · Snapshot 29/10/2026'

# Source-specific descriptions, separate from quantities derived from CSV.
VIDEO_NOTES = {
 ('Meta',2): ('SSI | Quiz phong cách đầu tư',
   'Tò mò về bản thân → quiz → ưu đãi mở tài khoản',
   'Motion chữ và huy hiệu mô tả các kiểu nhà đầu tư; mời làm bài test để khám phá phong cách.',
   'Lợi ích tương tác xuất hiện trước; ưu đãi mở tài khoản là bước tiếp theo. CTA trong clip là làm test.'),
 ('Meta',3): ('HD Securities | Cần bao nhiêu tiền để đầu tư?',
   'Câu hỏi của người mới → giải thích bằng ví dụ → theo dõi',
   'Hoạt hình, chữ và giọng đọc giải thích quy mô vốn cần để bắt đầu, dùng ví dụ phép tính.',
   'Nội dung gỡ rào cản nhận thức. Chưa có URL đích CTA xác minh trong bản ghi; không gán là cài app.'),
 ('Meta',4): ('HD Securities | Xanh chỉ số, đỏ tài khoản',
   'Hiện tượng quen thuộc → giải thích chỉ số → kiến thức',
   'Template chữ/hoạt hình và giọng đọc diễn giải hiện tượng chỉ số tăng nhưng nhiều cổ phiếu giảm.',
   'Đặt vấn đề gần trải nghiệm người xem, cung cấp lời giải trước khi yêu cầu hành động.'),
 ('Meta',6): ('SSI | Quà cổ phiếu PAN',
   'Quà cụ thể → mở tài khoản online → CTA',
   'Motion với thông điệp mở tài khoản và nhận cổ phiếu; dùng yếu tố đồng thương hiệu PAN.',
   'Caption và clip nói về ưu đãi. Dòng hạn 31/05 là nội dung lịch sử, không xác nhận ưu đãi còn hiệu lực.'),
 ('Meta',9): ('LPS | Tải một app, nhiều quyền lợi',
   'Tải app → chồng nhiều quà và lợi ích → mở tài khoản',
   'Điện thoại, chữ ưu đãi lớn và giọng đọc; kết hợp cổ phiếu, phí, margin và khóa học.',
   'Một lời mời được hỗ trợ bằng nhiều quyền lợi. Không suy ra số bản quảng cáo là số concept mới.'),
 ('Meta',10): ('MBS | Chuyên viên giải thích breakout',
   'Kiến thức giao dịch → chuyên viên giải thích → ưu đãi',
   'Người thật nói trước camera, phụ đề và minh họa; giới thiệu dấu hiệu breakout trước khi chèn mở tài khoản.',
   'Ví dụ rõ về cách dùng kiến thức làm phần mở đầu rồi mới chuyển sang ưu đãi. URL đích thuộc luồng app.'),
 ('Meta',11): ('VPS | Lợi ích của Direct Indexing',
   'Câu hỏi → lợi ích → các điều cần lưu ý',
   'Chữ động, minh họa và giọng đọc về tích sản dài hạn; có phần lưu ý thay vì chỉ liệt kê lợi ích.',
   'Vai trò quan sát được là giải thích sản phẩm/kiến thức. Không có URL đích CTA xác minh.'),
 ('Meta',12): ('VPS | Direct Indexing là gì?',
   'Giải nghĩa khái niệm → ví dụ danh mục → tìm hiểu',
   'Video cùng series tích sản dài hạn, giải thích khái niệm bằng chữ và minh họa.',
   'CTA trong metadata không đủ chứng minh điểm đến. Bộ dữ liệu chưa có URL đích xác minh cho mẫu này.'),
 ('Google App',3): ('ABS | Video giải thưởng',
   'Giải thưởng → uy tín → QR trải nghiệm',
   'Cúp vàng, chữ giải thưởng, nền tím và end card có QR; nội dung tạo lý do tin tưởng thương hiệu.',
   'Có creative mang nhãn Play. QR trong video chưa xác nhận URL đích click của quảng cáo.'),
 ('Google App',4): ('SSI | Hạt giống tích sản',
   'Bối cảnh tích sản → quà cổ phiếu → mở tài khoản',
   'Đồi chè, bình minh, ba quyền lợi và CTA mở tài khoản; nhấn mạnh quà và tích sản dài hạn.',
   'Đây là video ưu đãi, không phải hướng dẫn từng bước. Chỉ các creative mang Play được tính vào Google App.'),
 ('Google App',6): ('DNSE | Tài khoản không ngủ',
   'Tiền nhàn rỗi → lợi ích → giao diện → tải app',
   'Giọng đọc đặt câu hỏi, minh họa lợi ích và giao diện; cuối clip có Entrade X, App Store và Google Play.',
   'Demo giúp làm rõ sản phẩm hoạt động ra sao. Thông số trong video là nội dung lịch sử; chưa có URL đích click.'),
 ('Google App',8): ('KIS | Chào bạn mới',
   'Quà mở tài khoản → giao diện iKIS → CTA',
   'Video ngắn dùng con số quà lớn, chữ chuyển động và hình app để mời người mới mở tài khoản.',
   'Chỉ có bằng chứng lịch sử theo snapshot; không gọi mẫu này là đang chạy gần ngày chốt.'),
 ('Google App',9): ('KIS | Ba lý do trải nghiệm iKIS',
   'Liệt kê quyền lợi → ưu đãi/giới thiệu → mở app',
   'Bố cục đánh số các lý do, ghép quà mở tài khoản, lựa chọn giao dịch và giới thiệu bạn bè.',
   'Một video gói nhiều lý do lựa chọn. Đây là tư liệu lịch sử trong nhóm có dấu hiệu quảng bá app.'),
 ('YouTube tham khảo',2): ('SSI | Hướng dẫn mở tài khoản',
   'Tải app → thông tin/OTP → xác thực → hoàn tất',
   'Quay/minh họa giao diện app với các bước đánh số và chữ hướng dẫn; đây là mẫu quy trình thao tác cụ thể.',
   'Không mang nhãn Play trong bản ghi. Dùng tham khảo cách làm content; không cộng vào số liệu Google App.'),
 ('YouTube tham khảo',11): ('Vietcap | Demo lợi ích Vietcap IQ',
   'Khó khăn đọc dữ liệu → công cụ → các tính năng',
   'Người thật kết hợp overlay dữ liệu và giao diện, giới thiệu bộ lọc, dữ liệu và nhận định.',
   'Video này thuộc YouTube ngoài App. Không dùng nó để thay thế nội dung video App Vietcap đang thiếu ID.'),
}


TERMS=[('mẫu Google App','mẫu Google Ads (app)'),('Video Google App','Video Google Ads (app)'),('Google App','Google Ads (app)'),
       ('nhóm xu hướng','nhóm ngoài Top 10'),('gói Meta DCO','gói Facebook Ads DCO')]
def terms(s):
    for a,b in TERMS:s=s.replace(a,b)
    return s
def clean(s): return terms(base.display_text(s).replace('\\n','\n').replace('↗','').strip())
def short(s,n):
    s=' '.join(clean(s).split())
    return s if len(s)<=n else s[:n].rsplit(' ',1)[0]+'…'
def rel(path): return str(Path(path).relative_to(ROOT))
def slug(s): return re.sub(r'[^a-z0-9]+','_',base.fold(s)).strip('_')


def copy_asset(source, filename):
    source=Path(source);target=ASSETS/filename
    if not source.exists(): raise ValueError(f'Media missing: {source}')
    shutil.copy2(source,target)
    return target


# Outside Top 10, only companies that stand out or do something Top 10 has not done yet.
TREND_PICKS={
 'LPS':'Quy mô lớn nhất bộ dữ liệu (427 quảng cáo) và 12 mẫu Google Ads (app) còn chạy gần 29/10 — nhiều hơn mọi công ty Top 10.',
 'DNSE':'Quảng cáo API/MCP cho nhà đầu tư dùng tự động hóa và AI — góc sản phẩm Top 10 chưa triển khai; có video Google Ads (app) demo giao diện.',
 'ABS':'Dùng giải thưởng và kết quả kinh doanh làm thông điệp uy tín — góc nội dung không thấy ở Top 10; 3 mẫu Google Ads (app) còn chạy gần 29/10.',
 'HD Securities':'Series video trả lời câu hỏi của người mới. Ở Top 10 chỉ VPS làm video kiến thức, và theo hướng giới thiệu sản phẩm.',
 'Shinhan / SSV':'Quảng bá nền tảng thông tin/cộng đồng VinaStalk thay vì app giao dịch — Top 10 chưa có mẫu bán trải nghiệm cộng đồng.',
 'KBSV':'3 mẫu Google Ads (app) còn chạy gần 29/10 (ở Top 10 chỉ SSI và Vietcap); ghép tính năng lọc cổ phiếu với 0 phí.',
}
ORIGINALS=PROJ/'originals'
MAX_CARDS=4


FB_ADS='Facebook Ads'
GG='Google Ads'
GG_ADS='Google Ads (app)'
CHANNEL_NAME={'Meta':FB_ADS,'Google App':GG_ADS,'YouTube tham khảo':'YouTube (ngoài Google Ads app)'}
GLOSSARY=[
  (FB_ADS,'Quảng cáo trả tiền trên Facebook, Instagram, Messenger.',
   'Meta Ad Library: nội dung, định dạng, nút CTA, link đích, ngày chạy.',
   'Không có ngân sách, lượt hiển thị, chuyển đổi.'),
  (GG,'Quảng cáo trả tiền trên Google, 4 dạng: Search (chữ khi người dùng tìm kiếm), ảnh hiển thị trên web/app, video YouTube, và video kéo cài app (nhãn Google Play, gọi là Google Ads (app)).',
   'Google Ads Transparency Center: ảnh chụp mẫu, định dạng, nơi hiển thị, ngày hiển thị đầu/cuối.',
   'Không có link đích, từ khóa, ngân sách, chuyển đổi.'),
]
# Why ad counts differ between the two libraries; shown on the "Cách đọc" pages.
COUNT_DIFF=[
  ('1 quảng cáo là gì','1 quảng cáo trong 1 nhóm. Cùng một thiết kế chạy 10 nhóm (tệp khách, vị trí) = 10 quảng cáo.',
   '1 creative. Copy cùng nội dung sang nhiều nhóm/chiến dịch = nhiều quảng cáo; 1 quảng cáo Search tự ghép nhiều tiêu đề.'),
  ('Gom theo ý tưởng','Có sẵn: Meta gắn mã chung cho quảng cáo cùng nội dung → “mẫu thiết kế”.',
   'Không có. Báo cáo tự gom: video theo YouTube ID, Search theo thông điệp + trang đích, banner theo thông điệp + con số ưu đãi.'),
  ('Khoảng thời gian','Chỉ quảng cáo đang chạy ngày 29/10.',
   'Cộng dồn cả quảng cáo đã dừng. Khi so hai kênh, báo cáo chỉ dùng quảng cáo Google còn chạy gần 29/10.'),
  ('Link đích','Có: nút CTA và link thật, mở được trang đích.',
   'Không công bố. Báo cáo dùng bộ lọc website của Google để biết quảng cáo có dẫn về web công ty hay không.'),
]
STAGES=['Nhận biết','Cân nhắc','Chuyển đổi']
STAGE_INFO={
  'Nhận biết':('Đầu phễu','Cho người chưa biết thương hiệu biết và nhớ tới mình.','Nút Thích trang, xem video; nội dung kiến thức, giải thưởng, câu chuyện.'),
  'Cân nhắc':('Giữa phễu','Người đã quan tâm tìm hiểu sản phẩm, so sánh với bên khác.','Nút Xem chi tiết/Tìm hiểu thêm dẫn về trang sản phẩm, bài viết, webinar.'),
  'Chuyển đổi':('Đáy phễu','Kéo người dùng hành động ngay: cài app, mở tài khoản, để lại thông tin.','Nút Cài đặt ngay/Đăng ký ngay/Nhắn tin; link về App Store, Google Play, form.'),
}
STAGE_RULES={
  'Nhận biết':('Nút Thích trang; không có link ra ngoài, nút Xem thêm/Xem trang; link về fanpage/sự kiện Facebook.',
               'Chữ trên quảng cáo nói về kiến thức, tin tức, phân tích, uy tín/thương hiệu.'),
  'Cân nhắc':('Link về web sản phẩm, bài viết/PR, form hoặc webinar bên ngoài (trang không gắn Meta Pixel).',
              'Chữ nói về sản phẩm, tính năng: bảng giá, app, phái sinh, quỹ, tích sản.'),
  'Chuyển đổi':('Nút Cài đặt/Dùng app, link App Store/Google Play; Nhắn tin (Messenger/Zalo); Lead form trên Facebook; landing có form + Meta Pixel.',
                'Có nhãn Google Play (kéo cài app). Hoặc chữ nói về quà/tiền thưởng, mở tài khoản, phí/margin, giới thiệu bạn bè.'),
}
def stage_counts(rows):
    """Funnel stage per design (asset group), majority vote of its ads — so 427 copies of one design count once."""
    designs={}
    for r in rows:designs.setdefault(r['asset_id'] or r['ad_archive_id'],Counter())[r['stage']]+=1
    c=Counter(v.most_common(1)[0][0] for v in designs.values())
    return [c.get(st,0) for st in STAGES]
def stage_line(b):
    n=stage_counts(b['fb']);tot=sum(n)
    if not tot:return ''
    return f'{FB_ADS} theo phễu ({tot} mẫu thiết kế): '+' · '.join(f'{st} {v}' for st,v in zip(STAGES,n))
def funnel_summary(data):
    bs=data['profiles']
    top=[r for b in bs if b['group']=='Top 10' for r in b['fb']]
    rest=[r for b in bs if b['group']!='Top 10' for r in b['fb']]
    allr=top+rest
    pct=lambda n:round(100*n[2]/max(sum(n),1))
    ads=Counter(r['stage'] for r in allr)
    t10=[b for b in bs if b['group']=='Top 10']
    return dict(fb_top=sum(bool(b['fb']) for b in t10),g_top=sum(bool(b['google']) for b in t10),
        g_top_active=sum(bool(g_active(b)) for b in t10),
        top=stage_counts(top),rest=stage_counts(rest),all=stage_counts(allr),
        top_pct=pct(stage_counts(top)),rest_pct=pct(stage_counts(rest)),
        ads_conv=ads['Chuyển đổi'],ads_total=len(allr),
        leaders={st:[b['name'] for b in bs if b['fb'] and b['show'] and
             max(range(3),key=lambda i:stage_counts(b['fb'])[i])==STAGES.index(st)] for st in STAGES})


# Destination buckets from base.dest(), worded for readers who never saw the raw data.
DEST_LABEL={'Facebook / sự kiện':'Ở lại Facebook (fanpage / sự kiện FB)'}
DEST_HELP=('“Ở lại Facebook” = nút CTA dẫn về fanpage hoặc trang sự kiện trên Facebook (vd HSC mời hội thảo IDC), '
           'người xem không rời Facebook, không sang web hay kho ứng dụng.')
def dest_label(d):return DEST_LABEL.get(d,d)


def chart_notes(data):
    """Short, data-derived takeaways for the overview chart slides (numbers, not prose)."""
    bs=data['profiles'];top=[b for b in bs if b['group']=='Top 10'];rest=[b for b in bs if b['group']!='Top 10']
    fbt=[b for b in top if b['fb']];fbr=[b for b in rest if b['fb']]
    names=lambda seq:', '.join(rname(b) for b in seq) or 'không có'
    def best(keys,fn,grp):   # (label, count) with the highest company count in a group
        c=[(k,sum(fn(b,k) for b in grp)) for k in keys];return max(c,key=lambda x:x[1])
    def pct(rows,grp):return ', '.join(f'{k} {v}/{len(grp)}' for k,v in rows)
    fmts={'ảnh đơn':lambda r:r['format']=='Ảnh đơn','video':lambda r:r['format']=='Video',
          'carousel':lambda r:r['format'] in ['Carousel','Nhiều ảnh'],'DCO':lambda r:r['format']=='Dynamic (DCO)'}
    has_fmt=lambda b,k:any(fmts[k](r) for r in b['fb'])
    rank_fmt=lambda grp:sorted(((k,sum(has_fmt(b,k) for b in grp)) for k in fmts),key=lambda x:-x[1])
    themes=['Ưu đãi / chi phí','Tính năng / sản phẩm','Kiến thức / phân tích','Uy tín / cộng đồng','Tò mò / cá nhân hóa']
    rank_th=lambda grp:sorted(((k,sum(k in b['themes'] for b in grp)) for k in themes),key=lambda x:-x[1])
    dests=['Kho ứng dụng / mở app','Web nội dung / sản phẩm / sự kiện','Web có form (chưa xác nhận mục đích)','Facebook / sự kiện','Messenger']
    rank_de=lambda grp:sorted(((dest_label(k).split(' (')[0],sum(any(base.dest(r)==k for r in b['fb']) for b in grp)) for k in dests),key=lambda x:-x[1])
    shown=[b for b in bs if b.get('show')]
    ratio=sorted([b for b in shown if b['fb']],key=lambda b:-len(b['fb'])/max(b['designs'],1))[:3]
    gact=sorted(shown,key=lambda b:-len(g_active(b)))[:3]
    return {
      '01_channels':[f"Facebook Ads: Top 10 {len(fbt)}/10, ngoài Top 10 {len(fbr)}/15.",
        f"Google Ads còn chạy gần 29/10: Top 10 {sum(bool(g_active(b)) for b in top)}/10, ngoài {sum(bool(g_active(b)) for b in rest)}/15.",
        f"Video app còn chạy: Top 10 chỉ {names([b for b in top if b['recent']])}."],
      '02_top10':[f"Có cả hai kênh: {names([b for b in top if b['fb'] and b['google']])}; Google còn chạy chỉ {names([b for b in top if b['fb'] and g_active(b)])}.",
        f"Chỉ thấy Google Ads: {names([b for b in top if b['google'] and not b['fb']])}. Chỉ thấy Facebook Ads: {names([b for b in top if b['fb'] and not b['google']])}.",
        f"Chưa thấy kênh nào: {names([b for b in top if not b['fb'] and not b['google']])}."],
      '03_formats':[f"Top 10 ({len(fbt)} công ty có FB): {pct(rank_fmt(fbt)[:2],fbt)}.",
        f"Ngoài Top 10: {pct(rank_fmt(rest)[:2],rest)}.",
        f"Video: Top 10 {sum(has_fmt(b,'video') for b in fbt)}/{len(fbt)}, ngoài {sum(has_fmt(b,'video') for b in rest)}/15."],
      '04_content':[f"Top 10: {pct(rank_th(fbt)[:2],fbt)}.",f"Ngoài Top 10: {pct(rank_th(rest)[:2],rest)}.",
        'Đếm số công ty có nội dung, không phải tỷ trọng quảng cáo.'],
      '05_destinations':[f"Top 10: {pct(rank_de(fbt)[:2],fbt)}.",f"Ngoài Top 10: {pct(rank_de(rest)[:2],rest)}.",DEST_HELP],
      '06_volume_design':['Cùng thước đo cho hai kênh: quảng cáo còn chạy gần 29/10. Số trong ngoặc = Google cộng dồn cả mẫu đã dừng.',
        'Facebook, QC/mẫu cao nhất: '+', '.join(f"{rname(b)} {len(b['fb'])}/{b['designs']}" for b in ratio)+'.',
        'Google còn chạy nhiều nhất: '+', '.join(f"{rname(b)} {len(g_active(b))} QC ≈ {g_ideas(g_active(b))} ý tưởng" for b in gact)+'.'],
    }


def google_funnel_summary(data):
    bs=data['profiles'];t10=[b for b in bs if b['group']=='Top 10'];rest=[b for b in bs if b['group']!='Top 10']
    lead=sorted([b for b in rest if b['app']],key=lambda b:-len(b['app']))[:3]
    return dict(top_app_cos=sum(bool(b['app']) for b in t10),top_app=sum(len(b['app']) for b in t10),
        top_app_recent=sum(len(b['recent']) for b in t10),
        top_recent_names=', '.join(b['name'] for b in t10 if b['recent']) or 'không có',
        rest_app=sum(len(b['app']) for b in rest),
        rest_leaders=', '.join(f"{b['name']} ({len(b['app'])})" for b in lead),
        read=sum(g_read(b['google']) for b in bs),total=sum(len(b['google']) for b in bs))


G_FORMAT={'Chữ (Search)':'Search (chữ)','Ảnh':'Ảnh hiển thị','Video':'Video YouTube'}
G_KINDS=['Search (chữ)','Ảnh hiển thị','Video YouTube','Video kéo cài app']
G_ROLE={'Search (chữ)':'bắt người đang tìm kiếm (giữa → đáy phễu)','Ảnh hiển thị':'nhắc nhớ trên web/app (đầu → giữa phễu)',
        'Video YouTube':'nhận biết qua video (đầu phễu)','Video kéo cài app':'kéo cài app (đáy phễu)'}
GNOTES=json.loads((PROJ/'google_notes.json').read_text()).get('Hồ sơ',{})
def gkind(r):return 'Video kéo cài app' if base.app_row(r) else G_FORMAT.get(r['format'],r['format'])
# Google publishes no CTA or landing URL. Each creative is classified from text read on the ad itself
# (OCR of the preview, YouTube title) by google_messages.py; the Play label always means app install, and
# the destination comes from the Transparency website filter (google_dest_check.py).
GMSG={}
def load_gmsg():
    import google_messages
    GMSG.clear();GMSG.update(google_messages.build(PROJ.name)[1])
def gmsg(r):return GMSG[r['creative_id']]
def g_stage(r):return gmsg(r)['stage']
def g_stage_counts(rows):
    c=Counter(g_stage(r) for r in rows);return [c.get(st,0) for st in STAGES]
def g_ideas(rows):return len({gmsg(r)['idea'] for r in rows})
def g_read(rows):return sum(gmsg(r)['theme']!=UNREAD for r in rows)
UNREAD='Chưa đọc được nội dung'
def g_theme_lines(rows,n=5):
    by=defaultdict(list)
    for r in rows:by[gmsg(r)['theme']].append(r)
    top=sorted(((k,v) for k,v in by.items() if k!=UNREAD),key=lambda kv:-len(kv[1]))[:n]
    lines=[f"{k}: {len(v)} · {g_ideas(v)}" for k,v in top]
    if by.get(UNREAD):lines.append(f"Chưa đọc được chữ: {len(by[UNREAD])}")
    return '\n'.join(lines) or 'Chưa đọc được chữ trên quảng cáo.'
def g_dest_line(rows):
    web=sum(gmsg(r)['target']=='Web công ty' for r in rows)
    paths=Counter(re.sub(r'^[^/]*','',gmsg(r)['display_path']).rstrip('/') for r in rows if gmsg(r)['display_path'])
    paths=[p for p,_ in paths.most_common() if p][:2]
    return f"{web}/{len(rows)} QC dẫn về web công ty."+(f" Trang: {', '.join(paths)}." if paths else '')
GSTAGE_NOTE='Google Ads: Google không công bố nút CTA hay link đích, nên giai đoạn xếp theo chữ đọc được trên quảng cáo (OCR ảnh xem trước, tiêu đề video); không đọc được chữ thì theo định dạng (Search → Cân nhắc, ảnh/video → Nhận biết).'
def g_mix(rows):
    c=Counter(gkind(r) for r in rows);return ' · '.join(f'{k} {c[k]}' for k in G_KINDS if c[k])
def g_active(b):return [r for r in b['google'] if r['active']=='True']
def vn_date(d):return '/'.join(reversed(d.split('-'))) if d else '?'
def g_image(r):
    url=r['image_url']
    if not url:return None
    name=re.sub(r'\D','',url.rsplit('/',1)[-1])[:24] or hashlib.md5(url.encode()).hexdigest()[:16]
    path=PROJ/'google/img'/f'{name}.png';return path if path.exists() else None
PLACE={'Display/khác':'mạng hiển thị','Play':'Google Play'}
YT_THUMBS=PROJ/'google/yt'
def yt_thumb(r,fetch=True):
    """App videos rarely have a Transparency render; fall back to the cached YouTube thumbnail."""
    vid=r['youtube_id'].rsplit('/',1)[-1]
    if not vid:return None
    path=YT_THUMBS/f'{vid}.jpg'
    if not path.exists() and fetch:
        import urllib.request
        YT_THUMBS.mkdir(parents=True,exist_ok=True)
        for size in ('maxresdefault','hqdefault'):
            try:
                with urllib.request.urlopen(f'https://i.ytimg.com/vi/{vid}/{size}.jpg',timeout=20) as resp:
                    path.write_bytes(resp.read());break
            except Exception:continue
    return path if path.exists() else None
def g_visual(r,fetch=True):return g_image(r) or (yt_thumb(r,fetch) if base.app_row(r) else None)
def g_places(r):return ', '.join(PLACE.get(x,x) for x in r['platforms'].split(',') if x) or 'chưa rõ'
def g_text(r):
    kind=gkind(r);state='còn chạy gần 29/10' if r['active']=='True' else 'đã dừng'
    title=f"Tiêu đề video: “{r['video_title']}”. " if r['video_title'] and not r['video_title'].endswith('.mp4') else ''
    cap=f"{title}Hiển thị trên {g_places(r)}; {r['days_shown']} ngày có hiển thị, {state}."
    m=gmsg(r)
    return (f"{GG} · Mẫu {r['n']} · {kind} · {g_stage(r)}",cap,
        f"{vn_date(r['first_shown'])} → {vn_date(r['last_shown'])}  ·  Thông điệp: {m['theme']}  ·  Phễu: {m['stage']} ({m['stage_source'].lower()})  ·  Đích: {m['target']}",
        'Xem trên Google Ads Transparency →')
# Media-report overrides of editorial notes: Google now has its own section in each profile.
MEDIA_NOTES={'Vietcap':('Chỉ chạy Google Ads, một lời mời mở tài khoản trên ba định dạng',
  'Không chạy Facebook Ads. Trên Google, Vietcap lặp lại cùng một lời mời ở ba dạng: Search “Mở tài khoản chỉ trong 5 phút”, '
  'ảnh hiển thị “Bắt đầu hành trình đầu tư ngay” và video kéo cài app dùng con số 93% nhà đầu tư hài lòng. '
  'Video Vietcap IQ ở Thư viện video là YouTube tham khảo, không thuộc nhóm kéo cài app.')}
def drop_google(text):
    parts=re.split(r'(?<=\.)\s+',text)
    return ' '.join(x for x in parts if 'Google' not in x) or text


def rname(b):return f"#{b['rank']} {b['name']}" if b.get('rank') else b['name']
def group_label(b):return 'Top 10' if b['group']=='Top 10' else 'Ngoài Top 10 · Tham khảo'
def is_running(b):return bool(b['fb']) or bool(g_active(b))
def is_shown(b):return is_running(b) and (b['group']=='Top 10' or b['name'] in TREND_PICKS)


def _download(url,path):
    import urllib.request
    req=urllib.request.Request(url,headers={'User-Agent':base_ua()})
    path.write_bytes(urllib.request.urlopen(req,timeout=60).read())
    return path


def base_ua():
    import fb_ads_scraper as fb
    return fb.USER_AGENT


def _frame(video,out):
    dur=float(json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)],
        check=True,capture_output=True,text=True).stdout)['format']['duration'])
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',f'{dur*.3:.2f}','-i',str(video),
        '-frames:v','1','-q:v','2',str(out)],check=True,capture_output=True)
    return out


def _video_frame(url,out,folder):
    """Full-resolution frame at 30% of the video — Meta's own preview is often a blank first frame."""
    tmp=_download(url,folder/'_video.mp4')
    try:return _frame(tmp,out)
    finally:tmp.unlink(missing_ok=True)


def _snapshot(ctx,aid):
    import fb_ads_scraper as fb
    found={};page=ctx.new_page()
    page.on('response',lambda r:('graphql' in r.url) and fb.parse_json_blob(r.text(),found))
    try:
        page.goto(f'https://www.facebook.com/ads/library/?id={aid}',wait_until='domcontentloaded',timeout=60000)
        page.wait_for_timeout(8000)
        for m in re.finditer(r'<script type="application/json"[^>]*>(.*?)</script>',page.content(),re.S):
            try:fb.walk_for_ads(json.loads(m.group(1)),found)
            except json.JSONDecodeError:pass
    finally:page.close()
    return (found.get(aid) or {}).get('snapshot')


def _save_snapshot_media(s,folder):
    sources=[]
    for v in s.get('videos') or []:
        sources.append(('video',v.get('video_hd_url') or v.get('video_sd_url'),v.get('video_preview_image_url')))
    for x in (s.get('images') or [])+(s.get('cards') or []):
        if x.get('video_hd_url') or x.get('video_sd_url'):
            sources.append(('video',x.get('video_hd_url') or x.get('video_sd_url'),x.get('video_preview_image_url')))
        elif x.get('original_image_url') or x.get('resized_image_url'):
            sources.append(('image',x.get('original_image_url') or x.get('resized_image_url'),None))
    files=[]
    for i,(kind,url,preview) in enumerate(sources[:MAX_CARDS]):
        out=folder/f'{i+1:02d}.jpg'
        try:
            if kind=='video':_video_frame(url,out,folder)
            else:_download(url,out)
        except Exception:
            if preview:_download(preview,out)
            else:raise
        with Image.open(out) as im:im.convert('RGB').save(out,quality=92)
        files.append(out.name)
    return files


def fetch_originals(ad_ids,siblings=None,network=True,delay=2.5):
    """Download the original creative of each ad from Meta Ad Library into originals/<ad_id>/.
    Ads Meta has since removed from the library fall back to (1) the saved full video in winners/,
    (2) another live ad of the same design group (asset_id), recorded as `via`.
    Cached: an ad with meta.json is never fetched again. Returns {ad_id: {files, via}}."""
    import random,time
    siblings=siblings or {}
    todo=[a for a in ad_ids if network and not (ORIGINALS/a/'meta.json').exists()]
    if todo:
        from playwright.sync_api import sync_playwright
        import fb_ads_scraper as fb
        print(f'Tải ảnh gốc cho {len(todo)} quảng cáo…',flush=True)
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            ctx=browser.new_context(user_agent=fb.USER_AGENT,locale='vi-VN',viewport={'width':1366,'height':900})
            for n,aid in enumerate(todo):
                folder=ORIGINALS/aid;folder.mkdir(parents=True,exist_ok=True);files=[];error='';via=''
                try:
                    s=_snapshot(ctx,aid)
                    if s:files=_save_snapshot_media(s,folder)
                    else:
                        saved=next(iter(PROJ.glob(f'winners/*_{aid}/video.mp4')),None)
                        if saved:files=[_frame(saved,folder/'01.jpg').name];via='saved video'
                        for sib in siblings.get(aid,[])[:3]:
                            if files:break
                            time.sleep(delay+random.random())
                            s=_snapshot(ctx,sib)
                            if s:files=_save_snapshot_media(s,folder);via=sib
                    if not files:error='not in Ad Library any more; no live ad of the same design'
                except Exception as e:error=str(e)[:200]
                (folder/'meta.json').write_text(json.dumps(dict(ad_id=aid,files=files,via=via,error=error,
                    fetched_at=time.strftime('%Y-%m-%dT%H:%M:%S')),ensure_ascii=False,indent=2))
                print(f'  {n+1}/{len(todo)} {aid}: {len(files)} ảnh {via} {error}',flush=True)
                time.sleep(delay+random.random())
            browser.close()
    out={}
    for a in ad_ids:
        meta=ORIGINALS/a/'meta.json'
        if meta.exists():
            m=json.loads(meta.read_text())
            if m['files']:out[a]=dict(files=[rel(ORIGINALS/a/f) for f in m['files']],via=m.get('via',''))
    return out


def card_strip(paths,target,height=1080,gap=24):
    """Carousel / DCO: every card side by side at the same height, original pixels kept."""
    ims=[]
    for p in paths:
        with Image.open(ROOT/p) as im:
            im=im.convert('RGB');ims.append(im.resize((round(im.width*height/im.height),height)))
    page=Image.new('RGB',(sum(i.width for i in ims)+gap*(len(ims)-1),height),'white');x=0
    for im in ims:page.paste(im,(x,0));x+=im.width+gap
    page.save(target,quality=92);return target


def prepare_data(fetch=True):
    data=base.build_data();load_gmsg()
    raw={}
    for _,pid,_ in base.BRANDS:
        for r in json.loads((PROJ/'pages'/f'{pid}.json').read_text()):
            raw[str(r['ad_archive_id'])]=r
    landings=json.loads((PROJ/'landing/landings.json').read_text())
    videos=[];inventory=[]
    for b in data['profiles']:
        b['running']=is_running(b);b['show']=is_shown(b);b['why']=TREND_PICKS.get(b['name'],'')
        b['rank']=data['profiles'].index(b)+1 if b['group']=='Top 10' else None
        if b['name'] in MEDIA_NOTES:b['title'],b['analysis']=MEDIA_NOTES[b['name']]
        else:b['analysis']=drop_google(b['analysis'])
        eligible=[];seen_assets=set();seen_text=set()
        # Editorial samples first, followed by format diversity and new captions.
        candidates=(b['selected']+sorted(b['fb'],key=lambda r:(r['format'],r['ad_archive_id']))) if b['show'] else []
        for r in candidates:
            text=clean(r['body'])
            if not text or text=='{{product.brand}}': continue
            if r['asset_id'] in seen_assets or text in seen_text:continue
            rr=raw[r['ad_archive_id']]
            candidates_img=[PROJ/'thumbs'/f"{rr.get('collation_id','')}.jpg",PROJ/'thumbs'/f"{r['asset_id']}.jpg"]
            source=next((p for p in candidates_img if p.exists()),None)
            if not source:continue
            item=copy.deepcopy(r);item['thumb']=source
            item['caption']=text;item['url']=r['library_link']
            eligible.append(item);seen_assets.add(r['asset_id']);seen_text.add(text)
        b['_eligible']=eligible;b['gallery']=[]
    # Keep three samples per company that still have an original creative; ads Meta has since removed
    # (and with no live ad of the same design) give way to the next candidate of the same company.
    siblings={r['ad_archive_id']:[x['ad_archive_id'] for x in b['fb'] if x['asset_id']==r['asset_id'] and x['ad_archive_id']!=r['ad_archive_id']]
              for b in data['profiles'] for r in b['_eligible']}
    originals={};pos={id(b):0 for b in data['profiles']}
    for _ in range(6):
        batch=[]
        for b in data['profiles']:
            need=3-len(b['gallery']);take=b['_eligible'][pos[id(b)]:pos[id(b)]+need];pos[id(b)]+=len(take)
            batch += [(b,r) for r in take]
        if not batch:break
        originals.update(fetch_originals([r['ad_archive_id'] for _,r in batch],siblings,network=fetch))
        for b,r in batch:
            if r['ad_archive_id'] in originals:b['gallery'].append(r)
    for b in data['profiles']:   # still short (no originals left): fall back to saved 600px previews
        for r in b['_eligible']:
            if len(b['gallery'])>=3:break
            if r not in b['gallery']:b['gallery'].append(r)
        order={r['ad_archive_id']:i for i,r in enumerate(b['_eligible'])}
        b['gallery'].sort(key=lambda r:order[r['ad_archive_id']]);del b['_eligible']
    for b in data['profiles']:
        for r in b['gallery']:
            aid=r['ad_archive_id'];name=f"fb_{slug(b['name'])}_{aid}"
            info=originals.get(aid);files=info['files'] if info else None
            r['via']=info['via'] if info else ''
            if files:
                image=copy_asset(ROOT/files[0],name+'.jpg');kind='Facebook original'
                r['cards']=len(files)
                r['strip']=rel(card_strip(files,ASSETS/f'{name}_cards.jpg')) if len(files)>1 else None
                source=files[0]
            else:
                image=copy_asset(r['thumb'],name+'.jpg');kind='Facebook preview (600px)'
                r['cards']=1;r['strip']=None;source=rel(r['thumb'])
            r['original']=bool(files);r['image']=rel(image);r['source_image']=source;del r['thumb']
            inventory.append(dict(type=kind,brand=b['name'],source=source,local=rel(image),ad_id=aid,url=r['library_link']))
    for b in data['profiles']:
        chosen=b['gallery']
        # Google Ads samples: Transparency Center renders, one per format first, running ads first.
        # Web formats (Search / display / YouTube) and app-install videos get separate galleries, so a
        # company with Play-labelled videos shows its app assets instead of only its web ads.
        b['g_gallery']=[];b['app_gallery']=[]
        if b['google'] and b['show']:
            def order(rows):
                rows=sorted(rows,key=lambda r:r['last_shown'],reverse=True)
                return sorted(rows,key=lambda r:r['active']!='True')
            web=order([r for r in b['google'] if not base.app_row(r) and g_image(r)])
            picked=[];kinds=set()
            for r in web:
                if gkind(r) not in kinds:picked.append(r);kinds.add(gkind(r))
            seen={g_image(r) for r in picked}
            for r in web:
                if len(picked)>=3:break
                if r not in picked and g_image(r) not in seen:picked.append(r);seen.add(g_image(r))
            picked=sorted(picked[:3],key=lambda r:G_KINDS.index(gkind(r)) if gkind(r) in G_KINDS else 9)
            apps=[];seen=set()
            for r in order(b['app']):   # distinct videos: one creative per YouTube ID / render
                key=r['youtube_id'] or r['image_url'] or r['creative_id']
                if key in seen or not g_visual(r,fetch):continue
                apps.append(r);seen.add(key)
                if len(apps)>=3:break
            for gallery,rows in [(b['g_gallery'],picked),(b['app_gallery'],apps)]:
                for i,r in enumerate(rows):
                    source=g_visual(r,fetch);local=ASSETS/f"google_{slug(b['name'])}_{r['creative_id']}.jpg"
                    im=Image.open(source);im.load()
                    if im.mode in ('RGBA','LA','P'):
                        im=im.convert('RGBA');bg=Image.new('RGB',im.size,'white');bg.paste(im,mask=im.split()[-1]);im=bg
                    im=im.convert('RGB');im.thumbnail((1600,1600));im.save(local,quality=90)
                    item=dict(r,channel='google',n=i+1,image=rel(local),url=r['link'],kind=gkind(r),stage=g_stage(r))
                    item['text']=g_text(item);gallery.append(item)
                    inventory.append(dict(type='Google Ads sample',brand=b['name'],source=rel(source),local=rel(local),url=r['link']))
        b['landing_preview']=None
        for r in chosen:
            item=landings.get(r['link_url'])
            if item and item.get('screenshot'):
                source=PROJ/'landing'/item['screenshot']
                if source.exists() and not item.get('error'):
                    local=copy_asset(source,f"landing_{slug(b['name'])}.jpg")
                    b['landing_preview']=dict(image=rel(local),url=item['final_url'],title=item.get('title',''),
                                             source=rel(source),ad_id=r['ad_archive_id'])
                    inventory.append(dict(type='Landing screenshot',brand=b['name'],source=rel(source),local=rel(local),url=item['final_url']))
                    break
        b['videos']=[]
        for channel,packs in [('Meta',b['meta_packs']),('Google App',b['google_packs'])] if b['show'] else []:
            for pack in sorted(packs,key=lambda p:p['rank']):
                if (channel,pack['rank']) not in VIDEO_NOTES:raise ValueError((channel,pack['rank']))
                folder=ROOT/pack['folder'];identity=f"{slug(b['name'])}_{slug(channel)}_{pack['rank']:02d}"
                source=folder/'video.mp4'
                video=copy_asset(source,identity+'.mp4')
                poster=copy_asset(folder/'hook.jpg',identity+'_poster.jpg')
                board=copy_asset(folder/'storyboard.jpg',identity+'_storyboard.jpg')
                notes=VIDEO_NOTES[channel,pack['rank']]
                v=dict(brand=b['name'],channel=channel,rank=pack['rank'],title=notes[0],flow=notes[1],
                    content=notes[2],finding=notes[3],video=rel(video),poster=rel(poster),storyboard=rel(board),
                    source_video=rel(source),duration=pack.get('video_duration'),aspect=pack.get('aspect',''),
                    url=pack['library_links'][0] if channel=='Meta' else pack['transparency_links'][0],
                    caption=pack.get('caption',''),meta=pack)
                videos.append(v);b['videos'].append(v)
                inventory.append(dict(type='Verified video',brand=b['name'],channel=channel,source=rel(source),local=rel(video),url=v['url']))
    # Broader YouTube context is explicit and excluded from all App metrics.
    for rank in [2,11]:
        f=next(f for f in (PROJ/'winners_google').glob('*/meta.json') if json.loads(f.read_text())['rank']==rank)
        pack=json.loads(f.read_text());channel='YouTube tham khảo';notes=VIDEO_NOTES[channel,rank]
        name='SSI' if rank==2 else 'Vietcap';identity=f'{slug(name)}_youtube_context_{rank:02d}'
        paths={suffix:copy_asset(f.parent/namefile,identity+ending) for suffix,namefile,ending in [
            ('video','video.mp4','.mp4'),('poster','hook.jpg','_poster.jpg'),('storyboard','storyboard.jpg','_storyboard.jpg')]}
        v=dict(brand=name,channel=channel,rank=rank,title=notes[0],flow=notes[1],content=notes[2],finding=notes[3],
            **{k:rel(p) for k,p in paths.items()},source_video=rel(f.parent/'video.mp4'),duration=pack['video_duration'],
            aspect=pack['aspect'],url=pack['transparency_links'][0],caption='',meta=pack)
        videos.append(v)
        inventory.append(dict(type='Context video outside App',brand=name,source=v['source_video'],local=v['video'],url=v['url']))
    # Existing hook.jpg files are multi-frame strips, unsuitable as a movie
    # poster. Extract one real frame so the embedded player's aspect is right.
    for v in videos:
        video_path=ROOT/v['video']
        transcript_source=(ROOT/v['source_video']).with_name('transcript.txt')
        if transcript_source.exists():
            transcript=copy_asset(transcript_source,video_path.stem+'_transcript.txt')
            v['transcript']=rel(transcript)
            inventory.append(dict(type='Video transcript',brand=v['brand'],source=rel(transcript_source),local=rel(transcript),url=v['url']))
        probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,codec_name',
            '-of','json',str(video_path)],check=True,capture_output=True,text=True)
        streams=json.loads(probe.stdout)['streams']
        compatible=all(s['codec_name'] in ('h264','aac') for s in streams if s['codec_type'] in ('video','audio'))
        if not compatible:
            converted=video_path.with_suffix('.compatible.mp4')
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video_path),
                '-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
                '-c:a','aac','-b:a','128k','-movflags','+faststart',str(converted)],
                check=True,capture_output=True)
            converted.replace(video_path)
        v['delivery_encoding']='H.264 video; AAC audio when present; source cache unchanged'
        stamp=min(float(v['duration'])*.35,5.0)
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(stamp),
            '-i',str(ROOT/v['video']),'-frames:v','1','-q:v','2',str(ROOT/v['poster'])],
            check=True,capture_output=True)
        v['poster_timestamp_seconds']=stamp
    data['videos']=videos;data['inventory']=inventory
    return data


def setup_charts():
    from matplotlib import font_manager
    for f in (FONT,SEMI,BOLD):font_manager.fontManager.addfont(str(f))
    plt.rcParams.update({'font.family':FontProperties(fname=str(FONT)).get_name(),
        'font.size':12,'axes.spines.top':False,'axes.spines.right':False,
        'axes.spines.left':False,'axes.spines.bottom':True,'axes.edgecolor':INK,'axes.linewidth':.8,
        'axes.labelcolor':MUTED,'text.color':INK,'xtick.color':MUTED,'ytick.color':INK,
        'legend.labelcolor':INK,'figure.facecolor':'white'})


def save_chart(fig,name):
    path=CHARTS/f'{name}.png';fig.savefig(path,dpi=190,bbox_inches='tight',facecolor='white');plt.close(fig)
    return rel(path)


def charts(data):
    setup_charts();bs=data['profiles'];out={};top=bs[:10];trend=bs[10:]
    def grouped(labels,a,b,name,dena=10,denb=15):
        fig,ax=plt.subplots(figsize=(11,4.7));y=list(range(len(labels)))
        ax.barh([i-.18 for i in y],[100*v/dena for v in a],height=.32,color=SERIES_A,label=f'Top 10 (n={dena})')
        ax.barh([i+.18 for i in y],[100*v/denb for v in b],height=.32,color=SERIES_B,label=f'Ngoài Top 10 · tham khảo (n={denb})')
        for i,(v,w) in enumerate(zip(a,b)):
            ax.text(100*v/dena+1,i-.18,f'{v}/{dena}',va='center',fontsize=12)
            ax.text(100*w/denb+1,i+.18,f'{w}/{denb}',va='center',fontsize=12)
        ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlim(0,116)
        ax.set_xticks([0,25,50,75,100],['0%','25%','50%','75%','100%'])
        ax.set_xlabel('Tỷ lệ công ty có bằng chứng trong từng nhóm');ax.grid(axis='x',color=LINE,linewidth=.8);ax.set_axisbelow(True)
        ax.legend(loc='lower center',bbox_to_anchor=(.45,1.0),ncol=2,frameon=False,handlelength=1,handleheight=1);fig.tight_layout();out[name]=save_chart(fig,name)
    keys=[lambda b:b['fb'],lambda b:b['google'],g_active,lambda b:b['app']]
    grouped([FB_ADS,GG+': có chạy',GG+': còn chạy gần 29/10',GG_ADS],
        [sum(bool(k(b)) for b in top) for k in keys],[sum(bool(k(b)) for b in trend) for k in keys],'01_channels')
    fig,ax=plt.subplots(figsize=(11,5.4));matrix=[];texts=[]
    def cell(all_rows,act,unit):
        if not all_rows:return 0,'Không thấy'
        return (2,f'{len(all_rows)} {unit} · {len(act)} còn chạy') if act else (1,f'{len(all_rows)} {unit} · đã dừng')
    for b in top:
        cells=[(2,f"{len(b['fb'])} QC đang chạy") if b['fb'] else (0,'Không chạy'),
               cell(b['google'],g_active(b),'QC'),cell(b['app'],b['recent'],'video')]
        matrix.append([c[0] for c in cells]);texts.append([c[1] for c in cells])
    from matplotlib.colors import ListedColormap
    ax.imshow(matrix,cmap=ListedColormap([SURFACE_ALT,MINT,LIME]),vmin=0,vmax=2,aspect='auto')
    for i in range(len(top)):
        for j,t in enumerate(texts[i]):
            ax.text(j,i,t,ha='center',va='center',color=INK if matrix[i][j] else MUTED,fontsize=11,fontweight=600 if matrix[i][j]==2 else 400)
    ax.set_yticks(range(len(top)),[f'{i+1}. {b["name"]}' for i,b in enumerate(top)])
    ax.set_xticks([0,1,2],[FB_ADS,GG+' (mọi định dạng)','trong đó: '+GG_ADS])
    ax.tick_params(length=0);ax.xaxis.tick_top()
    for sp in ax.spines.values():sp.set_visible(False)
    ax.set_xticks([.5,1.5],minor=True);ax.grid(which='minor',axis='x',color='white',linewidth=3)
    ax.set_yticks([i+.5 for i in range(len(top)-1)],minor=True);ax.grid(which='minor',axis='y',color='white',linewidth=3)
    ax.tick_params(which='minor',length=0);fig.tight_layout();out['02_top10']=save_chart(fig,'02_top10')
    categories=[('Ảnh đơn',lambda r:r['format']=='Ảnh đơn'),('Video đã xác định',lambda r:r['format']=='Video'),
        ('Carousel / nhiều ảnh',lambda r:r['format'] in ['Carousel','Nhiều ảnh']),
        ('DCO — chưa tách media',lambda r:r['format']=='Dynamic (DCO)')]
    grouped([x[0] for x in categories],
        [sum(any(fn(r) for r in b['fb']) for b in top) for _,fn in categories],
        [sum(any(fn(r) for r in b['fb']) for b in trend) for _,fn in categories],'03_formats',7,15)
    themes=['Ưu đãi / chi phí','Tính năng / sản phẩm','Kiến thức / phân tích','Uy tín / cộng đồng','Tò mò / cá nhân hóa']
    grouped(themes,[sum(t in b['themes'] for b in top) for t in themes],
        [sum(t in b['themes'] for b in trend) for t in themes],'04_content',7,15)
    dests=['Kho ứng dụng / mở app','Web có form (chưa xác nhận mục đích)',
        'Web nội dung / sản phẩm / sự kiện','Facebook / sự kiện','Messenger']
    grouped(['Kho ứng dụng / mở app','Web có form','Web nội dung / sản phẩm',dest_label('Facebook / sự kiện'),'Messenger'],
        [sum(any(base.dest(r)==d for r in b['fb']) for b in top) for d in dests],
        [sum(any(base.dest(r)==d for r in b['fb']) for b in trend) for d in dests],'05_destinations',7,15)
    picks=[b for b in trend if b['show']]
    order=top+[None]+picks
    labels=[f'{i+1}. {b["name"]}' for i,b in enumerate(top)]+['NGOÀI TOP 10 · THAM KHẢO']+[b['name'] for b in picks]
    # Same yardsticks for both channels: ads live around 29/10, and ideas (FB design groups vs Google
    # distinct videos / Search messages+landing / banner messages) among those live ads.
    fig,axes=plt.subplots(1,4,figsize=(13,7),sharey=True)
    ga=lambda b:[r for r in b['google'] if r['active']=='True']
    panels=[(f'{FB_ADS}\nquảng cáo đang chạy',lambda b:len(b['fb']),SERIES_A,None),
            (f'{GG}\nquảng cáo còn chạy (cộng dồn)',lambda b:len(ga(b)),SERIES_B,lambda b:len(b['google'])),
            (f'{FB_ADS}\nsố mẫu thiết kế',lambda b:b['designs'] if b['fb'] else 0,SERIES_A,None),
            (f'{GG}\nsố ý tưởng còn chạy (cộng dồn)',lambda b:g_ideas(ga(b)),SERIES_B,lambda b:g_ideas(b['google']))]
    for ax,(label,fn,color,total) in zip(axes,panels):
        vals=[fn(b) if b else None for b in order];mx=max(v for v in vals if v is not None) or 1
        for i,(b,v) in enumerate(zip(order,vals)):
            if v is None:continue
            if v:ax.barh(i,v,color=color,height=.66)
            t=total(b) if total else None
            lab=(str(v) if v else '–')+(f' ({t})' if t else '')
            ax.text((v or 0)+mx*.02,i,lab,va='center',fontsize=10,color=INK if v else MUTED)
        ax.set_title(label,fontsize=12,loc='left',color=INK);ax.set_xlim(0,mx*(1.8 if total else 1.25));ax.set_xticks([])
        ax.spines['bottom'].set_visible(False)
        ax.axhline(len(top),color=LINE,linewidth=1);ax.tick_params(axis='y',length=0)
    axes[0].set_yticks(range(len(order)),labels);axes[0].invert_yaxis();axes[0].tick_params(axis='y',length=0)
    lab=axes[0].get_yticklabels()[len(top)];lab.set_color(MUTED);lab.set_fontsize(9);lab.set_fontweight(700)
    fig.text(.2,1.0,'ĐANG CHẠY GẦN 29/10',fontsize=11,color=ACCENT,fontweight=700)
    fig.text(.6,1.0,'SỐ Ý TƯỞNG',fontsize=11,color=ACCENT,fontweight=700)
    fig.tight_layout();out['06_volume_design']=save_chart(fig,'06_volume_design')
    # Funnel: share of designs per stage, analysed companies + group totals.
    fs=funnel_summary(data)
    rows=[(f'{i+1}. {b["name"]}',stage_counts(b['fb'])) for i,b in enumerate(top)]+[('Top 10 · tổng',fs['top']),None,
          ('NGOÀI TOP 10 · THAM KHẢO','header')]+[(b['name'],stage_counts(b['fb'])) for b in trend if b['show'] and b['fb']]+[
          ('Ngoài Top 10 · tổng (15 công ty)',fs['rest'])]
    fig,ax=plt.subplots(figsize=(11,8.6));colors=[MINT,EMERALD,PINE];ink=[INK,INK,'#FFFFFF']
    for i,row in enumerate(rows):
        if row is None or row[1]=='header':continue
        name,n=row;tot=sum(n);left=0
        if not tot:
            ax.text(1,i,'Không chạy Facebook Ads',va='center',fontsize=10,color=MUTED);continue
        for j,v in enumerate(n):
            w=100*v/tot
            if v:ax.barh(i,w,left=left,color=colors[j],height=.68,edgecolor='white',linewidth=1.2)
            if w>=9:ax.text(left+w/2,i,str(v),ha='center',va='center',color=ink[j],fontsize=11,fontweight=600)
            left+=w
        ax.text(101.5,i,f'{tot} mẫu',va='center',fontsize=10,color=MUTED)
    ax.set_yticks([i for i,r in enumerate(rows) if r],[r[0] for r in rows if r])
    for t in ax.get_yticklabels():
        if 'tổng' in t.get_text():t.set_fontweight(700)
        if t.get_text().startswith('NGOÀI'):t.set_color(MUTED);t.set_fontsize(9);t.set_fontweight(700)
    ax.axhline(len(top)+1.5,color=LINE,linewidth=1)
    ax.invert_yaxis();ax.set_xlim(0,112);ax.set_xticks([0,25,50,75,100],['0%','25%','50%','75%','100%'])
    ax.tick_params(axis='y',length=0)
    from matplotlib.patches import Patch
    ax.legend([Patch(color=c) for c in colors],[f'{st} ({STAGE_INFO[st][0].lower()})' for st in STAGES],
        loc='upper center',bbox_to_anchor=(.45,1.08),ncol=3,frameon=False,handlelength=1,handleheight=1)
    ax.set_xlabel(f'Tỷ lệ mẫu thiết kế {FB_ADS} theo giai đoạn phễu (số trong ô = số mẫu)')
    fig.tight_layout();out['07_funnel']=save_chart(fig,'07_funnel')
    # Google Ads funnel: per company, web ads by estimated stage plus app-install videos as their own
    # bottom-of-funnel segment, so the app share is visible next to the web formats.
    picks=[b for b in trend if b['show'] and b['google']]
    rows=[(f'{i+1}. {b["name"]}',b) for i,b in enumerate(top)]+[None,('NGOÀI TOP 10 · THAM KHẢO','header')]+[(b['name'],b) for b in picks]
    seg_colors=[MINT,EMERALD,PINE,LIME];seg_ink=[INK,INK,'#FFFFFF',INK]
    seg_names=['Nhận biết (web)','Cân nhắc (web)','Chuyển đổi (web)','Chuyển đổi: video kéo cài app']
    fig,ax=plt.subplots(figsize=(11,8.2))
    for i,row in enumerate(rows):
        if row is None or row[1]=='header':continue
        name,b=row;web=[r for r in b['google'] if not base.app_row(r)]
        n=g_stage_counts(web)+[len(b['app'])];tot=sum(n);left=0
        if not tot:
            ax.text(1,i,'Chưa thấy Google Ads',va='center',fontsize=10,color=MUTED);continue
        for j,v in enumerate(n):
            w=100*v/tot
            if v:ax.barh(i,w,left=left,color=seg_colors[j],height=.68,edgecolor='white',linewidth=1.2,hatch='//' if j==3 else None)
            if w>=7:ax.text(left+w/2,i,str(v),ha='center',va='center',color=seg_ink[j],fontsize=11,fontweight=600)
            left+=w
        ax.text(101.5,i,f"{tot} QC · {len(g_active(b))} còn chạy",va='center',fontsize=10,color=MUTED)
    ax.set_yticks([i for i,r in enumerate(rows) if r],[r[0] for r in rows if r])
    for t in ax.get_yticklabels():
        if t.get_text().startswith('NGOÀI'):t.set_color(MUTED);t.set_fontsize(9);t.set_fontweight(700)
    ax.invert_yaxis();ax.set_xlim(0,122);ax.set_xticks([0,25,50,75,100],['0%','25%','50%','75%','100%'])
    ax.tick_params(axis='y',length=0)
    ax.legend([Patch(facecolor=c,hatch='//' if j==3 else None,edgecolor='white') for j,c in enumerate(seg_colors)],seg_names,
        loc='upper center',bbox_to_anchor=(.45,1.09),ncol=4,frameon=False,handlelength=1.4,handleheight=1,fontsize=11)
    ax.set_xlabel(f'Tỷ lệ quảng cáo {GG} theo giai đoạn phễu, xếp theo chữ đọc được trên quảng cáo (số trong ô = số quảng cáo, gồm cả mẫu đã dừng)')
    fig.tight_layout();out['08_google_funnel']=save_chart(fig,'08_google_funnel')
    return out


# ---------------------------------------------------------------- report content
# Page items: ('cover',title,sub,stats) ('toc',) ('section',title,intro) ('kicker',t) ('h',t,toc) ('label',t)
# ('p',t) ('lead',bold,t) ('why',t) ('kp',num,lead,t) ('stats',[(n,label)]) ('sub',t) ('meta',t)
# ('sample',ad) ('image',path,caption,w,maxh) ('link',label,url) ('table',headers,rows,widths)
def P(t):return ('p',t)
def LEAD(b,t):return ('lead',b,t)
def SUB(t):return ('sub',t)
def META(t):return ('meta',t)
def LINK(label,url):return ('link',label,url)
def IMG(path,caption,w=170,mh=110):return ('image',path,caption,w,mh)
def H(text,kicker=None,toc=None):
    """'Kicker | Heading' becomes a small brand label above an insight headline; toc = table-of-contents line."""
    if kicker is None and ' | ' in text:kicker,text=text.split(' | ',1)
    return ([('kicker',kicker)] if kicker else [])+[('h',text,toc)]


KEY_POINTS=[
  ('Top 10 dùng cả Facebook Ads lẫn Google Ads.',
   '{fb_top}/10 công ty Top 10 chạy Facebook Ads, {g_top}/10 có Google Ads ({g_top_active} còn chạy gần 29/10). Riêng video kéo cài app trên Google chỉ SSI và Vietcap còn chạy.'),
  ('Đối thủ dồn vào đáy phễu: cài app, mở tài khoản.',
   '{top_pct}% mẫu Facebook Ads của Top 10 nhắm chuyển đổi; Google Ads (app) bản chất là kéo cài app. Đầu và giữa phễu ít bên Top 10 đầu tư.'),
  ('Mỗi tầng phễu một kiểu nội dung.',
   'Ưu đãi (quà, phí, margin) cho đáy phễu; tính năng sản phẩm cho giữa phễu; kiến thức, giải thưởng cho đầu phễu.'),
]
PATTERNS=[('Đầu phễu · Kiến thức','Câu hỏi của người mới → lời giải/chuyên gia → theo dõi trang, xem tiếp. Top 10 ít làm: cơ hội để chiếm chỗ trong tâm trí trước khi họ chọn app.'),
   ('Giữa phễu · Tính năng','Một nhu cầu cụ thể → demo giao diện/lợi ích → trang sản phẩm. Giúp khác biệt khi ai cũng tặng quà.'),
   ('Đáy phễu · Ưu đãi','Quà, phí, margin → điều kiện rõ → cài app/mở tài khoản. Đông đối thủ nhất: phải hơn về mức quà hoặc độ rõ ràng.')]
SECTIONS=['Bức tranh chung','Phễu: đối thủ đánh vào đâu?','Hồ sơ Top 10','Ngoài Top 10 — đáng tham khảo','Thư viện video','Từ quảng cáo đến trang đích']


def cover_stats(data):
    return [('25','công ty theo dõi'),(f"{data['totals']['fb']}",'quảng cáo Facebook Ads'),
            (str(sum(len(b['google']) for b in data['profiles'])),'quảng cáo Google Ads'),(str(len(data['videos'])),'video phân tích')]


def groups(data):
    bs=data['profiles']
    top=[b for b in bs if b['group']=='Top 10' and b['show']]
    picks=[b for b in bs if b['group']!='Top 10' and b['show']]
    idle=[b['name'] for b in bs if b['group']=='Top 10' and not b['running']]
    others=[b for b in bs if b['group']!='Top 10' and not b['show']]
    return top,picks,idle,others


def section_intros(data):
    top,picks,idle,others=groups(data)
    fs=funnel_summary(data)
    return [
      'Hai kênh Facebook Ads và Google Ads: ai chạy, định dạng, nội dung, điểm đến, quy mô. Top 10 xếp theo thứ hạng; ngoài Top 10 để tham khảo.',
      f'{fs["top_pct"]}% mẫu Facebook Ads của Top 10 nhắm đáy phễu (cài app, mở tài khoản). Ai đang chiếm đầu và giữa phễu.',
      f'{len(top)} công ty có quảng cáo, mỗi hồ sơ gồm cả Facebook Ads và Google Ads. Bỏ qua {" và ".join(idle)}: không chạy Facebook Ads, không có Google Ads còn chạy.' if idle else f'{len(top)} công ty có quảng cáo.',
      f'Chỉ phân tích {len(picks)}/15 công ty nổi bật hoặc có cách làm Top 10 chưa triển khai. {len(others)} công ty còn lại được tóm tắt trong một bảng.',
      f"{len(data['videos'])} video đã lưu, mỗi video kèm mạch nội dung, cách thể hiện và nhận định.",
      'Ảnh chụp lịch sử của trang sau cú click, đặt cạnh quảng cáo dẫn tới trang đó.']


def profile_blocks(b):
    fr=b['fb'];ar=b['app'];gr=b['google'];ga=g_active(b)
    blocks=[*H(f"{rname(b)} | {b['title']}" if b.get('rank') else b['title'],f"{group_label(b)} · {rname(b)}",f"{rname(b)} — {b['title']}")]
    if b['why']:blocks.append(('why',b['why']))
    blocks += [P(b['analysis']),
        ('stats',[(str(len(fr)),f'{FB_ADS}: quảng cáo'),(str(b['designs'] if fr else 0),f'{FB_ADS}: mẫu thiết kế'),
                  (str(len(gr)),f'{GG}: quảng cáo'),(str(len(ga)),f'{GG}: còn chạy')])]
    blocks.append(('label',FB_ADS))
    if fr:
        blocks.append(LEAD('Phễu:',stage_line(b).split(': ',1)[1]+'.'))
        blocks.append(META(f'Định dạng: '+base.counts(fr,'format')+'.'))
        for i,r in enumerate(b['gallery']):blocks.append(('sample',dict(r,n=i+1)))
    else:blocks.append(P(f'Không chạy {FB_ADS} trong kỳ.'))
    blocks.append(('label',GG))
    if gr:
        web=[r for r in gr if not base.app_row(r)]
        blocks.append(LEAD('Định dạng:',g_mix(gr)+f'. {len(ga)} mẫu còn chạy gần 29/10.'))
        blocks.append(LEAD('Phễu web (ước tính):',' · '.join(f'{st} {v}' for st,v in zip(STAGES,g_stage_counts(web)))+'. Theo thông điệp; thiếu thông điệp thì theo định dạng.'))
        for note in GNOTES.get(b['name'],[]):blocks.append(META('Nhận xét: '+note))
        for r in b['g_gallery']:blocks.append(('sample',r))
        if ar:
            blocks.append(('label',GG_ADS))
            sig=Counter(s.strip() for r in ar for s in r['signals'].split(';') if s.strip())
            blocks.append(LEAD('Phễu:',f"cả {len(ar)} video mang nhãn Google Play = chuyển đổi (kéo cài app); {len(b['recent'])} còn chạy gần 29/10."))
            if sig:blocks.append(LEAD('Video app nói gì:',' · '.join(f'{k} {v}' for k,v in sig.most_common(5))+'.'))
            for r in b['app_gallery']:blocks.append(('sample',r))
            if not b['app_gallery']:blocks.append(META('Chưa có ảnh xem trước cho video app (thiếu YouTube ID); xem trên Google Ads Transparency.'))
        else:blocks.append(META(f'Không có video {GG_ADS}.'))
    else:blocks.append(P(f'Chưa thấy quảng cáo {GG} trong dữ liệu thu thập.'))
    if b['videos']:
        blocks.append(META('Video phân tích ở phần Thư viện video: '+', '.join(v['title'].split('|')[-1].strip() for v in b['videos'])+'.'))
    return blocks


def others_table(others):
    return ('table',['Công ty',FB_ADS,GG,'Hướng nội dung quan sát được'],
        [[b['name'],f"{len(b['fb'])} QC",f"{len(b['google'])} ({len(g_active(b))} còn chạy)",b['title']] for b in others],
        [30,22,30,90])


def funnel_pages(data,chart):
    fs=funnel_summary(data);top,picks,idle,others=groups(data);L=fs['leaders']
    t,r=fs['top'],fs['rest'];j=lambda xs:', '.join(xs) or '—'
    app_cos=[b['name'] for b in data['profiles'] if b['app']]
    topn={b['name']:b for b in top}
    light=[f"{n} ({sum(stage_counts(topn[n]['fb']))} mẫu)" for n in L['Cân nhắc']+L['Nhận biết'] if n in topn]
    gf=google_funnel_summary(data);rank={b['name']:i+1 for i,b in enumerate(data['profiles'][:10])}
    def split(names):
        t=[f'#{rank[n]} {n}' for n in names if n in rank];o=[n for n in names if n not in rank]
        return f"Top 10: {', '.join(t) or '—'}\nNgoài Top 10: {', '.join(o) or '—'}"
    return [
      [('section',f'Phần 2 · {SECTIONS[1]}',section_intros(data)[1]),
       *H('Phễu | Tiêu chí xếp quảng cáo vào từng giai đoạn',toc='Phễu: tiêu chí phân loại'),
       ('table',['Giai đoạn',f'{FB_ADS} (nút CTA + link + trang đích thật)',f'{GG} (theo chữ đọc được trên quảng cáo)'],
        [[f'{st} ({STAGE_INFO[st][0].lower()})',*STAGE_RULES[st]] for st in STAGES],[30,72,68]),
       META('Nội dung không quyết định giai đoạn ở Facebook Ads: video kiến thức nhưng nút dẫn về cài app vẫn tính Chuyển đổi. Facebook Ads đếm theo mẫu thiết kế (đa số các quảng cáo cùng mẫu).'),
       META(GSTAGE_NOTE)],
      [*H('Phễu | Đối thủ dồn ngân sách vào đáy phễu',toc='Phễu: ai đánh vào giai đoạn nào?'),
       IMG(chart['07_funnel'],f'Top 10 xếp theo thứ hạng; ngoài Top 10 để tham khảo. Đếm theo mẫu thiết kế để 427 bản sao của cùng một mẫu (LPS) chỉ tính 1 lần. Theo số quảng cáo: {fs["ads_conv"]}/{fs["ads_total"]} quảng cáo Facebook Ads là chuyển đổi.',170,150),
       LEAD('Top 10:',f'{t[2]}/{sum(t)} mẫu ({fs["top_pct"]}%) là chuyển đổi, {t[1]} cân nhắc, {t[0]} nhận biết. Ngoài Top 10 cân bằng hơn: {fs["rest_pct"]}% chuyển đổi.'),
       LEAD(f'{GG_ADS}:',f'cả {data["totals"]["google_app"]} video kéo cài app của {len(app_cos)} công ty nằm ở đáy phễu ({j(app_cos)}). Phễu Google Ads ở trang sau.')],
      [*H('Phễu | Google Ads: app nằm ở đáy phễu, web trải ba tầng',toc='Phễu Google Ads và Google Ads (app)'),
       IMG(chart['08_google_funnel'],'Mỗi thanh = toàn bộ quảng cáo Google Ads của một công ty (gồm cả mẫu đã dừng). Phần gạch chéo = video kéo cài app (nhãn Google Play).',170,150),
       LEAD('Top 10:',f"{gf['top_app_cos']}/10 công ty có video kéo cài app ({gf['top_app']} video); {gf['top_app_recent']} còn chạy gần 29/10: {gf['top_recent_names']}."),
       LEAD('Ngoài Top 10:',f"{gf['rest_app']} video kéo cài app, nhiều nhất {gf['rest_leaders']}."),
       LEAD('Cách gán giai đoạn:','video có nhãn Google Play = chuyển đổi (kéo cài app). Quảng cáo web ước tính theo thông điệp: ưu đãi/mở tài khoản → chuyển đổi; tính năng/app/tích sản → cân nhắc; kiến thức/uy tín → nhận biết. Không có thông điệp thì theo định dạng: Search → cân nhắc, ảnh và video YouTube → nhận biết.')],
      [*H('Phễu | Mỗi giai đoạn: ai làm, làm thế nào',toc='Phễu: cách làm theo từng giai đoạn'),
       ('table',['Giai đoạn','Đối thủ tập trung','Cách làm điển hình'],[
         ['Chuyển đổi (đáy phễu)',split(L['Chuyển đổi']),'Quà cổ phiếu, miễn phí, margin ưu đãi + nút Cài đặt ngay/Đăng ký ngay, link thẳng App Store, Google Play. MBS mở đầu bằng kiến thức (breakout) nhưng vẫn kéo về cài app. Google Ads (app) cũng nằm ở đây.'],
         ['Cân nhắc (giữa phễu)',split(L['Cân nhắc']),'Giới thiệu tính năng cụ thể (DTRADE, API/MCP, VinaStalk, công cụ lọc), nút Xem chi tiết về trang sản phẩm. Không tặng quà mà chứng minh app tốt hơn.'],
         ['Nhận biết (đầu phễu)',split(L['Nhận biết']),'Video kiến thức cho người mới, giải thưởng, sự kiện; tối ưu lượt xem video và thích trang. Chủ yếu công ty ngoài Top 10.'],
       ],[34,40,96]),
       META('Cột “Đối thủ tập trung”: Top 10 ghi kèm thứ hạng (#); công ty ngoài Top 10 ghi ở dòng “Ngoài Top 10”.'),
       ('label','Hàm ý'),
       LEAD('Đáy phễu đông nhất:','gần như mọi công ty lớn cùng tặng quà để kéo cài app. Muốn thắng ở đây phải hơn về mức ưu đãi hoặc nói điều kiện rõ hơn.'),
       LEAD('Giữa và đầu phễu còn trống:',f'ở Top 10 chỉ {j(light)} chủ yếu chạy hai tầng này, và quy mô nhỏ. Nội dung kiến thức và demo tính năng ít đối thủ hơn, giúp có người dùng biết thương hiệu trước khi họ so ưu đãi.'),
       LEAD('Giới hạn:','không có ngân sách, lượt hiển thị hay chuyển đổi của đối thủ. Phễu cho thấy họ chọn làm gì, chưa cho thấy cách nào hiệu quả hơn.')],
    ]


def report_pages(data,chart):
    top,picks,idle,others=groups(data);intro=section_intros(data)
    def sec(i):return ('section',f'Phần {i+1} · {SECTIONS[i]}',intro[i])
    overview=[
      [*H('Top 10 | Ai chạy Facebook Ads, ai chạy Google Ads?',toc='Top 10: ai chạy kênh nào?'),
       IMG(chart['02_top10'],'Xếp theo thứ hạng Top 10. Xanh nhạt: có chạy nhưng đã dừng; xanh đậm: còn chạy gần 29/10.',170,125),
       LEAD('Google Ads:','gồm Search (chữ), ảnh hiển thị, video YouTube và video kéo cài app (nhãn Google Play). Cột cuối tách riêng nhóm kéo cài app.'),
       LEAD('Khoảng trống dữ liệu:','MBS và Mirae Asset chưa có tài khoản Google trong nguồn, nên “Không thấy” ở hai công ty này chưa chắc là không chạy.')],
      [*H('Facebook Ads · Định dạng | Ảnh, video và DCO cùng được sử dụng',toc='Facebook Ads: định dạng'),
       IMG(chart['03_formats'],'Chỉ Facebook Ads. Mẫu số: 7 công ty Top 10 có Facebook Ads và 15 công ty ngoài Top 10. Một công ty có thể dùng nhiều loại.',170,115),
       LEAD('DCO là nhóm riêng:','nhãn nội dung động không cho biết asset là ảnh hay video. Ảnh trong hồ sơ là creative gốc tải từ Ad Library; storyboard chỉ lấy từ video có liên hệ xác minh.'),
       LEAD('Cách thể hiện theo mục tiêu:','motion chữ cho ưu đãi; người thật giải thích kiến thức; demo màn hình cho tính năng và quy trình. Thư viện video có ví dụ cho từng cách.')],
      [*H('Facebook Ads · Nội dung | Ba hướng nội dung lặp lại',toc='Facebook Ads: nội dung'),
       IMG(chart['04_content'],'Số công ty có caption đại diện được đối chiếu; mức hiện diện tối thiểu, không phải tỷ trọng toàn bộ quảng cáo.',170,115),
       LEAD('Ưu đãi / chi phí:','quà cổ phiếu, miễn phí, margin, thưởng mở tài khoản hoặc giới thiệu. Ví dụ: SSI, MBS, KIS, LPS.'),
       LEAD('Tính năng / sản phẩm:','DTRADE, API/MCP, VinaStalk, công cụ lọc, giao diện mới. Ví dụ: VNDirect, DNSE, Shinhan, KBSV.'),
       LEAD('Kiến thức / phân tích:','giải thích khái niệm, giải đáp thắc mắc, sự kiện chuyên gia. Ví dụ: VPS, HSC, HD Securities. Quy trình thao tác được minh họa riêng bằng video SSI và DNSE.')],
      [*H('Facebook Ads · Điểm đến | Không phải mẫu nào cũng đi thẳng vào app',toc='Facebook Ads: điểm đến sau cú click'),
       IMG(chart['05_destinations'],'Chỉ Facebook Ads: điểm đến theo link và nút CTA. Các nhóm có thể chồng lấp ở cấp công ty.',170,115),
       LEAD('Ưu đãi →','app: LPS, MBS; web chương trình/onboarding: KIS, SSI, VPBankS.'),
       LEAD('Tính năng →','web sản phẩm: VNDirect, DNSE, AAS. Kiến thức → theo dõi/sự kiện: VPS, HSC, HD Securities.'),
       LEAD('Ở lại Facebook:',DEST_HELP.split(' = ',1)[1]),
       LEAD('Lưu ý:','web có form chưa chắc là mở tài khoản — cần đọc mục đích trang. Google Ads không công bố link đích; QR hay logo App Store trong clip chỉ là bằng chứng nội dung.')],
      [*H('Quy mô | Số quảng cáo nhiều chưa chắc nhiều ý tưởng',toc='Quy mô: số quảng cáo hai kênh'),
       IMG(chart['06_volume_design'],'Hai cột trái: quảng cáo còn chạy gần 29/10. Hai cột phải: số ý tưởng trong các quảng cáo đó. Số trong ngoặc = Google cộng dồn cả mẫu đã dừng. Không phải lượt hiển thị hay ngân sách.',170,135),
       LEAD('Cách đọc:','Facebook: 1 mẫu thiết kế = 1 ý tưởng (Meta gắn sẵn mã). Google: 1 ý tưởng = 1 video (YouTube ID), 1 thông điệp Search + trang đích, hoặc 1 thông điệp banner + con số ưu đãi (báo cáo tự gom, ước tính).'),
       *[P('• '+t) for t in chart_notes(data)['06_volume_design']],
       LEAD('Quy luật:','lời hứa nội dung đi cùng bước tiếp theo — ưu đãi gắn hành động cụ thể, tính năng cần minh họa sử dụng, kiến thức mở đầu quan hệ.'),
       LEAD('Gợi ý thử nghiệm:','cùng lợi ích và điểm đến, so demo thao tác với thông điệp ưu đãi ngắn. Chưa có CPA hay chuyển đổi để kết luận phương án nào tốt hơn.')],
    ]
    pages=[
      [('cover','Đối thủ quảng cáo:\nkênh nào, nội dung gì?',
        'Top 10 và 15 công ty ngoài Top 10 · Facebook Ads và Google Ads · Snapshot 29/10/2026',cover_stats(data)),
       ('label','Ba kết luận để đọc nhanh'),
       *[('kp',f'{i+1:02d}',a,b.format(**funnel_summary(data))) for i,(a,b) in enumerate(KEY_POINTS)],
       IMG(chart['01_channels'],'Tỷ lệ công ty chạy từng kênh. “Còn chạy gần 29/10” = lần hiển thị cuối dưới 3 ngày trước mốc chốt.',150,72),
       META('PowerPoint có video nhúng; PDF và Word dùng storyboard kèm liên kết tới thư mục media. Bấm vào dòng trong mục lục để tới trang tương ứng.')],
      [('kicker','Mục lục'),('h','Nội dung báo cáo',None),('toc',)],
      [sec(0),*H('Cách đọc | Hai kênh quảng cáo trong báo cáo',toc='Cách đọc: Facebook Ads và Google Ads'),
       P('Mọi số liệu, biểu đồ và mẫu đều ghi rõ kênh. Biểu đồ định dạng, nội dung, điểm đến và quy mô chỉ dùng dữ liệu Facebook Ads, vì Google không công bố đủ chi tiết.'),
       ('table',['Kênh','Là gì','Thấy được gì','Không thấy'],[list(g) for g in GLOSSARY],[28,52,52,38]),
       ('label','Facebook và Google đếm “quảng cáo” khác nhau'),
       ('table',['',FB_ADS,GG],[list(r) for r in COUNT_DIFF],[28,66,76]),
       META('Vì vậy khi so hai kênh, báo cáo dùng quảng cáo đang chạy và số ý tưởng, không dùng tổng số quảng cáo.'),
       ('label','Phễu quảng cáo: ba giai đoạn'),
       ('table',['Giai đoạn','Mục tiêu','Nhận biết qua'],[[f'{st} ({STAGE_INFO[st][0].lower()})',STAGE_INFO[st][1],STAGE_INFO[st][2]] for st in STAGES],[34,66,70]),
       META('Thư viện quảng cáo không công bố mục tiêu chiến dịch. Giai đoạn được suy ra từ nút CTA và trang đích thật của từng quảng cáo.')],
      overview[0],*overview[1:],
      *funnel_pages(data,chart),
    ]
    for i,b in enumerate(top):pages.append(([sec(2)] if i==0 else [])+profile_blocks(b))
    for i,b in enumerate(picks):pages.append(([sec(3)] if i==0 else [])+profile_blocks(b))
    if others:
        pages.append([*H('Các công ty còn lại ngoài Top 10','Ngoài Top 10 · Tóm tắt','Các công ty còn lại (bảng tóm tắt)'),
            P('Có quảng cáo nhưng không nổi bật hơn hoặc chưa có cách làm khác Top 10; chỉ ghi nhận để tra cứu.'),
            others_table(others)])
    for i,v in enumerate(data['videos']):
        blocks=([sec(4)] if i==0 else [])+[*H(v['title'].split(' | ',1)[-1],f"Video · {CHANNEL_NAME[v['channel']]} · {v['brand']}",
                 f"{v['brand']} — {v['title'].split(' | ',1)[-1]}"),
            META(f"{float(v['duration']):g} giây · tỷ lệ {v['aspect']}"),
            LEAD('Mạch nội dung:',v['flow']),LEAD('Cách thể hiện:',v['content']),LEAD('Nhận định:',v['finding']),
            IMG(v['storyboard'],'Khung hình theo thứ tự thời gian của một video, không phải nhiều mẫu độc lập.',170,140),
            LINK('Mở file video MP4 (trong thư mục media) →','media/'+Path(v['video']).name),LINK('Xem nguồn quảng cáo →',v['url'])]
        if v['caption']:blocks.append(META('Trích caption: '+short(v['caption'],420)))
        pages.append(blocks)
    landing_cases=[b for b in top+picks if b['landing_preview']][:6]
    for i in range(0,len(landing_cases),2):
        names=', '.join(b['name'] for b in landing_cases[i:i+2])
        blocks=([sec(5)] if i==0 else [])+[*H('Ảnh chụp trang sau quảng cáo','Facebook Ads · Điểm đến','Trang đích: '+names),
            META('Ảnh chụp lịch sử theo URL cuối trong cache. Trang có thể đã thay đổi; không xác nhận tỷ lệ chuyển đổi.')]
        for b in landing_cases[i:i+2]:
            item=b['landing_preview']
            blocks += [SUB(b['name']+' · '+short(item['title'],95)),
                IMG(item['image'],'Từ quảng cáo Facebook Ads '+item['ad_id'],160,83),
                LINK('Mở URL đích đã lưu →',item['url'])]
        pages.append(blocks)
    methodology=[('section','Phụ lục',None)]
    for item in base.make_pages(data)[-1]:
        if item[0] in ('p','h'):
            text=item[1].replace('evidence.json','evidence_media.json').replace('source_manifest.json','source_manifest_media.json')
            text=text.replace('Tái tạo bằng build_executive_report.py với python-docx, reportlab, Pillow và pypdf.',
                'Tái tạo bằng build_media_report.py; dùng thêm matplotlib, python-pptx, PyMuPDF, playwright, ffmpeg và ffprobe. Ảnh quảng cáo Facebook Ads là creative gốc tải lại từ Ad Library (thư mục originals/).')
            if item[0]=='h':methodology += H(text,'Phụ lục',text)
            else:
                lead,sep,rest=text.partition(': ')
                methodology.append(LEAD(lead+':',rest) if sep and len(lead)<20 else P(text))
        else:methodology.append(item)
    pages.append(methodology)
    return pages


def sample_text(r):
    if r.get('channel')=='google':return r['text']
    dest=r['landing_type'] or r['dest'] or 'chưa xác minh'
    cards=f" · {r['cards']} card" if r.get('cards',1)>1 else ''
    via=r.get('via','')
    note=('' if r.get('original') and not via else
          '  ·  Ảnh: khung hình từ video đã lưu (quảng cáo đã bị gỡ khỏi Ad Library)' if via=='saved video' else
          f'  ·  Ảnh gốc từ quảng cáo cùng thiết kế {via} (bản này đã bị gỡ khỏi Ad Library)' if via else
          '  ·  Ảnh xem trước 600px (quảng cáo đã bị gỡ khỏi Ad Library)')
    return (f"{FB_ADS} · Mẫu {r['n']} · {r['format']}{cards}",short(r['caption'],480),
            f"Phễu: {r.get('stage') or 'chưa rõ'}  ·  CTA: {r['cta'] or 'chưa rõ'}  ·  Điểm đến: {dest}{note}",'Xem quảng cáo gốc → Ad ID '+r['ad_archive_id'])


# ---------------------------------------------------------------- A4 report renderers (DSC)
def register_fonts():
    for name,f in [('DSC-R',FONT),('DSC-S',SEMI),('DSC-B',BOLD)]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(f)))
    pdfmetrics.registerFontFamily('DSC-R',normal='DSC-R',bold='DSC-B',italic='DSC-R',boldItalic='DSC-B')


def render_pdf(pages,path):
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (BaseDocTemplate,PageTemplate,Frame,PageBreak,Spacer,Table,TableStyle,
        KeepTogether,Image as RLImage)
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.platypus.tableofcontents import TableOfContents
    register_fonts();C=colors.HexColor;W=172*mm
    def st(name,font,size,lead,color=INK,**kw):
        return ParagraphStyle(name,fontName=font,fontSize=size,leading=lead,textColor=C(color),**kw)
    S=dict(p=st('p','DSC-R',9.5,14.2,spaceAfter=6),h=st('h','DSC-B',17,21,spaceAfter=5),
        kicker=st('k','DSC-S',8,10,ACCENT,spaceAfter=3),label=st('l','DSC-B',11,14,spaceBefore=10,spaceAfter=4),
        sub=st('s','DSC-S',10,13,ACCENT,spaceAfter=3),meta=st('m','DSC-R',8,11,MUTED,spaceAfter=5),
        link=st('a','DSC-S',8.5,11,ACCENT,spaceAfter=4),cap=st('c','DSC-R',7.5,10,MUTED,spaceAfter=8),
        cell=st('cell','DSC-R',8.5,11),th=st('th','DSC-S',8.5,11),
        kpn=st('kpn','DSC-B',15,18,ACCENT),kpt=st('kpt','DSC-R',9.5,13.6),
        snum=st('sn','DSC-B',18,21),slab=st('sl','DSC-R',7.5,9.5,MUTED),
        sec=st('sec','DSC-B',8.5,11,'#FFFFFF'),secintro=st('si','DSC-R',8.5,12,ON_DARK_MUTED),
        whyl=st('wl','DSC-S',8,10,ACCENT,spaceAfter=2),whyt=st('wt','DSC-R',9.5,13.6),
        ckick=st('ck','DSC-S',8,10,MINT,spaceAfter=8),ctitle=st('ct','DSC-B',26,31,'#FFFFFF',spaceAfter=8),
        csub=st('cs','DSC-R',10,14,ON_DARK_MUTED,spaceAfter=14),cnum=st('cn','DSC-B',22,25,LIME),
        clab=st('cl','DSC-R',8,10,ON_DARK_MUTED))
    def para(s,style='p'):return Paragraph(escape(clean(s)).replace('\n','<br/>'),S[style])
    def pad(t,l=0,r=0,tp=0,b=0):return [('LEFTPADDING',(0,0),(-1,-1),l),('RIGHTPADDING',(0,0),(-1,-1),r),('TOPPADDING',(0,0),(-1,-1),tp),('BOTTOMPADDING',(0,0),(-1,-1),b)]
    def stats_table(stats,num,lab,bg=None):
        t=Table([[[para(n,num),para(l,lab)] for n,l in stats]],colWidths=[W/len(stats)]*len(stats))
        style=[('VALIGN',(0,0),(-1,-1),'TOP')]+pad(t,8 if bg else 0,0,7,7)
        if bg:style+=[('BACKGROUND',(0,0),(-1,-1),C(bg)),('LINEAFTER',(0,0),(-2,-1),2.5,colors.white)]
        t.setStyle(TableStyle(style));return t
    def strip(width):
        tot=sum(f for _,f in STRIP)
        t=Table([['']*len(STRIP)],colWidths=[width*f/tot for _,f in STRIP],rowHeights=[2.4*mm])
        t.setStyle(TableStyle([('BACKGROUND',(i,0),(i,0),C(c)) for i,(c,_) in enumerate(STRIP)]+pad(t)));return t
    def picture(path,maxw,maxh):
        with Image.open(ROOT/path) as im:w,hg=im.size
        width=min(maxw,maxh*w/hg);img=RLImage(str(ROOT/path),width=width,height=width*hg/w);img.hAlign='LEFT';return img
    counter=[0]
    def toc_mark(flow,level,text):
        counter[0]+=1;flow.toc=(level,clean(text),f'toc{counter[0]}');return flow
    toc=TableOfContents(dotsMinLevel=1)
    toc.levelStyles=[st('t0','DSC-B',10.5,13,INK,spaceBefore=7,spaceAfter=1),
                     st('t1','DSC-R',9,11.6,INK,leftIndent=12,firstLineIndent=0)]
    story=[]
    for pi,page in enumerate(pages):
        if pi:story.append(PageBreak())
        for item in page:
            k=item[0]
            if k=='cover':
                _,title,sub,stats=item
                inner=[para('BÁO CÁO ĐỐI THỦ · NGÀNH CHỨNG KHOÁN','ckick'),para(title,'ctitle'),para(sub,'csub'),
                       stats_table(stats,'cnum','clab')]
                box=Table([[inner]],colWidths=[W]);box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),C(GUNMETAL))]+pad(box,18,18,20,12)))
                story += [box,strip(W),Spacer(1,8)]
            elif k=='toc':story.append(toc)
            elif k=='section':
                _,title,intro=item
                cell=[para(title.upper(),'sec')]+([para(intro,'secintro')] if intro else [])
                t=Table([[cell]],colWidths=[W]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),C(GUNMETAL))]+pad(t,10,10,7,8)))
                toc_mark(t,0,title)
                story += [t,Spacer(1,12)]
            elif k=='h':
                hp=para(item[1],'h')
                if item[2]:toc_mark(hp,1,item[2])
                story += [hp,HRFlowable(width='100%',thickness=.7,color=C(INK),spaceBefore=2,spaceAfter=9)]
            elif k=='label':story += [para(item[1],'label'),HRFlowable(width='100%',thickness=.7,color=C(INK),spaceBefore=0,spaceAfter=2)]
            elif k in ('p','kicker','sub','meta'):story.append(para(item[1].upper() if k=='kicker' else item[1],k))
            elif k=='lead':
                story.append(Paragraph(f'<font name="DSC-B">{escape(clean(item[1]))}</font> '+escape(clean(item[2])),S['p']))
            elif k=='why':
                t=Table([[[para('Vì sao đáng tham khảo','whyl'),para(item[1],'whyt')]]],colWidths=[W])
                t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),C(MINT_50)),('LINEABOVE',(0,0),(-1,0),2.5,C(LIME))]+pad(t,10,10,8,8)))
                story += [t,Spacer(1,8)]
            elif k=='kp':
                _,n,lead,text=item
                t=Table([[para(n,'kpn'),Paragraph(f'<font name="DSC-B">{escape(lead)}</font><br/>{escape(text)}',S['kpt'])]],colWidths=[14*mm,W-14*mm])
                t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.5,C(LINE))]+pad(t,0,0,7,7)))
                story.append(t)
            elif k=='stats':story += [stats_table(item[1],'snum','slab',SURFACE_ALT),Spacer(1,6)]
            elif k=='sample':
                r=item[1];label,cap,meta,linklabel=sample_text(r)
                text=[para(label,'sub'),para(cap,'p'),para(meta,'meta'),
                      Paragraph(f'<link href="{escape(r["url"],{chr(34):"&quot;"})}" color="{ACCENT}">{escape(linklabel)}</link>',S['link'])]
                if r.get('strip'):
                    block=[picture(r['strip'],W,72*mm),Spacer(1,5)]+text
                else:
                    t=Table([[picture(r['image'],66*mm,92*mm),text]],colWidths=[72*mm,W-72*mm])
                    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]+pad(t,0,0,0,0)));block=[t]
                story += [Spacer(1,6),HRFlowable(width='100%',thickness=.5,color=C(LINE),spaceAfter=8),KeepTogether(block)]
            elif k=='link':
                story.append(Paragraph(f'<link href="{escape(item[2],{chr(34):"&quot;"})}" color="{ACCENT}">{escape(item[1])}</link>',S['link']))
            elif k=='image':
                img=picture(item[1],min(item[3]*mm,W),item[4]*mm)
                story.append(KeepTogether([Spacer(1,3),img,Spacer(1,3),para(item[2],'cap')]))
            elif k=='table':
                _,headers,rows,widths=item
                vals=[[para(v,'th') for v in headers]]+[[para(v,'cell') for v in row] for row in rows]
                tab=Table(vals,colWidths=[w*mm for w in widths] if widths else None,repeatRows=1,hAlign='LEFT')
                tab.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,C(INK)),
                    ('LINEBELOW',(0,1),(-1,-1),.5,C(LINE))]+pad(tab,4,4,5,5)))
                story += [tab,Spacer(1,7)]
            else:raise ValueError(item)
    def decorate(c,doc):
        x=0;tot=sum(f for _,f in STRIP)
        for color,f in STRIP:
            c.setFillColor(C(color));c.rect(x,297*mm-2.4*mm,210*mm*f/tot,2.4*mm,fill=1,stroke=0);x+=210*mm*f/tot
        c.setFont('DSC-S',7.5);c.setFillColor(C(MUTED))
        c.drawString(19*mm,286*mm,'QUẢNG CÁO ĐỐI THỦ CHỨNG KHOÁN  ·  29.10.2026')
        if doc.page>2:
            c.drawRightString(191*mm,286*mm,'← Mục lục');c.linkRect('','toc_page',(170*mm,284*mm,191*mm,290*mm),relative=0)
        c.setStrokeColor(C(INK));c.setLineWidth(.6);c.line(19*mm,15*mm,191*mm,15*mm)
        c.drawString(19*mm,10*mm,'Dữ liệu quan sát · Không phải xếp hạng hiệu quả')
        c.setFont('DSC-B',8);c.setFillColor(C(INK));c.drawRightString(191*mm,10*mm,str(doc.page))
        if doc.page==2:c.bookmarkPage('toc_page')
    class Doc(BaseDocTemplate):
        def afterFlowable(self,f):
            if hasattr(f,'toc'):
                level,text,key=f.toc
                self.canv.bookmarkPage(key);self.canv.addOutlineEntry(text,key,level=level,closed=False)
                self.notify('TOCEntry',(level,text,self.page,key))
    doc=Doc(str(path),pagesize=(210*mm,297*mm),rightMargin=19*mm,leftMargin=19*mm,topMargin=21*mm,bottomMargin=19*mm,
        title='Quảng cáo đối thủ chứng khoán – bản có media – 29/10/2026',author='')
    doc.addPageTemplates([PageTemplate('main',[Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id='f')],onPage=decorate)])
    doc.multiBuild(story)


def render_docx(pages,path):
    from docx import Document
    from docx.shared import Mm,Pt as DPt,RGBColor as DRGB
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    def rgb(h):return DRGB.from_string(h[1:])
    def font(style_or_run,size=None,color=INK,bold=None):
        f=style_or_run.font;f.name=FAMILY
        if size:f.size=DPt(size)
        f.color.rgb=rgb(color)
        if bold is not None:f.bold=bold
        rpr=style_or_run.element.get_or_add_rPr();rf=rpr.find(qn('w:rFonts'))
        if rf is None:rf=OxmlElement('w:rFonts');rpr.append(rf)
        for a in ('w:asciiTheme','w:hAnsiTheme','w:eastAsiaTheme','w:cstheme'):
            if rf.get(qn(a)) is not None:del rf.attrib[qn(a)]
        for a in ('w:ascii','w:hAnsi','w:cs'):rf.set(qn(a),FAMILY)
    def shade(cell,hexcolor):
        tcpr=cell._tc.get_or_add_tcPr();sh=OxmlElement('w:shd')
        sh.set(qn('w:val'),'clear');sh.set(qn('w:color'),'auto');sh.set(qn('w:fill'),hexcolor[1:]);tcpr.append(sh)
    def bottom_border(par,color=INK):
        ppr=par._p.get_or_add_pPr();b=OxmlElement('w:pBdr');e=OxmlElement('w:bottom')
        for k,v in [('val','single'),('sz','6'),('space','4'),('color',color[1:])]:e.set(qn('w:'+k),v)
        b.append(e);ppr.append(b)
    def add(text,size=10,color=INK,bold=False,after=6,before=0,doc_or_cell=None,style=None):
        par=(doc_or_cell or doc).add_paragraph(style=style);par.paragraph_format.space_after=DPt(after);par.paragraph_format.space_before=DPt(before)
        if text:font(par.add_run(clean(text)),size,color,bold)
        return par
    def link(par,label,url):
        hl=OxmlElement('w:hyperlink');hl.set(qn('r:id'),par.part.relate_to(url,RT.HYPERLINK,is_external=True))
        run=OxmlElement('w:r');pr=OxmlElement('w:rPr')
        rf=OxmlElement('w:rFonts');[rf.set(qn('w:'+a),FAMILY) for a in ('ascii','hAnsi','cs')];pr.append(rf)
        b=OxmlElement('w:b');pr.append(b);c=OxmlElement('w:color');c.set(qn('w:val'),ACCENT[1:]);pr.append(c)
        sz=OxmlElement('w:sz');sz.set(qn('w:val'),'17');pr.append(sz)
        run.append(pr);t=OxmlElement('w:t');t.text=label;run.append(t);hl.append(run);par._p.append(hl)
    def stats_row(stats,num_color,lab_color,bg):
        tab=doc.add_table(rows=1,cols=len(stats))
        for cell,(n,l) in zip(tab.rows[0].cells,stats):
            shade(cell,bg);cell.paragraphs[0].paragraph_format.space_after=DPt(0)
            font(cell.paragraphs[0].add_run(n),18,num_color,True);add(l,8,lab_color,after=2,doc_or_cell=cell)
        add('',after=2)
    def picture(path,maxw,maxh,where=None):
        with Image.open(ROOT/path) as im:iw,ih=im.size
        width=Mm(min(maxw,maxh*iw/ih))
        if where is None:doc.add_picture(str(ROOT/path),width=width)
        else:where.paragraphs[0].add_run().add_picture(str(ROOT/path),width=width)
    doc=Document();sec=doc.sections[0]
    sec.page_width=Mm(210);sec.page_height=Mm(297);sec.top_margin=Mm(18);sec.bottom_margin=Mm(18)
    sec.left_margin=sec.right_margin=Mm(19)
    normal=doc.styles['Normal'];font(normal,10,INK);normal.paragraph_format.line_spacing=1.2
    for name,size in [('Heading 1',11),('Heading 2',17)]:
        stl=doc.styles[name];font(stl,size,INK,True);stl.paragraph_format.space_before=DPt(4);stl.paragraph_format.space_after=DPt(8)
    upd=OxmlElement('w:updateFields');upd.set(qn('w:val'),'true');doc.settings.element.append(upd)
    hp=sec.header.paragraphs[0];font(hp.add_run('QUẢNG CÁO ĐỐI THỦ CHỨNG KHOÁN  ·  29.10.2026'),7.5,MUTED,True)
    fp=sec.footer.paragraphs[0];bottom_border(fp)
    fp=sec.footer.add_paragraph();font(fp.add_run('Dữ liệu quan sát · Không phải xếp hạng hiệu quả     |     '),7.5,MUTED)
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');fp._p.append(field)
    for pi,page in enumerate(pages):
        if pi:doc.add_page_break()
        for item in page:
            k=item[0]
            if k=='cover':
                _,title,sub,stats=item
                tab=doc.add_table(rows=1,cols=1);cell=tab.rows[0].cells[0];shade(cell,GUNMETAL)
                cell.paragraphs[0].paragraph_format.space_before=DPt(10)
                font(cell.paragraphs[0].add_run('BÁO CÁO ĐỐI THỦ · NGÀNH CHỨNG KHOÁN'),8,MINT,True)
                add(title,24,'#FFFFFF',True,6,doc_or_cell=cell);add(sub,10,ON_DARK_MUTED,after=10,doc_or_cell=cell)
                add('   '.join(f'{n} {l}' for n,l in stats),11,LIME,True,12,doc_or_cell=cell)
                add('',after=4)
            elif k=='toc':
                par=doc.add_paragraph();fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'TOC \\o "1-2" \\h \\z \\u')
                r=OxmlElement('w:r');t=OxmlElement('w:t');t.text='Mở bằng Word và chọn Update Field (F9) để hiện mục lục có số trang.';r.append(t);fld.append(r)
                par._p.append(fld)
            elif k=='section':
                par=add(None,style='Heading 1',after=2);font(par.add_run(item[1].upper()),11,ACCENT,True)
                if item[2]:add(item[2],9,MUTED,after=10)
            elif k=='kicker':add(item[1].upper(),8,ACCENT,True,2,6)
            elif k=='h':
                par=add(None,style='Heading 2' if item[2] else None,after=10);font(par.add_run(clean(item[1])),17,INK,True);bottom_border(par)
            elif k=='label':bottom_border(add(item[1],11,INK,True,6,8))
            elif k=='p':add(item[1])
            elif k=='lead':
                par=add(None);font(par.add_run(clean(item[1])+' '),10,INK,True);font(par.add_run(clean(item[2])),10)
            elif k=='why':
                tab=doc.add_table(rows=1,cols=1);cell=tab.rows[0].cells[0];shade(cell,MINT_50)
                font(cell.paragraphs[0].add_run('VÌ SAO ĐÁNG THAM KHẢO'),8,ACCENT,True);add(item[1],10,after=4,doc_or_cell=cell)
                add('',after=2)
            elif k=='kp':
                par=add(None,after=8);font(par.add_run(item[1]+'   '),13,ACCENT,True);font(par.add_run(item[2]),10,INK,True)
                font(par.add_run('\n'+item[3]),10)
            elif k=='stats':stats_row(item[1],INK,MUTED,SURFACE_ALT)
            elif k=='sub':add(item[1],10,ACCENT,True,3,6)
            elif k=='meta':add(item[1],8,MUTED,after=5)
            elif k=='link':link(add(None,after=4),item[1],item[2])
            elif k=='sample':
                r=item[1];label,cap,meta,linklabel=sample_text(r)
                if r.get('strip'):picture(r['strip'],172,72)
                else:picture(r['image'],110,95)
                add(label,10,ACCENT,True,3,4);add(cap);add(meta,8,MUTED,after=3);link(add(None,after=10),linklabel,r['url'])
            elif k=='image':
                picture(item[1],min(item[3],172),item[4]);add(item[2],7.5,MUTED,after=8)
            elif k=='table':
                _,headers,rows,widths=item
                tab=doc.add_table(rows=1,cols=len(headers))
                for row,values in [(tab.rows[0],headers)]+[(tab.add_row(),v) for v in rows]:
                    for cell,value in zip(row.cells,values):
                        cell.paragraphs[0].paragraph_format.space_after=DPt(3)
                        font(cell.paragraphs[0].add_run(clean(value)),8.5,INK,row is tab.rows[0])
            else:raise ValueError(item)
    doc.core_properties.title='Quảng cáo đối thủ chứng khoán – bản có media – 29/10/2026'
    doc.save(path)


# ---------------------------------------------------------------- deck (PPTX + PDF handout)
SW,SH,M=13.333,7.5,.5


class Deck:
    """Shared geometric layout for PPTX and a matching static PDF handout, DSC slide grammar:
    brand strip on top, kicker + headline, full-width hairline footer with title left, page number right."""
    def __init__(self):self.slides=[];self.current=None
    def _strip(self,y):
        x=0;tot=sum(f for _,f in STRIP)
        for color,f in STRIP:self.rect(x,y,SW*f/tot,.08,color);x+=SW*f/tot
    def _footer(self,dark=False):
        self.rect(M,6.95,SW-2*M,.012,'#4A514F' if dark else INK)
        self.text(TITLE,M,7.07,8,.25,9,ON_DARK_MUTED if dark else MUTED,'s')
        if len(self.slides)>3:self.text('← Mục lục',SW-M-2.6,7.07,1.6,.25,9,ON_DARK_MUTED if dark else ACCENT,'s',goto=self.agenda)
        self.text(str(len(self.slides)),SW-M-.6,7.05,.6,.28,11,'#FFFFFF' if dark else INK,'b',align='r')
    agenda=2   # 0-based index of the "Mục lục" slide
    def slide(self,title,kicker='Bức tranh chung'):
        self.current=[];self.slides.append(self.current)
        self.rect(0,0,SW,SH,'#FFFFFF');self._strip(0)
        self.text(kicker.upper(),M,.38,12.3,.25,10,ACCENT,'s')
        self.text(title,M,.66,12.3,.8,26,INK,'b')
        self._footer();return len(self.slides)-1
    def dark(self):
        self.current=[];self.slides.append(self.current)
        self.rect(0,0,SW,SH,GUNMETAL);self._strip(SH-.08);return len(self.slides)-1
    def section(self,num,title,desc):
        idx=self.dark()
        self.text(f'{num:02d}',M+.1,1.9,3,1.1,64,LIME,'b')
        self.text(title,M+.1,3.15,11.5,1,42,'#FFFFFF','b')
        self.text(desc,M+.1,4.3,10.5,1.2,19,ON_DARK_MUTED)
        self._footer(True);return idx
    def label(self,s,x,y,w):self.text(s.upper(),x,y,w,.25,10,ACCENT,'s')
    def rect(self,x,y,w,h,color):self.current.append(dict(type='rect',x=x,y=y,w=w,h=h,color=color))
    def text(self,s,x,y,w,h,size=16,color=INK,weight='r',url=None,align='l',goto=None):
        self.current.append(dict(type='text',text=clean(s),x=x,y=y,w=w,h=h,size=size,color=color,weight=weight,url=url,align=align,goto=goto))
    def image(self,path,x,y,w,h,url=None):self.current.append(dict(type='image',path=path,x=x,y=y,w=w,h=h,url=url))
    def video(self,v,x,y,w,h):self.current.append(dict(type='video',v=v,path=v['poster'],x=x,y=y,w=w,h=h))


STAGE_COLOR={'Nhận biết':(MINT,INK),'Cân nhắc':(EMERALD,INK),'Chuyển đổi':(PINE,'#FFFFFF')}
def _stage_chip(deck,stage,x,y):
    if stage not in STAGE_COLOR:return
    bg,fg=STAGE_COLOR[stage];deck.rect(x,y,1.3,.3,bg);deck.text(stage.upper(),x+.08,y+.05,1.18,.22,9,fg,'b')


def _cards(deck,items):
    for i,r in enumerate(items):
        x=M+i*2.8;cw=2.6
        deck.rect(x,1.98,cw,4.77,SURFACE_ALT)
        deck.image(r['image'],x+.1,2.08,cw-.2,2.35,r['url'])
        _stage_chip(deck,r.get('stage'),x+.1,2.08)
        if r.get('channel')=='google':
            deck.text(f"Mẫu {i+1} · {r['kind']}",x+.15,4.55,cw-.3,.3,10,ACCENT,'s')
            body=r['video_title'] if base.app_row(r) and r['video_title'] and not r['video_title'].endswith('.mp4') else r['text'][1]
            deck.text(short(body,110),x+.15,4.9,cw-.3,.8,11)
            state='còn chạy' if r['active']=='True' else 'đã dừng'
            deck.text(f"{vn_date(r['first_shown'])} → {vn_date(r['last_shown'])} · {state}",x+.15,5.75,cw-.3,.28,9,MUTED)
            deck.text(f"Phễu: {r['stage']}"+(' · có nhắc tải app' if gmsg(r)['app_hint'] else ''),x+.15,6.0,cw-.3,.3,9,MUTED)
            deck.text('Xem trên Google →',x+.15,6.38,cw-.3,.25,10,ACCENT,'s',url=r['url'])
        else:
            cards=f" · {r['cards']} card" if r.get('cards',1)>1 else ''
            deck.text(f"Mẫu {i+1} · {r['format'].replace('Dynamic (DCO)','DCO')}{cards} · {r.get('stage','')}",x+.15,4.55,cw-.3,.3,10,ACCENT,'s')
            deck.text(short(r['caption'],150),x+.15,4.9,cw-.3,1.35,11)
            deck.text('Xem quảng cáo gốc →',x+.15,6.38,cw-.3,.25,10,ACCENT,'s',url=r['url'])


def _side(deck,b,y=2.05):
    x=9.0
    if b['why']:
        deck.rect(x-.15,1.98,3.98,1.75,MINT_50);deck.rect(x-.15,1.98,3.98,.06,LIME)
        deck.label('Vì sao đáng tham khảo',x,2.15,3.7);deck.text(b['why'],x,2.45,3.7,1.2,12);y=3.95
    deck.label('Cách triển khai',x,y,3.83)
    deck.text(b['analysis'],x,y+.35,3.83,5.4-y-.35,16 if not b['why'] else 13)
    return x


def profile_slide(deck,b):
    """Each analysed company gets a Facebook Ads slide and a Google Ads slide (when it has either)."""
    kick=group_label(b)+' · '+b['name'];nm=rname(b)
    first=None
    if b['gallery']:
        first=deck.slide(nm+' | '+b['title'],kick+' · '+FB_ADS)
        deck.text(f"{FB_ADS}: {len(b['fb'])} quảng cáo · {b['designs']} mẫu thiết kế · định dạng: {base.counts(b['fb'],'format')}",M,1.5,12.3,.32,12,ACCENT,'s')
        _cards(deck,b['gallery']);x=_side(deck,b)
        deck.rect(x,5.55,3.83,.012,LINE)
        deck.label('Phễu Facebook Ads (số mẫu)',x,5.7,3.83)
        dests=Counter(dest_label(base.dest(r)) for r in b['fb'])
        deck.text(' · '.join(f'{st} {v}' for st,v in zip(STAGES,stage_counts(b['fb'])))+'. Điểm đến chính: '+(lambda t:t[0].lower()+t[1:])(dests.most_common(1)[0][0])+'.',x,6.0,3.83,.75,12,MUTED)
    web=[r for r in b['google'] if not base.app_row(r)]
    if b['g_gallery'] or (web and not first and not b['app']):
        idx=deck.slide(nm+' | '+(GG+' (web: Search, ảnh, YouTube)' if first is not None else b['title']),kick+' · '+GG+' (web)')
        first=idx if first is None else first
        wa=[r for r in web if r['active']=='True']
        deck.text(f"{GG} (web): {len(web)} quảng cáo ≈ {g_ideas(web)} ý tưởng · {len(wa)} còn chạy · {g_mix(web)}"+(f" · Video app: xem slide sau" if b['app'] else ''),M,1.5,12.3,.32,12,ACCENT,'s')
        _cards(deck,b['g_gallery']);x=9.0
        if first==idx:x=_side(deck,b);y0=5.55
        else:
            deck.label('Thông điệp (số QC · số ý tưởng)',x,2.05,3.83)
            deck.text(g_theme_lines(web),x,2.38,3.83,2.1,12)
            deck.label('Đích và trang đích hay dùng',x,4.5,3.83)
            deck.text(g_dest_line(web),x,4.8,3.83,.6,11,MUTED);y0=5.4
        deck.rect(x,y0,3.83,.012,LINE)
        deck.label('Phễu Google Ads web (số QC)',x,y0+.15,3.83)
        deck.text(' · '.join(f'{st} {v}' for st,v in zip(STAGES,g_stage_counts(web)))+f'. Xếp theo chữ đọc được ({g_read(web)}/{len(web)} QC).',x,y0+.45,3.83,.9,11,MUTED)
    if b['app']:
        idx=deck.slide(nm+' | '+GG_ADS+': video kéo cài app',kick+' · '+GG_ADS)
        first=idx if first is None else first
        ar=b['app'];places=Counter(p for r in ar for p in r['platforms'].split(',') if p)
        span=f"{vn_date(min(r['first_shown'] for r in ar))} → {vn_date(max(r['last_shown'] for r in ar))}"
        deck.text(f"{GG_ADS}: {len(ar)} video mang nhãn Google Play · {len(b['recent'])} còn chạy gần 29/10 · {span}",M,1.5,12.3,.32,12,ACCENT,'s')
        if b['app_gallery']:_cards(deck,b['app_gallery'])
        else:
            deck.rect(M,1.98,8.2,4.77,SURFACE_ALT)
            deck.text('Google không lưu ảnh xem trước và bản ghi thiếu YouTube ID nên chưa hiển thị được video. Mở Google Ads Transparency để xem.',M+.3,3.9,7.6,1.0,14,MUTED)
        x=9.0
        if first==idx:x=_side(deck,b);y0=5.55
        else:
            sig=Counter(s.strip() for r in ar for s in r['signals'].split(';') if s.strip())
            deck.label('Video app nói gì (số video)',x,2.05,3.83)
            deck.text(' · '.join(f'{k} {v}' for k,v in sig.most_common(4)) or 'Bản ghi chưa có tiêu đề/thông điệp để phân loại.',x,2.4,3.83,1.3,13)
            deck.label('Hiển thị trên',x,3.85,3.83)
            deck.text(' · '.join(f'{PLACE.get(k,k)} {v}' for k,v in places.most_common()),x,4.15,3.83,.6,13)
            if any(v['channel']=='Google App' for v in b['videos']):
                deck.text('Video app có phân tích chi tiết ở phần Thư viện video.',x,4.75,3.83,.55,11,MUTED)
            y0=5.4
        deck.rect(x,y0,3.83,.012,LINE)
        deck.label('Phễu Google Ads (app)',x,y0+.15,3.83)
        noweb=sum(gmsg(r)['target']=='App (nhãn Google Play)' for r in ar)
        deck.text(f"Cả {len(ar)} video = Chuyển đổi (nhãn Google Play = kéo cài app). {noweb}/{len(ar)} không dẫn về web công ty theo bộ lọc website của Google.",x,y0+.45,3.83,.9,11,MUTED)
    return first


def build_deck(data,chart):
    deck=Deck();top,picks,idle,others=groups(data);intro=section_intros(data)
    # Cover
    deck.dark()
    deck.text('BÁO CÁO ĐỐI THỦ · NGÀNH CHỨNG KHOÁN',M+.1,1.05,12,.3,12,MINT,'s')
    deck.text('Đối thủ quảng cáo:\nkênh nào, nội dung gì?',M+.1,1.5,12,1.9,46,'#FFFFFF','b')
    deck.text('Top 10 và 15 công ty ngoài Top 10 · Facebook Ads và Google Ads · Snapshot 29/10/2026',M+.1,3.55,12,.45,18,ON_DARK_MUTED)
    deck.rect(M+.1,4.55,SW-2*M-.1,.012,'#4A514F')
    for i,(n,l) in enumerate(cover_stats(data)):
        x=M+.1+i*3.05;deck.text(n,x,4.8,2.9,.85,44,LIME,'b');deck.text(l,x,5.7,2.9,.6,15,ON_DARK_MUTED)
    deck._footer(True)
    deck.slide('Ba điều cần biết','Tóm tắt')
    for i,(lead,body) in enumerate(KEY_POINTS):
        x=M+i*4.18;deck.rect(x,1.75,3.94,4.95,SURFACE_ALT);deck.rect(x,1.75,3.94,.08,LIME)
        deck.text(f'{i+1:02d}',x+.3,2.05,1.5,.6,30,ACCENT,'b')
        deck.text(lead,x+.3,2.8,3.35,1.3,21,INK,'b');deck.text(body.format(**funnel_summary(data)),x+.3,4.2,3.35,2.3,15)
    agenda=deck.slide('Mục lục','Bấm vào từng dòng để tới slide');assert agenda==Deck.agenda
    targets={}
    targets['s0']=deck.section(1,SECTIONS[0],intro[0])
    deck.slide('Hai kênh quảng cáo trong báo cáo','Cách đọc')
    for i,(name,what,see,miss) in enumerate(GLOSSARY):
        x=M+i*6.27;deck.rect(x,1.7,6.03,4.95,SURFACE_ALT);deck.rect(x,1.7,6.03,.08,LIME)
        deck.text(name,x+.3,1.98,5.4,.6,28,INK,'b');deck.text(what,x+.3,2.7,5.4,1.0,16)
        deck.label('Thấy được',x+.3,3.85,5.4);deck.text(see,x+.3,4.15,5.4,1.0,13)
        deck.label('Không thấy',x+.3,5.3,5.4);deck.text(miss,x+.3,5.6,5.4,.9,13,MUTED)
    deck.text('Biểu đồ định dạng, nội dung, điểm đến và quy mô chỉ dùng Facebook Ads.',M,6.72,12.3,.2,11,MUTED)
    deck.slide('Facebook và Google đếm “quảng cáo” khác nhau','Cách đọc · Không so trực tiếp số quảng cáo')
    for x,w,hd in [(M,2.3,''),(2.9,4.7,FB_ADS),(7.8,5.03,GG)]:deck.text(hd,x,1.6,w,.3,13,INK,'b')
    deck.rect(M,1.98,SW-2*M,.012,INK)
    for i,(k,fb,gg) in enumerate(COUNT_DIFF):
        y=2.12+i*1.05
        deck.text(k,M,y,2.3,.8,15,INK,'b');deck.text(fb,2.9,y,4.7,.9,13);deck.text(gg,7.8,y,5.03,.9,13)
        deck.rect(M,y+.95,SW-2*M,.008,LINE)
    deck.text('Hệ quả: so hai kênh bằng quảng cáo đang chạy và số ý tưởng, không bằng tổng số quảng cáo.',M,6.4,12.3,.4,14,ACCENT,'s')
    notes=chart_notes(data)
    charts_intro=[
      ('Ai đang chạy Facebook Ads, ai chạy Google Ads?','01_channels','Hai kênh'),
      ('Top 10 theo thứ hạng: từng công ty trên hai kênh','02_top10','Hai kênh'),
      ('Facebook Ads: ảnh, video và nội dung động','03_formats','Facebook Ads · Định dạng'),
      ('Facebook Ads: ba góc nội dung ưu đãi, tính năng, kiến thức','04_content','Facebook Ads · Nội dung'),
      ('Facebook Ads: điểm đến sau cú bấm','05_destinations','Facebook Ads · Điểm đến'),
      ('Số quảng cáo nhiều chưa chắc nhiều ý tưởng','06_volume_design','Quy mô · Hai kênh cùng thước đo'),
    ]
    for title,key,kick in charts_intro:
        deck.slide(title,kick)
        deck.image(chart[key],M,1.7,8.95,5.0)
        deck.rect(9.75,1.7,3.08,5.0,SURFACE_ALT)
        deck.label('Điểm chính',10.0,1.95,2.6)
        deck.text('\n\n'.join('• '+t for t in notes[key]),10.0,2.4,2.6,4.1,14)
    fs=funnel_summary(data);L=fs['leaders'];j=lambda xs:', '.join(xs) or '—'
    targets['s1']=deck.section(2,SECTIONS[1],intro[1])
    deck.slide('Tiêu chí xếp quảng cáo vào từng giai đoạn','Phễu · Cách phân loại')
    cols=[(M,2.3,'Giai đoạn'),(2.9,5.1,FB_ADS+' · theo nút CTA + link + trang đích thật'),(8.2,4.63,GG+' · theo chữ đọc được trên quảng cáo')]
    for x,w,hd in cols:deck.text(hd,x,1.6,w,.3,11,MUTED,'s')
    deck.rect(M,1.95,SW-2*M,.012,INK)
    for i,st in enumerate(STAGES):
        y=2.1+i*1.3
        deck.rect(M,y,.12,1.1,[MINT,EMERALD,PINE][i])
        deck.text(st,M+.3,y,2.0,.45,20,INK,'b');deck.text(STAGE_INFO[st][0],M+.3,y+.5,2.0,.3,12,MUTED)
        deck.text(STAGE_RULES[st][0],2.9,y,5.1,1.15,13);deck.text(STAGE_RULES[st][1],8.2,y,4.63,1.15,13)
        deck.rect(M,y+1.2,SW-2*M,.008,LINE)
    deck.text('Nội dung không quyết định giai đoạn ở Facebook Ads: video kiến thức nhưng nút dẫn về cài app vẫn tính Chuyển đổi. '
        'Facebook Ads đếm theo mẫu thiết kế. '+GSTAGE_NOTE,M,5.98,12.3,.85,11,MUTED)
    deck.slide('Đối thủ dồn vào đáy phễu: cài app, mở tài khoản','Phễu · Facebook Ads theo mẫu thiết kế')
    deck.image(chart['07_funnel'],M,1.5,8.4,5.35)
    deck.rect(9.2,1.6,3.63,5.15,SURFACE_ALT)
    deck.label('Điểm chính',9.45,1.85,3.15)
    t,r=fs['top'],fs['rest']
    deck.text('\n\n'.join(['• '+x for x in [
        f"Top 10: {t[2]}/{sum(t)} mẫu ({fs['top_pct']}%) là Chuyển đổi; Nhận biết chỉ {t[0]}.",
        f"Ngoài Top 10: {r[2]}/{sum(r)} mẫu ({fs['rest_pct']}%) Chuyển đổi, ba tầng gần đều.",
        f"Theo số quảng cáo: {fs['ads_conv']}/{fs['ads_total']} là Chuyển đổi."]]),9.45,2.2,3.15,4.3,14)
    gf=google_funnel_summary(data)
    deck.slide('Google Ads: app nằm ở đáy phễu, web trải ba tầng','Phễu · Google Ads và Google Ads (app)')
    deck.image(chart['08_google_funnel'],M,1.5,8.4,5.35)
    deck.rect(9.2,1.6,3.63,5.15,SURFACE_ALT)
    deck.label('Điểm chính',9.45,1.85,3.15)
    deck.text('\n\n'.join(['• '+x for x in [
        f"Top 10: {gf['top_app_cos']}/10 có video app ({gf['top_app']} video); còn chạy: {gf['top_recent_names']}.",
        f"Ngoài Top 10: {gf['rest_app']} video app; nhiều nhất {gf['rest_leaders']}.",
        f"Đọc được chữ {gf['read']}/{gf['total']} quảng cáo Google ({round(100*gf['read']/gf['total'])}%); phần còn lại xếp theo định dạng."]]),9.45,2.2,3.15,4.3,14)
    rank={b['name']:i+1 for i,b in enumerate(data['profiles'][:10])}
    def names_split(names):
        t=[f'#{rank[n]} {n}' for n in names if n in rank];o=[n for n in names if n not in rank]
        return ', '.join(t) or '—',', '.join(o) or '—'
    deck.slide('Mỗi giai đoạn: ai làm, làm thế nào','Phễu · Cách làm')
    stage_rows=[('Nhận biết','Đầu phễu',L['Nhận biết'],'Video kiến thức cho người mới, giải thưởng, sự kiện. Đo bằng lượt xem, lượt thích trang.'),
        ('Cân nhắc','Giữa phễu',L['Cân nhắc'],'Demo tính năng cụ thể (DTRADE, API/MCP, VinaStalk), dẫn về trang sản phẩm. Chứng minh app tốt hơn thay vì tặng quà.'),
        ('Chuyển đổi','Đáy phễu',L['Chuyển đổi'],'Quà cổ phiếu, miễn phí, margin + nút Cài đặt ngay, link App Store/Google Play. Google Ads (app) cũng ở đây.')]
    deck.text('Giai đoạn',M,1.6,2.6,.3,11,MUTED,'s');deck.text('Đối thủ tập trung (Top 10 ghi kèm thứ hạng #)',3.3,1.6,3.5,.3,11,MUTED,'s');deck.text('Cách làm điển hình',6.9,1.6,5.9,.3,11,MUTED,'s')
    deck.rect(M,1.95,SW-2*M,.012,INK)
    for i,(st,pos,names,how) in enumerate(stage_rows):
        y=2.1+i*1.25;t10,rest=names_split(names)
        deck.rect(M,y,.12,1.0,[MINT,EMERALD,PINE][i])
        deck.text(st,M+.3,y,2.4,.45,20,INK,'b');deck.text(pos,M+.3,y+.5,2.4,.3,12,MUTED)
        deck.rect(3.3,y+.04,.62,.26,PINE);deck.text('TOP 10',3.35,y+.07,.6,.22,9,'#FFFFFF','b')
        deck.text(t10,4.0,y,2.75,.5,13,INK,'b')
        deck.rect(3.3,y+.6,.62,.26,LINE);deck.text('NGOÀI',3.36,y+.63,.6,.22,9,MUTED,'b')
        deck.text(rest,4.0,y+.56,2.75,.5,12,MUTED)
        deck.text(how,6.9,y,5.9,1.05,14)
        deck.rect(M,y+1.13,SW-2*M,.008,LINE)
    deck.label('Hàm ý',M,5.95,12.3)
    deck.text('Đáy phễu đông nhất: phải hơn về mức ưu đãi hoặc độ rõ ràng. Đầu và giữa phễu ít đối thủ Top 10 đầu tư: cơ hội để người dùng biết thương hiệu trước khi họ so ưu đãi.',M,6.25,12.3,.65,14)
    targets['s2']=deck.section(3,SECTIONS[2],intro[2])
    for b in top:targets[b['name']]=profile_slide(deck,b)
    targets['s3']=deck.section(4,SECTIONS[3],intro[3])
    for b in picks:targets[b['name']]=profile_slide(deck,b)
    if others:
        targets['others']=deck.slide('Các công ty còn lại: ghi nhận để tra cứu','Ngoài Top 10 · Tóm tắt')
        cols=[(M,2.3,'Công ty'),(2.9,1.5,FB_ADS),(4.5,2.0,GG),(6.6,6.2,'Hướng nội dung quan sát được')]
        for x,w,hd in cols:deck.text(hd,x,1.6,w,.3,11,MUTED,'s')
        deck.rect(M,1.95,SW-2*M,.012,INK)
        rh=min(.52,4.8/max(len(others),1))
        for i,b in enumerate(others):
            y=2.05+i*rh
            for (x,w,_),val,wt in zip(cols,[b['name'],f"{len(b['fb'])} QC",f"{len(b['google'])} · {len(g_active(b))} còn chạy",b['title']],'brrr'):
                deck.text(val,x,y,w,rh-.08,13,INK,wt)
            deck.rect(M,y+rh-.04,SW-2*M,.008,LINE)
    targets['s4']=deck.section(5,SECTIONS[4],intro[4])
    for v in data['videos']:
        deck.slide(v['title'],CHANNEL_NAME[v['channel']]+' · Video đã lưu')
        deck.video(v,M,1.65,5.4,4.7)
        deck.text(f"{float(v['duration']):g} giây · {v['aspect']} · bấm vào video để phát",M,6.47,5.4,.3,10,MUTED)
        deck.text(v['flow'],6.3,1.65,6.53,.95,20,ACCENT,'b')
        deck.label('Cách thể hiện',6.3,2.8,6.53);deck.text(v['content'],6.3,3.1,6.53,1.4,15)
        deck.label('Nhận định',6.3,4.65,6.53);deck.text(v['finding'],6.3,4.95,6.53,1.3,15)
        deck.text('Xem quảng cáo gốc →',6.3,6.42,6.53,.32,12,ACCENT,'s',url=v['url'])
    selected=[b for b in top+picks if b['landing_preview']][:6]
    targets['s5']=deck.section(6,SECTIONS[5],intro[5])
    for i in range(0,len(selected),3):
        deck.slide('Từ quảng cáo đến trang đích: bằng chứng đã lưu','Facebook Ads · Điểm đến')
        for j,b in enumerate(selected[i:i+3]):
            x=M+j*4.18;l=b['landing_preview']
            deck.text(b['name'],x,1.6,3.94,.4,18,INK,'b')
            deck.image(l['image'],x,2.1,3.94,3.9,l['url'])
            deck.text(short(l['title'],115),x,6.1,3.94,.65,11,MUTED)
    targets['end']=deck.slide('Nội dung theo từng tầng phễu','Kết luận')
    for i,(title,body) in enumerate(PATTERNS):
        x=M+i*4.18;deck.rect(x,1.75,3.94,4.25,SURFACE_ALT);deck.rect(x,1.75,3.94,.08,LIME)
        deck.text(f'{i+1:02d}',x+.3,2.05,1.5,.5,22,ACCENT,'b')
        deck.text(title,x+.3,2.65,3.35,.9,22,INK,'b')
        deck.text(body,x+.3,3.65,3.35,2.3,16)
    deck.text('Đây là mẫu triển khai quan sát được. Cần thử và đo chuyển đổi để biết cách nào hiệu quả.',M,6.3,12.3,.45,15,MUTED)
    targets['src']=deck.slide('Nguồn, phạm vi và giới hạn','Phụ lục')
    rows=[('Phạm vi',f"25 công ty · {data['totals']['fb']} quảng cáo Facebook Ads · {data['totals']['google_app']} quảng cáo Google Ads (app). Phân tích sâu: Top 10 có quảng cáo và 6 công ty ngoài Top 10."),
       ('Mốc tham chiếu','29/10/2026 14:29, giờ Việt Nam. “Còn chạy”: lần hiển thị cuối cách mốc dưới 3 ngày.'),
       ('Google Ads',f"{sum(len(b['google']) for b in data['profiles'])} quảng cáo mọi định dạng (Transparency Center); {data['totals']['google_app']} video nhãn Google Play = Google Ads (app). Chữ đọc bằng OCR; đích kiểm tra bằng bộ lọc website của Google."),
       ('Phễu','Facebook: theo nút CTA và trang đích thật, đếm theo mẫu thiết kế. Google: theo chữ đọc được trên quảng cáo; nhãn Google Play = kéo cài app.'),
       ('Loại trừ','4 gói Meta DCO chưa xác minh nguồn. Không có ngân sách, impressions, CPA hoặc chuyển đổi.'),
       ('Hình ảnh','Creative gốc tải lại từ Meta Ad Library; video lấy khung hình ở 30% thời lượng. PowerPoint chứa video nhúng.')]
    for i,(k,t) in enumerate(rows):
        y=1.65+i*.84
        deck.text(k,M,y,2.6,.7,15,INK,'b');deck.text(t,3.3,y,9.5,.7,14)
        deck.rect(M,y+.74,SW-2*M,.01,LINE)
    # Fill in the agenda now that every slide number is known.
    deck.current=deck.slides[agenda]
    def entry(x,y,w,label,key,size=14,weight='r',color=INK):
        n=targets[key]+1
        deck.text(label,x,y,w-.7,.3,size,color,weight,goto=targets[key])
        deck.text(str(n),x+w-.6,y,.6,.3,size,MUTED,'s',align='r',goto=targets[key])
    secs=[(f's{i}',t) for i,t in enumerate(SECTIONS)]+[('end','Kết luận'),('src','Nguồn và giới hạn')]
    deck.label('Các phần',M,1.6,3.9)
    for i,(key,label) in enumerate(secs):
        y=2.0+i*.54;entry(M,y,3.9,label,key,14,'b');deck.rect(M,y+.42,3.9,.008,LINE)
    for col,(title,items) in enumerate([('Hồ sơ Top 10',top),('Ngoài Top 10 — tham khảo',picks)]):
        x=4.9+col*4.05;deck.label(title,x,1.6,3.8)
        for i,b in enumerate(items):
            y=2.0+i*.47;entry(x,y,3.8,rname(b),b['name'],13)
            deck.rect(x,y+.38,3.8,.008,LINE)
        if col==1 and others:
            y=2.0+len(items)*.47;entry(x,y,3.8,f'Bảng {len(others)} công ty còn lại','others',13,'r',MUTED)
    if idle:deck.text(f"Không có quảng cáo trong phạm vi, bỏ qua phân tích: {', '.join(idle)}.",4.9,6.45,7.9,.3,11,MUTED)
    return deck


def fit_box(path,x,y,w,h):
    with Image.open(ROOT/path) as im:iw,ih=im.size
    k=min(w/iw,h/ih);dw,dh=iw*k,ih*k
    return x+(w-dw)/2,y+(h-dh)/2,dw,dh


def export_deck(deck,pptx_path,pdf_path):
    from pptx.enum.text import PP_ALIGN
    prs=Presentation();prs.slide_width=Inches(SW);prs.slide_height=Inches(SH)
    register_fonts();fonts={'r':'DSC-R','s':'DSC-S','b':'DSC-B'}
    c=canvas.Canvas(str(pdf_path),pagesize=(SW*72,SH*72))
    overflows=[];jumps=[];pptx_slides=[]
    for i,items in enumerate(deck.slides):
        slide=prs.slides.add_slide(prs.slide_layouts[6]);pptx_slides.append(slide);c.bookmarkPage(f'slide{i}')
        for it in items:
            kind=it['type'];x,y,w,h=[it[k] for k in ['x','y','w','h']]
            if kind=='rect':
                shape=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h))
                shape.fill.solid();shape.fill.fore_color.rgb=RGBColor.from_string(it['color'][1:]);shape.line.fill.background()
                shape.shadow.inherit=False
                c.setFillColor(it['color']);c.rect(x*72,(SH-y-h)*72,w*72,h*72,fill=1,stroke=0)
            elif kind=='text':
                size=it['size'];text=escape(it['text']).replace('\n','<br/>')
                while size>=9:
                    sty=ParagraphStyle('slide',fontName=fonts[it['weight']],fontSize=size,leading=size*1.25,
                        textColor=it['color'],alignment=2 if it['align']=='r' else 0)
                    par=Paragraph(text,sty);pw,ph=par.wrap(w*72,h*72)
                    if ph<=h*72:break
                    size-=.5
                if ph>h*72:overflows.append((i+1,it['text'][:60]))
                c.saveState();par.drawOn(c,x*72,(SH-y)*72-ph);c.restoreState()
                tb=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=tb.text_frame
                tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0;tf.word_wrap=True
                for j,line in enumerate(it['text'].split('\n')):
                    p=tf.paragraphs[0] if j==0 else tf.add_paragraph();p.text=line;p.space_after=Pt(0)
                    p.line_spacing=1.2
                    if it['align']=='r':p.alignment=PP_ALIGN.RIGHT
                    for run in p.runs:
                        run.font.name=FAMILY;run.font.size=Pt(size);run.font.bold=it['weight']!='r'
                        run.font.color.rgb=RGBColor.from_string(it['color'][1:])
                        if it.get('url'):run.hyperlink.address=it['url']
                rect=(x*72,(SH-y-h)*72,(x+w)*72,(SH-y)*72)
                if it.get('url'):c.linkURL(it['url'],rect,relative=0)
                if it.get('goto') is not None:
                    c.linkRect('',f"slide{it['goto']}",rect,relative=0);jumps.append((tb,it['goto']))
            elif kind in ['image','video']:
                xx,yy,ww,hh=fit_box(it['path'],x,y,w,h)
                if kind=='image':
                    shape=slide.shapes.add_picture(str(ROOT/it['path']),Inches(xx),Inches(yy),Inches(ww),Inches(hh))
                    if it.get('url'):shape.click_action.hyperlink.address=it['url']
                else:
                    v=it['v']
                    slide.shapes.add_movie(str(ROOT/v['video']),Inches(xx),Inches(yy),Inches(ww),Inches(hh),
                        poster_frame_image=str(ROOT/v['poster']),mime_type='video/mp4')
                c.drawImage(ImageReader(str(ROOT/it['path'])),xx*72,(SH-yy-hh)*72,ww*72,hh*72,mask='auto')
                url=it.get('url')
                if kind=='video':url='media/'+Path(it['v']['video']).name
                if url:c.linkURL(url,(xx*72,(SH-yy-hh)*72,(xx+ww)*72,(SH-yy)*72),relative=0)
        c.showPage()
    for shape,target in jumps:shape.click_action.target_slide=pptx_slides[target]
    prs.core_properties.title='Quảng cáo đối thủ chứng khoán – bản có media'
    prs.save(pptx_path);c.save()
    if overflows:raise ValueError(('Slide text exceeds allocated boxes',overflows))


def validate_and_package(data,pages,deck,pdf,pptx,slides_pdf):
    import pymupdf
    from pypdf import PdfReader
    reader=PdfReader(str(pdf));assert len(reader.pages)>=len(pages),(len(reader.pages),len(pages))
    assert len(PdfReader(str(slides_pdf)).pages)==len(deck.slides)
    assert sum(len(b['fb']) for b in data['profiles'])==844
    assert sum(len(b['app']) for b in data['profiles'])==195
    assert sum(len(b['recent']) for b in data['profiles'])==22
    assert len({v['video'] for v in data['videos']})==len(data['videos'])
    for v in data['videos']:
        m=v['meta']
        if v['channel']=='Meta':assert m['media_evidence']=='video_url_present'
        if v['channel']=='Google App':assert any('Play' in r['platforms'].split(',') and r['link']==v['url']
            for b in data['profiles'] for r in b['app'])
        if v['channel']=='YouTube tham khảo':assert 'Play' not in m['platforms']
        proc=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(ROOT/v['video'])],capture_output=True,text=True,check=True)
        duration=float(json.loads(proc.stdout)['format']['duration'])
        assert abs(duration-v['duration'])<2,(v['title'],duration,v['duration'])
        stream_probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,codec_name',
            '-of','json',str(ROOT/v['video'])],check=True,capture_output=True,text=True)
        assert all(s['codec_name'] in ('h264','aac') for s in json.loads(stream_probe.stdout)['streams']
                   if s['codec_type'] in ('video','audio'))
    with zipfile.ZipFile(pptx) as z:
        embedded=[n for n in z.namelist() if n.startswith('ppt/media/') and n.endswith('.mp4')]
        assert len(embedded)==len(data['videos']),(len(embedded),len(data['videos']))
        assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+.xml',n)])==len(deck.slides)
    # Check actual PDF text bounds; report pages and handout share this check.
    for path in [pdf,slides_pdf]:
        document=pymupdf.open(path)
        for pi,page in enumerate(document):
            for block in page.get_text('dict')['blocks']:
                if block['type']!=0:continue
                for line in block['lines']:
                    x0,y0,x1,y1=line['bbox']
                    assert x0>=0 and y0>=0 and x1<=page.rect.width+1 and y1<=page.rect.height+1,(path.name,pi,line['bbox'])
    stats=dict(report_pages=len(reader.pages),slides=len(deck.slides),embedded_videos=len(data['videos']),
        facebook_samples=sum(len(b['gallery']) for b in data['profiles']),
        facebook_originals=sum(r['original'] for b in data['profiles'] for r in b['gallery']),
        companies_analysed=sum(b['show'] for b in data['profiles']),
        google_samples=sum(len(b['g_gallery']) for b in data['profiles']),
        google_app_samples=sum(len(b['app_gallery']) for b in data['profiles']),
        landing_screenshots=sum(bool(b['landing_preview']) for b in data['profiles']),
        charts=8,checks='Reference totals, media attribution, video duration, PPTX embeds, PDF pagination and text bounds passed')
    (OUT/'validation_media.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    (OUT/'evidence_media.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    # Full, unabridged captions are easy to review outside the report excerpts.
    fields=['company','ad_id','format','caption','cta','landing_type','final_url','source_url','image_file']
    captions=[]
    with (OUT/'Thu_vien_caption_day_du.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for b in data['profiles']:
            for r in b['gallery']:
                writer.writerow(dict(company=b['name'],ad_id=r['ad_archive_id'],format=r['format'],caption=r['body'],
                    cta=r['cta'],landing_type=r['landing_type'],final_url=r['final_url'],source_url=r['url'],
                    image_file='media/'+Path(r['image']).name))
                captions.append(f"{b['name']} | {r['ad_archive_id']} | {r['format']}\n"
                    f"{r['body']}\n\nCTA: {r['cta']}\nĐiểm đến: {r['final_url'] or r['link_url']}\nNguồn: {r['url']}\n")
    (OUT/'Noi_dung_quang_cao_day_du.txt').write_text(
        'THƯ VIỆN NỘI DUNG QUẢNG CÁO ĐẦY ĐỦ\n'
        f'Snapshot 29/10/2026 · {len(captions)} mẫu minh họa · Caption nguyên văn từ dữ liệu đã lưu\n\n'
        +'\n'.join(captions),encoding='utf-8')
    manifest={}
    for item in data['inventory']:
        f=ROOT/item['source'];manifest[item['source']]=hashlib.sha256(f.read_bytes()).hexdigest()
    for f in [Path(__file__),ROOT/'build_executive_report.py',PROJ/'all_ads.csv',PROJ/'google_all_ads.csv',PROJ/'report_snapshot.json']:
        manifest[rel(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    for folder in ['winners','winners_google']:
        for f in (PROJ/folder).glob('*/meta.json'):
            manifest[rel(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    (OUT/'source_manifest_media.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    # Package relative video links and raw caption provenance with the documents.
    bundle=PROJ/f'{STEM}_tron_bo.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for f in sorted(OUT.rglob('*')):
            if f.is_file():z.write(f,Path('Bao_cao_media')/f.relative_to(OUT))
    print(json.dumps(dict(stats,bundle=str(bundle)),ensure_ascii=False,indent=2))


def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--no-fetch',action='store_true',help='không tải ảnh gốc từ Ad Library')
    ap.add_argument('--fetch-only',action='store_true');args=ap.parse_args()
    for path in [ASSETS,CHARTS]:shutil.rmtree(path,ignore_errors=True)   # derived copies only
    for path in [OUT,ASSETS,CHARTS]:path.mkdir(exist_ok=True)
    data=prepare_data(fetch=not args.no_fetch)
    if args.fetch_only:return
    chart=charts(data)
    pages=report_pages(data,chart);deck=build_deck(data,chart)
    report_pdf=OUT/f'{STEM}_bao_cao.pdf';report_docx=OUT/f'{STEM}_bao_cao.docx'
    pptx=OUT/f'{STEM}_slides.pptx';slides_pdf=OUT/f'{STEM}_slides.pdf'
    render_docx(pages,report_docx);render_pdf(pages,report_pdf)
    export_deck(deck,pptx,slides_pdf)
    validate_and_package(data,pages,deck,report_pdf,pptx,slides_pdf)


if __name__=='__main__':main()
