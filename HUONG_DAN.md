# Cào video Facebook Ads của đối thủ

## Cách 1: Xem và tải thủ công trên Meta Ad Library

1. Vào https://www.facebook.com/ads/library/
2. Chọn **Quốc gia: Việt Nam**, **Loại quảng cáo: Tất cả quảng cáo**.
3. Gõ tên fanpage đối thủ, chọn đúng page trong danh sách gợi ý (không bấm Enter, vì Enter sẽ tìm theo từ khoá).
4. Bộ lọc: **Loại phương tiện → Video**, **Trạng thái → Đang hoạt động**.
5. Đọc từng quảng cáo:
   - **"Bắt đầu chạy vào ngày…"**: chạy càng lâu thì càng có khả năng đang có lãi. Ưu tiên học quảng cáo chạy từ 30 ngày trở lên.
   - **"N quảng cáo dùng nội dung này"**: đối thủ đang nhân bản để scale, tức là mẫu này đang hiệu quả.
   - Nền tảng (FB / IG / Messenger / Audience Network), CTA, landing page.
6. Tải video: bấm **Xem chi tiết quảng cáo** → chuột phải vào video. Nếu không có nút tải thì mở DevTools (Cmd+Opt+I) → Network → lọc `mp4` → phát video → mở link `.mp4` trong tab mới → Cmd+S.

**Lấy Page ID** (dùng cho cách 3): sau bước 3, URL sẽ có dạng `...&view_all_page_id=123456789012345`. Dãy số đó chính là Page ID.

## Cách 3: Script tự động `fb_ads_scraper.py`

### Cài đặt (chỉ làm một lần)
```bash
pip3 install playwright && python3 -m playwright install chromium
```

### Chạy
```bash
# Một đối thủ theo Page ID
python3 fb_ads_scraper.py --page 123456789012345

# Nhiều đối thủ: mỗi dòng trong competitors.txt là 1 Page ID (dòng bắt đầu # bị bỏ qua)
python3 fb_ads_scraper.py --pages-file competitors.txt

# Theo từ khoá ngành
python3 fb_ads_scraper.py --keyword "kem chống nắng" --keyword "serum vitamin c"
```

Tuỳ chọn hữu ích:

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `--no-download` | Chỉ lấy metadata (CSV/JSON), không tải video |
| `--all-media` | Lấy cả quảng cáo ảnh |
| `--max-scrolls 60` | Cuộn nhiều hơn để lấy thêm quảng cáo (mặc định 30, khoảng 10 quảng cáo mỗi lần cuộn) |
| `--country ALL` | Tất cả quốc gia thay vì chỉ VN |
| `--show-browser` | Mở cửa sổ Chrome để xem script đang làm gì |

### Kết quả
```
output/<tên page hoặc kw_từ khoá>/
  ads.csv      ← mở bằng Excel/Google Sheets, đã sắp xếp theo số ngày chạy giảm dần
  ads.json
  videos/0120d_<ad_id>_0.mp4   ← tiền tố = số ngày đã chạy, nên sắp theo tên là thấy quảng cáo "lì" nhất trước
```
Các cột trong CSV: page, ngày bắt đầu, số ngày chạy, nền tảng, số bản nhân, caption, tiêu đề, CTA, link đích, link video, link Ad Library.

## Tìm và phân tích đối thủ: `competitor_intel.py`

Script này có 2 luồng, dùng chung bộ cào với `fb_ads_scraper.py`.

