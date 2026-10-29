"""
Dựng report_google.html cho google_ads_intel.py, cùng bố cục với báo cáo Facebook (report_builder.py):
Tổng quan · So sánh nhóm chính · Hồ sơ từng đối thủ · Thư viện creative · Nhóm ngoài (xu hướng) · Giới hạn dữ liệu.

"Creative" = 1 mã CR… trên Transparency Center. "Mẫu" = 1 video YouTube / 1 ảnh, thường được dùng trong nhiều creative
(nhiều kích thước, nhiều chiến dịch); giống "QC" và "mẫu" bên Facebook.
"""

import json
import re
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

import competitor_intel as ci
import dsc_theme as dsc
import report_builder as rb
from google_ads_intel import ACTIVE_DAYS, FORMATS, OTHER, PLATFORM_ORDER, thumb, weekly_new

esc = ci.esc
PLAT_KEYS = PLATFORM_ORDER + [OTHER]
TABLE_PLATS = ["Search", "YouTube", "Play", OTHER]  # Maps / Shopping chỉ là nơi Google hiện thêm QC Search

# Loại chiến dịch suy ra từ định dạng + tổ hợp nền tảng (Google không công bố):
# - QC chữ trên Search (+ YouTube / Maps / Shopping): chiến dịch Search thường. Mạng tìm kiếm của Google tự hiện QC chữ
#   cả trong kết quả tìm kiếm của YouTube, Google Maps và tab Mua sắm, nên một QC chữ mang nhiều nhãn là bình thường.
# - Có Play: App campaign (cài app), Google tự phân phối video / ảnh trên Search, YouTube, Play.
# - Video / ảnh trên Search + YouTube (không Play): Performance Max hoặc Demand Gen.
CAMPAIGNS = ["Search", "App (cài app)", "PMax / Demand Gen", "Video YouTube", "Display (GDN)", "Khác"]


def campaign_type(r):
    pl = set(r["platforms"].split(","))
    if r["format"].startswith("Chữ"):
        return "Search" if "Search" in pl else "Khác"
    if "Play" in pl:
        return "App (cài app)"
    if "Search" in pl or "Maps" in pl or "Shopping" in pl:
        return "PMax / Demand Gen"
    if pl == {"YouTube"}:
        return "Video YouTube"
    if pl == {OTHER}:
        return "Display (GDN)"
    return "Khác"
WEEKS = 12


def pct(n, d):
    return 100 * n / d if d else 0


def names(xs, n=4):
    xs = list(xs)
    more = f" và {len(xs) - n} đối thủ khác" if len(xs) > n else ""
    return ", ".join(f"<b>{esc(x)}</b>" for x in xs[:n]) + more


def auto_insights(rows, stats):
    """Nhận xét rút ra từ số liệu, theo từng mục của báo cáo. Tự cập nhật mỗi lần chạy."""
    live = [s for s in stats if s["total"]]
    act = [r for r in rows if r["active"]]
    n_act = len(act) or 1
    out = defaultdict(list)

    # 1. Ai đang chạy nhiều nhất
    top = sorted(live, key=lambda s: -s["active"])[:3]
    if act:
        out[1].append("Đang chạy nhiều nhất: " + ", ".join(f"<b>{esc(s['label'])}</b> {s['active']} ({pct(s['active'], n_act):.0f}%)" for s in top)
                      + f". Ba đối thủ này chiếm <b>{pct(sum(s['active'] for s in top), n_act):.0f}%</b> số creative đang chạy.")
    paused = [s["label"] for s in sorted(live, key=lambda s: -s["total"]) if not s["active"] and s["total"] >= 15]
    if paused:
        out[1].append(f"Từng chạy nhiều nhưng hiện <b>không có creative nào đang chạy</b>: {names(paused)}. "
                      "Google không phải kênh chính của họ, hoặc họ đang tạm nghỉ giữa hai đợt.")
    launching = [s for s in live if s["new_14d"] >= 5 and s["new_14d"] >= 0.5 * max(s["active"], 1)]
    if launching:
        out[1].append("Vừa mở đợt mới (phần lớn creative đang chạy mới ra trong 14 ngày): "
                      + ", ".join(f"<b>{esc(s['label'])}</b> {s['new_14d']} mới" for s in launching) + ". Nên theo dõi sát mấy tuần tới.")
    evergreen = sorted((s for s in live if s["winners"] >= 20), key=lambda s: -s["median_days"])
    if evergreen:
        out[1].append("Chạy kiểu \"always-on\" (nhiều creative ≥ 30 ngày hiển thị, trung vị cao): "
                      + ", ".join(f"<b>{esc(s['label'])}</b> trung vị {s['median_days']:g} ngày" for s in evergreen[:4]) + ".")
    absent = [s["label"] for s in stats if not s["total"]]
    if absent:
        out[1].append(f"{len(absent)} đối thủ trong danh sách không có QC Google nào: {names(absent)}.")

    # 2. Nền tảng
    def on(r, pl):
        return pl in r["platforms"].split(",")
    for pl in PLATFORM_ORDER + [OTHER]:
        c = Counter(r["competitor"] for r in act if on(r, pl))
        if c and pl in ("Search", "YouTube", "Play", OTHER):
            lead, v = c.most_common(1)[0]
            out[2].append(f"<b>{esc(pl)}</b>: {sum(c.values())} creative đang chạy, dẫn đầu là <b>{esc(lead)}</b> ({pct(v, sum(c.values())):.0f}%).")
    camp = Counter(campaign_type(r) for r in act)
    if act:
        out[2].append("Loại chiến dịch (suy luận từ định dạng + nền tảng): " + ", ".join(f"<b>{esc(k)}</b> {pct(v, n_act):.0f}%" for k, v in camp.most_common()) + ".")
    txt = [r for r in act if r["format"].startswith("Chữ")]
    if txt:
        out[2].append(f"{len(txt)} QC chữ đang chạy mang nhãn Search kèm YouTube / Maps / Shopping. Đây là <b>chiến dịch Search thường</b>: "
                      "Google tự hiện QC tìm kiếm cả trong ô tìm kiếm của YouTube, Google Maps và tab Mua sắm. Đối thủ không chạy QC bản đồ hay mua sắm riêng.")
    disp = [s["label"] for s in live if s["active"] >= 3
            and pct(sum(1 for r in s["rows"] if r["active"] and r["platforms"] == OTHER), s["active"]) >= 80]
    if disp:
        out[2].append(f"Gần như chỉ chạy mạng hiển thị (banner GDN), không chạy Search: {names(disp)}. Mục tiêu là phủ nhận diện, không phải bắt người đang tìm.")
    play = Counter(r["competitor"] for r in act if on(r, "Play"))
    if play:
        out[2].append("Có creative trên Google Play, tức <b>App campaign</b> kéo lượt cài app (video / ảnh chạy cùng lúc trên Search, YouTube, Play): "
                      + ", ".join(f"<b>{esc(k)}</b> {v}" for k, v in play.most_common(4)) + ".")

    # 3. Định dạng
    fmt = Counter(r["format"] for r in act)
    if act:
        out[3].append("Cơ cấu creative đang chạy của cả nhóm: " + " · ".join(f"<b>{esc(k)}</b> {pct(v, n_act):.0f}%" for k, v in fmt.most_common()) + ".")
    vid_heavy = [s["label"] for s in live if s["active"] >= 3 and pct(s["formats"].get("Video", 0), sum(s["formats"].values())) >= 60]
    if vid_heavy:
        out[3].append(f"Dồn vào video (≥ 60% creative đang chạy): {names(vid_heavy)}.")
    img_only = [s["label"] for s in live if s["active"] >= 3 and s["formats"].get("Ảnh", 0) == sum(s["formats"].values())]
    if img_only:
        out[3].append(f"Chỉ chạy ảnh: {names(img_only)}.")

    # 4. Nhịp ra creative mới
    rising, stopped = [], []
    for s in live:
        w = weekly_new(s["rows"], 12)
        recent, before = sum(w[-4:]), sum(w[:8]) / 2  # quy 8 tuần trước về cùng độ dài 4 tuần
        if recent >= 5 and recent >= 2 * max(before, 1):
            rising.append(f"<b>{esc(s['label'])}</b> {recent} mới trong 4 tuần (trước đó ~{before:.0f}/4 tuần)")
        if recent == 0 and sum(w[:8]) >= 5:
            stopped.append(s["label"])
    if rising:
        out[4].append("Đang tăng tốc ra creative mới: " + "; ".join(rising) + ".")
    if stopped:
        out[4].append(f"Ngừng ra creative mới 4 tuần gần đây (trước đó vẫn ra đều): {names(stopped)}.")
    if not rising and not stopped:
        out[4].append("Không có đối thủ nào thay đổi nhịp đột ngột trong 12 tuần.")

    # 5–6. Creative chạy lâu
    for sec, pool in ((5, [r for r in act if r["youtube_id"]]), (6, [r for r in act if not r["youtube_id"]])):
        if not pool:
            continue
        best = sorted(pool, key=lambda r: -r["days_shown"])[:3]
        out[sec].append("Lâu nhất: " + "; ".join(
            f"<b>{esc(r['competitor'])}</b> {r['days_shown']} ngày"
            + (f" (\"{esc(r['video_title'][:50])}\")" if r["video_title"] else "") for r in best) + ".")
        long_ = Counter(r["competitor"] for r in pool if r["days_shown"] >= 60)
        if long_:
            out[sec].append("Số creative ≥ 60 ngày hiển thị, tức gần như chắc đang hiệu quả: "
                            + ", ".join(f"<b>{esc(k)}</b> {v}" for k, v in long_.most_common(5)) + ".")
    files = [r for r in act if r["youtube_id"] and re.search(r"\.(mp4|mov)$|^\d{3,4}x\d{3,4}", r["video_title"], re.I)]
    if files:
        out[5].append(f"{len(files)} video đang chạy có tiêu đề chỉ là tên file (vd. \"1080x1920 15s.mp4\"). Video đăng ẩn chỉ để chạy QC, "
                      "nên thông điệp phải đọc từ chính video, không đọc từ tiêu đề.")

    # 7. Creative mới
    fresh = [r for r in rows if r["new_14d"]]
    if fresh:
        c = Counter(r["competitor"] for r in fresh)
        out[7].append(f"{len(fresh)} creative mới trong 14 ngày, đến từ {len(c)} đối thủ: "
                      + ", ".join(f"<b>{esc(k)}</b> {v}" for k, v in c.most_common(5)) + ".")
        f = Counter(r["format"] for r in fresh)
        out[7].append("Định dạng của creative mới: " + " · ".join(f"{esc(k)} {pct(v, len(fresh)):.0f}%" for k, v in f.most_common()) + ".")
    else:
        out[7].append("Không đối thủ nào tung creative mới trong 14 ngày.")

    # 8. Thông điệp
    vids = {r["youtube_id"]: r for r in rows if r["youtube_id"]}.values()
    sig = Counter(x for r in vids for x in r["signals"])
    no_sig = sum(1 for r in vids if not r["signals"])
    if sig:
        out[8].append("Chủ đề xuất hiện nhiều nhất trong tiêu đề video: " + ", ".join(f"<b>{esc(k)}</b> {v}" for k, v in sig.most_common(3)) + ".")
    if vids:
        out[8].append(f"{pct(no_sig, len(vids)):.0f}% video không khớp chủ đề nào (tiêu đề là tên file hoặc tên chung chung), "
                      "nên bảng này chỉ phản ánh một phần thông điệp. Xem gói winners_google để đọc thông điệp thật trong video.")
    return out


