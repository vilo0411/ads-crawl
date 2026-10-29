"""
Luồng 3: chốt video thắng của đối thủ và chuẩn bị gói phân tích cho từng video.

Đầu vào là cache của bước analyze (projects/<project>/pages/*.json).
Mỗi video thắng được tải về cùng với:
    hook.jpg        6 khung hình trong 3 giây đầu
    storyboard.jpg  tối đa 16 khung tại các điểm chuyển cảnh
    transcript.srt / transcript.txt   lời thoại (whisper.cpp, tiếng Việt)
    meta.json       số liệu và caption

Cách dùng:
    python3 winner_pack.py --project tam-lop-poly
    python3 winner_pack.py --project tam-lop-poly --top 20 --per-page 4 --include-images
"""

import argparse
import json
import math
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

import competitor_intel as ci
import dsc_theme as dsc
import fb_ads_scraper as fb

MODEL_SEARCH = [
    Path.home() / "Documents",
    Path.home() / ".cache",
    Path("/opt/homebrew/share"),
    Path.home() / "models",
]
# Font của design system DSC nếu đã cài (Google Fonts), không thì Arial
FONT = next((str(f) for d in [Path.home() / "Library/Fonts", Path("/Library/Fonts")] if d.exists()
             for f in sorted(d.glob("PlusJakartaSans*.ttf"))), "/System/Library/Fonts/Supplemental/Arial.ttf")
TIERS = ["Tín hiệu bền", "Triển khai rộng", "Chưa đủ dữ liệu"]


# ───────────────────────── Chọn video thắng ─────────────────────────

def creative_key(r):
    # NFKC đổi chữ "in đậm" kiểu 𝐆𝐨̃ về chữ thường để các bản trùng khớp nhau
    text = unicodedata.normalize("NFKC", r["body"] or r["title"] or "")
    text = re.sub(r"[^a-z0-9]+", " ", ci.norm(text)).strip()[:120]
    return f"{r['page_id']}|{text or r['collation_id']}"


def tier_of(days, copies, new_copy_14d):
    if days >= 60 or (days >= 30 and copies >= 2):
        return TIERS[0]
    if days >= 14 or new_copy_14d:
        return TIERS[1]
    return TIERS[2]


def group_creatives(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[creative_key(r)].append(r)
    now = time.time()
    creatives = []
    for key, ads in groups.items():
        ads.sort(key=lambda r: -(r["days_running"] or 0))
        days = ads[0]["days_running"] or 0
        starts = [r["start_ts"] for r in ads if r["start_ts"]]
        latest = max(starts) if starts else None
        new_copy = len(ads) > 1 and latest and now - latest < 14 * 86400
        copies = max(len(ads), max(r["collation_count"] or 1 for r in ads))
        creatives.append({
            "key": key,
            "ads": ads,
            "rep": ads[0],
            "page_id": ads[0]["page_id"],
            "page_name": ads[0]["page_name"],
            "days": days,
            "copies": copies,
            "latest_start": time.strftime("%Y-%m-%d", time.localtime(latest)) if latest else "",
            "new_copy_14d": bool(new_copy),
            "tier": tier_of(days, copies, new_copy),
            "score": days * (1 + math.log(copies)),
            "is_video": any(r["video_urls"] for r in ads),
        })
    return sorted(creatives, key=lambda c: -c["score"])


def pick(creatives, top, per_page, videos):
    out, per = [], defaultdict(int)
    for c in creatives:
        if c["is_video"] != videos or per[c["page_id"]] >= per_page:
            continue
        per[c["page_id"]] += 1
        out.append(c)
        if len(out) == top:
            break
    return out


# ───────────────────────── Tải video ─────────────────────────

def try_download(c, dest):
    for r in c["ads"]:
        for url in r["video_urls"]:
            try:
                fb.download(url, dest)
                if ci.probe_video(str(dest)):
                    return True
            except Exception:
                pass
            dest.unlink(missing_ok=True)
    return False


def refresh_links(c, proj, args):
    """Link video FB hết hạn sau vài ngày: cào lại riêng fanpage này để lấy link mới."""
    print(f"    link hết hạn, cào lại fanpage {c['page_name']}…")
    ns = SimpleNamespace(refresh=True, country=args.country, max_scrolls=args.max_scrolls, show_browser=False)
    fresh = ci.scrape_pages([c["page_id"]], proj, ns)
    same = [r for r in fresh if creative_key(r) == c["key"]]
    if same:
        c["ads"] = same
    return bool(same)


# ───────────────────────── Khung hình ─────────────────────────

def video_duration(path):
    info = ci.probe_video(str(path))
    return info["dur"] if info else 0


def scene_times(path, threshold=0.3):
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [float(t) for t in re.findall(r"pts_time:([\d\.]+)", out.stderr)]


def grab(path, t, dest, width=360):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(path),
                    "-frames:v", "1", "-vf", f"scale={width}:-2", str(dest)], check=False)
    return dest.exists()