### Luồng 1: Discover (có những đối thủ nào?)
Tìm theo nhiều cụm từ khoá chính xác, bỏ QC lạc đề bằng `--match`, rồi gom theo fanpage.
```bash
python3 competitor_intel.py discover --project tam-lop-poly \
  --keyword "tấm lợp poly" --keyword "tấm poly" --keyword "polycarbonate" \
  --keyword "tấm lợp lấy sáng" --keyword "nhựa lấy sáng" --keyword "tôn nhựa lấy sáng" \
  --match "polycarbonate|tam poly|tam lop|lay sang|ton nhua|mai poly|poly dac|poly rong" \
  --name-match "poly|lay sang|tam lop|tam nhua|nhua kinh|mai che|roofing|ton nhua"
```
- `--match`: regex **viết không dấu**. Chỉ giữ QC có caption/tiêu đề chứa các cụm này (vì Ad Library khớp từng chữ lẻ nên kết quả lẫn nhiều ngành khác).
- `--name-match`: fanpage có **tên** khớp sẽ được chọn sẵn. Các fanpage còn lại nằm trong file dưới dạng dòng có `#` đứng đầu.
- Kết quả: `projects/tam-lop-poly/competitors.txt` (danh sách để sửa tay) và `competitors.csv` (có số like, ngành, caption mẫu).

**Bước bắt buộc:** mở `competitors.txt`, thêm `#` vào đầu dòng của fanpage không phải đối thủ, và xoá `#` ở những dòng đúng là đối thủ. Thêm Page ID của đối thủ bạn đã biết nhưng chưa có trong danh sách.

### Luồng 2: Analyze (đối thủ đang chạy gì?)
```bash
python3 competitor_intel.py analyze --project tam-lop-poly
```
Script cào **toàn bộ** QC đang chạy của từng fanpage (cả video, ảnh, carousel), đo độ dài và tỉ lệ khung của video bằng ffprobe, rồi xuất:
- `report.html`: báo cáo có tab (tổng quan, so sánh, hồ sơ từng đối thủ, ưu đãi & thông điệp, thư viện creative có bộ lọc…), mở bằng trình duyệt. Thumbnail được lưu ở `thumbs/`
- `competitors_summary.csv`: mỗi đối thủ 1 dòng
- `all_ads.csv`: mỗi QC 1 dòng, để tự lọc hoặc pivot trên Google Sheets

Báo cáo trả lời các câu hỏi sau:

| Câu hỏi | Chỉ số |
|---|---|
| Có những đối thủ nào đang chạy? | Số QC đang chạy (thị phần hiển thị), số mẫu creative khác nhau, số like của fanpage |
| Định dạng và tài sản quảng cáo | Video / ảnh / nhiều ảnh / carousel; tỉ lệ khung video (9:16, 1:1, 4:5…); độ dài video; nền tảng; nút CTA; kênh chốt (Messenger / Zalo / Website / Gọi điện) |
| Thời gian chạy | Phân bố số ngày chạy, trung vị và lâu nhất của từng đối thủ, số QC chạy ≥ 30 ngày ("thắng") |
| Chỉ số gợi ý thêm | **Nhịp test** (số QC mới theo tuần, số QC mới trong 14 ngày); **mức nhân bản** (1 creative chạy nhiều bản = đang scale); **thông điệp** (% QC nói về giá, SĐT, Zalo, giao hàng, bảo hành, thi công, khuyến mãi, thông số, chống UV, tổng kho); **top 24 QC đáng học** |

Các tuỳ chọn khác:
- `--refresh`: cào lại từ đầu. Mặc định script dùng cache 12 giờ, nên có thể sửa danh sách rồi chạy lại mà không phải cào lại.
- `--page 123`: thêm Page ID mà không cần sửa file.
- `--no-probe`: bỏ qua bước đo video để chạy nhanh hơn.
- **Tín hiệu thông điệp theo ngành:** mặc định là bộ của ngành tấm lợp. Ngành khác thì tạo `projects/<project>/signals.json` dạng `{"Tên tín hiệu": "regex không dấu"}`. Ví dụ xem `projects/chung-khoan/signals.json`.
- `run`: chạy discover rồi analyze liền một lượt. Chỉ nên dùng khi `--name-match` đã đủ chính xác.

