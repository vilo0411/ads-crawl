"""
Báo cáo riêng cho App campaign (cài app) trên Google Ads của đối thủ → projects/<project>/report_google_app.html

Chỉ đọc cache của google_ads_intel.py (projects/<project>/google/AR*.json), không gọi Google.
Creative App = video / ảnh có nhãn Google Play (xem google_report.campaign_type).

    python3 google_app_report.py --project chung-khoan
"""

import argparse
import datetime as dt
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

import competitor_intel as ci
import dsc_theme as dsc
import google_ads_intel as gai
import google_report as gr
import report_builder as rb

esc = ci.esc
APP = "App (cài app)"
MONTHS = 12


# ───────────────────────── Dữ liệu ─────────────────────────

def load_rows(proj):
    """Toàn bộ creative Google trong cache, gắn tên đối thủ + nhóm theo google_competitors.txt."""
    entries = ci.read_competitors(proj / "google_competitors.txt")
    order = list(dict.fromkeys((ci.short_name(e["label"]) or e["pid"], e["group"]) for e in entries))
    rows, seen = [], set()
    for e in entries:
        cache = proj / "google" / f"{e['pid']}.json"
        if not e["pid"].startswith("AR") or e["pid"] in seen or not cache.exists():
            continue
        seen.add(e["pid"])
        for r in json.loads(cache.read_text(encoding="utf-8")):
            r["competitor"], r["group"] = ci.short_name(e["label"]) or e["pid"], e["group"]
            rows.append(r)
    gai.enrich(rows, time.time())
    return rows, order


def month_starts(n=MONTHS):
    d = dt.date.today().replace(day=1)
    out = []
    for _ in range(n):
        out.append(d)
        d = (d - dt.timedelta(days=1)).replace(day=1)
    return list(reversed(out))


def live_in_month(rows, m):
    """Số creative có hiển thị trong tháng m (khoảng first_shown → last_shown giao với tháng)."""
    nxt = (m + dt.timedelta(days=32)).replace(day=1)
    a = time.mktime(m.timetuple())
    b = time.mktime(nxt.timetuple())
    return sum(1 for r in rows if r["first_ts"] < b and r["last_ts"] >= a)


def ago(ts):
    return time.strftime("%d/%m/%Y", time.localtime(ts)) if ts else "–"


# ───────────────────────── Nhận xét tự tính ─────────────────────────

def insights(app, all_rows, by_comp):
    act = [r for r in app if r["active"]]
    out = []
    running = sorted(((k, [r for r in rs if r["active"]]) for k, rs in by_comp.items()), key=lambda x: -len(x[1]))
    running = [(k, a) for k, a in running if a]
    if running:
        out.append(f"<b>{len(running)}</b> đối thủ đang chạy App campaign: "
                   + ", ".join(f"<b>{esc(k)}</b> {len(a)} creative" for k, a in running[:8]) + ".")
    else:
        out.append("Hiện <b>không đối thủ nào</b> đang chạy App campaign trên Google.")
    g_act = [r for r in all_rows if r["active"]]
    if g_act:
        out.append(f"App chiếm <b>{rb.pct(len(act), len(g_act)):.0f}%</b> số creative Google đang chạy của cả ngành "
                   f"({len(act)}/{len(g_act)}); phần còn lại là Search, Display và video thường.")
    heavy = []
    for k, rs in by_comp.items():
        ga = [r for r in all_rows if r["competitor"] == k and r["active"]]
        a = [r for r in rs if r["active"]]
        if len(a) >= 3 and rb.pct(len(a), len(ga)) >= 50:
            heavy.append(f"<b>{esc(k)}</b> {rb.pct(len(a), len(ga)):.0f}%")
    if heavy:
        out.append("Dồn Google vào App (≥ 50% creative Google đang chạy là App): " + ", ".join(heavy) + ".")
    stopped = sorted(((k, max(r["last_ts"] for r in rs)) for k, rs in by_comp.items() if not any(r["active"] for r in rs)
                      and len(rs) >= 5), key=lambda x: -x[1])
    if stopped:
        out.append("Từng chạy App nhưng đã dừng: " + ", ".join(f"<b>{esc(k)}</b> (lần cuối {ago(t)})" for k, t in stopped[:5]) + ".")
    fresh = Counter(r["competitor"] for r in app if time.time() - r["first_ts"] < 30 * 86400)
    if fresh:
        out.append("Tung creative App mới trong 30 ngày: " + ", ".join(f"<b>{esc(k)}</b> {v}" for k, v in fresh.most_common(5)) + ".")
    longest = sorted(app, key=lambda r: -r["days_shown"])[:3]
    if longest:
        out.append("Creative App hiển thị lâu nhất: " + "; ".join(
            f"<b>{esc(r['competitor'])}</b> {r['days_shown']} ngày" + (f" (\"{esc(r['video_title'][:50])}\")" if r["video_title"] else "")
            for r in longest) + ".")
    return out


