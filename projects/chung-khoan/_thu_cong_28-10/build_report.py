import csv
import datetime as dt
import html
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TODAY = dt.date(2026, 10, 28)
TZ = dt.timezone(dt.timedelta(hours=7))
profiles = json.loads((ROOT / 'profiles.json').read_text())
esc = lambda x: html.escape(str(x or ''))
all_ads, summary = [], []
for p in profiles:
    fn = f"full-{p['tab']}.json" if p['examples'] else f"verified-{p['tab']}.json"
    d = json.loads((ROOT / 'raw' / fn).read_text())
    p['capture_url'] = d['url']
    p['ads'] = [a for a in d['ads'] if str(a['page_id']) == p['pid'] and a['is_active']]
    m = re.search(r'(~[\d,]+) results', d['text'])
    p['reported'] = m[1] if m else 'Không có mẫu phù hợp'
    for a in p['ads']:
        a['brand'] = p['brand']
        a['library_link'] = 'https://www.facebook.com/ads/library/?id=' + str(a['ad_archive_id'])
        start = dt.datetime.fromtimestamp(a['start_date'], TZ).date() if a.get('start_date') else None
        a['start_date_iso'] = str(start or '')
        a['days_since_start'] = (TODAY - start).days if start else None
        all_ads.append(a)
    p['formats'] = ', '.join(f'{k}: {v}' for k,v in Counter(a['format'] for a in p['ads']).items())
    summary.append(dict(brand=p['brand'],page_id=p['pid'],captured_active_ad_ids=len(p['ads']),library_approx_results=p['reported'],formats=p['formats'],new_ids_last_14_calendar_days=sum(0 <= a['days_since_start'] < 14 for a in p['ads']),ids_started_30plus_days_ago=sum(a['days_since_start'] >= 30 for a in p['ads']),angle=p['angle'],audience_inferred=p['audience'],funnel_observed=p['funnel'],limitations=p['risk'],library_url=d['url']))

def write_csv(name, rows):
    with (ROOT / name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})

write_csv('competitors_summary.csv',summary)
write_csv('all_ads.csv',all_ads)
(ROOT/'all_ads.json').write_text(json.dumps(all_ads,ensure_ascii=False,indent=2))
(ROOT/'competitors.txt').write_text('# Fanpage chính thức được kiểm tra ngày 28/10/2026; 0 kết quả không có nghĩa thương hiệu không chạy ads.\n'+'\n'.join(p['pid']+' # '+p['brand'] for p in profiles)+'\n')

intro='''<h1>Facebook Ads · 10 công ty chứng khoán</h1><p class="lead">Ngày kiểm tra: 28/10/2026 · Việt Nam · quảng cáo đang hoạt động · tất cả phương tiện.</p>
<div class="note"><strong>275 ad ID thu được từ 6/10 fanpage.</strong> Bốn fanpage còn lại hiển thị không có mẫu phù hợp với bộ lọc đã chọn. Đây là ảnh chụp tại một thời điểm, không phải bảng xếp hạng ngân sách hoặc hiệu quả quảng cáo.</div>
<h2>Những điều nổi bật</h2><ol>
<li><strong>MBS mở nhiều nhánh chuyển đổi:</strong> mở mới, quà cổ phiếu, nạp tiền, cashback, margin và khách ưu tiên MB. KIS tập trung vào iKIS, referral và quà trải nghiệm. Đây là hai thương hiệu có nhiều ad ID nhất trong tập thu được.</li>
<li><strong>SSI có cấu trúc quiz → mở tài khoản:</strong> dùng phong cách đầu tư để tạo tương tác, sau đó mời nhận quà và kích hoạt tài khoản. Một số copy gợi ý tiếp cận lại người đã quan tâm; không xác minh được cấu hình retargeting.</li>
<li><strong>VPS và VNDirect tạo lý do lựa chọn ngoài ưu đãi:</strong> VPS dùng kiến thức tích sản và webinar; VNDirect dùng lợi ích thao tác cụ thể của DTRADE.</li>
<li><strong>VPBankS có đợt mới 27/10:</strong> Zero Fee và eMax, tách lợi ích giảm phí giao dịch với tiền chưa sử dụng.</li></ol>
<h2>Phạm vi và cách đọc số liệu</h2><p>Đối tượng là 10 công ty do người dùng chọn; không kiểm định thứ hạng thị phần của danh sách. Tìm từ khóa để xác định trang, sau đó mở Ad Library theo Page ID. Loại quảng cáo trùng tên của ngành khác, tài chính tiêu dùng Mirae Asset và trang môi giới không thuộc tập fanpage chính. Lưu metadata nhúng trong trang, phản hồi tải thêm và văn bản giao diện tại thư mục raw.</p>
<p>“ID thu được” là số ad ID phân biệt đã đọc, không phải số chiến dịch, ad set hoặc concept. Meta hiển thị số kết quả xấp xỉ; MBS ~150 và KIS ~86 khác với 148 và 85 ID thu được. Không bảo đảm thu đủ tất cả biến thể. DCO có nhiều phiên bản; body có thể là placeholder, cần đối chiếu cards và giao diện. Không gộp creative chỉ bằng caption vì cùng copy có thể dùng nhiều hình/video.</p>
<p>Số ngày là chênh lệch ngày lịch từ ngày bắt đầu đến 28/10 theo UTC+7, không chứng minh quảng cáo chạy liên tục. Nhóm mới 14 ngày = bắt đầu từ 15–28/10. Không có dữ liệu chi tiêu, CPM, CTR, CPL, CPA, tiền nạp, ROAS hoặc targeting thực tế. Quảng cáo tồn tại lâu và có nhiều ID chỉ là tín hiệu để nghiên cứu thêm, không chứng minh “thắng”. Thông tin nền tảng có thể gồm Instagram/Threads/Audience Network; không gán toàn bộ phân phối cho Facebook.</p>
<p>Chưa xem toàn bộ video hoặc phân tích thiết kế từng hình; nhận định dựa trên nội dung chữ, định dạng, ngày bắt đầu, CTA và URL. Không có dữ liệu lịch sử toàn bộ quảng cáo đã dừng, không bao phủ mọi chi nhánh/kênh môi giới.</p>'''

