# database.py
import os
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

import pandas as pd

DB_PATH = os.path.join("data", "tech0_search.db")
SCHEMA_PATH = "schema.sql"


def get_connection():
    """SQLite接続を返す"""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """schema.sql を読み込んでDB初期化"""
    conn = get_connection()
    cursor = conn.cursor()

    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        cursor.executescript(schema_sql)
        conn.commit()
    else:
        raise FileNotFoundError(f"schema.sql が見つかりません: {SCHEMA_PATH}")

    conn.close()


def insert_page(
    url: str,
    title: str,
    description: str = "",
    full_text: str = "",
    author: str = "",
    category: str = "",
    word_count: int = 0,
    crawled_at: Optional[str] = None,
    embedding: Optional[Any] = None,
    keywords: Optional[List[str]] = None,
) -> int:
    """
    ページを新規追加する
    - 同じURLでも履歴として蓄積するため INSERT INTO を使う
    - embedding は list / dict / str を受け取り、DBにはTEXT(JSON)で保存
    - keywords があれば keywords テーブルにも登録
    """
    conn = get_connection()
    cursor = conn.cursor()

    if crawled_at is None:
        crawled_at = datetime.now().isoformat()

    if embedding is None:
        embedding_json = None
    elif isinstance(embedding, str):
        embedding_json = embedding
    else:
        embedding_json = json.dumps(embedding, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO pages
            (url, title, description, full_text, author, category, word_count, crawled_at, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        url,
        title,
        description,
        full_text,
        author,
        category,
        word_count,
        crawled_at,
        embedding_json
    ))

    page_id = cursor.lastrowid

    if keywords:
        keyword_rows = []
        for kw in keywords:
            kw = str(kw).strip()
            if kw:
                keyword_rows.append((page_id, kw, 0.0, 0.0))

        if keyword_rows:
            cursor.executemany("""
                INSERT INTO keywords (page_id, keyword, tf_score, tfidf_score)
                VALUES (?, ?, ?, ?)
            """, keyword_rows)

    conn.commit()
    conn.close()
    return page_id


def update_page(
    page_id: int,
    url: str,
    title: str,
    description: str = "",
    full_text: str = "",
    author: str = "",
    category: str = "",
    word_count: int = 0,
    crawled_at: Optional[str] = None,
    embedding: Optional[Any] = None,
    keywords: Optional[List[str]] = None,
) -> bool:
    """
    既存ページを更新する
    ※ 通常運用では履歴を積むため insert_page 推奨
    """
    conn = get_connection()
    cursor = conn.cursor()

    if crawled_at is None:
        crawled_at = datetime.now().isoformat()

    if embedding is None:
        embedding_json = None
    elif isinstance(embedding, str):
        embedding_json = embedding
    else:
        embedding_json = json.dumps(embedding, ensure_ascii=False)

    cursor.execute("""
        UPDATE pages
        SET url = ?,
            title = ?,
            description = ?,
            full_text = ?,
            author = ?,
            category = ?,
            word_count = ?,
            crawled_at = ?,
            embedding = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        url,
        title,
        description,
        full_text,
        author,
        category,
        word_count,
        crawled_at,
        embedding_json,
        page_id
    ))

    if keywords is not None:
        cursor.execute("DELETE FROM keywords WHERE page_id = ?", (page_id,))
        keyword_rows = []
        for kw in keywords:
            kw = str(kw).strip()
            if kw:
                keyword_rows.append((page_id, kw, 0.0, 0.0))

        if keyword_rows:
            cursor.executemany("""
                INSERT INTO keywords (page_id, keyword, tf_score, tfidf_score)
                VALUES (?, ?, ?, ?)
            """, keyword_rows)

    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def delete_page(page_id: int) -> bool:
    """ページ削除"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    return affected > 0


def get_page_by_id(page_id: int) -> Optional[Dict[str, Any]]:
    """IDでページ取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.*
        FROM pages p
        WHERE p.id = ?
    """, (page_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    page = dict(row)

    cursor.execute("""
        SELECT keyword
        FROM keywords
        WHERE page_id = ?
        ORDER BY keyword ASC
    """, (page_id,))
    page["keywords"] = [r["keyword"] for r in cursor.fetchall()]

    conn.close()
    return page

def get_all_pages():
    """すべてのページを取得（既存 app.py 互換: list[dict] を返す）"""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT 
            p.id,
            p.url,
            p.title,
            p.author,
            p.category,
            p.crawled_at,
            p.embedding,
            COALESCE(GROUP_CONCAT(k.keyword, ', '), '') AS keywords
        FROM pages p
        LEFT JOIN keywords k ON p.id = k.page_id
        GROUP BY 
            p.id,
            p.url,
            p.title,
            p.author,
            p.category,
            p.crawled_at,
            p.embedding
        ORDER BY p.crawled_at DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df.to_dict(orient="records")


def search_pages(keyword: str) -> pd.DataFrame:
    """
    シンプル検索
    title / description / full_text / category / author / keyword を対象
    """
    conn = get_connection()

    like = f"%{keyword}%"
    query = """
        SELECT DISTINCT
            p.id,
            p.url,
            p.title,
            p.description,
            p.full_text,
            p.author,
            p.category,
            p.word_count,
            p.crawled_at,
            p.embedding,
            p.created_at,
            p.updated_at
        FROM pages p
        LEFT JOIN keywords k ON p.id = k.page_id
        WHERE
            p.title LIKE ?
            OR p.description LIKE ?
            OR p.full_text LIKE ?
            OR p.category LIKE ?
            OR p.author LIKE ?
            OR k.keyword LIKE ?
        ORDER BY p.crawled_at DESC
    """
    df = pd.read_sql_query(query, conn, params=[like, like, like, like, like, like])
    conn.close()
    return df


def get_keywords_by_page(page_id: int) -> List[str]:
    """ページIDに紐づくキーワード一覧"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT keyword
        FROM keywords
        WHERE page_id = ?
        ORDER BY keyword ASC
    """, (page_id,))
    rows = cursor.fetchall()
    conn.close()

    return [row["keyword"] for row in rows]


def add_keywords(page_id: int, keywords: List[str]) -> int:
    """キーワード追加"""
    conn = get_connection()
    cursor = conn.cursor()

    rows = []
    for kw in keywords:
        kw = str(kw).strip()
        if kw:
            rows.append((page_id, kw, 0.0, 0.0))

    if rows:
        cursor.executemany("""
            INSERT INTO keywords (page_id, keyword, tf_score, tfidf_score)
            VALUES (?, ?, ?, ?)
        """, rows)

    conn.commit()
    inserted = len(rows)
    conn.close()
    return inserted


def log_search(query: str, results_count: int = 0, user_id: str = None) -> int:
    """検索ログ保存"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO search_logs (query, results_count, user_id, searched_at)
        VALUES (?, ?, ?, ?)
    """, (
        query,
        results_count,
        user_id,
        datetime.now().isoformat()
    ))

    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def log_click(page_id: int, search_log_id: Optional[int] = None, position: Optional[int] = None) -> int:
    """検索結果クリックログ保存"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO click_logs (search_log_id, page_id, position, clicked_at)
        VALUES (?, ?, ?, ?)
    """, (
        search_log_id,
        page_id,
        position,
        datetime.now().isoformat()
    ))

    click_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return click_id


