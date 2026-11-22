"""Chuẩn bị dữ liệu cho báo cáo "Khoá học chứng khoán & tài chính trên Facebook Ads".

Đọc projects/khoa-hoc-chung-khoan/all_ads.csv (đầu ra của competitor_intel.py analyze) và trả về dict số liệu
đã gộp theo BRAND (một brand có thể chạy nhiều fanpage). Ưu đãi / thông điệp được phân loại lại theo đặc thù
ngành đào tạo (không dùng bộ ưu đãi của ngành chứng khoán) và chỉ tính trên QC nói về đào tạo.
Mọi tỉ lệ đếm theo MẪU THIẾT KẾ (asset_id) để QC nhân bản không làm lệch số.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJ = ROOT / "projects/khoa-hoc-chung-khoan"
SNAPSHOT_DATE = "22/11/2026"

# ── Phân khúc & brand. Ánh xạ page_id → brand viết tay, không đoán theo tên. ──
SEGMENTS = [
    ("dt", "Đào tạo đầu tư chứng khoán", "Học viện, chuyên gia bán khoá học cho nhà đầu tư cá nhân"),
    ("ctck", "Công ty chứng khoán dùng đào tạo", "CTCK dùng khoá học, sự kiện làm mồi mở tài khoản"),
    ("cc", "Chứng chỉ & nghề tài chính", "CFA, ACCA, CMA, IFRS, BCTC cho sinh viên và người đi làm"),
    ("fx", "Tham chiếu: đào tạo Forex / vàng", "Sàn và chuyên gia Forex, vàng dùng đào tạo kéo khách"),
    ("warn", "Cảnh giác", "Page tự xưng chuyên gia, có dấu hiệu lừa đảo"),
]
BRANDS = [  # (brand, segment, [(page_id, vai trò ngắn)])
    ("Da Vinci Academy", "dt", [("239482392585943", "Page chính · video mạn đàm CEO"),
                                ("104853195980568", "Sói già đầu tư · tặng lớp online"),
                                ("150389878953916", "Chi nhánh HCM · chuỗi chuyên đề"),
                                ("140790359120072", "Viện đào tạo thực hành · landing Hà Nội")]),
    ("Đặng Trọng Khang", "dt", [("103560292523362", "KOL · tích sản cổ phiếu"),
                                ("1476708278856572", "Học đầu tư bài bản · 5 buổi online")]),
    ("AYP · Nguyễn Hữu Trí", "dt", [("1416800418458998", "KOL · Intelligent Investor / Money")]),
    ("Nguyễn Ngọc Nghĩa", "dt", [("478376278905693", "KOL · AI Trading offline")]),
    ("Cole.vn · Quant", "dt", [("1194560673739428", "Chuyên đề Quant trading")]),
    ("FlowCap · Trần Hữu Chung", "dt", [("314491455070404", "CEO Fialda · khoá FlowCap")]),
    ("Bí Mật Đầu Tư CK", "dt", [("104407095873070", "Khoá 5 ngày · QC từ 2023")]),
    ("Quang Dũng DBD", "dt", [("101395798576919", "KOL · Đọc vị dòng tiền qua mẫu hình")]),
    ("Phạm Thành Biên", "dt", [("1681252095439210", "KOL · webinar dòng tiền, tích sản")]),
    ("LITADO · Money Master", "dt", [("108975761847038", "Lớp offline Money Master K100")]),
    ("ProX Community", "dt", [("1146772301846357", "Cộng đồng học đầu tư · trải nghiệm 2 tuần")]),
    ("AFA Research & Education", "dt", [("329039727208609", "Khoá vĩ mô ứng dụng trong đầu tư")]),
    ("LPS", "ctck", [("197779796755847", "App LOOP · Học - Hành thành tài")]),
    ("DNSE", "ctck", [("2033102266712313", "Future Tech Summit · DNSE MCP")]),
    ("FireAnt", "ctck", [("114212403303209", "FireAnt Education · học CK miễn phí"),
                         ("894533687085632", "FireAnt Invest · khoá hàng hoá phái sinh")]),
    ("HDSecurities", "ctck", [("1291556907378925", "Học viện HDS · HD Academy")]),
    ("SAPP Academy", "cc", [("110594185188150", "CFA"), ("107868168455339", "CFA Online"),
                            ("457356237963570", "ACCA"), ("100587722956457", "CMA · FP&A"),
                            ("100253538401872", "IFRS")]),
    ("FTMS Global", "cc", [("1668824786488099", "Cơ sở Hồ Chí Minh"), ("171448986212518", "Cơ sở Hà Nội")]),
    ("AuditCare (ACV)", "cc", [("103260535477721", "IFRS / ACCA tiếng Việt")]),
    ("Taca Tax Academy", "cc", [("600060600345511", "BCTC & thuế")]),
    ("Fintech · ĐH Bách khoa HN", "cc", [("980711205116219", "Khoá Fintech 76 giờ")]),
    ("amiCoach", "cc", [("100148559966", "CFA")]),
    ("FIDT", "cc", [("1806449472924151", "CFP · hoạch định tài chính")]),
    ("Kolia Phan", "fx", [("172085610077373", "Vàng, crypto · cộng đồng Telegram")]),
    ("ATFX", "fx", [("156675635201090", "Sàn Forex · webinar miễn phí")]),
    ("ROVA Academy", "fx", [("952751184579336", "Trading · landing bán khoá")]),
    ("AutoTrade Forex", "fx", [("1131806326691978", "Bot giao dịch tự động")]),
    ("SFVN", "fx", [("103400059161055", "Đầu tư hàng hoá cùng chuyên gia")]),
    ("Gia Cát Lợi", "fx", [("1002982026504005", "Thực chiến đầu tư hàng hoá")]),
    ("Mr SL Trade", "fx", [("119967891196558", "Vàng · tặng khoá Price Action")]),
    ("Giraffe Markets", "fx", [("705806329282760", "Sàn Forex"), ("110415658701387", "ZEU$ · đối tác giới thiệu")]),
    ("“Chuyên gia chứng khoán: NCB”", "warn", [("252387400000877", "Mời ‘đầu tư nước ngoài’, hứa lãi 58%/tuần")]),
]
EXCLUDED = [  # page đã cào nhưng không đưa vào phân tích, ghi rõ lý do trong phụ lục
    ("Học viện Quản lý PACE", "93 QC, gần như toàn bộ là khoá quản trị (OKR, văn hoá, lãnh đạo), không phải tài chính"),
    ("Trường doanh nhân HBR", "13 QC về kế hoạch kinh doanh, marketing cho chủ doanh nghiệp"),
    ("UniTutor (UniCFA), Bee Investing Academy", "Không có QC đang chạy tại ngày cào"),
    ("Anfin, AKVSA, HCT, Giao dịch hàng hoá 3D…", "Có QC tài chính nhưng không QC nào nói về khoá học"),
    ("Kho khoá học share giá rẻ, khoá kế toán thuần, IELTS…", "Lạc đề hoặc bán lại khoá học"),
]

# ── Phân loại cho ngành đào tạo (regex trên chữ không dấu) ──
EDU = r"khoa hoc|lop hoc|hoc vien|dao tao|buoi hoc|hoc phi|tuyen sinh|chuong trinh|masterclass|workshop|webinar|hoi thao|summit|chuyen de|giang vien|khai giang|lo trinh|bai giang|hoc thu|man dam|kien thuc|cam nang|tai lieu|ebook|live trade|giao dich truc tiep|series|tap \d|cfa|acca|\bcma\b|ifrs|fp&a|hoc "

OFFERS = [  # (nhãn, regex trên chữ không dấu) — mỗi QC có thể có nhiều ưu đãi
    ("Học thử / tham dự miễn phí", r"hoc thu|ve mien phi|tham du mien phi|(webinar|hoi thao|masterclass|su kien|lop hoc online|dao tao truc tuyen)[^.!\n]{0,40}mien phi|mien phi foundation|\d+ ngay mien phi|suat hoc thu"),
    ("Tặng tài liệu / ebook / template", r"(tang|giveaway|tai mien phi|free download|free ebook|ebook mien phi|nhan tron bo|tai tron bo)[^.!\n]{0,50}(tai lieu|ebook|cam nang|template|cong thuc|chi bao|kich ban|video)|(tai lieu|cam nang|template)[^.!\n]{0,20}mien phi"),
    ("Tư vấn lộ trình miễn phí", r"tu van (mien phi|1-1|lo trinh)|nhan tu van|nhan lo trinh|lo trinh[^.!\n]{0,25}mien phi"),
    ("Ưu đãi học phí / học bổng", r"uu dai (hoc phi|len den \d|den \d)|giam \d+ ?%? ?hoc phi|tiet kiem (den|len den) \d|early ?bird|hoc bong|tai tro 100%|uu dai len toi \d"),
    ("Công bố giá khoá học", None),  # xử lý bằng hàm price_tag
    ("Cam kết đầu ra / học lại miễn phí", r"cam ket dau ra|hoc lai mien phi|hoan (100% )?hoc phi|bao dam dau ra"),
    ("Cộng đồng miễn phí (Zalo / Telegram)", r"cong dong[^.!\n]{0,25}(free|mien phi)|t\.me/|nhom zalo|tham gia (nhom|cong dong)"),
    ("Quà tài chính khi mở tài khoản", r"tang[^.!\n]{0,12}co phieu|mien (100% )?phi giao dich|lai vay margin|hoan tien len den|nhan ngay \d+ trieu"),
    ("Giới hạn suất / hạn chót", r"chi con \d|con \d+ (ve|slots?|cho|suat)|so luong co han|link sap dong|\d+ slots?\b|han chot|cuoi cung[^.!\n]{0,15}(dang ky|uu dai)|giu suat|giu cho"),
]
HOOKS = [  # góc tiếp cận chính của nội dung
    ("Nỗi sợ thua lỗ, mất tiền", r"thua lo|tai khoan (do|chim|am)|chim trong sac do|cat lo|gong lo|mat tien|cang giu cang lo|va sap mat|lo nang|chay tai khoan"),
    ("Thoát phụ thuộc ‘phím hàng’", r"phim hang|hoi (hom nay )?mua (gi|con gi)|nghe room|theo tin don|tu dua ra (quyet dinh|gia dinh)|tu ra quyet dinh|quyen quyet dinh"),
    ("Người mới, bắt đầu từ 0", r"nguoi moi|\bf0\b|chua biet gi|tu con so 0|tu so 0|moi bat dau|trai nganh|tay ngang|bat dau tu dau|tam chieu moi"),
    ("Phương pháp đầu tư cụ thể", r"phuong phap (dau tu|giao dich)|he thong (giao dich|dau tu)|tich san|dau tu gia tri|good company|wyckoff|price action|dinh luong|quant|backtest|phan tich ky thuat|phan tich co ban|dinh gia (co phieu|doanh nghiep)|doc (va phan tich )?bao cao tai chinh|chien luoc (dau tu|giao dich)|ho tro (&|va) khang cu"),
    ("AI & công nghệ", None),  # xử lý trên chữ gốc, phân biệt "AI" với "ai"
    ("Sự nghiệp, Big4, thu nhập", r"big ?4|su nghiep|thang tien|tuyen dung|\bcv\b|internship|thuc tap|muc luong|\busd\b|nha tuyen dung"),
    ("Mục tiêu tài chính cá nhân", r"ve huu|tai chinh ca nhan|dam cuoi|lo cho con|quan ly tien|tra no|no nan|giu va nhan ban|tu do tai chinh|thu nhap thu dong"),
    ("Uy tín giảng viên, thành tích học viên", r"\d+\+? nam kinh nghiem|\d+ kinh nghiem|charterholder|vinh danh|top score|prize winner|pass rate|hoc vien[^.!\n]{0,25}(pass|dat|do)|founder|\bceo\b|\bts\.|giang vien la"),
    ("Thời điểm thị trường", r"giai doan vang|thoi diem vang|2026 ?[-–] ?2027|thi truong (dang|quay dau|bien dong)|chu ky|cuoi nam"),
]
AI_RX = re.compile(r"\bAI\b|\bEA\b|Trí tuệ nhân tạo|trí tuệ nhân tạo|Machine Learning|MCP|Auto ?Trading|Fintech|FINTECH|\bBot\b|\bBOT\b")


def price_tag(t: str) -> bool:
    """Giá khoá học: số tiền ≥ 500.000đ đứng ngay sau 'học phí' / 'chỉ' / 'giá khoá'."""
    for m in re.finditer(r"(hoc phi|chi|gia khoa hoc|gia chi)\s*(tu\s*|con\s*)?(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*(d|vnd|dong|trieu|tr|k)\b", t):
        n = m.group(3).replace(".", "").replace(",", ".")
        try:
            v = float(n)
        except ValueError:
            continue
        unit = m.group(4)
        v = v * 1e6 if unit in ("trieu", "tr") else v * 1e3 if unit == "k" else v
        ctx = t[max(0, m.start() - 80):m.end() + 80]
        if v >= 5e5 and re.search(r"hoc|khoa|chuong trinh|lop", ctx) and not re.search(r"luong|thue|thuong", ctx):
            return True
    return False


def tag_offers(t: str) -> list[str]:
    return [k for k, rx in OFFERS if (price_tag(t) if rx is None else re.search(rx, t))]


def tag_hooks(t: str, orig: str) -> list[str]:
    return [k for k, rx in HOOKS if (AI_RX.search(orig) if rx is None else re.search(rx, t))]


def norm(s: str) -> str:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def ad_text(r) -> str:
    return norm(" ".join([r.get("title") or "", r.get("body") or ""]))


def load(proj: Path = PROJ):
    rows = list(csv.DictReader(open(proj / "all_ads.csv", encoding="utf-8-sig")))
    landings_f = proj / "landing/landings.json"
    landings = json.loads(landings_f.read_text(encoding="utf-8")) if landings_f.exists() else {}
    page_brand = {pid: (b, seg, role) for b, seg, pages in BRANDS for pid, role in pages}
    name_by_pid = {}
    out = []
    for r in rows:
        pid = page_id_of(r)
        if pid not in page_brand:
            continue
        b, seg, role = page_brand[pid]
        t = ad_text(r)
        r["page_id"] = pid
        name_by_pid[pid] = r["page_name"]
        r["brand"], r["seg"], r["role"] = b, seg, role
        r["edu"] = bool(re.search(EDU, t))
        r["offer_tags"] = tag_offers(t)
        r["hook_tags"] = tag_hooks(t, (r.get("title") or "") + " " + (r.get("body") or ""))
        r["days"] = int(float(r["days_running"] or 0))
        r["design"] = r["asset_id"] or r["ad_archive_id"]
        out.append(r)
    return out, name_by_pid, landings


def page_id_of(r) -> str:
    # all_ads.csv không có cột page_id; lấy từ cache pages/<id>.json theo ad_archive_id
    return _AD2PAGE.get(r["ad_archive_id"], "")


def _build_ad2page(proj: Path = PROJ):
    m, col = {}, {}
    for f in (proj / "pages").glob("*.json"):
        for a in json.loads(f.read_text(encoding="utf-8")):
            m[str(a.get("ad_archive_id"))] = f.stem
            col[str(a.get("ad_archive_id"))] = str(a.get("collation_id") or a.get("ad_archive_id"))
    return m, col


_AD2PAGE, _AD2COL = _build_ad2page()


def thumb_of(ad_id: str) -> str:
    """Thumbnail tải về được đặt tên theo collation_id (xem report_builder.assign_assets)."""
    f = f"thumbs/{_AD2COL.get(ad_id, ad_id)}.jpg"
    return f if (PROJ / f).exists() else ""


# Brand đào tạo chứng khoán đôi khi chạy QC cho khoá KHÁC ngành (AYP: hướng nghiệp, kỹ năng mềm; LITADO: AI cho chủ doanh nghiệp).
# Mẫu thuộc nhóm "dt" chỉ được tính khi nói về đầu tư / tài chính; mẫu lạc đề bị loại và ghi vào phụ lục.
OFFTOPIC_URL = r"career[-_]navigation|underground-leader|awaken-your-power"
OFFTOPIC_TEXT = r"cuoc choi ai|chu cua hang, chu doanh nghiep"  # LITADO: khoá AI cho chủ doanh nghiệp
FIN_RX = (r"chung khoan|co phieu|dau tu|tai chinh|tich san|trading|trade|phai sinh|danh muc|vn.?index|loi nhuan|"
          r"quan ly tien|tien bac|intelligent (money|investor)|dong tien|vang|forex|crypto|quant|backtest")


def off_topic(d) -> bool:
    if d["seg"] != "dt":
        return False
    t = norm((d.get("body") or "") + " " + (d.get("title") or ""))
    return (bool(re.search(OFFTOPIC_URL, (d.get("final_url") or "") + " " + (d.get("link_url") or "")))
            or bool(re.search(OFFTOPIC_TEXT, t)) or not re.search(FIN_RX, t))


def designs(rows):
    """Gộp QC theo mẫu thiết kế, giữ bản chạy lâu nhất làm đại diện; gộp nhãn của mọi bản trong mẫu."""
    by = defaultdict(list)
    for r in rows:
        by[(r["brand"], r["design"])].append(r)
    out = []
    for (_, _), rr in by.items():
        rep = max(rr, key=lambda x: (x["days"], bool(thumb_of(x["ad_archive_id"])))).copy()
        rep["thumb"] = next((t for t in [thumb_of(x["ad_archive_id"]) for x in sorted(rr, key=lambda x: -x["days"])] if t), "")
        rep["n_ads"] = len(rr)
        rep["ad_ids"] = [x["ad_archive_id"] for x in rr]
        # cách chốt / tầng phễu của mẫu = loại chiến dịch phổ biến nhất trong các bản của mẫu
        rep["objective"] = Counter(x["objective"] for x in rr).most_common(1)[0][0]
        rep["stage"] = Counter(x["stage"] for x in rr).most_common(1)[0][0]
        rep["edu"] = any(x["edu"] for x in rr)
        rep["offer_tags"] = sorted({t for x in rr for t in x["offer_tags"]}, key=[k for k, _ in OFFERS].index)
        rep["hook_tags"] = sorted({t for x in rr for t in x["hook_tags"]}, key=[k for k, _ in HOOKS].index)
        rep["pages"] = sorted({x["page_name"] for x in rr})
        out.append(rep)
    return out


CHANNEL = {  # gom objective + landing thành "cách chốt" dễ hiểu cho quản lý
    "Lead form trên FB": "Form ngay trên Facebook",
    "Lead / chuyển đổi trên web": "Landing page có form",
    "Traffic → landing": "Landing page có form",
    "Tin nhắn": "Nhắn tin Messenger",
    "Cài app": "Tải app",
    "Traffic → bài viết / PR": "Bài viết / nội dung",
    "Tương tác / video view": "Xem video, tương tác",
    "Like trang": "Xem video, tương tác",
}
CHANNEL_ORDER = ["Form ngay trên Facebook", "Landing page có form", "Nhắn tin Messenger", "Tải app",
                 "Bài viết / nội dung", "Xem video, tương tác"]
STAGES = ["Nhận biết", "Cân nhắc", "Chuyển đổi"]


def build():
    rows, name_by_pid, landings = load()
    ds_all = designs(rows)
    ds = [d for d in ds_all if not off_topic(d)]
    dropped = Counter(d["brand"] for d in ds_all if off_topic(d))
    rows = [r for r in rows if r["ad_archive_id"] not in {x for d in ds_all if off_topic(d) for x in d.get("ad_ids", [d["ad_archive_id"]])}]
    seg_name = {k: n for k, n, _ in SEGMENTS}
    brands = []
    for b, seg, pages in BRANDS:
        rr = [r for r in rows if r["brand"] == b]
        dd = [d for d in ds if d["brand"] == b]
        edu = [d for d in dd if d["edu"]]
        ch = Counter(CHANNEL.get(d["objective"], "Xem video, tương tác") for d in dd)
        st = Counter(d["stage"] for d in dd)
        vids = [d for d in dd if d["format"] == "Video"]
        durs = [float(d["video_duration"]) for d in vids if d.get("video_duration")]
        page_rows = []
        for pid, role in pages:
            pr = [r for r in rows if r["page_id"] == pid]
            pd_ = [d for d in dd if d["page_id"] == pid]
            pch = Counter(CHANNEL.get(d["objective"], "Xem video, tương tác") for d in pd_)
            page_rows.append({
                "page_id": pid, "name": name_by_pid.get(pid, role), "role": role, "ads": len(pr), "designs": len(pd_),
                "new14": sum(1 for d in pd_ if d["days"] <= 14), "max_days": max((d["days"] for d in pd_), default=0),
                "channel": pch.most_common(1)[0][0] if pch else "—",
            })
        samples = sorted(edu or dd, key=lambda d: (not d["thumb"], -d["days"], -d["n_ads"]))[:4]
        brands.append({
            "brand": b, "seg": seg, "seg_name": seg_name[seg], "pages": page_rows,
            "ads": len(rr), "designs": len(dd), "edu_designs": len(edu), "edu_ads": sum(d["n_ads"] for d in edu),
            "new14": sum(1 for d in dd if d["days"] <= 14), "d30": sum(1 for d in dd if d["days"] >= 30),
            "max_days": max((d["days"] for d in dd), default=0),
            "video_pct": round(100 * len(vids) / len(dd)) if dd else 0,
            "video_median_s": round(statistics.median(durs)) if durs else None,
            "aspect": Counter(d["aspect"] for d in vids if d["aspect"]).most_common(1)[0][0] if vids and any(d["aspect"] for d in vids) else "",
            "channels": {c: ch.get(c, 0) for c in CHANNEL_ORDER},
            "top_channel": ch.most_common(1)[0][0] if ch else "—",
            "stages": {s: st.get(s, 0) for s in STAGES},
            "offers": {k: sum(1 for d in edu if k in d["offer_tags"]) for k, _ in OFFERS},
            "hooks": {k: sum(1 for d in edu if k in d["hook_tags"]) for k, _ in HOOKS},
            "samples": [{
                "id": d["ad_archive_id"], "thumb": d["thumb"], "days": d["days"],
                "n_ads": d["n_ads"], "format": d["format"], "page": d["page_name"], "cta": d["cta"],
                "channel": CHANNEL.get(d["objective"], "Xem video, tương tác"),
                "title": (d["title"] or "").strip(), "body": re.sub(r"\s+", " ", d["body"] or "").strip()[:260],
                "offers": d["offer_tags"], "hooks": d["hook_tags"][:3], "link": d["library_link"],
            } for d in samples],
        })
    # Brand không còn QC nào đang chạy tại ngày cào: bỏ khỏi số liệu, ghi vào phụ lục
    stopped = [b["brand"] for b in brands if not b["designs"]]
    brands = [b for b in brands if b["designs"]]
    excluded = ([(", ".join(stopped), "Có QC khoá học ở lượt cào trước nhưng đã dừng toàn bộ QC tại ngày cào")]
                if stopped else []) + ([("Mẫu lạc đề: " + ", ".join(f"{b} ({n} mẫu)" for b, n in dropped.most_common()),
                                         "QC cho khoá không phải đầu tư, tài chính (hướng nghiệp, kỹ năng mềm, AI cho chủ doanh nghiệp), không tính vào số liệu")]
                                       if dropped else []) + EXCLUDED
    segs = []
    for k, n, desc in SEGMENTS:
        bb = [b for b in brands if b["seg"] == k]
        dd = [d for d in ds if d["seg"] == k]
        edu = [d for d in dd if d["edu"]]
        segs.append({
            "key": k, "name": n, "desc": desc, "brands": len(bb), "pages": sum(len(b["pages"]) for b in bb),
            "ads": sum(b["ads"] for b in bb), "designs": len(dd), "edu_designs": len(edu),
            "new14_pct": round(100 * sum(1 for d in dd if d["days"] <= 14) / len(dd)) if dd else 0,
            "d30": sum(1 for d in dd if d["days"] >= 30),
            "channels": {c: sum(1 for d in dd if CHANNEL.get(d["objective"], "Xem video, tương tác") == c) for c in CHANNEL_ORDER},
            "stages": {s: sum(1 for d in dd if d["stage"] == s) for s in STAGES},
            "offers": {o: sum(1 for d in edu if o in d["offer_tags"]) for o, _ in OFFERS},
            "hooks": {h: sum(1 for d in edu if h in d["hook_tags"]) for h, _ in HOOKS},
            "video_pct": round(100 * sum(1 for d in dd if d["format"] == "Video") / len(dd)) if dd else 0,
        })
    return {
        "snapshot": SNAPSHOT_DATE, "segments": segs, "brands": brands,
        "offers_order": [k for k, _ in OFFERS], "hooks_order": [k for k, _ in HOOKS],
        "channels_order": CHANNEL_ORDER, "stages_order": STAGES, "excluded": excluded,
        "totals": {"brands": len(brands), "pages": sum(len(b["pages"]) for b in brands),
                   "ads": sum(b["ads"] for b in brands), "designs": len(ds),
                   "edu_designs": sum(1 for d in ds if d["edu"])},
        "_designs": ds,
    }


if __name__ == "__main__":
    import sys
    data = build()
    if "--audit" in sys.argv:  # in mẫu để kiểm tra độ chính xác của từng nhãn
        import random
        random.seed(1)
        ds = [d for d in data["_designs"] if d["edu"]]
        for label in data["offers_order"] + data["hooks_order"]:
            hit = [d for d in ds if label in d["offer_tags"] or label in d["hook_tags"]]
            print(f"\n=== {label}: {len(hit)} mẫu")
            for d in random.sample(hit, min(4, len(hit))):
                print(f"  [{d['brand']}] {re.sub(chr(10), ' ', (d['title'] or '') + ' :: ' + (d['body'] or ''))[:230]}")
        sys.exit()
    t = data["totals"]
    print(t)
    for s in data["segments"]:
        print(s["name"], s["brands"], s["pages"], s["ads"], s["designs"], s["edu_designs"], s["new14_pct"], s["d30"])
    for b in data["brands"]:
        print(f"{b['brand'][:26]:26} pages={len(b['pages'])} ads={b['ads']:>3} designs={b['designs']:>3} edu={b['edu_designs']:>3} new14={b['new14']:>3} d30={b['d30']:>3} max={b['max_days']:>4} ch={b['top_channel']}")
