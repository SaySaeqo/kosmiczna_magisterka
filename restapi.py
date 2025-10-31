from fastapi import FastAPI, Request
import uvicorn
import kosmiczna_magisterka.fast_motor2 as cmotor2
import logging

app = FastAPI()

last_number = -1

@app.post('/rotate')
async def rotate(request: Request):
    data = await request.json()
    o = data["orientation"]
    x,y,z,w = float(o["x"]),float(o["y"]),float(o["z"]),float(o["w"])
    number = int(data["number"])

    global last_number
    if number < last_number:
        return
    last_number = number

    cmotor2.rotation_client_position(x, y, z, w)

@app.post('/print_globals')
async def print_globals():
    cmotor2.print_globals()

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    cmotor2.setup()
    cmotor2.rotation_server_simple()
    uvicorn.run(app, host="127.0.0.1", port=9090, log_level="warning")
