"""
Phân tích quảng cáo đối thủ trên Meta Ad Library, gồm 2 luồng:

  1) discover: tìm theo từ khoá ngành → lọc đúng ngành → danh sách fanpage đối thủ
  2) analyze : cào TOÀN BỘ quảng cáo đang chạy của từng fanpage → báo cáo HTML

Ví dụ (ngành tấm lợp poly):
    python3 competitor_intel.py discover --project tam-lop-poly \
        --keyword "tấm lợp poly" --keyword "tấm poly" --keyword "polycarbonate" \
        --keyword "tấm lợp lấy sáng" --keyword "nhựa lấy sáng" \
        --match "polycarbonate|tam poly|tam lop|lay sang|ton nhua|mai poly"

    # Mở projects/tam-lop-poly/competitors.txt, xoá dòng không phải đối thủ, thêm Page ID nếu thiếu
    python3 competitor_intel.py analyze --project tam-lop-poly

    # Hoặc chạy cả 2 bước liền
    python3 competitor_intel.py run --project tam-lop-poly --keyword ... --match ...
"""

import argparse
import csv
import html
import json
import math
import re
import shutil
import statistics
import subprocess
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import fb_ads_scraper as fb

CACHE_HOURS = 12

# Tín hiệu trong nội dung quảng cáo (so khớp trên văn bản đã bỏ dấu, chữ thường)
COPY_SIGNALS = {
    "Giá / báo giá": r"bao gia|gia (chi|tu|re|si|goc|xuong|tot|uu dai|canh tranh)|\d[\d\.,]*\s?(k|d|vnd|dong)\b|/ ?m2|/ ?tam",
    "Số điện thoại": r"(0|\+84)[\s\.]?\d{2,3}[\s\.]?\d{3}[\s\.]?\d{3,4}",
    "Zalo": r"zalo",
    "Giao hàng toàn quốc": r"giao hang|van chuyen|freeship|mien phi ship|toan quoc",
    "Bảo hành": r"bao hanh",
    "Thi công / lắp đặt": r"thi cong|lap dat",
    "Khuyến mãi": r"khuyen mai|giam gia|uu dai|qua tang|tang kem|\bsale\b|chiet khau",
    "Thông số kỹ thuật": r"\d+([\.,]\d+)?\s?(mm|ly|li|zem)\b|kich thuoc|do day|kho \d",
    "Chất lượng / chống UV": r"chinh hang|nhap khau|chong uv|\buv\b|chiu luc|khong vo|do ben",
    "Tổng kho / xưởng": r"tong kho|xuong|nha may|kho hang|san xuat",
}



def load_project_signals(proj):
    """projects/<project>/signals.json (tên → regex không dấu) thay bộ tín hiệu mặc định của ngành tấm lợp."""
    f = Path(proj) / "signals.json"
    if f.exists():
        COPY_SIGNALS.clear()
        COPY_SIGNALS.update({k: v for k, v in json.loads(f.read_text(encoding="utf-8")).items() if not k.startswith("_")})
        print(f"  Dùng bộ tín hiệu riêng của project: {f}")


FORMAT_LABELS = {
    "VIDEO": "Video",
    "IMAGE": "Ảnh đơn",
    "MULTI_IMAGES": "Nhiều ảnh",
    "CAROUSEL": "Carousel",
    "DCO": "Dynamic (DCO)",
    "DPA": "Catalog (DPA)",
    "TEXT": "Chỉ chữ",
    "EVENT": "Sự kiện",
}

DEFAULT_GROUP = "Đối thủ"

# Link rút gọn / deep link mở app (AppsFlyer, Branch, Adjust…)
APP_LINK_HOSTS = ("go.link", "onelink.me", "app.link", "adj.st", "page.link", "smart.link", "apps.apple.com",
                  "itunes.apple.com", "play.google.com")
# Chữ in hoa 3 ký tự hay đứng sau "cổ phiếu" nhưng không phải mã chứng khoán
NOT_TICKERS = {"HOT", "TOP", "VIP", "NEW", "APP", "CFA", "VND", "USD", "FREE", "MOI", "SALE", "LAI", "CAO", "DAU"}

