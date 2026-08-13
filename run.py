import os
import sys
import uvicorn
from app.config import settings

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 65)
    print(f"Starting {settings.APP_NAME}")
    print(f"Student Portal:  http://127.0.0.1:{settings.PORT}")
    print(f"Admin Dashboard: http://127.0.0.1:{settings.PORT}/admin")
    print(f"OpenAPI Docs:    http://127.0.0.1:{settings.PORT}/docs")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    reload_dirs = [
        os.path.join(base_dir, "app"),
        os.path.join(base_dir, "templates"),
        os.path.join(base_dir, "static", "css"),
        os.path.join(base_dir, "static", "js"),
    ]

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        reload_dirs=reload_dirs,
    )
