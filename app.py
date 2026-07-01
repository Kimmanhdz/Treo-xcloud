#!/usr/bin/env python3
"""
MKMusic Auto Renew — MK-TOOL EDITION (Full Support Exit Menu)
"""

import asyncio
import logging
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import box

# ─────────────────────────────────────────────
# ĐƯỜNG DẪN FILE CẤU HÌNH JSON
# ─────────────────────────────────────────────
ACCOUNT_FILE = Path(__file__).parent / "accounts.json"
EMAIL        = ""   
PASSWORD     = ""   

# ─────────────────────────────────────────────
# CÀI ĐẶT THỜI GIAN
# ─────────────────────────────────────────────
API_BASE          = "https://api.xcloudphone.com"
APP_BASE          = "https://app.xcloudphone.com"
RENEW_THRESHOLD_H = 4        
MAX_LIMIT_H       = 5        
POLL_INTERVAL_S   = 30       

console = Console()
logging.basicConfig(
    filename=Path.home() / ".xcloud_autorenew.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("xcloud")

# ─────────────────────────────────────────────
# MENU ĐĂNG NHẬP GỌN ĐẸP (SỬA LỖI THOÁT MENU)
# ─────────────────────────────────────────────
def load_or_create_account():
    global EMAIL, PASSWORD
    
    saved_email = ""
    saved_password = ""
    
    # Đọc cấu hình cũ từ accounts.json nếu có
    if ACCOUNT_FILE.exists():
        try:
            with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                saved_email = data.get("username", "").strip()
                saved_password = data.get("password", "").strip()
        except Exception:
            pass

    # LỰA CHỌN 1: Nếu đã tồn tại tài khoản cũ -> Hiện Menu lựa chọn nhanh gọn
    if saved_email and saved_password:
        while True:
            console.clear()
            console.print(
                Panel.fit(
                    f"[green]✓ Đã tải tài khoản đã lưu thành công[/green]\n\n"
                    f"Tài khoản hiện tại: [cyan]{saved_email}[/cyan]",
                    title="🔑 LOGIN SYSTEM",
                    border_style="green",
                    padding=(1, 5)
                )
            )
            console.print(" [bold yellow][1][/bold yellow] Tiếp tục đăng nhập bằng tài khoản này")
            console.print(" [bold yellow][2][/bold yellow] Đổi tài khoản khác (Nhập mới)")
            console.print(" [bold yellow][3][/bold yellow] Thoát Tool")
            console.print("[dim]──────────────────────────────────────────────────────────[/dim]\n")
            
            choice = Prompt.ask("[bold green]▸ Nhập lựa chọn (1-3)[/bold green]", choices=["1", "2", "3"], default="1")
            
            if choice == "1":
                EMAIL = saved_email
                PASSWORD = saved_password
                return
            elif choice == "2":
                break  
            elif choice == "3":
                console.print("[bold red]👋 Đang thoát chương trình...[/bold red]")
                sys.exit(0)

    # LỰA CHỌN 2: Chưa có tài khoản / Hoặc chọn nhập mới -> Hiện Form chuẩn Đẹp gọn
    while True:
        console.clear()
        console.print(
            Panel.fit(
                "[bold cyan]☁ XCP LOGIN SYSTEM[/bold cyan]\n"
                "[white]Vui lòng cấu hình tài khoản XCloud để bắt đầu[/white]",
                title="CẤU HÌNH",
                border_style="bright_blue",
                padding=(1, 4)
            )
        )
        
        console.print(" [bold yellow][1][/bold yellow] Tiếp tục nhập tài khoản mới")
        console.print(" [bold red][2][/bold red] Huỷ bỏ và Thoát Tool")
        console.print("[dim]──────────────────────────────────────────────────────────[/dim]\n")
        
        menu_choice = Prompt.ask("[bold green]▸ Nhập lựa chọn (1-2)[/bold green]", choices=["1", "2"], default="1")
        
        if menu_choice == "2":
            console.print("[bold red]👋 Đang thoát chương trình...[/bold red]")
            sys.exit(0)
            
        # Nếu chọn 1 thì tiến hành nhập User/Pass công khai hiện chữ
        console.print("")
        EMAIL = Prompt.ask("[cyan]▸ Username / Email[/cyan]").strip()
        PASSWORD = Prompt.ask("[cyan]▸ Password (Hiện chữ)[/cyan]").strip()

        if not EMAIL or not PASSWORD:
            console.print("\n[bold red]❌ Tài khoản và mật khẩu không được bỏ trống! Xin thử lại...[/bold red]")
            time.sleep(1.5)
            continue

        # Ghi lại thông tin vào file accounts.json và thoát vòng lặp nhập liệu
        try:
            with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
                json.dump({"username": EMAIL, "password": PASSWORD}, f, indent=4, ensure_ascii=False)
            console.print("\n[bold green]✓ Đã lưu cấu hình tài khoản thành công![/bold green]")
            time.sleep(1)
            break
        except Exception:
            break


# ─────────────────────────────────────────────
# ĐĂNG NHẬP API
# ─────────────────────────────────────────────
_LOGIN_HEADERS = {
    "Content-Type": "application/json",
    "Origin":       APP_BASE,
    "Referer":      APP_BASE + "/",
    "User-Agent":   "Mozilla/5.0 (XCloudAutoRenew/Python)",
}

def _deep_find(obj, *keys):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str) and len(v) > 20:
                return v
            found = _deep_find(v, *keys)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find(item, *keys)
            if found:
                return found
    return None