# Loại chiến dịch suy luận (Ad Library không công bố objective) → giai đoạn phễu
OBJECTIVE_STAGE = {
    "Cài app": "Chuyển đổi",
    "Lead form trên FB": "Chuyển đổi",
    "Lead / chuyển đổi trên web": "Chuyển đổi",
    "Tin nhắn": "Chuyển đổi",
    "Traffic → form / webinar ngoài": "Cân nhắc",
    "Traffic → landing": "Cân nhắc",
    "Traffic → bài viết / PR": "Cân nhắc",
    "Like trang": "Nhận biết",
    "Tương tác / video view": "Nhận biết",
}

DURATION_BUCKETS = [(0, 7, "< 7 ngày"), (7, 30, "7–29 ngày"), (30, 90, "30–89 ngày"), (90, 10**6, "≥ 90 ngày")]


def norm(s):
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def ad_text(r):
    return " ".join([r.get("body") or "", r.get("title") or "", r.get("link_description") or ""])


# ───────────────────────── Luồng 1: discover ─────────────────────────

def discover(args):
    proj = Path(args.out) / args.project
    proj.mkdir(parents=True, exist_ok=True)
    match = re.compile(norm(args.match)) if args.match else None

    rows, hits = {}, defaultdict(set)
    for kw in args.keyword:
        print(f"\n▶ Tìm từ khoá: {kw}")
        url = fb.build_url(args.country, keyword=kw, media_type="all", exact=True)
        for ad in fb.scrape(url, args.max_scrolls, not args.show_browser):
            r = fb.to_row(ad)
            rows[r["ad_archive_id"]] = r
            hits[r["ad_archive_id"]].add(kw)

    pages = {}
    dropped = Counter()
    for aid, r in rows.items():
        text = norm(ad_text(r) + " " + (r["page_name"] or ""))
        if match and not match.search(text):
            dropped[r["page_name"]] += 1
            continue
        p = pages.setdefault(r["page_id"], {
            "page_id": r["page_id"], "page_name": r["page_name"], "page_like_count": r["page_like_count"],
            "page_categories": r["page_categories"], "page_url": r["page_url"],
            "matched_ads": 0, "keywords": set(), "sample": "",
        })
        p["matched_ads"] += 1
        p["keywords"] |= hits[aid]
        if not p["sample"]:
            p["sample"] = (r["body"] or "").replace("\n", " ")[:160]

    # Fanpage có tên đúng ngành thì gần như chắc là đối thủ; còn lại để comment cho người dùng tự xem
    name_rx = re.compile(norm(args.name_match or args.match or "")) if (args.name_match or args.match) else None
    for p in pages.values():
        p["name_match"] = bool(name_rx and name_rx.search(norm(p["page_name"])))
    ranked = sorted(pages.values(), key=lambda p: (not p["name_match"], -p["matched_ads"], -(p["page_like_count"] or 0)))
    (proj / "discover_ads.json").write_text(json.dumps(list(rows.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    with open(proj / "competitors.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["page_id", "page_name", "name_match", "matched_ads", "page_like_count",
                                          "page_categories", "keywords", "page_url", "sample"])
        w.writeheader()
        for p in ranked:
            w.writerow({**p, "keywords": "; ".join(sorted(p["keywords"]))})
    with open(proj / "competitors.txt", "w", encoding="utf-8") as f:
        f.write("# Mỗi dòng 1 Page ID. Dòng bắt đầu bằng # sẽ bị bỏ qua.\n"
                "# Nhóm 1 (đã chọn): tên fanpage đúng ngành. Nhóm 2 (đang tắt): có QC khớp từ khoá nhưng tên\n"
                "# không rõ ngành, xoá dấu # ở đầu dòng nếu đúng là đối thủ.\n\n")
        for p in ranked:
            prefix = "" if p["name_match"] else "# "
            f.write(f"{prefix}{p['page_id']}  # {p['page_name']} ({p['matched_ads']} QC khớp, "
                    f"{p['page_like_count'] or '?'} like)\n")

    picked = [p for p in ranked if p["name_match"]]
    print(f"\n✔ {len(rows)} quảng cáo tìm được, {len(ranked)} fanpage có QC khớp ngành "
          f"(loại {sum(dropped.values())} QC lạc đề). Tự chọn {len(picked)} fanpage có tên đúng ngành:")
    for p in picked[:40]:
        print(f"  {p['matched_ads']:>3} QC  {p['page_name']}  (id {p['page_id']}, {p['page_like_count'] or '?'} like)")
    print(f"\n→ Kiểm tra lại {proj / 'competitors.txt'} rồi chạy: analyze --project {args.project}")


# ───────────────────────── Luồng 2: analyze ─────────────────────────

def read_competitors(path):
    """Mỗi dòng 1 Page ID. Dòng "#@ Tên nhóm" mở một nhóm mới (vd. "#@ Top 10"), dòng "#" khác là comment.
    Trả về [{pid, group, label}] theo đúng thứ tự trong file."""
    out, group = [], DEFAULT_GROUP
    for line in open(path, encoding="utf-8"):
        if line.startswith("#@"):
            group = line[2:].strip() or DEFAULT_GROUP
            continue
        pid, _, label = line.partition("#")
        if pid.strip():
            out.append({"pid": pid.strip(), "group": group, "label": label.strip()})
    return out


def scrape_pages(page_ids, proj, args):
    cache_dir = proj / "pages"
    cache_dir.mkdir(exist_ok=True)
    rows = []
    for pid in page_ids:
        cache = cache_dir / f"{pid}.json"
        if cache.exists() and not args.refresh and time.time() - cache.stat().st_mtime < CACHE_HOURS * 3600:
            page_rows = json.loads(cache.read_text(encoding="utf-8"))
            print(f"▶ {pid}: dùng cache ({len(page_rows)} QC)")
        else:
            print(f"\n▶ Cào fanpage {pid}")
            url = fb.build_url(args.country, page_id=pid, media_type="all")
            page_rows = [fb.to_row(a) for a in fb.scrape(url, args.max_scrolls, not args.show_browser)]
            # Trang page_id chỉ nên chứa QC của chính page đó
            page_rows = [r for r in page_rows if str(r["page_id"]) == str(pid)]
            cache.write_text(json.dumps(page_rows, ensure_ascii=False), encoding="utf-8")
            print(f"  → {len(page_rows)} QC")
        rows += page_rows
    return rows


def probe_video(url):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:format=duration", "-of", "json", url],
            capture_output=True, text=True, timeout=45)
        d = json.loads(out.stdout or "{}")
        st = (d.get("streams") or [{}])[0]
        return {"w": st.get("width"), "h": st.get("height"), "dur": float(d.get("format", {}).get("duration") or 0)}
    except Exception:
        return None


def probe_videos(rows, limit):
    if not shutil.which("ffprobe"):
        print("  (không có ffprobe, bỏ qua đo độ dài / tỉ lệ video)")
        return
    # Mỗi creative (collation) chỉ cần đo 1 lần
    targets = {}
    for r in rows:
        if r["video_urls"] and r["collation_id"] not in targets:
            targets[r["collation_id"]] = r["video_urls"][0]
    items = list(targets.items())[:limit]
    print(f"  Đo độ dài & tỉ lệ khung hình của {len(items)} video…")
    with ThreadPoolExecutor(8) as ex:
        results = dict(zip([k for k, _ in items], ex.map(probe_video, [u for _, u in items])))
    for r in rows:
        info = results.get(r["collation_id"])
        if info and info["w"] and info["h"]:
            r["video_duration"] = round(info["dur"], 1)
            r["aspect"] = aspect_label(info["w"], info["h"])


def aspect_label(w, h):
    x = w / h
    if x < 0.7:
        return "9:16 (dọc)"
    if x < 0.9:
        return "4:5"
    if x < 1.1:
        return "1:1 (vuông)"
    if x > 1.5:
        return "16:9 (ngang)"
    return "Khác"


def duration_bucket(sec):
    for lo, hi, lab in [(0, 15, "< 15s"), (15, 30, "15–30s"), (30, 60, "30–60s"), (60, 180, "1–3 phút"), (180, 10**6, "> 3 phút")]:
        if lo <= sec < hi:
            return lab


def run_bucket(days):
    for lo, hi, lab in DURATION_BUCKETS:
        if lo <= (days or 0) < hi:
            return lab


def destination(r):
    cta, link = (r["cta_type"] or "").upper(), (r["link_url"] or "").lower()
    host = urlparse(link).netloc.replace("www.", "") if link else ""
    if "zalo" in host or "zalo" in norm(r["cta"]):
        return "Zalo"
    if cta in ("MESSAGE_PAGE", "SEND_MESSAGE") or host in ("m.me", "messenger.com") or "messenger" in norm(r["cta"]):
        return "Messenger"
    if cta in ("WHATSAPP_MESSAGE",) or "wa.me" in host:
        return "WhatsApp"
    if cta == "CALL_NOW" or link.startswith("tel:"):
        return "Gọi điện"
    if "instagram.com" in host:
        return "Instagram"
    if "fb.me" in host or "facebook.com" in host:
        return "Facebook (form/trang)"
    if host:
        return "Website"
    return "Không có CTA"


def infer_objective(r, land):
    """(objective, độ tin cậy, lý do) suy ra từ nút CTA + link + trang đích thật."""
    cta = (r.get("cta_type") or "").upper()
    host = urlparse(r.get("link_url") or "").netloc.lower().replace("www.", "")
    lt = (land or {}).get("type", "")
    app_link = any(x in host for x in APP_LINK_HOSTS)
    if (cta in ("INSTALL_MOBILE_APP", "USE_APP", "INSTALL_APP") or lt in ("App Store", "Google Play", "Mở app (deep link)")
            or (app_link and cta in ("DOWNLOAD", "INSTALL_MOBILE_APP", "LEARN_MORE", "SIGN_UP", "APPLY_NOW", "GET_OFFER") and not lt)):
        return "Cài app", "Cao", f"Nút {cta or '–'}, đích {lt or host}"
    if cta in ("MESSAGE_PAGE", "SEND_MESSAGE", "WHATSAPP_MESSAGE") or lt in ("Messenger", "Zalo"):
        return "Tin nhắn", "Cao", f"Nút {cta}, đích {lt or host}"
    if cta == "LIKE_PAGE":
        return "Like trang", "Cao", "Nút Thích trang"
    if host in ("fb.me", "fb.com", "facebook.com", "m.facebook.com") and cta in (
            "SIGN_UP", "APPLY_NOW", "GET_QUOTE", "SUBSCRIBE", "GET_OFFER", "LEARN_MORE", "CONTACT_US"):
        if "messenger" in (r.get("link_url") or ""):
            return "Tin nhắn", "Trung bình", "Link fb.com/messenger"
        return "Lead form trên FB", "Trung bình", f"Nút {cta}, link về Facebook (thường là Instant Form)"
    if not r.get("link_url") or cta in ("", "NO_BUTTON", "VISIT_PROFILE", "WATCH_MORE") or lt == "Trang Facebook":
        return "Tương tác / video view", "Trung bình", "Không có link ra ngoài / nút xem trang, xem thêm"
    if lt in ("Google Form", "Đăng ký webinar (Zoom)"):
        return "Traffic → form / webinar ngoài", "Trung bình", f"Đích là {lt}"
    if lt == "Bài viết / PR":
        return "Traffic → bài viết / PR", "Trung bình", "Đích là bài viết"
    if lt == "Landing có form":
        if land.get("meta_pixel"):
            return "Lead / chuyển đổi trên web", "Trung bình", "Landing có form + Meta Pixel"
        return "Traffic → landing", "Thấp", "Landing có form nhưng không thấy Meta Pixel"
    if land and land.get("meta_pixel") and cta in ("SIGN_UP", "APPLY_NOW", "GET_OFFER", "DOWNLOAD"):
        return "Lead / chuyển đổi trên web", "Thấp", f"Nút {cta} + trang có Meta Pixel"
    return "Traffic → landing", "Thấp" if land else "Rất thấp", f"Nút {cta}, đích {lt or host}"


def _ascii_keep_case(s):
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", unicodedata.normalize("NFKC", s))
                   if unicodedata.category(c) != "Mn")


