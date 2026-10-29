"""
Phân tích quảng cáo Google Ads của đối thủ qua Google Ads Transparency Center (adstransparency.google.com).

Không cần trình duyệt, không cần đăng nhập: script gọi thẳng API nội bộ mà trang web dùng.

  1) discover: tìm nhà quảng cáo (mã AR…) theo tên công ty và/hoặc domain website
  2) analyze : lấy toàn bộ creative của từng nhà quảng cáo → report_google.html + CSV

Ví dụ (ngành chứng khoán):
    python3 google_ads_intel.py discover --project chung-khoan \
        --keyword "chứng khoán" --keyword "securities" --domain ssi.com.vn --domain vps.com.vn \
        --name-match "chung khoan|securities"

    # Mở projects/chung-khoan/google_competitors.txt, sửa tay, rồi:
    python3 google_ads_intel.py analyze --project chung-khoan

Lưu ý: đây là API nội bộ, Google có thể đổi bất kỳ lúc nào. Google KHÔNG công bố từ khoá,
ngân sách, lượt hiển thị hay nhắm mục tiêu; nội dung chữ của QC Search chỉ có dạng ảnh chụp.
"""

import argparse
import csv
import html
import json
import random
import re
import statistics
import subprocess
import time
import urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import competitor_intel as ci

API = "https://adstransparency.google.com/anji/_/rpc/"
UI = "https://adstransparency.google.com"
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
CACHE_HOURS = 12
ACTIVE_DAYS = 3  # QC có lần hiển thị cuối trong 3 ngày gần đây = đang chạy

# Mã vùng Google (geo target id)
REGIONS = {"VN": 2704, "US": 2840, "TH": 2764, "ID": 2360, "SG": 2702, "MY": 2458, "PH": 2608}
FORMATS = {1: "Chữ (Search)", 2: "Ảnh", 3: "Video"}
# Mã nền tảng lấy từ request của chính trang web (?platform=…)
PLATFORMS = {3: "Search", 5: "YouTube", 1: "Play", 2: "Maps", 4: "Shopping"}
OTHER = "Display/khác"
PLATFORM_ORDER = list(PLATFORMS.values())


# ───────────────────────── API ─────────────────────────

class Blocked(RuntimeError):
    pass


