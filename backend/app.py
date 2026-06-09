import os

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

try:
    from config import load_config
    from database import init_db
    from routes.api import api_bp
    from sockets.chat import register_chat_socket
except ImportError:
    from backend.config import load_config
    from backend.database import init_db
    from backend.routes.api import api_bp
    from backend.sockets.chat import register_chat_socket

config = load_config()
socketio = SocketIO(cors_allowed_origins=config.cors_origins)


def create_app() -> Flask:
    # 建立 Flask 應用程式實例，作為後端系統中樞。
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key

    # 開放前端 Vue dev server 存取後端 API。
    CORS(app, origins=config.cors_origins)

    # 初始化 SocketIO，後續即時聊天事件會透過 sockets/ 模組註冊。
    socketio.init_app(app)

    # 初始化 MongoDB 連線實例。此階段只建立連線物件，不撰寫查詢邏輯。
    init_db(config)

    # 註冊 REST API Blueprint。
    app.register_blueprint(api_bp, url_prefix="/api")

    # 註冊 SocketIO 事件監聽。
    register_chat_socket(socketio)

    return app


app = create_app()


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5001")),
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
