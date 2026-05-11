import streamlit as st
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

from PIL import Image
from pyzbar.pyzbar import decode

def fetch_book_info(isbn):
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    try:
        res = requests.get(url)
        data = res.json()
        if "items" in data:
            book_info = data["items"][0]["volumeInfo"]
            return book_info.get("title", "")
    except:
        pass
    return None

def decode_barcode(image_file):
    try:
        image = Image.open(image_file)
        decoded_objects = decode(image)
        for obj in decoded_objects:
            data = obj.data.decode('utf-8')
            if data.startswith("978") or data.startswith("979"):
                return data
    except:
        pass
    return None
# --- 1. 初期設定 & 接続 ---
@st.cache_resource
def get_global_db():
    return {"tables": {}}
global_db = get_global_db()
def get_gspread_client():
    import os
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            # Streamlit Community Cloud (本番環境) から読み込む
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"], scopes=scopes
            )
        elif os.path.exists("credentials.json"):
            # ローカル環境のファイルから読み込む
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        else:
            return None
        return gspread.authorize(creds)
    except:
        return None

def update_sheet(sheet_name, row_data):
    client = get_gspread_client()
    if client:
        try:
            sh = client.open("Library_Cafe_LUMINA_Data")
            sheet = sh.worksheet(sheet_name)
            sheet.append_row(row_data)
        except Exception as e:
            st.error(f"シート連携エラー: {e}")

def send_discord(msg):
    webhook_url = None
    if "discord_webhook_url" in st.secrets:
        webhook_url = st.secrets["discord_webhook_url"]
        
    if webhook_url and webhook_url != "YOUR_DISCORD_WEBHOOK_URL":
        try:
            requests.post(webhook_url, json={"content": msg})
        except:
            pass

def get_grouped_items(item_list, current_discount):
    grouped = {}
    for item in item_list:
        name = item['name']
        if name not in grouped:
            grouped[name] = {"count": 0, "base_price": item['price']}
        grouped[name]["count"] += 1
    
    result = []
    total_price = 0
    for name, data in grouped.items():
        count = data["count"]
        discounted_unit_price = int(data["base_price"] * current_discount)
        subtotal = discounted_unit_price * count
        total_price += subtotal
        result.append({
            "name": name,
            "count": count,
            "unit_price": discounted_unit_price,
            "subtotal": subtotal
        })
    return result, total_price

# --- 2. 煌びやかなデザイン設定 ---
st.set_page_config(page_title="LUMINA Order System", layout="centered")

