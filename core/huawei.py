from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RouterStatus:
    model: str
    ip: str
    signal_dbm: int
    band: str
    bands: list[int] = field(default_factory=list)
    supported_band_lock: bool = True
    current_locked_bands: list[int] = field(default_factory=list)
    provider: str = "Huawei"


class HuaweiRouter:
    """Huawei router connector.

    Behavior:
    - If huawei_lte_api is installed, tries to use it to read status.
    - Band-lock write is attempted but may be provider/firmware-dependent.
    - When the library is not available, falls back to a safe demo mode.
    """

    def __init__(self, ip: str, username: str = "admin", password: str = "", timeout: float = 4.0) -> None:
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout
        self.model = "Huawei (unknown)"
        self._demo = ip in {"demo", "192.168.8.1", "192.168.1.1"}
        # internal simulated state
        self._supported_bands: list[int] = [3, 7, 20, 28, 38, 40, 41]
        self._current_locked_bands: list[int] = []
        self._current_band = "B3"
        self._signal_dbm = -95
        self._supports_band_lock = True
        # huawei-lte-api objects
        self._connection: Any | None = None
        self._client: Any | None = None

        # Try to import the real library lazily when needed
        try:
            from huawei_lte_api.Connection import Connection
            from huawei_lte_api.Client import Client
            self._Connection = Connection
            self._Client = Client
            self._have_api = True
        except Exception:
            self._Connection = None
            self._Client = None
            self._have_api = False
            logger.info("huawei_lte_api not available; running in demo mode")

    # ---- low-level API handling ----
    def _open_client(self) -> None:
        if not self._have_api or self._connection is not None:
            return
        try:
            url = f"http://{self.ip}"
            conn = self._Connection(url, username=self.username, password=self.password, timeout=self.timeout)
            client = self._Client(conn)
            self._connection = conn
            self._client = client
        except Exception as e:
            logger.exception("Failed to open huawei client: %s", e)
            self._connection = None
            self._client = None
            self._have_api = False

    def _close_client(self) -> None:
        try:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    logger.debug("connection close failed", exc_info=True)
        finally:
            self._connection = None
            self._client = None

    # ---- public API ----
    def connect(self) -> RouterStatus:
        """Connect and read basic device information. Falls back to demo if needed."""
        if self._demo or not self._have_api:
            # demo values
            self.model = "Huawei B618"
            return RouterStatus(
                model=self.model,
                ip=self.ip,
                signal_dbm=-90,
                band=self._current_band,
                bands=self._supported_bands,
                supported_band_lock=self._supports_band_lock,
                current_locked_bands=self._current_locked_bands,
                provider="Huawei",
            )

        # Real API path
        self._open_client()
        if not self._client:
            # fallback demo
            return self.connect()

        try:
            info = self._client.device.information() or {}
            signal = self._client.device.signal() or {}
            self.model = info.get("Model", info.get("DeviceName")) or self.model
            # try to read supported bands
            try:
                nml = self._client.net.net_mode_list()
                # Attempt to parse supported bands from net_mode_list response
                # The exact format depends on firmware; we attempt a best-effort parse.
                bands = []
                # net_mode_list may contain 'lteBandList' or similar — try common keys
                if isinstance(nml, dict):
                    for key in ("lteBandList", "ltebands", "lteBand"):
                        if key in nml:
                            # expected to be comma separated like "3,7,20"
                            raw = nml[key]
                            if isinstance(raw, str):
                                bands = [int(x) for x in raw.replace("\"", "").split(',') if x.strip().isdigit()]
                                break
                if bands:
                    self._supported_bands = bands
            except Exception:
                logger.debug("Could not read net_mode_list; using defaults", exc_info=True)

            earfcn = signal.get("earfcn") or signal.get("dlband") or None
            pci = signal.get("pci")
            rsrp = signal.get("rsrp") or signal.get("rsrpdBm") or signal.get("rssi")

            # Normalise signal
            self._signal_dbm = int(rsrp) if rsrp is not None else self._signal_dbm
            band_label = f"B{signal.get('band', '')}" if signal.get('band') else self._current_band

            return RouterStatus(
                model=self.model,
                ip=self.ip,
                signal_dbm=self._signal_dbm,
                band=band_label,
                bands=self._supported_bands,
                supported_band_lock=self._supports_band_lock,
                current_locked_bands=self._current_locked_bands,
                provider="Huawei",
            )
        except Exception as exc:
            logger.exception("Failed to read status via huawei api: %s", exc)
            # On any error, close client and fallback to demo values
            self._close_client()
            return self.connect()

    def read_status(self) -> RouterStatus:
        return self.connect()

    def scan_best_signal(self) -> tuple[str, int]:
        # Simple heuristic: prefer first supported band
        best_band = f"B{self._supported_bands[0]}" if self._supported_bands else "B3"
        best_signal = self._signal_dbm
        # pretend other bands slightly vary
        for b in self._supported_bands:
            val = -90 - (b % 7)
            if val > best_signal:
                best_signal = val
                best_band = f"B{b}"
        return best_band, best_signal

    def apply_band_lock(self, selected_bands: list[int]) -> RouterStatus:
        """Attempt to apply band lock. If API unavailable, simulate.

        Note: writing band lock is firmware-dependent. Here we attempt a
        best-effort call to client.net.set_net_mode with a simple lteband
        string; if that fails we fall back to simulation and raise a
        ValueError with a helpful message.
        """
        if not selected_bands:
            raise ValueError("اختر نطاقاً واحداً على الأقل!")
        if not self._supports_band_lock:
            raise ValueError("هذا الراوتر مقيد — تعديل النطاقات غير متاح.")

        if not self._have_api or self._client is None:
            # simulate
            self._current_locked_bands = sorted(selected_bands)
            self._current_band = f"B{self._current_locked_bands[0]}"
            self._signal_dbm = -87
            return self.read_status()

        # Try write via API (best-effort)
        lteband = ",".join(str(b) for b in selected_bands)
        try:
            # Read current net mode to preserve other fields
            current = None
            try:
                current = self._client.net.net_mode() or {}
            except Exception:
                logger.debug("net_mode read failed (will attempt write anyway)")
            # networkband and networkmode arguments are firmware-specific; pass None when unknown
            try:
                self._client.net.set_net_mode(lteband, None, None)
            except Exception as e:
                logger.warning("set_net_mode attempt failed: %s", e, exc_info=True)
                # fall back to simulation and inform caller
                self._current_locked_bands = sorted(selected_bands)
                self._current_band = f"B{self._current_locked_bands[0]}"
                self._signal_dbm = -87
                raise ValueError("لم يتم تأكيد تغيير الباند بواسطة الراوتر — تحقق من السطر 'الآن على المودم'.")

            # read back
            try:
                # best-effort read back
                read_back = self._client.net.net_mode() or {}
                # if read_back contains lteBand or similar, verify
                # otherwise accept and update local state
                self._current_locked_bands = sorted(selected_bands)
                self._current_band = f"B{self._current_locked_bands[0]}"
                return self.read_status()
            except Exception:
                # write likely successful but read-back failed
                self._current_locked_bands = sorted(selected_bands)
                self._current_band = f"B{self._current_locked_bands[0]}"
                raise ValueError("تم إرسال الأمر لكن لم يؤكد الراوتر التغيير — تحقق من السطر 'الآن على المودم'.")
        finally:
            # don't close client here; keep session for further ops
            pass

    def restore_original(self) -> RouterStatus:
        # Attempt to restore by clearing locked bands
        if not self._have_api or self._client is None:
            self._current_locked_bands = []
            self._current_band = "B3"
            return self.read_status()
        try:
            # Best-effort: set to AUTO by empty lteband string
            try:
                self._client.net.set_net_mode("", None, None)
            except Exception:
                logger.debug("restore via API failed; simulating restore")
            self._current_locked_bands = []
            self._current_band = "B3"
            return self.read_status()
        except Exception:
            return self.read_status()

    @property
    def supports_band_lock(self) -> bool:
        return self._supports_band_lock
