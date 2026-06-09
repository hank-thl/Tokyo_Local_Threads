# 《共生東京》永續旅遊與分流引導平台 (Backend)

本專案為《共生東京》平台的後端核心與資料管線 PoC，專門針對日本東京台東區（淺草、上野、谷中等）常見的過度旅遊（Overtourism）問題進行設計。

系統透過爬蟲蒐集在地景點與餐廳資料，使用 AI 進行繁體中文清洗、SDG 標籤判斷與擁擠度分級，並將資料存入 MongoDB Atlas。前端則透過 Flask API 動態取得資料，後續將串接 RAG（檢索增強生成）與 WebSocket，讓 AI 旅伴即時提供具備永續與分流意識的深度旅遊建議。

## 系統架構與設計模式

本專案採用前後端分離架構，後端使用 Service-Repository 分層設計，讓 API、業務邏輯與資料存取責任清楚分離。

### 1. Presentation / Routing Layer

- `backend/routes/api.py`
  - 提供 HTTP REST API。
  - 目前包含：
    - `GET /api/health`
    - `GET /api/documents`
    - `GET /api/sdg-tags`

- `backend/sockets/chat.py`
  - 預留 WebSocket 即時聊天事件。
  - 目前包含 `connect` 與 `disconnect` 監聽。

### 2. Service Layer

- `backend/services/rag_service.py`
  - 作為 API 與 Repository 的中介層。
  - 目前先提供文件列表與 SDG 標籤取得。
  - 後續會封裝 LangChain、LLM 與 RAG 流程。

### 3. Repository Layer

- `backend/repositories/spot_repository.py`
  - 封裝 MongoDB documents collection 的資料存取。
  - 目前提供：
    - 取得 documents
    - 取得所有 `sdg_tags`

### 4. Data Pipeline

- `data/scraper.py`
  - 爬取台東區景點資料。
  - 最多爬取 50 筆景點。

- `data/restaurant_scraper.py`
  - 爬取台東區餐廳資料。
  - 所有餐廳類別都會爬，但每類最多 5 筆。
  - 餐廳地圖會轉換成免 API key 的 Google Maps embed URL。

- `data/ai_processor.py`
  - 讀取 raw documents。
  - 呼叫 Gemini 進行繁中翻譯、SDG 標籤、擁擠度分級與 AI 背景介紹生成。

- `data/import_to_mongodb.py`
  - 將 `data/taito_documents.json` 匯入 MongoDB Atlas。

## 技術棧

- Backend: Flask, Flask-CORS, Flask-SocketIO
- Database: MongoDB Atlas, PyMongo
- AI / RAG: LangChain, Gemini API
- Data Pipeline: requests, BeautifulSoup, Google GenAI SDK
- Package Manager: uv
- Frontend: Vue 3, Vite, Tailwind CSS

## 專案目錄

```text
.
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── database.py
│   ├── routes/
│   │   └── api.py
│   ├── sockets/
│   │   └── chat.py
│   ├── services/
│   │   └── rag_service.py
│   └── repositories/
│       └── spot_repository.py
├── data/
│   ├── scraper.py
│   ├── restaurant_scraper.py
│   ├── ai_processor.py
│   ├── import_to_mongodb.py
│   ├── raw_documents.json
│   └── taito_documents.json
├── frontend/
├── pyproject.toml
├── uv.lock
└── README.md
```

## 本地開發指南

### 1. 安裝 Python 依賴

本專案使用 `uv` 管理 Python 環境。

```bash
uv sync
```

### 2. 設定環境變數

請在專案根目錄建立 `.env`：

```env
GEMINI_API_KEY=your_gemini_api_key
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster-url>/?retryWrites=true&w=majority&appName=Cluster0
```

可選設定：

```env
MONGODB_DB_NAME=tokyo_local_threads
MONGODB_COLLECTION_NAME=documents
CORS_ORIGINS=http://localhost:5173
PORT=5004
```

### 3. 執行資料管線

爬取景點 raw data：

```bash
uv run python data/scraper.py
```

爬取餐廳 raw data：

```bash
uv run python data/restaurant_scraper.py
```

執行 AI 清洗：

```bash
uv run python data/ai_processor.py
```

匯入 MongoDB Atlas：

```bash
uv run python data/import_to_mongodb.py
```

目前匯入來源為：

```text
data/taito_documents.json
```

### 4. 啟動 Flask 後端

```bash
PORT=5004 uv run python backend/app.py
```

啟動後可測試：

```text
GET http://127.0.0.1:5004/api/health
GET http://127.0.0.1:5004/api/documents?limit=5
GET http://127.0.0.1:5004/api/sdg-tags
```

### 5. 啟動 Vue 前端

```bash
cd frontend
npm install
npm run dev
```

前端目前會透過 Fetch API 讀取 Flask 後端：

```text
GET /api/documents
GET /api/sdg-tags
```

若後端不是跑在 `http://127.0.0.1:5004`，請在 `frontend/.env` 設定：

```env
VITE_API_BASE_URL=http://127.0.0.1:5004
```

## API 文件

### Health Check

```http
GET /api/health
```

回傳：

```json
{
  "status": "ok",
  "service": "tokyo-local-threads-backend"
}
```

### 取得 Documents

```http
GET /api/documents
```

Query parameters:

- `limit`: 回傳筆數，預設 20，上限 100。
- `category`: 可選 `spot` 或 `restaurant`。

範例：

```http
GET /api/documents?category=spot&limit=5
```

### 取得所有 SDG 標籤

```http
GET /api/sdg-tags
```

回傳目前 MongoDB documents collection 中所有出現過的 `sdg_tags`。

## 資料結構

MongoDB collection: `documents`

每筆 document 大致包含：

```json
{
  "category": "spot",
  "name": {
    "zh": "淺草寺",
    "jp": "浅草寺"
  },
  "detail_url": "https://t-navi.city.taito.lg.jp/spot/1001",
  "image_url": "https://...",
  "google_map_url": "https://www.google.com/maps?q=...&output=embed",
  "ui_description": {
    "zh": "繁體中文介紹",
    "jp": "日文原文介紹"
  },
  "sdg_tags": ["歷史建築保存", "宗教與信仰文化"],
  "ai_context": "供 RAG 使用的背景內容",
  "crowd_level": 5,
  "crowd_reason": "東京代表性地標，全年人潮眾多",
  "food_categories": []
}
```

## 目前完成狀態

- 已完成景點與餐廳 raw data 爬取。
- 已完成 AI 清洗流程。
- 已完成 MongoDB Atlas 匯入腳本。
- 已完成 Flask Service-Repository 後端骨架。
- 已完成 documents 與 sdg-tags API。
- 已完成 Vue 前端 Fetch API 串接。

## 後續開發項目

- 在 `SpotRepository` 補上更完整的 MongoDB 檢索條件。
- 在 `RagService` 串接 LangChain RAG 流程。
- 在 `sockets/chat.py` 補上 WebSocket 聊天事件與 streaming 回覆。
- 將使用者問題、SDG 偏好與 crowd level 納入推薦策略。
