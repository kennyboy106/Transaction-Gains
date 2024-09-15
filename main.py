import sqlite3
import os
import csv

def create_db():
    '''
    Create/connect to the database file and create all necessary tables.

    Exceptions:
        Sqlite3 exceptions when executing statements
    Return:
        con: sqlite3.Connection: Connection to the database
        cur: sqlite3.Cursor: The cursor to go along with the connection
    '''

    # Initialize a database file
    con = sqlite3.connect("transactions.db")
    cur = con.cursor()

    # FOR TESTING PURPOSES REMOVE ALL TABLES#
    drop_sql = ["DROP TABLE IF EXISTS raw_transactions",
                "DROP TABLE IF EXISTS gains",
                "DROP TABLE IF EXISTS cusip_ticker",
                "DROP TABLE IF EXISTS holdings"]
    try:
        for statement in drop_sql:
            cur.execute(statement)
        con.commit()
    except sqlite3.Error as e:
        print(e)


    # Initialize a table for raw transactions
    sql_statement = [
        """CREATE TABLE IF NOT EXISTS raw_transactions(
            transaction_id INTEGER PRIMARY KEY,
            broker TEXT NOT NULL,
            date TEXT,
            account_name TEXT,
            account_number TEXT NOT NULL,
            type TEXT,
            cusip TEXT,
            ticker TEXT, 
            cost_basis REAL, 
            qty REAL, 
            date_inserted TEXT NOT NULL, 
            date_modified TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS gains(
            broker NOT NULL,
            ticker TEXT,
            cusip TEXT,
            date_buy TEXT, 
            qty_buy REAL,
            buy_cost_basis REAL,
            date_sell TEXT,
            qty_sell REAL,
            sell_cost_basis REAL,
            split_status TEXT,
            date_inserted TEXT NOT NULL, 
            date_modified TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS cusip_ticker(
            cusip TEXT NOT NULL,
            ticker TEXT NOT NULL,
            date_inserted TEXT NOT NULL, 
            date_modified TEXT NOT NULL,
            UNIQUE(cusip))"""
        ]
    try:
        for statement in sql_statement:
            cur.execute(statement)
        con.commit()
    except sqlite3.Error as e:
        print(e)
    
    return con, cur


def chase_process_transactions(file_name: str, con: sqlite3.Connection, cur: sqlite3.Cursor):

    # Read in raw transaction data from csv file
    insert_raw_transactions(file_name, con, cur)

    # Start calculating capital gains

    

def insert_raw_transactions(file_name: str, con: sqlite3.Connection, cur: sqlite3.Cursor):

    '''
    IDEA FOR EXPANDING: Maybe I can pass in a dict that contains the unique field 
    names for each brokerage and reuse all this code.

    The dict would contain standardized entries and their value would be the broker 
    specific values

    If I do this, then I also need to pass in the brokerage name into this function
    '''
    # Specifying the encoding removes the extra encoding flag inserted into first read later on
    csvfile = open(file_name, newline='', encoding='utf-8-sig')

    reader = csv.DictReader(csvfile)

    # Ensure all fields are present
    required_elements = ['Trade Date', 'Account Name', 'Account Number', 'Type', 'Cusip', 'Ticker', 'Price USD', 'Quantity']
    intersection_set = set(reader.fieldnames).intersection(set(required_elements))
    if len(intersection_set) != len(required_elements):
        raise Exception("""Chase transactions lacks required fields\n
                        REQUIRED: Trade Date, Account Name, Account Number, Type, Cusip, Ticker, Price USD, Quantity""")

    # Try inserting data line by line into raw_transactions and cusip_ticker tables
    try:
        for row in reader:
            data = (row['Trade Date'], row['Account Name'],  
                    row['Account Number'], row['Type'],
                    row['Cusip'], row['Ticker'],
                    row['Price USD'], row['Quantity'],)
            cur.execute("""INSERT INTO raw_transactions 
                        (broker, date, account_name, account_number, type, cusip, ticker, cost_basis, qty, date_inserted, date_modified) 
                        VALUES('Chase', ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""", data)

            # Save the cusip and ticker pair if present
            if data[4] and data[5]:
                cur.execute("""INSERT INTO cusip_ticker 
                            (cusip, ticker, date_inserted, date_modified)
                            VALUES(?, ?, datetime('now', 'localtime'), datetime('now', 'localtime')) 
                            ON CONFLICT(cusip) DO NOTHING""", (data[4], data[5]))
            
        # Commit changes after adding all data from the csv. If an error occurs, no data will write
        con.commit()

    except sqlite3.Error as e:
        print(e)
    
    # Close the file
    csvfile.close()

if __name__ == "__main__":
    
    
    con, cur = create_db()
    
    # for statement in sql_statement:
    #     print(statement)
    '''
    Initialize a table for processed transactions
        Columns shall consist of:
        Ticker
        Date of purchase
        Quantity Buy
        Cost basis Buy (cost of the transaction)
        Date of sale
        Quantity Sell
        Cost basis Sell (cost of the transaction)

    '''
    # Import data from CSVs, for now, just from chase or fidelity

    # FOR CHASE #
    chase_process_transactions('transactions.csv', con, cur)
    
    # Calculating capital gains
    '''
    Intermediate table that has buy and sell transactions
    If I sell, check for oldest buy that isn't closed out
        If it is closed out, find next oldest and use that
        If I sell all shares from that buy, close out the buy and move on to next oldest for remaining shares
    If rsa transaction, delete shares and add back later (there should be 2 per reverse or CIL)
        1. Find oldest buy
        2. subtract the shares depicted in the rsa transaction
        3. On the next rsa transaction, add shares depicted
            In the end, steps 2 and 3 should cancel or give me the final shares result and the sell logic should work fine
    ORDER
        To ensure that transactions happen in the proper order, I should sort the new raw transactions by type and enter from there

    To do this I can have a table structure of:
    [reference to transaction] [cost per share] [split] [shares adjusted] [shares sold]
    
        """CREATE TABLE IF NOT EXISTS holdings(
            transaction_id INTEGER NOT NULL,
            cost_per_share REAL,
            split TEXT,
            shares_adjusted REAL,
            shares_sold REAL)"""
        
    '''
    # Start processing the data and inserting it into te processed transactions table
    # If there is a transaction that went CIL, just say that we sold all the shares we had and use the CIL amount as the cost basis sell

    #### KENNETH, fidelity uses the new CUSIP in the reverse split transactions
    # Calculate capital gains from the processed transactions table
    
    # Close database # 
    con.close()


