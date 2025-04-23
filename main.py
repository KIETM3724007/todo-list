from flask import Flask, jsonify, request
import redis
import bcrypt
import os
import json

main = Flask(__name__)

# Kết nối Redis trên Railway
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://default:QYUJYIiPLwJEJMzAttWUxegSOdapDtKL@hopper.proxy.rlwy.net:49417",
)
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# API Đăng ký tài khoản
@main.route("/register", methods=["POST"])
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

# Login
@main.route("/login", methods=["POST"])
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


# API thêm task mới cho user
@main.route("/add-task", methods=["POST"])
def add_task():
    try:
        data = request.json
        username = data.get(
            "username"
        )  # bắt buộc phải truyền user để gắn task vào user đó
        task = data.get("task")  # phần JSON task như bạn gửi
        print(task)
        if not username or not task:
            return jsonify({"error": "Missing username or task data"}), 400

        # Kiểm tra user tồn tại
        if not redis_client.exists(f"user:{username}"):
            return jsonify({"error": "User not found"}), 404

        # Tạo ID tăng dần cho mỗi task của user
        task_id = redis_client.incr(f"task:{username}:next_id")
        
        # Thêm trường done_at = "" vào task
        task["done_at"] = ""
        task["created_by"] = username
        # Lưu task vào Redis
        redis_client.set(f"task:{username}:{task_id}", json.dumps(task))

        return jsonify({"message": "Task added successfully", "task_id": task_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main.route("/tasks", methods=["POST"])
def get_tasks_by_username():
    try:
        data = request.json
        username = data.get("username")
        
        if not username:
            return jsonify({"error": "Missing username"}), 400

        # Kiểm tra user có tồn tại không
        if not redis_client.exists(f"user:{username}"):
            return jsonify({"error": "User not found"}), 404

        # Tìm tất cả các key theo mẫu task:<username>:*
        pattern = f"task:{username}:*"
        keys = redis_client.keys(pattern)

        # Lọc ra những key có số ID (loại trừ key task:<username>:next_id)
        task_keys = [k for k in keys if not k.endswith(":next_id")]

        tasks = []
        for key in task_keys:
            task_json = redis_client.get(key)
            if task_json:
                task_data = json.loads(task_json)
                # # Xoá description khỏi task
                #task_data.pop("description", None)

                # Xoá img_url nếu tồn tại
                task_data.pop("img_url", None)
                # Xoá description trong từng công việc con (list_work)
                if "list_work" in task_data:
                    for work in task_data["list_work"]:
                        work.pop("description", None)
                task_data["task_id"] = key.split(":")[-1]  # gắn task_id để phân biệt
                task_data["create_by"] = username
                task_data["done_at"] = task_data.get("done_at", "")
                tasks.append(task_data)

        return jsonify({"tasks": tasks}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main.route("/delete-task", methods=["DELETE"])
def delete_task():
    try:
        data = request.get_json()
        username = data.get("username")
        task_id = data.get("task_id")

        if not username or not task_id:
            return jsonify({"error": "Missing username or task_id"}), 400

        task_key = f"task:{username}:{task_id}"

        if not redis_client.exists(task_key):
            return jsonify({"error": "Task not found"}), 404

        redis_client.delete(task_key)

        return jsonify({"message": f"Task {task_id} deleted successfully."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main.route("/update-task", methods=["PUT"])
def update_task():
    try:
        data = request.json
        username = data.get("username")
        task_id = data.get("task_id")
        new_task_data = data.get("task")

        if not username or not task_id or not new_task_data:
            return jsonify({"error": "Missing username, task_id, or task data"}), 400

        task_key = f"task:{username}:{task_id}"

        if not redis_client.exists(task_key):
            return jsonify({"error": "Task not found"}), 404

        # Ghi đè toàn bộ task bằng dữ liệu mới
        redis_client.set(task_key, json.dumps(new_task_data))

        return (
            jsonify({"message": "Task updated successfully", "task": new_task_data}),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    main.run(host="0.0.0.0", port=5000)
