"""Cập nhật bộ slide media tổng hợp chứng khoán sang kỳ mới (gộp 29/10, 11/11, 22/11).

Đọc bộ slide kỳ trước, kiểm tra từng số cũ có đúng như cách tính gộp 2 kỳ (nếu lệch thì dừng),
thay bằng số gộp 3 kỳ, thêm phần "Kỳ 22/11 · Có gì mới" sau Mục lục và đánh lại số trang, mục lục.

python3 update_media_deck.py
"""
import copy
import re
from collections import Counter
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu, Inches

import media_period_metrics as M

OUT = M.PROJ/'bao-cao-media'
SRC = OUT/'Doi_thu_chung_khoan_media_tong_hop_29-10_den_11-11-2026_slides.pptx'
DST = OUT/'Doi_thu_chung_khoan_media_tong_hop_29-10_den_22-11-2026_slides.pptx'
THUMBS = M.PROJ/'thumbs'
NEW_LABEL = '22/11'
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
IN = 914400


# ---------- tiện ích văn bản ----------
def fmt_n(n):
    return f'{n:,}'.replace(',', '.')


def set_text(sh, text):
    """Đổi chữ nhưng giữ định dạng của run đầu tiên mỗi đoạn."""
    tf = sh.text_frame
    parts = text.split('\n')
    paras = list(tf.paragraphs)
    while len(paras) < len(parts):
        new_p = copy.deepcopy(paras[-1]._p)
        paras[-1]._p.addnext(new_p)
        paras = list(tf.paragraphs)
    for p, t in zip(paras, parts):
        runs = p.runs
        if not runs:
            p.add_run().text = t
            continue
        runs[0].text = t
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    for p in paras[len(parts):]:
        p._p.getparent().remove(p._p)


def text_shapes(slide):
    return [sh for sh in slide.shapes if sh.has_text_frame]


def replace(slide, old, new, required=True):
    """Thay chuỗi trong đoạn văn (có thể nằm qua nhiều run)."""
    hits = 0
    for sh in text_shapes(slide):
        for p in sh.text_frame.paragraphs:
            full = ''.join(r.text for r in p.runs)
            if old not in full:
                continue
            hits += 1
            one = [r for r in p.runs if old in r.text]
            if one:
                one[0].text = one[0].text.replace(old, new)
            else:
                p.runs[0].text = full.replace(old, new)
                for r in p.runs[1:]:
                    r._r.getparent().remove(r._r)
    if required and not hits:
        raise SystemExit(f'Không tìm thấy “{old}” trên slide {slide_no(slide)}')
    return hits


def exact(slide, old, new):
    hit = [sh for sh in text_shapes(slide) if sh.text_frame.text == old]
    if not hit:
        raise SystemExit(f'Không có ô “{old}” trên slide {slide_no(slide)}')
    for sh in hit:
        set_text(sh, new)


PRS = None


def slide_no(slide):
    return list(PRS.slides).index(slide) + 1


def grid(slide, label_x=0.62):
    """{nhãn hàng: [ô bên phải theo thứ tự x]} cho các bảng dựng bằng textbox."""
    shapes = text_shapes(slide)
    rows = {}
    for sh in shapes:
        if abs(sh.left/IN - label_x) < 0.05 and sh.top/IN > 1.85:
            cells = [c for c in shapes if c is not sh and abs(c.top - sh.top) < 0.05*IN and c.left > sh.left]
            rows[sh.text_frame.text] = (sh, sorted(cells, key=lambda c: c.left))
    return rows


def bars(slide):
    """Các hàng biểu đồ cột: (nhãn, thanh, ô số) theo thứ tự từ trên xuống."""
    shapes = list(slide.shapes)
    out = []
    for b in shapes:
        if b.has_text_frame and b.text_frame.text:
            continue
        if not (0.30*IN < b.height < 0.36*IN and b.left > 2*IN and b.top < 6.5*IN):
            continue
        lab = [s for s in shapes if s.has_text_frame and s.left < b.left and abs(s.top - b.top) < 0.2*IN and s.text_frame.text]
        val = [s for s in shapes if s.has_text_frame and s.left > b.left and abs(s.top - b.top) < 0.1*IN and s.text_frame.text]
        if lab and val:
            out.append((lab[0], b, val[0]))
    return sorted(out, key=lambda t: t[1].top)


def set_bars(slide, items, old_items):
    rows = bars(slide)
    assert [(r[0].text_frame.text, r[2].text_frame.text) for r in rows] == \
        [(k, fmt_n(v)) for k, v in old_items], (slide_no(slide), [(r[0].text_frame.text, r[2].text_frame.text) for r in rows], old_items)
    maxw = max(r[1].width for r in rows)
    vmax = max(v for _, v in items)
    for (lab, bar, val), (k, v) in zip(rows, items):
        set_text(lab, k)
        set_text(val, fmt_n(v))
        bar.width = max(int(maxw*v/vmax), int(0.05*IN))
        val.left = bar.left + bar.width + int(0.11*IN)