def load_notes(proj):
    """projects/<project>/google_notes.json: nhận xét viết tay theo mục {"1": ["…"], …, "_updated": "dd/mm/yyyy"}."""
    f = Path(proj) / "google_notes.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def tk(*items, hand=()):
    """Khung "Nhận xét" kiểu báo cáo Facebook (viền xanh), nhưng mỗi ý một dòng. Ý viết tay (hand) đứng sau, có nhãn riêng."""
    items, hand = [x for x in items if x], [x for x in hand if x]
    if not items and not hand:
        return ""
    lis = "".join(f"<li>{x}</li>" for x in items) + "".join(f"<li class='hand{' first' if i == 0 and items else ''}'>{x}</li>" for i, x in enumerate(hand))
    return f"<div class='tk'><b>Nhận xét</b><ul>{lis}</ul></div>"


def comment_box(sec, auto, notes):
    """Một đoạn "Nhận xét:" kiểu báo cáo Facebook (rb.tk): câu tự tính từ số liệu, rồi câu viết tay trong google_notes.json."""
    return tk(*(auto.get(sec) or []), hand=notes.get(str(sec)) or [])


def diff_vs(rows_o, stats_o, rows_m, stats_m, lo, lm):
    """Nhóm ngoài khác nhóm chính ở đâu: dùng để đọc xu hướng ngành."""
    ao, am = [r for r in rows_o if r["active"]], [r for r in rows_m if r["active"]]
    if not ao:
        return [f"Nhóm {esc(lo)} hiện không có creative nào đang chạy."]
    out = []
    no, nm = sum(1 for s in stats_o if s["active"]), sum(1 for s in stats_m if s["active"])
    out.append(f"<b>{esc(lo)}</b>: {len(ao)} creative đang chạy từ {no} đối thủ (trung bình <b>{len(ao) / max(no, 1):.0f}</b>/đối thủ). "
               f"<b>{esc(lm)}</b>: {len(am)} creative từ {nm} đối thủ (trung bình <b>{len(am) / max(nm, 1):.0f}</b>/đối thủ).")
    fo, fm = pct(sum(r["new_14d"] for r in ao), len(ao)), pct(sum(r["new_14d"] for r in am), len(am))
    if abs(fo - fm) >= 10:
        who = lo if fo > fm else lm
        out.append(f"Tỉ lệ creative mới (ra trong 14 ngày) trong số đang chạy: {esc(lo)} <b>{fo:.0f}%</b> và {esc(lm)} <b>{fm:.0f}%</b>. "
                   f"Nhóm <b>{esc(who)}</b> đang làm mới creative nhanh hơn, tức đang test nhiều hơn.")
    def share(rs, f):
        return pct(sum(1 for r in rs if f(r)), len(rs))
    dims = [(f"định dạng {k}", lambda r, k=k: r["format"] == k) for k in FORMATS.values()]
    dims += [(f"nền tảng {p}", lambda r, p=p: p in r["platforms"].split(",")) for p in PLATFORM_ORDER + [OTHER]]
    gaps = sorted(((share(ao, f) - share(am, f), lab, share(ao, f), share(am, f)) for lab, f in dims), key=lambda x: -abs(x[0]))
    for d, lab, a, b in gaps[:4]:
        if abs(d) >= 10:
            out.append(f"{'Nhiều' if d > 0 else 'Ít'} {esc(lab)} hơn: {esc(lo)} <b>{a:.0f}%</b> và {esc(lm)} <b>{b:.0f}%</b> số creative đang chạy.")
    mo = statistics.median([r["days_shown"] for r in ao]); mm = statistics.median([r["days_shown"] for r in am]) if am else 0
    out.append(f"Trung vị số ngày hiển thị của creative đang chạy: {esc(lo)} <b>{mo:g}</b> ngày và {esc(lm)} <b>{mm:g}</b> ngày"
               + (". Nhóm ngoài giữ creative ngắn hơn, tức thay mẫu nhanh hơn." if mo < mm * 0.6 else
                  ". Nhóm ngoài giữ creative lâu hơn." if mo > mm * 1.5 else "."))
    so = Counter(x for r in {r["youtube_id"]: r for r in rows_o if r["youtube_id"]}.values() for x in r["signals"])
    sm = Counter(x for r in {r["youtube_id"]: r for r in rows_m if r["youtube_id"]}.values() for x in r["signals"])
    if so and sm:
        out.append(f"Chủ đề video nhiều nhất: {esc(lo)} <b>{esc(so.most_common(1)[0][0])}</b>, {esc(lm)} <b>{esc(sm.most_common(1)[0][0])}</b>.")
    return out




