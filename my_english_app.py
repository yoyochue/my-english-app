import streamlit as st
import sqlite3
import pandas as pd
import random
import os

# --- 資料庫與 CSV 讀取功能 ---

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
    
    # 如果資料庫是空的，自動嘗試讀取 CSV
    c.execute('SELECT count(*) FROM vocab')
    if c.fetchone()[0] == 0:
        load_csv_to_db(conn)
        
    conn.commit()
    conn.close()

def load_csv_to_db(conn=None):
    """讀取本地的 vocabulary.csv 檔案"""
    should_close = False
    if conn is None:
        conn = sqlite3.connect('english_data.db')
        should_close = True
    
    c = conn.cursor()
    
    # 檢查檔案是否存在
    if os.path.exists('vocabulary.csv'):
        try:
            new_data = []
            # 使用 utf-8 讀取，並手動切割確保格式正確
            with open('vocabulary.csv', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 判斷是否要跳過標題 (如果第一行有 word 這個字)
            start_idx = 0
            if len(lines) > 0 and 'word' in lines[0].lower():
                start_idx = 1
                
            for line in lines[start_idx:]:
                line = line.strip()
                if not line: continue
                
                # 只切前兩個逗號 (word, meaning, example...)
                parts = line.split(',', 2)
                
                if len(parts) >= 3:
                    w = parts[0].strip()
                    m = parts[1].strip()
                    e = parts[2].strip().strip('"') # 去除可能存在的引號
                    new_data.append((w, m, e))
                elif len(parts) == 2:
                    new_data.append((parts[0].strip(), parts[1].strip(), ""))

            if new_data:
                # 重新匯入前清空舊資料 (根據你的需求，這樣才能同步 CSV 修改)
                c.execute('DELETE FROM vocab')
                c.executemany('INSERT INTO vocab (word, meaning, example, status) VALUES (?, ?, ?, 0)', new_data)
                conn.commit()
                st.toast(f"✅ 成功讀取 CSV！共 {len(new_data)} 個單字。")
            else:
                st.warning("CSV 檔案是空的！")
                
        except Exception as e:
            st.error(f"讀取 CSV 發生錯誤: {e}")
    else:
        st.error("❌ 找不到 vocabulary.csv！請確認檔案放在同一個資料夾。")

    if should_close:
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

# --- App 介面設定 (手機版優化) ---
st.set_page_config(page_title="英文隨身練 (CSV版)", layout="centered")
init_db()

st.title("📱 英文隨身練 (CSV版)")

# 側邊選單
menu = ["🧠 抽卡模式", "🧩 連連看配對", "📊 單字列表", "🔄 重新讀取 CSV"]
choice = st.sidebar.selectbox("選單", menu)

# --- 功能 1: 抽卡模式 ---
if choice == "🧠 抽卡模式":
    st.header("🔥 單字記憶卡")
    
    # 讀取未背熟 (status=0) 的單字
    df = get_words(0)
    
    if not df.empty:
        if 'current_word_id' not in st.session_state:
            row = df.sample(1).iloc[0]
            st.session_state.current_word_data = row
            st.session_state.current_word_id = row['id']
            st.session_state.show_answer = False
        
        word = st.session_state.current_word_data
        
        # 大字體卡片區
        st.markdown(f"""
        <div style="padding:30px; background:#e3f2fd; border-radius:15px; text-align:center; margin-bottom:20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h2 style="color:#1565c0; font-size: 36px; margin:0;">{word['word']}</h2>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.show_answer:
            st.markdown(f"### 💡 {word['meaning']}")
            if word['example']:
                st.info(f"📝 {word['example']}")
            else:
                st.caption("（暫無例句）")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ 不熟", use_container_width=True):
                    del st.session_state.current_word_id
                    st.session_state.show_answer = False
                    st.rerun()
            with col2:
                if st.button("✅ 記住了", use_container_width=True):
                    update_status(word['id'], 1)
                    st.toast("已標記為熟練！")
                    del st.session_state.current_word_id
                    st.session_state.show_answer = False
                    st.rerun()
        else:
            if st.button("👁️ 查看意思", use_container_width=True, type="primary"):
                st.session_state.show_answer = True
                st.rerun()
    else:
        st.balloons()
        st.success("太棒了！所有單字都背完了！")
        st.info("如果想重新練習，請去「重新讀取 CSV」。")

# --- 功能 2: 連連看配對 ---
elif choice == "🧩 連連看配對":
    st.header("🧩 單字配對挑戰")
    
    if 'quiz_data' not in st.session_state:
        df = get_words()
        # 至少要有 5 個單字才能玩
        if len(df) < 5:
            st.warning(f"單字量不足 (目前只有 {len(df)} 個)，請先在 CSV 加入至少 5 個單字。")
        else:
            quiz_df = df.sample(5)
            st.session_state.quiz_correct_pairs = dict(zip(quiz_df['word'], quiz_df['meaning']))
            st.session_state.quiz_words = quiz_df['word'].tolist()
            options = quiz_df['meaning'].tolist()
            random.shuffle(options)
            st.session_state.quiz_options = ["請選擇..."] + options
            st.session_state.quiz_submitted = False

    if 'quiz_words' in st.session_state:
        user_answers = {}
        with st.form("matching_game"):
            for word in st.session_state.quiz_words:
                st.markdown(f"**{word}**")
                user_answers[word] = st.selectbox(
                    f"選擇意思:", 
                    st.session_state.quiz_options, 
                    key=f"q_{word}",
                    label_visibility="collapsed"
                )
                st.markdown("---")
            
            submitted = st.form_submit_button("送出檢查", use_container_width=True, type="primary")

        if submitted:
            score = 0
            st.write("### 📝 結果：")
            for word, user_ans in user_answers.items():
                correct = st.session_state.quiz_correct_pairs[word]
                if user_ans == correct:
                    st.success(f"✅ {word}")
                    score += 1
                else:
                    st.error(f"❌ {word} (正解: {correct})")
            
            if score == 5:
                st.balloons()
                st.markdown("### 💯 全對！")
            
            if st.button("🔄 再玩一局", use_container_width=True):
                del st.session_state.quiz_data
                st.rerun()

# --- 功能 3: 單字列表 ---
elif choice == "📊 單字列表":
    st.header("📚 單字本")
    df = get_words()
    st.metric("總單字數", len(df))
    st.dataframe(df, use_container_width=True)

# --- 功能 4: 重新讀取 CSV ---
elif choice == "🔄 重新讀取 CSV":
    st.header("資料庫同步")
    st.info("如果你剛剛修改了 CSV 檔案，請點下面的按鈕來更新 App。")
    if st.button("📥 重新載入 CSV 資料", type="primary", use_container_width=True):
        load_csv_to_db()