def contact_sheet(frames, cols, dest):
    """frames: [(giây, đường dẫn ảnh)] → lưới ảnh có ghi mốc thời gian."""
    imgs = [(t, Image.open(p).convert("RGB")) for t, p in frames]
    if not imgs:
        return
    w, h = imgs[0][1].size
    rows = math.ceil(len(imgs) / cols)
    pad, label = 6, 28
    sheet = Image.new("RGB", (cols * (w + pad) + pad, rows * (h + label + pad) + pad), dsc.GUNMETAL)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 20) if Path(FONT).exists() else ImageFont.load_default()
    for i, (t, im) in enumerate(imgs):
        x = pad + (i % cols) * (w + pad)
        y = pad + (i // cols) * (h + label + pad)
        draw.text((x + 4, y + 3), f"{int(t // 60)}:{t % 60:04.1f}", fill=dsc.FROSTED_MINT, font=font)
        sheet.paste(im.resize((w, h)), (x, y + label))
    sheet.save(dest, quality=85)


def storyboard_times(scenes, dur, n=16):
    """Điểm chuyển cảnh, cách nhau ít nhất dur/(2n), lấp thêm vào các đoạn dài không đổi cảnh."""
    min_gap, max_gap = dur / (2 * n), dur / n * 1.5
    times = [0.0]
    for t in sorted(scenes):
        if t - times[-1] >= min_gap and t < dur - 0.5:
            times.append(t)
    filled = []
    for a, b in zip(times, times[1:] + [dur]):
        filled.append(a)
        k = int((b - a) // max_gap)
        filled += [a + (b - a) * i / (k + 1) for i in range(1, k + 1)]
    if len(filled) > n:  # giữ khung đầu, rải đều phần còn lại
        step = (len(filled) - 1) / (n - 1)
        filled = [filled[round(i * step)] for i in range(n)]
    return filled


def build_frames(video, out_dir):
    dur = video_duration(video)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        hook = []
        for i, t in enumerate([0, 0.5, 1, 1.5, 2, 2.5]):
            if t < dur and grab(video, t, tmp / f"h{i}.jpg"):
                hook.append((t, tmp / f"h{i}.jpg"))
        contact_sheet(hook, 6, out_dir / "hook.jpg")

        times = storyboard_times(scene_times(video), dur)
        board = [(t, tmp / f"s{i}.jpg") for i, t in enumerate(times) if grab(video, t, tmp / f"s{i}.jpg", 300)]
        contact_sheet(board, 4, out_dir / "storyboard.jpg")
    return dur


# ───────────────────────── Lời thoại ─────────────────────────

def find_model(explicit):
    if explicit:
        return Path(explicit).expanduser()
    for base in MODEL_SEARCH:
        if base.exists():
            hits = sorted(base.rglob("ggml-*large*.bin")) or sorted(base.rglob("ggml-*.bin"))
            if hits:
                return hits[0]
    return None


def transcribe(video, out_dir, model):
    txt = out_dir / "transcript.txt"
    if not model or not shutil.which("whisper-cli"):
        txt.write_text("(chưa chuyển lời thoại: không tìm thấy whisper-cli hoặc model)", encoding="utf-8")
        return
    wav = out_dir / "audio.wav"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                        "-vn", "-ar", "16000", "-ac", "1", str(wav)], capture_output=True)
    if r.returncode or not wav.exists():
        txt.write_text("(video không có âm thanh)", encoding="utf-8")
        return
    subprocess.run(["whisper-cli", "-m", str(model), "-l", "vi", "-osrt", "-otxt", "-np",
                    "-of", str(out_dir / "transcript"), "-f", str(wav)], capture_output=True)
    wav.unlink(missing_ok=True)
    clean_transcript(out_dir)