**Gợi ý:** chạy analyze hằng tuần rồi so sánh các báo cáo. Đối thủ nào đột ngột tăng số QC hoặc tung nhiều QC mới là đang đẩy mạnh. Cũng nên đối chiếu thêm theo mùa (mùa mưa, mùa xây nhà).

### Nhóm đối thủ, link đích và loại chiến dịch

**Chia nhóm** trong `competitors.txt` bằng dòng `#@ Tên nhóm`:
```
#@ Top 10
108015722146379   # VPS
#@ Xu hướng
197779796755847   # Chứng khoán LPS
```
Nhóm đầu tiên là nhóm chính. Mọi tỉ lệ và nhận định trong report đều tính riêng cho nhóm này, nên một đối thủ chạy rất nhiều QC ở nhóm khác không kéo lệch số liệu. Các nhóm sau có tab riêng. Fanpage không chạy QC vẫn hiện trong bảng (ghi "Không chạy QC"). `winner_pack.py` mặc định chỉ chọn video của nhóm đầu tiên (`--group all` để lấy mọi nhóm).

**Mở link đích** (chạy sau analyze, rồi chạy lại analyze để report cập nhật):
```bash
python3 landing_crawl.py --project chung-khoan
python3 competitor_intel.py analyze --project chung-khoan
```
Script mở từng link bằng trình duyệt mobile, ghi URL cuối sau redirect, loại trang (App Store / Google Play / landing có form / bài viết / Google Form / Zalo…), có Meta Pixel hay không, và chụp màn hình vào `landing/`. Có cache 7 ngày.

**Loại chiến dịch (suy luận):** Ad Library không công bố objective, nên script suy ra từ nút CTA, link và trang đích thật. Kết quả gồm Cài app, Lead form trên FB, Lead/chuyển đổi trên web, Tin nhắn, Traffic (landing / bài viết / form ngoài), Like trang và Tương tác / video view. Mỗi loại được gán vào một tầng phễu (Nhận biết / Cân nhắc / Chuyển đổi). Cột `objective_confidence` trong `all_ads.csv` ghi mức tin cậy cho từng QC. Report có sơ đồ luồng "chủ đề → loại chiến dịch → trang đích" cho từng đối thủ.

**Mẫu và biến thể:** report đếm theo **mẫu** (một thiết kế), không đếm theo từng QC. Hai QC cùng fanpage có thumbnail gần giống nhau được tính là một mẫu, dù caption, nút bấm hay đích khác nhau. Các bản chỉ đổi chữ hoặc con số trên ảnh là **biến thể** của mẫu đó. Với video, script so 2 khung hình (30% và 70% thời lượng), vì khung đầu thường trống. Kết quả nằm ở cột `asset_id` (mẫu) và `variant_id` (biến thể) trong `all_ads.csv`.

**QC đã dừng:** với QC thương mại ở VN, Meta không công bố QC đã dừng. Lọc "đang chạy + đã dừng" vẫn chỉ trả về QC đang chạy (đã thử ngày 28/10/2026).

### Luồng 3: Video thắng và brief (`winner_pack.py`)
Chạy sau bước analyze, vì script dùng lại dữ liệu đã cào.
```bash
python3 winner_pack.py --project tam-lop-poly --include-images
```
1. **Gộp bản trùng.** Đối thủ hay nhân một video thắng thành nhiều quảng cáo. Script gộp các quảng cáo có cùng fanpage và cùng caption thành 1 creative, rồi đếm số bản.
2. **Phân hạng.**
   - **Win chắc**: chạy ≥ 60 ngày, hoặc ≥ 30 ngày và có ≥ 2 bản
   - **Đang lên**: chạy 14–59 ngày, hoặc vừa có bản mới trong 14 ngày
   - **Đang test**: chạy dưới 14 ngày

   Điểm xếp hạng = số ngày × (1 + ln số bản).