def _money(num, unit):
    v = float(num.replace(".", "").replace(",", "")) if re.fullmatch(r"\d{1,3}([.,]\d{3})+", num) else float(num.replace(",", "."))
    v *= {"k": 1e3, "nghin": 1e3, "ngan": 1e3, "trieu": 1e6, "tr": 1e6, "ty": 1e9}.get(unit, 1)
    if v < 1e4 or v > 5e7:  # bỏ số lẻ (giá cổ phiếu, mã…) và số quá lớn (hạn mức, quy mô, doanh thu)
        return None
    return f"{v / 1e6:g} triệu" if v >= 1e6 else f"{v / 1e3:g}K"


def extract_offers(r):
    """Trích con số ưu đãi trong caption: tiền thưởng, cổ phiếu tặng, % phí, % margin, hạn chương trình."""
    raw = _ascii_keep_case(ad_text(r))
    t = raw.lower()
    money = [m for m in (_money(a, b) for a, b in re.findall(
        r"(?:tang|nhan|thuong|hoan tien|qua|tri gia|len den)[^.\n]{0,25}?(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s?(k|nghin|ngan|trieu|tr|ty|d|dong|vnd)\b", t)) if m]
    # Dò trên chữ gốc (còn dấu) để "CỰC" không bị nhận thành mã "CUC"; [A-Z] chỉ khớp chữ ASCII
    orig = unicodedata.normalize("NFKC", ad_text(r))
    stocks = [x for x in re.findall(r"(?i:cổ phiếu|co phieu|\bcp)\s+([A-Z]{3})\b", orig) if x not in NOT_TICKERS]
    # Lãi margin thực tế < 30%/năm; "hoàn 100% lãi vay" không phải mức lãi
    margin = [x for x in re.findall(r"(?:margin|lai suat|lai vay)[^.%\n]{0,40}?(\d+(?:[.,]\d+)?)\s?%", t)
              if float(x.replace(",", ".")) < 30]
    # Phí giao dịch thực tế < 1%; "miễn 100% phí" đã được bắt ở dòng dưới thành 0%
    fee = [x for x in re.findall(r"phi(?: giao dich)?[^.%\n]{0,25}?(\d+(?:[.,]\d+)?)\s?%", t) if float(x.replace(",", ".")) < 1]
    if re.search(r"mien (100% )?phi giao dich|0 ?d? ?phi|phi (giao dich )?0\b|zero fee|khong phi", t):
        fee.append("0")
    deadline = re.findall(r"(?:den het|het han|ket thuc|truoc|den ngay)\s*(?:ngay\s*)?(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", t)
    uniq = lambda xs: list(dict.fromkeys(xs))
    pc = lambda x: x.replace(".", ",") + "%"  # thống nhất dấu thập phân kiểu Việt Nam
    return {"money": uniq(money)[:4], "stocks": uniq(stocks)[:4], "margin": uniq(pc(x) for x in margin)[:3],
            "fee": uniq(pc(x) for x in fee)[:3], "deadline": uniq(deadline)[:2]}