async def do_login(email: str, password: str) -> Optional[dict]:
    all_cookies: dict = {}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            r = await client.post(
                f"{API_BASE}/auth/renters/login",
                headers=_LOGIN_HEADERS,
                json={"username": email, "password": password},
                timeout=20,
            )
            for resp in ([r] + list(r.history)):
                for name, value in resp.cookies.items():
                    all_cookies[name] = value
                for hname, hval in resp.headers.multi_items():
                    if hname.lower() == "set-cookie":
                        part = hval.split(";")[0].strip()
                        if "=" in part:
                            k, v = part.split("=", 1)
                            all_cookies[k.strip()] = v.strip()
        except Exception:
            return None

    if r.status_code not in (200, 201):
        return None

    ACCESS_KEYS  = ("renterAccessToken",  "accessToken",  "access_token",  "token", "jwt")
    REFRESH_KEYS = ("renterRefreshToken", "refreshToken", "refresh_token", "refreshJwt")

    access = refresh = None
    try:
        body    = r.json()
        access  = _deep_find(body, *ACCESS_KEYS)
        refresh = _deep_find(body, *REFRESH_KEYS)
    except Exception:
        pass

    if not access:
        access  = all_cookies.get("renterAccessToken") or all_cookies.get("accessToken")
        refresh = all_cookies.get("renterRefreshToken") or all_cookies.get("refreshToken")

    if not access:
        return None

    return {"renterAccessToken": access, "renterRefreshToken": refresh or ""}

async def refresh_token_flow(tokens: dict) -> Optional[dict]:
    refresh = tokens.get("renterRefreshToken")
    if not refresh:
        return None
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.post(
                f"{API_BASE}/auth/renters/refresh-token",
                headers={**_LOGIN_HEADERS, "Authorization": f"Bearer {refresh}"},
                json={"refreshToken": refresh},
                timeout=15,
            )
        if r.status_code not in (200, 201):
            return None
        body    = r.json()
        access  = _deep_find(body, "renterAccessToken", "accessToken", "access_token", "token")
        new_ref = _deep_find(body, "renterRefreshToken", "refreshToken", "refresh_token") or refresh
        if access:
            return {"renterAccessToken": access, "renterRefreshToken": new_ref}
    except Exception:
        pass
    return None

def _build_headers(tokens: dict) -> dict:
    return {
        "Content-Type":  "application/json",
        "Cookie":        f"renterAccessToken={tokens['renterAccessToken']}; "
                         f"renterRefreshToken={tokens['renterRefreshToken']}",
        "Authorization": f"Bearer {tokens['renterAccessToken']}",
        "Origin":        APP_BASE,
        "Referer":       APP_BASE + "/",
        "User-Agent":    "Mozilla/5.0 (XCloudAutoRenew/Python)",
    }

async def _auto_refresh(tokens: dict) -> Optional[dict]:
    new_tokens = await refresh_token_flow(tokens)
    if new_tokens:
        tokens.update(new_tokens)
    return new_tokens

