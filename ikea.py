# encoding: utf-8

import re
import os
import sys
import subprocess
import random
import tempfile
import json
import gzip
import codecs
import requests
from PyPDF2 import PdfFileReader
import cv2
import numpy as np
from lxml import etree

ROOT_PATH = os.path.dirname(os.path.abspath(__file__)) + '/'

PRODUCT_NAME_RE = re.compile(u'([ÅÄÖA-Z/]+)')
LETTER_RE = re.compile(('[^\W\d]'))


CONTROL_CHARS = range(0, 31)
regex_str = \
    '[' +  \
        ''.join(r'\x' + hex(n)[2:].zfill(2) for n in CONTROL_CHARS) + \
    ']|</?[bi]>'
RE_STRIP_XML = re.compile(regex_str)

def strip_control_chars_and_tags(s):
    return RE_STRIP_XML.sub('', s)

def get_diagrams(png_filename, xml_filename):
    # img = cv2.imread(fname)
    img = cv2.imread(png_filename, 0)
    ret, gray = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)

    # Remove text from gray image
    xml_data = open(xml_filename).read()

    # Fix malformed input in xml. Bug in pdftohtml
    # https://bugs.freedesktop.org/show_bug.cgi?id=24890
    xml_data = strip_control_chars_and_tags(xml_data)

    tree = etree.fromstring(xml_data)
    page_elem = tree.xpath('//page')[0]
    page_width = int(page_elem.attrib['width'])
    page_height = int(page_elem.attrib['height'])

    vertical_scale = float(img.shape[0]) / page_height
    horizontal_scale = float(img.shape[1]) / page_width

    for text_elem in tree.xpath('//text'):
        top = int(vertical_scale * int(text_elem.attrib['top']))
        height = int(vertical_scale * int(text_elem.attrib['height']))
        left = int(horizontal_scale * int(text_elem.attrib['left']))
        width = int(horizontal_scale * int(text_elem.attrib['width']))
        top_left = (left, top)
        bottom_right = (left+width, top+height)
        cv2.rectangle(gray, top_left, bottom_right, 0, -1)


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

    radius = 15
    kernel = np.zeros((2*radius+1, 2*radius+1), np.uint8)
    y,x = np.ogrid[-radius:radius+1, -radius:radius+1]
    mask = x**2 + y**2 <= radius**2
    kernel[mask] = 1
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

#ASSEMBLY_FILES = get_assembly_files()

# Load a smaller file with just the assembly files
ASSEMBLY_FILES = json.load(codecs.getreader("utf-8")(gzip.open(ROOT_PATH + 'ikea/ikea_assembly_files.json.gz')))

def get_ikea_product():
    assembly_url = random.choice(ASSEMBLY_FILES.keys())
    product_name = ASSEMBLY_FILES[assembly_url]
    print product_name, assembly_url

    pdf_fname = tempfile.mkstemp(prefix='tmp_instruction_bot', suffix='.pdf')[1]

    with open(pdf_fname, 'w') as f:
        r = requests.get('http://www.ikea.com' + assembly_url)
        if r.status_code != 200:
            print u'ERROR: File returned status code {}: {}'.format(r.status_code, assembly_url)
            return None, None
        f.write(r.content)

    diagrams = get_diagrams_from_file(pdf_fname)
    os.unlink(pdf_fname)

    if not diagrams:
        return None, None

    chosen_diagram = random.choice(diagrams)

    output_filename = tempfile.mkstemp(prefix='tmp_instruction_bot', suffix='.png')[1]
    cv2.imwrite(output_filename, chosen_diagram)

    return product_name, output_filename

def get_diagrams_from_file(pdf_fname):
    with open(pdf_fname, 'rb') as f:
        pdf_doc = PdfFileReader(f)
        total_pages = pdf_doc.getNumPages()

    diagrams = []

    png_fname = tempfile.mkstemp(prefix='tmp_instruction_bot', suffix='.png')[1]
    xml_metadata_fname = tempfile.mkstemp(prefix='tmp_instruction_bot', suffix='.xml')[1]

    # pdftocairo bug, appending a suffix despite -singlefile
    png_fname_no_suffix = png_fname[:-4]

    for page_number in range(1, total_pages+1):
        page_number_str = str(page_number)
        subprocess.call(['pdftocairo', '-f', page_number_str, '-l', page_number_str,
            '-png', '-singlefile', '-scale-to', '1241', '-gray', pdf_fname, png_fname_no_suffix])
        subprocess.call(['pdftohtml', '-f', page_number_str, '-l', page_number_str,
            '-xml', '-i', pdf_fname, xml_metadata_fname],
            stdout=open(os.devnull),
            stderr=open(os.devnull))

        print 'Fetching diagrams from page', page_number, '...',
        page_diagrams = get_diagrams(png_fname, xml_metadata_fname)
        diagrams.extend(page_diagrams)
        print 'found', len(page_diagrams)
    os.unlink(png_fname)
    os.unlink(xml_metadata_fname)

    return diagrams

if __name__ == '__main__':
    for diagram in get_diagrams_from_file(sys.argv[1]):
        cv2.imshow('IMG', diagram)
        cv2.waitKey(0)
