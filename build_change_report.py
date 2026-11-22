"""Trang 'Có gì mới' so sánh hai kỳ crawl của project chứng khoán.

python3 build_change_report.py --old projects/chung-khoan/crawl-2026-11-11 --new projects/chung-khoan/crawl-2026-11-22

Đọc all_ads.csv, competitors_summary.csv, google_all_ads.csv của 2 kỳ và ghi chú viết tay
<new>/ghi-chu-thay-doi.json ({"headlines": [...], "brands": {tên: ghi chú}}).
Ghi ra <new>/thay-doi.html, <new>/quang-cao-moi.csv, <new>/do-phu.csv.
"""
import argparse, csv, html, json, re
from collections import Counter
from datetime import date
from pathlib import Path

import dsc_theme as T

# (tên hiển thị, nhóm, Page ID Facebook, tên đối thủ trong google_all_ads.csv)
BRANDS = [
    ('VPS', 'Top 10', '108015722146379', 'VPS'), ('SSI', 'Top 10', '132771703438783', 'SSI'),
    ('TCBS', 'Top 10', '1504697249783367', 'TCBS'), ('Vietcap', 'Top 10', '343028851058', 'Vietcap'),
    ('HSC', 'Top 10', '1517153298580277', 'HSC'), ('MBS', 'Top 10', '349312325177779', None),
    ('VNDirect', 'Top 10', '123434971018658', 'VNDirect'), ('KIS', 'Top 10', '561500030387546', 'KIS'),
    ('Mirae Asset', 'Top 10', '303619527172219', None), ('VPBankS', 'Top 10', '107578535212906', 'VPBankS'),
    ('LPS', 'Ngoài', '197779796755847', 'LPS'), ('Nhất Việt - VFS', 'Ngoài', '273872576046675', 'Nhất Việt - VFS'),
    ('Shinhan - SSV', 'Ngoài', '101384519398514', 'Shinhan - SSV'), ('An Bình - ABS', 'Ngoài', '390676534851790', 'An Bình - ABS'),
    ('Yuanta', 'Ngoài', '131656534155296', 'Yuanta'), ('DNSE', 'Ngoài', '2033102266712313', 'DNSE'),
    ('Smart Invest - AAS', 'Ngoài', '1197026010336908', 'Smart Invest - AAS'), ('KB Securities', 'Ngoài', '458482900870297', 'KB Securities'),
    ('ACBS', 'Ngoài', '107317735256838', 'ACBS'), ('Rồng Việt', 'Ngoài', '134188476770555', 'Rồng Việt'),
    ('TPS - Tiên Phong', 'Ngoài', '2070825876552556', None), ('KIRIN', 'Ngoài', '106218628765203', None),
    ('Tân Việt', 'Ngoài', '171970319483394', None), ('HD Securities', 'Ngoài', '1112132331974304', None),
    ('VCBS', 'Ngoài', '151091451760284', 'VCBS'),
    ('DSC', 'Google', None, 'DSC'), ('Thiên Việt - TVS', 'Google', None, 'Thiên Việt - TVS'),
    ('ASEAN', 'Google', None, 'ASEAN'), ('Pinetree', 'Google', None, 'Pinetree'),
    ('SHS', 'Google', None, 'SHS'), ('Kiến Thiết - CSI', 'Google', None, 'Kiến Thiết - CSI'),
]
GROUPS = {'Top 10': 'Top 10 công ty chứng khoán', 'Ngoài': 'Ngoài Top 10 · tham khảo',
          'Google': 'Chỉ chạy Google Ads · tham khảo'}


def rows(p):
    return list(csv.DictReader(open(p, encoding='utf-8-sig')))