st.markdown("""
    <style>
    /* 不要なStreamlit UIを非表示にする */
    [data-testid="stHeader"] { background: transparent !important; }
    .stAppDeployButton { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    footer { visibility: hidden !important; }

    .stApp {
        background-color: #4e342e;
        background-image: url("https://www.transparenttextures.com/patterns/dark-wood.png");
    }
    /* 全体のテキストを明るくする */
    h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, span {
        color: #fdf5e6 !important;
    }
    
    /* ---------- 透過UI (Glassmorphism) ---------- */
    /* サイドバー: ほんの少し茶色めの白木板＋半透明 */
    [data-testid="stSidebar"] {
        background-color: rgba(222, 203, 178, 0.85) !important;
        background-image: url("https://www.transparenttextures.com/patterns/wood-pattern.png") !important;
        backdrop-filter: blur(8px);
    }
    /* サイドバー内のテキストは暗い茶色 */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {
        color: #3e2723 !important;
    }

    /* ボタンの透過と文字色修正 */
    [data-testid="stAppViewContainer"] button {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        backdrop-filter: blur(4px);
    }
    [data-testid="stAppViewContainer"] button p, [data-testid="stAppViewContainer"] button div {
        color: #fdf5e6 !important;
    }
    [data-testid="stAppViewContainer"] button:hover {
        background-color: rgba(255, 255, 255, 0.25) !important;
    }

    /* サイドバー内のボタン */
    [data-testid="stSidebar"] button {
        background-color: rgba(62, 39, 35, 0.1) !important;
        border: 1px solid rgba(62, 39, 35, 0.3) !important;
    }
    [data-testid="stSidebar"] button p, [data-testid="stSidebar"] button div {
        color: #3e2723 !important;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: rgba(62, 39, 35, 0.25) !important;
    }

    /* ---------- 入力ウィジェットの透過 ---------- */
    [data-testid="stAppViewContainer"] [data-baseweb="select"] > div,
    [data-testid="stAppViewContainer"] [data-baseweb="input"] > div,
    [data-testid="stAppViewContainer"] [data-baseweb="textarea"] > div {
        background-color: rgba(0, 0, 0, 0.25) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        backdrop-filter: blur(4px);
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] [data-baseweb="textarea"] > div {
        background-color: rgba(62, 39, 35, 0.1) !important;
        border: 1px solid rgba(62, 39, 35, 0.3) !important;
        backdrop-filter: blur(4px);
    }
    /* 入力エリアの文字色とプレースホルダーを明示的に指定 */
    [data-testid="stAppViewContainer"] [data-baseweb="select"] *,
    [data-testid="stAppViewContainer"] [data-baseweb="input"] input,
    [data-testid="stAppViewContainer"] [data-baseweb="textarea"] textarea {
        color: #fdf5e6 !important;
    }
    [data-testid="stAppViewContainer"] [data-baseweb="input"] input::placeholder,
    [data-testid="stAppViewContainer"] [data-baseweb="textarea"] textarea::placeholder {
        color: rgba(253, 245, 230, 0.5) !important;
    }
    
    [data-testid="stSidebar"] [data-baseweb="select"] *,
    [data-testid="stSidebar"] [data-baseweb="input"] input,
    [data-testid="stSidebar"] [data-baseweb="textarea"] textarea {
        color: #3e2723 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] input::placeholder,
    [data-testid="stSidebar"] [data-baseweb="textarea"] textarea::placeholder {
        color: rgba(62, 39, 35, 0.5) !important;
    }

    /* ---------- 各種カードの透過 ---------- */
    .librarian-box {
        background: linear-gradient(135deg, rgba(75, 0, 130, 0.85), rgba(106, 27, 154, 0.85));
        color: white; padding: 25px; border-radius: 15px;
        border: 2px solid rgba(255, 215, 0, 0.6); 
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        margin-bottom: 30px;
        backdrop-filter: blur(5px);
    }
    .menu-card {
        background: rgba(255, 253, 249, 0.85); 
        border-left: 15px solid rgba(93, 64, 55, 0.9);
        padding: 20px; border-radius: 8px; color: #333;
        margin-bottom: 15px; box-shadow: 5px 5px 15px rgba(0,0,0,0.2);
        backdrop-filter: blur(5px);
    }
    .menu-card h3, .menu-card s, .menu-card div, .menu-card span {
        color: #333 !important;
    }
    .menu-card .gold-price {
        color: #d4af37 !important;
    }
    .timeline-card {
        background: rgba(255, 253, 249, 0.85); 
        border-left: 5px solid rgba(212, 175, 55, 0.9);
        padding: 15px; border-radius: 5px; color: #333;
        margin-bottom: 10px; font-style: italic;
        backdrop-filter: blur(5px);
    }
    .timeline-card span, .timeline-card p, .timeline-card div {
        color: #333 !important;
    }
    .cart-box {
        background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 10px;
        border: 1px dashed rgba(255, 215, 0, 0.5); color: white; margin-top: 20px;
        backdrop-filter: blur(5px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- セッションと画面構成（自動復元＆管理画面） ---
query_params = st.query_params
table_id = query_params.get("table", "不明")

# ================= 管理画面 =================
if table_id == "admin":
    st.set_page_config(page_title="LUMINA Admin", layout="centered")
    st.markdown("<style>.stApp {background-color: #2c3e50;} h1, h2, h3, p, div {color: white !important;} </style>", unsafe_allow_html=True)
    st.title("💻 店長専用 管理画面")
    st.markdown("各テーブルの注文状況（未会計の伝票）とリセット操作が行えます。")
    
    active_tables = [tid for tid in global_db["tables"] if len(global_db["tables"][tid].get("ordered_items", [])) > 0]
    
    if not active_tables:
        st.info("現在、お会計待ちのテーブルはありません。")
    else:
        for t_id in active_tables:
            data = global_db["tables"][t_id]
            st.markdown(f"### Table {t_id}")
            st.write("【注文済みの商品】")
            for item in data["ordered_items"]:
                st.write(f"- {item['name']}")
            
            if st.button(f"💳 Table {t_id} の会計を完了（リセット）", key=f"reset_{t_id}"):
                del global_db["tables"][t_id]
                st.success(f"Table {t_id} のデータをリセットしました！")
                st.rerun()
            st.divider()
    st.stop() # 顧客画面を描画せずにここで終了
# ============================================

# ================= 顧客画面 =================
if table_id not in global_db["tables"]:
    global_db["tables"][table_id] = {
        "cart": [],
        "ordered_items": [],
        "has_paper_book": False,
        "has_ebook": False,
        "scanned_book_title": None,
        "timeline": [
            {"time": "1時間前", "book": "「星の王子さま」 - 何度読んでも新しい発見があります。"},
            {"time": "3時間前", "book": "「銀河鉄道の夜」 - ホットティーと一緒に読むと最高です。"}
        ]
    }

# サーバー側のデータを復元
db_ref = global_db["tables"][table_id]
for key in ["cart", "ordered_items", "has_paper_book", "has_ebook", "scanned_book_title", "timeline"]:
    if key not in st.session_state:
        st.session_state[key] = db_ref[key]

# データをサーバーに保存するための関数（末尾で呼び出す）
def sync_db():
    db_ref["cart"] = list(st.session_state.cart)
    db_ref["ordered_items"] = list(st.session_state.ordered_items)
    db_ref["has_paper_book"] = st.session_state.has_paper_book
    db_ref["has_ebook"] = st.session_state.has_ebook
    db_ref["scanned_book_title"] = st.session_state.scanned_book_title
    db_ref["timeline"] = list(st.session_state.timeline)

st.markdown(f"""
    <div class="librarian-box">
        <span style="font-size: 1.5em;">🐾</span> <b>当カフェの楽しみ方</b><br><br>
        📖 <b>本をご持参の方</b>：下のボタンからスキャンして <b>25% OFF!</b><br>
        💬 <b>おすすめ本をシェア</b>：さらに <b>5% OFF!</b><br>
        最大30%OFFで、ゆったりとした読書の時間をお楽しみください☕<br>
        <br>
        <span style="font-size: 0.8em; color: #eee;">※大切な本を守るため、お済みの食器は一番下のボタンでお呼びいただければお下げします。</span>
    </div>
""", unsafe_allow_html=True)

st.title(f"📖 LUMINA - Table {table_id}")



# --- メインロジック（注文） ---
with st.expander("🎁 割引サービスを利用する（タップして開く）"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<span style='color: #fdf5e6; font-weight: bold;'>📖 本を持参した (25% OFF)</span>", unsafe_allow_html=True)
        
        st.session_state.has_ebook = st.checkbox("📱 電子書籍を持参（会計時に確認）", value=st.session_state.has_ebook)
        
        barcode_img = st.camera_input("📷 紙の本のバーコードをスキャン", key="paper_book_cam")
        if barcode_img:
            if not st.session_state.has_paper_book:
                isbn = decode_barcode(barcode_img)
                if isbn:
                    st.session_state.has_paper_book = True
                    title = fetch_book_info(isbn)
                    st.session_state.scanned_book_title = title if title else "不明な本"
                    st.rerun()
                else:
                    st.error("読み取れませんでした。")
                    
        if st.session_state.has_paper_book:
            if st.session_state.scanned_book_title and st.session_state.scanned_book_title != "不明な本":
                st.success(f"『{st.session_state.scanned_book_title}』を認識しました！(25% OFF適用)")
            else:
                st.success("バーコードを認識しました！(25% OFF適用)")

    with col2:
        st.markdown("<span style='color: #fdf5e6; font-weight: bold;'>💡 おすすめ本を教えてください (5% OFF)</span>", unsafe_allow_html=True)
        rec_book_title = st.text_input("本のタイトル", placeholder="例：星の王子さま")
        rec_book_reason = st.text_area("おすすめの理由・感想", placeholder="何度読んでも新しい発見があります。", height=68)

rec_book = ""
if rec_book_title:
    rec_book = f"『{rec_book_title}』 - {rec_book_reason}" if rec_book_reason else f"『{rec_book_title}』"

discount = 1.0
if st.session_state.has_ebook or st.session_state.has_paper_book: discount -= 0.25
if rec_book_title: discount -= 0.05

st.divider()

# メニューデータ
menu_data = {
    "☕ お飲み物": [
        {"name": "コーヒーブラック", "price": 650, "is_hot_drink": True},
        {"name": "カフェオレ", "price": 700, "is_hot_drink": True},
        {"name": "カプチーノ", "price": 750, "is_hot_drink": True},
        {"name": "カフェラテ", "price": 700, "is_hot_drink": True},
        {"name": "船長特製ブレンド", "price": 750, "is_hot_drink": True},
        {"name": "対馬の和紅茶", "price": 750, "is_hot_drink": True},
        {"name": "ミルクティ", "price": 750, "is_hot_drink": True},
        {"name": "オレンジジュース", "price": 550, "is_hot_drink": False},
        {"name": "ブドウジュース", "price": 550, "is_hot_drink": False},
        {"name": "リンゴジュース", "price": 550, "is_hot_drink": False},
        {"name": "カルピス", "price": 550, "is_hot_drink": False},
    ],
    "🍰 デザート": [
        {"name": "フィナンシェ", "price": 400, "is_hot_drink": False},
        {"name": "ハニーナッツテリーヌ", "price": 700, "is_hot_drink": False},
        {"name": "チーズケーキ", "price": 650, "is_hot_drink": False},
        {"name": "濃厚ガトーショコラ", "price": 700, "is_hot_drink": False},
    ]
}

# 夜限定メニュー(17:00〜翌4:59)
current_hour = datetime.now().hour
if current_hour >= 17 or current_hour < 5:
    menu_data["🌙 夜限定(17:00〜)"] = [
        {"name": "ハニーホットミルク", "price": 650, "is_hot_drink": False}
    ]

st.subheader("📚 メニュー")
tabs = st.tabs(list(menu_data.keys()))

for i, category in enumerate(menu_data.keys()):
    with tabs[i]:
        for item in menu_data[category]:
            base_price = item['price']
            item_name = item['name']
            
            with st.container():
                # オプションの選択（温かい飲み物のみ）
                if item.get('is_hot_drink', False):
                    item_option = st.radio("サイズを選択してください", ["カップ", "ティーポット (+300円)"], key=f"radio_{item_name}")
                    if item_option == "ティーポット (+300円)":
                        base_price += 300
                        item_name += " (ティーポット)"
                        st.info("☕ ティーポットは、ゆっくり読書を楽しみたい方におすすめです。")

                final_price = int(base_price * discount)
                
                st.markdown(f"""
                    <div class="menu-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div><h3 style="margin:0;">{item['name']}</h3><s>¥{base_price}</s></div>
                            <div class="gold-price" style="font-size: 1.4em; font-weight: bold;">¥{final_price}</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"🛒 {item_name} をカートに追加", key=f"add_{item['name']}"):
                    st.session_state.cart.append({"name": item_name, "price": base_price})
                    st.toast(f"{item_name} をカートに追加しました。")