async def api_get(client: httpx.AsyncClient, endpoint: str, tokens: dict, _retry: bool = True) -> tuple[int, Optional[dict]]:
    try:
        r = await client.get(f"{API_BASE}{endpoint}", headers=_build_headers(tokens), timeout=15)
        if r.status_code == 401 and _retry:
            if await _auto_refresh(tokens):
                return await api_get(client, endpoint, tokens, _retry=False)
            return 401, None
        return r.status_code, r.json()
    except Exception:
        return 0, None

async def api_post(client: httpx.AsyncClient, endpoint: str, body: dict, tokens: dict, _retry: bool = True) -> tuple[int, Optional[dict]]:
    try:
        r = await client.post(f"{API_BASE}{endpoint}", headers=_build_headers(tokens), json=body, timeout=15)
        if r.status_code == 401 and _retry:
            if await _auto_refresh(tokens):
                return await api_post(client, endpoint, body, tokens, _retry=False)
            return 401, None
        return r.status_code, r.json()
    except Exception:
        return 0, None

# ─────────────────────────────────────────────
# LOGIC GIA HẠN
# ─────────────────────────────────────────────
def _hours_remaining(end_time_str: str) -> float:
    end = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
    return max((end - datetime.now(timezone.utc)).total_seconds() / 3600, 0.0)

async def fetch_devices(client: httpx.AsyncClient, tokens: dict) -> tuple[int, list]:
    page, all_devices = 1, []
    while True:
        status, data = await api_get(client, f"/renters/rental-sessions?page={page}&limit=50", tokens)
        if status == 401:
            return 401, []
        if not data:
            break
        batch = data.get("data", [])
        all_devices.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    return 200, all_devices

async def renew_devices(client: httpx.AsyncClient, tokens: dict, devices: list) -> list[dict]:
    groups: dict[int, list[str]] = {}
    for d in devices:
        hrs = _hours_remaining(d["endTime"])
        if hrs < RENEW_THRESHOLD_H:
            h = int(MAX_LIMIT_H - hrs)
            if h > 0:
                groups.setdefault(h, []).append(d["id"])

    results = []
    for hours, ids in groups.items():
        status, _ = await api_post(client, "/rentals/extend", {"listSessionId": ids, "rentalHours": hours}, tokens)
        results.append({"hours": hours, "ids": ids, "success": 200 <= status < 300, "status": status})
    return results

async def check_and_renew(tokens: dict, verbose: bool = True) -> tuple[list, list]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        status, devices = await fetch_devices(client, tokens)
        if status == 401:
            new = await do_login(EMAIL.strip(), PASSWORD.strip())
            if new:
                tokens.update(new)
                _, devices = await fetch_devices(client, tokens)
            else:
                return [], []
        if not devices:
            return [], []
        renew_results = await renew_devices(client, tokens, devices)
        _, devices    = await fetch_devices(client, tokens)
        return devices, renew_results

# ─────────────────────────────────────────────
# GIAO DIỆN CHUẨN MMO GOLIKE - MK-TOOL
# ─────────────────────────────────────────────
def _time_str(end_time_str: str) -> str:
    hrs = _hours_remaining(end_time_str)
    if hrs <= 0:
        return "00g 00p"
    h, m  = int(hrs), int((hrs % 1) * 60)
    return f"{h:02d}g {m:02d}p"

def _build_device_table(devices: list) -> Table:
    table = Table(box=box.SQUARE, border_style="blue", header_style="bold cyan", expand=True, show_lines=True)
    table.add_column("STT",                  justify="center", style="yellow", width=6)
    table.add_column("DANH SÁCH CÁC MÁY",    style="bold white", min_width=25)
    table.add_column("TRẠNG THÁI",           justify="center", width=20)

    if not devices:
        table.add_row("1.1", "Không tìm thấy máy XCloud hoạt động", "[bold red]● Off (00g 00p)[/]")
        return table

    for i, d in enumerate(devices, 1):
        hrs = _hours_remaining(d["endTime"])
        name = d.get("sessionName", "Máy chưa đặt tên")
        time_left = _time_str(d["endTime"])
        
        if hrs >= RENEW_THRESHOLD_H:
            status = f"[bold green]● On ({time_left})[/]"
        elif hrs > 0:
            status = f"[bold yellow]● Renew ({time_left})[/]"
        else:
            status = f"[bold red]● Off ({time_left})[/]"
            
        table.add_row(f"1.{i}", f"Tool Auto Renew Session: {name}", status)
    return table


