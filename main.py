import sqlite3
import os
import csv

def create_db():


    # Initialize a database file
    con = sqlite3.connect("transactions.db")
    cur = con.cursor()

    # FOR TESTING PURPOSES #
    drop_sql = ["DROP TABLE IF EXISTS raw_transactions",
                "DROP TABLE IF EXISTS gains"]
    try:
        for statement in drop_sql:
            cur.execute(statement)
        con.commit()
    except sqlite3.Error as e:
        print(e)


    # Initialize a table for raw transactions
    sql_statement = [
        """CREATE TABLE IF NOT EXISTS raw_transactions(
            account_name TEXT,
            account_number TEXT NOT NULL,
            ticker TEXT, 
            cusip TEXT,
            type TEXT,
            date TEXT, 
            cost_basis REAL, 
            qty REAL, 
            date_inserted TEXT NOT NULL, 
            date_modified TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS gains(
            ticker TEXT NOT NULL,
            date_buy TEXT, 
            qty_buy REAL,
            buy_cost_basis REAL,
            date_sell TEXT,
            qty_sell REAL,
            sell_cost_basis REAL,
            split_status TEXT,
            date_inserted TEXT NOT NULL, 
            date_modified TEXT NOT NULL)"""
        ]
    try:
        for statement in sql_statement:
            cur.execute(statement)
        con.commit()
    except sqlite3.Error as e:
        print(e)
    
    return con, cur

if __name__ == "__main__":
    
    
    con, cur = create_db()
    
    # for statement in sql_statement:
    #     print(statement)
    '''
    Initialize a table for processed transactions
        Coloumns shall consist of:
        Ticker
        Date of purchase
        Quantity Buy
        Cost basis Buy (cost of the transaction)
        Date of sale
        Quantity Sell
        Cost basis Sell (cost of the transaction)

    '''     
    # Import data from CSVs, for now, just from chase or fidelity
    csvfile = open("transactions.csv", newline='', encoding='utf-8-sig')
    # rows = csv.reader(csvfile, delimiter=',')   # Read all info in the csv into lists
    reader = csv.DictReader(csvfile)
    
    try:
        for row in reader:
            data = (row['Account Name'], row['Account Number'], 
                    row['Ticker'], row['Cusip'], 
                    row['Type'], row['Trade Date'], 
                    row['Price USD'], row['Quantity'],)
            cur.execute("INSERT INTO raw_transactions VALUES(?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))", data)
        
        # Commit changes after adding all data from the csv. If an error occures, no data will write
        con.commit() 

    except sqlite3.Error as e:
        print(e)


    # Start processing the data and inserting it into te processed transactions table
    # If there is a transaction that went CIL, just say that we sold all the shares we had and use the CIL amount as the cost basis sell
    # Calculate capital gains from the processed transcations table
    
    # Close database # 
    con.close()


