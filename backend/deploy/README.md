# Deploying the backend to PythonAnywhere

Replace `USERNAME` everywhere with your PythonAnywhere username.
The server will be at `https://USERNAME.pythonanywhere.com`.

## First-time setup

1. Sign up for a free **Beginner** account at pythonanywhere.com.
2. **Consoles** tab → **Bash**, then run:
   ```
   git clone https://github.com/mobslayer62/get-to-the-points.git
   mkvirtualenv --python=/usr/bin/python3.13 gttp-venv
   cd get-to-the-points/backend
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   ```
3. **Web** tab → **Add a new web app** → **Manual configuration** → **Python 3.13**.
4. On the Web tab, set:
   - **Source code:** `/home/USERNAME/get-to-the-points/backend`
   - **Virtualenv:** `/home/USERNAME/.virtualenvs/gttp-venv`
   - **Static files:** URL `/static/` → Directory `/home/USERNAME/get-to-the-points/backend/staticfiles`
   - **Force HTTPS:** on
5. Click the **WSGI configuration file** link, delete everything in it, and paste
   the contents of `deploy/pythonanywhere_wsgi.py` (fill in USERNAME and the
   secret key). Save.
6. Click **Reload**. Open `https://USERNAME.pythonanywhere.com/api/` — you should
   see the API root.

## Building the app for the online server

On your laptop, phone plugged in:
```
cd front-end-flutter/mobile
flutter build apk --release --dart-define=API_BASE_URL=https://USERNAME.pythonanywhere.com/api
flutter install -d <device id>
```

## Updating after a merge to main

In a PythonAnywhere Bash console:
```
bash ~/get-to-the-points/backend/deploy/update.sh
```
then **Web** tab → **Reload**. The script backs up the database first
(`backend/backups/`, newest 5 kept).

## Every month

Free web apps stop after a month: on the Web tab click
**"Run until 1 month from today"**.

## Notes

- The online database is separate from everyone's laptop databases.
- Never delete or rename migration files that are already on main.
- If something breaks, the **error log** link on the Web tab shows the traceback.