def platform_note(app):
    base = [r for r in app if r["active"]] or app
    combos = Counter(r["platforms"] for r in base)
    with_search = rb.pct(sum("Search" in r["platforms"] for r in base), len(base))
    return (f"{with_search:.0f}% creative App mang cả nhãn Search: App campaign không cho chọn kênh, Google tự phân phối "
            f"cùng một bộ tài sản lên Search, YouTube, Play (và mạng hiển thị). Tổ hợp phổ biến nhất: "
            + ", ".join(f"<b>{esc(k.replace(',', ' + '))}</b> {rb.pct(v, len(base)):.0f}%" for k, v in combos.most_common(3)) + ".")


# ───────────────────────── HTML ─────────────────────────

def comp_table(by_comp, all_rows, order):
    def row(k):
        rs = by_comp[k]
        act = [r for r in rs if r["active"]]
        cr = gr.creatives_of(rs)
        ga = [r for r in all_rows if r["competitor"] == k and r["active"]]
        days = [r["days_shown"] for r in rs]
        return (f"<tr{'' if act else ' class=idle'}><td class='nm'>{esc(k)}</td>{gr.heat(len(act), mx)}<td class='n'>{len(rs)}</td>"
                f"<td class='n'>{sum(c['active'] for c in cr)}/{len(cr)}</td>"
                f"<td class='n'>{sum(1 for r in rs if time.time() - r['first_ts'] < 30 * 86400)}</td>"
                f"<td class='n'>{statistics.median(days):g}</td><td class='n'>{max(days)}</td>"
                f"<td class='n'>{f'{rb.pct(len(act), len(ga)):.0f}%' if ga else '–'}</td>"
                f"<td class='nw'>{ago(min(r['first_ts'] for r in rs))}</td>"
                f"<td class='nw'>{'đang chạy' if act else ago(max(r['last_ts'] for r in rs))}</td></tr>")
    keys = sorted(by_comp, key=lambda k: (-sum(r["active"] for r in by_comp[k]), -len(by_comp[k])))
    mx = max((sum(r["active"] for r in by_comp[k]) for k in keys), default=1) or 1
    never = [lab for lab, _ in order if lab not in by_comp]
    return (f"<div class='box tw'><table><tr><th>Đối thủ</th><th>Đang chạy</th><th>Tổng<small>mọi thời điểm</small></th>"
            f"<th>Mẫu<small>đang chạy / tổng</small></th><th>Mới 30 ngày</th><th>Trung vị ngày</th><th>Lâu nhất</th>"
            f"<th>% App<small>trong creative Google đang chạy</small></th><th>Chạy App từ</th><th>Hiển thị gần nhất</th></tr>"
            + "".join(row(k) for k in keys) + "</table>"
            + (f"<p class='muted'>Chưa thấy chạy App campaign trên Google: {', '.join(esc(x) for x in never)}.</p>" if never else "")
            + "<p class='muted'>Dòng in nghiêng: hiện không có creative App nào đang chạy. Mẫu = 1 video YouTube / 1 ảnh, "
              "một mẫu thường được Google cắt thành nhiều creative (nhiều kích thước).</p></div>")


