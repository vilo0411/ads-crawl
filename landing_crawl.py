"""
Mở link đích của các quảng cáo đã cào → biết QC dẫn về đâu.

Với mỗi URL (link chính + link từng card), ghi lại: URL cuối sau redirect, tiêu đề, loại trang
(App Store / Google Play / landing có form / bài viết / Google Form / Zalo / Facebook…),
có Meta Pixel / GTM không, và ảnh chụp màn hình bản mobile.

Chạy sau bước analyze (dùng lại cache projects/<project>/pages/):
    python3 landing_crawl.py --project chung-khoan
    python3 competitor_intel.py analyze --project chung-khoan   # dựng lại report có thông tin trang đích

Kết quả: projects/<project>/landing/landings.json + landing/<id>.jpg (cache 7 ngày)
"""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

CACHE_DAYS = 7
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1")
NEWS_HOSTS = ("cafef.vn", "tinnhanhchungkhoan.vn", "vnexpress.net", "vietstock.vn", "ndh.vn", "baodautu.vn",
              "vneconomy.vn", "znews.vn", "dantri.com.vn", "tuoitre.vn", "thanhnien.vn")


def url_id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def host_of(url):
    return urlparse(url or "").netloc.lower().replace("www.", "")


def page_type(final, has_form, is_article):
    h, path = host_of(final), urlparse(final or "").path.lower()
    scheme = (final or "").split(":", 1)[0].lower()
    if "play.google.com" in h or scheme in ("market", "intent"):
        return "Google Play"
    if "apps.apple.com" in h or "itunes.apple.com" in h or scheme.startswith("itms"):
        return "App Store"
    if "forms.gle" in h or ("docs.google.com" in h and "/forms" in path):
        return "Google Form"
    if "zalo.me" in h or "zalo" in scheme:
        return "Zalo"
    if scheme in ("fb", "fb-messenger"):
        return "Messenger" if "messenger" in scheme else "Trang Facebook"
    if scheme not in ("http", "https", ""):
        return "Mở app (deep link)"
    if "zoom.us" in h and "webinar" in path:
        return "Đăng ký webinar (Zoom)"
    if h in ("m.me", "messenger.com") or "messenger" in path:
        return "Messenger"
    if h.endswith("facebook.com") or h in ("fb.com", "fb.me"):
        return "Trang Facebook"
    if not h:
        return "Không mở được"
    if is_article or any(h.endswith(n) for n in NEWS_HOSTS):
        return "Bài viết / PR"
    if has_form:
        return "Landing có form"
    return "Trang thông tin / sản phẩm"


PROBE_JS = """() => {
  const q = s => document.querySelector(s);
  const inputs = [...document.querySelectorAll('input:not([type=hidden]):not([type=search]), textarea, select')];
  const lead = inputs.filter(i => /tel|phone|sdt|dien|email|mail|ho_?ten|name|ten/i.test(
      (i.type||'')+' '+(i.name||'')+' '+(i.id||'')+' '+(i.placeholder||''))).length;
  const words = (document.body ? document.body.innerText : '').split(/\\s+/).length;
  return {
    title: document.title || '',
    h1: (q('h1') && q('h1').innerText || '').trim().slice(0, 200),
    desc: (q('meta[name=description]') || q('meta[property="og:description"]') || {}).content || '',
    has_form: lead >= 1 || inputs.length >= 3,
    is_article: !!q('article') && words > 400,
    words,
  };
}"""


def crawl(urls, out_dir, headless=True):
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(user_agent=MOBILE_UA, locale="vi-VN", is_mobile=True, has_touch=True,
                                  viewport={"width": 390, "height": 844}, device_scale_factor=2)
        for i, url in enumerate(urls, 1):
            page = ctx.new_page()
            navs, scripts = [], []
            page.on("framenavigated", lambda f: f == page.main_frame and navs.append(f.url))
            page.on("request", lambda r: scripts.append(r.url) if r.resource_type in ("script", "image", "xhr", "fetch", "ping") else None)
            # Deep link mở app (itms-apps://, intent://…) làm trình duyệt báo lỗi: ghi lại địa chỉ đó làm URL cuối
            blocked = []
            page.on("requestfailed", lambda r: blocked.append(r.url) if r.is_navigation_request() else None)
            info, error = {}, ""
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3500)
                info = page.evaluate(PROBE_JS)
            except Exception as e:
                error = str(e).splitlines()[0][:200]
            final = page.url if page.url not in ("about:blank", "") else ""
            for b in blocked:
                if not b.startswith("http"):
                    final = b
            final = final or (navs[-1] if navs else url)
            html_blob = " ".join(scripts)
            try:
                html_blob += page.content()
            except Exception:
                pass
            shot = ""
            if final.startswith("http"):
                try:
                    dest = out_dir / f"{url_id(url)}.jpg"
                    page.screenshot(path=str(dest), type="jpeg", quality=60)
                    shot = dest.name
                except Exception:
                    pass
            results[url] = {
                "url": url,
                "final_url": final,
                "final_host": host_of(final) or final.split(":", 1)[0],
                "redirected": host_of(final) != host_of(url),
                "title": (info.get("title") or "").strip()[:200],
                "h1": info.get("h1", ""),
                "description": (info.get("desc") or "").strip()[:300],
                "type": page_type(final, info.get("has_form"), info.get("is_article")),
                "has_form": bool(info.get("has_form")),
                "meta_pixel": bool(re.search(r"connect\.facebook\.net|facebook\.com/tr[/?]|fbq\(", html_blob)),
                "gtm": "googletagmanager.com" in html_blob,
                "tiktok_pixel": "analytics.tiktok.com" in html_blob,
                "utm": "utm_" in url,
                "screenshot": shot,
                "error": error,
                "checked_at": time.time(),
            }
            r = results[url]
            print(f"  [{i}/{len(urls)}] {r['type']:<26} {r['final_host'][:40]:<40} ← {url[:70]}")
            page.close()
        browser.close()
    return results


def collect_urls(proj):
    urls = []
    for f in sorted((proj / "pages").glob("*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            urls += [r.get("link_url")] + (r.get("card_links") or [])
    return [u for u in dict.fromkeys(urls) if u and u.startswith("http")]


def main():
    ap = argparse.ArgumentParser(description="Mở link đích của quảng cáo đã cào")
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", default="projects")
    ap.add_argument("--refresh", action="store_true", help=f"Bỏ qua cache {CACHE_DAYS} ngày")
    ap.add_argument("--show-browser", action="store_true")
    args = ap.parse_args()

    proj = Path(args.out) / args.project
    if not (proj / "pages").exists():
        raise SystemExit(f"Chưa có dữ liệu. Chạy trước: python3 competitor_intel.py analyze --project {args.project}")
    out_dir = proj / "landing"
    out_dir.mkdir(exist_ok=True)
    store = out_dir / "landings.json"
    known = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}

    urls = collect_urls(proj)
    fresh = time.time() - CACHE_DAYS * 86400
    todo = [u for u in urls if args.refresh or known.get(u, {}).get("checked_at", 0) < fresh]
    print(f"{len(urls)} link đích, cần mở {len(todo)} link (còn lại dùng cache)")
    if todo:
        known.update(crawl(todo, out_dir, not args.show_browser))
    store.write_text(json.dumps(known, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✔ {store}")


if __name__ == "__main__":
    main()