# Whisper hay "bịa" mấy câu này khi video chỉ có nhạc, không có giọng nói
HALLUCINATIONS = r"subscribe|ghien mi go|dang ky kenh|cam on cac ban da (theo doi|xem)|like va share"


def clean_transcript(out_dir):
    txt = out_dir / "transcript.txt"
    lines = txt.read_text(encoding="utf-8").splitlines() if txt.exists() else []
    real = [l for l in lines if l.strip() and not re.search(HALLUCINATIONS, ci.norm(l))]
    if not real:
        txt.write_text("(không có lời thoại, chỉ có nhạc nền)", encoding="utf-8")
        (out_dir / "transcript.srt").unlink(missing_ok=True)
    elif len(real) < len(lines):
        txt.write_text("\n".join(real), encoding="utf-8")


# ───────────────────────── Main ─────────────────────────

def meta_of(c, rank, dur):
    r = c["rep"]
    return {
        "rank": rank, "tier": c["tier"], "page_name": c["page_name"], "page_id": c["page_id"],
        "days_running": c["days"], "copies": c["copies"], "latest_copy_start": c["latest_start"],
        "start_date": r["start_date"], "format": r["format"], "aspect": r.get("aspect"),
        "video_duration": round(dur, 1) if dur else r.get("video_duration"),
        "platforms": r["platforms"], "cta": r["cta"], "destination": r["dest"], "link_url": r["link_url"],
        "title": r["title"], "caption": r["body"], "signals": r["signals"],
        "library_links": [a["library_link"] for a in c["ads"]],
    }


