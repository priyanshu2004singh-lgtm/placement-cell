import pymysql
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_CA


def get_conn():
    ssl_args = {}
    if DB_CA:
        ssl_args = {'ca': DB_CA}
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        charset='utf8mb4',
        ssl=ssl_args if ssl_args else None,
    )


def query(sql, args=None, one=False):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
            return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def execute(sql, args=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()