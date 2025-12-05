# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from connection import fetch_and_format_mt5_data
from config import CONFIG

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")


def _df_to_series(df):
    """
    Convert MT5 DataFrame -> structures expected by frontend.

    Returned:
      - price:      [{ time, value }]
      - candles:    [{ time, open, high, low, close, volume, tickvol, spread }]
      - volume:     [{ time, value }]        # real volume (or 0)
      - tickvolume: [{ time, value }]
      - spread:     [{ time, value }]
    """
    price = []
    candles = []
    volume = []
    tickvolume = []
    spread = []

    # print("df", df.head())  # keep for debugging if you like

    for _, row in df.iterrows():
        ts = int(row["time"].timestamp())

        close = float(row["close"])

        vol_val = row.get("volume")
        if vol_val is None or vol_val != vol_val:  # NaN check
            vol_val = 0.0

        tick_val = row.get("tickvol", 0.0)
        spr_val = row.get("spread", 0.0)

        price.append({"time": ts, "value": close})

        candles.append(
            {
                "time": ts,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": close,
                "volume": float(vol_val),
                "tickvol": float(tick_val),
                "spread": float(spr_val),
            }
        )

        volume.append({"time": ts, "value": float(vol_val)})
        tickvolume.append({"time": ts, "value": float(tick_val)})
        spread.append({"time": ts, "value": float(spr_val)})

    return price, candles, volume, tickvolume, spread


@app.get("/api/levels")
def get_levels():
    prev_day = None
    prev_session = None

    # Previous day high/low (D1)
    try:
        daily_df = fetch_and_format_mt5_data(
            CONFIG["symbol"],
            timeframe="D1",
            limit=3,
        )
        if len(daily_df) >= 2:
            row = daily_df.iloc[-2]
            prev_day = {
                "high": float(row["high"]),
                "low": float(row["low"]),
            }
    except Exception as e:
        print("Error fetching D1 levels:", e)

    # Previous 4H session high/low (H4)
    try:
        h4_df = fetch_and_format_mt5_data(
            CONFIG["symbol"],
            timeframe="H4",
            limit=3,
        )
        if len(h4_df) >= 2:
            row = h4_df.iloc[-2]
            prev_session = {
                "high": float(row["high"]),
                "low": float(row["low"]),
            }
    except Exception as e:
        print("Error fetching H4 levels:", e)

    return {
        "prev_day": prev_day,
        "prev_session": prev_session,
    }


@app.get("/api/history")
def get_history():
    df = fetch_and_format_mt5_data(
        CONFIG["symbol"],
        timeframe="M1",
        limit=5000,
    )
    price, candles, volume, tickvolume, spread = _df_to_series(df)
    return {
        "price": price,
        "candles": candles,
        "volume": volume,
        "tickvolume": tickvolume,
        "spread": spread,
    }


@app.get("/api/latest")
def get_latest():
    df = fetch_and_format_mt5_data(
        CONFIG["symbol"],
        timeframe="M1",
        limit=5000,
    )
    price, candles, volume, tickvolume, spread = _df_to_series(df)
    return {
        "price": price[-1],
        "candle": candles[-1],
        "volume": volume[-1],
        "tickvolume": tickvolume[-1],
        "spread": spread[-1],
    }


@app.get("/")
def root():
    return FileResponse(BASE_DIR / "chart.html", media_type="text/html")


@app.get("/chart.html")
def get_chart():
    return FileResponse(BASE_DIR / "chart.html", media_type="text/html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