def ddmm(d):
    return f'{d[8:10]}/{d[5:7]}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', required=True)
    ap.add_argument('--new', required=True)
    a = ap.parse_args()
    old, new = Path(a.old), Path(a.new)
    d_old, d_new = re.search(r'\d{4}-\d\d-\d\d', old.name)[0], re.search(r'\d{4}-\d\d-\d\d', new.name)[0]
    notes = json.load(open(new/'ghi-chu-thay-doi.json', encoding='utf-8'))

    def fb(d):
        ads = rows(d/'all_ads.csv')
        name2id = {r['page_name']: r['page_id'] for r in rows(d/'competitors_summary.csv')}
        summ = {r['page_id']: r for r in rows(d/'competitors_summary.csv')}
        for r in ads:
            r['pid'] = name2id.get(r['page_name'], '')
        return ads, summ
    om, osum = fb(old)
    nm, nsum = fb(new)
    og, ng = rows(old/'google_all_ads.csv'), rows(new/'google_all_ads.csv')
    o_ids = {r['ad_archive_id'] for r in om}
    n_ids = {r['ad_archive_id'] for r in nm}
    og_ids = {r['creative_id'] for r in og}
    act = lambda r: r['active'] == 'True'

    table = []
    for label, grp, pid, gname in BRANDS:
        e = dict(label=label, grp=grp, note=notes['brands'].get(label, ''))
        if pid:
            e['fb_old'] = sum(r['pid'] == pid for r in om)
            e['fb_new'] = sum(r['pid'] == pid for r in nm)
            e['fb_add'] = sum(r['pid'] == pid and r['ad_archive_id'] not in o_ids for r in nm)
            e['fb_stop'] = sum(r['pid'] == pid and r['ad_archive_id'] not in n_ids for r in om)
            e['fb_des_old'] = int((osum.get(pid) or {}).get('creatives') or 0)
            e['fb_des_new'] = int((nsum.get(pid) or {}).get('creatives') or 0)
        if gname:
            e['g_old'] = sum(r['competitor'] == gname and act(r) for r in og)
            e['g_new'] = sum(r['competitor'] == gname and act(r) for r in ng)
            e['g_add'] = sum(r['competitor'] == gname and r['creative_id'] not in og_ids for r in ng)
        table.append(e)

    # CSV quảng cáo mới + độ phủ
    with open(new/'quang-cao-moi.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['kenh', 'cong_ty', 'id', 'ngay_bat_dau', 'lan_cuoi_hien_thi', 'dinh_dang', 'nen_tang',
                    'tieu_de', 'noi_dung', 'cta', 'trang_dich', 'tang_pheu', 'loai_chien_dich', 'link'])
        for r in sorted(nm, key=lambda r: (r['page_name'], r['start_date'])):
            if r['ad_archive_id'] not in o_ids:
                w.writerow(['Facebook Ads', r['page_name'], r['ad_archive_id'], r['start_date'], '', r['format'],
                            r['platforms'], r['title'], r['body'], r['cta'], r['final_url'] or r['link_url'],
                            r['stage'], r['objective'], r['library_link']])
        for r in sorted(ng, key=lambda r: (r['competitor'], r['first_shown'])):
            if r['creative_id'] not in og_ids:
                w.writerow(['Google Ads', r['competitor'], r['creative_id'], r['first_shown'], r['last_shown'],
                            r['format'], r['platforms'], r['video_title'], '', '', r['domain'], '', '', r['link']])
    with open(new/'do-phu.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cong_ty', 'nhom', f'fb_dang_chay_{d_old}', f'fb_dang_chay_{d_new}', 'fb_moi', 'fb_dung',
                    f'fb_mau_{d_old}', f'fb_mau_{d_new}', f'google_dang_chay_{d_old}', f'google_dang_chay_{d_new}', 'google_moi'])
        for e in table:
            w.writerow([e['label'], GROUPS[e['grp']]] + [e.get(k, '') for k in
                        ('fb_old', 'fb_new', 'fb_add', 'fb_stop', 'fb_des_old', 'fb_des_new', 'g_old', 'g_new', 'g_add')])

    # Tổng
    fb_add_total = len(n_ids - o_ids)
    fb_add_after = sum(r['ad_archive_id'] not in o_ids and r['start_date'] >= d_old for r in nm)
    g_add_total = len({r['creative_id'] for r in ng} - og_ids)
    stage = Counter(r['stage'] for r in nm if r['ad_archive_id'] not in o_ids)
    tot = dict(fb_old=len(om), fb_new=len(nm), g_old=sum(map(act, og)), g_new=sum(map(act, ng)))

    esc = html.escape

    def delta(a_, b_):
        if a_ is None or b_ is None:
            return '<td class="na">—</td>'
        d = b_ - a_
        cls = 'up' if d > 0 else 'down' if d < 0 else 'flat'
        sign = f'+{d}' if d > 0 else (f'−{-d}' if d < 0 else '±0')
        return f'<td class="num">{a_} → <b>{b_}</b> <span class="{cls}">{sign}</span></td>'

    def cell(v):
        return f'<td class="num">{v}</td>' if v is not None else '<td class="na">—</td>'

    rows_html = []
    for g in GROUPS:
        rows_html.append(f'<tr class="grp"><th colspan="6">{GROUPS[g]}</th></tr>')
        for e in [x for x in table if x['grp'] == g]:
            rows_html.append(
                f'<tr><th scope="row">{esc(e["label"])}</th>'
                + delta(e.get('fb_old'), e.get('fb_new')) + cell(e.get('fb_add')) + cell(e.get('fb_stop'))
                + delta(e.get('g_old'), e.get('g_new')) + cell(e.get('g_add')) + '</tr>'
                + (f'<tr class="note"><td></td><td colspan="5">{esc(e["note"])}</td></tr>' if e['note'] else ''))

    heads = ''.join(f'<article class="hl"><span class="n">{i:02d}</span><div><h3>{esc(h["title"])}</h3>'
                    f'<p class="ev"><b>Số liệu:</b> {esc(h["evidence"])}</p><p>{esc(h["insight"])}</p></div></article>'
                    for i, h in enumerate(notes['headlines'], 1))
    st_txt = ' · '.join(f'{k} {v}' for k, v in stage.most_common())

    page = f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cập nhật đối thủ {ddmm(d_new)}</title>{T.FONT_LINK}<style>{T.BASE_CSS}