def _build_h_tool_header(devices: list) -> str:
    total = len(devices)
    
    logo = "[bold red]███╗   ███╗██╗  ██╗     ████████╗ ██████╗  ██████╗ ██╗     [/bold red]\n" \
           "[bold orange3]████╗ ████║██║ ██╔╝     ╚══██╔══╝██╔═══██╗██╔═══██╗██║     [/bold orange3]\n" \
           "[bold dark_orange]██╔████╔██║█████╔╝  █████╗ ██║   ██║   ██║██║   ██║██║     [/bold dark_orange]\n" \
           "[bold yellow]██║╚██╔╝██║██╔═██╗  ╚════╝ ██║   ██║   ██║██║   ██║██║     [/bold yellow]\n" \
           "[bold gold1]██║ ╚═╝ ██║██║  ██╗        ██║   ╚██████╔╝╚██████╔╝███████╗[/bold gold1]\n" \
           "[bold light_goldenrod1]╚═╝     ╚═╝╚═╝  ╚═╝        ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝[/bold light_goldenrod1]\n"
                 
    meta_bar = "👤 Admin: [bold green]MK_ADMIN[/bold green]  │  🌐 IP: [bold cyan]127.0.0.1[/bold cyan]  │  💻 Client: [bold white]XCloud[/bold white]\n"
    
    border_top  = "[magenta]┌────────────────────────────────────────────────────────────────────────┐[/magenta]"
    info_str    = f" [bold white]ℹ️ THÔNG TIN THIẾT BỊ[/bold white]\n" \
                  f" 📅 Ngày chạy: [bold yellow]{datetime.now().strftime('%d/%m/%Y')}[/bold yellow]\n" \
                  f" 👥 Tài khoản: [bold white]{EMAIL}[/bold white]  │  📱 Tổng số máy: [bold cyan]{total}[/bold cyan] │ 🌐 Hệ thống: [bold green]Hoạt động[/bold green]"
    border_down = "[magenta]└────────────────────────────────────────────────────────────────────────┘[/magenta]"
               
    return f"{logo}{meta_bar}\n{border_top}\n{info_str}\n{border_down}"


# ─────────────────────────────────────────────
# ĐỒNG BỘ LAYOUT TOÀN MÀN HÌNH
# ─────────────────────────────────────────────
async def live_dashboard(tokens: dict) -> None:
    devices, _ = await check_and_renew(tokens, verbose=False)
    next_check_at = time.monotonic() + POLL_INTERVAL_S

    def render() -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=11),  
            Layout(name="table"),
            Layout(name="footer", size=3),
        )
        layout["header"].update(_build_h_tool_header(devices))
        layout["table"].update(_build_device_table(devices))
        
        secs = max(int(next_check_at - time.monotonic()), 0)
        layout["footer"].update(Panel(f"[bold yellow]»[/bold yellow] [white]Hệ thống tự động quét lại sau:[/white] [bold cyan]{secs} giây[/bold cyan] [dim]│ Bấm Ctrl+C để dừng tool[/dim]", border_style="blue", box=box.SQUARE))
        return layout

    with Live(render(), refresh_per_second=5, screen=True) as live:
        while True:
            live.update(render())
            await asyncio.sleep(0.2)
            if time.monotonic() >= next_check_at:
                devices, _ = await check_and_renew(tokens, verbose=False)
                next_check_at = time.monotonic() + POLL_INTERVAL_S


# ─────────────────────────────────────────────
# KHỞI CHẠY HỆ THỐNG
# ─────────────────────────────────────────────
async def main() -> None:
    load_or_create_account()

    console.print("[yellow]🔄 Đang kiểm tra cấu hình tài khoản hệ thống...[/yellow]")
    tokens = await do_login(EMAIL, PASSWORD)
    if not tokens:
        console.print("[red]❌ Đăng nhập thất bại! Kiểm tra lại tài khoản hoặc chạy lại tool chọn [2] để nhập mới.[/red]")
        time.sleep(3)
        sys.exit(1)
        
    console.print("[green]✓ Đăng nhập và đồng bộ dữ liệu thành công! Đang tải dữ liệu...[/green]")
    time.sleep(1)

    await live_dashboard(tokens)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        console.print("\n[bold green]Đã dừng chương trình thành công.[/bold green]")
        sys.exit(0)
