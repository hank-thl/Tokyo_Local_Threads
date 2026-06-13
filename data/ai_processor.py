import json
import os
import re
import time

from google import genai

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from pipeline_paths import FINAL_DOCUMENTS_PATH, RAW_DOCUMENTS_PATH, SCRIPT_DIR
except ImportError:
    from data.pipeline_paths import FINAL_DOCUMENTS_PATH, RAW_DOCUMENTS_PATH, SCRIPT_DIR

RAW_INPUT_PATH = RAW_DOCUMENTS_PATH
FINAL_OUTPUT_PATH = FINAL_DOCUMENTS_PATH
MODEL_NAME = "gemini-2.5-flash-lite"
PROCESS_LIMIT = int(os.environ.get("PROCESS_LIMIT", "0")) or None
CATEGORY_FILTER = os.environ.get("CATEGORY_FILTER")

SDG_OPTIONS = [
    "支持在地經濟",
    "在地生產與採購",
    "傳統老店/商店街",
    "友善小農/在地食材",
    "歷史建築保存",
    "傳統工藝傳承",
    "宗教與信仰文化",
    "在地飲食文化",
    "老屋活化",
    "綠色環保旅宿",
    "徒步友善區",
    "減塑/減碳理念",
    "教育與深度體驗",
    "社區發展與回饋",
    "無障礙空間",
    "跨文化交流",
]

# AI 必須補齊這些欄位，才算完成清洗；用於斷點續跑時判斷是否略過。
REQUIRED_AI_FIELDS = {
    "name_zh",
    "description_zh",
    "sdg_tags",
    "ai_context",
    "crowd_level",
    "crowd_reason",
}

# 有些景點文字會提到商店街或市場，但不一定真的和飲食有關。
# 這組詞用來降低「在地飲食文化」被誤標到一般景點上的機率。
FOOD_CONTEXT_TERMS = [
    "飲食",
    "食",
    "料理",
    "餐",
    "咖啡",
    "商店街",
    "横丁",
    "市場",
    "仲見世",
    "アメ横",
    "かっぱ橋",
    "おかず",
]

gemini = None


if load_dotenv:
    load_dotenv(os.path.join(SCRIPT_DIR, "..", ".env"))


def get_api_key() -> str:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("請先設定環境變數 GOOGLE_API_KEY 或 GEMINI_API_KEY")
    return api_key


def get_gemini_client():
    global gemini
    if gemini is None:
        gemini = genai.Client(api_key=get_api_key())
    return gemini


