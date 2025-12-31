import os
import sys
import time
import json
import ctypes
import subprocess
import threading
import winreg
import socket
import msvcrt

MITMDUMP = "mitmdump"
PORT = 10086
MITM_CERT = os.path.expanduser(r"~\.mitmproxy\mitmproxy-ca-cert.cer")
ADDON = "mitm_addon.py"

OBS_HOST = "127.0.0.1"
OBS_PORT = 4455
OBS_PASSWORD = "" #如果有自己设置


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def relaunch_as_admin():
    params = " ".join([f'"{i}"' for i in sys.argv])
    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        None,
        1
    )
    sys.exit(0)


def set_system_proxy(enable: bool):
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        0,
        winreg.KEY_SET_VALUE
    )

    if enable:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(
            key,
            "ProxyServer",
            0,
            winreg.REG_SZ,
            f"http=127.0.0.1:{PORT};https=127.0.0.1:{PORT}"
        )
    else:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)


def mitm_cert_installed():
    try:
        out = subprocess.check_output(
            ["certutil", "-store", "Root"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="gbk"
        )
        return "mitmproxy" in out
    except:
        return False


def ensure_mitm_cert():
    if mitm_cert_installed():
        return

    subprocess.Popen(
        [MITMDUMP, "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    for _ in range(10):
        if os.path.exists(MITM_CERT):
            break
        time.sleep(1)

    if not os.path.exists(MITM_CERT):
        raise RuntimeError("mitmproxy 证书生成失败")

    subprocess.check_call(["certutil", "-addstore", "Root", MITM_CERT])


def obs_set_stream(server, key):
    from obswebsocket import obsws, requests
    ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
    ws.connect()
    ws.call(
        requests.SetStreamServiceSettings(
            streamServiceType="rtmp_custom",
            streamServiceSettings={
                "server": server,
                "key": key,
                "use_auth": False
            }
        )
    )
    ws.disconnect()


def run_mitmdump(result: dict):
    proc = subprocess.Popen(
        [
            MITMDUMP,
            "-p", str(PORT),
            "--listen-host", "127.0.0.1",
            "-q",
            "-s", ADDON,
            "--no-http2",
            "--set", "ssl_insecure=true",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    try:
        for line in proc.stdout:
            if line.startswith("RTMP_JSON="):
                result.update(json.loads(line[10:]))
                proc.terminate()
                break
    except KeyboardInterrupt:
        pass
    finally:
        proc.kill()


def check_port():
    try:
        s = socket.create_connection(("127.0.0.1", PORT), timeout=2)
        s.close()
        return True
    except:
        return False


def main():
    if not is_admin():
        relaunch_as_admin()
        return

    ensure_mitm_cert()
    set_system_proxy(True)

    print("请开播")

    result = {}
    t = threading.Thread(target=run_mitmdump, args=(result,), daemon=True)
    t.start()

    time.sleep(2)
    if not check_port():
        set_system_proxy(False)
        return

    try:
        t.join()
    except KeyboardInterrupt:
        pass

    set_system_proxy(False)

    if not result:
        return

    print("成功获取推流信息")
    print("推流地址:", result["server"])
    print("推流码  :", result["key"])
    print("请关闭 直播伴侣,记得勾选记住开播界面位置状态!")
    print("不要选关闭直播间!")
    print("不要选关闭直播间!")
    print("不要选关闭直播间!")
    obs_set_stream(result["server"], result["key"])
    print("推流地址与推流码已自动填写")
    print("按任意键退出...")
    msvcrt.getch()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
