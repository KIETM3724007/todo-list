from flask import Flask, jsonify, request
import redis
import bcrypt
import os
import json

app = Flask(__name__)

# Kết nối Redis trên Railway
REDIS_URL = os.getenv("REDIS_URL", "redis://default:glWnCyzNKjSgrxQzLpkriCVKwDBXCgpr@crossover.proxy.rlwy.net:45987")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

#API Đăng ký tài khoản
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")
        name = data.get("name")

        # Kiểm tra thông tin hợp lệ
        if not username or not password or not name:
            return jsonify({"error": "Missing username, password, or name"}), 400

        # Kiểm tra username đã tồn tại chưa
        if redis_client.exists(f"user:{username}"):
            return jsonify({"error": "Username already exists"}), 409

        # Băm mật khẩu
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Lưu thông tin tài khoản vào Redis (dạng JSON)
        user_data = {"username": username, "name": name, "password": hashed_pw}
        redis_client.set(f"user:{username}", json.dumps(user_data))

        return jsonify({"message": "User registered successfully", "username": username}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

#Login
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")

        # Kiểm tra dữ liệu đầu vào
        if not username or not password:
            return jsonify({"error": "Missing username or password"}), 400

        # Lấy dữ liệu user từ Redis
        user_data_json = redis_client.get(f"user:{username}")
        if not user_data_json:
            return jsonify({"error": "User not found"}), 404  # Username không tồn tại

        # Chuyển đổi dữ liệu từ JSON
        user_data = json.loads(user_data_json)

        # Kiểm tra mật khẩu
        if bcrypt.checkpw(password.encode("utf-8"), user_data["password"].encode("utf-8")):
            return jsonify({"message": "Login successful", "username": username}), 200
        else:
            return jsonify({"error": "Invalid password"}), 401  # Sai mật khẩu

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
