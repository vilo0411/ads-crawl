"""Cập nhật báo cáo media tổng hợp (Word) sang ba kỳ 29/10, 11/11, 22/11 và xuất PDF bằng LibreOffice.

python3 update_media_report.py
Cần font Plus Jakarta Sans trong ~/Library/Application Support/LibreOffice/4/user/fonts.
"""
import copy
import subprocess
from collections import Counter

import docx
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn

import media_period_metrics as M
from update_media_deck import SAMPLES, THUMBS

OUT = M.PROJ/'bao-cao-media'
SRC = OUT/'Doi_thu_chung_khoan_media_tong_hop_29-10_den_11-11-2026.docx'
DST = OUT/'Doi_thu_chung_khoan_media_tong_hop_29-10_den_22-11-2026.docx'
SOFFICE = '/Applications/LibreOffice.app/Contents/MacOS/soffice'


def all_paragraphs(d):
    for p in d.paragraphs:
        yield p
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                yield from c.paragraphs
    for s in d.sections:
        yield from s.header.paragraphs
        yield from s.footer.paragraphs


def set_par(p, text):
    runs = p.runs
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def replace(d, old, new):
    hits = 0
    for p in all_paragraphs(d):
        if old in p.text:
            hits += 1
            one = [r for r in p.runs if old in r.text]
            if one:
                one[0].text = one[0].text.replace(old, new)
            else:
                set_par(p, p.text.replace(old, new))
    if not hits:
        raise SystemExit(f'Không tìm thấy “{old}”')


def para_set(d, startswith, text):
    hit = [p for p in d.paragraphs if p.text.startswith(startswith)]
    if not hit:
        raise SystemExit(f'Không có đoạn bắt đầu “{startswith}”')
    for p in hit:
        set_par(p, text)


def cell_set(cell, text):
    set_par(cell.paragraphs[0], text)


def add_column(table, values):
    """Thêm cột cuối bằng cách nhân bản cột cuối hiện có; chia lại độ rộng các cột sau cột đầu."""
    grid = table._tbl.tblGrid
    cols = grid.findall(qn('w:gridCol'))
    total = sum(int(c.get(qn('w:w'))) for c in cols)
    grid.append(copy.deepcopy(cols[-1]))
    cols = grid.findall(qn('w:gridCol'))
    first = int(cols[0].get(qn('w:w')))
    rest = (total - first)//(len(cols) - 1)
    widths = [first] + [rest]*(len(cols) - 1)
    for c, w in zip(cols, widths):
        c.set(qn('w:w'), str(w))
    for row, v in zip(table.rows, values):
        tc = copy.deepcopy(row._tr.findall(qn('w:tc'))[-1])
        row._tr.append(tc)
        for tcx, w in zip(row._tr.findall(qn('w:tc')), widths):
            tcw = tcx.find(qn('w:tcPr')).find(qn('w:tcW'))
            if tcw is not None:
                tcw.set(qn('w:w'), str(w)); tcw.set(qn('w:type'), 'dxa')
        cell_set(row.cells[-1], v)


def text_of(el):
    return ''.join(x.text or '' for x in el.iter(qn('w:t')))


