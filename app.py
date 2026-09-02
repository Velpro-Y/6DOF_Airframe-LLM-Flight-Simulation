"""
FastAPI

Dify唯一调用入口
"""

import logging

from fastapi import FastAPI

from flight_env import FlightEnv

from models import *

logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s %(levelname)s %(message)s"

)

app = FastAPI(

    title="Flight Simulator",

    version="1.0"

)

env = FlightEnv()




@app.post("/reset")

def reset():

    return env.reset()


@app.post("/step")
def step(action: Action):

    result = env.step(action.model_dump())

    return result


@app.get("/status")

def status():

    return {

        "status":"running",
        "simulation_time":env.time,
        "left_engine_fail":env.left_engine_fail,
        "model":env.model

    }


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        app,

        host= '0.0.0.0',

        port= 8000

    )