#!/usr/bin/env python3
"""
User management script for Home Library.

Usage:
  python manage_users.py add <username>          -- create user, shows QR code
  python manage_users.py list                    -- list all users
  python manage_users.py delete <username>       -- remove user
  python manage_users.py reset-password <username> -- set new password
  python manage_users.py show-qr <username>      -- show TOTP QR again

Run BEFORE starting the server for the first time to create the initial admin user.
"""
import sys
import os
import asyncio
import getpass
import io

import qrcode
import asyncpg
from dotenv import load_dotenv

# Resolve project root (one level up from scripts/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load .env from project root
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
from app.auth import hash_password, generate_totp_secret, get_totp_uri
from app.database import init_schema, get_pool


def print_qr_terminal(uri: str):
    """Print a QR code to the terminal as ASCII art."""
    qr = qrcode.QRCode(border=1)
    qr.add_data(uri)
    qr.make(fit=True)

    # Print as text art
    f = io.StringIO()
    qr.print_ascii(out=f)
    f.seek(0)
    print(f.read())


def save_qr_image(uri: str, username: str) -> str:
    """Save QR code as a PNG image and return path."""
    img = qrcode.make(uri)
    path = f"qr_{username}.png"
    img.save(path)
    return path


async def cmd_add(username: str):
    print(f"\n── Creating user: {username} ──")
    password = getpass.getpass("Enter password: ")
    confirm  = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("❌  Passwords do not match.")
        return

    totp_secret = generate_totp_secret()
    totp_uri    = get_totp_uri(totp_secret, username)
    pw_hash     = hash_password(password)

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO users (username, password_hash, totp_secret) VALUES ($1, $2, $3)",
                username, pw_hash, totp_secret,
            )
        except asyncpg.UniqueViolationError:
            print(f"❌  User '{username}' already exists.")
            return

    print(f"\n✅  User '{username}' created!\n")
    print("Scan this QR code in Google Authenticator:\n")
    print_qr_terminal(totp_uri)

    img_path = save_qr_image(totp_uri, username)
    print(f"📄  QR image saved to: {os.path.abspath(img_path)}")
    print(f"\nTOTP Secret (backup): {totp_secret}\n")
    print("⚠️  Store the TOTP secret somewhere safe — you'll need it if you lose your phone.\n")


async def cmd_list():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, username, created_at FROM users ORDER BY id")
    if not rows:
        print("No users found.")
        return
    print(f"\n{'ID':<6} {'Username':<24} Created")
    print("─" * 50)
    for r in rows:
        print(f"{r['id']:<6} {r['username']:<24} {r['created_at'].strftime('%Y-%m-%d %H:%M')}")
    print()


async def cmd_delete(username: str):
    confirm = input(f"Delete user '{username}'? This cannot be undone. [y/N] ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM users WHERE username=$1", username)
    if result == "DELETE 0":
        print(f"❌  User '{username}' not found.")
    else:
        print(f"✅  User '{username}' deleted.")


async def cmd_reset_password(username: str):
    password = getpass.getpass("New password: ")
    confirm  = getpass.getpass("Confirm: ")
    if password != confirm:
        print("❌  Passwords do not match.")
        return
    pw_hash = hash_password(password)
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET password_hash=$1 WHERE username=$2", pw_hash, username
        )
    if result == "UPDATE 0":
        print(f"❌  User '{username}' not found.")
    else:
        print(f"✅  Password updated for '{username}'.")


async def cmd_show_qr(username: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT totp_secret FROM users WHERE username=$1", username
        )
    if not row:
        print(f"❌  User '{username}' not found.")
        return
    uri = get_totp_uri(row["totp_secret"], username)
    print(f"\nQR code for '{username}':\n")
    print_qr_terminal(uri)
    img_path = save_qr_image(uri, username)
    print(f"📄  QR image saved to: {os.path.abspath(img_path)}")
    print(f"\nTOTP Secret: {row['totp_secret']}\n")


async def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]

    # Ensure schema exists before any user operations
    await init_schema()

    if cmd == "add" and len(args) == 2:
        await cmd_add(args[1])
    elif cmd == "list":
        await cmd_list()
    elif cmd == "delete" and len(args) == 2:
        await cmd_delete(args[1])
    elif cmd == "reset-password" and len(args) == 2:
        await cmd_reset_password(args[1])
    elif cmd == "show-qr" and len(args) == 2:
        await cmd_show_qr(args[1])
    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
