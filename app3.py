import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time
import base64

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Ghostly", page_icon="👻", layout="centered")

def get_connection():
    return sqlite3.connect('ghostly_v16.db', check_same_thread=False, timeout=30)

conn = get_connection()
cursor = conn.cursor()

cursor.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, display_name TEXT)')
cursor.execute('CREATE TABLE IF NOT EXISTS contacts (owner TEXT, friend TEXT)')
cursor.execute('CREATE TABLE IF NOT EXISTS groups (group_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, creator TEXT)')
cursor.execute('CREATE TABLE IF NOT EXISTS group_members (group_id INTEGER, user TEXT)')
cursor.execute('CREATE TABLE IF NOT EXISTS msgs (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, receiver TEXT, text TEXT, type TEXT, time TEXT, is_group INTEGER DEFAULT 0)')
conn.commit()

# Админ
try:
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?,?,?)", ("administrator", "Ghostly_Admin_2024", "Ghost"))
    conn.commit()
except: pass

st.markdown("<style>.stApp { background: #000; color: white; } .msg-box { background: rgba(255,255,255,0.07); border-radius: 15px; padding: 12px; margin: 5px 0; border: 1px solid #222; } .admin-text { font-size: 24px !important; font-weight: bold !important; color: #ffd700 !important; } .stButton>button { border-radius: 20px; background: #111; color: white; border: 1px solid #333; width: 100%; } input { border-radius: 10px !important; background-color: #111 !important; color: white !important; } #MainMenu, footer, header {visibility: hidden;}</style>", unsafe_allow_html=True)

def main():
    if 'username' not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>👻 Ghostly</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["Вход", "Регистрация"])
        with t1:
            u = st.text_input("Логин", key="l_u")
            p = st.text_input("Пароль", type="password", key="l_p")
            if st.button("ВОЙТИ"):
                u_c = u.replace("@","").strip()
                cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (u_c, p))
                res = cursor.fetchone()
                if res:
                    st.session_state.username = u_c
                    st.session_state.display_name = res[2]
                    st.rerun()
                else: st.error("Ошибка")
        return

    # --- ИНТЕРФЕЙС ---
    st.title(f"👤 {st.session_state.display_name}")
    
    col_g, col_s, col_out = st.columns(3)
    with col_g:
        with st.popover("👥 Группы"):
            g_n = st.text_input("Имя группы")
            if st.button("Создать"):
                cursor.execute("INSERT INTO groups (name, creator) VALUES (?,?)", (g_n, st.session_state.username))
                cursor.execute("INSERT INTO group_members VALUES (?,?)", (cursor.lastrowid, st.session_state.username))
                conn.commit()
                st.rerun()
    with col_s:
        with st.popover("⚙️ Настройки"):
            new_p = st.text_input("Новый пароль", type="password")
            if st.button("Сменить"):
                cursor.execute("UPDATE users SET password=? WHERE username=?", (new_p, st.session_state.username))
                conn.commit()
                st.success("Ок")
    with col_out:
        if st.button("🚪 Выход"):
            del st.session_state.username
            st.rerun()

    # ВЫБОР ЧАТА
    cursor.execute("SELECT friend FROM contacts WHERE owner=?", (st.session_state.username,))
    friends = [f[0] for f in cursor.fetchall()]
    cursor.execute("SELECT groups.name FROM groups JOIN group_members ON groups.group_id = group_members.group_id WHERE group_members.user=?", (st.session_state.username,))
    grps = [f"👥 {g[0]}" for g in cursor.fetchall()]
    target = st.selectbox("💬 Чат:", ["Общий"] + grps + friends)

    # ОКНО ЧАТА
    chat_win = st.container(height=400)
    with chat_win:
        is_admin = st.session_state.username == "administrator"
        if target == "Общий":
            q = "SELECT msgs.*, users.display_name FROM msgs JOIN users ON msgs.sender = users.username WHERE receiver='Общий' ORDER BY id ASC"
        elif target.startswith("👥"):
            gn = target.replace("👥 ", "")
            q = f"SELECT msgs.*, users.display_name FROM msgs JOIN users ON msgs.sender = users.username WHERE receiver='{gn}' AND is_group=1 ORDER BY id ASC"
        else:
            q = f"SELECT msgs.*, users.display_name FROM msgs JOIN users ON msgs.sender = users.username WHERE (sender='{st.session_state.username}' AND receiver='{target}') OR (sender='{target}' AND receiver='{st.session_state.username}') ORDER BY id ASC"
        
        try:
            df = pd.read_sql(q, conn)
            for _, r in df.iterrows():
                me = r['sender'] == st.session_state.username
                adm = r['sender'] == "administrator"
                align = "right" if me else "left"
                style = "class='admin-text'" if adm else ""
                st.markdown(f"<div style='text-align: {align}'><div class='msg-box'><b style='color:#00a381'>{r['display_name']}</b><br>", unsafe_allow_html=True)
                if r['type'] == 'text':
                    st.markdown(f"<span {style}>{r['text']}</span>", unsafe_allow_html=True)
                else:
                    st.image(r['text'], width=250)
                st.markdown("</div></div>", unsafe_allow_html=True)
                if (me or is_admin) and st.button("🗑", key=f"d_{r['id']}"):
                    cursor.execute("DELETE FROM msgs WHERE id=?", (r['id'],))
                    conn.commit()
                    st.rerun()
        except: pass

    # --- ЗОНА ОТПРАВКИ (ТЕКСТ + ФОТО) ---
    st.write("---")
    tab_t, tab_i = st.tabs(["📝 Текст", "🖼 Фото"])
    
    with tab_t:
        with st.form("msg_f", clear_on_submit=True):
            m = st.text_input("Напишите сообщение")
            if st.form_submit_button("Отправить"):
                if m.strip():
                    is_g = 1 if target.startswith("👥") else 0
                    rec = target.replace("👥 ", "")
                    cursor.execute("INSERT INTO msgs (sender, receiver, text, type, time, is_group) VALUES (?,?,?,?,?,?)", (st.session_state.username, rec, m.strip(), 'text', "", is_g))
                    conn.commit()
                    st.rerun()

    with tab_i:
        img_file = st.file_uploader("Выберите картинку", type=['png', 'jpg', 'jpeg'])
        if img_file and st.button("🚀 Отправить фото"):
            is_g = 1 if target.startswith("👥") else 0
            rec = target.replace("👥 ", "")
            enc_img = base64.b64encode(img_file.read()).decode()
            cursor.execute("INSERT INTO msgs (sender, receiver, text, type, time, is_group) VALUES (?,?,?,?,?,?)", (st.session_state.username, rec, f"data:image/png;base64,{enc_img}", 'img', "", is_g))
            conn.commit()
            st.rerun()

    time.sleep(5)
    st.rerun()

if __name__ == "__main__":
    main()