def month_table(by_comp):
    ms = month_starts()
    keys = sorted(by_comp, key=lambda k: -len(by_comp[k]))
    vals = {k: [live_in_month(by_comp[k], m) for m in ms] for k in keys}
    mx = max((v for vs in vals.values() for v in vs), default=1) or 1
    head = "".join(f"<th>{m:%m/%y}</th>" for m in ms)
    body = "".join(f"<tr><td class='nm'>{esc(k)}</td>" + "".join(gr.heat(v, mx) if v else "<td class='h' style='--a:0'></td>" for v in vals[k]) + "</tr>"
                   for k in keys)
    return f"<div class='box tw'><table class='wkt'><tr><th>Đối thủ</th>{head}</tr>{body}</table></div>"


def week_table(by_comp):
    keys = sorted(by_comp, key=lambda k: -len(by_comp[k]))
    wk = {k: gai.weekly_new(by_comp[k], gr.WEEKS) for k in keys}
    keys = [k for k in keys if sum(wk[k])]
    if not keys:
        return f"<p class='muted'>Không có creative App mới trong {gr.WEEKS} tuần.</p>"
    mx = max(max(v) for v in wk.values()) or 1
    head = "".join(f"<th>{'tuần này' if w == 0 else f'-{w}'}</th>" for w in reversed(range(gr.WEEKS)))
    body = "".join(f"<tr><td class='nm'>{esc(k)}</td>" + "".join(gr.heat(v, mx) for v in wk[k]) + "</tr>" for k in keys)
    return f"<div class='box tw'><table class='wkt'><tr><th>Đối thủ</th>{head}</tr>{body}</table></div>"


def winner_links(proj, app):
    d = proj / "winners_google"
    ids = {r["youtube_id"] for r in app if r["youtube_id"]}
    packs = [p for p in sorted(d.iterdir()) if p.is_dir() and any(p.name.endswith("_" + i) for i in ids)] if d.exists() else []
    if not packs:
        return ""
    return ("<div class='box'><h3>Gói phân tích video App có tín hiệu đáng chú ý</h3><p class='muted'>Khung hình + lời thoại của các video App đã được tách: "
            + " · ".join(f"<a href='winners_google/{esc(p.name)}/storyboard.jpg' target='_blank'>{esc(p.name)}</a>" for p in packs)
            + " · <a href='winners_google/analysis.md' target='_blank'>analysis.md</a></p></div>")


CSS = gr.CSS + """
.gal .card[hidden]{display:none}
"""

JS = """
const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const FB=document.getElementById('f_b'),FA=document.getElementById('f_a'),N=document.getElementById('gcount');
const CARDS=[...document.querySelectorAll('#gal .card')];
function run(){let n=0;CARDS.forEach(c=>{const ok=(!FB.value||c.dataset.b===FB.value)&&(!FA.value||c.dataset.a===FA.value);c.hidden=!ok;n+=ok});
 N.textContent=n+' / '+CARDS.length+' mẫu'}
FB.onchange=FA.onchange=run;run();
const LB=document.getElementById('lb'),LBF=document.getElementById('lbf');
function closeLB(){LB.classList.remove('on');LBF.innerHTML=''}
document.addEventListener('click',ev=>{const im=ev.target.closest('img.zoom');if(!im)return;
 const yt=im.dataset.yt,src=im.dataset.full,embed=yt&&location.protocol.startsWith('http');
 LBF.innerHTML=(embed?`<iframe src="https://www.youtube.com/embed/${e(yt)}?autoplay=1&rel=0" referrerpolicy="strict-origin-when-cross-origin" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>`
  :yt?`<a href="https://youtu.be/${e(yt)}" target="_blank" rel="noopener" class="ytbig"><img src="https://i.ytimg.com/vi/${e(yt)}/hqdefault.jpg" alt=""><b>▶</b></a>`:`<img src="${e(src)}" alt="">`)
 +`<figcaption><span>${e(im.dataset.cap)}</span><a href="${e(im.dataset.lib)}" target="_blank" rel="noopener">Mở trên Transparency ↗</a>`
 +(yt?`<a href="https://youtu.be/${e(yt)}" target="_blank" rel="noopener">YouTube ↗</a>`:'')+`<button id="lbx">Đóng (Esc)</button></figcaption>`;
 LB.classList.add('on');document.getElementById('lbx').onclick=closeLB});
LB.onclick=ev=>{if(ev.target===LB)closeLB()};document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closeLB()});
"""