rows=[]
for p,s in zip(profiles,summary):
    bar=f'<div class="bar" style="width:{len(p["ads"])/148*100:.1f}%"></div>'
    rows.append(f'<tr><td><a href="#{esc(p["brand"])}">{esc(p["brand"])}</a></td><td><strong>{len(p["ads"]) if p["ads"] else "Chưa thấy"}</strong>{bar}</td><td>{esc(p["reported"])}</td><td>{esc(p["angle"])}</td><td>{s["new_ids_last_14_calendar_days"] if p["ads"] else "—"}</td></tr>')
content=intro+'<h2>So sánh 10 công ty</h2><p>Thanh ngang thể hiện số ad ID thu được; không thể hiện ngân sách.</p><table><thead><tr><th>Công ty</th><th>ID thu được</th><th>Kết quả Meta</th><th>Hướng nội dung</th><th>ID mới 14 ngày</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'

for p in profiles:
    content+=f'<section id="{esc(p["brand"])}"><h2>{esc(p["brand"])}</h2><p class="tag">{esc(p["angle"])}</p><p><a href="{esc(p["capture_url"])}" target="_blank" rel="noopener">Mở Ad Library theo fanpage</a> · Page ID {p["pid"]} · {len(p["ads"])} ID thu được</p>'
    for title,key in [('Quan sát','finding'),('Tệp khách hàng — suy luận','audience'),('Phễu quan sát','funnel'),('Điểm đáng học — nhận định','lesson'),('Giới hạn khi diễn giải','risk')]:
        content+=f'<p><strong>{title}:</strong> {esc(p[key])}</p>'
    if p.get('source'):content+=f'<p><a href="{esc(p["source"])}">Nguồn website chính thức đối chiếu</a></p>'
    if p['ads']:content+=f'<p>Định dạng trong tập thu được: {esc(p["formats"])}.</p>'
    for aid in p['examples']:
        a=next((a for a in p['ads'] if str(a['ad_archive_id'])==aid),None)
        if not a:continue
        content+=f'<details><summary>Mẫu {aid} · {a["start_date_iso"]} · {esc(a["format"])} · {esc(a["cta"])}</summary><p><a href="{a["library_link"]}">Xem mẫu trên Meta</a></p><pre>{esc(a["body"])}</pre><p>URL đích trong metadata: {esc(a["link_url"] or "Không có URL website rõ ràng")}</p></details>'
    content+='</section>'

