from flask import Blueprint, jsonify, request

try:
    from services.rag_service import RagService
except ImportError:
    from backend.services.rag_service import RagService

# REST API 的 Blueprint。之後所有 HTTP API 都集中從這裡或同層模組註冊。
api_bp = Blueprint("api", __name__)
rag_service = RagService()


@api_bp.get("/health")
def health():
    # 最小健康檢查路由，用於確認 Flask app 與 Blueprint 註冊正常。
    return jsonify(
        {
            "status": "ok",
            "service": "tokyo-local-threads-backend",
        }
    )


@api_bp.get("/documents")
def get_documents():
    # 取得 MongoDB documents collection 的資料列表。
    # 可選 query string:
    # - limit: 回傳筆數上限，預設 20
    # - category: spot 或 restaurant
    limit = request.args.get("limit", default=20, type=int)
    category = request.args.get("category", default=None, type=str)

    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

    documents = rag_service.list_documents(category=category, limit=limit)
    return jsonify(
        {
            "count": len(documents),
            "data": documents,
        }
    )


@api_bp.get("/sdg-tags")
def get_sdg_tags():
    # 取得目前 documents collection 中所有出現過的 SDG 標籤。
    tags = rag_service.list_sdg_tags()
    return jsonify(
        {
            "count": len(tags),
            "data": tags,
        }
    )
