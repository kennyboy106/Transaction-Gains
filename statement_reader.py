import pymupdf
from enum import Enum
'''
To make a proper api I need to make an overall function that can call many smaller functions when needed
smaller functions should be like:
    Get account number
    Get account value
    Get xxx
Large function should return a dictionary of all values that might be needed
Maybe the larger functions can just return certain values that are determined by key word agruments passed in.
    If n keywords are passed in then n things are returned from the document
'''



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

def chase_statement_extract(filename: str):

    # Open the document given
    doc: pymupdf.Document = pymupdf.open(filename)

    

def chase_single_account_number(doc: pymupdf.Document):
    area_account_number = pymupdf.Rect()


doc = pymupdf.open('chase_multi_20240831-statements-8722-.pdf')

month, day, year = (None,) * 3

for page in doc:
    # Get account number
    # Get period value
    # Get current value
    # Get capital gains
    ret = page.get_text('words', sort=True)

    prev_period_value = 0
    cur_period_value = 0
    acc_number = None
    short_term_net_gains = 0
    long_term_net_gains = 0
    
    
    
    for i, word in enumerate(ret):
        text = word[4]

        '''
        Getting the account value, I need to ensure that I associate the value with the account number
        
        1. Get the account number on the page
        2. Try getting all information if it hasn't already been acquired with that account number
        '''
        
        # if 'Acct' in text:
        #     # Do stuff for this account page
        #     pass
        
        # # Nothing on this page? Go to the next page
        # else:
        #     break
        



# -------------------- # Extract the statement ending date # ---------------- #
        if not year and text == 'Statement':
            try:
                if ret[i + 1][4] == 'Period:':
                    month = ret[i + 2][4].lower()
                    day = ret[i + 6][4][:-1]
                    year = ret[i + 7][4]
                    if Months[month] and int(day) and int(year):
                        print('Date acquired')
            except:
                month, day, year = (None,) * 3
        