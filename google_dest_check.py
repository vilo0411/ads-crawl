"""Which Google creatives link to a company website? (Transparency Center "search by website" filter.)

Google publishes no landing URL, but its creative search accepts a website filter. For every advertiser we
query each candidate root domain; a creative returned for a domain links to that site. Play-labelled videos
never match a web domain, which corroborates them as app-install ads.

Candidates = official domains below + hosts seen in Facebook ad links + hosts read (OCR) on Search previews.
Output: projects/<project>/google_dest.json  {"domains": {competitor: [...]}, "creatives": {creative_id: [domain, ...]}}
"""
import csv, json, re, sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import google_ads_intel as g

ROOT = Path(__file__).resolve().parent
REGION = g.REGIONS['VN']
OFFICIAL = {
    'VPS': ['vps.com.vn'], 'SSI': ['ssi.com.vn'], 'TCBS': ['tcbs.com.vn'], 'Vietcap': ['vietcap.com.vn'],
    'HSC': ['hsc.com.vn'], 'VNDirect': ['vndirect.com.vn'], 'KIS': ['kisvn.vn'], 'VPBankS': ['vpbanks.com.vn'],
    'LPS': ['lpbs.com.vn'], 'Nhất Việt - VFS': ['vfs.com.vn'], 'Shinhan - SSV': ['shinhansec.com.vn', 'vinastalk.vn'],
    'An Bình - ABS': ['abs.vn'], 'Yuanta': ['yuanta.com.vn'], 'DNSE': ['dnse.com.vn', 'entrade.com.vn'],
    'Smart Invest - AAS': ['aas.com.vn'], 'KB Securities': ['kbsec.com.vn'], 'ACBS': ['acbs.com.vn'],
    'Rồng Việt': ['vdsc.com.vn'], 'VCBS': ['vcbs.com.vn'], 'ASEAN': ['aseansc.com.vn'], 'DSC': ['dsc.com.vn'],
    'Pinetree': ['pinetree.vn'], 'SHS': ['shs.com.vn'], 'Thiên Việt - TVS': ['tvs.vn'], 'Kiến Thiết - CSI': ['csi.com.vn'],
}
NOT_WEB = ('facebook.com', 'fb.com', 'fb.me', 'google.com', 'apple.com', 'bit.ly', 'zoom.us', 'go.link', 'onelink.me',
           'forms.gle', 'cafef.vn')
HOST = re.compile(r'\b((?:[a-z0-9-]+\.)+(?:com\.vn|vn|com|net))\b')


def root(host):
    host = host.lower().removeprefix('www.')
    parts = host.split('.')
    return '.'.join(parts[-3:] if host.endswith('.com.vn') else parts[-2:])


def candidates(proj, rows):
    out = defaultdict(set)
    for comp, doms in OFFICIAL.items():
        out[comp].update(doms)
    ocr_path = proj/'google_ocr.json'
    ocr = json.loads(ocr_path.read_text(encoding='utf-8')) if ocr_path.exists() else {}
    for r in rows:   # hosts printed on Search previews (display URL)
        if r['format'].startswith('Chữ') and r['creative_id'] in ocr:
            for h in HOST.findall(ocr[r['creative_id']]['text'].lower()):
                out[r['competitor']].add(root(h))
    import build_executive_report as base   # hosts of the same company's Facebook ad links
    gname = {b[0]: b[2] for b in base.BRANDS}
    for b in base.build_data()['profiles']:
        for r in b['fb']:
            for u in (r['final_url'], r['link_url']):
                h = urlparse(u or '').netloc
                if h and '.' in h:
                    out[gname[b['name']]].add(root(h))
    return {c: sorted(d for d in v if not any(d.endswith(x) for x in NOT_WEB)) for c, v in out.items()}


def main(project='chung-khoan'):
    proj = ROOT/'projects'/project
    rows = list(csv.DictReader(open(proj/'google_all_ads.csv', encoding='utf-8-sig')))
    out_path = proj/'google_dest.json'
    done = json.loads(out_path.read_text(encoding='utf-8')) if out_path.exists() else {'domains': {}, 'queried': [], 'creatives': {}}
    cands = candidates(proj, rows)
    advertisers = sorted({(r['competitor'], r['advertiser_id']) for r in rows})
    for comp, aid in advertisers:
        for dom in cands.get(comp, []):
            key = f'{aid}|{dom}'
            if key in done['queried']:
                continue
            items = g.search_creatives(REGION, advertiser=aid, domain=dom, max_items=2000)
            for c in items:
                done['creatives'].setdefault(c['2'], [])
                if dom not in done['creatives'][c['2']]:
                    done['creatives'][c['2']].append(dom)
            done['queried'].append(key)
            print(f'{comp:20s} {dom:22s} {len(items)}', flush=True)
            out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding='utf-8')
    done['domains'] = cands
    out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding='utf-8')
    matched = sum(r['creative_id'] in done['creatives'] for r in rows)
    print(f'xong: {matched}/{len(rows)} creative dẫn về một domain web')


if __name__ == '__main__':
    main(*sys.argv[1:])
