import sqlite3

def init_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            filepath TEXT PRIMARY KEY,
            hash TEXT,
            read_method TEXT,
            size INTEGER,
            mtime REAL
        )
    """)
    conn.commit()
    return conn

def get_metadata_map(conn):
    cur = conn.cursor()
    cur.execute("SELECT filepath, size, mtime, hash FROM images")
    return {row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()}

def upsert_entries(conn, entries):
    cur = conn.cursor()
    cur.executemany("""
        INSERT OR REPLACE INTO images (filepath, hash, read_method, size, mtime)
        VALUES (?, ?, ?, ?, ?)
    """, entries)
    conn.commit()

def update_filepath(conn, old_relpath, new_relpath, new_size, new_mtime):
    cur = conn.cursor()
    cur.execute("""
        UPDATE images
        SET filepath=?, size=?, mtime=?
        WHERE filepath=?
    """, (new_relpath, new_size, new_mtime, old_relpath))
    conn.commit()
