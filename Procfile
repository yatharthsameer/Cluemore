web: gunicorn server:APP --bind 0.0.0.0:$PORT --workers=2 --timeout=120
release: python -c "from database import db_manager; db_manager.init_database()" 