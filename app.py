"""
app.py - FastAPI Uygulama Sunucusu & WebSocket Streaming Hub
- Servis A (Generator), Servis B (Consumer) ve ML Dedektörünü koordine eder.
- Saniyede 1 telemetri üretip analiz eder ve bağlı WebSocket istemcilerine canlı yayınlar.
- Arayüzden gelen anomali enjeksiyon isteklerini karşılar.
"""

import asyncio
import json
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from generator import TelemetryGenerator
from service_b import WorkloadConsumerService
from ml_detector import AnomalyDetectorService

app = FastAPI(title="Outlier Stream Lab - Cloud Telemetry & ML Early Warning")

# Statik dosyaların dizini
app.mount("/static", StaticFiles(directory="static"), name="static")

# Sistem Bileşenleri
generator = TelemetryGenerator()
consumer = WorkloadConsumerService()
detector = AnomalyDetectorService()

# Aktif WebSocket bağlantı havuzu
connected_clients: Set[WebSocket] = set()

class ModeRequest(BaseModel):
    mode: str

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

@app.post("/api/set-mode")
async def set_simulation_mode(req: ModeRequest):
    success = generator.set_mode(req.mode)
    return {"success": success, "current_mode": generator.mode}

@app.post("/api/retrain")
async def retrain_model():
    result = detector.train_baseline()
    return {"success": True, "result": result}

@app.get("/api/state")
async def get_state():
    return {
        "mode": generator.mode,
        "is_model_trained": detector.is_trained,
        "active_clients": len(connected_clients)
    }

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        # İstemciden gelebilecek kontrol mesajlarını dinle (opsiyonel)
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if "mode" in msg:
                    generator.set_mode(msg["mode"])
            except Exception:
                pass
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def stream_broadcaster_loop():
    """Arka planda saniyede 1 çalışan veri boru hattı (Pipeline)"""
    while True:
        try:
            # 1. Servis A telemetri üretir
            telemetry = generator.generate_next()

            # 2. Servis B bu telemetri altında iş yükünü çalıştırır
            service_b_report = consumer.process_telemetry(telemetry)

            # 3. ML Servisi telemetriyi gerçek zamanlı skorlar ve proaktif bildirim üretir
            ml_report = detector.analyze_stream(telemetry)

            # 4. Paketleme ve Yayın
            payload = {
                "telemetry": telemetry,
                "service_b": service_b_report,
                "ml": ml_report,
                "connected_clients": len(connected_clients)
            }

            if connected_clients:
                message = json.dumps(payload)
                # Tüm bağlı arayüzlere yayınla
                dead_clients = set()
                for ws in connected_clients:
                    try:
                        await ws.send_text(message)
                    except Exception:
                        dead_clients.add(ws)
                connected_clients.difference_update(dead_clients)

        except Exception as e:
            print(f"[Stream Error]: {e}")

        await asyncio.sleep(1.0)

@app.on_event("startup")
async def startup_event():
    # Arka plan veri akış döngüsünü başlat
    asyncio.create_task(stream_broadcaster_loop())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