# ───────────────────────── Tải ảnh về máy ─────────────────────────

def download_images(proj, rows, workers=8):
    """Lưu ảnh QC (ảnh + QC Search dạng ảnh chụp) vào projects/<project>/google/img/, để báo cáo xem offline,
    tải được từng ảnh và không phụ thuộc link của Google. Ảnh đã có thì bỏ qua."""
    import hashlib
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    img_dir = Path(proj) / "google" / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    todo = {}
    for r in rows:
        url = r.get("image_url")
        if url:
            name = re.sub(r"\D", "", url.rsplit("/", 1)[-1])[:24] or hashlib.md5(url.encode()).hexdigest()[:16]
            r["image_local"] = f"google/img/{name}.png"
            if not (Path(proj) / r["image_local"]).exists():
                todo[url] = Path(proj) / r["image_local"]

    def get(item):
        url, dest = item
        tmp = dest.with_suffix(".part")
        ok = subprocess.run(["curl", "-sSfL", "--max-time", "40", "-o", str(tmp), url], capture_output=True).returncode == 0
        if ok and tmp.stat().st_size > 0:
            tmp.rename(dest)
        else:
            tmp.unlink(missing_ok=True)
        return ok

    if todo:
        print(f"  Tải {len(todo)} ảnh QC về {img_dir}…")
        with ThreadPoolExecutor(workers) as ex:
            ok = sum(ex.map(get, todo.items()))
        print(f"  → {ok}/{len(todo)} ảnh")
    for r in rows:  # ảnh tải hỏng thì dùng lại link gốc
        if r.get("image_local") and not (Path(proj) / r["image_local"]).exists():
            r["image_local"] = ""


def thumb_of(r):
    # Ảnh dựng từ script preview (lệnh previews) cho QC không có ảnh tĩnh
    rendered = f"google/img/r_{r['creative_id']}.png"
    if not r.get("image_url") and not r.get("youtube_id") and PROJ and (PROJ / rendered).exists():
        return rendered
    return r.get("image_local") or thumb(r)


PROJ = None  # thư mục project, gán trong render()


# ───────────────────────── Mẫu (gộp creative dùng chung video / ảnh) ─────────────────────────

def creatives_of(rows):
    groups = defaultdict(list)
    for r in rows:
        key = ("yt", r["youtube_id"]) if r["youtube_id"] else ("img", r["image_url"]) if r["image_url"] else ("cr", r["creative_id"])
        groups[(r["competitor"],) + key].append(r)
    now = time.time()
    out = []
    for rs in groups.values():
        rs.sort(key=lambda r: (-r["active"], -r["days_shown"]))
        rep = rs[0]
        days = max(r["days_shown"] for r in rs)
        active = any(r["active"] for r in rs)
        out.append({
            "rep": rep, "rows": rs, "competitor": rep["competitor"], "group": rep["group"], "days": days,
            "copies": len(rs), "active": active, "first_ts": min(r["first_ts"] for r in rs),
            "last_ts": max(r["last_ts"] for r in rs), "new_14d": now - min(r["first_ts"] for r in rs) < 14 * 86400,
            "platforms": sorted({p for r in rs for p in r["platforms"].split(",") if p}, key=PLAT_KEYS.index),
            "thumb": thumb_of(rep), "title": rep["video_title"], "format": rep["format"], "camp": campaign_type(rep),
            # Đang chạy được ưu tiên; chạy càng lâu + càng nhiều creative dùng chung → càng đáng học
            "score": (days * (1 + 0.5 * (len(rs) - 1) ** 0.5)) * (1 if active else 0.3),
        })
    return sorted(out, key=lambda c: -c["score"])


def creative_card(c, show_brand=True):
    r = c["rep"]
    img = (f"<img loading='lazy' src='{esc(c['thumb'])}' alt='' class='zoom' data-full='{esc(c['thumb'])}' data-yt='{esc(r['youtube_id'])}' "
           f"data-lib='{esc(r['link'])}' data-cap='{esc(c['competitor'] + ' · ' + (c['title'] or c['format']))}'>" if c["thumb"] else "<div class='noimg'></div>")
    tags = [f"{c['days']} ngày", c["format"], c["camp"]]
    if c["copies"] > 1:
        tags.append(f"{c['copies']} creative")
    status = f"<span class='px' title='Nền tảng: {esc(', '.join(c['platforms']))}'>Đang chạy</span>" if c["active"] else f"<span>Dừng {time.strftime('%d/%m', time.localtime(c['last_ts']))}</span>"
    yt = f" · <a href='https://youtu.be/{r['youtube_id']}' target='_blank' rel='noopener'>YouTube ↗</a>" if r["youtube_id"] else ""
    return (f"<div class='card{' wide' if c['format'].startswith('Chữ') else ''}'>{img}<div class='cb'>"
            + (f"<div class='cp'>{esc(c['competitor'])}</div>" if show_brand else "")
            + f"<div class='tags'>{status}" + "".join(f"<span>{esc(t)}</span>" for t in tags) + "</div>"
            + (f"<p>{esc(c['title'][:120])}</p>" if c["title"] else "")
            + f"<p class='muted'>{r['first_shown']} → {r['last_shown']} · <a href='{esc(r['link'])}' target='_blank' rel='noopener'>Transparency ↗</a>{yt}</p></div></div>")


def gallery_data(creatives):
    return [{
        "b": c["competitor"], "g": c["group"], "f": c["format"], "p": c["platforms"], "k": c["camp"], "a": "Đang chạy" if c["active"] else "Đã dừng",
        "d": c["days"], "x": c["copies"], "st": c["first_ts"], "s": round(c["score"], 1), "img": c["thumb"], "lib": c["rep"]["link"],
        "t": c["title"][:200], "yt": c["rep"]["youtube_id"], "fs": c["rep"]["first_shown"], "ls": c["rep"]["last_shown"],
    } for c in creatives]


