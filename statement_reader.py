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
    '''
    Extracts information from chase brokerage statements using pymupdf library.

    Parameters
    filename: The name of the statement pdf file

    Returns
    statement_data: dict: A nested dictionary containing keys for each account found 
    as the last 4 digits of the account number. 
    
    Each account key has a dictionary that contains the following:
    date: Ending statement date
    prev_period_val: Account value at the end of the previous period
    cur_period_val: Account value at the end of the current period
    short_net: Net short term capital gains this period
    short_net_YTD: Net short term capital gains this year
    long_net: Net long term capital gains this period
    long_net_YTD: Net long term capital gains this year
    '''

    # Open the document given
    doc: pymupdf.Document = pymupdf.open(filename)

    # Dictionary to hold account data extracted
    statement_data = {}

    # Declare for later. Outside of for loop as the statement 
    # will only contain one date repeated many times
    month, day, year, date = (None,) * 4

    for page in doc:

        # Get all page text
        ret = page.get_text('words', sort=True)

        # Declare variables that can be extracted in a page
        prev_period_value = None
        cur_period_value = None
        acc_number = None
        short_term_net_gains = None
        short_term_net_gains_YTD = None
        long_term_net_gains = None
        long_term_net_gains_YTD = None

        # Used to indicate if a page is relevant or not
        page_flag = False

        # Go through all words in the page
        for i, word in enumerate(ret):
            text = word[4]

            # Ensure this page has relevant info to a specific account
            if 'Acct' in text:
                try:
                    acc_number = ret[i + 2][4]                  # Get the account number which should be after the following # sign
                    acc_number = acc_number.replace(')', '')    # Remove the ) that follows
                    acc_number = acc_number[-4:]                # Keep only the last 4 numbers of the account
                    if int(acc_number):
                        page_flag = True    # Mark page as relevant

                        # Add an entry to the statement_data dict if it isn't present
                        if not acc_number in statement_data:
                            statement_data[acc_number] = {'date': None, 'prev_period_val': None, 
                                                        'cur_period_val': None, 
                                                        'short_net': None, 'short_net_YTD': None, 
                                                        'long_net': None, 'long_net_YTD': None}
                except:
                    acc_number = None

            # If account number is present on page try getting data
            if page_flag:

                # Extract the statement ending date
                # if we haven't gotten the date yet
                if not date and text == 'Statement':
                    try:
                        if ret[i + 1][4] == 'Period:':
                            month = ret[i + 2][4].lower()
                            day = ret[i + 6][4][:-1]    # Remove the ',' that follows
                            year = ret[i + 7][4]
                            if int(Months[month].value) and int(day) and int(year):
                                date = year + '-' + str(Months[month].value) + '-' + day
                    except:
                        # Reset if we had any errors
                        month, day, year, date = (None,) * 4

                # Extract the previous period value and current value
                if not cur_period_value and text == 'TOTAL':
                    try:
                        if ret[i + 1][4] == 'ACCOUNT' and ret[i + 2][4] == 'VALUE':
                            prev_period_value = ret[i + 3][4].replace('$', '')
                            cur_period_value = ret[i + 4][4].replace('$', '')
                            statement_data[acc_number]['prev_period_val'] = float(prev_period_value)
                            statement_data[acc_number]['cur_period_val'] = float(cur_period_value)
                    except:
                        cur_period_value = prev_period_value = None

                # Extract the short term gains
                if not short_term_net_gains and text == 'Short-Term':
                    try:
                        if ret[i + 1][4] == 'Net' and ret[i + 2][4] == 'Gain':
                            short_term_net_gains = ret[i + 5][4].replace('$', '')
                            short_term_net_gains_YTD = ret[i + 6][4].replace('$', '')
                            statement_data[acc_number]['short_net'] = float(short_term_net_gains)
                            statement_data[acc_number]['short_net_YTD'] = float(short_term_net_gains_YTD)
                    except:
                        short_term_net_gains = short_term_net_gains_YTD = None

                # Extract the long term gains
                if not long_term_net_gains and text == 'Long-Term':
                    try:
                        if ret[i + 1][4] == 'Net' and ret[i + 2][4] == 'Gain':
                            long_term_net_gains = ret[i + 5][4].replace('$', '')
                            long_term_net_gains_YTD = ret[i + 6][4].replace('$', '')
                            statement_data[acc_number]['long_net'] = float(long_term_net_gains)
                            statement_data[acc_number]['long_net_YTD'] = float(long_term_net_gains_YTD)
                    except:
                        long_term_net_gains = long_term_net_gains_YTD = None


    # Fix the date for each entry
    for acc in statement_data:
        if statement_data[acc]['date'] == None:
            statement_data[acc]['date'] = date

    doc.close()
    return statement_data






if __name__ == '__main__':
    
    chase_statement_extract('chase_single_20240831-statements-8722-.pdf')
    