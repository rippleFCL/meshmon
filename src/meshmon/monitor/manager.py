import datetime
from dataclasses import dataclass
from threading import Event, Thread

from structlog.stdlib import get_logger

from meshmon.config.config import Config, LoadedNetworkMonitor, LoadedNetworkNodeInfo
from meshmon.config.structure.network import MonitorTypes
from meshmon.pulsewave.store import SharedStore

from ..config.bus import ConfigBus, ConfigPreprocessor
from ..distrostore import (
    StoreManager,
)
from ..dstypes import DSMonitorData, DSNodeInfo, DSNodeStatus
from ..version import VERSION
from .monitors import (
    DirectMonitorConfigPreprocessor,
    HTTPMonitor,
    MonitorProto,
    PingMonitor,
    RebroadcastMonitor,
)


class Monitor:
    def __init__(
        self,
        monitor: MonitorProto,
        monitor_name: str,
        network_id: str,
        store_manager: StoreManager,
    ):
        self.name = monitor_name
        self.store = store_manager
        self.network_id = network_id
        self.monitor = monitor
        self.thread = Thread(
            target=self.monitor_thread,
            name=f"{self.name}-thread",
        )
        self.stop_flag = Event()
        self.logger = get_logger().bind(
            module="meshmon.monitor", component="Monitor", name=self.name
        )

    def setup(self):
        store = self.store.get_store(self.network_id)
        ctx = store.get_context("monitor_data", DSMonitorData)
        ctx.set(
            self.monitor.ctx_name,
            DSMonitorData(
                status=DSNodeStatus.UNKNOWN,
                req_time_rtt=-1,
                date=datetime.datetime.now(datetime.timezone.utc),
                interval=self.monitor.interval,
                retry=self.monitor.retry,
            ),
        )

    def shutdown(self) -> None:
        store = self.store.get_store(self.network_id)
        ctx = store.get_context("monitor_data", DSMonitorData)
        ctx.delete(self.monitor.ctx_name)

    def invalidate_old_ping(self):
        store = self.store.get_store(self.network_id)
        ctx = store.get_context("monitor_data", DSMonitorData)
        ping_data = ctx.get(self.monitor.ctx_name)
        if ping_data is None:
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        if (
            (now - ping_data.date).total_seconds()
            > ping_data.interval * ping_data.retry
            and ping_data.status != DSNodeStatus.OFFLINE
        ):
            ctx.set(
                self.monitor.ctx_name,
                DSMonitorData(
                    status=DSNodeStatus.OFFLINE,
                    req_time_rtt=-1,
                    date=now,
                    interval=ping_data.interval,
                    retry=ping_data.retry,
                ),
            )

    def monitor_thread(self):
        self.logger.debug("Starting monitor thread")
        self.setup()
        store = self.store.get_store(self.network_id)
        ctx = store.get_context("monitor_data", DSMonitorData)
        while True:
            try:
                self.invalidate_old_ping()
                if ping_data := self.monitor.run():
                    ctx.set(self.monitor.ctx_name, ping_data)
            except Exception as exc:
                self.logger.error("Error in monitor loop", error=exc)
            val = self.stop_flag.wait(self.monitor.interval)
            if val:
                break
        self.shutdown()
        self.logger.debug("Monitor thread stopped")

    def start(self) -> None:
        self.logger.info(
            "Starting monitor thread at interval", interval_s=self.monitor.interval
        )
        self.thread.start()

    def stop(self):
        self.logger.info("Stopping monitor")
        self.stop_flag.set()

    def join(self):
        self.thread.join()
        self.logger.debug("Monitor thread stopped")


@dataclass(frozen=True)
class RebroadcastKey:
    src_network_id: str
    dest_network_id: str
    dest_name: str
    src_monitor_name: str

    def __hash__(self) -> int:
        return hash(
            (
                self.src_network_id,
                self.dest_network_id,
                self.dest_name,
                self.src_monitor_name,
            )
        )


@dataclass
class MonitorConfig:
    monitors: dict[tuple[str, str], LoadedNetworkMonitor]
    rebroadcast: set[RebroadcastKey]


