"""
Dựng report.html từ dữ liệu đã enrich của competitor_intel.analyze.

Gồm các tab: Tổng quan · So sánh (nhóm chính) · Hồ sơ từng đối thủ · Ưu đãi & thông điệp ·
Thư viện creative · các nhóm phụ (vd. "Xu hướng") · Giới hạn dữ liệu.
Ảnh thumbnail được tải về projects/<project>/thumbs/ vì link ảnh của Facebook hết hạn sau vài ngày.
"""

import datetime as dt
import json
import re
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

import competitor_intel as ci
import dsc_theme as dsc
import fb_ads_scraper as fb
from competitor_intel import esc, pct

WEEKS = 12
OBJ_ORDER = list(ci.OBJECTIVE_STAGE)
OBJ_COLORS = {
    "Cài app": "#e8590c",
    "Lead form trên FB": "#c2255c",
    "Lead / chuyển đổi trên web": "#9c36b5",
    "Tin nhắn": "#1c7ed6",
    "Traffic → form / webinar ngoài": "#0ca678",
    "Traffic → landing": "#74b816",
    "Traffic → bài viết / PR": "#f59f00",
    "Like trang": "#4263eb",
    "Tương tác / video view": "#868e96",
}
STAGES = ["Nhận biết", "Cân nhắc", "Chuyển đổi"]
# Gán trong render(): khi competitor_intel chạy như script, "import competitor_intel" ở đây là một bản module
# khác, nên COPY_SIGNALS của nó vẫn là bộ mặc định chứ không phải signals.json của project
SIGNAL_KEYS = []


# ───────────────────────── Dữ liệu ─────────────────────────

# dHash 16×16 = 256 bit. Đo trên dữ liệu chứng khoán, khoảng cách giữa 2 thumbnail cùng fanpage chia 3 vùng rõ:
#   0–9   cùng 1 ảnh (chỉ khác nút, góc, nén)         → cùng BIẾN THỂ
#   20–34 cùng thiết kế, đổi chữ / con số ưu đãi     → cùng MẪU, khác biến thể
#   ≥ 45  thiết kế khác
VARIANT_MATCH_BITS = 12
ASSET_MATCH_BITS = 40


def _dhash(path, n=16):
    im = Image.open(path).convert("L").resize((n + 1, n))
    px, bits = im.load(), 0
    for y in range(n):
        for x in range(n):
            bits = bits << 1 | (px[x, y] > px[x + 1, y])
    return bits


def video_frame(url, duration, dest, at=0.3):
    t = (duration or 10) * at
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.1f}", "-i", url, "-frames:v", "1",
                        "-vf", "scale=600:-2", "-q:v", "4", str(dest)], capture_output=True, timeout=60)
    except Exception:
        pass
    if dest.exists() and dest.stat().st_size == 0:
        dest.unlink()