# ---------- nhân bản slide ----------
def clone_slide(prs, src, index):
    new = prs.slides.add_slide(src.slide_layout)
    for shp in list(new.shapes):
        shp._element.getparent().remove(shp._element)
    rid = {}
    for k, rel in src.part.rels.items():
        if rel.reltype.endswith(('/slideLayout', '/notesSlide')):
            continue
        if rel.is_external:
            rid[k] = new.part.relate_to(rel.target_ref, rel.reltype, is_external=True)
        else:
            rid[k] = new.part.relate_to(rel.target_part, rel.reltype)
    tree = new.shapes._spTree
    for el in list(src.shapes._spTree)[2:]:
        tree.append(copy.deepcopy(el))
    for el in tree.iter():
        for a, v in list(el.attrib.items()):
            if a.startswith(R_NS) and v in rid:
                el.set(a, rid[v])
    lst = prs.slides._sldIdLst
    item = lst[-1]
    lst.remove(item)
    lst.insert(index, item)
    return new


def by_name(slide, name):
    return next(sh for sh in slide.shapes if sh.name == name)


def set_link(sh, url):
    """Đổi link của run đầu tiên (hoặc bỏ link nếu url rỗng)."""
    run = sh.text_frame.paragraphs[0].runs[0]
    run.hyperlink.address = url or None


# ---------- số liệu ----------
def meta_line(rs):
    f = Counter(r['format'] for r in rs)
    return f'{len(rs)} ID Meta tổng hợp  ·  ' + ' · '.join(f'{v} {k}' for k, v in f.most_common())


def funnel_line(rs):
    s = Counter(r['stage'] for r in rs)
    d = Counter(M.dest_class(r) for r in rs)
    return (f'Nhận biết {s["Nhận biết"]} · Cân nhắc {s["Cân nhắc"]} · Chuyển đổi {s["Chuyển đổi"]}.',
            ' · '.join(f'{v} {k}' for k, v in d.most_common(2)) + '.')


def google_lines(g, last, comp):
    x = [r for r in g if r['competitor'] == comp]
    f = Counter(r['format'] for r in x)
    vid = [r for r in x if r['format'] == 'Video']
    head = f'{len(x)} creative tổng hợp · {last.g_active(comp)} gần đây · ' + ' · '.join(f'{v} {k}' for k, v in f.most_common())
    play = f'{sum("Play" in r["platforms"] for r in x)} creative có nhãn Play.'
    yt = f'{sum(not r["youtube_id"] for r in vid)}/{len(vid)} video thiếu YouTube ID.' if vid else None
    return head, play, yt


class Snap:
    def __init__(self, periods):
        self.ps = periods
        self.last = periods[-1]
        self.meta = M.union_meta(periods)
        self.google = M.union_google(periods)

    def meta_of(self, pid):
        return [r for r in self.meta if r['pid'] == pid]

    def g_count(self, comp):
        return sum(r['competitor'] == comp for r in self.google)


COMPANIES = {n: (pid, g) for n, pid, g in M.TOP10 + M.TREND}


# ---------- nội dung phần mới ----------
HEADLINES = [
    ('KỲ 22/11 · ĐIỂM ĐÁNG CHÚ Ý', 'Ba thay đổi lớn nhất', [
        ('Shinhan tăng mạnh trên cả hai kênh',
         'Facebook Ads tăng từ 2 lên 35 QC, Google Ads từ 5 lên 17 creative đang chạy. Cả hai kênh dùng chung thông điệp 0% phí trọn đời và lãi margin ưu đãi.'),
        ('VNDirect thay toàn bộ quảng cáo Facebook',
         'Cả 11 QC cũ đã dừng. 28 QC mới, trong đó 21 là quảng cáo động, quảng bá tính năng DTRADE và không dùng quà.'),
        ('LPS cắt bớt QC, VFS dừng Google Ads',
         'LPS giảm từ 568 xuống 345 QC Facebook Ads nhưng số mẫu thiết kế tăng từ 11 lên 30. VFS giảm từ 53 xuống 0 creative Google đang chạy.')]),
    ('KỲ 22/11 · NỘI DUNG', 'Ba hướng nội dung mới', [
        ('Cạnh tranh bằng lãi margin',
         'Ngoài LPS (99 QC mới), Shinhan (margin 0%), MBS (7,5%), Yuanta (6,8%) và KBSV cùng quảng bá chi phí vốn vay trong kỳ này.'),
        ('Quà gắn với một hành động cụ thể',
         'TCBS tặng 50 iXu khi mở tài khoản và đăng ký iPower. KIS tặng 3 cổ phiếu qua 3 bước trong app, kèm thưởng giới thiệu bạn bè.'),
        ('Sự kiện và nội dung cuối năm',
         'VPBankS quảng bá hội thảo Chiến lược 2027, VCBS có fan meeting tháng 12, HSC tóm tắt KQKD quý 3. Mới có SSI chạy ưu đãi Tết.')]),
]