def render(project, proj, all_rows, order):
    gr.PROJ = proj
    app = [r for r in all_rows if gr.campaign_type(r) == APP]
    if not app:
        raise SystemExit("Không có creative App campaign nào trong cache.")
    by_comp = defaultdict(list)
    for r in app:
        by_comp[r["competitor"]].append(r)
    act = [r for r in app if r["active"]]
    creatives = gr.creatives_of(app)
    base = act or app
    vids = {r["youtube_id"]: r for r in app if r["youtube_id"]}.values()
    sig = Counter(x for r in vids for x in r["signals"])
    titled = sorted((c for c in creatives if c["title"]), key=lambda c: (-c["active"], -c["days"]))

    kpi = [(f"{sum(1 for rs in by_comp.values() if any(r['active'] for r in rs))}/{len(by_comp)}", "đối thủ đang chạy App (trên số từng chạy)"),
           (len(act), "creative App đang chạy"),
           (sum(c["active"] for c in creatives), "mẫu App đang chạy (video / ảnh khác nhau)"),
           (sum(c["new_14d"] for c in creatives), "mẫu App mới trong 14 ngày"),
           (f"{statistics.median([r['days_shown'] for r in base]):g} ngày", "trung vị ngày hiển thị" + (" (đang chạy)" if act else "")),
           (len(app), "creative App mọi thời điểm")]
    cards = "".join(gr.creative_card(c).replace("<div class='card", f"<div data-b='{esc(c['competitor'])}' data-a='{'Đang chạy' if c['active'] else 'Đã dừng'}' class='card", 1)
                    for c in creatives)
    brands = sorted(by_comp, key=lambda k: -len(by_comp[k]))

    page = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>App campaign Google · {esc(project)}</title>{dsc.FONT_LINK}<style>{CSS}</style></head><body>{dsc.BRAND_STRIP}<main>
<h1>App campaign trên Google Ads · {esc(project)}</h1>
<p class="sub">Google Ads Transparency Center (Việt Nam) · cập nhật {time.strftime('%d/%m/%Y %H:%M')} · {len(app)} creative App ({len(act)} đang chạy),
{len(creatives)} mẫu, {len(by_comp)} đối thủ từng chạy · <a href="report_google.html">Báo cáo Google Ads đầy đủ</a></p>

<div class="kpis">{''.join(f"<div class='kpi'><b>{v}</b>{esc(t)}</div>" for v, t in kpi)}</div>
<div class="box"><h3>Nhận định nhanh</h3><ul class="ins">{''.join(f'<li>{x}</li>' for x in insights(app, all_rows, by_comp))}</ul></div>

<h3>1. Ai đang chạy App campaign</h3>{comp_table(by_comp, all_rows, order)}

<h3>2. Dòng thời gian <small class="muted">· số creative App có hiển thị trong từng tháng</small></h3>
<p class="sub">Cho thấy đối thủ chạy App liên tục (always-on) hay theo đợt (mùa mở tài khoản, chiến dịch ưu đãi).</p>
{month_table(by_comp)}

<h3>3. Nhịp tung creative App mới <small class="muted">· {gr.WEEKS} tuần, theo ngày hiển thị đầu tiên</small></h3>
{week_table(by_comp)}