def main():
    d = docx.Document(SRC)
    ps = M.load()
    p1, p2, p3 = ps
    arrow = lambda *v: ' → '.join(str(x) for x in v)

    # Đầu trang, tiêu đề
    replace(d, '29.10–11.11.2026', '29.10–22.11.2026')
    d.core_properties.title = 'Quảng cáo đối thủ chứng khoán · Báo cáo media tổng hợp 29/10–22/11/2026'
    replace(d, 'Hai kỳ quan sát 29/10 và 11/11/2026', 'Ba kỳ quan sát 29/10, 11/11 và 22/11/2026')

    o_m = {r['ad_archive_id'] for r in p2.meta}
    new_m = [r for r in p3.meta if r['ad_archive_id'] not in o_m]
    o_g = {r['creative_id'] for r in p2.google}
    new_g = [r for r in p3.google if r['creative_id'] not in o_g]

    t = d.tables
    for c, v in zip(t[0].rows[0].cells, ['Meta đang hoạt động', 'Google hiển thị gần đây', 'ID mới từ 11/11']):
        cell_set(c, v)
    for c, v in zip(t[0].rows[1].cells, [arrow(len(p1.meta), len(p2.meta), len(p3.meta)),
                                          arrow(p1.g_active(), p2.g_active(), p3.g_active()),
                                          f'{len(new_m)} Meta · {len(new_g)} Google']):
        cell_set(c, v)

    lps = '197779796755847'
    para_set(d, 'Meta tăng nhẹ về số ID', 'Meta giảm mạnh về số ID, chủ yếu do LPS.')
    para_set(d, 'Meta tăng từ 844 lên 868 ID',
             f'Meta giảm từ {len(p2.meta)} xuống {len(p3.meta)} ID. LPS giảm từ {p2.meta_count(lps)} xuống {p3.meta_count(lps)} ID '
             f'nhưng số mẫu thiết kế tăng từ 11 lên 30. Không tính LPS, tổng gần như không đổi '
             f'({len(p2.meta)-p2.meta_count(lps)} → {len(p3.meta)-p3.meta_count(lps)}). '
             f'Trong {len(new_m)} ID Meta mới, {sum(r["pid"] == lps for r in new_m)} thuộc LPS.')
    para_set(d, 'Google ghi nhận ít creative', 'Shinhan tăng trên cả hai kênh, VFS dừng Google.')
    para_set(d, 'Tổng số creative trong mỗi lần truy xuất',
             f'Shinhan tăng từ 2 lên 35 ID Meta và từ 5 lên 17 creative Google hiển thị gần đây, cùng thông điệp 0% phí trọn đời '
             f'và lãi margin ưu đãi. VFS giảm từ 53 xuống 0 creative Google hiển thị gần đây. Tổng creative Google hiển thị gần đây '
             f'giảm từ {p2.g_active()} xuống {p3.g_active()}.')
    para_set(d, 'Thông điệp ưu đãi đi cùng', 'Lãi margin trở thành thông điệp cạnh tranh chính.')
    para_set(d, 'Qua hai kỳ, LPS duy trì',
             '149/291 ID Meta mới nhắc margin hoặc lãi vay, trong đó LPS chiếm 99. Ngoài LPS còn Shinhan (margin 0%), MBS (7,5%), '
             'Yuanta (6,8%) và KBSV. VNDIRECT thay toàn bộ quảng cáo Meta bằng 28 ID quảng bá tính năng DTRADE, không dùng quà.')
    para_set(d, 'Trang 2–7 đối chiếu',
             'Các trang đầu đối chiếu độ phủ, đối thủ, định dạng, phễu và Google Play qua ba kỳ. Phần thư viện phân tích 26 mẫu của '
             'hai kỳ đầu và 10 mẫu mới của kỳ 22/11. Trang cuối ghi hướng thử nghiệm và cách đọc dữ liệu.')

    # Ba kỳ quan sát
    replace(d, 'HAI KỲ QUAN SÁT', 'BA KỲ QUAN SÁT')
    cell_set(t[1].rows[0].cells[0], 'Chỉ số')
    add_column(t[1], ['22/11', str(len(p3.meta)), str(p3.snapshot['meta']['assets']), str(p3.fanpages_with_data()),
                      str(p3.g_total()), str(p3.g_active()), str(p3.app()), str(p3.app(active=True))])
    both_m = len(p3.meta) - len(new_m); both_g = len(p3.google) - len(new_g)
    rows2 = [('ID giữa 11/11 và 22/11', 'Meta', 'Google'),
             ('Có mặt ở cả hai kỳ', both_m, both_g),
             ('Chỉ xuất hiện trong dữ liệu 22/11', len(new_m), len(new_g)),
             ('Trong nhóm trên, bắt đầu từ 11/11', sum(r['start_date'] >= '2026-11-11' for r in new_m),
              sum(r['first_shown'] >= '2026-11-11' for r in new_g)),
             ('Chỉ xuất hiện trong dữ liệu 11/11', len(p2.meta) - both_m, len(p2.google) - both_g),
             ('Tổng ID phân biệt qua ba kỳ', len(M.union_meta(ps)), len(M.union_google(ps)))]
    for row, vals in zip(t[2].rows, rows2):
        for c, v in zip(row.cells, vals):
            cell_set(c, str(v))
    para_set(d, 'Trong 530 ID Meta',
             f'Trong {len(new_m)} ID Meta và {len(new_g)} ID Google chỉ có ở kỳ 22/11, '
             f'{sum(r["start_date"] < "2026-11-11" for r in new_m)} ID Meta và {sum(r["first_shown"] < "2026-11-11" for r in new_g)} ID Google '
             'có ngày bắt đầu hoặc hiển thị lần đầu trước 11/11. Chênh lệch số ID giữa các kỳ phản ánh thay đổi trong tập dữ liệu quan sát.')

    # Hồ sơ đối thủ
    replace(d, 'Top 10 qua hai kỳ', 'Top 10 qua ba kỳ')
    replace(d, 'Mỗi ô đọc theo thứ tự 29/10 → 11/11.', 'Mỗi ô đọc theo thứ tự 29/10 → 11/11 → 22/11.')
    names = {n: (pid, g) for n, pid, g in M.TOP10 + M.TREND}
    for tbl in (t[3], t[4]):
        for row in tbl.rows[1:]:
            pid, g = names[row.cells[0].text]
            assert row.cells[1].text == arrow(p1.meta_count(pid), p2.meta_count(pid)), row.cells[0].text
            cell_set(row.cells[1], arrow(p1.meta_count(pid), p2.meta_count(pid), p3.meta_count(pid)))
            cell_set(row.cells[2], arrow(p1.g_active(g), p2.g_active(g), p3.g_active(g)) if g else '—')
    for row in t[5].rows[1:]:
        g = row.cells[0].text
        cell_set(row.cells[1], arrow(p1.g_total(g), p2.g_total(g), p3.g_total(g)))
        cell_set(row.cells[2], arrow(p1.g_active(g), p2.g_active(g), p3.g_active(g)))
    para_set(d, 'MBS giảm từ 148 xuống 107 ID',
             'MBS giảm từ 107 xuống 69 ID nhưng vẫn đứng đầu Top 10. VNDIRECT tăng từ 11 lên 28 ID, toàn bộ là quảng cáo mới. '
             'KIS giữ 25 ID, TCBS tăng từ 1 lên 6. Vietcap giảm từ 13 xuống 3 và Mirae Asset về 0.')
    para_set(d, 'Google gần đây tập trung ở cùng bốn công ty', 'SSI vẫn dẫn Google gần đây trong Top 10.')
    para_set(d, 'SSI, Vietcap, VNDIRECT và KIS đều có',
             'SSI giảm từ 65 xuống 57 creative hiển thị gần đây nhưng vẫn chiếm phần lớn của Top 10. HSC có 4 video YouTube mới cắt từ '
             'hội thảo C2C. KIS và VNDIRECT giữ 7 và 6. Dấu “—” chỉ công ty chưa có tài khoản Google trong danh sách cào.')
    para_set(d, 'LPS tăng ở cả hai cột',
             'LPS giảm từ 568 xuống 345 ID Meta nhưng tăng từ 30 lên 34 creative Google gần đây. Shinhan tăng từ 2 lên 35 ID Meta và '
             'từ 5 lên 17 creative Google. VFS giảm về 0 creative Google gần đây; AAS dừng toàn bộ quảng cáo Meta.')
    para_set(d, 'DSC có creative hiển thị gần đây ở cả hai kỳ', 'DSC bật lại quảng cáo cũ trên Google.')
    para_set(d, 'Số creative gần đây của DSC',
             f'Số creative gần đây của DSC tăng từ {p2.g_active("DSC")} lên {p3.g_active("DSC")}, không có ID mới. '
             'Năm công ty còn lại trả về 0 theo ngưỡng gần đây ở cả ba mốc.')
    acc = len({r['advertiser_id'] for r in p3.google}); comp = len({r['competitor'] for r in p3.google})
    para_set(d, 'Google có 31 tài khoản',
             f'Google có 31 tài khoản được kiểm tra tại kỳ 22/11. Nguồn trả về ít nhất một creative cho {acc} tài khoản, thuộc {comp} công ty. '
             'Một công ty có thể có nhiều tài khoản quảng cáo.')

    # Định dạng và phễu
    f3 = p3.formats()
    main_f = ['Ảnh đơn', 'Video', 'Dynamic (DCO)', 'Carousel', 'Nhiều ảnh']
    add_column(t[6], ['22/11'] + [str(f3[k]) for k in main_f] + [str(sum(v for k, v in f3.items() if k not in main_f))])
    add_column(t[7], ['22/11'] + [' / '.join(f'{x}%' for x in p3.funnel(g)) for g in ('Top 10', 'Xu hướng')])
    para_set(d, 'Ảnh đơn tăng, video giảm trên Meta', 'Ảnh đơn giảm, video và nhiều ảnh tăng trên Meta')
    s2, s3 = round(100*p2.formats()['Ảnh đơn']/len(p2.meta)), round(100*f3['Ảnh đơn']/len(p3.meta))
    para_set(d, 'Ảnh đơn tăng từ 69% lên 80%',
             f'Tỷ trọng ảnh đơn giảm từ {s2}% xuống {s3}% toàn bộ Meta, chủ yếu do LPS cắt bớt quảng cáo ảnh. Video tăng từ '
             f'{p2.formats()["Video"]} lên {f3["Video"]} ID, nhiều ảnh từ {p2.formats()["Nhiều ảnh"]} lên {f3["Nhiều ảnh"]}. Trong Top 10, '
             f'tỷ trọng ID gắn chuyển đổi tăng từ {p2.funnel("Top 10")[2]}% lên {p3.funnel("Top 10")[2]}%; nhóm xu hướng giảm từ '
             f'{p2.funnel("Xu hướng")[2]}% xuống {p3.funnel("Xu hướng")[2]}%. Cơ cấu chịu ảnh hưởng của số bản lặp theo từng công ty.')

    # Google Play
    replace(d, 'Google Play qua hai kỳ', 'Google Play qua ba kỳ')
    tb = t[8]
    total_row = tb.rows[-1]
    new_tr = copy.deepcopy(tb.rows[-2]._tr)
    total_row._tr.addprevious(new_tr)
    gmap = {'LPS': 'LPS', 'An Bình - ABS': 'An Bình - ABS', 'SSI': 'SSI', 'DNSE': 'DNSE', 'KB Securities': 'KB Securities',
            'Vietcap': 'Vietcap', 'Shinhan - SSV': 'Shinhan - SSV'}
    for c, v in zip(tb.rows[-2].cells, ['Shinhan - SSV', str(p1.app('Shinhan - SSV', True)), str(p2.app('Shinhan - SSV', True))]):
        cell_set(c, v)
    vals = ['App gần đây 22/11'] + [str(p3.app(gmap[r.cells[0].text], True)) for r in tb.rows[1:-1]] + [str(p3.app(active=True))]
    add_column(tb, vals)
    para_set(d, 'LPS tăng từ 12 lên 14 creative App',
             f'Creative App hiển thị gần đây tăng từ {p2.app(active=True)} lên {p3.app(active=True)}.')
    para_set(d, 'Trong 32 ID Google mới',
             f'LPS có {p3.app("LPS", True)} và Shinhan có {p3.app("Shinhan - SSV", True)} creative App hiển thị gần đây. Trong {len(new_g)} '
             f'ID Google mới, {sum("YouTube" in r["platforms"] for r in new_g)} có nhãn YouTube, '
             f'{sum("Search" in r["platforms"] for r in new_g)} có nhãn Search và {sum("Play" in r["platforms"] for r in new_g)} có nhãn Play. '
             'Các số đếm này có thể trùng ID giữa các cột.')
    v3 = [r for r in p3.google if r['format'] == 'Video']
    replace(d, 'Kỳ 11/11 có 197/719.', f'Kỳ 11/11 có 197/719. Kỳ 22/11 có {sum(not r["youtube_id"] for r in v3)}/{len(v3)}.')

    # Thư viện mẫu kỳ 22/11: nhân bản khối một trang (ngắt trang + 3 tiêu đề + 2 bảng mẫu)
    body = d.element.body
    els = list(body)
    start = next(i for i, el in enumerate(els) if text_of(el) == 'LPS · Chi phí và cài app') - 2
    block = els[start:start + 8]
    anchor = next(el for el in els if text_of(el) == 'ỨNG DỤNG CHO TEAM MEDIA')
    anchor = anchor.getprevious()  # đoạn ngắt trang trước trang cuối
    pages = [('Shinhan và LPS · Hai cách nói về chi phí', 'Một mẫu gộp phí và lãi, một mẫu quy đổi tiền lãi ra số tiền', (0, 2)),
             ('MBS và Yuanta · Margin bằng con số', 'Một mẫu quy đổi ra tiền tiết kiệm, một mẫu cần cập nhật thời hạn', (3, 4)),
             ('VNDirect và SSI · Tính năng trong app', 'Giao diện thật và deep link tới màn hình tính năng', (1, 7)),
             ('KIS và TCBS · Quà gắn với từng bước', 'Số bước và thời hạn được ghi ngay trong caption', (5, 6)),
             ('VPBankS và VCBS · Sự kiện cuối năm', 'Hội thảo chiến lược 2027 và fan meeting tháng 12', (8, 9))]
    cur_rows = {r['ad_archive_id']: r for r in p3.meta}
    for title, sub, (a, b) in pages:
        new = [copy.deepcopy(el) for el in block]
        for el in new:
            anchor.addprevious(el)
        P = lambda el: docx.text.paragraph.Paragraph(el, d._body)
        set_par(P(new[1]), 'MẪU MỚI KỲ 22/11')
        set_par(P(new[2]), title)
        set_par(P(new[3]), sub)
        for tbl_el, smp in ((new[4], SAMPLES[a]), (new[6], SAMPLES[b])):
            tbl = docx.table.Table(tbl_el, d._body)
            r = cur_rows[smp['ad']]
            c0, c1 = tbl.rows[0].cells
            rid, _ = d.part.get_or_add_image(str(THUMBS/f'{smp["thumb"]}.jpg'))
            blip = c0._tc.find('.//' + qn('a:blip'))
            blip.set(qn('r:embed'), rid)
            ext = c0._tc.find('.//' + qn('wp:extent'))
            for e in c0._tc.iter():
                if e.tag in (qn('wp:extent'), qn('a:ext')) and e.get('cx'):
                    e.set('cy', e.get('cx'))
            set_par(c0.paragraphs[-1], 'Ảnh xem trước Meta')
            ps_ = c1.paragraphs
            set_par(ps_[0], smp['title'])
            set_par(ps_[1], 'Kỳ 22/11 · Meta · ' + smp['meta'])
            set_par(ps_[2], smp['how'])
            set_par(ps_[3], f'CTA quan sát được là “{smp["cta"]}”.' if smp['cta'] != 'Không có nút' else 'Quảng cáo không gắn nút CTA.')
            set_par(ps_[4], smp['impl'])
            links = ps_[5]._p.findall(qn('w:hyperlink'))
            lib = f'https://www.facebook.com/ads/library/?id={smp["ad"]}'
            links[0].set(qn('r:id'), d.part.relate_to(lib, RT.HYPERLINK, is_external=True))
            if r['link_url']:
                links[1].set(qn('r:id'), d.part.relate_to(r['link_url'], RT.HYPERLINK, is_external=True))
                ts = links[1].findall('.//' + qn('w:t'))
                ts[0].text = 'Điểm đến trong dữ liệu'
                for x in ts[1:]:
                    x.text = ''
            else:
                sep = links[1].getprevious()
                links[1].getparent().remove(links[1])
                if sep is not None and text_of(sep).strip() == '·':
                    sep.getparent().remove(sep)

    # Nguồn và phương pháp
    para_set(d, 'Dữ liệu lấy từ hai snapshot',
             'Dữ liệu lấy từ ba snapshot lưu trong dự án. Mốc tham chiếu lần lượt là 14:29 ngày 29/10, 06:49 ngày 11/11 và 15:51 ngày '
             '22/11 theo giờ Việt Nam. Kỳ 22/11 dựa trên 25 fanpage Meta và 31 tài khoản Google đã cấu hình.')
    replace(d, 'Hai mốc cho biết trạng thái', 'Mỗi mốc cho biết trạng thái')
    replace(d, 'Creative có thể thay đổi giữa hai lần cào', 'Creative có thể thay đổi giữa các lần cào')
    replace(d, 'Danh sách ID mới nằm trong crawl-2026-11-11/quang-cao-moi.csv.',
            'Danh sách ID mới nằm trong quang-cao-moi.csv của crawl-2026-11-11 và crawl-2026-11-22.')

    d.save(DST)
    subprocess.run([SOFFICE, '--headless', '--convert-to', 'pdf', '--outdir', str(OUT), str(DST)],
                   check=True, capture_output=True)
    print('→', DST, '+ PDF')


if __name__ == '__main__':
    main()
