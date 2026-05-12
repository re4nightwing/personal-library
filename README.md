# 📚 Home Library

A personal book collection manager with full-text search, colorful tags, and two-factor authentication.

**Stack:** FastAPI · PGroonga (PostgreSQL) · TOTP (Google Authenticator) · Vanilla JS

---

## Project Overview

This project is a robust and secure web application designed to help users manage their personal book collections. It leverages **FastAPI** for a high-performance backend, **PostgreSQL with PGroonga** for efficient full-text search capabilities, and **Vanilla JavaScript** for a dynamic frontend. Key aspects include a secure authentication system with two-factor authentication (TOTP), real-time search, and flexible tag management for organizing books. The application emphasizes security best practices with HttpOnly cookies, security headers, and rate limiting.

---

## Features

- **Fast full-text search** powered by PGroonga — finds books instantly as you type
- **Colorful tags** — create, recolor, and filter by tags in real time
- **Two-factor auth** — username + password + Google Authenticator TOTP code
- **Secure by default** — HttpOnly cookies, security headers, rate limiting, no secrets in JS
- **Keyboard shortcuts** — `Ctrl+K` to search, `Ctrl+N` to add book, `Esc` to close modals

---

## Prerequisites

- Python 3.11+
- PostgreSQL with the **PGroonga** extension (`pgroonga:latest-alpine-17` Docker image)
- Nginx (for production)

---

## Setup

### 1. Clone and install

```bash
git clone <your-repo> /opt/library
cd /opt/library
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env
```

Fill in:

```env
DATABASE_URL=postgresql://libraryuser:yourpassword@localhost:5432/library
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
TOTP_ISSUER=HomeLibrary
SECURE_COOKIES=true
SESSION_MINUTES=60
```

### 3. Create the database

```bash
# Connect to your PGroonga postgres container/server
psql -U postgres -c "CREATE DATABASE library;"
psql -U postgres -c "CREATE USER libraryuser WITH PASSWORD 'yourpassword';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE library TO libraryuser;"
psql -U postgres -d library -c "GRANT ALL ON SCHEMA public TO libraryuser;"
```

The PGroonga extension and tables are created automatically on first startup.

### 4. Add your first user

```bash
source venv/bin/activate
python scripts/manage_users.py add admin
```

You'll be prompted for a password, then a QR code will be shown in the terminal **and** saved as `qr_admin.png`. Scan it with **Google Authenticator**.

**Store the TOTP secret somewhere safe!** You'll need it if you change phones.

### 5. Run the server

**Development:**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Production (systemd):**
```bash
sudo cp library.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable library
sudo systemctl start library
```

### 6. Configure Nginx

```bash
sudo cp nginx.conf /etc/nginx/sites-available/library
# Edit yourdomain.com and SSL cert paths
sudo ln -s /etc/nginx/sites-available/library /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## User Management

```bash
# Add a new user
python scripts/manage_users.py add <username>

# List all users
python scripts/manage_users.py list

# Delete a user
python scripts/manage_users.py delete <username>

# Reset password
python scripts/manage_users.py reset-password <username>

# Show TOTP QR again (e.g. new phone)
python scripts/manage_users.py show-qr <username>
```

---

## Security

| Layer | Implementation |
|-------|---------------|
| Authentication | Username + bcrypt password + TOTP (Google Authenticator) |
| Session | Signed JWT in HttpOnly + Secure + SameSite=Lax cookie |
| Rate limiting | 10 login attempts/minute per IP (slowapi) |
| Headers | CSP, X-Frame-Options, X-Content-Type-Options, HSTS (nginx) |
| SQL | Parameterized queries via asyncpg, no raw string interpolation |
| Transport | HTTPS enforced by nginx, `SECURE_COOKIES=true` |
| API | All endpoints require valid session; Swagger UI disabled |

---

## Project Structure

```
library/
├── app/
│   ├── main.py           # FastAPI app, middleware
│   ├── auth.py           # bcrypt, TOTP, JWT cookie
│   ├── database.py       # asyncpg pool, schema init
│   ├── routers/
│   │   ├── auth.py       # /login, /logout
│   │   ├── books.py      # /api/books, /api/search
│   │   └── tags.py       # /api/tags
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   └── index.html
│   └── static/
│       ├── css/app.css
│       └── js/app.js
├── scripts/
│   └── manage_users.py   # CLI user management + QR generation
├── nginx.conf
├── library.service
├── requirements.txt
└── .env.example
```

---

## PGroonga Search Notes

The app uses PGroonga's `&@~` operator with `TokenBigram` tokenizer. This means:
- Works great for partial matches (e.g. "lord" finds "Lord of the Rings")
- Works for non-Latin scripts too (CJK, Arabic, etc.)
- Results are ranked by relevance score

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Focus search |
| `Ctrl+N` | Add new book |
| `Esc` | Close modal |
| `Enter` | Save in modal |
