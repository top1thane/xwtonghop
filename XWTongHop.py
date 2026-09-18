#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XWORLD TOOL - License protected launcher
- Tự nhớ install_id + KEY trên máy
- KEY được server kiểm tra, hạn 24 giờ
- Hết hạn -> API tạo KEY mới + trang lấy KEY + Link4M
- 1 cài đặt chỉ được tạo tối đa 1 KEY trong mỗi 24 giờ (rolling window)
- Không lưu Link4M token trong tool
"""

import os
import sys
import json
import time
import uuid
import webbrowser
import subprocess
import traceback
from datetime import datetime, timezone

# ==================== AUTO INSTALL ====================
def _install(pkgs):
    for mod, pip_name in pkgs.items():
        try:
            __import__(mod)
        except ImportError:
            print(f"[>] Cai {pip_name}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            except Exception as e:
                print(f"[X] Loi cai {pip_name}: {e}")
                raise SystemExit(1)

_install({"requests": "requests", "rich": "rich", "websocket": "websocket-client"})

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ==================== CONFIG ====================
LICENSE_API = "https://kiemtien.shopaccvt.site/license.php"
APP_NAME = "XWORLD TOOL TỔNG HỢP"
CLIENT_VERSION = "1.1.0"
LOCAL_DIR = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "XWorldTool")
LOCAL_STATE = os.path.join(LOCAL_DIR, "license.json")
HTTP_TIMEOUT = 15

# ==================== LICENSE CLIENT ====================
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def ensure_state_dir():
    os.makedirs(LOCAL_DIR, exist_ok=True)


def load_local_state():
    ensure_state_dir()
    try:
        with open(LOCAL_STATE, "r", encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}

    install_id = str(state.get("install_id") or "").strip()
    if not install_id:
        install_id = str(uuid.uuid4())
        state = {"install_id": install_id}
        save_local_state(state)

    state["install_id"] = install_id
    return state


def save_local_state(state):
    ensure_state_dir()
    tmp = LOCAL_STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, LOCAL_STATE)


def license_request(action, **payload):
    data = {
        "action": action,
        "app": APP_NAME,
        "version": CLIENT_VERSION,
        **payload,
    }
    try:
        r = requests.post(
            LICENSE_API,
            json=data,
            timeout=HTTP_TIMEOUT,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "XWorldTool/" + CLIENT_VERSION,
            },
        )
        try:
            body = r.json()
        except Exception:
            body = {}
        if not r.ok:
            return {"ok": False, "message": body.get("message") or f"HTTP {r.status_code}"}
        return body if isinstance(body, dict) else {"ok": False, "message": "API trả dữ liệu không hợp lệ."}
    except requests.RequestException as e:
        return {"ok": False, "message": f"Không kết nối được License API: {e}"}


def parse_iso(value):
    if not value:
        return None
    try:
        s = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def remaining_text(expires_at):
    dt = parse_iso(expires_at)
    if not dt:
        return "Không xác định"
    sec = int((dt - datetime.now(timezone.utc)).total_seconds())
    if sec <= 0:
        return "ĐÃ HẾT HẠN"
    days, sec = divmod(sec, 86400)
    hours, sec = divmod(sec, 3600)
    minutes, sec = divmod(sec, 60)
    if days:
        return f"{days} ngày {hours} giờ {minutes} phút"
    if hours:
        return f"{hours} giờ {minutes} phút {sec} giây"
    if minutes:
        return f"{minutes} phút {sec} giây"
    return f"{sec} giây"


def print_license_status(state, result, title="XWORLD LICENSE"):
    clear_screen()
    t = Table(show_header=False, box=None, padding=(0, 1))
    t.add_row("Thiết bị", str(state.get("install_id", ""))[:18] + "...")
    t.add_row("KEY", str(result.get("key") or state.get("key") or "-"))
    t.add_row("Tạo lúc", str(result.get("created_at") or state.get("created_at") or "-"))
    t.add_row("Hết hạn", str(result.get("expires_at") or state.get("expires_at") or "-"))
    t.add_row("Còn lại", remaining_text(result.get("expires_at") or state.get("expires_at")))
    console.print(Panel(t, title=f"[bold cyan]{title}[/bold cyan]", border_style="magenta"))


def activate_key(state, key):
    key = key.strip().upper()
    if not key:
        return {"ok": False, "message": "KEY trống."}
    return license_request("validate", key=key, install_id=state["install_id"])


def create_new_key(state):
    return license_request("create", install_id=state["install_id"])


def license_gate():
    state = load_local_state()
    saved_key = str(state.get("key") or "").strip()

    # 1) Có KEY cũ -> tự check, còn hạn thì vào thẳng.
    if saved_key:
        result = activate_key(state, saved_key)
        if result.get("ok") and result.get("valid"):
            state.update({
                "key": result.get("key", saved_key),
                "created_at": result.get("created_at"),
                "expires_at": result.get("expires_at"),
            })
            save_local_state(state)
            print_license_status(state, result, "XWORLD TOOL - LICENSE OK")
            time.sleep(0.8)
            return

    # 2) Không có KEY hoặc KEY hết hạn -> yêu cầu server tạo link lấy KEY mới.
    clear_screen()
    console.print(Panel.fit(
        "[bold cyan]XWORLD TOOL TỔNG HỢP[/bold cyan]\n"
        "[white]KEY có hạn 24 giờ · kiểm tra online · tự nhớ trên thiết bị[/white]",
        border_style="magenta",
    ))
    console.print("\n[yellow][!] Chưa có KEY hợp lệ trên thiết bị này.[/yellow]")
    console.print("[cyan][>] Đang yêu cầu server tạo KEY mới...[/cyan]\n")

    created = create_new_key(state)
    if not created.get("ok"):
        console.print(f"[red][X] {created.get('message', 'Không thể tạo KEY.')}[/red]")
        input("\nEnter để thoát...")
        raise SystemExit(1)

    key_url = created.get("key_url") or created.get("url")
    short_url = created.get("short_url") or created.get("shorten_url")
    if not short_url:
        console.print("[red][X] Server không trả về LINK RÚT GỌN LINK4M.[/red]")
        console.print("[yellow]Không hiển thị link gốc để tránh người dùng bỏ qua Link4M.[/yellow]")
        input("\nEnter để thoát...")
        raise SystemExit(1)

    console.print(Panel(
        f"[bold green]LINK4M - LINK LẤY KEY[/bold green]\n\n"
        f"[bold cyan]{short_url}[/bold cyan]\n\n"
        f"[dim]Mở link rút gọn để nhận KEY. Link trang đích không hiển thị trong tool.[/dim]",
        border_style="green",
    ))
    console.print("\n[cyan][1][/cyan] Mở link bằng trình duyệt")
    console.print("[cyan][2][/cyan] Tự copy link vào clipboard nếu có")
    console.print("[yellow][0][/yellow] Bỏ qua")
    choice = console.input("\n[bold cyan]>> Chọn: [/bold cyan]").strip()
    if choice == "1":
        try:
            webbrowser.open(short_url)
        except Exception:
            pass
    elif choice == "2":
        copied = False
        try:
            import tkinter as tk
            root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(short_url); root.update(); root.destroy()
            copied = True
        except Exception:
            copied = False
        console.print("[green]Đã copy link.[/green]" if copied else "[yellow]Không copy được tự động.[/yellow]")

    while True:
        key = console.input("\n[bold cyan]Nhập KEY nhận được: [/bold cyan]").strip().upper()
        if not key:
            console.print("[red][X] KEY không được để trống.[/red]")
            continue
        result = activate_key(state, key)
        if result.get("ok") and result.get("valid"):
            state.update({
                "key": result.get("key", key),
                "created_at": result.get("created_at"),
                "expires_at": result.get("expires_at"),
            })
            save_local_state(state)
            console.print("\n[bold green][OK] KEY hợp lệ. Đã lưu cho thiết bị này.[/bold green]")
            console.print(f"[cyan]Còn lại: {remaining_text(state.get('expires_at'))}[/cyan]")
            time.sleep(1)
            return
        console.print(f"[red][X] KEY không hợp lệ: {result.get('message', 'Không xác định')}[/red]")

# ==================== TOOL UI ====================
def main_menu():
    while True:
        clear_screen()
        console.print(Panel.fit(
            "[bold cyan]MULTI-GAME AUTO BET TOOL - ALL IN ONE[/bold cyan]\n"
            "[dim]XWORLD TOOL TỔNG HỢP[/dim]",
            border_style="magenta",
        ))
        console.print("\n[magenta][1][/magenta] ESCAPE MASTER AUTO BET")
        console.print("[magenta][2][/magenta] SPRINTRUN AUTO BET")
        console.print("[magenta][3][/magenta] WINHASH AUTO BET")
        console.print("[yellow][4][/yellow] Xem trạng thái KEY")
        console.print("[red][0][/red] Thoát\n")
        c = console.input("[bold cyan]>> Chọn tool (0-4): [/bold cyan]").strip()
        if c == "1":
            run_escape_master()
        elif c == "2":
            run_sprintrun()
        elif c == "3":
            run_winhash()
        elif c == "4":
            state = load_local_state()
            res = activate_key(state, str(state.get("key") or ""))
            if res.get("ok") and res.get("valid"):
                print_license_status(state, res, "TRẠNG THÁI KEY")
            else:
                console.print("[red]KEY hiện tại không còn hợp lệ.[/red]")
            input("\nEnter...")
        elif c == "0":
            raise SystemExit(0)
        else:
            console.print("[red][X] Sai lựa chọn.[/red]")
            time.sleep(0.8)

# ============================================================
# TOOL 1: ESCAPE MASTER
# ============================================================
def run_escape_master():
    import random
    import json
    import websocket
    from threading import Lock, Thread, Event
    from datetime import datetime

    ASSET_TYPE = "BUILD"
    WS_URL = "wss://api.escapemaster.net/escape_master/ws"
    WATCHDOG_TIMEOUT = 360

    class C:
        RESET="\033[0m"; RED="\033[91m"; GREEN="\033[92m"; YELLOW="\033[93m"
        BLUE="\033[94m"; MAGENTA="\033[95m"; CYAN="\033[96m"; WHITE="\033[97m"
        BOLD="\033[1m"; NEON="\033[38;5;51m"; PURPLE="\033[38;5;141m"
        ORANGE="\033[38;5;208m"; DIM="\033[2m"

    cfg = {"BASE_BET": 1.0, "LOSS_THRESHOLD": 2, "SKIP_ROUNDS": 3, "MULTIPLIER": 2.0}
    disp = {"room":0,"countdown":0,"show_timer":False,"random_active":False,
            "log_msg":None,"log_color":C.RESET,"watchdog_remaining":WATCHDOG_TIMEOUT,
            "show_watchdog":False,"session_state":"IDLE"}
    dlock = Lock(); stop_ev = Event(); wd_lock = Lock()
    rt = {"wd_last":time.time(),"ws":None,"betting_id":None,"curr_id":None,
          "has_bet":False,"cd_active":False,"need_restart":False,"uid":None,"skey":None}
    session = requests.Session()
    session.headers.update({"User-Agent":"Mozilla/5.0 (Linux; Android 6.0)","Origin":"https://escapemaster.net",
        "Accept":"application/json","Accept-Language":"vi-VN,vi;q=0.9","Referer":"https://escapemaster.net/"})

    def H():
        return {"Content-Type":"application/json","user-id":str(rt["uid"]),"user-login":"login_v2",
                "user-secret-key":rt["skey"],"Accept":"application/json","xb-language":"vi-VN"}
    def api(m,u,**kw):
        try:
            r=session.request(m,u,headers=H(),timeout=15,**kw)
            if r.status_code==200: return r.json()
        except: pass
        return {}
    def LOG(msg,col=C.RESET):
        with dlock: disp["log_msg"]=f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"; disp["log_color"]=col
    def SETS(s):
        with dlock: disp["session_state"]=s
    def WDRESET():
        with wd_lock: rt["wd_last"]=time.time()
        with dlock: disp["watchdog_remaining"]=WATCHDOG_TIMEOUT; disp["show_watchdog"]=True
    def WDLEFT():
        with wd_lock: return int(max(0,WATCHDOG_TIMEOUT-(time.time()-rt["wd_last"])))
    def bal_wallet():
        try:
            r=requests.post("https://wallet.3games.io/api/wallet/total_asset_in_usdt",json={"user_id":rt["uid"],"filter":{"top_n":{"n":10}},"refresh":0},
                headers={"accept":"*/*","content-type":"application/json","country-code":"vn","nonce":"dohQi","origin":"https://xworld.info","platform":"h5",
                "referer":"https://xworld.info/","user-agent":"Mozilla/5.0","user-id":str(rt["uid"]),"user-secret-key":rt["skey"],"xb-language":"vi-VN"},timeout=10)
            if r.status_code==200:
                d=r.json(); res=d.get("data")
                if d.get("code")==0:
                    if isinstance(res,list):
                        for it in res:
                            if isinstance(it,dict) and it.get("symbol")=="BUILD": return float(it.get("balance",0))
                    elif isinstance(res,dict):
                        for it in res.get("items",[]):
                            if isinstance(it,dict) and it.get("symbol")=="BUILD": return float(it.get("balance",0))
        except: pass
        return 0.0
    def bal_old():
        d=api("POST","https://api.escapemaster.net/escape_game/get_user_asset",json={"asset_type":ASSET_TYPE,"user_id":rt["uid"]})
        return float(d.get("data",{}).get("balance",0)) if d and d.get("code")==0 else 0.0
    def BAL():
        b=bal_wallet(); return b if b>0 else bal_old()
    def ENTER(rid):
        d = api("POST", "https://api.escapemaster.net/escape_game/enter_room",
                json={"asset_type": ASSET_TYPE, "user_id": rt["uid"], "room_id": rid})
        if not d or d.get("code") != 0:
            LOG(f"   [DEBUG] enter_room fail: {d}", C.RED)
            return False
        return True
    def BET(rid, amt):
        d = api("POST", "https://api.escapemaster.net/escape_game/bet",
                json={"asset_type": ASSET_TYPE, "user_id": rt["uid"],
                      "room_id": rid, "bet_amount": amt})
        if not d or d.get("code") != 0:
            LOG(f"   [DEBUG] bet fail: {d}", C.RED)
            return False
        return True
    def JOINED(p=1):
        try:
            r=session.get("https://api.escapemaster.net/escape_game/my_joined",params={"asset":ASSET_TYPE,"page":p,"page_size":10},headers=H(),timeout=10)
            d=r.json(); return d.get("data",{}) if d.get("code")==0 else {}
        except: return {}
    def wd_loop():
        while True:
            time.sleep(2)
            if rt["need_restart"]: continue
            rem=WDLEFT()
            with dlock: disp["watchdog_remaining"]=rem; disp["show_watchdog"]=True
            if rem<=0:
                LOG(f"[!] WATCHDOG {WATCHDOG_TIMEOUT}s -> Restart WS!",C.RED); RESTART(); time.sleep(5)
    def disp_loop():
        last=""; fd=1.0/60
        while True:
            with dlock:
                lm=disp.get("log_msg"); lc=disp.get("log_color",C.RESET); rm=disp.get("room",0); cd=disp.get("countdown",0)
                st=disp.get("show_timer",False); ra=disp.get("random_active",False); wr=disp.get("watchdog_remaining",WATCHDOG_TIMEOUT)
                sw=disp.get("show_watchdog",False); ss=disp.get("session_state","IDLE")
                if lm: disp["log_msg"]=None
            if lm: sys.stdout.write(f"\r\033[K{lc}{lm}{C.RESET}\n"); sys.stdout.flush(); last=""
            if ra or st or sw:
                tp=""; rp=f"{C.MAGENTA}{C.BOLD}Phong: {rm}{C.RESET}" if (ra and rm>0) else ""
                if st and cd>0:
                    bl=25; fl=int(bl*cd/60); bar="#"*fl+"-"*(bl-fl); cc=C.GREEN if cd>15 else (C.YELLOW if cd>7 else C.RED); tp=f"{cc}[{bar}] {cd:2d}s{C.RESET}  "
                sb=f"  {C.NEON}* BETTING{C.RESET}" if ss=="BETTING" else (f"  {C.ORANGE}* WAITING{C.RESET}" if ss=="WAITING" else (f"  {C.YELLOW}* SKIPPING{C.RESET}" if ss=="SKIPPING" else ""))
                wp=f"  {C.GREEN if wr>240 else C.CYAN if wr>120 else C.YELLOW if wr>60 else C.RED}WD: {wr}s{C.RESET}" if sw and wr>0 else ""
                nr=f"\r\033[K  {tp}{rp}{sb}{wp}     "
                if nr!=last: sys.stdout.write(nr); sys.stdout.flush(); last=nr
            time.sleep(fd)
    def RAND_START(bet_rid,cd):
        stop_ev.clear()
        with dlock: disp["random_active"]=True; disp["room"]=0
        SETS("BETTING"); LOG(f"[*] RANDOM PHONG ({cd}s)...",C.MAGENTA)
        def loop():
            rooms=[1,2,3,4,5,6,7,8]
            while not stop_ev.is_set():
                rid=random.choice(rooms)
                with dlock: disp["room"]=rid
                def call():
                    try: session.post("https://api.escapemaster.net/escape_game/enter_room",json={"asset_type":ASSET_TYPE,"user_id":rt["uid"],"room_id":rid},headers=H(),timeout=2)
                    except: pass
                Thread(target=call,daemon=True).start(); time.sleep(0.2)
        Thread(target=loop,daemon=True).start()
        Thread(target=lambda: (time.sleep(cd+1),RAND_STOP()),daemon=True).start()
    def RAND_STOP():
        stop_ev.set()
        with dlock: disp["random_active"]=False; disp["room"]=0
    def STOP_TIMER():
        with dlock: disp["show_timer"]=False; disp["countdown"]=0
    def RESTART():
        rt["cd_active"]=False; rt["need_restart"]=True; RAND_STOP(); STOP_TIMER(); SETS("IDLE"); LOG("[~] Restart WebSocket...",C.YELLOW)
        if rt["ws"]:
            try: rt["ws"].close()
            except: pass

    class Strat:
        def __init__(self): self.cb=cfg["BASE_BET"]; self.cl=0; self.tp=0.0; self.tb=0; self.w=0; self.l=0; self.sk=0; self.lk=Lock()
        def proc(self,iid,killed,award,bet,kr,mr):
            RAND_STOP(); STOP_TIMER()
            with self.lk:
                prof=award-bet; self.tb+=1
                print(f"\n{C.PURPLE}{'='*60}{C.RESET}\n{C.BOLD}  [KQ] PHIEN #{iid}{C.RESET}\n  Cuoc: {bet:.6f} | Thuong: {award:.6f}")
                if not killed: self.w+=1; self.cl=0; self.cb=cfg["BASE_BET"]; self.sk=0; print(f"  {C.GREEN}[WIN] +{prof:.6f}{C.RESET}")
                else:
                    self.l+=1; self.cl+=1; print(f"  {C.RED}[LOSE] {prof:+.6f}{C.RESET}")
                    if self.cl>=cfg["LOSS_THRESHOLD"]: self.sk=cfg["SKIP_ROUNDS"]; print(f"  {C.YELLOW}[!] Nghi {cfg['SKIP_ROUNDS']} tran{C.RESET}")
                    else: self.cb*=cfg["MULTIPLIER"]; print(f"  {C.YELLOW}[x] Nhan -> {self.cb:.2f}{C.RESET}")
                self.tp+=prof; wr=self.w/self.tb*100 if self.tb else 0; print(f"  [STAT] {self.tb} | W:{self.w} L:{self.l} | WR:{wr:.1f}% | Loi:{self.tp:+.4f}")
            rt.update({"has_bet":False,"betting_id":None,"curr_id":None,"cd_active":False}); SETS("IDLE"); RESTART()
        def skip(self):
            with self.lk:
                if self.sk>0: self.sk-=1; return True
                return False
    strat=Strat()
    def cd_loop():
        while True:
            if rt["need_restart"]: time.sleep(0.1); continue
            if rt["cd_active"]:
                with dlock:
                    cd=disp.get("countdown",0)
                    if cd>0: disp["countdown"]=cd-1; disp["show_timer"]=True
                time.sleep(1)
            else: time.sleep(0.1)
    def DOBET(iid,cd):
        if rt["need_restart"] or (rt["curr_id"] is not None and rt["curr_id"]!=iid) or rt["betting_id"]==iid or rt["has_bet"]: return
        rt["curr_id"]=iid; rt["betting_id"]=iid; rt["has_bet"]=False; rt["cd_active"]=True
        with dlock: disp["countdown"]=cd
        LOG(f"[>] PHIEN #{iid} | {cd}s",C.CYAN)
        if not strat.skip():
            room=random.randint(1,8); amt=strat.cb
            LOG(f"   [.] Cuoc {amt:.6f} -> P{room}",C.WHITE); SETS("WAITING")
            enter_ok = ENTER(room)
            bet_ok = BET(room, amt) if enter_ok else False
            if enter_ok and bet_ok:
                rt["has_bet"]=True; SETS("BETTING"); LOG(f"   [OK] P{room} | {amt:.6f}",C.GREEN); WDRESET(); RAND_START(room,cd)
            else:
                LOG(f"   [X] Cuoc/vao phong fail! enter={enter_ok} bet={bet_ok}",C.RED)
                rt.update({"betting_id":None,"has_bet":False,"curr_id":None}); RESTART()
        else:
            SETS("SKIPPING"); LOG("   [~] Nghi",C.YELLOW); rt["curr_id"]=None; RESTART()
    def on_msg(ws,msg):
        if rt["need_restart"]: return
        try:
            d=json.loads(msg); mt=d.get("msg_type","")
            if mt=="notify_count_down":
                iid=d.get("issue_id"); cd=d.get("count_down",0); rt["cd_active"]=True
                with dlock: disp["countdown"]=cd
                if rt["curr_id"] is None or rt["curr_id"]!=iid: DOBET(iid,cd)
            elif mt=="notify_result":
                rt["cd_active"]=False; STOP_TIMER(); RAND_STOP(); iid=d.get("issue_id")
                if rt["has_bet"] and iid==rt["betting_id"]:
                    aw=float(d.get("award_amount",0)); bt=float(d.get("bet_amount",0)); strat.proc(iid,not(aw>bt),aw,bt,d.get("killed_room","?"),d.get("room_id","?"))
            elif mt=="notify_heartbeat":
                try: ws.send(json.dumps({"msg_type":"heartbeat_ack"}))
                except: pass
        except Exception as e: LOG(f"[!] on_msg: {e}",C.RED)
    def on_err(ws,e): RAND_STOP(); STOP_TIMER(); SETS("IDLE"); LOG(f"[X] WS Err: {e}",C.RED)
    def on_close(ws,_,__):
        rt["need_restart"]=False; RAND_STOP(); STOP_TIMER(); SETS("IDLE"); LOG("[~] WS dong. Reconnect 2s...",C.YELLOW); time.sleep(2); run_ws()
    def on_open(ws):
        rt.update({"betting_id":None,"has_bet":False,"curr_id":None,"cd_active":False,"need_restart":False}); WDRESET(); RAND_STOP(); STOP_TIMER(); SETS("IDLE"); LOG("[OK] WS CONNECTED!",C.GREEN)
        ws.send(json.dumps({"msg_type":"handle_enter_game","asset_type":ASSET_TYPE,"user_id":rt["uid"],"user_secret_key":rt["skey"]}))
        LOG("[>] enter game",C.CYAN)
    def run_ws():
        rt["ws"]=websocket.WebSocketApp(WS_URL,header={"Origin":"https://escapemaster.net","User-Agent":"Mozilla/5.0"},on_open=on_open,on_message=on_msg,on_error=on_err,on_close=on_close)
        rt["ws"].run_forever(ping_interval=15,ping_timeout=10)

    clear_screen(); console.print(Panel.fit("[bold cyan]ESCAPE MASTER AUTO BET[/bold cyan]",border_style="magenta"))
    uid=console.input("USER_ID: ").strip()
    sk=console.input("SECRET_KEY: ").strip()
    if not uid.isdigit() or not sk: console.print("[red]Thông tin đăng nhập không hợp lệ.[/red]"); input("Enter..."); return
    rt["uid"]=int(uid); rt["skey"]=sk
    try: cfg["BASE_BET"]=float(console.input(f"Base Bet ({cfg['BASE_BET']}): ").strip() or cfg["BASE_BET"]); cfg["LOSS_THRESHOLD"]=int(console.input(f"Thua liên tiếp ({cfg['LOSS_THRESHOLD']}): ").strip() or cfg["LOSS_THRESHOLD"]); cfg["SKIP_ROUNDS"]=int(console.input(f"Nghỉ ({cfg['SKIP_ROUNDS']}): ").strip() or cfg["SKIP_ROUNDS"]); cfg["MULTIPLIER"]=float(console.input(f"Nhân (x{cfg['MULTIPLIER']}): ").strip() or cfg["MULTIPLIER"])
    except ValueError: console.print("[red]Cấu hình không hợp lệ.[/red]"); return
    strat.cb = cfg["BASE_BET"]
    Thread(target=disp_loop,daemon=True).start(); Thread(target=cd_loop,daemon=True).start(); Thread(target=wd_loop,daemon=True).start(); run_ws()

# ============================================================
# TOOL 2: SPRINTRUN
# ============================================================
def run_sprintrun():
    import random
    from decimal import Decimal, ROUND_DOWN
    from rich.progress import track
    BASE_API="https://api.sprintrun.win"
    clear_screen(); console.print(Panel.fit("[bold cyan]SPRINTRUN AUTO BET - RANDOM 3 VDV[/bold cyan]",border_style="magenta"))
    uid=console.input("User ID: ").strip(); sk=console.input("Secret Key: ").strip(); base=console.input("Tổng build (1): ").strip() or "1"; ll=int(console.input("Thua mấy trận nghỉ (3): ").strip() or 3); rr=int(console.input("Nghỉ bao nhiêu phiên (1): ").strip() or 1); mult=Decimal(console.input("Hệ số nhân (2.5): ").strip() or "2.5"); asset=console.input("Asset (BUILD): ").strip() or "BUILD"
    headers={"accept":"*/*","content-type":"application/json","origin":"https://sprintrun.win","referer":"https://sprintrun.win/","user-agent":"Mozilla/5.0","user-id":uid,"user-login":"login_v2","user-secret-key":sk}
    def home():
        try:
            r=requests.get(f"{BASE_API}/sprint/home?asset={asset}",headers=headers,timeout=10); return r.status_code,r.json()
        except: return None,None
    def bet(p):
        try: r=requests.post(f"{BASE_API}/sprint/bet",json=p,headers=headers,timeout=10); return r.status_code,r.json()
        except: return None,None
    def result(iid):
        try: r=requests.get(f"{BASE_API}/sprint/issue_result?issue={iid}&asset={asset}",headers=headers,timeout=10); return r.status_code,r.json()
        except: return None,None
    tw=tl=sl=0; cb=Decimal(base); bb=cb
    while True:
        code,data=home()
        if code!=200: console.print(f"[red]HOME lỗi {code}[/red]"); time.sleep(3); continue
        d=data.get("data",{}); iid=d.get("issue_id"); exp=int(d.get("expire_seconds",50)); ath=d.get("athlete_list",[])
        if not iid or len(ath)<3: time.sleep(2); continue
        if sl>=ll:
            console.print(f"[yellow]Nghỉ {rr} phiên...[/yellow]")
            for _ in range(rr):
                _,h=home(); e=int((h or {}).get("data",{}).get("expire_seconds",30)); time.sleep(max(5,e))
            sl=0; continue
        chosen=random.sample(ath,3); each=(cb/Decimal(3)).quantize(Decimal("0.000001"),rounding=ROUND_DOWN)
        console.print(f"\n[cyan]PHIÊN #{iid}[/cyan] | VDV: {', '.join(str(x.get('name')) for x in chosen)} | Mỗi: {each} | Tổng: {each*3}")
        for a in chosen:
            bet({"issue_id":iid,"bet_group":"winner","asset_type":asset,"athlete_id":a["id"],"bet_amount":float(each)}); time.sleep(.2)
        for _ in track(range(exp),description="Đợi kết quả..."): time.sleep(1)
        win=None
        for _ in range(30):
            code,res=result(iid)
            if code==200:
                rank=(res or {}).get("data",{}).get("athlete_rank",[])
                if rank: win=rank[0]; break
            time.sleep(1)
        total=each*3
        if win in [a["id"] for a in chosen]:
            prof=each*5-total; tw+=1; sl=0; cb=bb; console.print(f"[green]WIN +{prof}[/green]")
        else:
            tl+=1; sl+=1; cb=(cb*mult).quantize(Decimal("0.000001"),rounding=ROUND_DOWN); console.print(f"[red]LOSE -{total} | Nhân -> {cb}[/red]")
        time.sleep(1)

# ============================================================
# TOOL 3: WINHASH
# ============================================================
def run_winhash():
    from decimal import Decimal
    clear_screen(); console.print(Panel.fit("[bold cyan]WINHASH AUTO BET - SMALL/BIG[/bold cyan]",border_style="magenta"))
    user_id=console.input("user-id: ").strip(); user_login=console.input("user-login (Không Có Nhập ENTER Nhé): ").strip(); user_key=console.input("user-secret-key: ").strip(); asset=console.input("Asset (BUILD): ").strip() or "BUILD"; total=float(console.input("Tổng build (10): ").strip() or 10); mult=float(console.input("Hệ số nhân (2): ").strip() or 2); lose_count,rest_stop=map(int,console.input("Thua X -> nghỉ Y (3 1): ").strip().split() or [3,1])
    H={"accept":"*/*","accept-language":"vi-VN,vi;q=0.9","content-type":"application/json","country-code":"vn","origin":"https://winhash.io","referer":"https://winhash.io/","user-agent":"Mozilla/5.0","user-id":user_id,"user-login":"login_v2","user-secret-key":user_key,"xb-language":"vi-VN"}
    BASE="https://api.winhash.net/lucky_game/v2"; cur=total/2; losses=0; rest=0
    def current():
        try:
            r = requests.get(
                f"https://api.winhash.net/lucky_game/home?game_id=1&asset={asset}",
                headers=H,
                timeout=10
            )
            d=r.json().get("data",{}); items=d.get("bet_section",{}).get("sum_in_range",{}).get("items",[]); small=next((x for x in items if x.get("props",{}).get("value")==[3,9]),None); big=next((x for x in items if x.get("props",{}).get("value")==[12,18]),None); return d.get("issue_id"),small,big,int(d.get("expire_seconds",50))
        except: return None,None,None,50
    
    def order(iid, s, b):
        try:
            r = requests.post(
                f"{BASE}/create_order",
                headers=H,
                json={
                    "game_id": 1,
                    "issue_id": iid,
                    "items": [
                        {
                            "id": s["id"],
                            "amount": str(cur),
                            "asset": asset
                        },
                        {
                            "id": b["id"],
                            "amount": str(cur),
                            "asset": asset
                        }
                    ]
                },
                timeout=10
            )

            try:
                data = r.json()
            except Exception:
                data = {"raw": r.text}

            return r.status_code, data

        except Exception as e:
            return None, {"error": str(e)}

    def getres(iid):
        try:
            r=requests.get("https://api.winhash.net/lucky_game/my_orders",params={"game_id":1,"page":1,"page_size":15,"asset":asset,"game":"hash_lotto"},headers=H,timeout=10); orders=r.json().get("data",{}).get("orders",[])
            for o in orders:
                if str(o.get("issue_id"))==str(iid):
                    st=o.get("state",{})
                    if st.get("state")!="finish": return None
                    raw=st.get("lucky_data"); lucky=json.loads(raw) if isinstance(raw,str) else raw
                    return {"lucky":lucky,"is_hit":o.get("is_hit",False),"hit_amount":o.get("hit_amount",0),"bet_total":o.get("bet_total",0)}
        except: pass
        return None
    while True:
        if rest>0: console.print(f"[yellow]Nghỉ {rest} phiên[/yellow]"); rest-=1; time.sleep(15); continue
        iid,sm,bg,exp=current()
        if not iid or not sm or not bg: time.sleep(10); continue
        console.print(f"[cyan]PHIÊN #{iid}[/cyan] | Small {sm['id']} | Big {bg['id']} | Mỗi {cur}")
        status, res = order(iid, sm, bg)

        if status != 200:
            console.print(
                f"[red][X] GỬI CƯỢC THẤT BẠI | HTTP {status}[/red]"
            )
            console.print(f"[dim]{res}[/dim]")
            time.sleep(10)
            continue

        # Kiểm tra API báo thành công
        success = (
            res.get("success") is True
            or res.get("ok") is True
            or res.get("code") in (0, "0")
        )

        if not success:
            console.print(
                "[red][X] API không xác nhận cược thành công[/red]"
            )
            console.print(f"[dim]Response: {res}[/dim]")
            time.sleep(10)
            continue

        console.print(
            f"[bold green]✓ GỬI CƯỢC THÀNH CÔNG[/bold green] "
            f"| Phiên #{iid} "
            f"| Small: {cur} "
            f"| Big: {cur} "
            f"| Tổng: {cur * 2:.6f}"
        )

 
        time.sleep(exp)
        result=None
        for _ in range(6):
            result=getres(iid)
            if result: break
            time.sleep(5)
        if not result: console.print("[yellow]Chưa có KQ, bỏ phiên[/yellow]"); continue
        lucky=result["lucky"]; hit=result["is_hit"]; bt=float(result["bet_total"] or cur*2); ha=float(result["hit_amount"] or 0); console.print(f"KQ {lucky} | Tổng {sum(lucky)} | {'THẮNG' if hit else 'THUA'} | Cược {bt} | Nhận {ha}")
        if hit and ha>bt: cur=total/2; losses=0; console.print("[green]Reset cược[/green]")
        else:
            cur*=mult; losses+=1; console.print(f"[yellow]Nhân -> {cur}[/yellow]")
            if losses>=lose_count: rest=rest_stop; losses=0
        time.sleep(10)


if __name__ == "__main__":
    try:
        license_gate()
        main_menu()
    except KeyboardInterrupt:
        print("\n[!] Đã thoát!")
    except Exception:
        traceback.print_exc()
        input("\nEnter để thoát...")