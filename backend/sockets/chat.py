from flask import request
from flask_socketio import SocketIO

try:
    from services.rag_service import RagService
except ImportError:
    from backend.services.rag_service import RagService


def register_chat_socket(socketio: SocketIO) -> None:
    # 建立 RAG 服務實例，讓 Socket 層只負責收送訊息，不直接處理 AI 與資料邏輯。
    rag_service = RagService()

    @socketio.on("connect")
    def handle_connect():
        print("SocketIO client connected")

    @socketio.on("disconnect")
    def handle_disconnect():
        print("SocketIO client disconnected")

    @socketio.on("user_message")
    def handle_user_message(data):
        # 前端送來 session_id 與 message；session_id 用來綁定 MongoDB 對話歷史。
        payload = data or {}
        session_id = payload.get("session_id") or "default_session"
        message = payload.get("message", "").strip()

        if not message:
            payload = {
                "session_id": session_id,
                "answer": "請輸入想詢問的旅遊需求。",
                "message": "請輸入想詢問的旅遊需求。",
            }
            socketio.emit("ai_response", payload, to=request.sid)
            return

        print(f"[SocketIO] user_message session_id={session_id} message={message}")

        try:
            answer = rag_service.generate_travel_advice(
                session_id=session_id,
                user_query=message,
            )
            sources = rag_service.get_last_sources()
            recommendations = rag_service.get_last_recommendations()
            print(f"[SocketIO] ai_response session_id={session_id}")
        except Exception as error:
            print(f"[SocketIO] RAG error session_id={session_id}: {error}")
            answer = "AI 永續旅伴目前處理失敗，請稍後再試，或確認後端 API Key 與 MongoDB 連線設定。"
            sources = []
            recommendations = []

        # 回傳 AI 回覆給前端；ai_response 是正式事件。
        payload = {
            "session_id": session_id,
            "answer": answer,
            "message": answer,
            "sources": sources,
            "recommendations": recommendations,
        }
        # 指定 request.sid，避免把某位使用者的 AI 回覆廣播給所有線上使用者。
        socketio.emit("ai_response", payload, to=request.sid)
