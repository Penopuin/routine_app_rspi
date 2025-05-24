import sqlite3
import os

# 절대 경로로 DB 위치 고정
DB_PATH = "/home/pi/LCD_final/routine_db.db"

def init_db():
    # DB 파일이 존재하는지 확인
    if os.path.exists(DB_PATH):
        print(f"🔍 기존 DB 파일 존재: {DB_PATH}")
    else:
        print(f"📁 새 DB 파일 생성 예정: {DB_PATH}")

    # DB 연결 및 테이블 생성
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # routines 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY,
            date TEXT,
            start_time TEXT,
            routine_minutes INTEGER,
            icon TEXT,
            routine_name TEXT,
            group_routine_name TEXT,
            completed INTEGER DEFAULT 0
        )
    """)

    # timers 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timers (
            id INTEGER PRIMARY KEY,
            timer_minutes INTEGER,
            rest INTEGER,
            repeat_count INTEGER,
            icon TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✅ routine_db 초기화 완료")

if __name__ == "__main__":
    init_db()
