import datetime
import time
from typing import Protocol

import requests
from icmplib import ping
from structlog import get_logger

from meshmon.config.config import Config, LoadedNetworkMonitor
from meshmon.dstypes import DSMonitorData, DSNodeStatus
from meshmon.pulsewave.store import SharedStore
from meshmon.pulsewave.update.events import ConfigWatcher

from ..config.bus import ConfigPreprocessor


class DirectMonitorConfigPreprocessor(ConfigPreprocessor[LoadedNetworkMonitor]):
    """Preprocessor for a specific HTTP monitor's config"""

    def __init__(self, network_id: str, monitor_name: str):
        self.network_id = network_id
        self.monitor_name = monitor_name

    def preprocess(self, config: Config | None) -> LoadedNetworkMonitor | None:
        if config is None:
            return None

        network = config.networks.get(self.network_id)
        if network is None:
            return None

        # Find the monitor by name
        for monitor in network.monitors:
            if monitor.name == self.monitor_name:
                return monitor

        return None


class MonitorProto(Protocol):
    def run(self) -> DSMonitorData | None: ...

    @property
    def ctx_name(self) -> str: ...

    @property
    def interval(self) -> int: ...

    @property
    def retry(self) -> int: ...


class HTTPMonitor(MonitorProto):
    def __init__(
        self,
        net_id: str,
        name: str,
        config_watcher: ConfigWatcher[LoadedNetworkMonitor],
    ):
        self.logger = get_logger().bind(
            module="meshmon.monitor",
            component="HTTPMonitor",
            name=name,
            net_id=net_id,
        )
        self.config_watcher = config_watcher
        self.config = config_watcher.current_config

        self.session = requests.Session()

    def reload(self, config: LoadedNetworkMonitor):
        self.logger.info(
            "HTTPMonitor config reloaded",
            host=config.host,
            interval=config.interval,
            retry=config.retry,
        )
        self.config = config

    @property
    def ctx_name(self) -> str:
        return self.config.name

    @property
    def interval(self) -> int:
        return self.config.interval

    @property
    def retry(self) -> int:
        return self.config.retry

    def run(self):
        try:
            st = time.time()
            response = requests.get(f"{self.config.host}", timeout=self.config.interval)
            rtt = time.time() - st
        except requests.RequestException as exc:
            self.logger.debug("Request timed out", exc=exc)
            return
        if rtt > self.config.interval:
            self.logger.warning("High RTT detected", rtt_ms=rtt)
            return
        elif response.status_code != 200:
            self.logger.warning(
                "Invalid response from monitor",
                status=response.status_code,
                body=response.text,
            )
            return
        else:
            self.logger.debug(
                "Successful response from monitor",
            )
            return DSMonitorData(
                status=DSNodeStatus.ONLINE,
                req_time_rtt=rtt,
                date=datetime.datetime.now(datetime.timezone.utc),
                interval=self.config.interval,
                retry=self.config.retry,
            )


class PingMonitor(MonitorProto):
    """
    ICMP "ping" using icmplib with a TCP connect fallback.

    Host parsing rules:
    - If config.host starts with http/https, use hostname and default ports (80/443) unless a port is present.
    - If config.host is host:port (optionally with [ipv6]:port), use provided host and port.
    - Otherwise, default to port 80.

    On success, returns DSPingData with ONLINE and RTT.
    On failure or high RTT (> interval), returns None and manager will handle retries/invalidations.
    """

    def __init__(
        self,
        net_id: str,
        name: str,
        config_watcher: ConfigWatcher[LoadedNetworkMonitor],
    ):
        self.logger = get_logger().bind(
            module="meshmon.monitor",
            component="PingMonitor",
            name=name,
            net_id=net_id,
        )
        self.config_watcher = config_watcher
        self.config = config_watcher.current_config

    def reload(self, config: LoadedNetworkMonitor):
        self.logger.info(
            "PingMonitor config reloaded",
            host=config.host,
            interval=config.interval,
            retry=config.retry,
        )
        self.config = config

    @property
    def ctx_name(self) -> str:
        return self.config.name

    @property
    def interval(self) -> int:
        return self.config.interval

    @property
    def retry(self) -> int:
        return self.config.retry

    def run(self):
        timeout = float(self.config.interval)

        # 1) Prefer ICMP using icmplib (works unprivileged with privileged=False on many platforms)
        try:
            result = ping(
                address=self.config.host,
                count=4,
                interval=1,
                timeout=10,
                privileged=False,
            )
            if result.is_alive:
                rtt_ms = result.avg_rtt or result.min_rtt or result.max_rtt or 0.0
                rtt = rtt_ms / 1000.0
                if rtt > timeout:
                    self.logger.warning(
                        "High RTT detected (ICMP)", host=self.config.host, rtt_ms=rtt
                    )
                    return
                self.logger.debug(
                    "ICMP ping successful", host=self.config.host, rtt_ms=rtt
                )
                return DSMonitorData(
                    status=DSNodeStatus.ONLINE,
                    req_time_rtt=rtt,
                    date=datetime.datetime.now(datetime.timezone.utc),
                    interval=self.config.interval,
                    retry=self.config.retry,
                )
            else:
                self.logger.debug("ICMP ping reported host down", host=self.config.host)
                return
        except Exception as e:
            self.logger.debug("ICMP ping failed, falling back to TCP connect", error=e)


class RebroadcastMonitor(MonitorProto):
    def __init__(
        self,
        monitor_name: str,
        dest_name: str,
        store: SharedStore,
        config_watcher: ConfigWatcher[LoadedNetworkMonitor],
    ):
        self.logger = get_logger().bind(
            module="meshmon.monitor",
            component="RebroadcastMonitor",
            name=monitor_name,
            net_id=store.network_id,
        )
        self.dest_name = dest_name
        self.store = store
        self.config_watcher = config_watcher
        self.config = config_watcher.current_config

    def reload(self, config: LoadedNetworkMonitor):
        self.logger.info(
            "RebroadcastMonitor config reloaded",
            host=config.host,
            interval=config.interval,
            retry=config.retry,
        )
        self.config = config

    @property
    def ctx_name(self) -> str:
        return self.dest_name

    @property
    def interval(self) -> int:
        return self.config.interval

    @property
    def retry(self) -> int:
        return self.config.retry

    def run(self):
        monitor_ctx = self.store.get_context("monitor_data", DSMonitorData)
        monitor_data = monitor_ctx.get(self.config.name)
        if monitor_data is None:
            self.logger.debug("No monitor data to rebroadcast", monitor=self.dest_name)
            return
        self.logger.debug("Rebroadcasting monitor data", monitor=self.dest_name)
        return monitor_data