# --- カートと注文確定 ---
if len(st.session_state.cart) > 0:
    st.markdown('<div class="cart-box">', unsafe_allow_html=True)
    st.subheader("🛒 現在のカート")
    grouped_cart, total_price = get_grouped_items(st.session_state.cart, discount)
    
    for item in grouped_cart:
        if item['count'] > 1:
            st.write(f"- {item['name']} × {item['count']} : ¥{item['subtotal']}")
        else:
            st.write(f"- {item['name']} : ¥{item['subtotal']}")
    
    st.markdown(f"**合計金額: ¥{total_price}**")
    
    col_order, col_clear = st.columns(2)
    with col_order:
        if st.button("✨ 注文を確定する", use_container_width=True):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            items_str_list = []
            for item in grouped_cart:
                items_str_list.append(f"{item['name']}(x{item['count']})")
            items_str = ", ".join(items_str_list)
            
            update_sheet("Sales", [now, table_id, items_str, total_price, rec_book if rec_book else "なし"])
            if rec_book:
                update_sheet("Recommendations", [now, rec_book])
                st.session_state.timeline.insert(0, {"time": "たった今", "book": rec_book})
            
            send_discord(f"🔔 **【注文】Table {table_id}**\n内容: {items_str}\n今回の注文金額: ¥{total_price}")
            
            # 注文済みリストに移動
            for item in st.session_state.cart:
                st.session_state.ordered_items.append(item)
            
            st.session_state.cart.clear()
            st.balloons()
            st.success("注文を承りました！少々お待ちください。")
            st.rerun()
            
    with col_clear:
        if st.button("🗑 カートを空にする", use_container_width=True):
            st.session_state.cart.clear()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 注文済みリスト（伝票） ---