SAMPLES = [
    dict(ad='1588769779958382', thumb='1874200230404634', kicker='ƯU ĐÃI PHÍ VÀ MARGIN · META · NGUỒN 22/11',
         title='Shinhan · Không phải chọn giữa phí và lãi', meta='Ảnh đơn · Bắt đầu 20/11 · 4 bản',
         how='Ảnh lấy “0% phí giao dịch trọn đời” làm tiêu đề, kèm ba quyền lợi: tư vấn 1:1, lãi margin từ 0%, hạn mức đến 10 tỷ. Caption tách hai mức lãi: 0%/năm trong 2 tháng đầu (đến 500 triệu) và 6,8%/năm trong 4 tháng tiếp theo.',
         impl='Khi gộp nhiều ưu đãi, cần ghi điều kiện và thời hạn của từng mức ngay trong caption như mẫu này. Shinhan chạy cùng thông điệp trên Google Ads (17 creative đang chạy). Nên thử đo hiệu quả khi chạy đồng thời hai kênh.',
         cta='Tìm hiểu thêm'),
    dict(ad='1677757007085696', thumb='1186233931008955', kicker='TÍNH NĂNG VÀ TIỆN ÍCH · META · NGUỒN 22/11',
         title='VNDirect · Không gian giao dịch theo góc nhìn bạn', meta='Dynamic (DCO) · Bắt đầu 19/11 · 5 bản',
         how='Hình là màn hình DTRADE thật trên nền tối. Caption so sánh với người thợ lâu năm luôn để dụng cụ đúng chỗ, rồi tả một thao tác: chọn một mã thì biểu đồ, sổ lệnh và tin tức cùng cập nhật.',
         impl='Cả 28 QC Facebook Ads của VNDirect kỳ này đều mới và không dùng quà. Đây là một ví dụ cho bài thử “Một tính năng, một thao tác”: giao diện thật đi cùng một tình huống sử dụng.',
         cta='Tìm hiểu thêm'),
    dict(ad='1505898858051249', thumb='1154437717133170', kicker='ƯU ĐÃI PHÍ VÀ MARGIN · META · NGUỒN 22/11',
         title='LPS · Vay 50 triệu, tiết kiệm 57% tiền lãi', meta='Ảnh đơn · Bắt đầu 18/11 · 12 bản',
         how='Ảnh đặt hai mức tiền lãi cạnh nhau: 1.304.110đ khi vay nơi khác và 562.630đ khi dùng Double Zero tại LPS. Caption ghi rõ giả định: dư nợ 50 triệu trong 68 ngày, mức tham chiếu 14%/năm.',
         impl='So sánh bằng số tiền cụ thể dễ hình dung hơn so sánh lãi suất, nhưng phải ghi giả định như mẫu này. Qua ba kỳ, LPS có 21 nội dung chữ khác nhau, nhiều bài theo dạng “cùng khoản vay, tốn ít hơn X%”.',
         cta='Cài đặt ngay'),
    dict(ad='4470288576554328', thumb='1192418880407141', kicker='ƯU ĐÃI PHÍ VÀ MARGIN · META · NGUỒN 22/11',
         title='MBS · Bỏ túi tới 18 triệu với margin 7,5%', meta='Ảnh đơn · Bắt đầu 16/11 · 6 bản',
         how='Ảnh đổi lãi suất thành số tiền: “Bỏ túi 18.000.000đ/năm” với combo Margin Plus và Margin 7,5%. Caption ghi hạn mức ưu đãi tới 300 triệu đồng mỗi tài khoản, dành cho khách hàng mở mới.',
         impl='18 triệu là mức tiết kiệm tối đa, nhưng caption chưa nêu cách tính. Nếu dùng cách quy đổi này, cần ghi rõ dư nợ, thời gian và mức lãi đem so, như cách LPS đã làm.',
         cta='Xem chi tiết'),
    dict(ad='1546236457280258', thumb='2051275775510430', kicker='ƯU ĐÃI PHÍ VÀ MARGIN · META · NGUỒN 22/11',
         title='Yuanta · Margin Lộc Phát 6,8%/năm', meta='Ảnh đơn · Bắt đầu 18/11',
         how='Ảnh lấy mức 6,8%/năm làm điểm nhấn, kèm hạn mức 3 tỷ, hạn vay 6 tháng, giới hạn 100 suất và miễn lãi 2 ngày đầu. Caption gắn ưu đãi với mùa công bố KQKD quý 3.',
         impl='Ảnh và caption ghi thời gian đăng ký 01/10–31/10/2026, trong khi quảng cáo bắt đầu chạy ngày 18/11. Nên để phần thời hạn ở end card hoặc một dòng riêng để dễ cập nhật, tránh chạy ưu đãi đã hết hạn.',
         cta='Xem chi tiết'),
    dict(ad='1522996346319554', thumb='1115673270982370', kicker='QUÀ CỔ PHIẾU · META · NGUỒN 22/11',
         title='KIS · Chứng Sĩ Mã Đáo, nhận 3 cổ phiếu', meta='Dynamic (DCO) · Bắt đầu 13/11',
         how='Ảnh minh hoạ app iKIS với tên chương trình. Caption liệt kê 3 bước nhận cổ phiếu PDR ngay trong app: đăng nhập, vào mục Khám Phá, bấm “Nhận cổ phiếu”.',
         impl='Hướng dẫn từng bước giúp người xem biết phải làm gì sau cú nhấp. Song song, KIS chạy chương trình giới thiệu bạn bè (50K mỗi lượt, đua top tới 1,5 triệu): quà được gắn với cả kích hoạt lẫn giới thiệu.',
         cta='Đăng ký'),
    dict(ad='1150659967486593', thumb='1447178747522817', kicker='MỞ TÀI KHOẢN · META · NGUỒN 22/11',
         title='TCBS · Mở tài khoản, nhận 50 iXu', meta='Ảnh đơn · Bắt đầu 13/11',
         how='Ảnh dùng linh vật và lãi iPower tối đa 9% + 1%/năm trong tháng 11, kèm 50 iXu cho khách mới. Caption chỉ có 2 bước: mở tài khoản, rồi đăng ký iPower trong 3 ngày; áp dụng đến 30/11/2026.',
         impl='Thời hạn và số bước được ghi gọn ngay trong caption. TCBS tăng từ 1 lên 6 QC Facebook Ads, tất cả đều là chiến dịch cài app.',
         cta='Cài đặt ngay'),
    dict(ad='1866264861455814', thumb='1120169880846289', kicker='TÍNH NĂNG VÀ TIỆN ÍCH · META · NGUỒN 22/11',
         title='SSI · Mua cổ phiếu định kỳ', meta='Ảnh đơn · Bắt đầu 20/11 · 2 bản',
         how='Ảnh dùng hình đồng hồ cát chứa các mã cổ phiếu, kèm tiêu đề “Khỏi lo canh giá, tích sản đường xa”. Caption giới thiệu tính năng mới trên iBoard Pro: thiết lập một lần, hệ thống tự đặt lệnh theo ngày, tuần hoặc tháng.',
         impl='Link dẫn thẳng vào màn hình tính năng trong app (deep link). Với tính năng mới, nên thử cách này để rút ngắn đường đi từ quảng cáo đến thao tác.',
         cta='Xem chi tiết'),
    dict(ad='1084168887437713', thumb='1823351778939609', kicker='TƯƠNG TÁC VÀ SỰ KIỆN · META · NGUỒN 22/11',
         title='VPBankS · Hội thảo Chiến lược đầu tư 2027', meta='Ảnh đơn · Bắt đầu 21/11',
         how='Ảnh giới thiệu 7 diễn giả kèm chức danh. Caption nêu 4 nội dung của hội thảo, trong đó có định hướng thị trường đến năm 2030 do đại diện Ủy ban Chứng khoán Nhà nước trình bày.',
         impl='Cả 3 QC mới của VPBankS đều quảng bá hội thảo này và không gắn nút CTA. Nên cân nhắc dùng chủ đề chiến lược cho năm mới cho nội dung tháng 12 (chưa có dữ liệu hiệu quả).',
         cta='Không có nút'),
    dict(ad='1451224803179379', thumb='1631927697887886', kicker='TƯƠNG TÁC VÀ SỰ KIỆN · META · NGUỒN 22/11',
         title='VCBS · Rủ bạn mở tài khoản, săn vé fan meeting', meta='Nhiều ảnh · Bắt đầu 19/11',
         how='Ảnh hướng dẫn mở tài khoản VCBS qua app VCB Digibank. Caption liệt kê 4 bước và nhiệm vụ săn vé: giới thiệu thành công 20 bạn bè để nhận vé Fan Meeting Quán Nhà Haha.',
         impl='Phần thưởng là trải nghiệm sự kiện thay vì tiền hay cổ phiếu, và việc mở tài khoản đi qua app của ngân hàng mẹ. Cả 3 QC Facebook Ads của VCBS kỳ này đều thuộc chương trình này.',
         cta='Không có nút'),
]