main{{max-width:1080px;margin:0 auto;padding:var(--space-3) 16px var(--space-4)}}
.lede{{color:var(--ink-muted);margin:0 0 var(--space-3)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));border-top:1px solid var(--hairline)}}
.kpi{{padding:var(--space-2) var(--space-2) var(--space-2) 0;border-bottom:1px solid var(--line)}}
.kpi .l{{font-size:13px;color:var(--ink-muted);font-weight:600}}.kpi .v{{font-size:28px;font-weight:700;line-height:1.2}}
.kpi .s{{font-size:13px;color:var(--ink-muted)}}
.hl{{display:grid;grid-template-columns:48px 1fr;gap:var(--space-2);padding:var(--space-2) 0;border-bottom:1px solid var(--line)}}
.hl .n{{font-size:20px;font-weight:700;color:var(--accent-text)}}.hl h3{{margin:0 0 4px}}.hl p{{margin:4px 0}}
.ev{{font-size:14px;color:var(--ink-muted)}}
.wrap{{overflow-x:auto}}table.t td.num{{white-space:nowrap;font-variant-numeric:tabular-nums}}
table.t tr.grp th{{background:var(--surface-alt);color:var(--ink);padding-top:12px}}
table.t tr.note td{{border-bottom:1px solid var(--line);font-size:13px;color:var(--ink-muted);padding-top:0}}
table.t tr:has(+ tr.note) > *{{border-bottom:0}}
.up{{color:var(--accent-text);font-weight:700}}.down{{color:#b3261e;font-weight:700}}.flat{{color:var(--ink-muted)}}
:root[data-theme=dark] .down{{color:#ff8a80}}@media (prefers-color-scheme:dark){{:root:not([data-theme=light]) .down{{color:#ff8a80}}}}
.na{{color:var(--ink-muted)}}dl{{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;font-size:14px}}dt{{font-weight:700}}dd{{margin:0}}
ul.lim li{{margin:4px 0;font-size:14px}}
</style></head><body>{T.BRAND_STRIP}<main>
<h1>Đối thủ chứng khoán: có gì mới từ {ddmm(d_old)} đến {ddmm(d_new)}</h1>
<p class="lede">So sánh hai lần crawl Meta Ad Library (Facebook Ads) và Google Ads Transparency Center, khu vực Việt Nam, cùng danh sách 25 fanpage và 31 tài khoản Google Ads. Ngày crawl: {date.fromisoformat(d_old):%d/%m/%Y} và {date.fromisoformat(d_new):%d/%m/%Y}.</p>
<section class="kpis">
<div class="kpi"><div class="l">Facebook Ads · QC đang chạy</div><div class="v">{tot["fb_old"]} → {tot["fb_new"]}</div><div class="s">LPS chiếm {sum(r["pid"]=="197779796755847" for r in nm)} QC kỳ này</div></div>
<div class="kpi"><div class="l">Facebook Ads · QC mới</div><div class="v">{fb_add_total}</div><div class="s">{fb_add_after} QC bắt đầu chạy từ {ddmm(d_old)}</div></div>
<div class="kpi"><div class="l">Google Ads · creative đang chạy</div><div class="v">{tot["g_old"]} → {tot["g_new"]}</div><div class="s">Search, YouTube, Display, Play</div></div>
<div class="kpi"><div class="l">Google Ads · creative mới</div><div class="v">{g_add_total}</div><div class="s">ID chưa có ở kỳ {ddmm(d_old)}</div></div>
</section>
<h2>Điểm đáng chú ý</h2>{heads}
<h2>Từng công ty</h2>
<p class="lede">“Đang chạy” là số quảng cáo đang hoạt động tại ngày crawl. “Mới” là ID chưa xuất hiện ở kỳ trước; “Dừng” là ID có ở kỳ trước nhưng không còn chạy. Dấu — nghĩa là công ty không có tài khoản trên kênh đó. Các tầng phễu của QC Facebook Ads mới: {esc(st_txt)}.</p>
<div class="wrap"><table class="t"><thead><tr><th>Công ty</th><th>Facebook Ads · đang chạy</th><th>FB mới</th><th>FB dừng</th><th>Google Ads · đang chạy</th><th>Google mới</th></tr></thead>
<tbody>{"".join(rows_html)}</tbody></table></div>
<h2>Cách đọc và giới hạn</h2>
<dl><dt>Facebook Ads</dt><dd>Quảng cáo trên Facebook, Instagram, Messenger, lấy từ Meta Ad Library. Meta chỉ công bố QC đang chạy của nhà quảng cáo thương mại ở VN.</dd>
<dt>Google Ads</dt><dd>Quảng cáo Search, YouTube, Display và quảng cáo cài app (Play), lấy từ Google Ads Transparency Center.</dd></dl>
<ul class="lim">
<li>Số quảng cáo không phản ánh ngân sách. Một mẫu thiết kế có thể được nhân thành hàng chục QC, nên LPS có số QC lớn hơn hẳn các công ty khác.</li>
<li>Fanpage VPS trả về 0 QC ở cả hai kỳ, nên VPS chưa được quan sát trên Facebook Ads.</li>
<li>Một số ID Google Ads mới đã hiển thị lần đầu từ nhiều tháng trước, ví dụ của SSI. Đó là quảng cáo cũ mới được ghi nhận, không phải chiến dịch mới.</li>
<li>Các nhận định về lý do (ví dụ mùa cao điểm cuối năm) là giả thuyết, cần kiểm tra lại ở kỳ crawl sau.</li></ul>
<p><a href="report.html">Báo cáo Facebook Ads đầy đủ kỳ {ddmm(d_new)}</a> · <a href="report_google.html">Báo cáo Google Ads</a> · <a href="quang-cao-moi.csv">Tải danh sách QC mới (CSV)</a> · <a href="do-phu.csv">Bảng số liệu theo công ty (CSV)</a></p>
{T.footer("DSC · Theo dõi quảng cáo đối thủ", f"Crawl {date.fromisoformat(d_new):%d/%m/%Y}")}
</main></body></html>'''
    (new/'thay-doi.html').write_text(page, encoding='utf-8')
    print('→', new/'thay-doi.html', '| FB mới', fb_add_total, '| Google mới', g_add_total)


if __name__ == '__main__':
    main()