# ───────────────────────── Các khối dùng chung ─────────────────────────

def heat(v, mx):
    return f"<td class='h' style='--a:{v / mx if mx else 0:.2f}'>{v}</td>"


def compare_section(rows, stats, notes):
    """Bảng so sánh (mục 1–4, 8) cho một nhóm, kèm nhận xét."""
    live = [s for s in stats if s["total"]]
    if not live:
        return "<p class='muted'>Không có đối thủ nào chạy QC Google.</p>"
    ins = auto_insights(rows, stats)
    cb = lambda sec: comment_box(sec, ins, notes)
    mx_a = max(s["active"] for s in live) or 1
    sov = "".join(
        f"<tr{'' if s['active'] else ' class=idle'}><td class='nm'><a href='#p-{slug(s['label'])}' data-tab='profiles'>{esc(s['label'])}</a></td>"
        f"{heat(s['active'], mx_a)}<td class='n'>{s['total']}</td><td class='n'>{s['new_14d']}</td><td class='n'>{s['new_30d']}</td>"
        f"<td class='n'>{s['winners']}</td><td class='n'>{s['median_days']:g}</td><td class='n'>{s['max_days']}</td>"
        f"<td class='n'>{s['videos']}</td><td class='nw'>{last_seen(s)}</td></tr>" for s in stats)
    idle = lambda s: "" if s["active"] else " class=idle"

    def on(rs, pl):
        return sum(1 for r in rs if pl in r["platforms"].split(","))
    act_on = {(s["label"], pl): on([r for r in s["rows"] if r["active"]], pl) for s in stats for pl in TABLE_PLATS}
    mx_p = max(act_on.values()) or 1
    plat = "".join(f"<tr{idle(s)}><td class='nm'>{esc(s['label'])}</td>" + "".join(heat(act_on[s['label'], pl], mx_p) for pl in TABLE_PLATS) + "</tr>"
                   for s in stats)
    fmt_keys = list(FORMATS.values())
    fmt = "".join(f"<tr{idle(s)}><td class='nm'>{esc(s['label'])}</td>" + "".join(
        f"<td class='h' style='--a:{rb.pct(s['formats'].get(k, 0), sum(s['formats'].values())) / 100:.2f}'>"
        f"{rb.pct(s['formats'].get(k, 0), sum(s['formats'].values())):.0f}%</td>" for k in fmt_keys) + "</tr>" for s in stats)
    wk = {s["label"]: weekly_new(s["rows"], WEEKS) for s in stats}
    mx_w = max(max(v) for v in wk.values()) or 1
    cad = "".join(f"<tr{idle(s)}><td class='nm'>{esc(s['label'])}</td>" + "".join(heat(v, mx_w) for v in wk[s["label"]]) + "</tr>" for s in stats)
    cad_head = "".join(f"<th>{'tuần này' if w == 0 else f'-{w}'}</th>" for w in reversed(range(WEEKS)))
    vids = {r["youtube_id"]: r for r in rows if r["youtube_id"]}.values()
    sig = Counter(x for r in vids for x in r["signals"])
    return f"""
<h3>1. Ai đang chạy nhiều nhất</h3>{cb(1)}
<div class="box tw"><table><tr><th>Đối thủ</th><th>Đang chạy</th><th>Tổng<small>mọi thời điểm</small></th><th>Mới 14 ngày</th><th>Mới 30 ngày</th>
<th>≥ 30 ngày<small>hiển thị</small></th><th>Trung vị ngày</th><th>Lâu nhất</th><th>Video YouTube</th><th>Hiển thị gần nhất</th></tr>{sov}</table>
<p class='muted'>Dòng in nghiêng: hiện không có creative nào đang chạy. "Không có tài khoản" = không tìm thấy tài khoản Google Ads của đối thủ này.</p></div>
<h3>2. Nền tảng <small class="muted">· số creative đang chạy</small></h3>{cb(2)}
<div class="box tw"><table><tr><th>Đối thủ</th>{''.join(f'<th>{esc(p)}</th>' for p in TABLE_PLATS)}</tr>{plat}</table>
<p class="muted">Một creative có thể mang nhiều nhãn nền tảng nên cộng theo hàng có thể lớn hơn số creative. Không có cột Maps và Shopping: hai nhãn này chỉ xuất hiện trên QC chữ, vì Google tự hiện QC tìm kiếm trên Google Maps và tab Mua sắm (không đối thủ nào chạy QC bản đồ hay QC sản phẩm). Tương tự, QC chữ luôn kèm nhãn YouTube vì cũng hiện trong ô tìm kiếm của YouTube.
"{OTHER}" là creative không nằm trong bộ lọc nền tảng nào của Google, chủ yếu là mạng hiển thị (GDN).</p></div>
<h3>3. Định dạng <small class="muted">· % creative đang chạy (nếu không có thì tính trên toàn bộ)</small></h3>{cb(3)}
<div class="box tw"><table><tr><th>Đối thủ</th>{''.join(f'<th>{esc(k)}</th>' for k in fmt_keys)}</tr>{fmt}</table></div>
<h3>4. Nhịp ra creative mới <small class="muted">· {WEEKS} tuần, theo ngày hiển thị đầu tiên</small></h3>{cb(4)}
<div class="box tw"><table class="wkt"><tr><th>Đối thủ</th>{cad_head}</tr>{cad}</table></div>
<h3>5. Thông điệp trong tiêu đề video YouTube</h3>{cb(8)}
<div class="box">{rb.bar_rows(sig, len(vids)) if sig else "<p class='muted'>Không có dữ liệu.</p>"}
<p class="muted">Dựa trên {len(vids)} tiêu đề video, theo bộ tín hiệu của project. % tính trên số video.</p></div>"""


def last_seen(s):
    if s["active"]:
        return "đang chạy"
    if not s["accounts"]:
        return "không có tài khoản"
    return time.strftime("%d/%m/%Y", time.localtime(s["last"])) if s["last"] else "–"


def slug(label):
    return re.sub(r"[^a-z0-9]+", "-", ci.norm(label)).strip("-")


def kpis(rows, stats, creatives):
    act = [r for r in rows if r["active"]]
    items = [(f"{sum(1 for s in stats if s['active'])}/{len(stats)}", "đối thủ đang chạy QC Google"),
             (len(act), "creative đang chạy"),
             (sum(1 for c in creatives if c["active"]), "mẫu đang chạy (video / ảnh khác nhau)"),
             (sum(c["new_14d"] for c in creatives), "mẫu mới trong 14 ngày"),
             (f"{rb.pct(sum(r['format'] == 'Video' for r in act), len(act)):.0f}%", "creative đang chạy là video"),
             (f"{rb.pct(sum('YouTube' in r['platforms'] for r in act), len(act)):.0f}%", "đang chạy có YouTube")]
    return "<div class='kpis'>" + "".join(f"<div class='kpi'><b>{v}</b>{esc(t)}</div>" for v, t in items) + "</div>"


# ───────────────────────── Hồ sơ đối thủ ─────────────────────────

