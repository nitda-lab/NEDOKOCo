import sqlite3
con = sqlite3.connect("data/buisui.db")
cur = con.cursor()
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("tables:", tables)
for (t,) in tables:
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {n}件")
    try:
        r2 = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1").fetchone()[0]
        r3 = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE ai_sleep_score IS NULL").fetchone()[0]
        print(f"    ぶい睡適合: {r2}件 / 未評価: {r3}件")
    except Exception:
        pass
con.close()
