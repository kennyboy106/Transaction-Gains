import pymupdf
from enum import Enum
'''
To make a proper api I need to make an overall function that can call many smaller functions when needed
smaller functions should be like:
    Get account number
    Get account value
    Get xxx
Large function should return a dictionary of all values that might be needed
Maybe the larger functions can just return certain values that are determined by key word arguments passed in.
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
    
    # Get all page text
    ret = page.get_text('words', sort=True)

    prev_period_value = None
    cur_period_value = None
    acc_number = None
    short_term_net_gains = None
    short_term_net_gains_YTD = None
    long_term_net_gains = None
    long_term_net_gains_YTD = None
    
    page_flag = False
    
    for i, word in enumerate(ret):
        text = word[4]

        '''
        Getting the account value, I need to ensure that I associate the value with the account number
        
        1. Get the account number on the page
        2. Try getting all information if it hasn't already been acquired with that account number
        '''
        # Ensure this page has relevant info 
        if 'Acct' in text:
            try:
                acc_number = ret[i + 2][4]  # Get the account number which should be after the following # sign
                acc_number = acc_number.replace(')', '')    # Remove the ) that follows
                acc_number = acc_number[-4:]    # Keep only the last 4 numbers of the account
                if int(acc_number):
                    page_flag = True
            
            except:
                pass
        
        # Nothing on this page pertaining to this account? Go to the next page
        # But if we did get the account number earlier, don't skip the page
        if page_flag:
            
            # Extract the statement ending date #
            # If we haven't gotten the year yet
            if not year and text == 'Statement':
                try:
                    if ret[i + 1][4] == 'Period:':
                        month = ret[i + 2][4].lower()
                        day = ret[i + 6][4][:-1]
                        year = ret[i + 7][4]
                        if Months[month] and int(day) and int(year):
                            print('Date acquired')
                except:
                    # Reset if we had any errors
                    month, day, year = (None,) * 3
            
            # Extract the previous period value and current value
            if not cur_period_value and text == 'TOTAL':
                try:
                    if ret[i + 1][4] == 'ACCOUNT' and ret[i + 2][4] == 'VALUE':
                        prev_period_value = ret[i + 3][4].replace('$', '')
                        cur_period_value = ret[i + 4][4].replace('$', '')
                        prev_period_value = float(prev_period_value)
                        cur_period_value = float(cur_period_value)
                except:
                    cur_period_value = prev_period_value = None
            
            # Extract the short term gains
            if not short_term_net_gains and text == 'Short-Term':
                try:
                    if ret[i + 1][4] == 'Net' and ret[i + 2][4] == 'Gain':
                        short_term_net_gains = ret[i + 5][4].replace('$', '')
                        short_term_net_gains_YTD = ret[i + 6][4].replace('$', '')
                        short_term_net_gains = float(short_term_net_gains)
                        short_term_net_gains_YTD = float(short_term_net_gains_YTD)
                except:
                    short_term_net_gains = short_term_net_gains_YTD = None
            
            # Extract the long term gains
            if not long_term_net_gains and text == 'Long-Term':
                try:
                    if ret[i + 1][4] == 'Net' and ret[i + 2][4] == 'Gain':
                        long_term_net_gains = ret[i + 5][4].replace('$', '')
                        long_term_net_gains_YTD = ret[i + 6][4].replace('$', '')
                        long_term_net_gains = float(long_term_net_gains)
                        long_term_net_gains_YTD = float(long_term_net_gains_YTD)
                except:
                    long_term_net_gains = long_term_net_gains_YTD = None

    # Check and save for any info collected with account number
    if page_flag and (type(prev_period_value) == float or short_term_net_gains):
        print(f'Information found')
        print(f'Account number: {acc_number}')
        print(f'Statement date: {Months[month].value}/{int(day)}/{int(year)}')
        print(f'Previous value: {prev_period_value}')
        print(f'Current value: {cur_period_value}')
        print(f'Short-term net gains: {short_term_net_gains} {short_term_net_gains_YTD}')
        print(f'Long-term net gains: {long_term_net_gains} {long_term_net_gains_YTD}')
