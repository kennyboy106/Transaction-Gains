import pymupdf
import os
import fitz

from enum import Enum
class Months(Enum):
    january = 1
    february = 2
    march = 3
    april = 4
    may = 5
    june = 6
    july = 7
    august = 8
    september = 9
    october = 10
    november = 11
    december = 12


def extract_all(doc: pymupdf.Document, output, page_num: int):

    page = doc[page_num - 1]
    ret = page.get_text('words', sort=True)

    for i, word in enumerate(ret):
        text = word[4]
        output.write(str(i) + ' ' + text + '\n')

if __name__ == '__main__':

    
    try:
        os.remove('output.txt')
    except:
        pass
    output = open('output.txt', 'a')
    doc = pymupdf.open('bad_Schwab_Brokerage Statement_2024-08-31_615.PDF')

    extract_all(doc, output, 1)
    doc.close()
    output.close()