def main():
    ap = argparse.ArgumentParser(description="Chốt video thắng của đối thủ + gói phân tích")
    ap.add_argument("--project", required=True)
    ap.add_argument("--top", type=int, default=12, help="Số video thắng cần lấy")
    ap.add_argument("--per-page", type=int, default=3, help="Tối đa bao nhiêu video mỗi đối thủ")
    ap.add_argument("--include-images", action="store_true", help="Liệt kê thêm QC ảnh thắng trong index.md")
    ap.add_argument("--whisper-model", help="Đường dẫn model ggml cho whisper.cpp (mặc định tự tìm)")
    ap.add_argument("--country", default="VN")
    ap.add_argument("--max-scrolls", type=int, default=30)
    ap.add_argument("--out", default="projects")
    ap.add_argument("--group", help='Chỉ lấy đối thủ thuộc nhóm "#@ …" trong competitors.txt '
                    '(mặc định: nhóm đầu tiên; "all" = mọi nhóm)')
    args = ap.parse_args()

    proj = Path(args.out) / args.project
    cache = sorted((proj / "pages").glob("*.json"))
    if not cache:
        raise SystemExit(f"Chưa có dữ liệu. Chạy trước: python3 competitor_intel.py analyze --project {args.project}")
    rows = [r for f in cache for r in json.loads(f.read_text(encoding="utf-8"))]
    comp = proj / "competitors.txt"
    entries = ci.read_competitors(comp) if comp.exists() else []
    group = args.group or (entries[0]["group"] if entries else "all")
    if group != "all" and len({e["group"] for e in entries}) > 1:
        keep = {e["pid"] for e in entries if e["group"] == group}
        rows = [r for r in rows if str(r["page_id"]) in keep]
        print(f"Nhóm: {group} ({len(keep)} fanpage)")
    ci.load_project_signals(proj)
    ci.enrich(rows, ci.load_landings(proj))

    creatives = group_creatives(rows)
    videos = pick(creatives, args.top, args.per_page, videos=True)
    images = pick(creatives, args.top, args.per_page, videos=False) if args.include_images else []
    model = find_model(args.whisper_model)
    print(f"{len(rows)} QC → {len(creatives)} creative khác nhau → chọn {len(videos)} video thắng")
    print(f"Whisper model: {model or 'KHÔNG TÌM THẤY'}")

    win_dir = proj / "winners"
    win_dir.mkdir(exist_ok=True)
    packs = []
    for rank, c in enumerate(videos, 1):
        name = f"{rank:02d}_{fb.safe_name(c['page_name'])[:30]}_{c['rep']['ad_archive_id']}"
        out = win_dir / name
        out.mkdir(exist_ok=True)
        print(f"\n[{rank}/{len(videos)}] {c['tier']} · {c['days']} ngày · ×{c['copies']} · {c['page_name']}")

        video = out / "video.mp4"
        if not video.exists():
            ok = try_download(c, video) or (refresh_links(c, proj, args) and try_download(c, video))
            if not ok:
                print("    ✗ không tải được video, bỏ qua")
                continue
        dur = 0
        if not (out / "storyboard.jpg").exists():
            print("    khung hình…")
            dur = build_frames(video, out)
        if not (out / "transcript.txt").exists():
            print("    lời thoại…")
            transcribe(video, out, model)
        clean_transcript(out)
        info = ci.probe_video(str(video)) or {}
        meta = meta_of(c, rank, info.get("dur") or dur)
        if info.get("w") and info.get("h"):
            meta["aspect"] = ci.aspect_label(info["w"], info["h"])
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        packs.append((out, meta))
        print(f"    ✓ {out}")

    write_index(win_dir, packs, images, len(rows), len(creatives))
    print(f"\n✔ {len(packs)} gói phân tích → {win_dir / 'index.md'}")


def write_index(win_dir, packs, images, n_ads, n_creatives):
    lines = [
        "# Creative có tín hiệu thắng · video đối thủ",
        "",
        f"Cập nhật {time.strftime('%d/%m/%Y %H:%M')} · {n_ads} QC → {n_creatives} creative khác nhau sau khi gộp bản trùng.",
        "",
        "Các nhãn chỉ phản ánh tín hiệu quan sát được: **Tín hiệu bền** = chạy ≥ 60 ngày, hoặc ≥ 30 ngày và có ≥ 2 bản · **Triển khai rộng** = 14–59 ngày, hoặc vừa có bản mới · **Chưa đủ dữ liệu** = < 14 ngày. Số QC đo mức độ active, không đại diện cho ngân sách hay thị phần. Dữ liệu không có tương tác trên bài quảng cáo; `page_like_count` chỉ là quy mô fanpage và không được dùng để xếp hạng creative.",
        "",
        "| # | Hạng | Fanpage | Ngày chạy | Số bản | Độ dài | Khung | Đích sau CTA | Gói |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for out, m in packs:
        lines.append(f"| {m['rank']} | {m['tier']} | {m['page_name']} | {m['days_running']} | {m['copies']} | "
                     f"{m['video_duration'] or '?'}s | {m['aspect'] or '?'} | {m['destination']} | [{out.name}]({out.name}/) |")
    if images:
        lines += ["", "## QC ảnh có tín hiệu đáng chú ý (chỉ liệt kê)", "", "| Hạng | Fanpage | Ngày chạy | Số bản | Caption | Link |",
                  "|---|---|---|---|---|---|"]
        for c in images:
            cap = (c["rep"]["body"] or "").replace("\n", " ").replace("|", "/")[:90]
            lines.append(f"| {c['tier']} | {c['page_name']} | {c['days']} | {c['copies']} | {cap} | "
                         f"[Ad Library]({c['rep']['library_link']}) |")
    (win_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
