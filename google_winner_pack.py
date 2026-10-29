"""
Video YouTube thắng trong Google Ads của đối thủ + gói phân tích (giống winner_pack.py bản Facebook).

Đầu vào là cache của google_ads_intel.py analyze (projects/<project>/google/AR*.json).
Một video YouTube thường được dùng trong nhiều creative (nhiều kích thước, nhiều chiến dịch) → gộp theo ID video,
số creative dùng chung = "số bản".

Mỗi video thắng được tải bằng yt-dlp, kèm hook.jpg, storyboard.jpg, transcript (whisper.cpp) và meta.json.

Cách dùng:
    python3 google_winner_pack.py --project chung-khoan
    python3 google_winner_pack.py --project chung-khoan --top 20 --per-page 4 --all-time
"""

import argparse
import json
import math
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import competitor_intel as ci
import fb_ads_scraper as fb
import google_ads_intel as g
import winner_pack as wp


def group_videos(rows, recent_days):
    by = defaultdict(list)
    for r in rows:
        if r["youtube_id"]:
            by[r["youtube_id"]].append(r)
    now = time.time()
    out = []
    for vid, rs in by.items():
        rs.sort(key=lambda r: -r["days_shown"])
        last = max(r["last_ts"] for r in rs)
        if recent_days and now - last > recent_days * 86400:
            continue
        days, copies = rs[0]["days_shown"], len({r["creative_id"] for r in rs})
        new_copy = copies > 1 and now - max(r["first_ts"] for r in rs) < 14 * 86400
        out.append({
            "vid": vid, "rows": rs, "rep": rs[0], "competitor": rs[0]["competitor"], "days": days, "copies": copies,
            "active": now - last < g.ACTIVE_DAYS * 86400, "new_copy_14d": bool(new_copy),
            "first": min(r["first_shown"] for r in rs), "last": max(r["last_shown"] for r in rs),
            "platforms": sorted({p for r in rs for p in r["platforms"].split(",")},
                                key=lambda p: (g.PLATFORM_ORDER + [g.OTHER]).index(p)),
            "tier": wp.tier_of(days, copies, new_copy),
            "score": days * (1 + math.log(copies)),
        })
    return sorted(out, key=lambda v: -v["score"])


def pick(videos, top, per_page):
    out, per = [], defaultdict(int)
    for v in videos:
        if per[v["competitor"]] >= per_page:
            continue
        per[v["competitor"]] += 1
        out.append(v)
        if len(out) == top:
            break
    return out


def download(vid, dest):
    # 720p là đủ để xem khung hình và chuyển lời thoại, tải nhanh hơn nhiều so với 1080p
    r = subprocess.run(["yt-dlp", "-q", "--no-warnings", "--no-playlist", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
                        "--merge-output-format", "mp4", "-o", str(dest), f"https://www.youtube.com/watch?v={vid}"],
                       capture_output=True, text=True)
    if r.returncode or not dest.exists():
        print(f"    ✗ yt-dlp: {(r.stderr or '').strip().splitlines()[-1:] or 'lỗi'}")
        dest.unlink(missing_ok=True)
        return False
    return True


def meta_of(v, rank, video):
    info = ci.probe_video(str(video)) or {}
    r = v["rep"]
    return {
        "rank": rank, "tier": v["tier"], "competitor": v["competitor"], "advertiser": r["advertiser_name"],
        "youtube": f"https://youtu.be/{v['vid']}", "video_title": r["video_title"],
        "days_shown": v["days"], "creatives_using_video": v["copies"], "active": v["active"],
        "first_shown": v["first"], "last_shown": v["last"], "platforms": v["platforms"],
        "video_duration": round(info["dur"], 1) if info.get("dur") else None,
        "aspect": ci.aspect_label(info["w"], info["h"]) if info.get("w") and info.get("h") else None,
        "signals": r.get("signals", []),
        "transparency_links": [x["link"] for x in v["rows"][:10]],
    }