class MonitorConfigPreprocessor(ConfigPreprocessor[MonitorConfig]):
    @staticmethod
    def get_rebroadcasts(
        cfg: Config, node_cfg: LoadedNetworkNodeInfo, net_id: str
    ) -> set[RebroadcastKey]:
        rebroadcasts: set[RebroadcastKey] = set()
        for src_network_id, rebs in node_cfg.rebroadcast.items():
            net_config = cfg.networks.get(src_network_id)
            if not net_config:
                continue
            if rebs.monitors:
                monitor_names = {monitor.name for monitor in net_config.monitors}
                for reb in rebs.monitors:
                    if reb.name in monitor_names:
                        rebroadcasts.add(
                            RebroadcastKey(
                                src_network_id,
                                net_id,
                                f"{rebs.prefix}{reb.dest_name}",
                                reb.name,
                            )
                        )
            else:
                for monitor in net_config.monitors:
                    rebroadcasts.add(
                        RebroadcastKey(
                            src_network_id,
                            net_id,
                            f"{rebs.prefix}{monitor.name}",
                            monitor.name,
                        )
                    )

        return rebroadcasts

    def preprocess(self, config: Config | None) -> MonitorConfig:
        monitors: dict[tuple[str, str], LoadedNetworkMonitor] = {}
        rebroadcast: set[RebroadcastKey] = set()
        if config is None:
            return MonitorConfig(monitors=monitors, rebroadcast=rebroadcast)
        for net_id, network in config.networks.items():
            # Find local node
            for monitor in network.monitors:
                node_id = network.node_id
                if node_id not in monitor.block and (
                    not monitor.allow or node_id in monitor.allow
                ):
                    monitors[(net_id, monitor.name)] = monitor
            for node_config in network.node_config:
                if node_config.node_id == network.node_id:
                    rebroadcast.update(
                        self.get_rebroadcasts(config, node_config, net_id)
                    )
        return MonitorConfig(monitors=monitors, rebroadcast=rebroadcast)


