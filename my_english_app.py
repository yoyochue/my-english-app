import streamlit as st
import sqlite3
import pandas as pd
import requests
import random

# --- 資料庫函式 ---
def init_db():
    conn = sqlite3.connect('english_data.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS vocab (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT,
            meaning TEXT,
            example TEXT,
            status INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_words(status_filter=None):
    conn = sqlite3.connect('english_data.db')
    query = "SELECT * FROM vocab"
    if status_filter is not None:
        query += f" WHERE status = {status_filter}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def update_status(word_id, new_status):
    conn = sqlite3.connect('english_data.db')
    c = conn.cursor()
    c.execute('UPDATE vocab SET status = ? WHERE id = ?', (new_status, word_id))
    conn.commit()
    conn.close()

# --- 自動下載函式 ---
def download_2000_words():
    url = "https://raw.githubusercontent.com/pwxcoo/dictionary/master/dictionary/cet6.json"
    status_text = st.empty()
    progress_bar = st.progress(0)
    try:
        status_text.text("📡 正在連線下載...")
        response = requests.get(url, timeout=10)
        data = response.json()
        conn = sqlite3.connect('english_data.db')
        c = conn.cursor()
        existing_df = pd.read_sql("SELECT word FROM vocab", conn)
        existing_words = set(existing_df['word'].str.lower() if not existing_df.empty else [])
        added_count = 0
        total = len(data)
        for i, item in enumerate(data):
            word = item.get('word', '')
            if word and word.lower() not in existing_words:
                trans = item.get('trans', [])
                meaning = "; ".join(trans) if isinstance(trans, list) else str(trans)
                meaning = meaning.replace("的", "的").replace("么", "麼").replace("发", "發").replace("忧", "憂")
                c.execute('INSERT INTO vocab (word, meaning, example, status) VALUES (?, ?, ?, 0)', (word, meaning, ""))
                added_count += 1
            if i % 100 == 0: progress_bar.progress((i + 1) / total)
        conn.commit()
        conn.close()
        progress_bar.progress(1.0)
        status_text.success(f"匯入完成！新增 {added_count} 字。")
    except Exception as e:
        status_text.error(f"下載失敗：{e}")

# --- App 介面設定 ---
st.set_page_config(page_title="英文隨身練", layout="centered") # 改成 centered 比較適合手機
init_db()

st.title("📱 英文隨身練")

# 側邊選單 (手機上會變成左上角的箭頭 >)
menu = ["🧠 抽卡模式", "🧩 連連看配對", "📊 單字列表", "📥 下載單字庫"]
choice = st.sidebar.selectbox("選單", menu)

# --- 功能 1: 抽卡 ---
if choice == "🧠 抽卡模式":
    st.header("🔥 單字記憶卡")
    df = get_words(0)
    if not df.empty:
        if 'current_word_id' not in st.session_state:
            row = df.sample(1).iloc[0]
            st.session_state.current_word_data = row
            st.session_state.current_word_id = row['id']
            st.session_state.show_answer = False
        
        word = st.session_state.current_word_data
        
        # 手機版面優化：使用大字體
        st.markdown(f"""
        <div style="padding:20px; background:#e3f2fd; border-radius:10px; text-align:center; margin-bottom:10px;">
            <h2 style="color:#1565c0; margin:0;">{word['word']}</h2>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.show_answer:
            st.markdown(f"### {word['meaning']}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ 不熟", use_container_width=True):
                    del st.session_state.current_word_id
                    st.session_state.show_answer = False
                    st.rerun()
            with col2:
                if st.button("✅ 記住了", use_container_width=True):
                    update_status(word['id'], 1)
                    del st.session_state.current_word_id
                    st.session_state.show_answer = False
                    st.rerun()
        else:
            if st.button("查看意思", use_container_width=True):
                st.session_state.show_answer = True
                st.rerun()
    else:
        st.info("沒有單字囉！請去下載單字庫。")

# --- 功能 2: 連連看配對 (新功能) ---
elif choice == "🧩 連連看配對":
    st.header("🧩 單字配對挑戰")
    st.caption("請找出正確的中文意思")

    # 初始化題目
    if 'quiz_data' not in st.session_state:
        df = get_words()
        if len(df) < 5:
            st.warning("單字量不足 5 個，無法開始遊戲。")
        else:
            # 隨機選 5 個字
            quiz_df = df.sample(5)
            st.session_state.quiz_correct_pairs = dict(zip(quiz_df['word'], quiz_df['meaning']))
            st.session_state.quiz_words = quiz_df['word'].tolist()
            # 產生隨機選項 (包含正確答案 + 混淆視聽)
            options = quiz_df['meaning'].tolist()
            random.shuffle(options)
            st.session_state.quiz_options = ["請選擇..."] + options
            st.session_state.quiz_submitted = False

    if 'quiz_words' in st.session_state:
        user_answers = {}
        
        # 顯示題目介面
        with st.form("matching_game"):
            for word in st.session_state.quiz_words:
                st.markdown(f"**{word}**")
                # 每個單字配一個下拉選單
                user_answers[word] = st.selectbox(
                    f"選擇 {word} 的意思:", 
                    st.session_state.quiz_options, 
                    key=f"q_{word}"
                )
                st.markdown("---")
            
            submitted = st.form_submit_button("送出檢查", use_container_width=True)

        if submitted:
            score = 0
            st.session_state.quiz_submitted = True
            st.write("### 📝 結果發表：")
            
            for word, user_ans in user_answers.items():
                correct_ans = st.session_state.quiz_correct_pairs[word]
                if user_ans == correct_ans:
                    st.success(f"✅ {word}：答對了！")
                    score += 1
                else:
                    st.error(f"❌ {word}：答錯了 (正確：{correct_ans})")
            
            if score == 5:
                st.balloons()
                st.markdown("### 🏆 全對！太強了！")
            
            # 再玩一次按鈕
            if st.button("🔄 再玩一局", use_container_width=True):
                del st.session_state.quiz_data
                st.rerun()

# --- 其他功能 ---
elif choice == "📊 單字列表":
    st.header("📚 單字本")
    df = get_words()
    st.dataframe(df, use_container_width=True)

elif choice == "📥 下載單字庫":
    st.header("📥 擴充內容")
    if st.button("下載 2000 個高階單字", type="primary", use_container_width=True):
        download_2000_words()