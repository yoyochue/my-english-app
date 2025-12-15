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
    
    c.execute('SELECT count(*) FROM vocab')
    if c.fetchone()[0] == 0:
        load_csv_to_db(conn)
        
    conn.commit()
    conn.close()

def load_csv_to_db(conn=None):
    should_close = False
    if conn is None:
        conn = sqlite3.connect('english_data.db')
        should_close = True
    
    c = conn.cursor()
    
    if os.path.exists('vocabulary.csv'):
        try:
            new_data = []
            with open('vocabulary.csv', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            start_idx = 0
            if len(lines) > 0 and 'word' in lines[0].lower():
                start_idx = 1
                
            for line in lines[start_idx:]:
                line = line.strip()
                if not line: continue
                
                parts = line.split(',', 2)
                
                if len(parts) >= 3:
                    w = parts[0].strip()
                    m = parts[1].strip()
                    e = parts[2].strip().strip('"')
                    new_data.append((w, m, e))
                elif len(parts) == 2:
                    new_data.append((parts[0].strip(), parts[1].strip(), ""))

            if new_data:
                c.execute('DELETE FROM vocab')
                c.executemany('INSERT INTO vocab (word, meaning, example, status) VALUES (?, ?, ?, 0)', new_data)
                conn.commit()
                st.toast(f"✅ 成功讀取 CSV！共 {len(new_data)} 個單字。")
            else:
                st.warning("CSV 檔案是空的！")
                
        except Exception as e:
            st.error(f"讀取 CSV 發生錯誤: {e}")
    else:
        st.error("❌ 找不到 vocabulary.csv！")

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

# --- App 介面設定 ---
st.set_page_config(page_title="英文隨身練 (CSV版)", layout="centered")
init_db()

st.title("📱 英文隨身練")

# 側邊選單
menu = ["🧠 抽卡模式", "🧩 連連看配對", "📊 單字列表", "🔄 重新讀取 CSV"]
choice = st.sidebar.selectbox("選單", menu)

# --- 功能 1: 抽卡模式 ---
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

# --- 功能 2: 連連看配對 (已修正邏輯) ---
elif choice == "🧩 連連看配對":
    st.header("🧩 單字配對挑戰")
    
    # 初始化題目：只有當 session_state 裡沒有題目時，才去抓新題目
    # 這樣就算按下送出，因為 'quiz_data' 還在，所以不會換題目
    if 'quiz_data' not in st.session_state:
        df = get_words()
        if len(df) < 5:
            st.warning(f"單字量不足 (目前只有 {len(df)} 個)，請先在 CSV 加入至少 5 個單字。")
        else:
            # 隨機選 5 個字並存入 session_state
            quiz_df = df.sample(5)
            st.session_state.quiz_data = quiz_df
            st.session_state.quiz_correct_pairs = dict(zip(quiz_df['word'], quiz_df['meaning']))
            
            # 準備選項
            options = quiz_df['meaning'].tolist()
            random.shuffle(options)
            st.session_state.quiz_options = ["請選擇..."] + options
            
            # 狀態標記：是否已送出答案
            st.session_state.quiz_submitted = False

    # 確保有題目才顯示
    if 'quiz_data' in st.session_state:
        quiz_df = st.session_state.quiz_data
        
        # 使用 Form 表單
        with st.form("matching_game"):
            st.write("請為下列單字選擇正確的中文意思：")
            
            # 這裡用來暫存使用者的選擇
            user_answers = {}
            
            for index, row in quiz_df.iterrows():
                word = row['word']
                st.markdown(f"### **{word}**")
                user_answers[word] = st.selectbox(
                    f"選擇意思:", 
                    st.session_state.quiz_options, 
                    key=f"q_{word}",
                    label_visibility="collapsed"
                )
                st.markdown("---")
            
            # 送出按鈕
            submitted = st.form_submit_button("📝 送出檢查", use_container_width=True, type="primary")

        # --- 判斷邏輯 ---
        if submitted:
            st.session_state.quiz_submitted = True
        
        # 如果已經送出過，就顯示結果與「下一局」按鈕
        if st.session_state.get('quiz_submitted'):
            st.write("### 📊 答題結果")
            score = 0
            
            # 顯示對錯
            for word, user_ans in user_answers.items():
                correct_ans = st.session_state.quiz_correct_pairs[word]
                if user_ans == correct_ans:
                    st.success(f"✅ **{word}**：答對了！")
                    score += 1
                else:
                    st.error(f"❌ **{word}**：答錯了 (正確答案是：{correct_ans})")
            
            if score == 5:
                st.balloons()
                st.markdown("### 💯 全對！太強了！")
            else:
                st.markdown(f"### 得分：{score} / 5")

            st.markdown("---")
            # 按下這個按鈕，才清除舊題目，重新一局
            if st.button("🔄 繼續作答 (下一局)", use_container_width=True, type="primary"):
                del st.session_state.quiz_data
                del st.session_state.quiz_submitted
                # 清除 selectbox 的快取 key，確保下一題選項會重置
                for key in list(st.session_state.keys()):
                    if key.startswith("q_"):
                        del st.session_state[key]
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
    if st.button("📥 重新載入 CSV 資料", type="primary", use_container_width=True):
        load_csv_to_db()