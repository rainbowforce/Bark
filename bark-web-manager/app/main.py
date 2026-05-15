import os
from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime, timedelta
from typing import Optional, List
import httpx
import urllib.parse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .database import init_db, get_db, PushRecord, Setting

app = FastAPI(title="Bark Web Manager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def startup_event():
    init_db()
    scheduler.start()
    scheduler.add_job(cleanup_old_records, 'cron', hour=2, minute=0, id='cleanup_job')


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()


async def cleanup_old_records():
    db = next(get_db())
    try:
        cleanup_enabled = db.query(Setting).filter(Setting.key == "cleanup_enabled").first()
        if not cleanup_enabled or cleanup_enabled.value != "true":
            return

        cleanup_days = db.query(Setting).filter(Setting.key == "cleanup_days").first()
        days = int(cleanup_days.value) if cleanup_days else 30
        cutoff_date = datetime.now() - timedelta(days=days)
        db.query(PushRecord).filter(PushRecord.created_at < cutoff_date).delete()
        db.commit()
    except Exception as e:
        print(f"Cleanup error: {e}")
        db.rollback()
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    settings = {s.key: s.value for s in db.query(Setting).all()}
    return templates.TemplateResponse("index.html", {"request": request, "settings": settings})


@app.get("/api/v1/records")
async def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    group: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(PushRecord)
    
    if group:
        query = query.filter(PushRecord.group_name == group)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                PushRecord.title.like(search_term),
                PushRecord.body.like(search_term),
                PushRecord.subtitle.like(search_term)
            )
        )
    
    total = query.count()
    records = query.order_by(desc(PushRecord.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    groups = db.query(PushRecord.group_name).filter(PushRecord.group_name.isnot(None)).distinct().all()
    group_list = [g[0] for g in groups]
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "groups": group_list,
        "records": [
            {
                "id": r.id,
                "key": r.key,
                "title": r.title,
                "subtitle": r.subtitle,
                "body": r.body,
                "url": r.url,
                "group_name": r.group_name,
                "icon": r.icon,
                "sound": r.sound,
                "level": r.level,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "status": r.status
            }
            for r in records
        ]
    }


@app.delete("/api/v1/records/{record_id}")
async def delete_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(PushRecord).filter(PushRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    db.commit()
    return {"success": True}


@app.delete("/api/v1/records")
async def delete_records(
    before: Optional[str] = None,
    group: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(PushRecord)
    
    if before:
        try:
            before_date = datetime.fromisoformat(before)
            query = query.filter(PushRecord.created_at < before_date)
        except ValueError:
            pass
    
    if group:
        query = query.filter(PushRecord.group_name == group)
    
    count = query.delete()
    db.commit()
    return {"success": True, "deleted_count": count}


@app.get("/api/v1/settings")
async def get_settings(db: Session = Depends(get_db)):
    settings = db.query(Setting).all()
    return {s.key: s.value for s in settings}


@app.put("/api/v1/settings")
async def update_settings(settings: dict, db: Session = Depends(get_db)):
    for key, value in settings.items():
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    db.commit()
    return {"success": True}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_bark(request: Request, path: str, db: Session = Depends(get_db)):
    bark_server_url = db.query(Setting).filter(Setting.key == "bark_server_url").first()
    base_url = bark_server_url.value if bark_server_url else "http://localhost:8080"
    
    path_parts = path.split("/")
    key = path_parts[0] if path_parts else ""
    
    title = ""
    subtitle = ""
    body = ""
    
    if len(path_parts) >= 2:
        body = urllib.parse.unquote(path_parts[1])
    if len(path_parts) >= 3:
        subtitle = body
        body = urllib.parse.unquote(path_parts[2])
    if len(path_parts) >= 4:
        title = subtitle
        subtitle = body
        body = urllib.parse.unquote(path_parts[3])
    
    query_params = dict(request.query_params)
    
    record = PushRecord(
        key=key,
        title=title or query_params.get("title"),
        subtitle=subtitle or query_params.get("subtitle"),
        body=body or query_params.get("body"),
        url=query_params.get("url"),
        group_name=query_params.get("group"),
        icon=query_params.get("icon"),
        sound=query_params.get("sound"),
        level=query_params.get("level"),
        is_archive=query_params.get("isArchive") == "1",
        status=0
    )
    db.add(record)
    db.commit()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if request.method == "GET":
                response = await client.get(f"{base_url}/{path}", params=query_params)
            else:
                body_data = await request.body()
                response = await client.request(
                    method=request.method,
                    url=f"{base_url}/{path}",
                    params=query_params,
                    content=body_data,
                    headers=dict(request.headers)
                )
        
        record.status = 1 if response.status_code == 200 else 2
        db.commit()
        
        return JSONResponse(
            content=response.json() if response.headers.get("content-type") == "application/json" else response.text,
            status_code=response.status_code
        )
    except Exception as e:
        record.status = 2
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
