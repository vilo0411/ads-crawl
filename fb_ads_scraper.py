"""
Cào video quảng cáo của đối thủ từ Meta Ad Library (facebook.com/ads/library).

Cách dùng:
    python3 fb_ads_scraper.py --page 123456789012345            # theo Page ID
    python3 fb_ads_scraper.py --page 111 --page 222              # nhiều fanpage
    python3 fb_ads_scraper.py --keyword "serum vitamin c"        # theo từ khoá
    python3 fb_ads_scraper.py --pages-file competitors.txt       # mỗi dòng 1 Page ID
    python3 fb_ads_scraper.py --page 111 --no-download           # chỉ lấy metadata

Kết quả nằm trong ./output/<tên>/: ads.json, ads.csv và thư mục videos/.
"""

import argparse
import csv
import json
import random
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

LIBRARY_URL = "https://www.facebook.com/ads/library/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)


def build_url(country, page_id=None, keyword=None, active_only=True, media_type="video", exact=False):
    params = {
        "active_status": "active" if active_only else "all",
        "ad_type": "all",
        "country": country,
        "media_type": media_type,
    }
    if page_id:
        params["view_all_page_id"] = page_id
        params["search_type"] = "page"
    else:
        params["q"] = keyword
        params["search_type"] = "keyword_exact_phrase" if exact else "keyword_unordered"
    return LIBRARY_URL + "?" + urllib.parse.urlencode(params)


