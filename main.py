import sys
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

MAX_CONCURRENT = 10
REQUEST_TIMEOUT = 10

R = "\033[38;5;196m"
G = "\033[38;5;46m"
Y = "\033[38;5;226m"
D = "\033[38;5;240m"
W = "\033[0m"


def parse_proxy(proxy_line: str) -> dict | None:
    parts = proxy_line.strip().split(":")
    if len(parts) != 4:
        return None
    host, port, username, password = parts
    proxy_url = f"http://{username}:{password}@{host}:{port}"
    return {"http": proxy_url, "https": proxy_url}


def load_proxies(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        proxies = [parse_proxy(line) for line in f if line.strip()]
    return [p for p in proxies if p is not None]


def send_discord_webhook(webhook_url: str, username: str):
    payload = {
        "embeds": [{
            "title": f"Available username: {username}",
            "description": f"`{username}` is available on osu!",
            "color": 0x00ff00
        }]
    }
    try:
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception:
        pass


def check_username(username: str, proxy: dict | None) -> dict | str | None:
    url = "https://osu.ppy.sh/users/check-username-availability"
    headers = {
        "Host": "osu.ppy.sh",
        "Cookie": f"XSRF-TOKEN={os.environ.get('XSRF_TOKEN')}; osu_session={os.environ.get('OSU_SESSION')}",
        "X-Csrf-Token": os.environ.get("XSRF_TOKEN"),
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
        "Origin": "https://osu.ppy.sh",
        "Referer": "https://osu.ppy.sh/store/products/username-change",
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        r = requests.post(url, headers=headers, data={"username": username}, proxies=proxy, timeout=REQUEST_TIMEOUT)
        if not r.text.strip():
            return None
        return r.json()
    except requests.exceptions.ProxyError:
        return "proxy_error"
    except requests.exceptions.Timeout:
        return "timeout"
    except Exception:
        return None


def process(username: str, proxy: dict | None, webhook_url: str | None):
    data = check_username(username, proxy)

    if data in ("proxy_error", "timeout", None):
        return

    if data.get("available"):
        print(f"  {G}[AVAILABLE]{W}  {username}")
        if webhook_url:
            send_discord_webhook(webhook_url, username)
        return

    message = re.sub(r"<[^>]+>", "", data.get("message", "")).strip()

    if message == "Username is already in use!":
        print(f"  {R}[TAKEN    ]{W}  {username}")
    elif message == "This username choice is not allowed.":
        print(f"  {R}[BLOCKED  ]{W}  {username}")
    elif message == "The requested username contains invalid characters.":
        print(f"  {R}[INVALID  ]{W}  {username}")
    elif "supported osu!" in message:
        print(f"  {D}[TAKEN    ]{W}  {username}")
    elif m := re.search(r"available for use in (.+)$", message):
        print(f"  {Y}[COOLDOWN ]{W}  {username}  {D}{m.group(1)}{W}")


def main():
    print()
    print(f"  \033[1mosu! username checker\033[0m")
    print(f"  {D}{'─' * 36}{W}")
    print()

    usernames_path = input("  usernames file  : ").strip()
    if not os.path.isfile(usernames_path):
        print(f"\n  {R}file not found{W}\n")
        sys.exit(1)

    proxies_path = input("  proxies file    : ").strip()
    webhook_url  = input("  discord webhook : ").strip() or None

    with open(usernames_path, "r", encoding="utf-8") as f:
        usernames = [line.strip() for line in f if line.strip()]

    if not usernames:
        print(f"\n  {R}no usernames found{W}\n")
        sys.exit(1)

    proxies = []
    if proxies_path:
        if not os.path.isfile(proxies_path):
            print(f"\n  {R}proxy file not found{W}\n")
            sys.exit(1)
        proxies = load_proxies(proxies_path)

    print()
    print(f"  {D}{'─' * 36}{W}")
    print()

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = {
            executor.submit(process, username, proxies[i % len(proxies)] if proxies else None, webhook_url): username
            for i, username in enumerate(usernames)
        }
        for future in as_completed(futures):
            future.result()

    print()
    print(f"  {D}{'─' * 36}{W}")
    print(f"  done  {D}({len(usernames)} checked){W}")
    print()


if __name__ == "__main__":
    main()