def profile_insights(s, cr):
    rs, act = s["rows"], [r for r in s["rows"] if r["active"]]
    out = []
    if not act:
        out.append(f"Hiện <b>không có creative nào đang chạy</b>. Lần hiển thị cuối: <b>{last_seen(s)}</b>.")
    else:
        pl = Counter(p for r in act for p in r["platforms"].split(",") if p in TABLE_PLATS)
        out.append(f"<b>{s['active']}</b> creative đang chạy, chủ yếu trên " + ", ".join(f"<b>{esc(k)}</b> {rb.pct(v, len(act)):.0f}%" for k, v in pl.most_common(3)) + ".")
        camp = Counter(campaign_type(r) for r in act)
        out.append("Loại chiến dịch (suy luận): " + ", ".join(f"<b>{esc(k)}</b> {v}" for k, v in camp.most_common()) + " creative.")
    w = weekly_new(rs, WEEKS)
    if sum(w[-4:]) >= 5 and sum(w[-4:]) >= sum(w[:8]):
        out.append(f"Đang <b>tăng tốc</b>: {sum(w[-4:])} creative mới trong 4 tuần gần nhất (8 tuần trước đó: {sum(w[:8])}).")
    elif sum(w) and not sum(w[-4:]):
        out.append("Không ra creative mới trong 4 tuần gần nhất.")
    best = [c for c in cr if c["active"]][:1]
    if best:
        c = best[0]
        out.append(f"Mẫu chạy tốt nhất đang hoạt động: <b>{esc(c['format'])}</b> {c['days']} ngày hiển thị"
                   + (f" (\"{esc(c['title'][:60])}\")" if c["title"] else "") + (f", dùng trong {c['copies']} creative" if c["copies"] > 1 else "") + ".")
    return out


def winner_links(proj, s):
    d = Path(proj) / "winners_google"
    if not d.exists():
        return ""
    ids = {r["youtube_id"] for r in s["rows"] if r["youtube_id"]}
    packs = [p for p in sorted(d.iterdir()) if p.is_dir() and any(p.name.endswith("_" + i) for i in ids)]
    if not packs:
        return ""
    return ("<h4>Gói phân tích video thắng</h4><p class='muted'>" + " · ".join(
        f"<a href='winners_google/{esc(p.name)}/storyboard.jpg' target='_blank'>{esc(p.name)}</a>" for p in packs)
            + " · <a href='winners_google/analysis.md' target='_blank'>analysis.md</a></p>")


def profile_section(s, cr, proj, notes):
    pid = slug(s["label"])
    accounts = " · ".join(f"<a href='https://adstransparency.google.com/advertiser/{a}?region=VN' target='_blank' rel='noopener'>{esc(n)} ↗</a>"
                          for a, n in sorted({(r['advertiser_id'], r['advertiser_name']) for r in s["rows"]}))
    if not s["total"]:
        return (f"<section class='prof box' id='p-{pid}'><div class='ph'><h3>{esc(s['label'])}</h3><span class='muted'>{esc(s['group'])}</span></div>"
                + ("<p class='muted'>Không có tài khoản Google Ads (đã tìm theo tên công ty và domain trên Transparency Center).</p></section>"
                 if not s["accounts"] else "<p class='muted'>Không tìm thấy QC Google nào của tài khoản trong danh sách.</p></section>"))
    act = [r for r in s["rows"] if r["active"]]
    base, note = (act, "creative đang chạy") if act else (s["rows"], "mọi creative (hiện không có creative đang chạy)")
    pl = Counter(p for r in base for p in r["platforms"].split(",") if p in TABLE_PLATS)
    fm = Counter(r["format"] for r in base)
    w = weekly_new(s["rows"], WEEKS)
    mx = max(w) or 1
    spark = "".join(f"<i style='height:{max(4, 100 * v / mx) if v else 2:.0f}%' title='{'tuần này' if i == WEEKS - 1 else f'{WEEKS - 1 - i} tuần trước'}: {v} creative mới'></i>"
                    for i, v in enumerate(w))
    TOP = 8
    cards = "".join(creative_card(c, show_brand=False) for c in cr[:TOP])
    more = (f"<button class='seeall' data-b='{esc(s['label'])}'>Xem đủ {len(cr)} mẫu của {esc(s['label'])} trong Thư viện →</button>"
            if len(cr) > TOP else "")
    hand = notes.get(s["label"]) or []
    return f"""
<section class="prof box" id="p-{pid}">
<div class="ph"><h3>{esc(s['label'])}</h3><span class="muted">{esc(s['group'])} · {len(s['accounts'])} tài khoản: {accounts}</span></div>
<div class="kpis sm"><div class="kpi"><b>{s['active']}</b>creative đang chạy ({s['total']} mọi thời điểm)</div>
<div class="kpi"><b>{sum(1 for c in cr if c['active'])}</b>mẫu đang chạy ({len(cr)} tổng)</div>
<div class="kpi"><b>{s['new_14d']}</b>creative mới trong 14 ngày</div>
<div class="kpi"><b>{s['median_days']:g} ngày</b>một creative thường hiển thị</div>
<div class="kpi"><b>{s['winners']}</b>creative ≥ 30 ngày hiển thị</div>
<div class="kpi"><b>{last_seen(s)}</b>hiển thị gần nhất</div></div>
{tk(*profile_insights(s, cr), hand=hand)}
<div class="grid2"><div><h4>Loại chiến dịch <small class="muted">· suy luận, % {note}</small></h4>{rb.bar_rows(Counter(campaign_type(r) for r in base), len(base))}</div>
<div><h4>Định dạng</h4>{rb.bar_rows(fm, len(base))}</div></div>
<h4>Nền tảng Google gắn nhãn <small class="muted">· QC chữ luôn kèm YouTube vì Google hiện QC tìm kiếm cả trong ô tìm kiếm của YouTube</small></h4>{rb.bar_rows(pl, len(base))}
<h4>Creative mới theo tuần ({WEEKS} tuần)</h4><div class="spark">{spark}</div><div class="muted sprk"><span>{WEEKS} tuần trước</span><span>tuần này</span></div>
<h4>Mẫu đáng học nhất · {min(TOP, len(cr))} / {len(cr)} mẫu</h4>
<p class="muted">Ưu tiên mẫu đang chạy, rồi xếp theo số ngày hiển thị và số creative dùng chung mẫu đó. Bấm ảnh để mở trên Transparency Center.</p>
<div class="cards">{cards}</div>{more}
{winner_links(proj, s)}
</section>"""


# ───────────────────────── Trang ─────────────────────────