def write_index(win_dir, packs, n_rows, n_videos):
    lines = [
        "# Creative có tín hiệu thắng · video YouTube trong Google Ads",
        "",
        f"Cập nhật {time.strftime('%d/%m/%Y %H:%M')} · {n_rows} creative Google → {n_videos} video YouTube khác nhau.",
        "",
        "Các nhãn chỉ phản ánh tín hiệu quan sát được: **Tín hiệu bền** = hiển thị ≥ 60 ngày, hoặc ≥ 30 ngày và dùng trong ≥ 2 creative · **Triển khai rộng** = 14–59 ngày, "
        "hoặc vừa có creative mới · **Chưa đủ dữ liệu** = < 14 ngày. \"Ngày hiển thị\" là số ngày Google ghi nhận phân phối. Số creative đo mức độ active/triển khai, không đại diện cho ngân sách, impression share hay hiệu quả kinh doanh.",
        "",
        "| # | Hạng | Đối thủ | Ngày hiển thị | Số creative | Đang chạy | Độ dài | Khung | Nền tảng | Tiêu đề | Gói |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for out, m in packs:
        title = (m["video_title"] or "").replace("|", "/")[:60]
        lines.append(f"| {m['rank']} | {m['tier']} | {m['competitor']} | {m['days_shown']} | {m['creatives_using_video']} | "
                     f"{'✓' if m['active'] else ''} | {m['video_duration'] or '?'}s | {m['aspect'] or '?'} | "
                     f"{', '.join(m['platforms'])} | [{title}]({m['youtube']}) | [{out.name}]({out.name}/) |")
    (win_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Video YouTube thắng trong Google Ads của đối thủ + gói phân tích")
    ap.add_argument("--project", required=True)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--per-page", type=int, default=3, help="Tối đa bao nhiêu video mỗi đối thủ")
    ap.add_argument("--recent-days", type=int, default=30,
                    help="Chỉ lấy video có hiển thị trong N ngày gần nhất (mặc định 30)")
    ap.add_argument("--all-time", action="store_true", help="Lấy cả video đã ngừng chạy từ lâu")
    ap.add_argument("--whisper-model", help="Model ggml cho whisper.cpp (mặc định tự tìm)")
    ap.add_argument("--out", default="projects")
    args = ap.parse_args()

    if not shutil.which("yt-dlp"):
        raise SystemExit("Cần yt-dlp: brew install yt-dlp")
    proj = Path(args.out) / args.project
    comp = proj / "google_competitors.txt"
    cache = proj / "google"
    if not comp.exists() or not any(cache.glob("AR*.json")):
        raise SystemExit(f"Chưa có dữ liệu. Chạy trước: python3 google_ads_intel.py analyze --project {args.project} --browser")
    ci.load_project_signals(proj)
    rows = []
    for e in ci.read_competitors(comp):
        f = cache / f"{e['pid']}.json"
        if f.exists():
            for r in json.loads(f.read_text(encoding="utf-8")):
                r["competitor"] = ci.short_name(e["label"]) or e["pid"]
                rows.append(r)
    g.enrich(rows, time.time())

    videos = group_videos(rows, None if args.all_time else args.recent_days)
    chosen = pick(videos, args.top, args.per_page)
    model = wp.find_model(args.whisper_model)
    print(f"{len(rows)} creative → {len(videos)} video YouTube"
          f"{'' if args.all_time else f' hiển thị trong {args.recent_days} ngày'} → chọn {len(chosen)}")
    print(f"Whisper model: {model or 'KHÔNG TÌM THẤY'}")

    win_dir = proj / "winners_google"
    win_dir.mkdir(exist_ok=True)
    packs = []
    for rank, v in enumerate(chosen, 1):
        out = win_dir / f"{rank:02d}_{fb.safe_name(v['competitor'])[:30]}_{v['vid']}"
        out.mkdir(exist_ok=True)
        print(f"\n[{rank}/{len(chosen)}] {v['tier']} · {v['days']} ngày · ×{v['copies']} · {v['competitor']} · "
              f"{v['rep']['video_title'][:60]}")
        video = out / "video.mp4"
        if not video.exists() and not download(v["vid"], video):
            continue
        if not (out / "storyboard.jpg").exists():
            print("    khung hình…")
            wp.build_frames(video, out)
        if not (out / "transcript.txt").exists():
            print("    lời thoại…")
            wp.transcribe(video, out, model)
        wp.clean_transcript(out)
        meta = meta_of(v, rank, video)
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        packs.append((out, meta))
        print(f"    ✓ {out}")

    write_index(win_dir, packs, len(rows), len(videos))
    print(f"\n✔ {len(packs)} gói phân tích → {win_dir / 'index.md'}")


if __name__ == "__main__":
    main()