def offers_text(o):
    parts = []
    if o["money"]:
        parts.append("Tiền/quà " + ", ".join(o["money"]))
    if o["stocks"]:
        parts.append("Cổ phiếu " + ", ".join(o["stocks"]))
    if o["fee"]:
        parts.append("Phí " + ", ".join(o["fee"]))
    if o["margin"]:
        parts.append("Margin " + ", ".join(o["margin"]))
    if o["deadline"]:
        parts.append("Hạn " + ", ".join(o["deadline"]))
    return " · ".join(parts)


def load_landings(proj):
    f = Path(proj) / "landing" / "landings.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def enrich(rows, landings=None):
    landings = landings or {}
    for r in rows:
        r["format"] = FORMAT_LABELS.get(r["display_format"], r["display_format"] or "Khác")
        r["dest"] = destination(r)
        r["run_bucket"] = run_bucket(r["days_running"])
        t = norm(ad_text(r))
        r["signals"] = [k for k, rx in COPY_SIGNALS.items() if re.search(rx, t)]
        r["body_len"] = len(r["body"] or "")
        r["website"] = urlparse(r["link_url"]).netloc.replace("www.", "") if r["dest"] == "Website" else ""
        land = landings.get(r["link_url"]) or next((landings[u] for u in r.get("card_links") or [] if u in landings), None)
        r["landing"] = land
        r["final_url"] = (land or {}).get("final_url", "")
        r["landing_type"] = (land or {}).get("type", "")
        r["objective"], r["objective_confidence"], r["objective_reason"] = infer_objective(r, land)
        r["stage"] = OBJECTIVE_STAGE.get(r["objective"], "Cân nhắc")
        r["theme"] = r["signals"][0] if r["signals"] else "Khác"
        r["offers"] = extract_offers(r)
        r["offers_text"] = offers_text(r["offers"])


