from fastapi import FastAPI, Request
import uvicorn
import kosmiczna_magisterka.fast_motor as cmotor

app = FastAPI()

last_number = -1

@app.post('/rotate')
async def rotate(request: Request):
    data = await request.json()
    x,y,z,w = data["orientation"]
    number = data["number"]

    global last_number
    if number < last_number:
        return
    last_number = number

    cmotor.rotation_client(x, y, z, w)

if __name__ == "__main__":
    cmotor.setup()
    cmotor.rotation_server()
    uvicorn.run(app, host="0.0.0.0", port=8888)