CSS = rb.CSS + """
div.tk>b{display:block;margin-bottom:4px}
div.tk ul{margin:0;padding-left:20px}div.tk li{margin:4px 0}
div.tk li.hand{list-style:"✎  "}div.tk li.hand::marker{color:var(--accent-text)}
div.tk li.first{margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}
.box>h3:first-child{margin-top:0}.box h3 small{font-weight:400}
.card .cb p.muted{font-size:12px;margin-top:6px}
.card img,.card .noimg{aspect-ratio:4/3;object-fit:contain;background:var(--track)}
.card.wide img{background:#fff;padding:6px;border-bottom:1px solid var(--line)}
img.zoom{cursor:zoom-in}
#lb{position:fixed;inset:0;z-index:50;background:rgba(15,18,17,.86);display:none;align-items:center;justify-content:center;padding:16px}
#lb.on{display:flex}
#lb figure{margin:0;max-width:min(1100px,100%);max-height:100%;display:flex;flex-direction:column;gap:10px}
#lb img{max-width:100%;max-height:78vh;object-fit:contain;background:#fff;padding:16px;box-sizing:border-box;border-radius:var(--radius-md);image-rendering:auto;min-width:min(720px,100%)}
#lb iframe{width:min(1000px,92vw);aspect-ratio:16/9;border:0;border-radius:var(--radius-md);background:#000}
#lb figcaption{color:#fff;font-size:14px;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
#lb figcaption a,#lb button{color:#fff;font:inherit;font-weight:600;background:none;border:1px solid rgba(255,255,255,.5);border-radius:var(--radius-sm);padding:6px 12px;text-decoration:none;cursor:pointer}
#lb figcaption span{flex:1 1 100%}
#lb .ytbig{position:relative;display:block;border:0;padding:0}#lb .ytbig img{padding:0;min-width:min(720px,92vw)}
#lb .ytbig b{position:absolute;inset:0;margin:auto;width:88px;height:62px;border-radius:14px;background:#f00;color:#fff;font-size:30px;display:flex;align-items:center;justify-content:center}
#lb .lbn{font-size:13px;opacity:.8}#lb code{background:rgba(255,255,255,.15);padding:1px 6px;border-radius:4px}
h3 small.muted{font-weight:400}
"""

JS = """
const T=[...document.querySelectorAll('nav.tabs button')],P=[...document.querySelectorAll('[data-panel]')];
function show(id,scroll){T.forEach(b=>b.setAttribute('aria-selected',b.dataset.t===id));P.forEach(p=>p.hidden=p.dataset.panel!==id);
 try{localStorage.setItem('gtab',id)}catch(e){} if(scroll!==false)window.scrollTo(0,0)}
T.forEach(b=>b.onclick=()=>show(b.dataset.t));
const PR=[...document.querySelectorAll('section.prof')],PJ=[...document.querySelectorAll('a[data-prof]')];
function prof(id){if(!PR.some(p=>p.id===id))id=PR[0]&&PR[0].id;PR.forEach(p=>p.hidden=p.id!==id);PJ.forEach(a=>a.setAttribute('aria-current',a.dataset.prof===id));
 try{localStorage.setItem('gprof',id)}catch(e){}}
PJ.forEach(a=>a.onclick=e=>{e.preventDefault();prof(a.dataset.prof)});
document.querySelectorAll('a[data-tab]').forEach(a=>a.onclick=e=>{e.preventDefault();show(a.dataset.tab);prof(a.getAttribute('href').slice(1))});
let fp;try{fp=localStorage.getItem('gprof')}catch(e){}prof(fp);
let first='overview';try{first=localStorage.getItem('gtab')||first}catch(e){}
if(!T.some(b=>b.dataset.t===first))first='overview';show(first,false);
const D=JSON.parse(document.getElementById('gdata').textContent);
const F=['b','g','f','a','k'].map(k=>[k,document.getElementById('f_'+k)]),FP=document.getElementById('f_p'),Q=document.getElementById('f_q'),S=document.getElementById('f_s');
const G=document.getElementById('gal'),N=document.getElementById('gcount'),M=document.getElementById('more');let lim=60,cur=[];
const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function card(x){return `<div class="card${x.f.startsWith('Chữ')?' wide':''}">${x.img?`<img loading="lazy" src="${e(x.img)}" alt="" class="zoom" data-full="${e(x.img)}" data-yt="${e(x.yt)}" data-lib="${e(x.lib)}" data-cap="${e(x.b+' · '+(x.t||x.f))}">`:'<div class="noimg"></div>'}
<div class="cb"><div class="cp">${e(x.b)}</div><div class="tags">${x.a==='Đang chạy'?'<span class="px">Đang chạy</span>':`<span>Dừng ${e(x.ls.slice(8,10)+'/'+x.ls.slice(5,7))}</span>`}
<span>${x.d} ngày</span><span>${e(x.f)}</span><span title="Nền tảng: ${e(x.p.join(', '))}">${e(x.k)}</span>${x.x>1?`<span>${x.x} creative</span>`:''}</div>
${x.t?`<p>${e(x.t.slice(0,120))}</p>`:''}<p class="muted">${e(x.fs)} → ${e(x.ls)} · <a href="${e(x.lib)}" target="_blank" rel="noopener">Transparency ↗</a>${x.yt?` · <a href="https://youtu.be/${e(x.yt)}" target="_blank" rel="noopener">YouTube ↗</a>`:''}</p></div></div>`}
function run(){const q=Q.value.toLocaleLowerCase('vi');cur=D.filter(x=>F.every(([k,el])=>!el||!el.value||x[k]===el.value)&&(!FP.value||x.p.includes(FP.value))&&(!q||(x.b+' '+x.t).toLocaleLowerCase('vi').includes(q)));
 const k=S.value;cur.sort((a,b)=>k==='new'?b.st-a.st:k==='days'?b.d-a.d:k==='copies'?b.x-a.x:b.s-a.s);draw()}
function draw(){G.innerHTML=cur.slice(0,lim).map(card).join('');N.textContent=cur.length+' / '+D.length+' mẫu';M.hidden=cur.length<=lim}
F.forEach(([k,el])=>el&&(el.onchange=()=>{lim=60;run()}));FP.onchange=()=>{lim=60;run()};
document.querySelectorAll('button.seeall').forEach(bt=>bt.onclick=()=>{F.forEach(([k,el])=>{if(el)el.value=''});FP.value='';
 Q.value='';document.getElementById('f_b').value=bt.dataset.b;S.value='score';lim=60;run();show('gallery')});
document.querySelectorAll('button.preset').forEach(bt=>bt.onclick=()=>{F.forEach(([k,el])=>{if(el)el.value=''});FP.value='';Q.value='';
 const o=JSON.parse(bt.dataset.f);for(const k in o){const el=document.getElementById('f_'+k);if(el)el.value=o[k]}S.value=bt.dataset.s||'score';lim=60;run();show('gallery')});
Q.oninput=()=>{lim=60;run()};S.onchange=run;M.onclick=()=>{lim+=60;draw()};run();
const LB=document.getElementById('lb'),LBF=document.getElementById('lbf');
function closeLB(){LB.classList.remove('on');LBF.innerHTML=''}
document.addEventListener('click',ev=>{const im=ev.target.closest('img.zoom');if(!im)return;
 const yt=im.dataset.yt,src=im.dataset.full,local=!/^https?:/.test(src);
 // YouTube chặn trình phát nhúng khi trang mở từ file:// (không có referrer → lỗi 153): khi đó hiện ảnh lớn + link YouTube
 const embed=yt&&location.protocol.startsWith('http');
 LBF.innerHTML=(embed?`<iframe src="https://www.youtube.com/embed/${e(yt)}?autoplay=1&rel=0" referrerpolicy="strict-origin-when-cross-origin" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>`
  :yt?`<a href="https://youtu.be/${e(yt)}" target="_blank" rel="noopener" class="ytbig"><img src="https://i.ytimg.com/vi/${e(yt)}/hqdefault.jpg" alt=""><b>▶</b></a>`:`<img src="${e(src)}" alt="">`)
 +`<figcaption><span>${e(im.dataset.cap)}</span><a href="${e(im.dataset.lib)}" target="_blank" rel="noopener">Mở trên Transparency ↗</a>`
 +(yt?`<a href="https://youtu.be/${e(yt)}" target="_blank" rel="noopener">YouTube ↗</a>`:`<a href="${e(src)}" ${local?'download':'target="_blank" rel="noopener"'}>Tải ảnh</a>`)
 +`<button id="lbx">Đóng (Esc)</button>`+(yt&&!embed?`<span class="lbn">Muốn xem video ngay trong báo cáo: mở báo cáo bằng lệnh <code>python3 google_ads_intel.py open --project …</code></span>`:'')+`</figcaption>`;LB.classList.add('on');document.getElementById('lbx').onclick=closeLB});
LB.onclick=ev=>{if(ev.target===LB)closeLB()};document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closeLB()});
"""


