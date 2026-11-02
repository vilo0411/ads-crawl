"""OCR the Transparency Center previews of Google ads (Search text, display banners, video renders).

Output: projects/<project>/google_ocr.json  {creative_id: {"text": ..., "image": ...}}  (cached, incremental).
Needs Tesseract with vie.traineddata; paths via TESSERACT_CMD / TESSDATA_DIR env vars.
"""
import csv, hashlib, json, os, re, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESS = os.environ.get('TESSERACT_CMD', r'C:\Users\loc.nv\AppData\Local\Programs\Tesseract-OCR\tesseract.exe')
TESSDATA = os.environ.get('TESSDATA_DIR', str(Path.home()/'.tessdata'))


def image_path(proj, r):
    u = r['image_url']
    if not u:
        return None
    n = re.sub(r'\D', '', u.rsplit('/', 1)[-1])[:24] or hashlib.md5(u.encode()).hexdigest()[:16]
    p = proj/'google/img'/f'{n}.png'
    return p if p.exists() else None


def ocr(path):
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = TESS
    im = Image.open(path).convert('L')
    im = im.resize((im.width*2, im.height*2))   # small renders read far better upscaled
    text = pytesseract.image_to_string(im, lang='vie', config=f'--tessdata-dir {TESSDATA} --psm 6')
    return ' '.join(text.split())


def main(project='chung-khoan'):
    proj = ROOT/'projects'/project
    out = proj/'google_ocr.json'
    cache = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    rows = list(csv.DictReader(open(proj/'google_all_ads.csv', encoding='utf-8-sig')))
    todo = {}
    for r in rows:
        p = image_path(proj, r)
        if p and r['creative_id'] not in cache:
            todo[r['creative_id']] = p
    print(f'OCR {len(todo)} ảnh (đã có {len(cache)})', flush=True)
    with ProcessPoolExecutor(max_workers=6) as ex:
        for i, (cid, text) in enumerate(zip(todo, ex.map(ocr, todo.values(), chunksize=8))):
            cache[cid] = dict(text=text, image=str(todo[cid].relative_to(ROOT)))
            if i % 100 == 99:
                out.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')
                print(f'  {i+1}/{len(todo)}', flush=True)
    out.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')
    print('xong', len(cache))


if __name__ == '__main__':
    main(*sys.argv[1:])