def main():
    global PRS
    prs = PRS = Presentation(SRC)
    periods = M.load()
    old, new = Snap(periods[:2]), Snap(periods)
    S = list(prs.slides)
    prev, cur = periods[1], periods[2]

    # Bìa
    s = S[0]
    replace(s, 'Dữ liệu chốt đến 11/11/2026', f'Dữ liệu chốt đến {NEW_LABEL}/2026')
    exact(s, fmt_n(len(old.meta)), fmt_n(len(new.meta)))
    exact(s, fmt_n(len(old.google)), fmt_n(len(new.google)))
    exact(s, '26', str(26 + len(SAMPLES)))

    # Slide 5: phạm vi
    s = S[4]
    replace(s, f'{fmt_n(len(old.meta))} ID từng', f'{fmt_n(len(new.meta))} ID từng')
    replace(s, f'{fmt_n(len(old.google))} creative truy xuất', f'{fmt_n(len(new.google))} creative truy xuất')
    oa, na = sum(map(M.Period.is_app, old.google)), sum(map(M.Period.is_app, new.google))
    replace(s, f'{oa} creative hình ảnh', f'{na} creative hình ảnh')
    replace(s, f'{len(prev.meta)} ID Meta đang hoạt động tại mốc chốt. {prev.g_active()} creative Google',
            f'{len(cur.meta)} ID Meta đang hoạt động tại mốc chốt. {cur.g_active()} creative Google')

    # Slide 6: định dạng Meta
    def fmt_items(rs, n=5):
        return [(k, v) for k, v in Counter(r['format'] for r in rs).most_common(n)]
    set_bars(S[5], fmt_items(new.meta), fmt_items(old.meta))
    o1 = Counter(r['format'] for r in old.meta)['Ảnh đơn']; n1 = Counter(r['format'] for r in new.meta)['Ảnh đơn']
    replace(S[5], f'Ảnh đơn chiếm {round(100*o1/len(old.meta))}%', f'Ảnh đơn chiếm {round(100*n1/len(new.meta))}%')
    lps = '197779796755847'
    replace(S[5], f'LPS đóng góp {len(old.meta_of(lps))} ID', f'LPS đóng góp {len(new.meta_of(lps))} ID')

    # Slide 7: định dạng Google
    gi = lambda g: [(k, v) for k, v in Counter(r['format'] for r in g).most_common()]
    set_bars(S[6], gi(new.google), gi(old.google))
    ov = Counter(r['format'] for r in old.google)['Video']; nv = Counter(r['format'] for r in new.google)['Video']
    replace(S[6], f'Video chiếm {round(100*ov/len(old.google))}%', f'Video chiếm {round(100*nv/len(new.google))}%')

    # Slide 8: phễu theo nhóm
    def funnel(sn, grp):
        x = [r for r in sn.meta if r['group'] == grp]
        c = Counter(r['stage'] for r in x)
        return [fmt_n(len(x))] + [f'{round(100*c[k]/len(x))}%' for k in ('Nhận biết', 'Cân nhắc', 'Chuyển đổi')]
    g8 = grid(S[7])
    for lab, grp in (('Top 10', 'Top 10'), ('Xu hướng', 'Xu hướng')):
        cells = g8[lab][1]
        assert [c.text_frame.text for c in cells] == funnel(old, grp), (lab, [c.text_frame.text for c in cells])
        for c, v in zip(cells, funnel(new, grp)):
            set_text(c, v)

    def app_stats(sn):
        ca = [r for r in sn.meta if r['objective'] == 'Cài app']
        byp = Counter(r['pid'] for r in ca)
        nol = [r for r in sn.meta if r['pid'] != lps]
        return len(ca), byp[lps], byp['349312325177779'], round(100*sum(r['objective'] == 'Cài app' for r in nol)/len(nol))
    a, b = app_stats(old), app_stats(new)
    replace(S[7], f'{fmt_n(a[0])} ID Meta. Trong đó {a[1]} ID thuộc LPS, {a[2]} ID thuộc MBS',
            f'{fmt_n(b[0])} ID Meta. Trong đó {b[1]} ID thuộc LPS, {b[2]} ID thuộc MBS')
    replace(S[7], f'là {a[3]}%', f'là {b[3]}%')

    # Slide 9: App Google
    def app_rows(sn):
        c = Counter(r['competitor'] for r in sn.google if M.Period.is_app(r))
        rec = Counter(r['competitor'] for r in sn.last.google if M.Period.is_app(r) and r['active'] == 'True')
        return [(k, str(v), str(rec[k])) for k, v in c.most_common(7)], sum(c.values()), sum(rec.values()), rec['LPS']
    (orows, ot, orc, ol), (nrows, nt, nrc, nl) = app_rows(old), app_rows(new)
    g9 = sorted(grid(S[8]).values(), key=lambda t: t[0].top)
    assert [(l.text_frame.text, *[c.text_frame.text for c in cs]) for l, cs in g9] == orows
    for (l, cs), row in zip(g9, nrows):
        set_text(l, row[0]); set_text(cs[0], row[1]); set_text(cs[1], row[2])
    replace(S[8], f'{ot} creative App suy luận được quan sát. Tại mốc chốt có {orc} creative App hiển thị gần đây, trong đó {ol} thuộc LPS',
            f'{nt} creative App suy luận được quan sát. Tại mốc chốt có {nrc} creative App hiển thị gần đây, trong đó {nl} thuộc LPS')

    # Slide 12, 14, 15: bảng công ty
    def comp_cells(sn, name):
        pid, g = COMPANIES[name]
        return [str(len(sn.meta_of(pid))), str(sn.g_count(g)) if g else '—', str(sn.last.g_active(g)) if g else '—']
    for idx in (11, 13, 14):
        for lab, (l, cs) in grid(S[idx]).items():
            if lab not in COMPANIES:
                continue
            assert [c.text_frame.text for c in cs] == comp_cells(old, lab), (idx+1, lab, [c.text_frame.text for c in cs])
            for c, v in zip(cs, comp_cells(new, lab)):
                set_text(c, v)
    replace(S[11], 'mốc chốt 11/11', f'mốc chốt {NEW_LABEL}')
    replace(S[13], 'LPS có 753 ID Meta với 13 nội dung chữ khác nhau. VFS có 53 ID Meta và 73 creative Google quan sát được.',
            f'LPS có {len(new.meta_of(lps))} ID Meta với '
            f'{len({" ".join(r["body"].split()) for r in new.meta_of(lps)})} nội dung chữ khác nhau. '
            f'Shinhan tăng từ 34 lên {len(new.meta_of("101384519398514"))} ID Meta. VFS không còn creative Google hiển thị gần đây.')

    # Slide 13: Top 10 theo ID Meta
    def top4(sn):
        return sorted(((n, len(sn.meta_of(pid))) for n, pid, _ in M.TOP10), key=lambda t: -t[1])[:4]
    t_old, t_new = top4(old), top4(new)
    set_bars(S[12], t_new, t_old)
    replace(S[12], 'MBS, KIS và SSI dẫn Top 10 về ID Meta', f'{t_new[0][0]}, {t_new[1][0]} và {t_new[2][0]} dẫn Top 10 về ID Meta')
    for sh in text_shapes(S[12]):
        if sh.text_frame.text.startswith('MBS có 248 ID'):
            set_text(sh, f'MBS có {t_new[0][1]} ID, phần lớn dẫn về app. KIS nổi bật ở luồng web. '
                         f'VNDirect tăng lên {dict(t_new)["VNDirect"]} ID sau khi thay toàn bộ quảng cáo ở kỳ {NEW_LABEL}, '
                         'chủ yếu là quảng cáo động về DTRADE.')

    # Slide 16: chỉ trên Google
    for lab, (l, cs) in grid(S[15]).items():
        if lab in M.GOOGLE_ONLY:
            assert [c.text_frame.text for c in cs] == [str(old.g_count(lab)), str(old.last.g_active(lab))]
            set_text(cs[0], str(new.g_count(lab))); set_text(cs[1], str(new.last.g_active(lab)))
    replace(S[15], f'{old.last.g_active("DSC")} creative hiển thị gần đây', f'{new.last.g_active("DSC")} creative hiển thị gần đây')
    replace(S[15], f'DSC có {old.g_count("DSC")} creative', f'DSC có {new.g_count("DSC")} creative')

    # Slide 17: điểm đến
    od = Counter(M.dest_class(r) for r in old.meta); nd = Counter(M.dest_class(r) for r in new.meta)
    for lab, (l, cs) in grid(S[16]).items():
        if lab in od:
            assert cs[0].text_frame.text == str(od[lab]), (lab, cs[0].text_frame.text)
            set_text(cs[0], str(nd[lab]))

    # Hồ sơ từng công ty (slide 22–62)
    for s in S[21:62]:
        kicker, title = by_name(s, 'TextBox 7').text_frame.text, by_name(s, 'TextBox 8').text_frame.text
        name = title.split(' · ')[0]
        if name not in COMPANIES:
            continue
        pid, g = COMPANIES[name]
        if 'FACEBOOK ADS' in kicker:
            replace(s, meta_line(old.meta_of(pid)), meta_line(new.meta_of(pid)))
            for o, n in zip(funnel_line(old.meta_of(pid)), funnel_line(new.meta_of(pid))):
                replace(s, o, n)
        elif 'GOOGLE ADS' in kicker:
            for o, n in zip(google_lines(old.google, old.last, g), google_lines(new.google, new.last, g)):
                if o:
                    replace(s, o, n)
    lps_slide = S[40]
    replace(lps_slide, '753 ID chỉ có 13 nội dung chữ khác nhau',
            f'{len(new.meta_of(lps))} ID chỉ có {len({" ".join(r["body"].split()) for r in new.meta_of(lps)})} nội dung chữ khác nhau')

    # Phụ lục
    s = S[96]
    replace(s, 'Gộp theo ID từ dữ liệu 29/10 và 11/11/2026', f'Gộp theo ID từ dữ liệu 29/10, 11/11 và {NEW_LABEL}/2026')
    replace(s, 'tại mốc 11/11, 06:49 giờ Việt Nam', f'tại mốc {NEW_LABEL}/2026, 15:51 giờ Việt Nam')

    # ---------- phần mới, chèn sau Mục lục ----------
    pos = 3
    div = clone_slide(prs, S[3], pos); pos += 1
    exact(div, '01', NEW_LABEL)
    exact(div, 'Bức tranh chung', 'Có gì mới so với 11/11')
    set_text(by_name(div, 'TextBox 9'), 'Thay đổi của từng công ty trên Facebook Ads và Google Ads sau 11 ngày, kèm 10 quảng cáo mới.')

    for kick, ttl, cards in HEADLINES:
        sl = clone_slide(prs, S[1], pos); pos += 1
        exact(sl, 'TÓM TẮT', kick)
        exact(sl, 'Ba điều cần biết', ttl)
        for (h, body), (tb, bb) in zip(cards, (('TextBox 15', 'TextBox 16'), ('TextBox 20', 'TextBox 21'), ('TextBox 25', 'TextBox 26'))):
            set_text(by_name(sl, tb), h); set_text(by_name(sl, bb), body)

    def change_cells(name):
        pid, g = COMPANIES[name]
        fb_new = len(cur.meta_ids(pid) - prev.meta_ids(pid))
        return [f'{prev.meta_count(pid)} → {cur.meta_count(pid)}', str(fb_new),
                f'{prev.g_active(g)} → {cur.g_active(g)}' if g else '—']
    heads = ['Công ty', 'Facebook Ads · đang chạy', 'Facebook Ads · QC mới', 'Google Ads · đang chạy']
    note = (f'Mỗi ô “đang chạy” đọc theo thứ tự 11/11 → {NEW_LABEL}. QC mới là ID chưa có ở kỳ 11/11. '
            'Dấu “—” là công ty chưa có tài khoản Google Ads trong danh sách theo dõi.')
    for src_i, kick, ttl in ((11, f'KỲ {NEW_LABEL} · TOP 10', 'Top 10 · Thay đổi trên hai kênh'),
                             (13, f'KỲ {NEW_LABEL} · NGOÀI TOP 10', 'Nhóm xu hướng · 8 công ty đầu'),
                             (14, f'KỲ {NEW_LABEL} · NGOÀI TOP 10', 'Nhóm xu hướng · 7 công ty còn lại')):
        sl = clone_slide(prs, S[src_i], pos); pos += 1
        tx = text_shapes(sl)
        set_text(by_name(sl, 'TextBox 7'), kick); set_text(by_name(sl, 'TextBox 8'), ttl)
        hdr = sorted([sh for sh in tx if abs(sh.top/IN - 1.73) < 0.03], key=lambda s_: s_.left)
        for sh, h in zip(hdr, heads):
            set_text(sh, h)
        for lab, (l, cs) in grid(sl).items():
            if lab in COMPANIES:
                for c, v in zip(cs, change_cells(lab)):
                    set_text(c, v)
        for sh in tx:
            if sh.top/IN > 5.9 and sh.top/IN < 6.9 and len(sh.text_frame.text) > 40:
                set_text(sh, note)
    sl = clone_slide(prs, S[15], pos); pos += 1
    tx = text_shapes(sl)
    set_text(by_name(sl, 'TextBox 7'), f'KỲ {NEW_LABEL} · CHỈ TRÊN GOOGLE')
    hdr = sorted([sh for sh in tx if abs(sh.top/IN - 1.73) < 0.03], key=lambda s_: s_.left)
    for sh, h in zip(hdr, ['Công ty', 'Creative truy xuất', 'Đang chạy']):
        set_text(sh, h)
    for lab, (l, cs) in grid(sl).items():
        if lab in M.GOOGLE_ONLY:
            set_text(cs[0], f'{prev.g_total(lab)} → {cur.g_total(lab)}')
            set_text(cs[1], f'{prev.g_active(lab)} → {cur.g_active(lab)}')
    for sh in tx:
        if sh.text_frame.text.startswith('DSC có'):
            set_text(sh, f'DSC tăng từ {prev.g_active("DSC")} lên {cur.g_active("DSC")} creative đang chạy nhưng không có ID mới: '
                         'công ty bật lại các quảng cáo cũ. Năm công ty còn lại không có creative đang chạy ở cả hai kỳ.')

    rows = {r['ad_archive_id']: r for r in cur.meta}
    for smp in SAMPLES:
        r = rows[smp['ad']]
        sl = clone_slide(prs, S[64], pos); pos += 1
        set_text(by_name(sl, 'TextBox 7'), smp['kicker'])
        set_text(by_name(sl, 'TextBox 8'), smp['title'])
        set_text(by_name(sl, 'TextBox 15'), smp['meta'])
        set_text(by_name(sl, 'TextBox 17'), smp['how'])
        set_text(by_name(sl, 'TextBox 19'), smp['impl'])
        set_text(by_name(sl, 'TextBox 20'), f'CTA  ·  {smp["cta"]}')
        lib = f'https://www.facebook.com/ads/library/?id={smp["ad"]}'
        set_link(by_name(sl, 'TextBox 21'), lib)
        dest = by_name(sl, 'TextBox 22')
        if r['link_url']:
            set_link(dest, r['link_url'])
        else:
            set_text(dest, 'Không ghi nhận điểm đến')
            set_link(dest, None)
        pic = by_name(sl, 'Picture 13')
        _, rid = sl.part.get_or_add_image_part(str(THUMBS/f'{smp["thumb"]}.jpg'))
        pic._element.blipFill.blip.set(f'{R_NS}embed', rid)
        pic.click_action.hyperlink.address = lib

    # ---------- Mục lục ----------
    toc = S[2]
    first = div
    left = [sh for sh in toc.shapes if sh.left/IN < 4.5 and 1.95 < sh.top/IN < 6.2]
    step = int(0.48*IN)
    row0 = [sh for sh in left if abs(sh.top/IN - 2.00) < 0.02 or abs(sh.top/IN - 2.39) < 0.02]
    copies = [copy.deepcopy(sh._element) for sh in row0]
    for sh in left:
        sh.top += step
    for sh, el in zip(row0, copies):
        sh._element.addprevious(el)
    new_row = [sh for sh in toc.shapes if sh.left/IN < 4.5 and (abs(sh.top/IN - 2.00) < 0.02 or abs(sh.top/IN - 2.39) < 0.02)]
    for sh in new_row:
        if sh.has_text_frame and sh.text_frame.text and not sh.text_frame.text.isdigit():
            set_text(sh, f'Kỳ {NEW_LABEL} · Có gì mới')
        if sh.has_text_frame and sh.text_frame.text:
            sh.click_action.target_slide = first

    # ---------- số trang ----------
    slides = list(prs.slides)
    for i, s in enumerate(slides, 1):
        for sh in text_shapes(s):
            if sh.left/IN > 12.1 and sh.top/IN > 7.0 and sh.text_frame.text.isdigit():
                set_text(sh, str(i))
    for sh in text_shapes(toc):
        try:
            tgt = sh.click_action.target_slide
        except Exception:
            tgt = None
        if tgt is not None and sh.text_frame.text.isdigit():
            set_text(sh, str(slides.index(tgt) + 1))
    prs.save(DST)
    print('→', DST, len(slides), 'slide')
    export_pdf()


def export_pdf():
    """Xuất PDF bằng LibreOffice rồi bỏ video nhúng (giữ ảnh poster) để file < 25 MB, đưa được lên web."""
    import subprocess, tempfile, pymupdf
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['/Applications/LibreOffice.app/Contents/MacOS/soffice', '--headless', '--convert-to', 'pdf',
                        '--outdir', tmp, str(DST)], check=True, capture_output=True)
        doc = pymupdf.open(Path(tmp)/(DST.stem + '.pdf'))
        for page in doc:
            for a in list(page.annots(types=[pymupdf.PDF_ANNOT_SCREEN])):
                page.delete_annot(a)
        for x in range(1, doc.xref_length()):
            if doc.xref_is_stream(x) and '/EmbeddedFile' in doc.xref_object(x, compressed=True):
                doc.update_stream(x, b'')
        out = DST.with_suffix('.pdf')
        doc.save(out, garbage=4, deflate=True)
    print('→', out, f'{out.stat().st_size/1e6:.1f} MB')


if __name__ == '__main__':
    main()