def pct(n, d):
    return 100 * n / d if d else 0


def short_name(label):
    # "Chứng khoán LPS (242 QC khớp)" → "Chứng khoán LPS"
    return re.sub(r"\s*\(.*$", "", label or "").strip()


def competitor_stats(rows, entries=None):
    """Mỗi fanpage 1 dòng. Có entries (từ competitors.txt) thì giữ thứ tự + nhóm trong file,
    kể cả fanpage đang không chạy QC nào; không có thì sắp theo số QC."""
    by = defaultdict(list)
    for r in rows:
        by[r["page_id"]].append(r)
    entries = entries or [{"pid": pid, "group": DEFAULT_GROUP, "label": ""} for pid in by]
    now = time.time()
    stats = []
    for order, e in enumerate(dict((e["pid"], e) for e in entries).values()):
        pid, rs = e["pid"], by.get(e["pid"], [])
        if not rs:
            stats.append({"page_id": pid, "page_name": short_name(e["label"]) or pid, "short": short_name(e["label"]) or pid,
                          "group": e["group"],
                          "order": order, "ads": 0, "rows": [], "page_url": f"https://facebook.com/{pid}"})
            continue
        for r in rs:
            r["group"] = e["group"]
        days = [r["days_running"] or 0 for r in rs]
        fmt = Counter(r["format"] for r in rs)
        dest = Counter(r["dest"] for r in rs)
        plat = Counter(p for r in rs for p in r["platforms"].split(",") if p)
        # Theo MẪU (collation): 1 mẫu = nhiều bản QC; ngày chạy của mẫu = bản chạy lâu nhất
        by_cre = defaultdict(list)
        for r in rs:
            by_cre[r.get("asset_id") or r["collation_id"]].append(r)
        cre_days = [max(x["days_running"] or 0 for x in v) for v in by_cre.values()]
        cre_copies = [len(v) for v in by_cre.values()]
        cre_first = [min((x["start_ts"] for x in v if x["start_ts"]), default=None) for v in by_cre.values()]
        stats.append({
            "page_id": pid,
            "group": e["group"],
            "order": order,
            "short": short_name(e["label"]) or rs[0]["page_name"],
            "page_name": rs[0]["page_name"],
            "page_url": rs[0]["page_url"],
            "likes": rs[0]["page_like_count"],
            "category": rs[0]["page_categories"],
            "ads": len(rs),
            "creatives": len(by_cre),
            "video_pct": pct(fmt.get("Video", 0), len(rs)),
            "formats": fmt,
            "median_days": statistics.median(days),
            "cre_median_days": statistics.median(cre_days),
            "cre_30d": sum(d >= 30 for d in cre_days),
            "cre_new_14d": sum(1 for t in cre_first if t and now - t < 14 * 86400),
            "avg_copies": len(rs) / len(by_cre),
            "max_days": max(days),
            "winners": sum(d >= 30 for d in days),
            "new_14d": sum(1 for r in rs if r["start_ts"] and now - r["start_ts"] < 14 * 86400),
            "top_dest": dest.most_common(1)[0][0],
            "dests": dest,
            "platforms": plat,
            "max_dup": max(cre_copies),
            "signals": Counter(s for r in rs for s in r["signals"]),
            "websites": Counter(r["website"] for r in rs if r["website"]),
            "objectives": Counter(r["objective"] for r in rs),
            "stages": Counter(r["stage"] for r in rs),
            "landing_types": Counter(r["landing_type"] or "(chưa mở)" for r in rs if r["link_url"]),
            "rows": rs,
        })
    groups = list(dict.fromkeys(e["group"] for e in entries))
    return sorted(stats, key=lambda s: (groups.index(s["group"]), -s["ads"] if len(groups) == 1 else s["order"]))


