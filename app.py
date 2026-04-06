"""
app.py — Tech0 Search v3.0（AI検索版）

"""

import re
import json
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# secrets安全取得
try:
    PASSWORD = st.secrets["APP_PASSWORD"]
except Exception:
    PASSWORD = os.getenv("APP_PASSWORD")


# =========================
# 🔒 認証処理
# =========================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 ログイン")

    password = st.text_input("パスワードを入力", type="password")

    if st.button("ログイン"):
        if password == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います")

    st.stop()


from database import init_db, get_all_pages, insert_page, log_search, get_dashboard_summary, get_top_categories, get_top_authors, get_popular_queries, get_recent_pages
from ranking_AI import get_engine, rebuild_index
from chat_manager import refine_query
from crawler import crawl_url
from openai_client import get_embedding
from tips_engine import load_tips_json, get_best_tip



# アプリ起動時に DB を初期化する（テーブルが未作成なら作る）
init_db()

st.set_page_config(
    page_title="Tech0 Search v3.0(AI検索版)",
    page_icon="🔍",
    layout="wide"
)

# ── キャッシュ付きインデックス構築 ─────────────────────────────
@st.cache_resource
def load_and_index():
    pages = get_all_pages()
    if pages is not None and len(pages) > 0:
        rebuild_index(pages)
    return pages

pages = load_and_index()
engine = get_engine()

#tips用jsonファイルの読み書き関数
@st.cache_data
def load_pages():
    with open("tips_db.json", "r", encoding="utf-8") as f:
        load_pages = json.load(f)
        return load_pages

def save_pages(pages): 
    with open("tips_db.json", "w", encoding='utf-8') as f:
        json.dump(pages, f, ensure_ascii=False, indent=1) #indent=2を削除
        return
    
tips_pages = load_pages() #tips登録用のjsonファイルをすべて読み込んだtipsデータ

# Tipsデータ（キャッシュ）
@st.cache_data
def get_tips_data():
    return load_tips_json()

tips_data = get_tips_data() #best-Tipsを取りに行くための格納先

# ── ヘッダー ──────────────────────────────────────────────────
st.title("🔍 Tech0 Search 3.0(AI検索版)")
st.caption("PROJECT ZERO — 社内ナレッジ検索エンジン【AI検索ランキング搭載】")
st.markdown(f"登録資料数：{len(pages)} 件")
if st.button("🔄 インデックスを更新"):
        st.cache_resource.clear()
        st.rerun()

# ── タブ ──────────────────────────────────────────────────────
tab_search, tab_crawl, tab_form, tab_list ,tab_tips_list, tab_dashboard = st.tabs(["🔍 検索", "🤖 資料登録", '👉Tips登録', "📋 資料一覧","👓 tips一覧", "📊 ダッシュボード"])

# ── 検索タブ ───────────────────────────────────────────────────

