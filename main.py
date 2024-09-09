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
                "DROP TABLE IF EXISTS cusip_ticker"]
    try:
        for statement in drop_sql:
            cur.execute(statement)
        con.commit()
    except sqlite3.Error as e:
        print(e)


    # Initialize a table for raw transactions
    sql_statement = [
        """CREATE TABLE IF NOT EXISTS raw_transactions(
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

    '''
    IDEA FOR EXPANDING: Maybe I can pass in a dict that contains the unique field 
    names for each brokerage and reuse all this code.

    The dict would contain standardized entries and their value would be the broker 
    specific values
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
            cur.execute("""INSERT INTO raw_transactions VALUES(
                        'Chase', ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))""", data)

            # Save the cusip and ticker pair if present
            if data[4] and data[5]:
                cur.execute("""INSERT INTO cusip_ticker VALUES(
                            ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime')) 
                            ON CONFLICT(cusip) DO NOTHING""", (data[4], data[5]))    
            
        # Commit changes after adding all data from the csv. If an error occurs, no data will write
        con.commit()

    except sqlite3.Error as e:
        print(e)
    pass

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
    

    # Start processing the data and inserting it into te processed transactions table
    # If there is a transaction that went CIL, just say that we sold all the shares we had and use the CIL amount as the cost basis sell

    #### KENNETH, fidelity uses the new CUSIP in the reverse split transactions
    # Calculate capital gains from the processed transactions table
    
    # Close database # 
    con.close()


