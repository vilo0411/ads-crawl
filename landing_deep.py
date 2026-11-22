"""Đọc sâu landing page: chụp TOÀN TRANG (mobile) + lấy chữ, form, nút bấm, giá để phân tích offer.

Khác landing_crawl.py (chỉ chụp màn hình đầu + phân loại trang), script này dùng cho phần "Landing page: họ bán gì,
offer gì" của báo cáo. Đầu vào là danh sách URL (mỗi dòng: url<TAB>nhãn), đầu ra:
  projects/<project>/landing/deep/<id>.json       chữ, tiêu đề, form, nút, giá tìm thấy
  projects/<project>/landing/deep/<id>_full.jpg   ảnh toàn trang (cắt tối đa --max-height px)
  projects/<project>/landing/deep/<id>_top.jpg    màn hình đầu (để làm thumbnail)

  python3 landing_deep.py --project khoa-hoc-chung-khoan --urls urls.tsv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")

PROBE_JS = r"""() => {
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const txt = el => (el.innerText || el.value || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
  const fields = [];
  document.querySelectorAll('input, select, textarea').forEach(el => {
    if (!vis(el) || ['hidden', 'submit', 'button'].includes(el.type)) return;
    let label = el.getAttribute('placeholder') || el.getAttribute('aria-label') || el.name || '';
    if (el.id) { const l = document.querySelector(`label[for="${el.id}"]`); if (l) label = txt(l) || label; }
    fields.push(label.trim().slice(0, 60));
  });
  const buttons = [...document.querySelectorAll('button, a, input[type=submit]')].filter(vis).map(txt)
    .filter(t => t && t.length <= 40);
  const heads = [...document.querySelectorAll('h1, h2, h3')].filter(vis).map(txt).filter(Boolean).slice(0, 40);
  return { title: document.title, text: (document.body ? document.body.innerText : '').slice(0, 30000),
           fields, buttons: [...new Set(buttons)].slice(0, 60), heads,
           height: document.documentElement.scrollHeight };
}"""

PRICE_RX = re.compile(r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(đ|₫|vnđ|vnd|đồng|triệu|tr|k)\b", re.I)


def url_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]


def crawl(items, out, max_height):
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(user_agent=MOBILE_UA, locale="vi-VN", is_mobile=True, has_touch=True,
                            viewport={"width": 390, "height": 844}, device_scale_factor=1)
        for i, (url, label) in enumerate(items, 1):
            uid = url_id(url)
            page = ctx.new_page()
            info, err = {}, ""
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000)
                # chụp màn hình đầu TRƯỚC khi cuộn: nhiều trang không cuộn về đầu được bằng scrollTo
                page.screenshot(path=str(out / f"{uid}_top.jpg"), type="jpeg", quality=70)
                # cuộn dần để ảnh lazy-load hiện ra trước khi chụp toàn trang
                h = page.evaluate("document.documentElement.scrollHeight")
                for y in range(0, min(h, max_height), 700):
                    page.evaluate(f"window.scrollTo(0, {y})")
                    page.wait_for_timeout(250)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(800)
                info = page.evaluate(PROBE_JS)
                full_h = min(info.get("height") or 844, max_height)
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(out / f"{uid}_full.jpg"), type="jpeg", quality=55, full_page=True,
                                clip={"x": 0, "y": 0, "width": 390, "height": full_h})
            except Exception as e:
                err = str(e).splitlines()[0][:200]
            text = info.get("text", "")
            res[url] = {
                "url": url, "label": label, "id": uid, "final_url": page.url, "error": err,
                "title": info.get("title", ""), "heads": info.get("heads", []),
                "fields": info.get("fields", []), "buttons": info.get("buttons", []),
                "prices": sorted({m.group(0) for m in PRICE_RX.finditer(text)})[:30],
                "height": info.get("height"), "text": text, "checked_at": time.time(),
            }
            (out / f"{uid}.json").write_text(json.dumps(res[url], ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[{i}/{len(items)}] {'LỖI ' + err if err else 'ok'} · {label} · {len(text)} ký tự · cao {info.get('height')}px")
            page.close()
        b.close()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--urls", required=True, help="File TSV: url<TAB>nhãn")
    ap.add_argument("--max-height", type=int, default=9000, help="Cắt ảnh toàn trang ở độ cao này (px)")
    a = ap.parse_args()
    out = ROOT / "projects" / a.project / "landing" / "deep"
    out.mkdir(parents=True, exist_ok=True)
    items = [tuple((l.split("\t") + [""])[:2]) for l in Path(a.urls).read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.startswith("#")]
    crawl(items, out, a.max_height)


if __name__ == "__main__":
    main()