def options(values, label, selected=None):
    return f"<option value=''>{label}</option>" + "".join(
        f"<option{' selected' if v == selected else ''}>{esc(v)}</option>" for v in values)


def render(project, proj, rows, stats, notes=None):
    global PROJ
    PROJ = Path(proj)
    notes = notes or {}
    groups = list(dict.fromkeys(s["group"] for s in stats))
    g0 = groups[0]
    lo = f"Ngoài {g0}"
    multi = len(groups) > 1
    s0, s1 = [s for s in stats if s["group"] == g0], [s for s in stats if s["group"] != g0]
    r0, r1 = [r for r in rows if r["group"] == g0], [r for r in rows if r["group"] != g0]
    # Nhận xét viết tay: {"Top 10": {"1": [...]}, "Ngoài Top 10": {...}, "Hồ sơ": {"SSI": [...]}}
    flat = {k: v for k, v in notes.items() if k.isdigit()}
    note_of = lambda g: {**(flat if g == g0 else {}), **notes.get(g, {}), "_updated": notes.get("_updated", "?")}
    prof_notes = {**notes.get("Hồ sơ", {}), "_updated": notes.get("_updated", "?")}

    creatives = creatives_of(rows)
    c0 = [c for c in creatives if c["group"] == g0]
    by_comp = defaultdict(list)
    for c in creatives:
        by_comp[c["competitor"]].append(c)

    # Tổng quan (nhóm chính)
    ins0 = auto_insights(r0, s0)
    n0 = note_of(g0)
    quick = ins0.get(1, []) + ins0.get(2, [])[-3:]
    hand0 = n0.get("1", [])
    act0 = [r for r in r0 if r["active"]]
    top_cards = "".join(creative_card(c) for c in [c for c in c0 if c["active"]][:8])
    fresh0 = sorted([c for c in c0 if c["new_14d"]], key=lambda c: -c["first_ts"])[:8]

    def grp_row(label, ss, rr):
        a = [r for r in rr if r["active"]]
        cc = creatives_of(rr)
        return (f"<tr><td class='nm'>{esc(label)}</td><td class='n'>{sum(1 for s in ss if s['active'])}/{len(ss)}</td><td class='n'>{len(a)}</td>"
                f"<td class='n'>{sum(1 for c in cc if c['active'])}</td><td class='n'>{rb.pct(sum(r['new_14d'] for r in a), len(a)):.0f}%</td>"
                f"<td class='n'>{statistics.median([r['days_shown'] for r in a]) if a else 0:g}</td>"
                + "".join(f"<td class='n'>{rb.pct(sum(p in r['platforms'].split(',') for r in a), len(a)):.0f}%</td>" for p in ("Search", "YouTube", "Play", OTHER))
                + "</tr>")
    group_table = (f"""<h3>So sánh các nhóm</h3><div class="box tw"><table><tr><th>Nhóm</th><th>Đối thủ đang chạy</th><th>Creative đang chạy</th>
<th>Mẫu đang chạy</th><th>Mới 14 ngày<small>% creative đang chạy</small></th><th>Trung vị ngày hiển thị</th><th>Search</th><th>YouTube</th><th>Play</th><th>{esc(OTHER)}</th></tr>
{grp_row(g0, s0, r0)}{grp_row(lo, s1, r1)}</table><p class="muted">Chi tiết và xu hướng của nhóm ngoài: tab <a href="#" data-goto="g1">{esc(lo)}</a>.</p></div>""" if multi else "")

    overview = f"""<section data-panel="overview">
<h2>{'Nhóm ' + esc(g0) if multi else 'Toàn cảnh'}</h2>{kpis(r0, s0, c0)}
<div class="box"><h3>Nhận định nhanh</h3><ul class="ins">{''.join(f'<li>{x}</li>' for x in hand0 + quick)}</ul></div>
<div class="grid">
<div class="box"><h3>Loại chiến dịch <small class="muted">· suy luận, creative đang chạy</small></h3>{rb.bar_rows(Counter(campaign_type(r) for r in act0), len(act0))}</div>
<div class="box"><h3>Định dạng <small class="muted">· creative đang chạy</small></h3>{rb.bar_rows(Counter(r['format'] for r in act0), len(act0))}</div>
</div>
{group_table}
<h3>Mẫu đáng học nhất đang chạy</h3>
<p class="muted">Đang chạy, xếp theo số ngày hiển thị và số creative dùng chung. <button class="seeall preset" data-f='{{"g":"{esc(g0)}","a":"Đang chạy"}}'>Xem tất cả trong Thư viện →</button></p>
{tk(*(ins0.get(5) or []), *(ins0.get(6) or []), hand=(n0.get("5") or []) + (n0.get("6") or []))}
<div class="cards">{top_cards or "<p class='muted'>Không có.</p>"}</div>
<h3>Mẫu mới tung ra trong 14 ngày</h3>
{comment_box(7, ins0, n0)}<div class="cards">{''.join(creative_card(c) for c in fresh0) or "<p class='muted'>Không có mẫu mới.</p>"}</div>
</section>"""

    # Hồ sơ
    jump, profs = "", ""
    for g in groups:
        ss = [s for s in stats if s["group"] == g]
        jump += (f"<div class='jrow'>{f'<span class=muted>{esc(g)}</span>' if multi else ''}"
                 + "".join(f"<a href='#p-{slug(s['label'])}' data-prof='p-{slug(s['label'])}'>{esc(s['label'])}"
                           f"<small>{s['active']} đang chạy</small></a>" for s in ss) + "</div>")
        profs += "".join(profile_section(s, by_comp[s["label"]], proj, prof_notes) for s in ss)

    # Nhóm ngoài
    other_tab = ""
    if multi:
        n1 = note_of(lo)
        diffs = "".join(f"<li>{d}</li>" for d in diff_vs(r1, s1, r0, s0, lo, g0))
        xu = n1.get("xu", [])
        c1 = [c for c in creatives if c["group"] != g0]
        other_tab = f"""<section data-panel="g1" hidden><h2>Nhóm {esc(lo)} <small class="muted">({' + '.join(esc(g) for g in groups[1:])})</small></h2>
<p class="sub">Dùng để tham khảo và đọc xu hướng ngành, không tính vào số liệu của nhóm {esc(g0)}.</p>
{kpis(r1, s1, c1)}
<div class="box note"><h3>Khác gì nhóm {esc(g0)}? (xu hướng)</h3><ul class="ins">{''.join(f'<li>{x}</li>' for x in xu)}{diffs}</ul></div>
{compare_section(r1, s1, n1)}
<h3>Mẫu đáng học nhất đang chạy</h3>
{tk(*(auto_insights(r1, s1).get(5) or []), hand=(n1.get("5") or []) + (n1.get("7") or []))}
<div class="cards">{''.join(creative_card(c) for c in [c for c in c1 if c['active']][:8])}</div>
</section>"""

    tabs = [("overview", "Tổng quan"), ("compare", f"So sánh {g0}" if multi else "So sánh đối thủ"), ("profiles", "Hồ sơ từng đối thủ"),
            ("gallery", "Thư viện creative")] + ([("g1", f"Nhóm {lo}")] if multi else []) + [("limits", "Giới hạn dữ liệu")]
    nav = "".join(f"<button data-t='{k}' aria-selected='false'>{esc(v)}</button>" for k, v in tabs)
    gdata = gallery_data(creatives)
    brands = [s["label"] for s in stats if s["total"]]

    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Google Ads đối thủ · {esc(project)}</title>{dsc.FONT_LINK}<style>{CSS}</style></head><body>{dsc.BRAND_STRIP}<main>
