from flask import Flask, request

app = Flask(__name__)

@app.route("/command", methods=["POST"])
def receive_command():

    data = request.json
    command = data["command"]

    print("Received command:", command)

    # Here you call your robot control code
    execute_robot_command(command)

    return {"status": "ok"}


def execute_robot_command(cmd):
    # TODO: parse WALK(), TURN(), SPEAK(), etc
    print("Executing:", cmd)


app.run(host="0.0.0.0", port=5000)