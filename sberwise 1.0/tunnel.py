"""
Автоматический HTTPS-туннель через встроенный OpenSSH (localhost.run).
Предоставляет реальный публичный HTTPS-домен для работы Telegram Mini App.
Включает автоматический сторож (watchdog) для переподключения при разрывах связи.
"""

import os
import subprocess
import threading
import time
import re
import logging

logger = logging.getLogger(__name__)

_tunnel_proc = None
_public_https_url = None
_target_port = 8899
_stopping = False
_on_url_change_callback = None


def set_on_url_change(callback):
    global _on_url_change_callback
    _on_url_change_callback = callback


def _drain_and_monitor(proc):
    """Непрерывное чтение вывода SSH и мониторинг состояния процесса."""
    global _public_https_url
    try:
        for line in iter(proc.stdout.readline, ''):
            if not line or _stopping:
                break
            if "lhr.life" in line:
                m = re.search(r"https://[a-zA-Z0-9.-]+\.lhr\.life", line)
                if m and m.group(0) != _public_https_url:
                    _public_https_url = m.group(0)
                    logger.info(f"🔄 HTTPS туннель обновлён: {_public_https_url}")
                    if _on_url_change_callback:
                        try:
                            _on_url_change_callback(_public_https_url)
                        except Exception:
                            pass
    except Exception:
        pass


def _connect_ssh(target_port: int) -> str:
    global _tunnel_proc, _public_https_url
    try:
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            "-R", f"80:127.0.0.1:{target_port}",
            "nokey@localhost.run"
        ]

        logger.info(f"🌐 Подключаю SSH-туннель к localhost.run (порт {target_port})...")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _tunnel_proc = proc

        start_time = time.time()
        while time.time() - start_time < 25:
            line = proc.stdout.readline()
            if not line:
                break
            if "lhr.life" in line:
                m = re.search(r"https://[a-zA-Z0-9.-]+\.lhr\.life", line)
                if m:
                    _public_https_url = m.group(0)
                    logger.info(f"✅ Публичный HTTPS туннель активен: {_public_https_url}")
                    try:
                        with open("current_tunnel_url.txt", "w", encoding="utf-8") as url_f:
                            url_f.write(_public_https_url)
                    except Exception:
                        pass
                    if _on_url_change_callback:
                        try:
                            _on_url_change_callback(_public_https_url)
                        except Exception as cb_err:
                            logger.warning(f"Ошибка в callback обновления URL: {cb_err}")
                    monitor_thread = threading.Thread(target=_drain_and_monitor, args=(proc,), daemon=True)
                    monitor_thread.start()
                    return _public_https_url

        logger.warning("⚠️ Не удалось получить HTTPS URL от localhost.run за 25 сек")
        return ""
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при запуске туннеля: {e}")
        return ""


def _watchdog_loop():
    """Сторожевой поток: если ssh отключился или туннель перестал отвечать (503), автоматически переподключает."""
    global _tunnel_proc, _stopping, _public_https_url
    fail_count = 0
    while not _stopping:
        time.sleep(10)
        if _stopping:
            break

        # Проверка живости процесса ssh
        if _tunnel_proc is None or _tunnel_proc.poll() is not None:
            logger.info("⚠️ Туннель разорван (процесс завершился), запускаю автоматическое переподключение...")
            _connect_ssh(_target_port)
            fail_count = 0
            continue

        # Активная проверка доступности через HTTP GET
        if _public_https_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"{_public_https_url}/api/health",
                    headers={"User-Agent": "Tunnel-Watchdog/1.0"}
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    if resp.status == 200:
                        fail_count = 0
                    else:
                        fail_count += 1
            except Exception:
                fail_count += 1

            if fail_count >= 2:
                logger.warning("⚠️ Публичный туннель не отвечает 2 проверки подряд, перезапускаю SSH...")
                fail_count = 0
                if _tunnel_proc:
                    try:
                        _tunnel_proc.terminate()
                    except Exception:
                        pass


def start_tunnel(local_port: int = 8080, port: int = None) -> str:
    """Запустить SSH-туннель к localhost.run с авто-переподключением."""
    global _target_port, _stopping
    _target_port = port or local_port
    _stopping = False

    url = _connect_ssh(_target_port)

    watchdog = threading.Thread(target=_watchdog_loop, daemon=True)
    watchdog.start()

    return url


def stop_tunnel():
    """Остановить процесс туннеля при выходе."""
    global _tunnel_proc, _stopping
    _stopping = True
    if _tunnel_proc:
        try:
            _tunnel_proc.terminate()
            logger.info("Туннель остановлен")
        except Exception:
            pass
        _tunnel_proc = None


def get_public_url() -> str:
    if _public_https_url:
        return _public_https_url
    try:
        if os.path.exists("current_tunnel_url.txt"):
            with open("current_tunnel_url.txt", "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val.startswith("https://"):
                    return val
    except Exception:
        pass
    return ""
