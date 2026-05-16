import os
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# 載入 .env 檔案中的環境變數
load_dotenv()

# ==========================================
# 1. API 金鑰與環境設定
# ==========================================
# 透過 os.getenv 安全地取得 API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# 初始化 Gemini 模型
model = genai.GenerativeModel('gemini-pro')

# ==========================================
# 2. 模擬爬蟲抓取日文網站資料
# ==========================================
def scrape_japanese_tourism_site(url):
    print(f"開始抓取目標網站: {url}")
    # 這裡為爬蟲雛形，實際情況可依照目標網站的 HTML 結構調整
    # response = requests.get(url)
    # soup = BeautifulSoup(response.text, 'html.parser')
    # text_content = soup.get_text()
    
    # 為了測試，我們在此先模擬一段從日本觀光網站抓下來的非結構化日文介紹
    sample_japanese_text = """
    谷中銀座にある築80年の古民家を改装したカフェ。
    地元のフェアトレード珈琲豆を使用し、使い捨てプラスチックを一切使用していません。
    昭和のレトロな雰囲気を楽しみながら、下町の文化を体験できます。
    アクセス：千代田線千駄木駅から徒歩5分。
    """
    return sample_japanese_text

# ==========================================
# 3. 透過 Gemini 進行翻譯、清洗與標籤化
# ==========================================
def process_data_with_llm(raw_text):
    print("正在將資料交由 Gemini 進行翻譯與 SDG 標籤盤點...")
    
    prompt = f"""
    你現在是一位熟悉聯合國永續發展目標(SDGs)的日本觀光翻譯專家。
    請閱讀以下從日本觀光網站抓取的非結構化日文資料，幫我完成以下任務：
    1. 將內容翻譯為繁體中文，寫成一段吸引人的景點描述。
    2. 根據內文，從以下標籤中挑選符合的 SDG 指標：['老屋活化', '支持在地商店街', '環境友善', '文化體驗']。
    3. 萃取交通方式。
    4. 嚴格以 JSON 格式輸出，不要包含其他多餘的文字。

    JSON 格式範例：
    {{
      "name": "請自行為景點取個合適的中文名稱",
      "description": "翻譯並潤飾後的描述",
      "access": "交通方式",
      "tags": ["標籤1", "標籤2"]
    }}

    待處理日文資料：
    {raw_text}
    """
    
    response = model.generate_content(prompt)
    return response.text

# ==========================================
# 4. 主程式執行區
# ==========================================
if __name__ == "__main__":
    # 目標：針對台東區（如谷根千、淺草周邊）抓取 15-20 筆資料
    target_url = "https://example-tokyo-tourism.jp/yanaka"
    
    # 步驟 A：擷取非結構化資料
    raw_data = scrape_japanese_tourism_site(target_url)
    
    # 步驟 B：透過 LLM 清洗並轉換為 JSON 格式
    clean_json_data = process_data_with_llm(raw_data)
    
    print("\n✅ 資料清洗與轉換完成！符合系統所需的 JSON 結構如下：")
    print(clean_json_data)
    
    # 步驟 C：(未來將加上寫入 MongoDB 的程式碼)
    # TODO: 連線至 MongoDB 並將 BSON/JSON 寫入