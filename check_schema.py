
import mysql.connector

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'shopping_list'
}

try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DESCRIBE items")
    columns = cursor.fetchall()
    print("Columns in 'items' table:")
    for col in columns:
        print(col)
    conn.close()
except Exception as e:
    print(f"Error connecting to MySQL: {e}")