def winner_score(r):
    # Chạy càng lâu + càng được nhân bản nhiều → càng có khả năng là mẫu thắng
    return (r["days_running"] or 0) * (1 + math.log(r["collation_count"] or 1))


def esc(s):
    return html.escape(str(s if s is not None else ""))


def analyze(args):
    proj = Path(args.out) / args.project
    comp_file = Path(args.pages_file) if args.pages_file else proj / "competitors.txt"
    entries = [{"pid": p, "group": DEFAULT_GROUP, "label": ""} for p in args.page]
    entries += read_competitors(comp_file) if comp_file.exists() else []
    page_ids = [e["pid"] for e in entries]
    if not page_ids:
        raise SystemExit(f"Không có Page ID nào. Chạy discover trước hoặc truyền --page / --pages-file.")
    proj.mkdir(parents=True, exist_ok=True)
    load_project_signals(proj)

    rows = scrape_pages(dict.fromkeys(page_ids), proj, args)
    if not rows:
        raise SystemExit("Không cào được quảng cáo nào (đối thủ không chạy QC, hoặc bị Facebook chặn).")
    landings = load_landings(proj)
    enrich(rows, landings)
    if not args.no_probe:
        probe_videos(rows, args.probe_limit)
    import report_builder
    report_builder.assign_assets(rows, proj)
    stats = competitor_stats(rows, entries)

    with open(proj / "all_ads.csv", "w", newline="", encoding="utf-8-sig") as f:
        cols = ["group", "page_name", "ad_archive_id", "asset_id", "variant_id", "format", "aspect", "video_duration", "start_date", "days_running",
                "run_bucket", "collation_count", "platforms", "dest", "cta", "website", "signals", "objective", "objective_confidence", "stage", "offers_text",
                "title", "body", "link_url", "final_url", "landing_type", "library_link", "video_urls"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        order = {s["page_id"]: i for i, s in enumerate(stats)}
        for r in sorted(rows, key=lambda r: (order.get(r["page_id"], 99), -(r["days_running"] or 0))):
            w.writerow({**r, "signals": "; ".join(r["signals"]), "video_urls": " | ".join(r["video_urls"])})
    with open(proj / "competitors_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["group", "page_name", "page_id", "likes", "ads", "creatives", "video_%", "new_14d", "ads_30d+",
                    "median_days_per_ad", "median_days_per_creative", "creatives_30d+", "new_creatives_14d",
                    "avg_ads_per_creative", "max_days", "max_ads_per_creative", "top_destination", "top_objective"])
        for s in stats:
            if not s["ads"]:
                w.writerow([s["group"], s["page_name"], s["page_id"], "", 0])
                continue
            w.writerow([s["group"], s["page_name"], s["page_id"], s["likes"], s["ads"], s["creatives"], round(s["video_pct"]),
                        s["new_14d"], s["winners"], s["median_days"], s["cre_median_days"], s["cre_30d"], s["cre_new_14d"],
                        round(s["avg_copies"], 1), s["max_days"], s["max_dup"], s["top_dest"],
                        s["objectives"].most_common(1)[0][0]])

    report = proj / "report.html"
    report_builder.render(args.project, proj, rows, stats, has_landings=bool(landings), signal_keys=list(COPY_SIGNALS))
    if not landings:
        print(f"  (chưa có dữ liệu trang đích, chạy: python3 landing_crawl.py --project {args.project})")
    print(f"\n✔ {sum(1 for s in stats if s['ads'])} đối thủ đang chạy, {len(rows)} QC → {report}")