content+='''<h2>Hàm ý cho kế hoạch research và thử nghiệm</h2><p>Đây là giả thuyết đề xuất từ mẫu quan sát, chưa phải kết quả đã đo:</p><ul>
<li><strong>Thu hút khách mới:</strong> so sánh quà trực tiếp với quiz hoặc nội dung giáo dục. Đo tài khoản eKYC hợp lệ và tỷ lệ có tiền nạp, tránh chỉ tối ưu lượt để lại thông tin.</li>
<li><strong>Kích hoạt khách đã mở tài khoản:</strong> tách lời mời nạp tiền, giao dịch lần đầu và dùng thử sản phẩm. Đo chi phí cho tài khoản có giao dịch và số tiền nạp ròng.</li>
<li><strong>Trader hiện hữu:</strong> so sánh demo một tác vụ cụ thể như DTRADE với thông điệp tiết kiệm chi phí vốn như MBS. Đo chất lượng tài khoản, tần suất giao dịch và khả năng duy trì.</li>
<li><strong>Khách có tài sản:</strong> thử nội dung phân bổ tài sản/webinar theo VPS và checklist chuyển danh mục theo KIS. Đo người tham dự đủ điều kiện, giá trị chuyển về và tỷ lệ sử dụng dịch vụ.</li>
<li><strong>Theo dõi định kỳ:</strong> lưu snapshot từng tuần và so ad ID mới/dừng, hướng nội dung mới, CTA, điều kiện ưu đãi; bổ sung kênh sản phẩm và kênh vệ tinh để mở rộng độ phủ.</li></ul>
<h2>Kho metadata quảng cáo</h2><p><a href="all_ads.csv">Tải CSV quảng cáo</a> · <a href="competitors_summary.csv">Tải CSV so sánh 10 công ty</a> · <a href="all_ads.json">JSON</a>. CSV mã hóa UTF-8 BOM cho Excel. Link video trong JSON có thể hết hạn; chưa tải media.</p><input id="search" type="search" placeholder="Lọc theo công ty, thông điệp, CTA hoặc ad ID…" aria-label="Lọc quảng cáo"><p id="count"></p><table id="ads"><thead><tr><th>Công ty / ID</th><th>Bắt đầu</th><th>Định dạng / CTA</th><th>Nội dung</th></tr></thead><tbody>'''
for a in all_ads:
    cardtext='\n'.join(str(c.get('body') or '') for c in a.get('cards') or [])
    body=a['body']
    if '{{' in body and cardtext:body+='\n[Cards]\n'+cardtext
    content+=f'<tr><td>{esc(a["brand"])}<br><a href="{a["library_link"]}" target="_blank" rel="noopener">{a["ad_archive_id"]}</a></td><td>{a["start_date_iso"]}</td><td>{esc(a["format"])}<br>{esc(a["cta"])}</td><td><details><summary>{esc(body[:140])}</summary><pre>{esc(body)}</pre><p>Đích: {esc(a["link_url"])}</p></details></td></tr>'
content+='</tbody></table><footer>Được tổng hợp từ dữ liệu công khai ngày 28/10/2026. Phân biệt quan sát trực tiếp, thông tin website và suy luận trong từng mục.</footer>'
css='''body{font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f6f8fb;color:#18283b;max-width:1240px;margin:auto;padding:42px 28px}h1{font-size:38px;line-height:1.2}h2{margin-top:38px;font-size:24px}a{color:#075bb5}table{border-collapse:collapse;width:100%;background:white;font-size:14px;margin:20px 0}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #e0e7ef;padding:12px}th{background:#e8eef6}section{padding:8px 25px 25px;background:white;border:1px solid #e0e7ef;border-radius:12px;margin:25px 0}.note{padding:18px 24px;background:#e5f2ff;border-left:4px solid #1477c9}.tag{font-weight:600;color:#086c67}.lead,footer{color:#596c80}.bar{height:6px;background:#267bbc;margin-top:8px;min-width:0}details{padding:8px 0}summary{cursor:pointer}pre{font:14px/1.7 inherit;white-space:pre-wrap;overflow-wrap:anywhere}input{font:inherit;padding:12px;width:min(95%,650px);border:1px solid #9eacbd;border-radius:7px}footer{margin-top:35px}@media(max-width:700px){body{padding:20px 12px}h1{font-size:29px}table{display:block;overflow-x:auto}section{padding:4px 14px 18px}}'''
js='''const rows=[...document.querySelectorAll('#ads tbody tr')];const count=document.querySelector('#count');function filter(){const q=document.querySelector('#search').value.toLocaleLowerCase('vi');let n=0;for(const row of rows){const show=row.textContent.toLocaleLowerCase('vi').includes(q);row.hidden=!show;n+=show}count.textContent=n+' / '+rows.length+' ad ID'}document.querySelector('#search').addEventListener('input',filter);filter();'''
(ROOT/'report.html').write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research Facebook Ads Chứng khoán · 28/10/2026</title><style>'+css+'</style><body>'+content+'<script>'+js+'</script></body></html>')
assert len(all_ads)==len({a['ad_archive_id'] for a in all_ads})
assert len(profiles)==10
assert all(a['days_since_start'] >= 0 for a in all_ads)
print(json.dumps({'companies':len(profiles),'ad_ids':len(all_ads),'report':str(ROOT/'report.html'),'by_brand':{p['brand']:len(p['ads']) for p in profiles}},ensure_ascii=False,indent=2))