with tab_search:
    col_left, col_right = st.columns([2, 3]) #レイアウトを左右に分割

    #左：AIと会話するエリア
    with col_left:
        st.subheader("AIに相談して検索")

        st.markdown(
            '<p style="font-size:24px; font-weight:500;">検索とAIへの会話投稿はｺｺ</p>',
            unsafe_allow_html=True
        )

        query = st.text_input("🔍 知りたいｺﾄを入力", placeholder="🔍 知りたいｺﾄを入力（例:プログラミングを始めたい）", label_visibility="collapsed")
        search_clicked = st.button("AIとの会話に投稿", type="primary")
        reset_clicked = st.button('会話をリセット', type="secondary")
            
        st.markdown(
            '<p style="font-size:24px; font-weight:500;">AIとの会話内容</p>',
            unsafe_allow_html=True
        )

        # 🔽 セッション初期化
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        if "query" not in st.session_state:
            st.session_state.query = ""

        if "is_refined" not in st.session_state: #ここを追加
            st.session_state.is_refined = False #ここを追加

        # 🔽 リセット処理
        if reset_clicked:
            st.session_state.chat_history = []
            st.session_state.query = ""
            st.session_state.is_refined = False #ここを追加

        # 🔽 入力処理(ここを追加)
        if search_clicked and query:

            # ユーザー発言追加
            st.session_state.chat_history.append(("user", query))

            # =========================
            # 初回 or 2回目以降 判定
            # =========================
            if len(st.session_state.chat_history) == 1:
                # 🟢 初回：そのまま検索
                st.session_state.query = query
                st.session_state.is_refined = False

                ai_response = f"『{query}』で検索します"

            else:
                # 🟡 2回目以降：AIでクエリ精錬
                refined_query = refine_query(st.session_state.chat_history)

                st.session_state.query = refined_query
                st.session_state.is_refined = True

                ai_response = f"検索条件を整理しました：\n👉 {refined_query}"

            # AI発言追加
            st.session_state.chat_history.append(("ai", ai_response))

        # 🔽 会話カードの表示
        for role, msg in st.session_state.chat_history:
            if role == "user":
                # ユーザーは右寄せ
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:flex-end; margin-bottom:5px;">
                        <div style="
                            background-color:#d4fcdc;
                            padding:10px;
                            border-radius:10px;
                            max-width:70%;
                        ">
                            🟩 {msg}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                # AIは左寄せ（従来通り）
                st.markdown(
                    f"""
                    <div style="
                        background-color:#f0f0f0;
                        padding:10px;
                        border-radius:10px;
                        margin-bottom:5px;
                        max-width:70%;
                    ">
                        ⬜ {msg}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    #右：検索結果表示
    with col_right:
        col_title, col_select = st.columns([3, 1])

        with col_title:
            st.subheader('###検索結果###')

        with col_select:
            top_n = st.selectbox("表示件数", [10, 20, 50], index=0)
            
        # 🔽 検索実行
        if st.session_state.query:

            results = engine.search(st.session_state.query, top_n=top_n)

            # 👇 refinedかどうか表示するとUX良い
            if st.session_state.is_refined:
                st.info(f"🤖 AI最適化検索内容：{st.session_state.query}")
            else:
                st.info(f"🔍 検索内容：{st.session_state.query}")

            st.markdown(f"**📊 検索結果：{len(results)} 件**")
            st.divider()

            if results:
                for i, page in enumerate(results, 1):
                    with st.container():
                        col_rank, col_title, col_score = st.columns([0.5, 4, 1])
                        with col_rank:
                            # 上位3件にはメダルを表示する
                            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else str(i)
                            st.markdown(f"### {medal}")
                        with col_title:
                            st.markdown(f"### {page['title']}")
                        with col_score:
                            # relevance_score（最終スコア）と base_score（TF-IDFのみ）を両方表示
                            st.metric("スコア", f"{page['relevance_score']}",
                                    delta=f"基準: {page['base_score']}")

                        desc = page.get("description", "")
                        if desc:
                            st.markdown(f"*{desc[:200]}{'...' if len(desc) > 200 else ''}*")

                        kw = page.get("keywords", "") or ""
                        if kw:
                            kw_list = [k.strip() for k in kw.split(",") if k.strip()][:5]
                            tags = " ".join([f"`{k}`" for k in kw_list])
                            st.markdown(f"🏷️ {tags}")

                        col1, col2, col3, col4 = st.columns(4)
                        with col1: st.caption(f"👤 {page.get('author', '不明') or '不明'}")
                        with col2: st.caption(f"📊 {page.get('word_count', 0)} 語")
                        with col3: st.caption(f"📁 {page.get('category', '未分類') or '未分類'}")
                        with col4: st.caption(f"📅 {(page.get('crawled_at', '') or '')[:10]}")

                        st.markdown(f"🔗 [{page['url']}]({page['url']})")
                        
                        #best-tipsの表示
                        tips_key = f"tips_{i}"
                        button_key = f"btn_{i}"

                        if st.button("💡 Tips表示", key=button_key):

                            page_embedding = page.get("embedding")

                            if page_embedding:
                                best_tip, score = get_best_tip(page_embedding, tips_data)

                                if best_tip:
                                    st.session_state[tips_key] = (best_tip, score)
                                else:
                                    st.session_state[tips_key] = None
                            else:
                                st.session_state[tips_key] = "no_embedding"

                        # 表示部分（毎回再描画される
                        if tips_key in st.session_state:

                            if st.session_state[tips_key] == "no_embedding":
                                st.warning("このページにはembeddingがありません")

                            elif st.session_state[tips_key] is None:
                                st.info("関連するTipsが見つかりませんでした")

                            else:
                                best_tip, score = st.session_state[tips_key]
                                st.success(best_tip.get("description", ""))
                                st.write(f'Tips登録日: {best_tip.get("registered_at", "")}   ※Tips登録日に注意して活用ください')

                        st.divider()
            else:
                st.info("該当するページが見つかりませんでした")

    
# ── 資料ページ登録タブ ─────────────────────────────────────────────
if "crawl_results" not in st.session_state:
    st.session_state.crawl_results = []

with tab_crawl:
    st.subheader("🤖 自動資料登録")
    st.caption("URLを入力してボタンを押すと自動でURLをクロールし、インデックスに登録する")

    crawl_url_input = st.text_area(
        "クロール対象URL",
        placeholder="URLを改行またはスペース区切りで入力してください",
        height=150
    )

    if st.button("🤖 クロール実行", type="primary"):
        if crawl_url_input:
            raw_parts = re.split(r'[\s]+', crawl_url_input.strip())
            urls = [p for p in raw_parts if p.startswith(("http://", "https://"))]

            if not urls:
                st.error("有効なURLが見つかりませんでした")
            else:
                st.write(f"🔗 {len(urls)}件のURLを処理します")

                st.session_state.crawl_results = []

                for url in urls:
                    with st.spinner(f"クロール中: {url}"):
                        result = crawl_url(url)

                    if result and result.get('crawl_status') == 'success':
                        st.success(f"✅ 成功: {url}")

                        col1, col2 = st.columns(2)
                        with col1:
                            title = result.get('title', '')
                            st.metric("📄 タイトル", (title[:30] + "...") if len(title) > 30 else title)
                        with col2:
                            st.metric("📊 文字数", f"{result.get('word_count', 0)}語")

                        st.session_state.crawl_results.append(result)
                    else:
                        st.error(f"❌ 失敗: {url}")

    if st.session_state.crawl_results:
        st.info(f"{len(st.session_state.crawl_results)}件のクロール結果を登録できます。")

        if st.button("💾 全てインデックスに登録"):
            total = len(st.session_state.crawl_results)

            progress_text = st.empty()
            progress_bar = st.progress(0)

            for i, r in enumerate(st.session_state.crawl_results, start=1):
                progress_text.write(f"📥 {i} / {total} 件登録中...")
                insert_page(r)
                progress_bar.progress(i / total)

            progress_text.write(f"✅ {total} / {total} 件 登録完了！")
            st.success(f"{total}件 登録完了！")
            st.session_state.crawl_results = []
            st.cache_resource.clear()
            st.rerun()

# ── Tips登録タブ ─────────────────────────────────────────────
with tab_form:
    with st.form('register_form'):
        #入力フィールドを作る
        title = st.text_input('タイトル')
        description = st.text_input('説明')
        category = st.text_input('カテゴリ')
        registered_at = st.date_input('登録日')

        submitted = st.form_submit_button('登録する')

    if submitted:
        #ここで新しく登録されたTipsのembeddingを計算
        text_for_embedding = title + " " + description
        tips_embedding = get_embedding(text_for_embedding)

        new_tips_page =  {
            'title':title,
            'description':description,
            'category':category,
            'registered_at':str(registered_at),
            'embedding': tips_embedding.tolist() #embeddingをjsonに保存
        }
        tips_pages.append(new_tips_page)
        save_pages(tips_pages)
        st.cache_resource.clear()
        st.rerun()

# ── 資料一覧タブ ───────────────────────────────────────────────────
with tab_list:
    st.subheader(f"📋 登録済みページ一覧（{len(pages)} 件）")
    if pages is None or len(pages) == 0:
        st.info("登録されているページがありません。クローラータブからページを追加してください。")
    else:
        for page in pages:

            with st.expander(f"📄 {page['title']}"):
                st.markdown(f"**URL：** {page['url']}")
                st.markdown(f"**説明：** {page.get('description', '（なし）') or '（なし）'}")
                col1, col2, col3 = st.columns(3)
                with col1: st.caption(f"語数：{page.get('word_count', 0)}")
                with col2: st.caption(f"作成者：{page.get('author', '不明') or '不明'}")
                with col3: st.caption(f"カテゴリ：{page.get('category', '未分類') or '未分類'}")

# ── Tips一覧タブ ───────────────────────────────────────────────────
with tab_tips_list:
    st.subheader(f"👓 登録済みtips一覧（{len(tips_pages)} 件）")
    for tp in tips_pages:
        with st.expander(tp['title']):
            st.write('tips:', tp['description'] )
            st.write('カテゴリ:', tp['category'])
            st.write('登録日:', tp['registered_at'])
            st.markdown(
                """
                <p style='color:red; font-weight:bold; font-size:14px;'>
                ※情報作成日に注意してtipsを活用してください
                </p>
                """,
                unsafe_allow_html=True
            )

#ダッシュボードを追加
with tab_dashboard:
    st.subheader("📊 検索ランキングダッシュボード")
    st.caption("登録文書・カテゴリ・検索傾向を可視化します")

    summary = get_dashboard_summary()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("登録ページ数", summary["total_pages"])
    with col2:
        st.metric("カテゴリ数", summary["total_categories"])
    with col3:
        st.metric("著者数", summary["total_authors"])
    with col4:
        st.metric("検索回数", summary["total_searches"])

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### 📁 カテゴリ別ページ数")
        cat_df = get_top_categories()
        if not cat_df.empty:
            st.bar_chart(cat_df.set_index("category"))
            #st.dataframe(cat_df, use_container_width=True)
            st.dataframe(cat_df, width="stretch")
        else:
            st.info("カテゴリデータがありません")

    with col_right:
        st.markdown("### 👤 著者別ページ数")
        author_df = get_top_authors()
        if not author_df.empty:
            st.bar_chart(author_df.set_index("author"))
            #st.dataframe(author_df, use_container_width=True)
            st.dataframe(cat_df, width="stretch")
        else:
            st.info("著者データがありません")

    st.divider()

    col_left2, col_right2 = st.columns(2)

    with col_left2:
        st.markdown("### 🔥 人気検索キーワード")
        query_df = get_popular_queries()
        if not query_df.empty:
            st.bar_chart(query_df.set_index("query"))
            #st.dataframe(query_df, use_container_width=True)
            st.dataframe(cat_df, width="stretch")
        else:
            st.info("まだ検索ログがありません")

    with col_right2:
        st.markdown("### 🕒 最近登録されたページ")
        recent_df = get_recent_pages()
        if not recent_df.empty:
            #st.dataframe(recent_df, use_container_width=True)
            st.dataframe(cat_df, width="stretch")
        else:
            st.info("登録ページがありません")


st.divider()
st.caption("© 2026 PROJECT ZERO — Tech0 Search v3.0 | Powered by embedding")