def main():
    ap = argparse.ArgumentParser(description="Tìm và phân tích quảng cáo đối thủ trên Meta Ad Library")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--project", required=True, help="Tên dự án, ví dụ tam-lop-poly")
        p.add_argument("--country", default="VN")
        p.add_argument("--max-scrolls", type=int, default=30)
        p.add_argument("--show-browser", action="store_true")
        p.add_argument("--out", default="projects")

    def disc_opts(p):
        p.add_argument("--keyword", action="append", required=True, help="Cụm từ khoá chính xác (lặp lại được)")
        p.add_argument("--match", help="Regex (không dấu) để giữ lại QC đúng ngành, ví dụ 'polycarbonate|tam lop|lay sang'")
        p.add_argument("--name-match", help="Regex (không dấu) cho TÊN fanpage để tự chọn đối thủ (mặc định = --match)")

    def ana_opts(p):
        p.add_argument("--page", action="append", default=[], help="Thêm Page ID thủ công")
        p.add_argument("--pages-file", help="Mặc định: projects/<project>/competitors.txt")
        p.add_argument("--refresh", action="store_true", help=f"Bỏ qua cache (mặc định cache {CACHE_HOURS} giờ)")
        p.add_argument("--no-probe", action="store_true", help="Không đo độ dài / tỉ lệ khung video")
        p.add_argument("--probe-limit", type=int, default=300)

    p1 = sub.add_parser("discover", help="Luồng 1: tìm đối thủ theo từ khoá")
    common(p1); disc_opts(p1)
    p2 = sub.add_parser("analyze", help="Luồng 2: phân tích QC của danh sách đối thủ")
    common(p2); ana_opts(p2)
    p3 = sub.add_parser("run", help="Chạy discover rồi analyze liền")
    common(p3); disc_opts(p3); ana_opts(p3)

    args = ap.parse_args()
    if args.cmd in ("discover", "run"):
        discover(args)
    if args.cmd in ("analyze", "run"):
        analyze(args)


if __name__ == "__main__":
    main()
