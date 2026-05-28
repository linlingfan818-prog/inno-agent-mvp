import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.chat import router as chat_router

app = FastAPI(title="INNO-Agent High Concurrency Engine")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 挂载 API
app.include_router(chat_router, prefix="/api/v1")

# 挂载前端页面
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

@app.get("/api/download")
async def download_file(file: str):
    import urllib.parse
    # The file query param will be automatically URL-decoded by FastAPI
    # Ensure it doesn't try to access directories outside static/reports
    safe_file = os.path.basename(file)
    file_path = os.path.join("static", "reports", safe_file)
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path, 
            filename=safe_file,
            media_type="application/octet-stream"
        )
    return {"error": "File not found"}

if __name__ == "__main__":
    import uvicorn
    # 异步高并发启动
    port = int(os.getenv("PORT", 8001))  # 👈 它是去读系统环境
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)