3. **Chọn video.** Mặc định lấy 12 video, tối đa 3 video mỗi đối thủ. Đổi bằng `--top` và `--per-page`.
4. **Tạo gói phân tích** cho mỗi video, trong `projects/<project>/winners/<hạng>_<fanpage>_<id>/`:
   - `video.mp4`
   - `hook.jpg`: 6 khung hình trong 3 giây đầu
   - `storyboard.jpg`: các cảnh chính, có ghi mốc thời gian
   - `transcript.txt` / `.srt`: lời thoại, chuyển bằng whisper.cpp ngay trên máy
   - `meta.json`: số liệu và caption
5. **File tổng `winners/index.md`**: bảng xếp hạng tất cả video thắng. Nếu có `--include-images` thì liệt kê thêm QC ảnh thắng.

Nếu link video đã hết hạn, script tự cào lại fanpage đó. Model Whisper được tự tìm (file `ggml-*.bin`), hoặc chỉ định bằng `--whisper-model`.

**Phân tích và viết brief:** mở Claude trong thư mục `ads-crawl` rồi nhắn:
> Phân tích winners của project tam-lop-poly và viết brief

Claude sẽ xem khung hình, đọc lời thoại, rồi viết:
- `winners/analysis.md`: hook, kịch bản, bằng chứng, USP, CTA của từng video, và điểm chung của nhóm thắng
- `brief.md`: các concept mới kèm hook, kịch bản theo giây, shot list, caption và kế hoạch test

### Lưu ý
- Link video của Facebook **hết hạn sau vài ngày**, nên tải ngay chứ đừng chỉ lưu link.
- Cào Ad Library vi phạm điều khoản của Meta. Script **không cần đăng nhập** (đừng chạy bằng tài khoản chính), đã có độ trễ ngẫu nhiên, và chỉ nên chạy vài lần mỗi ngày. Nếu bị chặn thì đổi mạng hoặc đợi vài giờ.
- Nếu Facebook đổi giao diện khiến script trả về 0 quảng cáo, hãy chạy với `--show-browser` để xem trang có đang hiện captcha hoặc lỗi không.
- Chỉ dùng video để **phân tích** (hook, góc tiếp cận, kịch bản). Không đăng lại video của đối thủ.

## Google Ads của đối thủ: `google_ads_intel.py`

Nguồn là Google Ads Transparency Center (adstransparency.google.com). Script gọi API nội bộ của trang, không cần đăng nhập.

```bash
# 1. Tìm nhà quảng cáo (mã AR…) theo tên công ty và domain website
python3 google_ads_intel.py discover --project chung-khoan --browser \
  --keyword "chứng khoán" --keyword "SSI" --domain ssi.com.vn --domain vps.com.vn \
  --name-match "chung khoan|securities"

# 2. Sửa projects/<project>/google_competitors.txt (giống competitors.txt; các mã AR cùng "# Tên ngắn" được gộp làm 1 đối thủ)
# 3. Phân tích
python3 google_ads_intel.py analyze --project chung-khoan --browser
```
Kết quả: `report_google.html`, `google_summary.csv` (mỗi đối thủ 1 dòng), `google_all_ads.csv` (mỗi creative 1 dòng, có link YouTube và tiêu đề video).

