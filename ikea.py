# encoding: utf-8

import re
import os
import subprocess
import random
import tempfile
import json
import gzip
import codecs
from StringIO import StringIO
import requests
from PyPDF2 import PdfFileReader
import cv2
import numpy as np
import cairosvg

ROOT_PATH = os.path.dirname(os.path.abspath(__file__)) + '/'

PRODUCT_NAME_RE = re.compile(u'([ÅÄÖA-Z/]+)')
LETTER_RE = re.compile(('[^\W\d]'))

def get_diagrams(png_image):
    # img = cv2.imread(fname)
    data = np.fromstring(png_image.getvalue(), dtype=np.uint8)
    img = cv2.imdecode(data, -1)

    # Turning alpha to white
    channels = cv2.split(img)
    inverted_alpha = ~channels[3]
    channels[0] |= inverted_alpha
    channels[1] |= inverted_alpha
    channels[2] |= inverted_alpha
    img = cv2.merge(channels[:3])

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, gray = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Remove borders

    linek = np.zeros((11,11), dtype=np.uint8)
    linek[5, ...] = 1
    x = cv2.morphologyEx(gray, cv2.MORPH_OPEN, linek, iterations=1)
    x = cv2.dilate(x, np.ones((9, 9), np.uint8))
    linek = np.zeros((11,11), dtype=np.uint8)
    linek[..., 5] = 1
    y = cv2.morphologyEx(gray, cv2.MORPH_OPEN, linek, iterations=1)
    y = cv2.dilate(y, np.ones((9, 9), np.uint8))
    gray_squares = ~(x | y)
    contours, hier = cv2.findContours(gray_squares, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    squares = []
    for cnt in contours:
        approx = cv2.approxPolyDP(cnt, cv2.arcLength(cnt, closed=True)*0.02, closed=True)
        if len(approx) == 4 and cv2.contourArea(cnt) > 40000 and cv2.isContourConvex(cnt):
            squares.append(approx)
    for square in squares:
        # cv2.drawContours(img, [square], 0, (255, 0, 255), 1)
        cv2.drawContours(gray, [square], 0, (0, 0, 0), 12)
        cv2.drawContours(img, [square], 0, (255, 255, 255), 5)

    kernel = np.ones((3, 3),np.uint8)
    for i in range(10):
        gray = cv2.dilate(gray, kernel)

    contours, hier = cv2.findContours(gray, cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE, (0, 0))

    def good_contour(c):
        x, y, w, h = cv2.boundingRect(c)
        if w > 170 and h > 170 and not (h in [247, 248] and w in [726, 727]):
            return True
        else:
            return False

    contours = [c for c in contours if good_contour(c)]

    diagrams = []
    for cnt in contours:
        (x, y, w, h) = cv2.boundingRect(cnt)
        roi = img[y:y+h, x:x+w]

        mask = np.zeros(roi.shape, np.uint8)
        cv2.drawContours(mask, [cnt - [x, y]], 0, (255, 255, 255), -1)

        new_image = roi & mask | (~mask)
        diagrams.append(new_image)

    return diagrams


def is_text_page(filename, page_number):
    # This skips a few pages that have text AND images
    page_number = str(page_number)
    text = subprocess.check_output(['pdftotext', '-f', page_number, '-l', page_number,
        filename, '-'])
    return len(LETTER_RE.findall(text)) > 60


def extract_product_name(s):
    if s.startswith('IKEA 365+'):
        s = s[len('IKEA 365+'):]
    match = PRODUCT_NAME_RE.match(s)
    if not match:
        return None, None
    product_name = match.groups()[0]
    return product_name

def get_assembly_files():
    reader = codecs.getreader("utf-8")
    ikea_catalog = json.load(reader(gzip.open(ROOT_PATH + 'ikea/ikea_catalog.json.gz')))

    assemblies = {}

    for product_id, info in ikea_catalog.iteritems():
        if 'IKEA' in info.get('product_name', ''):
            continue
        product_data = info.get('product_data')
        if not product_data:
            continue
        for item in product_data['product'].get('items', []):
            for attachment in item.get('attachments', []):
                for atch in attachment.get('atcharray', []):
                    if atch['attachmentPath'].startswith('/us/en/assembly_instructions'):
                        assemblies[atch['attachmentPath']] = extract_product_name(atch['attachmentName'])
    return assemblies

ASSEMBLY_FILES = get_assembly_files()

def get_ikea_product():
    assembly_url = random.choice(ASSEMBLY_FILES.keys())
    product_name = ASSEMBLY_FILES[assembly_url]
    print product_name, assembly_url

    pdf_fname = tempfile.mkstemp(prefix='tmp_instruction_bot', suffix='.pdf')[1]

    with open(pdf_fname, 'w') as f:
        r = requests.get('http://www.ikea.com' + assembly_url)
        f.write(r.content)

    # Parse PDF
    with open(pdf_fname, 'rb') as f:
        pdf_doc = PdfFileReader(f)
        total_pages = pdf_doc.getNumPages()

    diagrams = []

    temp_filename = tempfile.mkstemp(prefix='tmp_instruction_bot')[1]

    for page_number in range(2, total_pages+1):
        if is_text_page(pdf_fname, page_number):
            print 'skipping text page', page_number
            continue

        subprocess.call(['pdftocairo', '-f', str(page_number), '-l', str(page_number),
            '-svg', pdf_fname, temp_filename])

        png_image = StringIO()

        with open(temp_filename) as f_in:
            cairosvg.svg2png(file_obj=f_in, write_to=png_image)

        print 'Fetching diagrams from page', page_number, '...',
        page_diagrams = get_diagrams(png_image)
        diagrams.extend(page_diagrams)
        print 'found', len(page_diagrams)
    os.unlink(pdf_fname)

    if not diagrams:
        os.unlink(temp_filename)
        return None, None

    chosen_diagram = random.choice(diagrams)

    output_filename = temp_filename + '.png'
    cv2.imwrite(output_filename, chosen_diagram)

    return product_name, output_filename