def assign_assets(rows, proj):
    """Gán r["asset_id"] (MẪU = cùng thiết kế) và r["variant_id"] (BIẾN THỂ = cùng 1 ảnh) bằng so khớp thumbnail
    trong từng fanpage, bỏ qua caption, nút CTA, đích. Meta chỉ gom (collation) những QC giống hệt nhau, nên 1 thiết
    kế thường bị tách thành nhiều nhóm. Thumbnail được tải về projects/<project>/thumbs/ (link ảnh FB hết hạn)."""
    tdir = Path(proj) / "thumbs"
    tdir.mkdir(exist_ok=True)
    reps = {}
    for r in rows:
        if r["collation_id"] not in reps or (r.get("thumbnail") and not reps[r["collation_id"]].get("thumbnail")):
            reps[r["collation_id"]] = r

    def get(item):
        cid, r = item
        dest = tdir / f"{cid}.jpg"
        # Video: ảnh preview của Meta là khung đầu (hay trống / chỉ có nền) → lấy khung ở 30% làm thumbnail,
        # thêm khung ở 70% để so khớp: 2 video chỉ cùng mẫu khi cả 2 khung đều giống
        dest2, prev = tdir / f"{cid}_b.jpg", tdir / f"{cid}_p.jpg"
        if r.get("video_urls"):
            if not prev.exists() and r.get("thumbnail"):  # ảnh preview gốc của Meta (khung đầu)
                try:
                    fb.download(r["thumbnail"], prev)
                except Exception:
                    pass
            if not (dest.exists() and dest.stat().st_size > 0):
                video_frame(r["video_urls"][0], r.get("video_duration"), dest, 0.3)
            if not dest2.exists():
                video_frame(r["video_urls"][0], r.get("video_duration"), dest2, 0.7)
        if not (dest.exists() and dest.stat().st_size > 0) and r.get("thumbnail"):
            try:
                fb.download(r["thumbnail"], dest)
            except Exception:
                pass
        if not (dest.exists() and dest.stat().st_size > 0):
            return cid, None
        try:
            vid = bool(r.get("video_urls"))
            h2 = _dhash(dest2) if vid and dest2.exists() else None
            hp = _dhash(prev) if vid and prev.exists() else None
            return cid, (_dhash(dest), h2, hp)
        except Exception:
            return cid, None

    with ThreadPoolExecutor(8) as ex:
        hashes = dict(ex.map(get, reps.items()))
    by_page = defaultdict(list)
    for cid, r in reps.items():
        if hashes.get(cid) is not None:
            by_page[r["page_id"]].append(cid)

    bits = lambda a, b: bin(a ^ b).count("1")

    def dist(x, y):
        """x, y = (khung 30%, khung 70%, preview gốc); ảnh tĩnh chỉ có phần tử đầu."""
        if x[1] is not None and y[1] is not None:  # 2 video: cả 2 khung phải giống (khung đầu hay trống nên bỏ qua)
            return max(bits(x[0], y[0]), bits(x[1], y[1]))
        if x[1] is not None or y[1] is not None:  # video với ảnh tĩnh (bản chuyển động / bản tĩnh của cùng thiết kế)
            v, im = (x, y) if x[1] is not None else (y, x)
            return min(bits(v[0], im[0]), bits(v[2], im[0]) if v[2] is not None else 999)
        return bits(x[0], y[0])

    def cluster(max_bits):
        parent = {cid: cid for cid in reps}

        def root(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for cids in by_page.values():
            for i, a in enumerate(cids):
                for b in cids[i + 1:]:
                    if dist(hashes[a], hashes[b]) <= max_bits:
                        parent[root(a)] = root(b)
        return {cid: root(cid) for cid in reps}

    asset, variant = cluster(ASSET_MATCH_BITS), cluster(VARIANT_MATCH_BITS)
    for r in rows:
        r["asset_id"] = asset[r["collation_id"]]
        r["variant_id"] = variant[r["collation_id"]]
        r["thumb_local"] = f"thumbs/{r['collation_id']}.jpg" if hashes.get(r["collation_id"]) is not None else ""
    print(f"  Gộp mẫu theo hình: {len(reps)} nhóm Meta → {len(set(variant.values()))} ảnh khác nhau → "
          f"{len(set(asset.values()))} mẫu thiết kế (thumbnail {sum(h is not None for h in hashes.values())}/{len(reps)})")


def creatives_of(rows):
    """Gộp QC theo mẫu (asset_id = cùng hình/video), giữ bản chạy lâu nhất làm đại diện."""
    by = defaultdict(list)
    for r in rows:
        by[r.get("asset_id") or r["collation_id"]].append(r)
    out = []
    for cid, ads in by.items():
        ads.sort(key=lambda r: (-(r["days_running"] or 0), not r.get("thumb_local")))
        rep = ads[0]
        copies = len(ads)
        captions = {re.sub(r"\W+", " ", ci.norm(a["body"] or a["title"] or "")).strip()[:150] for a in ads}
        vthumbs = {}
        for a in ads:  # ads đã sắp theo ngày chạy giảm dần → biến thể chạy lâu nhất đứng đầu
            if a.get("thumb_local"):
                vthumbs.setdefault(a.get("variant_id") or a["collation_id"], a["thumb_local"])
        out.append({"cid": cid, "rep": rep, "ads": ads, "copies": copies, "days": rep["days_running"] or 0,
                    "captions": len(captions), "variants": max(1, len(vthumbs)), "vthumbs": list(vthumbs.values()),
                    "thumb": next((a["thumb_local"] for a in ads if a.get("thumb_local")), ""),
                    "score": ci.winner_score({**rep, "collation_count": copies})})
    return sorted(out, key=lambda c: -c["score"])


def dest_label(r):
    if r["landing_type"]:
        return r["landing_type"]
    if r["dest"] in ("Messenger", "Zalo", "WhatsApp", "Gọi điện"):
        return r["dest"]
    return "Không có link" if not r["link_url"] else "(chưa mở)"


def age_bucket(days):
    return "< 7 ngày" if days < 7 else "7–29 ngày" if days < 30 else "≥ 30 ngày"


def week_of(r, today):
    """Cửa sổ 7 ngày tính lùi từ hôm nay: 0 = hôm nay và 6 ngày trước, 1 = 7–13 ngày trước…"""
    if not r["start_ts"]:
        return None
    w = (today - dt.date.fromtimestamp(r["start_ts"])).days // 7
    return w if 0 <= w < WEEKS else None


def week_span(i, today):
    end = today - dt.timedelta(days=7 * i)
    return end - dt.timedelta(days=6), end


def week_label(i, today):
    a, b = week_span(i, today)
    return f"{a:%d/%m}–{b:%d/%m}"


def week_head(today):
    return "".join(f"<th title='{week_label(i, today)}'>{'7 ngày qua' if i == 0 else f'{week_span(i, today)[0]:%d/%m}'}</th>"
                   for i in reversed(range(WEEKS)))


ASSET_FIRST = {}  # asset_id → ngày bắt đầu sớm nhất của mẫu (gán trong render)


def week_counts(rows, today):
    """{tuần: (số QC, số mẫu, số mẫu hoàn toàn mới)} theo ngày bắt đầu của QC.
    Mẫu hoàn toàn mới = QC đầu tiên của hình đó bắt đầu trong tuần này (không phải hình cũ chạy thêm QC)."""
    ads, cre = Counter(), defaultdict(set)
    for r in rows:
        w = week_of(r, today)
        if w is not None:
            ads[w] += 1
            cre[w].add(r.get("asset_id") or r["collation_id"])
    out = {}
    for w in ads:
        fresh = sum(1 for a in cre[w] if a in ASSET_FIRST and week_of({"start_ts": ASSET_FIRST[a]}, today) == w)
        out[w] = (ads[w], len(cre[w]), fresh)
    return out


def week_cells(cnt, today, field, value, mx):
    """Ô "QC / mẫu", tô màu theo số mẫu (mx = max của cả bảng, để các hàng so được với nhau);
    bấm vào thì mở thư viện creative lọc đúng khoảng ngày."""
    mx = mx or 1
    out = ""
    for i in reversed(range(WEEKS)):
        a, m, fresh = cnt.get(i, (0, 0, 0))
        if not a:
            out += '<td class="h" style="--a:0"></td>'
            continue
        lo, hi = week_span(i, today)
        t0 = dt.datetime.combine(lo, dt.time()).timestamp()
        t1 = dt.datetime.combine(hi + dt.timedelta(days=1), dt.time()).timestamp()
        out += (f'<td class="h wk" style="--a:{m / mx:.2f}" data-f="{field}" data-v="{esc(value)}" data-from="{t0:.0f}" '
                f'data-to="{t1:.0f}" data-l="{week_label(i, today)}" title="{week_label(i, today)}: {a} QC mới bắt đầu, dùng {m} mẫu '
                f'({fresh} mẫu hoàn toàn mới, {m - fresh} mẫu cũ chạy thêm QC) · bấm để xem">'
                f'{a}<small>/{m}</small></td>')
    return out


def offer_summary(rows):
    keys = {"money": "Tiền / quà", "stocks": "Cổ phiếu tặng", "fee": "Phí", "margin": "Margin", "deadline": "Hạn"}
    out = {}
    for k, lab in keys.items():
        c = Counter(v for r in rows for v in r["offers"][k])
        out[lab] = c
    return out


# ───────────────────────── Thành phần HTML ─────────────────────────

def bar_rows(counter, total, colors=None):
    rows = []
    for k, c in counter.most_common():
        p = pct(c, total)
        col = f";background:{colors[k]}" if colors and k in colors else ""
        rows.append(f'<div class="bar"><span class="bl">{esc(k)}</span>'
                    f'<span class="bt"><i style="width:{p:.1f}%{col}"></i></span>'
                    f'<span class="bv">{c} · {p:.0f}%</span></div>')
    return "".join(rows) or '<p class="muted">Không có dữ liệu</p>'


def vn(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def obj_list(counter, total, top=3):
    """Loại chiến dịch dạng danh sách có nhãn: ■ Cài app ███ 55%. Phần còn lại gộp thành "khác"."""
    items = counter.most_common()
    rows = "".join(
        f"<div class='ol'><span class='on'><b style='background:{OBJ_COLORS.get(k, '#adb5bd')}'></b>{esc(k)}</span>"
        f"<span class='ob2'><i style='width:{pct(c, total):.1f}%;background:{OBJ_COLORS.get(k, '#adb5bd')}'></i></span>"
        f"<span class='ov'>{'<1' if pct(c, total) < 1 else f'{pct(c, total):.0f}'}%</span></div>" for k, c in items[:top])
    rest = sum(c for _, c in items[top:])
    if rest:
        rows += f"<div class='muted ol-more'>+ {len(items) - top} loại khác {pct(rest, total):.0f}%</div>"
    return f"<div class='olist'>{rows}</div>"


def heat_table(stats, keys, value, head_label="Đối thủ", fmt=lambda v: f"{v:.0f}%"):
    head = "".join(f"<th>{esc(k)}</th>" for k in keys)
    body = ""
    for s in stats:
        vals = [value(s, k) for k in keys]
        body += f"<tr><td class='nm'>{esc(s['short'])}</td>" + "".join(
            f'<td class="h" style="--a:{min(v, 100) / 100:.2f}">{fmt(v) if v else ""}</td>' for v in vals) + "</tr>"
    return f"<div class='tw'><table><tr><th>{head_label}</th>{head}</tr>{body}</table></div>"


def week_table(stats, today):
    counts = [(s, week_counts(s["rows"], today)) for s in stats]
    mx = max((v[1] for _, c in counts for v in c.values()), default=1)
    body = "".join(f"<tr><td class='nm'>{esc(s['short'])}</td>{week_cells(c, today, 'b', s['short'], mx)}</tr>" for s, c in counts)
    return f"<div class='tw'><table class='wkt'><tr><th>Đối thủ</th>{week_head(today)}</tr>{body}</table></div>"


WEB_TYPES = ("Landing có form", "Trang thông tin / sản phẩm", "Bài viết / PR")


def dest_detail(r):
    """Trang đích kèm tên miền với trang web (vd. "Landing có form · iboard.ssi.com.vn")."""
    lab = dest_label(r)
    host = (r.get("landing") or {}).get("final_host", "")
    return f"{lab} · {host}" if lab in WEB_TYPES and host else lab


def chips(counter, total, top=3):
    return "".join(f"<span>{esc(k)} <b>{pct(v, total):.0f}%</b></span>" for k, v in counter.most_common(top))


def flow_rows(rows):
    """Luồng chạy dạng hàng: mỗi loại chiến dịch 1 hàng = tỉ lệ + chủ đề hay dùng + trang đích."""
    n = len(rows)
    if not n:
        return ""
    by = defaultdict(list)
    for r in rows:
        by[r["objective"]].append(r)
    out = ""
    for obj, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        p = pct(len(rs), n)
        col = OBJ_COLORS.get(obj, "#adb5bd")
        themes = Counter(r["theme"] for r in rs)
        dests = Counter(dest_detail(r) for r in rs)
        out += (f"<div class='fr'><div class='fh'><span class='fo'><b style='background:{col}'></b>{esc(obj)}</span>"
                f"<span class='fb'><i style='width:{p:.1f}%;background:{col}'></i></span>"
                f"<span class='fv'>{'<1' if p < 1 else f'{p:.0f}'}% · {len(rs)} QC</span></div>"
                f"<div class='fd'><span class='fl'>Chủ đề</span>{chips(themes, len(rs))}</div>"
                f"<div class='fd'><span class='fl'>→ Đích</span>{chips(dests, len(rs))}</div></div>")
    return f"<div class='flow'>{out}</div>"


def creative_card(c, show_brand=True):
    r = c["rep"]
    img = f"<img loading='lazy' src='{esc(c['thumb'] or r.get('thumbnail') or '')}' alt=''>" if (c["thumb"] or r.get("thumbnail")) else "<div class='noimg'></div>"
    tags = [f"{c['days']} ngày", r["format"]]
    if r.get("video_duration"):
        tags.append(f"{r['video_duration']:.0f}s · {r.get('aspect') or ''}")
    if c["variants"] > 1:
        tags.append(f"{c['variants']} biến thể")
    if c["copies"] > 1:
        tags.append(f"{c['copies']} QC")
    if c["captions"] > 1:
        tags.append(f"{c['captions']} caption")
    body = (r["body"] or r["title"] or "")
    strip = ("<div class='vs'>" + "".join(f"<img loading='lazy' src='{esc(t)}' alt=''>" for t in c["vthumbs"][:5])
             + (f"<span>+{len(c['vthumbs']) - 5}</span>" if len(c["vthumbs"]) > 5 else "") + "</div>") if c["variants"] > 1 else ""
    return (f"<a class='card' href='{esc(r['library_link'])}' target='_blank' rel='noopener'>{img}{strip}<div class='cb'>"
            + (f"<div class='cp'>{esc(c.get('short') or r['page_name'])}</div>" if show_brand else "")
            + f"<div class='tags'><span class='ob' style='--c:{OBJ_COLORS.get(r['objective'], '#adb5bd')}'>{esc(r['objective'])}</span>"
            + "".join(f"<span>{esc(t)}</span>" for t in tags) + "</div>"
            + (f"<div class='of'>{esc(r['offers_text'])}</div>" if r["offers_text"] else "")
            + f"<p>{esc(body[:200])}{'…' if len(body) > 200 else ''}</p></div></a>")


# ───────────────────────── Nhận định tự động ─────────────────────────

def insights(group, stats, rows, others):
    out = []
    live = [s for s in stats if s["ads"]]
    idle = [s["short"] for s in stats if not s["ads"]]
    n = len(rows)
    if not n:
        return ["Không có quảng cáo nào đang chạy trong nhóm này."]
    out.append(f"<b>{len(live)}/{len(stats)}</b> đối thủ trong nhóm <b>{esc(group)}</b> đang chạy QC"
               + (f"; <b>{esc(', '.join(idle))}</b> không có QC nào lúc cào." if idle else "."))
    top3 = sorted(live, key=lambda s: -s["ads"])[:3]
    out.append("Chạy nhiều nhất: " + ", ".join(f"<b>{esc(s['short'])}</b> {s['ads']} QC ({pct(s['ads'], n):.0f}%)" for s in top3)
               + f". Ba đối thủ này chiếm {pct(sum(s['ads'] for s in top3), n):.0f}% số QC của nhóm.")
    obj = Counter(r["objective"] for r in rows)
    out.append("Loại chiến dịch (suy luận): " + ", ".join(f"<b>{esc(k)}</b> {pct(v, n):.0f}%" for k, v in obj.most_common(3)) + ".")
    dom = [f"{esc(s['short'])} {pct(c, s['ads']):.0f}% {esc(k)}" for s in live
           for k, c in [s["objectives"].most_common(1)[0]] if s["ads"] >= 3 and pct(c, s["ads"]) >= 60]
    if dom and pct(obj.most_common(1)[0][1], n) < 90:  # cả nhóm chung 1 mục tiêu thì dòng này thừa
        more = f" và {len(dom) - 5} đối thủ khác" if len(dom) > 5 else ""
        out.append("Đối thủ dồn vào 1 mục tiêu: " + "; ".join(dom[:5]) + more + ".")
    mixed = [s["short"] for s in live if s["ads"] >= 5 and len([1 for st in STAGES if s["stages"].get(st)]) == 3]
    if mixed:
        out.append(f"Có QC ở đủ 3 tầng phễu theo CTA/đích đến (nhận biết + cân nhắc + chuyển đổi): "
                   f"<b>{esc(', '.join(mixed))}</b>. Dữ liệu không cho biết đối tượng nhắm chọn nên không thể xác nhận retargeting.")
    fast = max(live, key=lambda s: s["cre_new_14d"])
    if fast["cre_new_14d"]:
        out.append(f"<b>{esc(fast['short'])}</b> ra nhiều ý tưởng mới nhất: {fast['cre_new_14d']} mẫu mới trong 14 ngày "
                   f"(chạy thành {fast['new_14d']} QC).")
    longest = max(rows, key=lambda r: r["days_running"] or 0)
    out.append(f"QC sống lâu nhất: <b>{esc(longest.get('short') or longest['page_name'])}</b> {longest['days_running']} ngày "
               f"({esc(longest['theme'])}, {esc(longest['format'])}).")
    off = offer_summary(rows)
    if off["Cổ phiếu tặng"]:
        out.append("Cổ phiếu được dùng làm quà nhiều nhất: " + ", ".join(f"<b>{k}</b> ({v} QC)" for k, v in off["Cổ phiếu tặng"].most_common(5)) + ".")
    zero = sorted({r.get("short") or r["page_name"] for r in rows if "0%" in r["offers"]["fee"]})
    if zero:
        out.append(f"Có QC nói về <b>0 phí giao dịch</b>: {esc(', '.join(zero))}.")
    fmt = Counter(r["format"] for r in rows)
    out.append("Định dạng: " + ", ".join(f"<b>{esc(k)}</b> {pct(v, n):.0f}%" for k, v in fmt.most_common(3)) + ".")
    web = [r for r in rows if r.get("landing") and r["landing"]["type"] not in ("App Store", "Google Play", "Trang Facebook")]
    if web:
        out.append(f"Trong {len(web)} QC dẫn về web, <b>{pct(sum(r['landing']['meta_pixel'] for r in web), len(web)):.0f}%</b> trang đích có Meta Pixel "
                   "(tức là có đo chuyển đổi để tối ưu).")
    for g, s_other, r_other in others:
        if r_other:
            big = max(s_other, key=lambda s: s["ads"])
            out.append(f"Nhóm <b>{esc(g)}</b>: {len(r_other)} QC ({len(r_other) / n:.1f} lần nhóm {esc(group)}), "
                       f"riêng <b>{esc(big['short'])}</b> có {big['ads']} QC. Mục tiêu chính: {esc(Counter(r['objective'] for r in r_other).most_common(1)[0][0])}.")
    return out


def diff_vs(rows_a, rows_b, label_a, label_b):
    """Điểm khác nhau rõ (≥ 10 điểm %) giữa 2 nhóm về objective, định dạng, chủ đề."""
    out = []
    for key, name in (("objective", "loại chiến dịch"), ("format", "định dạng"), ("theme", "chủ đề")):
        ca, cb = Counter(r[key] for r in rows_a), Counter(r[key] for r in rows_b)
        for k in set(ca) | set(cb):
            pa, pb = pct(ca[k], len(rows_a)), pct(cb[k], len(rows_b))
            if abs(pa - pb) >= 10:
                out.append((abs(pa - pb), f"{name.capitalize()} <b>{esc(k)}</b>: {label_a} {pa:.0f}% so với {label_b} {pb:.0f}%"))
    return [t for _, t in sorted(out, reverse=True)[:6]]



# ───────────────────────── Nhận xét ngắn cho từng bảng ─────────────────────────

OBJ_MEANING = {
    "Cài app": "chốt khách ngay trên app (đua lượt cài và eKYC)",
    "Lead form trên FB": "lấy thông tin khách bằng form ngay trên Facebook",
    "Lead / chuyển đổi trên web": "đưa khách về landing mở tài khoản có Meta Pixel để tối ưu chuyển đổi",
    "Tin nhắn": "kéo khách vào inbox để tư vấn",
    "Traffic → form / webinar ngoài": "dẫn khách đăng ký sự kiện / form bên ngoài",
    "Traffic → landing": "dẫn khách về trang thông tin, chưa thấy dấu hiệu tối ưu chuyển đổi",
    "Traffic → bài viết / PR": "dẫn về bài báo / PR để xây uy tín",
    "Like trang": "tăng người theo dõi fanpage",
    "Tương tác / video view": "xây nhận biết bằng nội dung, chưa kêu gọi hành động",
}
APP_DEST = ("App Store", "Google Play", "Mở app (deep link)")


def tk(*parts):
    txt = " ".join(x for x in parts if x)
    return f"<p class='tk'><b>Nhận xét:</b> {txt}</p>" if txt else ""


def names(xs, n=4):
    xs = list(xs)
    return ", ".join(esc(x) for x in xs[:n]) + (f" và {len(xs) - n} đối thủ khác" if len(xs) > n else "")


def money_val(x):
    num, _, unit = x.partition(" ")
    if x.endswith("K"):
        return float(x[:-1]) * 1e3
    return float(num) * (1e6 if unit.startswith("triệu") else 1)


def tk_objectives(rows):
    if not rows:
        return ""
    c, n = Counter(r["objective"] for r in rows), len(rows)
    (o1, n1), *rest = c.most_common()
    out = f"{pct(n1, n):.0f}% QC là <b>{esc(o1)}</b>, tức là nhóm này chủ yếu {OBJ_MEANING.get(o1, esc(o1))}."
    if rest and pct(rest[0][1], n) >= 15:
        out += f" Hướng thứ hai là <b>{esc(rest[0][0])}</b> ({pct(rest[0][1], n):.0f}%): {OBJ_MEANING.get(rest[0][0], '')}."
    return tk(out)


def tk_funnel(rows):
    if not rows:
        return ""
    st, n = Counter(r["stage"] for r in rows), len(rows)
    conv, aware = pct(st.get("Chuyển đổi", 0), n), pct(st.get("Nhận biết", 0), n)
    if conv >= 70:
        return tk(f"{conv:.0f}% QC được xếp tầng <b>Chuyển đổi</b> theo CTA/đích đến, tầng Nhận biết là {aware:.0f}%. "
                  "Tỷ lệ này phản ánh số QC đang quan sát được, không phản ánh ngân sách hay vai trò nuôi dưỡng của nội dung.")
    if aware >= 40:
        return tk(f"{aware:.0f}% QC được xếp tầng <b>Nhận biết</b> theo CTA/đích đến; đây là phân bố loại hành động, không phải phân bổ ngân sách.")
    return tk(f"Số QC phân bố tương đối đều giữa các tầng theo CTA/đích đến (Chuyển đổi {conv:.0f}%, Nhận biết {aware:.0f}%).")


def tk_landing(rows):
    if not rows:
        return ""
    n = len(rows)
    app = sum(dest_label(r) in APP_DEST for r in rows)
    web = [r for r in rows if r.get("landing") and dest_label(r) not in APP_DEST + ("Trang Facebook", "Messenger")]
    out = f"{pct(app, n):.0f}% QC đưa thẳng về kho ứng dụng."
    if web:
        out += (f" Trong {len(web)} QC dẫn về web, {pct(sum(r['landing']['meta_pixel'] for r in web), len(web)):.0f}% trang có Meta Pixel, "
                "nghĩa là đối thủ có đo và tối ưu theo hành động trên web, không chỉ mua click.")
    return tk(out)


def tk_format(rows):
    if not rows:
        return ""
    c, n = Counter(r["format"] for r in rows), len(rows)
    (f1, n1), = c.most_common(1)
    out = f"Định dạng chủ lực là <b>{esc(f1)}</b> ({pct(n1, n):.0f}%)."
    dco, vid = pct(c.get("Dynamic (DCO)", 0), n), pct(c.get("Video", 0), n)
    if dco >= 15 and f1 != "Dynamic (DCO)":
        out += f" {dco:.0f}% là DCO: đối thủ đưa nhiều tiêu đề / ảnh để Meta tự ghép và chọn bản tốt nhất."
    if vid < 30:
        out += f" Video chỉ chiếm {vid:.0f}%, nên video ngắn vẫn là kênh còn ít cạnh tranh."
    return tk(out)


def tk_flow(rows):
    if not rows:
        return ""
    c = Counter((r["objective"], r["theme"], dest_detail(r)) for r in rows)
    (o, t, d), k = c.most_common(1)[0]
    return tk(f"Công thức hay gặp nhất: chủ đề <b>{esc(t)}</b> → <b>{esc(o)}</b> → <b>{esc(d)}</b> "
              f"({k} QC, {pct(k, len(rows)):.0f}%). Muốn cạnh tranh trực diện thì đây là luồng cần so ưu đãi và trải nghiệm.")


def tk_groups(by_group):
    items = [(g, len({r["asset_id"] for r in rr}), len(rr), rr) for g, (_, rr) in by_group.items() if rr]
    if len(items) < 2:
        return ""
    (g1, m1, q1, r1), (g2, m2, q2, r2) = items[0], items[1]
    a1, a2 = q1 / m1, q2 / m2
    out = f"Nhóm {esc(g1)} trung bình {vn(a1)} QC mỗi mẫu, nhóm {esc(g2)} {vn(a2)} QC mỗi mẫu."
    if a2 > a1 * 1.5:
        out += f" {esc(g2)} tập trung nhiều QC vào ít thiết kế, còn {esc(g1)} có nhiều mẫu khác nhau hơn."
    elif a1 > a2 * 1.5:
        out += f" {esc(g1)} tập trung nhiều QC vào ít thiết kế hơn, còn {esc(g2)} có nhiều mẫu khác nhau hơn."
    o1, o2 = Counter(r["objective"] for r in r1).most_common(1)[0][0], Counter(r["objective"] for r in r2).most_common(1)[0][0]
    out += (f" Cả hai nhóm đều chủ yếu chạy {esc(o1)}." if o1 == o2
            else f" Mục tiêu chính: {esc(g1)} là {esc(o1)}, {esc(g2)} là {esc(o2)}.")
    return tk(out)


def tk_compare(stats):
    live = [s for s in stats if s["ads"]]
    if not live:
        return ""
    idle = [s["short"] for s in stats if not s["ads"]]
    most = max(live, key=lambda s: s["creatives"])
    new = max(live, key=lambda s: s["cre_new_14d"])
    out = [f"<b>{esc(most['short'])}</b> có nhiều mẫu nhất ({most['creatives']} mẫu, {most['ads']} QC)."]
    if new["cre_new_14d"] and new is not most:
        out.append(f"<b>{esc(new['short'])}</b> ra nhiều mẫu mới nhất trong 14 ngày ({new['cre_new_14d']}).")
    elif new["cre_new_14d"]:
        out.append(f"Cũng là đối thủ ra nhiều mẫu mới nhất ({new['cre_new_14d']} trong 14 ngày).")
    keep = max(live, key=lambda s: (s["cre_30d"], s["cre_median_days"]))
    if keep["cre_30d"]:
        out.append(f"<b>{esc(keep['short'])}</b> giữ mẫu lâu nhất ({keep['cre_30d']} mẫu chạy ≥ 30 ngày, một mẫu thường chạy "
                   f"{keep['cre_median_days']:.0f} ngày): có mẫu được duy trì lâu, đáng xem trước.")
    dup = max(live, key=lambda s: s["avg_copies"])
    if dup["avg_copies"] >= 2:
        out.append(f"<b>{esc(dup['short'])}</b> có nhiều QC liên quan trên mỗi mẫu nhất (×{vn(dup['avg_copies'])}); đây là tín hiệu triển khai rộng, không phải dữ liệu ngân sách.")
    if idle:
        out.append(f"{names(idle)} không chạy QC lúc cào.")
    return tk(*out)


def tk_obj_heat(live):
    by = defaultdict(list)
    for s in live:
        o, c = s["objectives"].most_common(1)[0]
        by[o].append(f"{s['short']} {pct(c, s['ads']):.0f}%")
    if not by:
        return ""
    parts = "; ".join(f"<b>{esc(o)}</b>: {esc(', '.join(v))}" for o, v in sorted(by.items(), key=lambda kv: -len(kv[1])))
    return tk(f"Mỗi đối thủ chọn một hướng chính: {parts}.")


def tk_fmt_heat(live):
    if not live:
        return ""
    vid = max(live, key=lambda s: pct(s["formats"].get("Video", 0), s["ads"]))
    out = []
    if vid["formats"].get("Video"):
        out.append(f"<b>{esc(vid['short'])}</b> dùng video nhiều nhất ({pct(vid['formats']['Video'], vid['ads']):.0f}% QC).")
    dco = [s["short"] for s in live if pct(s["formats"].get("Dynamic (DCO)", 0), s["ads"]) >= 30]
    if dco:
        out.append(f"{names(dco)} dựa nhiều vào DCO (≥ 30% QC).")
    img = [s["short"] for s in live if s["ads"] >= 3 and pct(s["formats"].get("Ảnh đơn", 0), s["ads"]) >= 80]
    if img:
        out.append(f"{names(img)} gần như chỉ chạy ảnh đơn.")
    return tk(*out)


def tk_week(live, today):
    if not live:
        return ""
    rows = []
    for s in live:
        c = week_counts(s["rows"], today)
        recent = sum(c.get(i, (0, 0, 0))[2] for i in range(4))       # mẫu hoàn toàn mới 4 tuần gần nhất
        prior = sum(c.get(i, (0, 0, 0))[2] for i in range(4, 8))
        last7 = c.get(0, (0, 0, 0))
        rows.append((s, recent, prior, last7))
    out = []
    top = max(rows, key=lambda x: x[3][1])
    if top[3][1]:
        out.append(f"7 ngày qua <b>{esc(top[0]['short'])}</b> tung nhiều nhất: {top[3][0]} QC trên {top[3][1]} mẫu "
                   f"({top[3][2]} mẫu hoàn toàn mới).")
    up = [x[0]["short"] for x in rows if x[1] >= 4 and x[1] >= 1.5 * max(x[2], 1)]
    if up:
        out.append(f"Đang tăng tốc ra mẫu mới (4 tuần gần đây nhiều hơn hẳn 4 tuần trước): {names(up)}.")
    quiet = [x[0]["short"] for x in rows if x[1] == 0]
    if quiet:
        out.append(f"Không có mẫu mới nào trong 4 tuần: {names(quiet)}, chỉ chạy lại mẫu cũ.")
    return tk(*out)


def tk_profile(s, creatives, lands):
    rs, out = s["rows"], []
    o, c = s["objectives"].most_common(1)[0]
    t = Counter(r["theme"] for r in rs if r["objective"] == o).most_common(1)[0][0]
    d = Counter(dest_detail(r) for r in rs if r["objective"] == o).most_common(1)[0][0]
    out.append(f"{esc(s['short'])} chủ yếu chạy <b>{esc(o)}</b> ({pct(c, s['ads']):.0f}% QC), xoáy vào chủ đề <b>{esc(t)}</b> và dẫn về {esc(d)}.")
    if all(s["stages"].get(st) for st in STAGES):
        out.append("Có QC ở đủ 3 tầng phễu theo CTA/đích đến; dữ liệu không cho biết đối tượng nhắm chọn hay hành trình thực tế sau cú nhấp.")
    elif s["stages"].get("Chuyển đổi", 0) == s["ads"]:
        out.append("100% QC hướng tới hành động chuyển đổi theo CTA/đích đến; cách phân loại này không khẳng định nội dung thiếu vai trò nuôi dưỡng.")
    return tk(*out)


def tk_spark(s, today):
    c = week_counts(s["rows"], today)
    recent = sum(c.get(i, (0, 0, 0))[2] for i in range(2))
    before = sum(c.get(i, (0, 0, 0))[2] for i in range(2, 6))
    if recent == 0 and before == 0:
        return tk("Không có mẫu hoàn toàn mới trong 6 tuần, chỉ duy trì mẫu cũ.")
    if recent >= 2 and recent > before / 2 * 1.5:
        return tk(f"Đang tăng tốc: {recent} mẫu mới trong 2 tuần gần nhất, so với {before} mẫu trong 4 tuần trước đó.")
    if recent == 0:
        return tk(f"Đã chững lại: không có mẫu mới trong 2 tuần, trước đó có {before} mẫu.")
    return tk(f"Nhịp ra mẫu đều: {recent} mẫu mới trong 2 tuần gần nhất, {before} mẫu trong 4 tuần trước đó.")


def tk_offers_profile(rs):
    off = offer_summary(rs)
    parts = []
    if off["Tiền / quà"]:
        parts.append("quà tiền " + ", ".join(k for k, _ in off["Tiền / quà"].most_common(2)))
    if off["Cổ phiếu tặng"]:
        parts.append("tặng cổ phiếu " + ", ".join(k for k, _ in off["Cổ phiếu tặng"].most_common(3)))
    if off["Phí"]:
        parts.append("phí " + ", ".join(k for k, _ in off["Phí"].most_common(1)))
    if off["Margin"]:
        parts.append("margin " + ", ".join(k for k, _ in off["Margin"].most_common(2)))
    return tk("Ưu đãi chủ lực: " + "; ".join(esc(x) for x in parts) + ".") if parts else ""


def tk_top_creatives(creatives):
    if not creatives:
        return ""
    c = creatives[0]
    r = c["rep"]
    out = f"Mẫu mạnh nhất đã chạy {c['days']} ngày với {c['copies']} QC: {esc(r['format'])}, chủ đề {esc(r['theme'])}"
    out += f", {c['variants']} biến thể." if c["variants"] > 1 else "."
    vids = sum(1 for x in creatives[:8] if x["rep"]["format"] == "Video")
    if vids:
        out += f" {vids}/{min(8, len(creatives))} mẫu đứng đầu là video."
    return tk(out)


def tk_lands(lands):
    if not lands:
        return ""
    types = Counter(v["land"]["type"] for v in lands.values())
    t, _ = types.most_common(1)[0]
    out = f"{len(lands)} trang đích khác nhau, phần lớn là {esc(t)}."
    # Meta Pixel chỉ có nghĩa với trang web (App Store / Facebook không gắn được Pixel)
    web = [v for v in lands.values() if v["land"]["type"] in WEB_TYPES + ("Google Form", "Đăng ký webinar (Zoom)")]
    if web:
        px = sum(v["land"]["meta_pixel"] for v in web)
        out += f" {px}/{len(web)} trang web có Meta Pixel" + (" (có đo chuyển đổi)." if px else " (không thấy đo chuyển đổi).")
    return tk(out)


def tk_offer_race(live):
    out = []
    best = []
    for s in live:
        vals = [money_val(x) for r in s["rows"] for x in r["offers"]["money"]]
        if vals:
            best.append((max(vals), s["short"]))
    if best:
        v, who = max(best)
        out.append(f"Quà tiền cao nhất: <b>{esc(who)}</b> ({vn(v / 1e6, 1).rstrip('0').rstrip(',')} triệu)." if v >= 1e6
                   else f"Quà tiền cao nhất: <b>{esc(who)}</b> ({v / 1e3:.0f}K).")
    stocks = [f"{s['short']} ({', '.join(k for k, _ in offer_summary(s['rows'])['Cổ phiếu tặng'].most_common(3))})"
              for s in live if offer_summary(s["rows"])["Cổ phiếu tặng"]]
    if stocks:
        out.append(f"Tặng cổ phiếu: {esc('; '.join(stocks))}.")
    zero = [s["short"] for s in live if any("0%" in r["offers"]["fee"] for r in s["rows"])]
    if zero:
        out.append(f"Đánh vào <b>0 phí giao dịch</b>: {names(zero)}.")
    mg = [(float(x[:-1].replace(",", ".")), s["short"]) for s in live for r in s["rows"] for x in r["offers"]["margin"]]
    if mg:
        v, who = min(mg)
        out.append(f"Margin thấp nhất được quảng cáo: <b>{esc(who)}</b> {vn(v, 1).rstrip('0').rstrip(',')}%.")
    return tk(*out)


def tk_signals(live, rows, keys):
    if not rows:
        return ""
    n = len(rows)
    share = {k: pct(sum(k in r["signals"] for r in rows), n) for k in keys}
    top = sorted(share, key=lambda k: -share[k])[:2]
    out = []
    for k in top:
        lead = max(live, key=lambda s: pct(s["signals"].get(k, 0), s["ads"]))
        out.append(f"<b>{esc(k)}</b> có trong {share[k]:.0f}% QC (mạnh nhất: {esc(lead['short'])}).")
    gaps = [k for k in keys if share[k] < 10]
    if gaps:
        out.append(f"Ít ai nói tới: {esc(', '.join(gaps))}. Đây là các góc tiếp cận còn trống.")
    return tk(*out)


def tk_themes_week(rows, today):
    if not rows:
        return ""
    recent, before = Counter(), Counter()
    for r in rows:
        w = week_of(r, today)
        if w is None:
            continue
        (recent if w < 2 else before if w < 6 else Counter())[r["theme"]] += 1
    if not recent:
        return tk("Không có QC mới nào trong 2 tuần gần nhất.")
    t, k = recent.most_common(1)[0]
    out = f"2 tuần gần nhất, chủ đề được tung nhiều nhất là <b>{esc(t)}</b> ({k} QC)."
    rising = [x for x in recent if recent[x] >= 5 and recent[x] > before.get(x, 0)]
    if rising:
        out += f" Đang lên so với 4 tuần trước: {esc(', '.join(rising[:3]))}."
    return tk(out)


# ───────────────────────── Các tab ─────────────────────────

def compare_section(stats, rows, today):
    trs = ""
    for s in stats:
        lib = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=VN&view_all_page_id={s['page_id']}"
        if not s["ads"]:
            trs += (f"<tr class='idle'><td class='nm'>{esc(s['short'])}</td><td colspan='7'>Không chạy QC tại thời điểm cào</td>"
                    f"<td class='nw'><a href='{lib}' target='_blank' rel='noopener'>Ad Library ↗</a></td></tr>")
            continue
        off = offer_summary(s["rows"])
        hl = "; ".join(f"{lab}: {', '.join(k for k, _ in c.most_common(2))}" for lab, c in off.items() if c and lab != "Hạn")
        lt = s["landing_types"].most_common(1)
        trs += (f"<tr><td class='nm'><a href='#p-{s['page_id']}' data-tab='profiles'>{esc(s['short'])}</a></td>"
                f"<td class='n'><b>{s['creatives']}</b><div class='muted'>{s['ads']} QC</div></td>"
                f"<td class='n'>{s['cre_new_14d']}</td>"
                f"<td class='n'>{s['cre_median_days']:.0f} ngày<div class='muted'>lâu nhất {s['max_days']}</div></td>"
                f"<td class='n'>{s['cre_30d']}</td>"
                f"<td class='n'>×{vn(s['avg_copies'])}<div class='muted'>nhiều nhất ×{s['max_dup']}</div></td>"
                f"<td style='min-width:280px'>{obj_list(s['objectives'], s['ads'])}</td>"
                f"<td>{esc(lt[0][0] if lt else s['top_dest'])}<div class='muted'>{esc(hl)}</div></td>"
                f"<td class='nw'><a href='{lib}' target='_blank' rel='noopener'>Ad Library ↗</a></td></tr>")
    live = [s for s in stats if s["ads"]]
    fmt_keys = [k for k, _ in Counter(r["format"] for r in rows).most_common()]
    obj_keys = [k for k in OBJ_ORDER if any(r["objective"] == k for r in rows)]
    return f"""
<div class="box read"><b>Cách đọc:</b> <b>Mẫu</b> là một thiết kế quảng cáo (các bản chỉ đổi chữ / con số được tính chung). Đối thủ thường chạy 1 mẫu thành nhiều
<b>QC</b> (nhiều bản) trong quá trình triển khai, nên tính theo <b>mẫu</b> mới thấy họ có bao nhiêu ý tưởng khác nhau. Bấm tên đối thủ để xem hồ sơ.</div>
{tk_compare(stats)}
<div class="box tw"><table class="cmp"><tr><th>Đối thủ</th>
<th>Mẫu đang chạy<small>và tổng số QC</small></th>
<th>Mẫu mới<small>bắt đầu trong 14 ngày</small></th>
<th>Mẫu thường chạy<small>một nửa số mẫu chạy lâu hơn</small></th>
<th>Mẫu ≥ 30 ngày<small>dấu hiệu mẫu hiệu quả</small></th>
<th>Mỗi mẫu chạy<small>trung bình bao nhiêu QC</small></th>
<th>Loại chiến dịch<small>% số QC, suy luận</small></th>
<th>Trang đích chính · ưu đãi</th><th></th></tr>{trs}</table></div>
<h3>Loại chiến dịch theo đối thủ</h3><p class="sub">Mỗi ô = % số QC của đối thủ đó thuộc loại chiến dịch này (mỗi hàng cộng lại 100%). Ô càng đậm càng nhiều.</p>
{tk_obj_heat(live)}
<div class="box">{heat_table(live, obj_keys, lambda s, k: pct(s['objectives'].get(k, 0), s['ads']))}</div>
<h3>Định dạng theo đối thủ</h3><p class="sub">Mỗi ô = % số QC của đối thủ đó dùng định dạng này (mỗi hàng cộng lại 100%).</p>
{tk_fmt_heat(live)}
<div class="box">{heat_table(live, fmt_keys, lambda s, k: pct(s['formats'].get(k, 0), s['ads']))}</div>
<h3>Nhịp tung QC mới theo tuần</h3>
<p class="sub">Mỗi ô = <b>số QC mới bắt đầu / số mẫu (hình) mà các QC đó dùng</b> trong 7 ngày đó (chỉ tính QC còn đang chạy lúc cào). Màu đậm theo số mẫu.
Một mẫu có thể là hình hoàn toàn mới hoặc hình cũ được chạy thêm QC; rê chuột vào ô để xem tách riêng. Cột đầu tiên bên phải là 7 ngày gần nhất, các cột khác ghi ngày đầu của mỗi đợt 7 ngày. <b>Bấm vào ô để xem các mẫu đó.</b></p>
{tk_week(live, today)}
<div class="box">{week_table(live, today)}</div>"""


def profile_section(s, creatives, today):
    rs = s["rows"]
    if not rs:
        return (f"<section class='prof box' id='p-{s['page_id']}'><h3>{esc(s['short'])}</h3>"
                f"<p class='muted'>Không có QC đang chạy tại thời điểm cào. "
                f"<a href='https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=VN&view_all_page_id={s['page_id']}' target='_blank' rel='noopener'>Kiểm tra lại trên Ad Library ↗</a></p></section>")
    stages = " · ".join(f"{st} <b>{pct(s['stages'].get(st, 0), s['ads']):.0f}%</b>" for st in STAGES)
    cnt = week_counts(rs, today)
    mx = max((v[1] for v in cnt.values()), default=1)
    spark = "".join(f"<i style='height:{max(4, 100 * cnt[i][1] / mx) if i in cnt else 2:.0f}%' title='{week_label(i, today)}: "
                    f"{cnt.get(i, (0, 0, 0))[0]} QC, {cnt.get(i, (0, 0, 0))[1]} mẫu ({cnt.get(i, (0, 0, 0))[2]} hoàn toàn mới)'></i>"
                    for i in reversed(range(WEEKS)))
    off = offer_summary(rs)
    off_rows = "".join(f"<tr><td>{esc(lab)}</td><td>{esc(', '.join(f'{k} ({v})' for k, v in c.most_common(6)))}</td></tr>"
                       for lab, c in off.items() if c)
    TOP = 8
    cards = "".join(creative_card(c, show_brand=False) for c in creatives[:TOP])
    more = (f"<button class='seeall' data-b='{esc(s['short'])}'>Xem đủ {len(creatives)} mẫu của {esc(s['short'])} trong Thư viện →</button>"
            if len(creatives) > TOP else "")
    # Trang đích: gộp theo URL cuối
    lands = defaultdict(lambda: {"n": 0, "land": None})
    for r in rs:
        if r.get("landing"):
            key = r["landing"]["final_url"] or r["link_url"]
            lands[key]["n"] += 1
            lands[key]["land"] = r["landing"]
    land_cards = "".join(
        f"<a class='lp' href='{esc(v['land']['final_url'] if v['land']['final_url'].startswith('http') else v['land']['url'])}' target='_blank' rel='noopener'>"
        + (f"<img loading='lazy' src='landing/{esc(v['land']['screenshot'])}' alt=''>" if v["land"]["screenshot"] else "<div class='noimg'></div>")
        + f"<div class='cb'><div class='tags'><span>{esc(v['land']['type'])}</span><span>{v['n']} QC</span>"
        + ("<span class='px'>Meta Pixel</span>" if v["land"]["meta_pixel"] else "")
        + f"</div><p>{esc((v['land']['title'] or v['land']['final_host'])[:90])}</p><div class='muted'>{esc(v['land']['final_host'])}</div></div></a>"
        for k, v in sorted(lands.items(), key=lambda kv: -kv[1]["n"])[:8])
    return f"""
<section class="prof box" id="p-{s['page_id']}">
<div class="ph"><h3>{esc(s['short'])}</h3><span class="muted">{esc(s['page_name'])} · {s['likes'] or '–'} like</span></div>
<div class="kpis sm"><div class="kpi"><b>{s['creatives']}</b>mẫu đang chạy ({s['ads']} QC)</div>
<div class="kpi"><b>{s['cre_new_14d']}</b>mẫu mới trong 14 ngày</div>
<div class="kpi"><b>{s['cre_median_days']:.0f} ngày</b>một mẫu thường chạy</div>
<div class="kpi"><b>{s['cre_30d']}</b>mẫu chạy ≥ 30 ngày</div>
<div class="kpi"><b>×{vn(s['avg_copies'])}</b>QC mỗi mẫu (nhiều nhất ×{s['max_dup']})</div></div>
<h4>Loại chiến dịch → chủ đề → trang đích</h4>
<p class="muted">Tầng phễu theo CTA/đích đến: {stages}. % tính trên số QC, không phải ngân sách hay kết quả chuyển đổi.</p>{tk_profile(s, creatives, lands)}{flow_rows(rs)}
<div class="grid2"><div><h4>Số mẫu có QC mới theo 7 ngày</h4>{tk_spark(s, today)}<div class="spark">{spark}</div><div class="muted sprk"><span>{week_span(WEEKS - 1, today)[0]:%d/%m}</span><span>7 ngày qua</span></div></div>
<div><h4>Ưu đãi trích từ caption (số QC)</h4>{tk_offers_profile(rs)}{f"<table class='mini'>{off_rows}</table>" if off_rows else "<p class='muted'>Không thấy con số ưu đãi.</p>"}</div></div>
<h4>Mẫu có tín hiệu đáng chú ý · {min(TOP, len(creatives))} / {len(creatives)} mẫu</h4>
<p class="muted">Xếp theo thời gian duy trì và số QC liên quan. Đây là tín hiệu về mức độ duy trì/triển khai, không phải bằng chứng về chi tiêu, tương tác trên bài hay hiệu quả kinh doanh.</p>
{tk_top_creatives(creatives)}<div class="cards">{cards}</div>{more}
{f"<h4>Trang đích</h4>{tk_lands(lands)}<div class='lps'>{land_cards}</div>" if land_cards else ""}
</section>"""


def offers_section(stats, rows, today):
    live = [s for s in stats if s["ads"]]
    trs = ""
    for s in live:
        off = offer_summary(s["rows"])
        cells = "".join(f"<td>{esc(', '.join(f'{k} ({v})' for k, v in off[lab].most_common(4)))}</td>"
                        for lab in ("Tiền / quà", "Cổ phiếu tặng", "Phí", "Margin", "Hạn"))
        trs += f"<tr><td class='nm'>{esc(s['short'])}</td>{cells}</tr>"
    sig_keys = SIGNAL_KEYS or list(ci.COPY_SIGNALS)
    themes = [k for k, _ in Counter(r["theme"] for r in rows).most_common()]
    head = week_head(today)
    counts = [(t, week_counts([r for r in rows if r["theme"] == t], today)) for t in themes]
    mx = max((v[1] for _, c in counts for v in c.values()), default=1)
    tbody = "".join(f"<tr><td class='nm'>{esc(t)}</td>{week_cells(c, today, 't', t, mx)}</tr>" for t, c in counts)
    return f"""
<h3>Cuộc đua ưu đãi</h3>
<p class="sub">Con số trích tự động từ caption, trong ngoặc là số QC có nhắc. Nên kiểm tra lại thể lệ trên trang đích trước khi so sánh.</p>
{tk_offer_race(live)}
<div class="box tw"><table><tr><th>Đối thủ</th><th>Tiền / quà</th><th>Cổ phiếu tặng</th><th>Phí</th><th>Margin</th><th>Hạn</th></tr>{trs}</table></div>
<h3>Thông điệp theo đối thủ</h3><p class="sub">Mỗi ô = % số QC của đối thủ đó có nhắc tới ý này trong caption. Một QC có thể nhắc nhiều ý, nên hàng không cộng lại 100%.</p>
{tk_signals(live, rows, sig_keys)}
<div class="box">{heat_table(live, sig_keys, lambda s, k: pct(s['signals'].get(k, 0), s['ads']))}</div>
<h3>Chủ đề chính theo 7 ngày tung QC</h3><p class="sub">Mỗi QC được gán 1 chủ đề chính (tín hiệu ưu tiên cao nhất khớp được). Ô = số QC / số mẫu, bấm để xem.</p>
{tk_themes_week(rows, today)}
<div class="box tw"><table class="wkt"><tr><th>Chủ đề</th>{head}</tr>{tbody}</table></div>"""


def gallery_data(creatives):
    out = []
    for c in creatives:
        r = c["rep"]
        out.append({
            "b": c["short"], "g": r.get("group", ""), "f": r["format"], "o": r["objective"], "oc": r["objective_confidence"],
            "t": r["theme"], "a": age_bucket(c["days"]), "d": c["days"], "x": c["copies"], "cap": c["captions"], "v": c["vthumbs"][:6], "s": round(c["score"], 1),
            "st": r["start_ts"] or 0, "sts": sorted({a["start_ts"] for a in c["ads"] if a["start_ts"]}), "img": c["thumb"] or r.get("thumbnail") or "", "lib": r["library_link"],
            "body": (r["body"] or r["title"] or "")[:400], "of": r["offers_text"], "cta": r["cta"],
            "lt": r["landing_type"], "fu": r["final_url"] or r["link_url"], "vd": r.get("video_duration") or 0,
        })
    return out


# ───────────────────────── Trang ─────────────────────────

CSS = dsc.BASE_CSS + """
main{max-width:1240px;margin:0 auto;padding:32px 16px 48px}
@media (min-width:900px){main{padding:40px 48px 48px}}
section>h2:first-child{margin-top:var(--space-3)}
.tk{margin:var(--space-1) 0 12px;padding:10px 14px;border-left:4px solid var(--primary);background:var(--surface-alt);font-size:14px;line-height:1.55}
.tk>b:first-child{margin-right:4px}
.muted{color:var(--ink-muted);font-size:14px}.sub{color:var(--ink-muted);margin:0 0 var(--space-2);font-size:14px}
nav.tabs{position:sticky;top:0;z-index:5;background:var(--surface);display:flex;gap:var(--space-1);overflow-x:auto;padding:12px 0;border-bottom:1px solid var(--hairline);margin:var(--space-3) 0 var(--space-1)}
nav.tabs button{font:inherit;font-size:14px;font-weight:600;border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:8px 14px;border-radius:var(--radius-sm);cursor:pointer;white-space:nowrap}
nav.tabs button:hover{border-color:var(--ink)}
nav.tabs button[aria-selected=true]{background:var(--primary);color:var(--on-primary);border-color:var(--primary)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:var(--space-2) 0}
.kpi{background:var(--surface);padding:var(--space-2);font-size:14px;color:var(--ink-muted)}
.kpi b{display:block;font-size:32px;line-height:1.2;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums;margin-bottom:4px}.kpis.sm .kpi b{font-size:20px;line-height:1.3}
.box{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-md);padding:var(--space-3);margin:var(--space-2) 0}
.box.note,.note{background:var(--surface-alt);border-color:transparent}
.ins{padding-left:20px;margin:0}.ins li{margin:var(--space-1) 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:var(--space-2)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-3)}
.tw{overflow-x:auto}
td.n{text-align:right;font-variant-numeric:tabular-nums}td.nm{font-weight:600;white-space:nowrap}
td.h{text-align:center;background:color-mix(in srgb,var(--heat) calc(var(--a) * var(--heat-max)),transparent);font-variant-numeric:tabular-nums;min-width:38px}
tr.idle td{color:var(--ink-muted);font-style:italic}table.mini td{padding:6px var(--space-1)}
.bar{display:grid;grid-template-columns:170px 1fr 84px;gap:var(--space-1);align-items:center;margin:6px 0;font-size:14px}
.bt{background:var(--track);height:12px;overflow:hidden}.bt i{display:block;height:100%;background:var(--accent)}
.bv{text-align:right;color:var(--ink-muted);font-variant-numeric:tabular-nums}
.flow{display:grid;gap:0}.fr{padding:12px 0;border-bottom:1px solid var(--line)}.fr:last-child{border-bottom:0}
.fh{display:grid;grid-template-columns:230px 1fr 110px;gap:10px;align-items:center}
.fo{font-weight:600;font-size:14px}.fo b{display:inline-block;width:10px;height:10px;margin-right:var(--space-1)}
.fb{background:var(--track);height:14px;overflow:hidden}.fb i{display:block;height:100%}
.fv{text-align:right;color:var(--ink-muted);font-size:14px;font-variant-numeric:tabular-nums}
.fd{display:flex;flex-wrap:wrap;gap:4px 6px;align-items:center;margin:6px 0 0 18px;font-size:13px}
.fd span{background:var(--chip);border-radius:var(--radius-sm);padding:2px 8px}.fd span b{font-weight:700}
.fd .fl{background:none;color:var(--ink-muted);padding:0;min-width:56px;font-weight:600}
.spark{display:flex;align-items:flex-end;gap:3px;height:72px;border-bottom:1px solid var(--hairline)}.spark i{flex:1;background:var(--accent)}
.sprk{display:flex;justify-content:space-between}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:var(--space-2)}
.card,.lp{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-md);overflow:hidden;color:inherit;text-decoration:none;display:flex;flex-direction:column}
a.card:hover,a.lp:hover{border-color:var(--ink)}
.card img,.card .noimg{width:100%;aspect-ratio:1;object-fit:cover;background:var(--track)}
.lps{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:var(--space-2)}
.lp img,.lp .noimg{width:100%;aspect-ratio:390/600;object-fit:cover;object-position:top;background:var(--track)}
.vs{display:flex;gap:4px;padding:4px 4px 0}.vs img{width:34px;height:34px;object-fit:cover;background:var(--track)}
.vs span{font-size:12px;color:var(--ink-muted);align-self:center;margin-left:2px}
.cb{padding:12px}
.seeall,#more{font:inherit;font-size:14px;font-weight:600;padding:8px 16px;border-radius:var(--radius-sm);border:1px solid var(--ink);background:var(--surface);color:var(--ink);cursor:pointer}
.seeall{margin-top:12px}.seeall:hover,#more:hover{background:var(--primary);border-color:var(--primary);color:var(--on-primary)}
#more{margin:var(--space-2) auto;display:block}
.cp{font-weight:700;font-size:14px}.card p,.lp p{font-size:13px;color:var(--ink-muted);margin:6px 0 0;white-space:pre-line}
.of{font-size:13px;margin-top:6px;font-weight:700}
.tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}.tags span{font-size:12px;padding:2px 8px;border-radius:var(--radius-sm);background:var(--chip);color:var(--ink)}
.tags .ob::before{content:"";display:inline-block;width:8px;height:8px;background:var(--c);margin-right:6px}
.tags .px{background:var(--primary);color:var(--on-primary);font-weight:600}
.prof{margin:var(--space-2) 0}.ph{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline}.ph h3{margin:0;font-size:20px;font-weight:600}
.jump{display:grid;gap:var(--space-1);margin:12px 0}.jrow{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.jrow>span{min-width:80px;font-weight:600}
.jump a{font-size:14px;font-weight:600;padding:4px 10px;border-radius:var(--radius-sm);background:var(--surface);border:1px solid var(--line);text-decoration:none;color:var(--ink)}
.jump a:hover{border-color:var(--ink)}
.jump a small{margin-left:6px;color:var(--ink-muted);font-weight:400}.jump a[aria-current=true]{background:var(--primary);color:var(--on-primary);border-color:var(--primary)}.jump a[aria-current=true] small{color:var(--on-primary)}
.flt{display:flex;flex-wrap:wrap;gap:var(--space-1);margin:12px 0}.flt select,.flt input{font:inherit;font-size:14px;padding:8px 10px;border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--surface);color:var(--ink);max-width:100%}
.flt select:hover,.flt input:hover{border-color:var(--ink)}
.flt input{flex:1;min-width:180px}
th small{display:block;font-weight:400;font-size:12px;white-space:normal;max-width:140px;line-height:1.3}
.read{font-size:14px;background:var(--surface-alt);border:0}
.olist{display:grid;gap:4px;font-size:13px}.ol{display:grid;grid-template-columns:minmax(150px,1fr) 56px 34px;gap:6px;align-items:center}
.on{line-height:1.3}.on b{display:inline-block;width:9px;height:9px;margin-right:6px}
.ob2{background:var(--track);height:8px;overflow:hidden}.ob2 i{display:block;height:100%}
.ov{text-align:right;font-variant-numeric:tabular-nums}.ol-more{font-size:12px}
td.nw{white-space:nowrap}table.gl td:first-child{font-weight:700;white-space:nowrap;width:150px}
.wkt td.h{white-space:nowrap;font-size:13px}.wkt td.h small{color:inherit;opacity:.75;margin-left:1px}.wkt td.wk{cursor:pointer}
.wkt td.wk:hover{outline:2px solid var(--ink);outline-offset:-2px}
#f_r{display:none;align-items:center;gap:6px;font-size:14px;font-weight:600;padding:6px 10px;border-radius:var(--radius-sm);background:var(--ink);color:var(--surface)}
#f_r button{font:inherit;border:0;background:transparent;color:var(--surface);cursor:pointer;padding:0 2px}
@media (max-width:700px){.fh{grid-template-columns:1fr 90px}.fb{grid-column:1/-1;order:3}.fd{margin-left:0}
.bar{grid-template-columns:110px 1fr 70px}.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.lps{grid-template-columns:repeat(2,minmax(0,1fr))}.grid2{grid-template-columns:1fr}h1{font-size:26px}.box{padding:var(--space-2)}}
"""

JS = """
const T=[...document.querySelectorAll('nav.tabs button')],P=[...document.querySelectorAll('[data-panel]')];
function show(id,scroll){T.forEach(b=>b.setAttribute('aria-selected',b.dataset.t===id));P.forEach(p=>p.hidden=p.dataset.panel!==id);
 try{localStorage.setItem('tab',id)}catch(e){} if(scroll!==false)window.scrollTo(0,0)}
T.forEach(b=>b.onclick=()=>show(b.dataset.t));
const PR=[...document.querySelectorAll('section.prof')],PJ=[...document.querySelectorAll('a[data-prof]')];
function prof(id){if(!PR.some(p=>p.id===id))id=PR[0]&&PR[0].id;PR.forEach(p=>p.hidden=p.id!==id);PJ.forEach(a=>a.setAttribute('aria-current',a.dataset.prof===id));
 try{localStorage.setItem('prof',id)}catch(e){}}
PJ.forEach(a=>a.onclick=e=>{e.preventDefault();prof(a.dataset.prof)});
document.querySelectorAll('a[data-tab]').forEach(a=>a.onclick=e=>{e.preventDefault();show(a.dataset.tab);prof(a.getAttribute('href').slice(1))});
let fp;try{fp=localStorage.getItem('prof')}catch(e){}prof(fp);
let first='overview';try{first=localStorage.getItem('tab')||first}catch(e){}
if(!T.some(b=>b.dataset.t===first))first='overview';show(first,false);
const D=JSON.parse(document.getElementById('gdata').textContent),C=JSON.parse(document.getElementById('gcolors').textContent);
const F=['b','g','f','o','t','a'].map(k=>[k,document.getElementById('f_'+k)]),Q=document.getElementById('f_q'),S=document.getElementById('f_s');
const G=document.getElementById('gal'),N=document.getElementById('gcount'),M=document.getElementById('more');let lim=60,cur=[],R=null;const RB=document.getElementById('f_r');
const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function card(x){return `<a class="card" href="${e(x.lib)}" target="_blank" rel="noopener">${x.img?`<img loading="lazy" src="${e(x.img)}" alt="">`:'<div class="noimg"></div>'}
${x.v.length>1?`<div class="vs">${x.v.slice(0,5).map(t=>`<img loading="lazy" src="${e(t)}" alt="">`).join('')}${x.v.length>5?'<span>+</span>':''}</div>`:''}
<div class="cb"><div class="cp">${e(x.b)}</div><div class="tags"><span class="ob" style="--c:${C[x.o]||'#adb5bd'}">${e(x.o)}</span>
<span>${x.d} ngày</span><span>${e(x.f)}</span>${x.vd?`<span>${Math.round(x.vd)}s</span>`:''}${x.v.length>1?`<span>${x.v.length}${x.v.length>5?'+':''} biến thể</span>`:''}${x.x>1?`<span>${x.x} QC</span>`:''}${x.cap>1?`<span>${x.cap} caption</span>`:''}${x.lt?`<span>→ ${e(x.lt)}</span>`:''}</div>
${x.of?`<div class="of">${e(x.of)}</div>`:''}<p>${e(x.body.slice(0,220))}${x.body.length>220?'…':''}</p></div></a>`}
function run(){const q=Q.value.toLocaleLowerCase('vi');cur=D.filter(x=>F.every(([k,el])=>!el||!el.value||x[k]===el.value)&&(!R||x.sts.some(t=>t>=R[0]&&t<R[1]))&&(!q||(x.b+' '+x.body+' '+x.of+' '+x.cta+' '+x.fu).toLocaleLowerCase('vi').includes(q)));
 const k=S.value;cur.sort((a,b)=>k==='new'?b.st-a.st:k==='days'?b.d-a.d:k==='copies'?b.x-a.x:b.s-a.s);draw()}
function draw(){G.innerHTML=cur.slice(0,lim).map(card).join('');N.textContent=cur.length+' / '+D.length+' mẫu';M.hidden=cur.length<=lim}
F.forEach(([k,el])=>el&&(el.onchange=()=>{lim=60;run()}));
function range(r,l){R=r;RB.style.display=r?'inline-flex':'none';RB.firstChild.textContent=r?'Bắt đầu chạy '+l:''}
RB.lastChild.onclick=()=>{range(null);lim=60;run()};
document.querySelectorAll('button.seeall').forEach(bt=>bt.onclick=()=>{F.forEach(([k,el])=>{if(el&&el.tagName==='SELECT')el.value=''});
 Q.value='';range(null);document.getElementById('f_b').value=bt.dataset.b;S.value='score';lim=60;run();show('gallery')});
document.querySelectorAll('td.wk').forEach(td=>td.onclick=()=>{F.forEach(([k,el])=>{if(el&&el.tagName==='SELECT')el.value=''});Q.value='';
 const el=document.getElementById('f_'+td.dataset.f);if(el)el.value=td.dataset.v;range([+td.dataset.from,+td.dataset.to],td.dataset.l);
 S.value='new';lim=60;run();show('gallery')});Q.oninput=()=>{lim=60;run()};S.onchange=run;M.onclick=()=>{lim+=60;draw()};run();
"""


def options(values, label, selected=None):
    return f"<option value=''>{label}</option>" + "".join(
        f"<option{' selected' if v == selected else ''}>{esc(v)}</option>" for v in values)


def render(project, proj, rows, stats, has_landings=False, signal_keys=None):
    global SIGNAL_KEYS
    SIGNAL_KEYS = list(signal_keys or [])
    proj = Path(proj)
    now = time.time()
    today = dt.date.today()
    short = {s["page_id"]: s["short"] for s in stats}
    for r in rows:
        r["short"] = short.get(r["page_id"], r["page_name"])
    groups = list(dict.fromkeys(s["group"] for s in stats))
    g0 = groups[0]
    by_group = {g: ([s for s in stats if s["group"] == g], [r for r in rows if r.get("group", g0) == g]) for g in groups}
    s0, r0 = by_group[g0]
    multi = len(groups) > 1

    ASSET_FIRST.clear()
    for r in rows:
        a = r.get("asset_id") or r["collation_id"]
        if r["start_ts"] and (a not in ASSET_FIRST or r["start_ts"] < ASSET_FIRST[a]):
            ASSET_FIRST[a] = r["start_ts"]
    creatives = creatives_of(rows)
    for c in creatives:
        c["short"] = c["rep"]["short"]
    cr_by_page = defaultdict(list)
    for c in creatives:
        cr_by_page[c["rep"]["page_id"]].append(c)

    n0 = len(r0)
    obj0 = Counter(r["objective"] for r in r0)
    stage0 = Counter(r["stage"] for r in r0)
    others = [(g, *by_group[g]) for g in groups[1:]]
    ins = "".join(f"<li>{x}</li>" for x in insights(g0, s0, r0, others))
    group_rows = "".join(
        f"<tr><td class='nm'>{esc(g)}</td><td class='n'>{sum(1 for s in ss if s['ads'])}/{len(ss)}</td><td class='n'>{len(rr)}</td>"
        f"<td class='n'>{len({r['asset_id'] for r in rr})}</td>"
        f"<td style='min-width:240px'>{obj_list(Counter(r['objective'] for r in rr), len(rr)) if rr else ''}</td>"
        f"<td>{esc(Counter(r['theme'] for r in rr).most_common(1)[0][0]) if rr else ''}</td></tr>"
        for g, (ss, rr) in by_group.items())

    tabs = [("overview", "Tổng quan"), ("compare", f"So sánh {g0}" if multi else "So sánh đối thủ"), ("profiles", "Hồ sơ từng đối thủ"),
            ("offers", "Ưu đãi & thông điệp"), ("gallery", "Thư viện creative")]
    tabs += [(f"g{i}", f"Nhóm {g}") for i, g in enumerate(groups[1:], 1)]
    tabs += [("limits", "Giới hạn dữ liệu")]
    nav = "".join(f"<button data-t='{k}' aria-selected='false'>{esc(v)}</button>" for k, v in tabs)

    # Tab hồ sơ: chọn 1 đối thủ để xem (nhóm chính trước, nhóm phụ chỉ những ai có QC)
    prof_stats = s0 + [s for _, ss, _ in others for s in ss if s["ads"]]
    profiles_main = "".join(profile_section(s, cr_by_page[s["page_id"]], today) for s in prof_stats)
    profiles_other = ""
    jump = ""
    for g, ss in [(g0, s0)] + [(g, [s for s in ss if s["ads"]]) for g, ss, _ in others]:
        jump += (f"<div class='jrow'>{f'<span class=muted>{esc(g)}</span>' if multi else ''}"
                 + "".join(f"<a href='#p-{s['page_id']}' data-prof='p-{s['page_id']}'>{esc(s['short'])}"
                           f"<small>{s['creatives'] if s['ads'] else 0} mẫu</small></a>" for s in ss) + "</div>")

    group_tabs = ""
    for i, (g, ss, rr) in enumerate(others, 1):
        diffs = "".join(f"<li>{d}</li>" for d in diff_vs(rr, r0, esc(g), esc(g0)))
        group_tabs += f"""<section data-panel="g{i}" hidden><h2>Nhóm {esc(g)}</h2>
<p class="sub">Dùng để theo dõi xu hướng ngành, không tính vào số liệu của nhóm {esc(g0)}.</p>
{f'<div class="box note"><h3 style="margin-top:0">Khác gì nhóm {esc(g0)}?</h3><ul class="ins">{diffs}</ul></div>' if diffs else ''}
{compare_section(ss, rr, today) if rr else '<p class="muted">Không có QC.</p>'}
<h3>Luồng chạy của cả nhóm</h3>{tk_flow(rr)}<div class="box">{flow_rows(rr)}</div>
<h3>Ưu đãi & thông điệp</h3>{offers_section(ss, rr, today) if rr else ''}</section>"""

    gdata = gallery_data(creatives)
    vals = lambda k: [v for v, _ in Counter(x[k] for x in gdata).most_common() if v]
    brand_order = [s["short"] for s in stats if s["ads"]]
    land_note = "" if has_landings else "<div class='box note'>Chưa mở trang đích. Chạy <code>python3 landing_crawl.py --project " + esc(project) + "</code> rồi chạy lại analyze để có loại trang đích, Meta Pixel và ảnh chụp.</div>"

    page = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QC đối thủ · {esc(project)}</title>{dsc.FONT_LINK}<style>{CSS}</style></head><body>{dsc.BRAND_STRIP}<main>
<h1>Quảng cáo đối thủ · {esc(project)}</h1>
<p class="sub">Meta Ad Library (Việt Nam) · chỉ QC <b>đang chạy</b> · cào lúc {time.strftime('%d/%m/%Y %H:%M')} · {len(rows)} QC, {len(creatives)} creative, {sum(1 for s in stats if s['ads'])} đối thủ có QC</p>
<nav class="tabs" aria-label="Các phần của báo cáo">{nav}</nav>

<section data-panel="overview">
{land_note}
<h2>{'Nhóm ' + esc(g0) if multi else 'Toàn cảnh'}</h2>
<div class="kpis">
<div class="kpi"><b>{sum(1 for s in s0 if s['ads'])}/{len(s0)}</b>đối thủ đang chạy QC</div>
<div class="kpi"><b>{n0}</b>QC đang chạy</div>
<div class="kpi"><b>{len({r['asset_id'] for r in r0})}</b>mẫu quảng cáo khác nhau</div>
<div class="kpi"><b>{sum(s['cre_new_14d'] for s in s0 if s['ads'])}</b>mẫu mới trong 14 ngày</div>
<div class="kpi"><b>{pct(obj0.most_common(1)[0][1], n0) if n0 else 0:.0f}%</b>QC là chiến dịch {esc(obj0.most_common(1)[0][0]) if n0 else ''}</div>
<div class="kpi"><b>{pct(sum(r['format'] == 'Video' for r in r0), n0):.0f}%</b>QC là video</div>
</div>
<div class="box"><h3 style="margin-top:0">Nhận định nhanh</h3><ul class="ins">{ins}</ul></div>
<div class="grid">
<div class="box"><h3 style="margin-top:0">Loại chiến dịch (suy luận)</h3>{tk_objectives(r0)}{bar_rows(obj0, n0, OBJ_COLORS)}</div>
<div class="box"><h3 style="margin-top:0">Tầng phễu</h3>{tk_funnel(r0)}{bar_rows(Counter({st: stage0.get(st, 0) for st in STAGES}), n0)}
<p class="muted">Nhận biết = like trang, tương tác, video view · Cân nhắc = traffic về bài viết / landing / form ngoài · Chuyển đổi = cài app, lead form, tin nhắn, chuyển đổi web.</p></div>
<div class="box"><h3 style="margin-top:0">Trang đích</h3>{tk_landing(r0)}{bar_rows(Counter(dest_label(r) for r in r0), n0)}</div>
<div class="box"><h3 style="margin-top:0">Định dạng</h3>{tk_format(r0)}{bar_rows(Counter(r['format'] for r in r0), n0)}</div>
</div>
<h3>Luồng chạy của nhóm {esc(g0)}</h3>{tk_flow(r0)}<div class="box">{flow_rows(r0)}</div>
{f'<h3>So sánh các nhóm</h3>{tk_groups(by_group)}<div class="box tw"><table><tr><th>Nhóm</th><th>Đối thủ có QC</th><th>QC</th><th>Mẫu</th><th>Loại chiến dịch<small>% số QC</small></th><th>Chủ đề hay dùng nhất</th></tr>{group_rows}</table></div>' if multi else ''}
</section>

<section data-panel="compare" hidden><h2>So sánh {esc(g0) if multi else 'đối thủ'}</h2>{compare_section(s0, r0, today)}</section>

<section data-panel="profiles" hidden><h2>Hồ sơ từng đối thủ</h2>
<p class="sub">Loại chiến dịch là <b>suy luận</b> từ nút CTA và trang đích; xem lý do ở tab Giới hạn dữ liệu.</p>
<div class="jump">{jump}</div>{profiles_main}{profiles_other}</section>

<section data-panel="offers" hidden><h2>Ưu đãi & thông điệp · {esc(g0)}</h2>{offers_section(s0, r0, today)}</section>

<section data-panel="gallery" hidden><h2>Thư viện creative</h2>
<p class="sub">Mỗi thẻ là 1 <b>mẫu</b> = 1 thiết kế. Các bản chỉ đổi chữ / con số ưu đãi trên cùng thiết kế là <b>biến thể</b> (ảnh nhỏ dưới ảnh chính). Thẻ ghi số biến thể, số QC và số caption đang chạy với thiết kế đó. Bấm vào để mở trên Ad Library.</p>
<div class="flt">
<input id="f_q" type="search" placeholder="Tìm trong caption, ưu đãi, link…" aria-label="Tìm kiếm">
<select id="f_b" aria-label="Đối thủ">{options(brand_order, 'Mọi đối thủ')}</select>
{f'<select id="f_g" aria-label="Nhóm">{options(groups, "Mọi nhóm", selected=g0)}</select>' if multi else '<span id="f_g"></span>'}
<select id="f_o" aria-label="Loại chiến dịch">{options(vals('o'), 'Mọi loại chiến dịch')}</select>
<select id="f_f" aria-label="Định dạng">{options(vals('f'), 'Mọi định dạng')}</select>
<select id="f_t" aria-label="Chủ đề">{options(vals('t'), 'Mọi chủ đề')}</select>
<select id="f_a" aria-label="Thời gian chạy">{options(['< 7 ngày', '7–29 ngày', '≥ 30 ngày'], 'Mọi thời gian chạy')}</select>
<span id="f_r"><span></span><button aria-label="Bỏ lọc ngày">✕</button></span>
<select id="f_s" aria-label="Sắp xếp"><option value="score">Đáng học nhất</option><option value="new">Mới nhất</option><option value="days">Chạy lâu nhất</option><option value="copies">Nhiều QC nhất</option></select>
</div><p id="gcount" class="muted"></p><div id="gal" class="cards"></div><button id="more" hidden>Xem thêm</button>
<p class="muted">Tải dữ liệu: <a href="all_ads.csv">all_ads.csv</a> · <a href="competitors_summary.csv">competitors_summary.csv</a></p>
</section>

{group_tabs}

<section data-panel="limits" hidden><h2>Thuật ngữ</h2>
<div class="box"><table class="mini gl">
<tr><td>QC</td><td>Một quảng cáo trên Ad Library (1 mã ID).</td></tr>
<tr><td>Mẫu</td><td>Một thiết kế quảng cáo (hình / video). Các QC cùng thiết kế được tính là 1 mẫu, dù caption, nút bấm, trang đích hay con số ưu đãi trên ảnh khác nhau (nhận diện bằng so khớp ảnh thumbnail). Một mẫu có thể được triển khai thành nhiều QC.</td></tr>
<tr><td>Biến thể</td><td>Các bản của cùng 1 mẫu chỉ khác chữ / con số trên ảnh, ví dụ "Tải app 0đ – nhận tới 80K" và "… 100K". Nhiều biến thể cho thấy mức độ triển khai trên cùng thiết kế; dữ liệu không xác nhận mục đích test.</td></tr>
<tr><td>QC mỗi mẫu</td><td>Trung bình 1 mẫu đang chạy bằng bao nhiêu QC. ×4 = mỗi ý tưởng có khoảng 4 QC liên quan. "Nhiều nhất ×9" = mẫu có nhiều QC liên quan nhất có 9 bản.</td></tr>
<tr><td>Mẫu thường chạy</td><td>Trung vị số ngày chạy của các mẫu: một nửa số mẫu chạy lâu hơn con số này, một nửa ngắn hơn. Ngày chạy của mẫu = bản chạy lâu nhất.</td></tr>
<tr><td>Mẫu ≥ 30 ngày</td><td>Số mẫu đã chạy từ 30 ngày trở lên. Đây là tín hiệu mẫu được duy trì, không phải bằng chứng trực tiếp về hiệu quả.</td></tr>
<tr><td>Mẫu mới</td><td>Mẫu có QC đầu tiên bắt đầu chạy trong 14 ngày gần nhất.</td></tr>
<tr><td>Loại chiến dịch</td><td>Mục tiêu chiến dịch suy ra từ nút bấm và trang đích (Meta không công bố). Xem quy tắc bên dưới.</td></tr>
<tr><td>Tầng phễu</td><td>Phân loại theo CTA/đích đến, không theo phong cách nội dung: Nhận biết = like trang, tương tác, xem video · Cân nhắc = dẫn về bài viết, landing, form ngoài · Chuyển đổi = cài app, lead form, tin nhắn, chuyển đổi trên web. Video kiến thức dẫn tới mở tài khoản vẫn được tính là Chuyển đổi.</td></tr>
</table></div>
<h2>Giới hạn dữ liệu & cách suy luận</h2>
<div class="box"><ul class="ins">
<li><b>Chỉ thấy QC đang chạy.</b> Meta chỉ công bố QC đã dừng, chi tiêu và lượt hiển thị cho QC chính trị và QC ở EU. Với QC thương mại ở VN, lọc "đang chạy + đã dừng" vẫn chỉ trả về QC đang chạy (đã thử ngày 28/10/2026).</li>
<li><b>Loại chiến dịch là suy luận</b>, vì Ad Library không có trường objective. Quy tắc: nút Cài đặt / đích App Store, Google Play → <i>Cài app</i> (tin cậy cao); nút Gửi tin nhắn / Zalo → <i>Tin nhắn</i>; nút Thích trang → <i>Like trang</i>; link về fb.me / facebook kèm nút Đăng ký, Áp dụng → <i>Lead form trên FB</i>; không link / nút xem trang → <i>Tương tác / video view</i>; Google Form, Zoom → <i>Traffic → form/webinar ngoài</i>; bài báo → <i>Traffic → bài viết / PR</i>; landing có form + Meta Pixel → <i>Lead / chuyển đổi trên web</i>; còn lại → <i>Traffic → landing</i> (tin cậy thấp). Cột objective_confidence trong all_ads.csv ghi mức tin cậy cho từng QC.</li>
<li><b>Số QC không phải ngân sách.</b> Một đối thủ có nhiều QC có thể chỉ là đang dùng DCO hoặc nhân bản nhiều biến thể.</li>
<li><b>Số QC đo mức độ active, không phải thị phần.</b> Các tỷ lệ trong báo cáo tính trên số QC đang quan sát được tại thời điểm cào.</li>
<li><b>Không có tương tác trên bài quảng cáo.</b> <code>page_like_count</code> chỉ phản ánh quy mô fanpage, không được dùng để đánh giá hay xếp hạng creative.</li>
<li><b>Creative có tín hiệu đáng chú ý</b> được xếp theo thời gian duy trì và số QC liên quan. Đây không phải bằng chứng về chi tiêu, tương tác trên bài hoặc hiệu quả kinh doanh.</li>
<li><b>Ưu đãi và chủ đề</b> được trích bằng từ khoá trong caption, có thể sót hoặc nhầm; cần đối chiếu với thể lệ trên trang đích.</li>
<li><b>Trang đích</b> được mở bằng trình duyệt mobile (iPhone). Deep link mở app được ghi nhận là App Store / Google Play. Meta Pixel được phát hiện qua script connect.facebook.net / fbq.</li>
</ul></div></section>
{dsc.footer('Quảng cáo đối thủ · ' + esc(project), time.strftime('%d/%m/%Y'))}
</main>
<script type="application/json" id="gdata">{json.dumps(gdata, ensure_ascii=False).replace("</", "<\\/")}</script>
<script type="application/json" id="gcolors">{json.dumps(OBJ_COLORS, ensure_ascii=False)}</script>
<script>{JS}</script></body></html>"""
    (proj / "report.html").write_text(page, encoding="utf-8")
