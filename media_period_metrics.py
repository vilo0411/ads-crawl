"""Chỉ số theo kỳ cho báo cáo media tổng hợp chứng khoán (đọc CSV của từng kỳ crawl).

Kỳ 29/10 nằm ở gốc projects/chung-khoan, các kỳ sau ở projects/chung-khoan/crawl-YYYY-MM-DD.
"""
import csv
import json
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent/'projects/chung-khoan'
PERIODS = [('29/10', PROJ), ('11/11', PROJ/'crawl-2026-11-11'), ('22/11', PROJ/'crawl-2026-11-22')]

# Tên công ty dùng trong báo cáo, Page ID Meta, tên trong google_all_ads.csv
TOP10 = [('VPS', '108015722146379', 'VPS'), ('SSI', '132771703438783', 'SSI'), ('TCBS', '1504697249783367', 'TCBS'),
         ('Vietcap', '343028851058', 'Vietcap'), ('HSC', '1517153298580277', 'HSC'), ('MBS', '349312325177779', None),
         ('VNDirect', '123434971018658', 'VNDirect'), ('KIS', '561500030387546', 'KIS'),
         ('Mirae Asset', '303619527172219', None), ('VPBankS', '107578535212906', 'VPBankS')]
TREND = [('LPS', '197779796755847', 'LPS'), ('VFS', '273872576046675', 'Nhất Việt - VFS'),
         ('Shinhan / SSV', '101384519398514', 'Shinhan - SSV'), ('ABS', '390676534851790', 'An Bình - ABS'),
         ('Yuanta', '131656534155296', 'Yuanta'), ('DNSE', '2033102266712313', 'DNSE'),
         ('AAS', '1197026010336908', 'Smart Invest - AAS'), ('KBSV', '458482900870297', 'KB Securities'),
         ('ACBS', '107317735256838', 'ACBS'), ('Rồng Việt', '134188476770555', 'Rồng Việt'),
         ('TPS', '2070825876552556', None), ('KIRIN', '106218628765203', None), ('TVSI', '171970319483394', None),
         ('HD Securities', '1112132331974304', None), ('VCBS', '151091451760284', 'VCBS')]
GOOGLE_ONLY = ['DSC', 'Thiên Việt - TVS', 'ASEAN', 'Pinetree', 'SHS', 'Kiến Thiết - CSI']


def rows(p):
    return list(csv.DictReader(open(p, encoding='utf-8-sig')))


class Period:
    def __init__(self, label, d):
        self.label, self.d = label, d
        self.meta = rows(d/'all_ads.csv')
        summ = rows(d/'competitors_summary.csv')
        name2id = {r['page_name']: r['page_id'] for r in summ}
        for r in self.meta:
            r['pid'] = name2id.get(r['page_name'], '')
        self.summary = {r['page_id']: r for r in summ}
        self.google = rows(d/'google_all_ads.csv')
        snap = d/'report_snapshot.json'
        self.snapshot = json.load(open(snap)) if snap.exists() else {}

    # Meta
    def meta_ids(self, pid=None):
        return {r['ad_archive_id'] for r in self.meta if pid is None or r['pid'] == pid}

    def meta_count(self, pid):
        return sum(r['pid'] == pid for r in self.meta)

    def fanpages_with_data(self):
        return len({r['pid'] for r in self.meta})

    def formats(self):
        return Counter(r['format'] for r in self.meta)

    def funnel(self, group):
        c = Counter(r['stage'] for r in self.meta if r['group'] == group)
        n = sum(c.values()) or 1
        return [round(100*c[s]/n) for s in ('Nhận biết', 'Cân nhắc', 'Chuyển đổi')]

    # Google
    def g_active(self, comp=None):
        return sum(r['active'] == 'True' and (comp is None or r['competitor'] == comp) for r in self.google)

    def g_total(self, comp=None):
        return sum(comp is None or r['competitor'] == comp for r in self.google)

    @staticmethod
    def is_app(r):
        return 'Play' in r['platforms'] and r['format'] in ('Ảnh', 'Video')

    def app(self, comp=None, active=False):
        return sum(self.is_app(r) and (comp is None or r['competitor'] == comp)
                   and (not active or r['active'] == 'True') for r in self.google)


def load():
    return [Period(l, d) for l, d in PERIODS]


if __name__ == '__main__':
    ps = load()
    for p in ps:
        print(p.label, 'meta', len(p.meta), 'pages', p.fanpages_with_data(), 'g', p.g_total(), p.g_active(),
              'app', p.app(), p.app(active=True), dict(p.formats()), p.funnel('Top 10'), p.funnel(ps[0].meta[0]['group'] if False else 'Xu hướng'))
    for name, pid, g in TOP10 + TREND:
        print(f'{name:15}', ' → '.join(str(p.meta_count(pid)) for p in ps), '|',
              ' → '.join(str(p.g_active(g)) for p in ps) if g else '—', '| app', [p.app(g, True) for p in ps] if g else '')
    for g in GOOGLE_ONLY:
        print(f'{g:15}', [p.g_total(g) for p in ps], [p.g_active(g) for p in ps])


# ---- Tập gộp nhiều kỳ (mỗi ID một lần, bản ghi kỳ mới hơn được dùng) ----
from urllib.parse import urlparse

DEST_ORDER = ['Kho ứng dụng', 'Web và điểm đến khác', 'Link chuyển hướng app', 'Không ghi nhận URL',
              'Facebook / sự kiện', 'Tin nhắn', 'Biểu mẫu ngoài']


def dest_class(r):
    url = r['link_url'].strip()
    h = urlparse(url).netloc.lower() if url else ''
    if r['dest'] == 'Messenger' or 'm.me' == h:
        return 'Tin nhắn'
    if not h:
        return 'Facebook / sự kiện' if r['format'] == 'Sự kiện' else 'Không ghi nhận URL'
    if h in ('play.google.com', 'itunes.apple.com', 'apps.apple.com'):
        return 'Kho ứng dụng'
    if h.endswith('onelink.me') or h.endswith('go.link') or h.endswith('app.link') or 'adjust' in h:
        return 'Link chuyển hướng app'
    if h in ('forms.gle', 'docs.google.com'):
        return 'Biểu mẫu ngoài'
    if r['dest'].startswith('Facebook') or r['format'] == 'Sự kiện':
        return 'Facebook / sự kiện'
    return 'Web và điểm đến khác'


def union_meta(periods):
    u = {}
    for p in periods:
        for r in p.meta:
            u[r['ad_archive_id']] = r
    return list(u.values())


def union_google(periods):
    u = {}
    for p in periods:
        for r in p.google:
            u[r['creative_id']] = r
    return list(u.values())
