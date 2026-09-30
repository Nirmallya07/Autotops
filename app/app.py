from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "project": "AutoTops",
        "message": "Autonomous Troubleshooting and Operations Platform",
        "status": "running"
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy"
    }), 200


@app.route("/failure")
def failure():
    return jsonify({
        "status": "failure",
        "message": "Intentional test failure for AutoTops"
    }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)