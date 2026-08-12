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

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        # Watch only source files. Without this the reloader also watches
        # course_sales.db and static/uploads, so every registration or file
        # upload would restart the server and briefly refuse connections.
        reload_dirs=["app", "templates", "static/css", "static/js"],
        reload_includes=["*.py", "*.html", "*.css", "*.js"]
    )