<div class="grid">
<div class="box"><h3>4. Nơi Google phân phối <small class="muted">· % creative App{' đang chạy' if act else ''}</small></h3>
{gr.tk(platform_note(app))}{rb.bar_rows(Counter(p for r in base for p in r['platforms'].split(',')), len(base))}</div>
<div class="box"><h3>5. Thông điệp trong tiêu đề video</h3>
{rb.bar_rows(sig, len(vids)) if sig else "<p class='muted'>Không có dữ liệu.</p>"}
<p class="muted">Dựa trên {len(vids)} video YouTube dùng trong App campaign, theo bộ tín hiệu của project. % tính trên số video.</p></div>
</div>
{f'''<div class="box tw"><h3>Tiêu đề video App</h3><table class="mini"><tr><th>Đối thủ</th><th>Tiêu đề</th><th>Ngày hiển thị</th><th>Creative</th><th>Trạng thái</th></tr>
{"".join(f"<tr><td class='nm'>{esc(c['competitor'])}</td><td><a href='https://youtu.be/{esc(c['rep']['youtube_id'])}' target='_blank' rel='noopener'>{esc(c['title'][:110])}</a></td><td class='n'>{c['days']}</td><td class='n'>{c['copies']}</td><td class='nw'>{'đang chạy' if c['active'] else 'dừng ' + ago(c['last_ts'])}</td></tr>" for c in titled[:30])}
</table></div>''' if titled else ''}
{winner_links(proj, app)}

<h3>6. Thư viện creative App</h3>
<p class="sub">Mỗi thẻ là 1 <b>mẫu</b> (1 video YouTube / 1 ảnh), xếp theo mức đáng học: đang chạy trước, rồi theo số ngày hiển thị và số creative dùng chung. Bấm ảnh để xem lớn / phát video.</p>
<div class="flt"><select id="f_b" aria-label="Đối thủ">{gr.options(brands, 'Mọi đối thủ')}</select>
<select id="f_a" aria-label="Trạng thái">{gr.options(['Đang chạy', 'Đã dừng'], 'Mọi trạng thái')}</select></div>
<p id="gcount" class="muted"></p><div id="gal" class="cards gal">{cards}</div>

<h2>Cách đọc & giới hạn</h2>
<div class="box"><ul class="ins">
<li><b>Creative App</b> = video / ảnh có nhãn <b>Google Play</b> trên Transparency Center. Chỉ App campaign mới hiện trên Play, nên đây là dấu hiệu chắc chắn nhất. QC chữ không được tính.</li>
<li>Có thể <b>sót</b>: ảnh của App campaign chỉ hiện trên mạng hiển thị (không mang nhãn Play) sẽ bị xếp vào Display (GDN) trong báo cáo chính.</li>
<li><b>Đang chạy</b> = có lần hiển thị cuối trong {gai.ACTIVE_DAYS} ngày gần nhất. <b>Ngày hiển thị</b> = số ngày Google thực sự phân phối, không phải khoảng từ ngày đầu tới ngày cuối.</li>
<li>Google <b>không công bố</b> ngân sách, lượt cài, CPI hay app cụ thể được quảng bá. Số creative không tỉ lệ với ngân sách: App campaign tự cắt một video thành nhiều creative (nhiều kích thước, nhiều vị trí).</li>
<li>Số creative phản ánh mức độ active/triển khai trong dữ liệu quan sát được, không phải thị phần hay hiệu quả cài đặt.</li>
<li>Dòng thời gian tính theo khoảng hiển thị đầu → cuối của từng creative, nên một creative chạy ngắt quãng vẫn được tính ở các tháng giữa.</li>
</ul></div>
{dsc.footer('App campaign Google · ' + esc(project), time.strftime('%d/%m/%Y'))}
</main>
<div id="lb" role="dialog" aria-modal="true" aria-label="Xem lớn"><figure id="lbf"></figure></div>
<script>{JS}</script></body></html>"""
    out = proj / "report_google_app.html"
    out.write_text(page, encoding="utf-8")
    return out, app, act


def main():
    ap = argparse.ArgumentParser(description="Báo cáo App campaign trên Google Ads của đối thủ (đọc từ cache)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default="projects")
    args = ap.parse_args()
    proj = Path(args.out) / args.project
    ci.load_project_signals(proj)
    rows, order = load_rows(proj)
    if not rows:
        raise SystemExit(f"Chưa có cache trong {proj / 'google'}. Chạy google_ads_intel.py analyze trước.")
    gr.download_images(proj, [r for r in rows if gr.campaign_type(r) == APP])
    out, app, act = render(args.project, proj, rows, order)
    print(f"✔ {len(app)} creative App ({len(act)} đang chạy) → {out}")


if __name__ == "__main__":
    main()