- **Nên luôn chạy với `--browser`.** Script mở cửa sổ Chromium. Nếu Google hiện captcha, máy sẽ báo bằng thông báo kèm tiếng chuông: bạn tự giải trong cửa sổ đó, script tự chạy tiếp.
- **Đừng chạy dồn.** Mỗi tuần 1 lần là đủ. Script đã nghỉ 2–4 giây mỗi request và có cache 12 giờ (`--refresh` để bỏ cache).
- "Đang chạy" = creative có lần hiển thị cuối trong 3 ngày gần nhất. "Ngày hiển thị" là số ngày creative thực sự được phân phối.
- Google không công bố từ khoá, ngân sách, lượt hiển thị hay nhắm mục tiêu. QC Search chỉ có ảnh chụp, không có chữ.
- **Nhận xét trong báo cáo** có 2 lớp. Khung "Nhận xét" do script tự tính từ số liệu và tự cập nhật. Khung "Nhận xét của người phân tích" đọc từ `projects/<project>/google_notes.json`, chia theo tên tab (`"Top 10"`, `"Ngoài Top 10"`) rồi theo số mục; khoá `"xu"` là khung xu hướng ở tab nhóm ngoài. Cho phép thẻ `<b>`. Nhớ sửa `_updated` khi viết lại.
- **Bố cục giống báo cáo Facebook** (dựng bằng `google_report.py`). Các tab gồm: Tổng quan · So sánh Top 10 · **Hồ sơ từng đối thủ** (chọn tên ở thanh trên cùng: số liệu, nền tảng, định dạng, nhịp ra mẫu, mẫu đáng học, link tài khoản Transparency và gói winners_google) · **Thư viện creative** (lọc theo đối thủ, nhóm, trạng thái, định dạng, nền tảng) · Nhóm Ngoài Top 10 · Giới hạn dữ liệu. Nhận xét viết tay cho từng hồ sơ nằm ở khoá `"Hồ sơ"` trong `google_notes.json`.
- **Chia nhóm như bản Facebook:** nhóm đầu tiên trong `google_competitors.txt` (dòng `#@ Top 10`) là tab chính. Mọi nhóm sau gộp vào tab "Ngoài Top 10", có khung "Khác gì nhóm Top 10?" để đọc xu hướng.
- **QC không có ảnh** (QC chữ dạng HTML, QC app) được dựng lại thành ảnh khi chạy analyze với `--browser`, hoặc riêng bằng lệnh `python3 google_ads_intel.py previews --project chung-khoan`.
- Dòng `-  # Tên` trong `google_competitors.txt` = đối thủ không có tài khoản Google Ads. Họ vẫn hiện trong báo cáo, ví dụ MBS và Mirae Asset trong Top 10.
- **Xem báo cáo có video YouTube:** chạy `python3 google_ads_intel.py open --project chung-khoan`. Lệnh này mở báo cáo qua `http://localhost:8765`, tắt bằng Ctrl+C. Nếu mở thẳng file `report_google.html` thì YouTube báo **lỗi 153** (YouTube không cho phát video nhúng trong trang mở từ file); khi đó khung xem chỉ hiện ảnh và nút "Xem trên YouTube".
- Bấm vào ảnh bất kỳ để phóng to; QC Search đọc được chữ, có nút "Tải ảnh". Ảnh QC được tải sẵn về `projects/<project>/google/img/`.
- Chỉ sửa nhận xét mà không muốn gọi Google: `python3 google_ads_intel.py report --project chung-khoan` (dựng lại HTML từ cache).

### Video YouTube thắng trên Google (`google_winner_pack.py`)
Chạy sau `google_ads_intel.py analyze`, vì script dùng lại cache, không gọi Transparency Center nữa.
```bash
python3 google_winner_pack.py --project chung-khoan            # 12 video, tối đa 3 mỗi đối thủ, có hiển thị trong 30 ngày
python3 google_winner_pack.py --project chung-khoan --top 20 --per-page 4 --all-time
```
- Gộp theo **ID video YouTube**: một video thường được dùng trong nhiều creative. "Số creative" tương ứng với "số bản" bên Facebook.
- Video được tải bằng `yt-dlp` (720p). Mỗi gói gồm `hook.jpg`, `storyboard.jpg`, `transcript.txt` và `meta.json`, nằm trong `projects/<project>/winners_google/`. File tổng là `index.md`.
- Nhiều QC Google là motion graphic không lời (chỉ có chữ và nhạc). Khi đó thông điệp nằm trong `storyboard.jpg`, không có trong transcript.