if len(st.session_state.ordered_items) > 0:
    st.divider()
    st.subheader("🧾 ご注文伝票（現在のお会計予定）")
    st.markdown('<div class="cart-box" style="border-color: #4CAF50;">', unsafe_allow_html=True)
    
    grouped_ordered, order_total = get_grouped_items(st.session_state.ordered_items, discount)
    for item in grouped_ordered:
        if item['count'] > 1:
            st.write(f"- {item['name']} × {item['count']} : ¥{item['subtotal']}")
        else:
            st.write(f"- {item['name']} : ¥{item['subtotal']}")
    
    st.markdown(f"**合計金額: ¥{order_total}**")
    
    # 電子書籍の割引目視確認が必要かどうか
    needs_check = "（※レジにて電子書籍の目視確認があります）" if st.session_state.has_ebook else ""
    st.markdown(f"<span style='color: #ffcccb;'>{needs_check}</span>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- おすすめ本タイムライン ---
st.divider()
st.subheader("🤝 他のお客様のおすすめ本")
for t in st.session_state.timeline:
    st.markdown(f"""
    <div class="timeline-card">
        <span style="font-size:0.8em; color:#666;">{t['time']}</span><br>
        「{t['book']}」
    </div>
    """, unsafe_allow_html=True)

# --- お会計 ---
st.divider()
if len(st.session_state.ordered_items) > 0:
    if st.button("💳 お会計を依頼する", use_container_width=True):
        grouped_ordered, order_total = get_grouped_items(st.session_state.ordered_items, discount)
        
        items_detail_list = []
        for item in grouped_ordered:
            if item['count'] > 1:
                items_detail_list.append(f"- {item['name']} × {item['count']}: ¥{item['subtotal']}")
            else:
                items_detail_list.append(f"- {item['name']}: ¥{item['subtotal']}")
        items_detail = "\n".join(items_detail_list)
        
        msg = f"💰 **【会計依頼】Table {table_id}**\n"
        msg += f"【注文内訳】\n{items_detail}\n"
        msg += f"**合計金額: ¥{order_total}**"
        
        if st.session_state.has_ebook:
            msg += "\n⚠️ **【注意】電子書籍の目視確認が必要です（割引適用済み）**"
        
        send_discord(msg)
        st.info("レジにてお会計の準備をしております。お忘れ物がないようお気をつけください。")

# --- クイックサービス（おかたづけ・BGM） ---
st.divider()
st.markdown("<h3 style='color: #fdf5e6;'>🛎️ クイックサービス</h3>", unsafe_allow_html=True)
st.markdown('<div class="menu-card">', unsafe_allow_html=True)

if st.button("🧹 食器を下げてほしい", use_container_width=True):
    send_discord(f"🧹 **【食器回収依頼】Table {table_id}**\n本棚を守るため、速やかな回収をお願いします。")
    st.toast("スタッフに伝わりました。そのままお待ちください。")

st.markdown("<hr style='border: 1px solid rgba(0,0,0,0.1);'>", unsafe_allow_html=True)

st.markdown("<h4 style='color: #333;'>🎵 BGMリクエスト</h4>", unsafe_allow_html=True)
bgm_choice = st.selectbox("今の気分に合う音楽は？", ["静かなジャズ", "クラシック", "雨の音", "ケルト音楽", "無音（静寂）"])
if st.button("リクエスト送信", use_container_width=True):
    send_discord(f"🎵 **【BGMリクエスト】Table {table_id}**\n希望BGM: {bgm_choice}")
    st.toast(f"「{bgm_choice}」をリクエストしました！")

st.markdown('</div>', unsafe_allow_html=True)

# スクリプトの最後で常に状態をサーバーに同期・保存する
sync_db()
