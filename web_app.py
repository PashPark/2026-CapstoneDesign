from threading import Lock
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
seat_status = {
    seat_id: {
        "state": "NO DETECT",
        "mean_heat": 0,
        "max_heat": 0,
        "crop_image": "",
        "warning_message": "",
        "hot_object": "",
    }
    for seat_id in ("A1", "A2", "A3", "B1", "B2", "B3")
}
status_lock = Lock()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/update_seats", methods=["POST"])
def update_seats():
    data = request.get_json()
    if data is None:
        return (jsonify({"result": "no data"}), 400)
    with status_lock:
        for seat_id, info in data.items():
            seat_id = seat_id.upper()
            if seat_id not in seat_status:
                seat_status[seat_id] = {
                    "state": "NO DETECT",
                    "mean_heat": 0,
                    "max_heat": 0,
                    "crop_image": "",
                    "warning_message": "",
                    "hot_object": "",
                }
            seat_status[seat_id].update(info)
    return jsonify({"result": "ok"})


@app.route("/seat_status")
def get_seat_status():
    with status_lock:
        return jsonify(seat_status)


@app.route("/seat-data")
def get_seat_data():
    simple_status = {}
    with status_lock:
        for seat_id, info in seat_status.items():
            state = str(info.get("state", "NO DETECT")).upper()
            hot_object = str(info.get("hot_object", "")).lower()
            if state == "HOT":
                simple_status[seat_id] = "hot"
            elif state == "WARN":
                simple_status[seat_id] = "warn"
            elif hot_object in ("handbag", "backpack", "bag"):
                simple_status[seat_id] = "bag"
            elif state == "OK":
                simple_status[seat_id] = "empty"
            else:
                simple_status[seat_id] = "nodetect"
    return jsonify(simple_status)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
