"""Talousvalmentaja - AI personal finance coach. Run:  python main.py  -> http://localhost:8931
(PORT / HOST env vars override; use HOST=0.0.0.0 to open it from a phone on the same Wi-Fi.)"""
from __future__ import annotations

import os
import pathlib


def _load_dotenv(path: pathlib.Path) -> None:
    """Read KEY=value lines from .env (real environment variables win)."""
    if not path.exists():
        return
    for line in path.read_text("utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip().removeprefix("export ").strip(), v.strip().strip('"').strip("'"))


_load_dotenv(pathlib.Path(__file__).resolve().parent / ".env")

import logging  # noqa: E402
import time  # noqa: E402
from typing import Literal  # noqa: E402

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from coach import agent
from coach import analytics as A
from coach.data import customers, load_all

log = logging.getLogger("talousvalmentaja")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
WEB = pathlib.Path(__file__).resolve().parent / "web"
app = FastAPI(title="Talousvalmentaja – Personal Finance Coach", version="1.0.0")
STARTED = time.time()


@app.exception_handler(ValueError)
async def _bad_input(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)


def ok(x):
    return JSONResponse(A.clean(x))


def _check(cid: str):
    if cid not in {c["id"] for c in customers()}:
        raise HTTPException(404, f"unknown customer {cid}")


class ChatIn(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, max_length=64)
    include_other_banks: bool = True


class ReclassIn(BaseModel):
    basket: Literal["regular", "irregular", "everyday"]
    category: str | None = Field(default=None, max_length=100)
    merchant: str | None = Field(default=None, max_length=100)


@app.get("/api/health")
def health():
    return {"status": "ok", "uptime_s": round(time.time() - STARTED), "customers": len(customers()),
            "ai_provider": agent.provider()}


@app.get("/api/status")
def status():
    p = agent.provider()
    return {"ai": p != "offline", "provider": p, "model": agent.model_name()}


@app.get("/api/customers")
def api_customers():
    return customers()


@app.get("/api/{cid}/overview")
def api_overview(cid: str):
    _check(cid)
    return ok(A.overview(cid))


@app.get("/api/{cid}/baskets")
def api_baskets(cid: str, period: str = "last_3_months", other_banks: bool = True):
    _check(cid)
    return ok(A.basket_summary(cid, period, other_banks))


@app.get("/api/{cid}/trend")
def api_trend(cid: str):
    _check(cid)
    return ok(A.monthly_trend(cid))


@app.get("/api/{cid}/explore")
def api_explore(cid: str, period: str = "last_3_months", group_by: str = "category", category: str | None = None,
                merchant: str | None = None, basket: str | None = None, other_banks: bool = True):
    _check(cid)
    try:
        return ok(A.query(cid, period=period, group_by=group_by, category=category, merchant=merchant,
                          basket=basket, include_other_banks=other_banks))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/{cid}/transactions")
def api_txns(cid: str, basket: str | None = None, q: str | None = None, limit: int = 60):
    _check(cid)
    return ok(A.transactions(cid, limit, basket, q))


@app.get("/api/{cid}/whatif")
def api_whatif(cid: str, reduce_pct: float = 20, category: str | None = None, basket: str | None = None,
               annual_return: float = 0.03):
    _check(cid)
    return ok(A.what_if(cid, reduce_pct, category=category, basket=basket, annual_return=annual_return))


@app.get("/api/{cid}/categories")
def api_categories(cid: str):
    _check(cid)
    sp = A.spending(cid)
    g = sp.groupby(["category", "basket"])["spend"].sum().reset_index().sort_values("spend", ascending=False)
    return ok([{"category": r["category"], "basket": r["basket"]} for _, r in g.iterrows()])


@app.post("/api/{cid}/reclassify")
def api_reclassify(cid: str, body: ReclassIn):
    _check(cid)
    try:
        return ok(A.reclassify(cid, body.basket, body.category, body.merchant))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/chat")
def api_chat(body: ChatIn):
    _check(body.customer_id)
    t = time.time()
    r = agent.chat(body.customer_id, body.message.strip(), body.session_id, body.include_other_banks)
    # log engine, tools and latency only - never message content or amounts
    log.info("chat engine=%s tools=%s %.1fs", r.get("engine"), ",".join(r.get("tools", [])), time.time() - t)
    return ok(r)


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")

if __name__ == "__main__":
    import os

    import uvicorn
    load_all()  # build / load the dataset before serving
    for c in customers():  # warm the analytics cache so the first screen is instant
        A.overview(c["id"])
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8931")))