def walk_for_ads(obj, found):
    """Duyệt đệ quy JSON, gom mọi object có ad_archive_id + snapshot."""
    if isinstance(obj, dict):
        if "ad_archive_id" in obj and isinstance(obj.get("snapshot"), dict):
            found[str(obj["ad_archive_id"])] = obj
        for v in obj.values():
            walk_for_ads(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk_for_ads(v, found)


def parse_json_blob(text, found):
    # Response GraphQL của FB có thể chứa nhiều JSON nối nhau theo từng dòng
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("for (;;);"):
            line = line[len("for (;;);"):]
        if not line.startswith("{"):
            continue
        try:
            walk_for_ads(json.loads(line), found)
        except json.JSONDecodeError:
            continue


def extract_videos(snapshot):
    videos = []
    for v in snapshot.get("videos") or []:
        videos.append(v)
    for card in snapshot.get("cards") or []:
        if card.get("video_hd_url") or card.get("video_sd_url"):
            videos.append(card)
    out = []
    for v in videos:
        url = v.get("video_hd_url") or v.get("video_sd_url")
        if url:
            out.append({"url": url, "preview": v.get("video_preview_image_url")})
    return out


def text_of(field):
    if isinstance(field, dict):
        return field.get("text") or ""
    return field or ""


def to_row(ad):
    s = ad["snapshot"]
    start, end = ad.get("start_date"), ad.get("end_date")
    days = None
    if start:
        days = int(((end if end and not ad.get("is_active") else time.time()) - start) // 86400)
    return {
        "ad_archive_id": ad["ad_archive_id"],
        "page_id": ad.get("page_id") or s.get("page_id"),
        "page_name": ad.get("page_name") or s.get("page_name"),
        "is_active": ad.get("is_active"),
        "start_date": time.strftime("%Y-%m-%d", time.localtime(start)) if start else "",
        "days_running": days,
        "platforms": ",".join(ad.get("publisher_platform") or []),
        "collation_count": ad.get("collation_count"),
        "body": text_of(s.get("body")),
        "title": s.get("title") or "",
        "cta": s.get("cta_text") or "",
        "link_url": s.get("link_url") or "",
        "video_urls": [v["url"] for v in extract_videos(s)],
        "library_link": f"https://www.facebook.com/ads/library/?id={ad['ad_archive_id']}",
        # Các trường dưới đây phục vụ phân tích (competitor_intel.py)
        "display_format": s.get("display_format") or "",
        "cta_type": s.get("cta_type") or "",
        "collation_id": ad.get("collation_id") or ad["ad_archive_id"],
        "page_like_count": s.get("page_like_count"),
        "page_categories": ",".join(s.get("page_categories") or []),
        "page_url": s.get("page_profile_uri") or "",
        "link_description": text_of(s.get("link_description")),
        "n_images": len(s.get("images") or []),
        "n_cards": len(s.get("cards") or []),
        "start_ts": start,
        "end_ts": end,
        "thumbnail": first_thumbnail(s),
        "categories": ",".join(ad.get("categories") or []),
        "page_is_deleted": ad.get("page_is_deleted"),
        # Link đích riêng của từng card (carousel / DCO) và link phụ
        "card_links": list(dict.fromkeys(c["link_url"] for c in s.get("cards") or [] if c.get("link_url"))),
        "extra_links": [x for x in s.get("extra_links") or [] if isinstance(x, str)],
    }


def first_thumbnail(s):
    for v in extract_videos(s):
        if v["preview"]:
            return v["preview"]
    for img in (s.get("images") or []) + (s.get("cards") or []):
        url = img.get("resized_image_url") or img.get("original_image_url") or img.get("video_preview_image_url")
        if url:
            return url
    return ""


def scrape(url, max_scrolls, headless):
    found = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(user_agent=USER_AGENT, locale="vi-VN",
                                  viewport={"width": 1366, "height": 900})
        page = ctx.new_page()

        def on_response(resp):
            if "/api/graphql" in resp.url:
                try:
                    parse_json_blob(resp.text(), found)
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        # Lô quảng cáo đầu tiên được nhúng sẵn trong HTML, không qua GraphQL
        for blob in page.locator('script[type="application/json"]').all_text_contents():
            if "ad_archive_id" in blob:
                parse_json_blob(blob, found)

        stale = 0
        for i in range(max_scrolls):
            before = len(found)
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(random.randint(1800, 3200))
            print(f"  cuộn {i + 1}/{max_scrolls}: {len(found)} quảng cáo")
            stale = stale + 1 if len(found) == before else 0
            if stale >= 4:  # 4 lần cuộn liền không có gì mới thì coi như hết
                break
        browser.close()
    return list(found.values())


def download(url, dest):
    # Dùng curl thay urllib: Python cài từ python.org trên macOS hay thiếu chứng chỉ SSL
    tmp = dest.with_suffix(".part")
    subprocess.run(["curl", "-sSfL", "--max-time", "300", "-A", USER_AGENT, "-o", str(tmp), url],
                   check=True, capture_output=True, text=True)
    tmp.rename(dest)


def safe_name(s):
    return re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")[:60] or "ads"


def run_target(label, url, args):
    print(f"\n▶ {label}\n  {url}")
    ads = scrape(url, args.max_scrolls, not args.show_browser)
    rows = [to_row(a) for a in ads]
    rows = [r for r in rows if r["video_urls"]] if args.video_only else rows
    rows.sort(key=lambda r: r["days_running"] or 0, reverse=True)

    # Tìm theo fanpage thì đặt tên thư mục theo tên page; theo từ khoá thì giữ nhãn kw_
    page_name = next((r["page_name"] for r in rows if r["page_name"]), None)
    out = Path(args.out) / safe_name(page_name if label.startswith("page_") and page_name else label)
    out.mkdir(parents=True, exist_ok=True)

    (out / "ads.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "ads.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["ad_archive_id"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "video_urls": " | ".join(r["video_urls"])})

    print(f"  → {len(rows)} quảng cáo có video, lưu tại {out}")

    if args.no_download:
        return
    vdir = out / "videos"
    vdir.mkdir(exist_ok=True)
    for r in rows:
        for i, vurl in enumerate(r["video_urls"]):
            dest = vdir / f"{r['days_running'] or 0:04d}d_{r['ad_archive_id']}_{i}.mp4"
            if dest.exists():
                continue
            try:
                download(vurl, dest)
                print(f"  ✓ {dest.name}")
            except Exception as e:
                print(f"  ✗ {r['ad_archive_id']}: {e}")
            time.sleep(random.uniform(0.5, 1.5))


def main():
    ap = argparse.ArgumentParser(description="Cào video quảng cáo từ Meta Ad Library")
    ap.add_argument("--page", action="append", default=[], help="Page ID của fanpage (lặp lại được)")
    ap.add_argument("--pages-file", help="File txt, mỗi dòng 1 Page ID")
    ap.add_argument("--keyword", action="append", default=[], help="Từ khoá tìm kiếm (lặp lại được)")
    ap.add_argument("--country", default="VN", help="Mã quốc gia, mặc định VN (ALL = mọi nước)")
    ap.add_argument("--max-scrolls", type=int, default=30)
    ap.add_argument("--all-media", dest="video_only", action="store_false",
                    help="Lấy cả quảng cáo ảnh, không chỉ video")
    ap.add_argument("--no-download", action="store_true", help="Chỉ lưu metadata, không tải video")
    ap.add_argument("--show-browser", action="store_true", help="Hiện cửa sổ trình duyệt để theo dõi")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    pages = list(args.page)
    if args.pages_file:
        pages += [l.strip() for l in open(args.pages_file, encoding="utf-8")
                  if l.strip() and not l.startswith("#")]
    if not pages and not args.keyword:
        ap.error("Cần ít nhất --page, --pages-file hoặc --keyword")

    media = "video" if args.video_only else "all"
    for pid in pages:
        run_target(f"page_{pid}", build_url(args.country, page_id=pid, media_type=media), args)
    for kw in args.keyword:
        run_target(f"kw_{kw}", build_url(args.country, keyword=kw, media_type=media), args)


if __name__ == "__main__":
    main()