class BrowserSession:
    """Gọi API trong một cửa sổ Chromium thật (--browser). Nếu Google hiện captcha, NGƯỜI DÙNG tự giải
    trong cửa sổ đó; script chỉ chờ. Hồ sơ trình duyệt được giữ lại để lần sau đỡ phải giải lại."""

    PROFILE = Path.home() / ".cache" / "ads-crawl" / "google-profile"

    def __init__(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.ctx = self.pw.chromium.launch_persistent_context(
            str(self.PROFILE), headless=False, locale="vi-VN", viewport={"width": 1200, "height": 850})
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.ensure_access()

    def ensure_access(self, minutes=10):
        self.page.goto(f"{UI}/?region=VN", wait_until="domcontentloaded", timeout=60000)
        if "google.com/sorry" not in self.page.url:
            return
        print(f"\n⚠ Google đang hiện captcha trong cửa sổ Chromium vừa mở. Hãy tự giải nó (chờ tối đa {minutes} phút)…")
        self.page.bring_to_front()
        subprocess.run(["osascript", "-e", 'display notification "Mở cửa sổ Chromium và giải captcha để script chạy tiếp" '
                        'with title "Google Ads Transparency" sound name "Glass"'], capture_output=True)
        deadline = time.time() + minutes * 60
        while time.time() < deadline:
            self.page.wait_for_timeout(3000)
            if self.page.url.startswith(UI):
                print("  ✓ Đã qua captcha, tiếp tục.")
                self.page.wait_for_timeout(3000)
                return
        raise Blocked("Hết thời gian chờ giải captcha.")

    def post(self, method, body):
        return self.page.evaluate(
            """async ([url, body]) => {
                const r = await fetch(url, {method: 'POST', body, redirect: 'manual', credentials: 'include',
                    headers: {'content-type': 'application/x-www-form-urlencoded'}});
                return [r.type === 'opaqueredirect' ? 302 : r.status, r.status === 200 ? await r.text() : ''];
            }""", [f"{API}{method}?authuser=0", body])

    def close(self):
        self.ctx.close()
        self.pw.stop()


BROWSER = None  # BrowserSession khi chạy với --browser


def rpc(method, req, retries=3):
    body = urllib.parse.urlencode({"f.req": json.dumps(req, ensure_ascii=False)})
    if BROWSER:
        for attempt in range(retries):
            code, text = BROWSER.post(method, body)
            if code == 200:
                time.sleep(random.uniform(2, 4))
                return json.loads(text or "{}")
            if code == 302:
                BROWSER.ensure_access()
                continue
            print(f"  ! {method} HTTP {code}, thử lại sau {10 * (attempt + 1)}s")
            time.sleep(10 * (attempt + 1))
        raise RuntimeError(f"{method} lỗi liên tục")
    for attempt in range(retries):
        out = subprocess.run(
            ["curl", "-sS", "--max-time", "60", "-A", USER_AGENT, "-X", "POST", f"{API}{method}?authuser=0",
             "-H", "content-type: application/x-www-form-urlencoded", "-H", f"origin: {UI}", "-H", f"referer: {UI}/",
             "--data-binary", body, "-w", "\n%{http_code} %{redirect_url}"],
            capture_output=True, text=True)
        text, _, status = out.stdout.rpartition("\n")
        code, _, redirect = status.partition(" ")
        if code == "200":
            # Nghỉ 2–4 giây mỗi lần gọi: gọi dồn dập sẽ bị đẩy sang trang captcha google.com/sorry
            time.sleep(random.uniform(2, 4))
            return json.loads(text or "{}")
        if "google.com/sorry" in redirect:
            raise Blocked("Google tạm chặn IP này (trang captcha /sorry). Đợi 30–60 phút hoặc đổi mạng rồi chạy lại; "
                          "phần đã lấy được nằm trong cache.")
        wait = 10 * (attempt + 1)
        print(f"  ! {method} HTTP {code or out.stderr.strip()}, thử lại sau {wait}s")
        time.sleep(wait)
    raise RuntimeError(f"{method} lỗi liên tục")


def cached(path, fn):
    """Lưu kết quả từng truy vấn discover, để chạy lại sau khi bị chặn không phải gọi lại từ đầu."""
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_HOURS * 3600:
        return json.loads(path.read_text(encoding="utf-8"))
    data = fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def suggest(query, region):
    """Gợi ý nhà quảng cáo theo tên → [{id, name, country, creatives}]"""
    d = rpc("SearchService/SearchSuggestions", {"1": query, "2": 30, "3": 30})
    out = []
    for item in d.get("1") or []:
        a = item.get("1")
        if not a:
            continue  # gợi ý dạng domain
        n = ((a.get("4") or {}).get("2") or {}).get("2")
        out.append({"id": a["2"], "name": a["1"], "country": a.get("3", ""), "creatives": int(n or 0)})
    return out


def search_creatives(region, advertiser=None, domain=None, platform=None, max_items=2000):
    """Duyệt hết các trang kết quả, trả về danh sách creative thô."""
    flt = {"8": [region]}
    if advertiser:
        flt["13"] = {"1": [advertiser]}
    if domain:
        flt["12"] = {"1": domain, "2": True}
    if platform:
        flt["14"] = [platform]
    req = {"2": 100, "3": flt, "7": {"1": 1, "2": 0, "3": region}}
    items, token = [], None
    while len(items) < max_items:
        if token:
            req["4"] = token
        d = rpc("SearchService/SearchCreatives", req)
        items += d.get("1") or []
        token = d.get("2")
        if not token or not d.get("1"):
            break
    return items[:max_items]


def ts(field):
    return int((field or {}).get("1") or 0)


def preview_of(c):
    """(kiểu, giá trị): ảnh tĩnh simgad hoặc link content.js cần mở thêm."""
    p = c.get("3") or {}
    m = re.search(r'src="([^"]+)"', (p.get("3") or {}).get("2") or "")
    if m:
        return "img", m.group(1)
    if (p.get("1") or {}).get("4"):
        return "js", p["1"]["4"]
    return "", ""


def to_row(c, label, group):
    first, last = ts(c.get("6")), ts(c.get("7"))
    kind, prev = preview_of(c)
    return {
        "group": group,
        "competitor": label,
        "advertiser_id": c["1"],
        "advertiser_name": c.get("12", ""),
        "creative_id": c["2"],
        "format": FORMATS.get(c.get("4"), "Khác"),
        "first_shown": time.strftime("%Y-%m-%d", time.localtime(first)) if first else "",
        "last_shown": time.strftime("%Y-%m-%d", time.localtime(last)) if last else "",
        "first_ts": first,
        "last_ts": last,
        "days_shown": int(c.get("13") or 0),
        "span_days": (last - first) // 86400 if first and last else 0,
        "domain": c.get("14", ""),
        "image_url": prev if kind == "img" else "",
        "preview_js": prev if kind == "js" else "",
        "youtube_id": "",
        "video_title": "",
        "platforms": "",
        "link": f"{UI}/advertiser/{c['1']}/creative/{c['2']}?region=VN",
    }


# ───────────────────────── Bổ sung chi tiết ─────────────────────────

def fetch(url, timeout=40):
    out = subprocess.run(["curl", "-sSL", "--max-time", str(timeout), "-A", USER_AGENT, url],
                         capture_output=True, text=True)
    return out.stdout


def resolve_preview(r):
    """Mở content.js: lấy ID video YouTube, hoặc ảnh của QC HTML5."""
    if not r["preview_js"] or r["youtube_id"] or r["image_url"]:
        return r
    js = fetch(r["preview_js"])
    m = re.search(r"ytimg\.com/vi/([\w-]{11})", js) or re.search(r"youtube\.com/(?:embed|watch\?v=)/?([\w-]{11})", js)
    if m:
        r["youtube_id"] = m.group(1)
    else:
        img = re.search(r"(https://tpc\.googlesyndication\.com/(?:archive/)?simgad/\d+)", js.replace("\\/", "/"))
        r["image_url"] = img.group(1) if img else ""
    return r


def video_title(vid):
    try:
        d = json.loads(fetch(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json", 20))
        return d.get("title", "")
    except Exception:
        return ""


def thumb(r):
    if r["youtube_id"]:
        return f"https://i.ytimg.com/vi/{r['youtube_id']}/hqdefault.jpg"
    return r["image_url"]


# ───────────────────────── Luồng 1: discover ─────────────────────────

def discover(args):
    proj = Path(args.out) / args.project
    proj.mkdir(parents=True, exist_ok=True)
    region = REGIONS[args.country]
    found = {}

    def add(a, via):
        e = found.setdefault(a["id"], {**a, "via": set()})
        e["creatives"] = max(e["creatives"], a.get("creatives", 0))
        e["via"].add(via)

    qdir = proj / "google" / "discover"
    for kw in args.keyword:
        print(f"▶ Tên: {kw}")
        for a in cached(qdir / f"name_{ci.norm(kw).replace(' ', '_')}.json", lambda: suggest(kw, region)):
            if a["country"] in ("", args.country):
                add(a, f"tên: {kw}")
    for dom in args.domain:
        print(f"▶ Domain: {dom}")
        per = Counter()
        names = {}
        for c in cached(qdir / f"domain_{dom}.json", lambda: search_creatives(region, domain=dom, max_items=200)):
            per[c["1"]] += 1
            names[c["1"]] = c.get("12", "")
        for aid, n in per.items():
            add({"id": aid, "name": names[aid], "country": "", "creatives": n}, f"domain: {dom}")

    name_rx = re.compile(ci.norm(args.name_match)) if args.name_match else None
    ranked = sorted(found.values(), key=lambda a: (not (name_rx and name_rx.search(ci.norm(a["name"]))), -a["creatives"]))
    with open(proj / "google_competitors.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["advertiser_id", "name", "country", "creatives", "found_via"])
        for a in ranked:
            w.writerow([a["id"], a["name"], a["country"], a["creatives"], "; ".join(sorted(a["via"]))])
    with open(proj / "google_competitors.txt", "w", encoding="utf-8") as f:
        f.write("# Mỗi dòng 1 mã nhà quảng cáo (AR…) + '# Tên ngắn'. Các mã cùng tên ngắn được gộp làm 1 đối thủ.\n"
                "# Dòng '#@ Tên nhóm' mở nhóm mới. Dòng có # đứng đầu bị bỏ qua.\n\n")
        for a in ranked:
            on = bool(name_rx and name_rx.search(ci.norm(a["name"])))
            f.write(f"{'' if on else '# '}{a['id']}  # {a['name']} ({a['creatives']} creative, {a['country'] or '?'})\n")
    print(f"\n✔ {len(ranked)} nhà quảng cáo → {proj / 'google_competitors.txt'} (sửa tay rồi chạy analyze)")


# ───────────────────────── Luồng 2: analyze ─────────────────────────

def tag_platforms(rows, aid, region, args):
    """Gắn nhãn nền tảng: mỗi nền tảng 1 lượt lọc. Chỉ gọi những nền tảng chưa có trong cache."""
    by_id = {r["creative_id"]: r for r in rows}
    for code, name in PLATFORMS.items():
        todo = [r for r in rows if code not in r.setdefault("plat_checked", [])]
        if not todo:
            continue
        for c in search_creatives(region, advertiser=aid, platform=code, max_items=args.max_creatives):
            r = by_id.get(c["2"])
            if r and name not in r.setdefault("plat_list", []):
                r["plat_list"].append(name)
        for r in todo:
            r["plat_checked"].append(code)
    for r in rows:
        # Không thuộc nền tảng nào trong bộ lọc = mạng hiển thị (GDN) / đối tác
        r["platforms"] = ",".join(sorted(r.get("plat_list") or [], key=PLATFORM_ORDER.index) or [OTHER])


def scrape_advertiser(aid, label, group, proj, args, region):
    cache = proj / "google" / f"{aid}.json"
    if not aid.startswith("AR"):
        return []
    offline = getattr(args, "offline", False)
    if offline and not cache.exists():
        print(f"▶ {label} ({aid}): chưa có cache, bỏ qua")
        return []
    if cache.exists() and (offline or not args.refresh and time.time() - cache.stat().st_mtime < CACHE_HOURS * 3600):
        rows = json.loads(cache.read_text(encoding="utf-8"))
        print(f"▶ {label} ({aid}): dùng cache ({len(rows)} creative)")
        for r in rows:
            r["competitor"], r["group"] = label, group
            if "plat_checked" not in r:  # cache cũ chỉ có Search / YouTube
                r["plat_list"] = [x for x in r["platforms"].split(",") if x in PLATFORM_ORDER]
                r["plat_checked"] = [3, 5]
        if not offline and any(len(r["plat_checked"]) < len(PLATFORMS) for r in rows):
            print("  bổ sung nhãn nền tảng còn thiếu…")
            tag_platforms(rows, aid, region, args)
            cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return rows

    print(f"▶ {label} ({aid})")
    rows = [to_row(c, label, group) for c in search_creatives(region, advertiser=aid, max_items=args.max_creatives)]
    print(f"  {len(rows)} creative", end="", flush=True)
    tag_platforms(rows, aid, region, args)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(resolve_preview, [r for r in rows if r["preview_js"]]))
    vids = {r["youtube_id"] for r in rows if r["youtube_id"]}
    with ThreadPoolExecutor(8) as ex:
        titles = dict(zip(vids, ex.map(video_title, vids)))
    for r in rows:
        r["video_title"] = titles.get(r["youtube_id"], "")
    print(f", {len(vids)} video YouTube")
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def enrich(rows, now):
    for r in rows:
        r["active"] = now - r["last_ts"] < ACTIVE_DAYS * 86400
        r["new_14d"] = now - r["first_ts"] < 14 * 86400
        r["run_bucket"] = ci.run_bucket(r["days_shown"])
        t = ci.norm(r["video_title"])
        r["signals"] = [k for k, rx in ci.COPY_SIGNALS.items() if t and re.search(rx, t)]


def comp_stats(rows, order):
    by = defaultdict(list)
    for r in rows:
        by[r["competitor"]].append(r)
    stats = []
    for label, group in order:
        rs = by.get(label, [])
        act = [r for r in rs if r["active"]]
        days = [r["days_shown"] for r in rs] or [0]
        stats.append({
            "label": label, "group": group, "rows": rs, "total": len(rs), "active": len(act),
            "accounts": sorted({r["advertiser_id"] for r in rs}),
            "new_14d": sum(r["new_14d"] for r in rs),
            "new_30d": sum(1 for r in rs if time.time() - r["first_ts"] < 30 * 86400),
            "formats": Counter(r["format"] for r in act or rs),
            "platforms": Counter(p for r in act or rs for p in r["platforms"].split(",") if p),
            "median_days": statistics.median(days), "max_days": max(days),
            "winners": sum(d >= 30 for d in days),
            "videos": len({r["youtube_id"] for r in rs if r["youtube_id"]}),
            "domains": Counter(r["domain"] for r in rs if r["domain"]),
            "last": max((r["last_ts"] for r in rs), default=0),
        })
    return stats


def weekly_new(rows, weeks=12):
    now = time.time()
    out = Counter()
    for r in rows:
        w = int((now - r["first_ts"]) // (7 * 86400))
        if 0 <= w < weeks:
            out[w] += 1
    return [out[w] for w in reversed(range(weeks))]


def analyze(args):
    proj = Path(args.out) / args.project
    comp_file = proj / "google_competitors.txt"
    if not comp_file.exists():
        raise SystemExit(f"Chưa có {comp_file}. Chạy discover trước.")
    ci.load_project_signals(proj)
    region = REGIONS[args.country]
    entries = ci.read_competitors(comp_file)
    order = list(dict.fromkeys((ci.short_name(e["label"]) or e["pid"], e["group"]) for e in entries))
    rows = []
    for e in entries:
        rows += scrape_advertiser(e["pid"], ci.short_name(e["label"]) or e["pid"], e["group"], proj, args, region)
    if not rows:
        raise SystemExit("Không lấy được creative nào.")
    now = time.time()
    enrich(rows, now)
    stats = comp_stats(rows, order)

    cols = ["group", "competitor", "advertiser_name", "advertiser_id", "creative_id", "format", "platforms", "active",
            "first_shown", "last_shown", "days_shown", "span_days", "run_bucket", "domain", "youtube_id", "video_title",
            "signals", "image_url", "link"]
    with open(proj / "google_all_ads.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["competitor"], -r["days_shown"])):
            w.writerow({**r, "signals": "; ".join(r["signals"]),
                        "youtube_id": f"https://youtu.be/{r['youtube_id']}" if r["youtube_id"] else ""})
    with open(proj / "google_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["group", "competitor", "accounts", "creatives_total", "active_now", "new_14d", "new_30d",
                    "ads_30d+", "median_days", "max_days", "youtube_videos"] + [f"active_on_{p}" for p in PLATFORM_ORDER + [OTHER]])
        for s in stats:
            w.writerow([s["group"], s["label"], len(s["accounts"]), s["total"], s["active"], s["new_14d"], s["new_30d"],
                        s["winners"], s["median_days"], s["max_days"], s["videos"]] +
                       [sum(1 for r in s["rows"] if r["active"] and pl in r["platforms"].split(","))
                        for pl in PLATFORM_ORDER + [OTHER]])

    out = proj / "report_google.html"
    import google_report  # import muộn: google_report cần các hằng số của module này
    google_report.download_images(proj, rows)
    if BROWSER:
        render_previews(proj, rows)
    out.write_text(google_report.render(args.project, proj, rows, stats, google_report.load_notes(proj)), encoding="utf-8")
    print(f"\n✔ {sum(1 for s in stats if s['total'])} đối thủ có QC Google, {len(rows)} creative "
          f"({sum(r['active'] for r in rows)} đang chạy) → {out}")


def serve(proj, port):
    """YouTube không cho phát video nhúng trong trang mở từ file:// (lỗi 153), nên phục vụ thư mục project qua localhost."""
    import functools
    import http.server
    import webbrowser
    if not (proj / "report_google.html").exists():
        raise SystemExit(f"Chưa có {proj / 'report_google.html'}. Chạy analyze hoặc report trước.")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(proj))
    handler.log_message = lambda *a: None
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://localhost:{port}/report_google.html"
        print(f"Đang mở {url}  (Ctrl+C để tắt)")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def html_route(body):
    # Playwright truyền (route, request) cho handler có 2 tham số, nên body phải nằm trong closure
    return lambda route: route.fulfill(status=200, content_type="text/html", body=body)


def render_previews(proj, rows):
    """QC không có ảnh tĩnh (QC chữ dạng HTML, QC app…) chỉ có script content.js, script này vẽ QC vào iframe /adframe
    của chính adstransparency.google.com. Dựng nó trong phiên --browser rồi chụp lại thành google/img/r_<creative>.png."""
    page = BROWSER.page
    img_dir = Path(proj) / "google" / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    todo = [r for r in rows if r["preview_js"] and not r["image_url"] and not r["youtube_id"]
            and not (img_dir / f"r_{r['creative_id']}.png").exists()]
    if not todo:
        return
    print(f"  Dựng ảnh cho {len(todo)} QC không có ảnh tĩnh…")
    fake = f"{UI}/__render"
    ok = 0
    for r in todo:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(r["preview_js"]).query)
        pid, cb = q.get("htmlParentId", ["p"])[0], q.get("responseCallback", ["cb"])[0]
        body = (f'<html><body style="margin:0;background:#fff"><div id="{pid}" style="display:inline-block"></div>'
                f'<script>window["{cb}"]=function(){{}}</script><script src="{html.escape(r["preview_js"])}"></script></body></html>')
        page.route(fake, html_route(body))
        try:
            page.goto(fake, wait_until="load", timeout=30000)
            if "google.com/sorry" in page.url:
                BROWSER.ensure_access()
                page.goto(fake, wait_until="load", timeout=30000)
            page.wait_for_timeout(3500)
            el = page.query_selector(f"#{pid} iframe")
            if el and (el.bounding_box() or {}).get("height", 0) > 20:
                el.screenshot(path=str(img_dir / f"r_{r['creative_id']}.png"))
                ok += 1
        except Exception as e:
            print(f"    ✗ {r['creative_id']}: {str(e)[:80]}")
        finally:
            page.unroute(fake)
        time.sleep(random.uniform(1, 2))
    print(f"  → {ok}/{len(todo)} ảnh")


def main():
    ap = argparse.ArgumentParser(description="Tìm và phân tích QC Google Ads của đối thủ (Ads Transparency Center)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--project", required=True)
        p.add_argument("--country", default="VN", choices=list(REGIONS))
        p.add_argument("--out", default="projects")
        p.add_argument("--browser", action="store_true",
                       help="Gọi API qua cửa sổ Chromium thật; nếu gặp captcha thì bạn tự giải trong cửa sổ đó")

    p1 = sub.add_parser("discover", help="Tìm nhà quảng cáo theo tên / domain")
    common(p1)
    p1.add_argument("--keyword", action="append", default=[], help="Tên công ty / thương hiệu (lặp lại được)")
    p1.add_argument("--domain", action="append", default=[], help="Domain website, ví dụ ssi.com.vn")
    p1.add_argument("--name-match", help="Regex (không dấu) cho tên nhà quảng cáo để tự chọn")
    p2 = sub.add_parser("analyze", help="Phân tích creative của danh sách trong google_competitors.txt")
    common(p2)
    p2.add_argument("--refresh", action="store_true", help=f"Bỏ cache (mặc định {CACHE_HOURS} giờ)")
    p2.add_argument("--max-creatives", type=int, default=1500, help="Tối đa creative mỗi nhà quảng cáo")

    p3 = sub.add_parser("report", help="Dựng lại report_google.html từ cache, không gọi Google")
    common(p3)
    p5 = sub.add_parser("previews", help="Dựng ảnh cho QC không có ảnh tĩnh (cần cửa sổ trình duyệt)")
    common(p5)
    p4 = sub.add_parser("open", help="Mở báo cáo qua http://localhost (xem được video YouTube ngay trong báo cáo)")
    common(p4)
    p4.add_argument("--port", type=int, default=8765)

    args = ap.parse_args()
    if args.cmd == "open":
        return serve(Path(args.out) / args.project, args.port)
    if args.cmd in ("report", "previews"):
        args.offline, args.refresh, args.max_creatives = True, False, 0
    if args.cmd == "previews":
        args.browser = True
    if args.cmd == "discover" and not args.keyword and not args.domain:
        ap.error("Cần ít nhất --keyword hoặc --domain")
    global BROWSER
    try:
        if args.browser:
            BROWSER = BrowserSession()
        discover(args) if args.cmd == "discover" else analyze(args)  # report, previews = analyze offline
    except Blocked as e:
        raise SystemExit(f"\n✗ {e}")
    finally:
        if BROWSER:
            BROWSER.close()


if __name__ == "__main__":
    main()