def get_dashboard_summary() -> Dict[str, int]:
    """ダッシュボード用サマリー"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS cnt FROM pages")
    total_pages = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(DISTINCT category) AS cnt
        FROM pages
        WHERE category IS NOT NULL AND TRIM(category) <> ''
    """)
    total_categories = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(DISTINCT author) AS cnt
        FROM pages
        WHERE author IS NOT NULL AND TRIM(author) <> ''
    """)
    total_authors = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) AS cnt FROM search_logs")
    total_searches = cursor.fetchone()["cnt"]

    conn.close()

    return {
        "total_pages": total_pages,
        "total_categories": total_categories,
        "total_authors": total_authors,
        "total_searches": total_searches,
    }


def get_top_categories(limit: int = 10) -> pd.DataFrame:
    """カテゴリ別件数"""
    conn = get_connection()

    query = """
        SELECT
            category,
            COUNT(*) AS count
        FROM pages
        WHERE category IS NOT NULL AND TRIM(category) <> ''
        GROUP BY category
        ORDER BY count DESC, category ASC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df


def get_top_authors(limit: int = 10) -> pd.DataFrame:
    """著者別件数"""
    conn = get_connection()

    query = """
        SELECT
            author,
            COUNT(*) AS count
        FROM pages
        WHERE author IS NOT NULL AND TRIM(author) <> ''
        GROUP BY author
        ORDER BY count DESC, author ASC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df


def get_popular_queries(limit: int = 10) -> pd.DataFrame:
    """人気検索クエリ"""
    conn = get_connection()

    query = """
        SELECT
            query,
            COUNT(*) AS count,
            MAX(searched_at) AS last_searched_at
        FROM search_logs
        WHERE query IS NOT NULL AND TRIM(query) <> ''
        GROUP BY query
        ORDER BY count DESC, last_searched_at DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df


def get_recent_pages(limit: int = 10) -> pd.DataFrame:
    """最近登録/クロールされたページ"""
    conn = get_connection()

    query = """
        SELECT
            id,
            title,
            url,
            author,
            category,
            word_count,
            crawled_at
        FROM pages
        ORDER BY crawled_at DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df


def get_page_count() -> int:
    """ページ総数"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS cnt FROM pages")
    count = cursor.fetchone()["cnt"]
    conn.close()
    return count


def clear_all_data():
    """全データ削除（開発用）"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM click_logs")
    cursor.execute("DELETE FROM search_logs")
    cursor.execute("DELETE FROM keywords")
    cursor.execute("DELETE FROM pages")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