class MonitorManager:
    def __init__(
        self,
        store_manager: StoreManager,
        config_bus: ConfigBus,
    ):
        config_watcher = config_bus.get_watcher(MonitorConfigPreprocessor())
        if config_watcher is None:
            raise ValueError("No initial config available for monitor manager")
        self.store_manager = store_manager
        self.config_bus = config_bus
        self.config_watcher = config_watcher
        self.config = config_watcher.current_config
        self.config_watcher.subscribe(self.reload)
        self.logger = get_logger().bind(
            module="meshmon.monitor", component="MonitorManager"
        )
        self.monitors: dict[tuple[str, str], Monitor] = {}
        self.rebroadcast: dict[RebroadcastKey, Monitor] = {}
        self.stop_flag = Event()
        self.thread = Thread(target=self.manager, name="monitor-manager")
        self.logger.debug("MonitorManager initialized")
        # Initialize monitors from current config
        self._create_monitors(self.config.monitors)
        self._create_rebroadcasts(self.config.rebroadcast)

    def manager(self):
        while True:
            try:
                for store in self.store_manager.stores.values():
                    node_info = DSNodeInfo(version=VERSION)
                    store.set_value("node_info", node_info)
            except Exception as exc:
                self.logger.error("Error in MonitorManager heartbeat", error=exc)
            val = self.stop_flag.wait(5)
            if val:
                break

    def _create_monitors(
        self, desired_monitors: dict[tuple[str, str], LoadedNetworkMonitor]
    ) -> None:
        """Create and start monitors from the desired monitor config."""
        for key, m_info in desired_monitors.items():
            if key not in self.monitors:
                net_id, monitor_name = key
                monitor_watcher = self.config_bus.get_watcher(
                    DirectMonitorConfigPreprocessor(net_id, monitor_name)
                )
                if monitor_watcher is None:
                    self.logger.warning(
                        "No config available for monitor; skipping",
                        network_id=net_id,
                        monitor_name=monitor_name,
                    )
                    continue
                if m_info.type == MonitorTypes.HTTP:
                    full_monitor_name = f"HTTPMonitor-{monitor_name}"
                    self.logger.debug("Creating HTTP monitor", key=key)
                    monitor = HTTPMonitor(net_id, full_monitor_name, monitor_watcher)
                    monitor_wrapper = Monitor(
                        monitor, full_monitor_name, net_id, self.store_manager
                    )
                    self.monitors[key] = monitor_wrapper
                    monitor_wrapper.start()
                elif m_info.type == MonitorTypes.PING:
                    full_monitor_name = f"PingMonitor-{monitor_name}"
                    self.logger.debug("Creating PING monitor", key=key)
                    monitor = PingMonitor(net_id, full_monitor_name, monitor_watcher)
                    monitor_wrapper = Monitor(
                        monitor, full_monitor_name, net_id, self.store_manager
                    )
                    self.monitors[key] = monitor_wrapper
                    monitor_wrapper.start()
                else:
                    self.logger.warning(
                        "Unsupported monitor type; skipping",
                        key=key,
                        type=str(m_info.type),
                    )

    def _create_rebroadcasts(self, desired_rebroadcasts: set[RebroadcastKey]) -> None:
        """Create and start rebroadcast monitors from the desired rebroadcast config."""
        for key in desired_rebroadcasts:
            if key not in self.rebroadcast:
                src_network_id = key.src_network_id
                net_id = key.dest_network_id
                dest_name = key.dest_name
                src_monitor_name = key.src_monitor_name
                monitor_watcher = self.config_bus.get_watcher(
                    DirectMonitorConfigPreprocessor(src_network_id, src_monitor_name)
                )
                if monitor_watcher is None:
                    self.logger.warning(
                        "No config available for rebroadcast monitor; skipping",
                        network_id=src_network_id,
                        monitor_name=src_monitor_name,
                    )
                    continue
                full_monitor_name = (
                    f"RebroadcastMonitor-{src_monitor_name}-to-{dest_name}"
                )
                self.logger.debug("Creating Rebroadcast monitor", key=key)
                remote_store: SharedStore = self.store_manager.get_store(src_network_id)
                monitor = RebroadcastMonitor(
                    full_monitor_name, dest_name, remote_store, monitor_watcher
                )
                monitor_wrapper = Monitor(
                    monitor, full_monitor_name, net_id, self.store_manager
                )
                self.rebroadcast[key] = monitor_wrapper
                monitor_wrapper.start()

    def reload(self, new_config: MonitorConfig) -> None:
        """Handle config reload - stop removed/changed monitors and create new ones."""
        self.logger.info(
            "Config reload triggered for MonitorManager",
            current_monitor_count=len(self.monitors),
            new_monitor_count=len(new_config.monitors),
        )
        self.config = new_config

        desired_monitors = new_config.monitors
        current_keys = set(self.monitors.keys())
        desired_keys = set(desired_monitors.keys())

        # Stop monitors that are no longer desired or changed
        to_remove = []
        for key in current_keys - desired_keys:
            to_remove.append(key)

        self.logger.debug(
            "Monitors to remove/recreate",
            remove_count=len(to_remove),
            keys=list(to_remove),
        )

        for key in to_remove:
            try:
                self.logger.debug("Stopping removed/changed monitor", key=key)
                self.monitors[key].stop()
            except Exception:
                pass
        for key in to_remove:
            try:
                self.monitors[key].join()
            except Exception:
                pass
            self.monitors.pop(key, None)

        # Create and start new/changed monitors
        self._create_monitors(desired_monitors)

        desired_rebroadcasts_keys = new_config.rebroadcast
        current_rebroadcast_keys = set(self.rebroadcast.keys())
        # Stop rebroadcast monitors that are no longer desired
        to_remove_rebroadcast = []
        for key in current_rebroadcast_keys - desired_rebroadcasts_keys:
            to_remove_rebroadcast.append(key)
        self.logger.debug(
            "Rebroadcast monitors to remove",
            remove_count=len(to_remove_rebroadcast),
            keys=list(to_remove_rebroadcast),
        )
        for key in to_remove_rebroadcast:
            try:
                self.logger.debug("Stopping removed rebroadcast monitor", key=key)
                self.rebroadcast[key].stop()
            except Exception:
                pass
        for key in to_remove_rebroadcast:
            try:
                self.rebroadcast[key].join()
            except Exception:
                pass
            self.rebroadcast.pop(key, None)

        self._create_rebroadcasts(desired_rebroadcasts_keys)

        self.logger.info(
            "MonitorManager reload complete",
            total_monitors=len(self.monitors),
        )

    def start(self):
        self.logger.info("Starting MonitorManager thread")
        self.thread.start()

    def stop(self):
        self.logger.info("Stopping all monitors in MonitorManager")
        for monitor_key, monitor in self.monitors.items():
            self.logger.debug("Stopping monitor", key=monitor_key)
            monitor.stop()
        for monitor in self.monitors.values():
            monitor.join()
        self.monitors.clear()

        self.logger.info("All monitors stopped")

    def stop_manager(self):
        self.logger.info("Stopping MonitorManager")
        self.stop_flag.set()
        if self.thread.is_alive():
            self.thread.join()
        self.logger.info("MonitorManager stopped")