def load_json(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def clean_json_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def has_complete_ai_fields(record: dict) -> bool:
    # 斷點續跑的判斷條件：已經有完整 AI 欄位的資料不重送 API。
    if "name" not in record or "ui_description" not in record:
        return False

    flat_record = {
        "name_zh": record.get("name", {}).get("zh"),
        "description_zh": record.get("ui_description", {}).get("zh"),
        "sdg_tags": record.get("sdg_tags"),
        "ai_context": record.get("ai_context"),
        "crowd_level": record.get("crowd_level"),
        "crowd_reason": record.get("crowd_reason"),
    }
    return all(flat_record.get(field) not in (None, "", []) for field in REQUIRED_AI_FIELDS)


def normalize_crowd_level(value) -> int:
    # crowd_level 統一落在 1 到 5，避免 AI 回傳字串或超出範圍。
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 3

    return max(1, min(5, level))


def has_food_context(raw_document: dict) -> bool:
    if raw_document.get("category") == "restaurant":
        return True

    searchable_text = " ".join(
        [
            raw_document.get("name_jp", ""),
            raw_document.get("description_jp", ""),
            " ".join(raw_document.get("food_categories", [])),
        ]
    )
    return any(term in searchable_text for term in FOOD_CONTEXT_TERMS)


def normalize_sdg_tags(raw_document: dict, tags: list[str]) -> list[str]:
    # 只接受白名單內的 SDG 標籤，避免資料庫出現過多近義但不同名的標籤。
    normalized_tags = []
    for tag in tags:
        if tag not in SDG_OPTIONS:
            continue
        if tag == "在地飲食文化" and not has_food_context(raw_document):
            continue
        if tag not in normalized_tags:
            normalized_tags.append(tag)

    return normalized_tags


def call_gemini(raw_document: dict) -> dict:
    # 將單筆 raw document 交給 Gemini，轉成前端與 RAG 都能使用的結構化資料。
    client = get_gemini_client()
    category_label = "餐廳/美食店家" if raw_document.get("category") == "restaurant" else "景點"
    food_categories = "、".join(raw_document.get("food_categories", [])) or "無"
    prompt = f"""
你是一位熟悉東京台東區、永續旅遊與 SDG 11 的日文旅遊內容編譯員。
請根據以下日文旅遊資料，以 JSON 格式回覆，禁止使用 Markdown 程式碼區塊。

資料類型：{category_label}
美食分類（日文）：{food_categories}
名稱（日文）：{raw_document.get("name_jp", "")}
介紹（日文）：{raw_document.get("description_jp") or "（無介紹）"}

請嚴格輸出以下 JSON 結構，不得添加其他文字：
{{
  "name_zh": "繁體中文名稱",
  "description_zh": "繁體中文介紹（至少 80 字）",
  "sdg_tags": ["標籤1", "標籤2"],
  "ai_context": "AI 背景介紹（繁體中文，至少 150 字，包含歷史背景、文化意義、旅遊建議）",
  "crowd_level": 3,
  "crowd_reason": "20字以內繁中原因"
}}

sdg_tags 請從以下選項中選擇最相關的 2～4 個：
{", ".join(SDG_OPTIONS)}

標籤判斷限制：
- 請只輸出上述選項中的標籤。
- 「在地飲食文化」僅適用於餐廳、美食店家、商店街、市場、飲食相關設施或介紹文字明確提到飲食文化的資料。
- 一般寺廟、河川、公園、博物館、橋梁、紀念碑等景點，不要因為位於觀光區就標註「在地飲食文化」。

crowd_level 評分規則：
1 = 極冷門秘境
2 = 人潮偏少
3 = 普通景點
4 = 熱門但可分流
5 = 過度擁擠地標
"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            time.sleep(4)
            break
        except Exception:
            if attempt == 2:
                raise
            print(f"  [重試 {attempt + 1}/3] Gemini 呼叫失敗，等待 15 秒...")
            time.sleep(15)

    return json.loads(clean_json_text(response.text))


def build_final_record(raw_document: dict, ai_data: dict) -> dict:
    # 最終文件格式會直接匯入 MongoDB documents collection。
    crowd_reason = str(ai_data.get("crowd_reason", "")).strip()
    if len(crowd_reason) > 20:
        crowd_reason = crowd_reason[:20]

    return {
        "category": raw_document.get("category", "spot"),
        "name": {
            "zh": ai_data.get("name_zh", ""),
            "jp": raw_document.get("name_jp", ""),
        },
        "detail_url": raw_document.get("detail_url", ""),
        "image_url": raw_document.get("image_url", ""),
        "google_map_url": raw_document.get("google_map_url", ""),
        "food_categories": raw_document.get("food_categories", []),
        "source_category_url": raw_document.get("source_category_url", ""),
        "ui_description": {
            "zh": ai_data.get("description_zh", ""),
            "jp": raw_document.get("description_jp", ""),
        },
        "sdg_tags": normalize_sdg_tags(raw_document, ai_data.get("sdg_tags", [])),
        "ai_context": ai_data.get("ai_context", ""),
        "crowd_level": normalize_crowd_level(ai_data.get("crowd_level")),
        "crowd_reason": crowd_reason,
    }


def upsert_record(records: list[dict], new_record: dict) -> None:
    # 以 detail_url 當作資料唯一鍵；重新處理時更新原資料而不是新增重複筆。
    detail_url = new_record.get("detail_url")
    for idx, record in enumerate(records):
        if record.get("detail_url") == detail_url:
            records[idx] = new_record
            return
    records.append(new_record)


def main() -> None:
    print("=" * 60)
    print("共生東京資料管線 Step 2：AI 清洗與 SDG / 人潮標註")
    print("=" * 60)
    print(f"模型：{MODEL_NAME}")
    print(f"輸入檔案：{RAW_INPUT_PATH}")
    print(f"輸出檔案：{FINAL_OUTPUT_PATH}")
    print(f"類別過濾：{CATEGORY_FILTER or '全部'}")
    print(f"處理上限：{PROCESS_LIMIT or '不限'}")

    raw_documents = load_json(RAW_INPUT_PATH)
    if not raw_documents:
        raise FileNotFoundError(
            "找不到 raw_documents.json，請先執行：uv run python data/scraper.py"
        )

    results = load_json(FINAL_OUTPUT_PATH)
    completed_urls = {
        record.get("detail_url")
        for record in results
        if has_complete_ai_fields(record)
    }
    # 只挑尚未完成 AI 清洗的資料，讓中斷後可以從上次進度繼續。
    pending = [
        raw_document
        for raw_document in raw_documents
        if raw_document.get("detail_url") not in completed_urls
    ]
    if CATEGORY_FILTER:
        pending = [
            raw_document
            for raw_document in pending
            if raw_document.get("category") == CATEGORY_FILTER
        ]
    if PROCESS_LIMIT is not None:
        pending = pending[:PROCESS_LIMIT]

    print(f"載入 raw document：{len(raw_documents)} 筆")
    print(f"載入既有清洗資料：{len(results)} 筆")
    print(f"待 AI 處理：{len(pending)} 筆")

    for idx, raw_document in enumerate(pending, start=1):
        print(f"\n[{idx}/{len(pending)}] {raw_document.get('name_jp', '')}")
        try:
            ai_data = call_gemini(raw_document)
            final_record = build_final_record(raw_document, ai_data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"  [錯誤] AI 處理失敗：{e}")
            continue

        upsert_record(results, final_record)
        save_json(FINAL_OUTPUT_PATH, results)
        print(
            "  -> 完成："
            f"{final_record['name']['zh']} "
            f"(crowd_level={final_record['crowd_level']})"
        )

    print(f"\nAI 處理完成，共 {len(results)} 筆資料儲存至 {FINAL_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
