"""Design system DSC dùng chung cho mọi báo cáo HTML.

Nguồn: https://claude.ai/artifact/22k27xbh7rBryUcMrDZoH4 (tokens.json + README).
Quy tắc chính: chữ trên Lime Green / Emerald luôn là Gunmetal; Lime Green / Emerald không làm màu chữ
trên nền trắng (dùng --accent-text); khối vuông, chia vùng bằng đường kẻ mảnh, không gradient, không bóng đổ.
Nền, chữ phụ, chip, đường kẻ dùng xám trung tính; màu xanh chỉ dành cho nút đang chọn, biểu đồ, link, heatmap.
"""

FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
             '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,600;0,700;1,400'
             '&display=swap" rel="stylesheet">')

# Màu brand (RGB) cho ảnh sinh bằng PIL
GUNMETAL = (39, 45, 43)
FROSTED_MINT = (140, 255, 204)

# Theme tối: nền xám than trung tính (họ Gunmetal) thay cho Gunmetal/Pine Teal ngả xanh, để màu xanh chỉ còn ở điểm nhấn
_DARK = ("--surface:#1c1f1e;--surface-alt:#242827;--ink:var(--white);--ink-muted:#b3b9b7;"
         "--hairline:#3a403e;--line:rgba(255,255,255,.12);--track:rgba(255,255,255,.08);--chip:#323736;"
         "--accent-text:var(--lime-green);--bar-2:#b3b9b7;--heat-max:45%;color-scheme:dark")

BASE_CSS = """
:root{--gunmetal:#272d2b;--pine-teal:#1d4130;--lime-green:#2ad03d;--emerald:#1bbe72;--frosted-mint:#8cffcc;--white:#ffffff;--mint-50:#eafff4;
--surface:var(--white);--surface-alt:#f3f4f4;--ink:var(--gunmetal);--ink-muted:#5b6260;--hairline:var(--gunmetal);
--line:rgba(39,45,43,.14);--track:rgba(39,45,43,.08);--chip:#eceeed;
--primary:var(--lime-green);--on-primary:var(--gunmetal);--accent:var(--emerald);--accent-text:var(--pine-teal);--bar-2:#5b6260;
--heat:var(--lime-green);--heat-max:55%;
--font-sans:"Plus Jakarta Sans",system-ui,sans-serif;--space-1:8px;--space-2:16px;--space-3:24px;--space-4:48px;
--radius-sm:4px;--radius-md:8px;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){%DARK%}}
:root[data-theme=dark]{%DARK%}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);font:400 15px/1.5 var(--font-sans);-webkit-font-smoothing:antialiased}
h1{font-size:32px;line-height:1.2;font-weight:700;letter-spacing:-.01em;margin:0 0 var(--space-1)}
h2{font-size:20px;line-height:1.3;font-weight:600;margin:var(--space-4) 0 var(--space-2);padding-bottom:var(--space-1);border-bottom:1px solid var(--hairline)}
h3{font-size:15px;line-height:1.5;font-weight:700;margin:var(--space-3) 0 var(--space-1)}
h4{font-size:14px;line-height:1.45;font-weight:600;color:var(--ink-muted);margin:var(--space-2) 0 var(--space-1)}
a{color:var(--accent-text);text-underline-offset:2px}
b,strong{font-weight:700}
code{font-size:13px;background:var(--chip);padding:1px 6px;border-radius:var(--radius-sm)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:var(--space-1);border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--ink-muted);font-weight:600;white-space:nowrap;border-bottom-color:var(--hairline)}
:focus-visible{outline:2px solid var(--accent-text);outline-offset:2px}
.brand-strip{display:flex;height:8px}.brand-strip i{display:block}
footer.foot{display:flex;justify-content:space-between;gap:var(--space-2);flex-wrap:wrap;border-top:1px solid var(--hairline);
margin-top:var(--space-4);padding-top:var(--space-2);font-size:14px;font-weight:600;color:var(--ink-muted)}
""".replace("%DARK%", _DARK)

# Dải khối màu thương hiệu ở đầu trang (lấy từ cover của design system)
BRAND_STRIP = ('<div class="brand-strip" aria-hidden="true">'
               + "".join(f'<i style="flex:{f};background:var(--{c})"></i>' for c, f in
                         [("gunmetal", 3), ("pine-teal", 2), ("lime-green", 4.5), ("emerald", 2.5), ("frosted-mint", 2.5)])
               + "</div>")


def footer(left, right):
    return f'<footer class="foot"><span>{left}</span><span>{right}</span></footer>'