<h1>Google Ads của đối thủ · {esc(project)}</h1>
<p class="sub">Google Ads Transparency Center (Việt Nam) · cập nhật {time.strftime('%d/%m/%Y %H:%M')} · {len(rows)} creative ({sum(r['active'] for r in rows)} đang chạy),
{len(creatives)} mẫu, {sum(1 for s in stats if s['total'])} đối thủ có QC Google</p>
<nav class="tabs" aria-label="Các phần của báo cáo">{nav}</nav>
{overview}
<section data-panel="compare" hidden><h2>So sánh {esc(g0) if multi else 'đối thủ'}</h2>{compare_section(r0, s0, note_of(g0))}</section>
<section data-panel="profiles" hidden><h2>Hồ sơ từng đối thủ</h2>
<p class="sub">Chọn một đối thủ. Số bên cạnh tên là số creative đang chạy.</p>
<div class="jump">{jump}</div>{profs}</section>
<section data-panel="gallery" hidden><h2>Thư viện creative</h2>
<p class="sub">Mỗi thẻ là 1 <b>mẫu</b> = 1 video YouTube hoặc 1 ảnh. Một mẫu thường được dùng trong nhiều <b>creative</b> (nhiều kích thước, nhiều chiến dịch); thẻ ghi số creative dùng chung. Bấm ảnh để mở trên Transparency Center.</p>
<div class="flt">
<input id="f_q" type="search" placeholder="Tìm trong tên đối thủ, tiêu đề video…" aria-label="Tìm kiếm">
<select id="f_b" aria-label="Đối thủ">{options(brands, 'Mọi đối thủ')}</select>
{f'<select id="f_g" aria-label="Nhóm">{options(groups, "Mọi nhóm")}</select>' if multi else '<span id="f_g"></span>'}
<select id="f_a" aria-label="Trạng thái">{options(['Đang chạy', 'Đã dừng'], 'Mọi trạng thái', selected='Đang chạy')}</select>
<select id="f_f" aria-label="Định dạng">{options(list(FORMATS.values()), 'Mọi định dạng')}</select>
<select id="f_k" aria-label="Loại chiến dịch">{options(CAMPAIGNS, 'Mọi loại chiến dịch')}</select>
<select id="f_p" aria-label="Nền tảng">{options(TABLE_PLATS, 'Mọi nền tảng')}</select>
<select id="f_s" aria-label="Sắp xếp"><option value="score">Đáng học nhất</option><option value="new">Mới nhất</option><option value="days">Hiển thị lâu nhất</option><option value="copies">Nhiều creative nhất</option></select>
</div><p id="gcount" class="muted"></p><div id="gal" class="cards"></div><button id="more" hidden>Xem thêm</button>
<p class="muted">Tải dữ liệu: <a href="google_all_ads.csv">google_all_ads.csv</a> · <a href="google_summary.csv">google_summary.csv</a></p>
</section>
{other_tab}
<section data-panel="limits" hidden><h2>Thuật ngữ</h2>
<div class="box"><table class="mini gl">
<tr><td>Creative</td><td>Một mã CR… trên Transparency Center. Một video hay ảnh được đưa vào nhiều chiến dịch / kích thước sẽ thành nhiều creative.</td></tr>
<tr><td>Mẫu</td><td>Một video YouTube hoặc một ảnh. Các creative dùng chung video / ảnh được gộp làm 1 mẫu. Mẫu dùng trong nhiều creative = đang được đẩy rộng.</td></tr>
<tr><td>Nhận xét</td><td>Ý gạch đầu dòng thường = tự tính từ số liệu, cập nhật mỗi lần chạy. Ý có dấu ✎ = nhận xét viết tay của người phân tích (google_notes.json).</td></tr>
<tr><td>Đang chạy</td><td>Có lần hiển thị cuối trong {ACTIVE_DAYS} ngày gần nhất.</td></tr>
<tr><td>Ngày hiển thị</td><td>Số ngày Google thực sự phân phối creative (không phải từ ngày đầu đến ngày cuối). ≥ 30 ngày gần như chắc là đang hiệu quả.</td></tr>
<tr><td>Nền tảng</td><td>Search, YouTube, Play, Maps, Shopping lấy từ bộ lọc của Google. "{esc(OTHER)}" = không thuộc bộ lọc nào, chủ yếu mạng hiển thị (GDN). </td></tr>
<tr><td>Loại chiến dịch</td><td>Suy luận, vì Google không công bố: QC chữ có Search → <b>Search</b> (Google tự hiện cả trên YouTube, Maps, tab Mua sắm) · video / ảnh có Play → <b>App (cài app)</b> · video / ảnh có Search hoặc Maps nhưng không có Play → <b>PMax / Demand Gen</b> · chỉ YouTube → <b>Video YouTube</b> · chỉ "{esc(OTHER)}" → <b>Display (GDN)</b>.</td></tr>
</table></div>
<h2>Giới hạn dữ liệu</h2>
<div class="box"><ul class="ins">
<li><b>Google không công bố</b> từ khoá, ngân sách, lượt hiển thị, CTR hay nhắm mục tiêu (trừ QC chính trị). Muốn biết từ khoá đối thủ bid: Keyword Planner hoặc SEMrush.</li>
<li><b>QC Search chỉ có ảnh chụp</b>, không có chữ, nên không phân tích được thông điệp QC Search tự động. Bấm vào ảnh để đọc.</li>
<li><b>Thông điệp video</b> chỉ đọc từ tiêu đề YouTube. Nhiều tiêu đề là tên file; muốn đọc thông điệp thật thì xem gói winners_google (khung hình + lời thoại).</li>
<li><b>Số creative không phải ngân sách.</b> App campaign và Performance Max tự sinh nhiều creative từ ít tài sản.</li>
<li>Dữ liệu lấy qua API nội bộ của Transparency Center; Google có thể đổi bất kỳ lúc nào.</li>
</ul></div></section>
{dsc.footer('Google Ads đối thủ · ' + esc(project), time.strftime('%d/%m/%Y'))}
</main>
<div id="lb" role="dialog" aria-modal="true" aria-label="Xem lớn"><figure id="lbf"></figure></div>
<script type="application/json" id="gdata">{json.dumps(gdata, ensure_ascii=False).replace("</", "<\\/")}</script>
<script>{JS}
document.querySelectorAll('a[data-goto]').forEach(a=>a.onclick=e=>{{e.preventDefault();show(a.dataset.goto)}});</script></body></html>"""
