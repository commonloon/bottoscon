"""
Generate printable QR-code PDFs for the tables.

    pip install -r requirements-tools.txt
    export TABLE_USAGE_CSV_URL=...  ORGANIZER_GAMES_CSV_URL=...   # same as the app (to read the table list)
    python tools/make_qr.py --base-url https://bottoscon-app-xxxx.run.app

writes a folder (default: table_qr_codes/) containing
    <TABLE>.pdf      one single-page PDF per table, named after the table
    00_ALL_TABLES.pdf   every table, one table per page

Each code links to <base-url>/table/<table id>. Keep the base URL stable once
codes are printed. To skip the sheets and name the tables yourself:

    python tools/make_qr.py --base-url https://... --tables NW01,NW02,SE09
"""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import quote

import segno
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ALL_FILENAME = '00_ALL_TABLES.pdf'
QR_SIZE = 5.5 * inch          # includes the 4-module quiet zone
QUIET_MODULES = 4


def load_tables(names):
    """[(table id, type)] from --tables, or from the Table Usage sheet."""
    if names:
        return [(n.strip(), '') for n in names.split(',') if n.strip()]
    import tables as tables_mod
    return [(t.id, t.type) for t in tables_mod.get_table_data().tables]


def safe_filename(table_id):
    return re.sub(r'[^A-Za-z0-9._-]', '_', table_id) + '.pdf'


def draw_qr(c, url, center_x, top_y, size):
    """Draw `url` as a vector QR code (one filled path, so no hairline seams)."""
    matrix = segno.make(url, error='m', boost_error=False).matrix
    modules = len(matrix)
    module = size / (modules + 2 * QUIET_MODULES)
    left = center_x - size / 2 + QUIET_MODULES * module
    top = top_y - QUIET_MODULES * module
    path = c.beginPath()
    for row_idx, row in enumerate(matrix):
        for col_idx, dark in enumerate(row):
            if dark:
                path.rect(left + col_idx * module, top - (row_idx + 1) * module, module, module)
    c.setFillColorRGB(0, 0, 0)
    c.drawPath(path, stroke=0, fill=1)


def draw_page(c, table_id, table_type, url):
    """One table per page (letter, portrait)."""
    width, height = letter
    cx = width / 2

    font_size = 96
    while stringWidth(table_id, 'Helvetica-Bold', font_size) > width - 1.2 * inch and font_size > 24:
        font_size -= 4
    c.setFillColorRGB(0, 0, 0)
    c.setFont('Helvetica-Bold', font_size)
    c.drawCentredString(cx, height - 1.9 * inch, table_id)
    if table_type:
        c.setFont('Helvetica', 28)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.drawCentredString(cx, height - 2.5 * inch, table_type)

    qr_top = height - 2.8 * inch
    draw_qr(c, url, cx, qr_top, QR_SIZE)

    c.setFillColorRGB(0, 0, 0)
    c.setFont('Helvetica-Bold', 24)
    c.drawCentredString(cx, qr_top - QR_SIZE - 0.45 * inch, "Scan to see this table's schedule")
    c.setFont('Helvetica', 14)
    c.drawCentredString(cx, qr_top - QR_SIZE - 0.85 * inch, 'and find open tables for a pickup game')
    c.setFont('Helvetica', 10)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(cx, 0.6 * inch, url)
    c.showPage()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', required=True, help='public URL of the app')
    ap.add_argument('--tables', help='comma-separated table ids (default: read the Table Usage sheet)')
    ap.add_argument('--out-dir', default='table_qr_codes')
    args = ap.parse_args()

    base = args.base_url.rstrip('/')
    if not base.startswith(('http://', 'https://')):
        sys.exit('--base-url must start with http:// or https://')
    tables = load_tables(args.tables)
    if not tables:
        sys.exit('No tables found')

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_canvas = canvas.Canvas(str(out_dir / ALL_FILENAME), pagesize=letter)
    all_canvas.setTitle('BottosCon table QR codes')

    for table_id, table_type in tables:
        url = f'{base}/table/{quote(table_id)}'
        single = canvas.Canvas(str(out_dir / safe_filename(table_id)), pagesize=letter)
        single.setTitle(f'Table {table_id}')
        draw_page(single, table_id, table_type, url)
        single.save()
        draw_page(all_canvas, table_id, table_type, url)
    all_canvas.save()
    print(f'Wrote {len(tables)} table PDFs plus {ALL_FILENAME} to {out_dir}/')


if __name__ == '__main__':
    main()
