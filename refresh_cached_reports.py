"""Rebuild derived reports and existing pack metadata without network or media changes.

python3 refresh_cached_reports.py --project chung-khoan --as-of 2026-10-29T14:29:00+07:00
Uses the exported visual IDs so a cached rebuild does not silently re-cluster assets.
"""
import argparse
import csv
import json
from pathlib import Path

import competitor_intel as ci
import google_ads_intel as gai
import google_app_report as gar
import google_report as gr
import google_winner_pack as gwp
import report_builder as rb
import report_quality as rq
import winner_pack as wp


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def refresh_meta(proj):
    exports = {r['ad_archive_id']: r for r in read_csv(proj / 'all_ads.csv')}
    entries = ci.read_competitors(proj / 'competitors.txt')
    rows = []
    for pid in dict.fromkeys(e['pid'] for e in entries):
        cache = proj / 'pages' / f'{pid}.json'
        if not cache.exists():
            raise ValueError(f'Missing cache: {cache}')
        rows.extend(json.loads(cache.read_text()))
    if {r['ad_archive_id'] for r in rows} != set(exports):
        raise ValueError('Cache and CSV contain different ad IDs; run analyze before a cached rebuild.')
    ci.enrich(rows, ci.load_landings(proj))
    for r in rows:
        exported = exports[r['ad_archive_id']]
        for key in ['asset_id', 'variant_id', 'aspect']:
            r[key] = exported[key]
        r['video_duration'] = float(exported['video_duration']) if exported['video_duration'] else None
        r['thumb_local'] = f"thumbs/{r['collation_id']}.jpg" if (proj / 'thumbs' / f"{r['collation_id']}.jpg").exists() else ''
    stats = ci.competitor_stats(rows, entries)
    rb.render(proj.name, proj, rows, stats, has_landings=bool(ci.load_landings(proj)), signal_keys=list(ci.COPY_SIGNALS))
    # The raw export remains the source of the visual grouping and observation ages.
    summary = []
    for s in stats:
        item = dict.fromkeys(read_csv(proj / 'competitors_summary.csv')[0], '')
        item.update(group=s['group'], page_name=s['page_name'], page_id=s['page_id'], ads=s['ads'])
        if s['ads']:
            item.update(likes=s['likes'], creatives=s['creatives'], new_14d=s['new_14d'],
                        median_days_per_ad=s['median_days'], median_days_per_creative=s['cre_median_days'],
                        new_creatives_14d=s['cre_new_14d'], avg_ads_per_creative=round(s['avg_copies'], 1),
                        max_days=s['max_days'], max_ads_per_creative=s['max_dup'], top_destination=s['top_dest'],
                        top_objective=s['objectives'].most_common(1)[0][0])
            item.update({'video_%': round(s['video_pct']), 'ads_30d+': s['winners'], 'creatives_30d+': s['cre_30d']})
        summary.append(item)
    write_csv(proj / 'competitors_summary.csv', summary)
    groups = wp.group_creatives(rows)
    by_id = {r['ad_archive_id']: c for c in groups for r in c['ads']}
    packs = []
    for path in sorted((proj / 'winners').glob('*/meta.json')):
        previous = json.loads(path.read_text())
        aid = path.parent.name.rsplit('_', 1)[-1]
        if aid not in by_id:
            raise ValueError(f'Pack ad is no longer in snapshot: {aid}')
        c = dict(by_id[aid])
        # Keep the inspected representative and its media; update group evidence only.
        c['rep'] = next(r for r in c['ads'] if r['ad_archive_id'] == aid)
        meta = wp.meta_of(c, previous['rank'], previous.get('video_duration'))
        meta['aspect'] = previous.get('aspect') or meta['aspect']
        meta['reference_at'] = rq.stamp()
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
        packs.append((path.parent, meta))
    for path, meta in packs:
        meta['related_pack_ranks'] = [other['rank'] for _, other in packs
                                      if other['asset_id'] == meta['asset_id'] and other['rank'] != meta['rank']]
        (path / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    wp.write_index(proj / 'winners', packs, wp.pick(groups, 12, 3, False), len(rows), len(groups))
    return rows, packs


def refresh_google(proj):
    rows, order = gar.load_rows(proj)
    stats = gai.comp_stats(rows, order)
    videos = gwp.group_videos(rows, 30)
    by_vid = {(v['competitor'], v['vid']): v for v in gwp.group_videos(rows, None)}
    packs = []
    for path in sorted((proj / 'winners_google').glob('*/meta.json')):
        meta = json.loads(path.read_text())
        vid = meta['youtube'].rsplit('/', 1)[-1]
        v = by_vid[(meta['competitor'], vid)]
        meta.update(tier=v['tier'], days_shown=v['days'], creatives_using_video=v['copies'], active=v['active'],
                    first_shown=v['first'], last_shown=v['last'], platforms=v['platforms'], reference_at=rq.stamp())
        meta['transparency_links'] = [r['link'] for r in v['rows']]
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
        packs.append((path.parent, meta))
    gwp.write_index(proj / 'winners_google', packs, len(rows), len(videos))
    (proj / 'report_google.html').write_text(gr.render(proj.name, proj, rows, stats, gr.load_notes(proj)))
    gar.render(proj.name, proj, rows, order)
    # Reconcile active flags to the same reference clock; preserve the CSV URL representation.
    exported = read_csv(proj / 'google_all_ads.csv')
    active = {(r['advertiser_id'], r['creative_id']): r['active'] for r in rows}
    if set(active) != {(r['advertiser_id'], r['creative_id']) for r in exported}:
        raise ValueError('Google cache and CSV contain different creative IDs.')
    for r in exported:
        r['active'] = active[(r['advertiser_id'], r['creative_id'])]
    write_csv(proj / 'google_all_ads.csv', exported)
    summary = []
    for s in stats:
        item = dict(group=s['group'], competitor=s['label'], accounts=len(s['accounts']), creatives_total=s['total'],
                    active_now=s['active'], new_14d=s['new_14d'], new_30d=s['new_30d'],
                    **{'ads_30d+': s['winners']}, median_days=s['median_days'], max_days=s['max_days'], youtube_videos=s['videos'])
        item.update({f'active_on_{p}': sum(r['active'] and p in r['platforms'].split(',') for r in s['rows'])
                     for p in gai.PLATFORM_ORDER + [gai.OTHER]})
        summary.append(item)
    write_csv(proj / 'google_summary.csv', summary)
    return rows


def write_analysis(proj, meta_rows, packs, google_rows):
    """Generate evidence tables from the same snapshot as the HTML reports."""
    c = rq.coverage(meta_rows, 'meta')
    unique = len({m['asset_id'] for _, m in packs})
    lines = [
        '# Phân tích mẫu đáng khảo sát · Meta', '',
        f"Ngày tham chiếu {rq.stamp()} · {c['ads']} QC · {c['assets']} nhóm thiết kế · {c['brands']} fanpage có dữ liệu.", '',
        '[Báo cáo](../report.html) · [Manifest](../report_snapshot.json) · [Gói tư liệu](index.md) · [Ghi chép nội dung đã xem](observations.md)', '',
        '## Phạm vi và cách đọc', '',
        'Số liệu lấy từ cache và CSV hiện có; lần dựng này không crawl lại. Chỉ gồm quảng cáo trong danh sách fanpage được chọn. Không thấy dữ liệu không chứng minh một công ty không chạy quảng cáo.', '',
        f'{len(packs)} gói video đã lưu thuộc {unique} nhóm thiết kế. Giữ nguyên video và thứ tự gói để truy vết tư liệu đã xem; đây không phải xếp hạng hiệu quả. '
        'Số QC cùng nhóm đếm ad ID quan sát được có cùng thiết kế và cùng trạng thái media; không xác nhận mọi bản dùng cùng một video. Các gói trùng nhóm không được cộng dồn.', '',
        '## Các gói đã lưu', '',
        'DCO thiếu video URL chưa xác minh được quan hệ giữa clip đã lưu và ad đại diện. Các gói này giữ lại để truy vết, cần đối chiếu nguồn trước khi phân tích nội dung.', '',
        '| Gói | Fanpage | Tuổi QC lâu nhất trong nhóm | QC cùng nhóm | Gói liên quan |',
        '|---|---|---|---|---|']
    for path, m in packs:
        related = ', '.join(str(x) for x in m.get('related_pack_ranks', [])) or '–'
        lines.append(f"| [{m['rank']}]({path.name}/) | {m['page_name']} | {m['days_running']} ngày | {m['copies']} | {related} |")
    by = {}
    for r in meta_rows:
        by.setdefault(r['page_name'], []).append(r)
    lines += ['', '## Quy mô triển khai và độ đa dạng', '',
              '| Fanpage | QC | Nhóm thiết kế | Tỷ trọng QC | Tỷ trọng nhóm thiết kế |',
              '|---|---|---|---|---|']
    for name, rs in sorted(by.items(), key=lambda item: -len(item[1]))[:5]:
        assets = len({r['asset_id'] for r in rs})
        lines.append(f"| {name} | {len(rs)} | {assets} | {len(rs)/len(meta_rows):.1%} | {assets/c['assets']:.1%} |")
    lines += ['', '## Diễn giải và hành động', '',
              '- Quan sát: mức triển khai và số mẫu có thể khác nhau rất lớn. Diễn giải: nhiều QC không đồng nghĩa nhiều ý tưởng. Hành động: đọc hai chỉ số cạnh nhau và kiểm tra thủ công các nhóm hình ảnh lớn.',
              '- Quan sát: bộ tư liệu có video ưu đãi ngắn, kiến thức và người thật nói chuyện. Chưa có dữ liệu để kết luận nhóm nào rẻ hơn hoặc chuyển đổi tốt hơn. Hành động: so các phương án trong cùng mục tiêu và cohort.',
              '- DCO có thể dùng caption placeholder; không dùng caption đó để xác nhận trùng video. Các nhóm hiện dựa trên hình ảnh và loại media, vẫn có thể gồm nhiều biến thể.',
              '- Tuổi QC là thời gian từ ngày bắt đầu tới mốc quan sát lưu trong cache, không xác nhận phân phối liên tục. Một snapshot không xác nhận tái sử dụng hoặc tăng ngân sách.', '',
              '## Giả thuyết nên thử', '',
              '| Giả thuyết | Bản thử | Chỉ số quyết định |',
              '|---|---|---|',
              '| Demo giúp giảm lo ngại thủ tục | Thao tác thật so với motion chữ, cùng lợi ích | Chi phí eKYC và tỷ lệ nạp tiền |',
              '| Điều kiện rõ giúp tăng chất lượng tài khoản | Giải thích điều kiện so với thông điệp ngắn | Chi phí tài khoản có nạp tiền/giao dịch |',
              '| Tính năng tạo động lực ngoài săn quà | Một tình huống sử dụng so với ưu đãi | Chi phí tài khoản có giao dịch |', '',
              'Đây là đề xuất thử nghiệm, chưa phải khoảng trống toàn thị trường. Nội dung ưu đãi phải đối chiếu thể lệ còn hiệu lực. Xem [brief](../brief.md).']
    (proj / 'winners' / 'analysis.md').write_text('\n'.join(lines) + '\n')
    c = rq.coverage(google_rows, 'google')
    gps = [(path.parent, json.loads(path.read_text())) for path in sorted((proj / 'winners_google').glob('*/meta.json'))]
    lines = ['# Phân tích mẫu đáng khảo sát · Google / YouTube', '',
             f'Ngày tham chiếu {rq.stamp()} · {len(google_rows)} creative · {len({r["competitor"] for r in google_rows})} công ty có dữ liệu.', '',
             '[Báo cáo](../report_google.html) · [Manifest](../report_snapshot.json) · [Gói tư liệu](index.md) · [Ghi chép nội dung đã xem](observations.md)', '',
             '## Độ phủ', '',
             f"Có {c['videos']} bản ghi video; {c['unresolved']} chưa lấy được YouTube ID. Trong {c['active_videos']} bản ghi video có hiển thị gần đây, {c['active_unresolved']} thiếu ID. Không được dùng bộ đã xem để kết luận ‘chưa ai làm’.", '',
             'Trạng thái gần đây được suy ra từ lần hiển thị cuối trong ba ngày trước mốc tham chiếu. Đây không phải trạng thái chiến dịch do Google xác nhận. Ngày hiển thị lấy từ trường Google trả về; không đồng nghĩa thời gian liên tục từ ngày đầu tới ngày cuối.', '',
             '## Các gói đã lưu', '',
             '| Gói | Công ty | Ngày hiển thị cao nhất | Creative dùng video | Hiển thị gần đây |',
             '|---|---|---|---|---|']
    for path, m in gps:
        lines.append(f"| [{m['rank']}]({path.name}/) | {m['competitor']} | {m['days_shown']} | {m['creatives_using_video']} | {'Có' if m['active'] else 'Không'} |")
    lines += ['', '## Bài học có thể kiểm chứng', '',
              '- SSI có video hướng dẫn mở tài khoản trong bộ đã xem. Có thể học cách chia bước; chưa đủ căn cứ xác nhận video khớp truy vấn nào hoặc tạo chuyển đổi tốt.',
              '- DNSE minh hoạ lợi ích tính năng bằng giao diện. Có thể thử tình huống sử dụng cụ thể; mọi thông số và điều kiện phải kiểm tra lại trước khi dùng.',
              '- Vietcap IQ có người thật và minh hoạ công cụ. Đây là hướng sáng tạo để khảo sát, không phải bằng chứng rằng chỉ Vietcap dùng cách này.',
              '- Video có ưu đãi theo đợt và video evergreen cần đánh giá riêng. Cùng ngày hiển thị cuối không chứng minh nguyên nhân dừng hoặc hết ngân sách.', '',
              '## Giới hạn suy luận', '',
              '- Nhãn Search/YouTube/Play/Maps/Shopping là bằng chứng nền tảng. Loại chiến dịch trong HTML là suy luận; nhãn Play chưa xác nhận cài mới hay tái tương tác.',
              '- Bảng tháng trong báo cáo app đo khoảng ngày đầu–cuối giao với tháng, không xác nhận có phân phối ở mọi tháng giữa.',
              '- Danh sách có thể thiếu agency và tài khoản phụ. Chưa kiểm tra tương đương trên Meta thì không suy ra kênh chính từ việc chỉ có tên trong danh sách Google.',
              '- Không có ngân sách, CPA, từ khoá bid hoặc chất lượng tài khoản để xác nhận winner. Thứ tự gói giữ theo tư liệu đã khảo sát.', '',
              'Xem [brief thử nghiệm](../brief_google.md).']
    (proj / 'winners_google' / 'analysis.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--as-of', required=True, help='ISO timestamp with timezone; reference only, not a crawl timestamp')
    parser.add_argument('--update-analysis', action='store_true', help='Replace analysis.md with snapshot evidence tables')
    args = parser.parse_args()
    if args.update_analysis and args.project != 'chung-khoan':
        parser.error('--update-analysis currently supports chung-khoan only')
    rq.set_reference(args.as_of)
    proj = Path('projects') / args.project
    ci.load_project_signals(proj)
    meta, packs = refresh_meta(proj)
    google = refresh_google(proj)
    if args.update_analysis:
        write_analysis(proj, meta, packs, google)
    manifest = dict(reference_at=args.as_of, rebuilt_from='local cache and CSV visual IDs; no network calls',
                    meta=rq.coverage(meta, 'meta'), google=rq.coverage(google, 'google'))
    (proj / 'report_snapshot.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
