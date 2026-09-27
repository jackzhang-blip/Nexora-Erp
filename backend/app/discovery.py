"""由独立服务进程发布局域网发现信息。"""

import ipaddress
import logging
import threading
from typing import Callable

import ifaddr
from zeroconf import IPVersion, ServiceInfo, Zeroconf


LOG = logging.getLogger(__name__)
SERVICE_TYPE = "_nexora._tcp.local."


def lan_addresses() -> tuple[str, ...]:
    """只发布客户端允许连接的 IPv4 局域网地址。"""
    found: set[str] = set()
    for adapter in ifaddr.get_adapters():
        for entry in adapter.ips:
            if not isinstance(entry.ip, str):
                continue
            try:
                address = ipaddress.IPv4Address(entry.ip)
            except ipaddress.AddressValueError:
                continue
            if address in ipaddress.IPv4Network("10.0.0.0/8") or address in ipaddress.IPv4Network(
                    "172.16.0.0/12") or address in ipaddress.IPv4Network("192.168.0.0/16") or address in ipaddress.IPv4Network(
                    "169.254.0.0/16"):
                found.add(str(address))
    return tuple(sorted(found))


class DiscoveryPublisher:
    def __init__(self, instance_id: str, version: str, port: int,
                 address_provider: Callable[[], tuple[str, ...]] = lan_addresses):
        self.instance_id = instance_id
        self.version = version
        self.port = port
        self.address_provider = address_provider
        self._addresses: tuple[str, ...] = ()
        self._zeroconf: Zeroconf | None = None
        self._service: ServiceInfo | None = None
        self._lock = threading.RLock()

    def sync(self) -> None:
        """地址变化或开机时网络未就绪时，在下一轮重新发布。"""
        with self._lock:
            addresses = self.address_provider()
            if addresses == self._addresses:
                return
            self.close()
            if not addresses:
                return
            service = ServiceInfo(
                SERVICE_TYPE, f"Nexora-{self.instance_id}.{SERVICE_TYPE}",
                addresses=[ipaddress.IPv4Address(value).packed for value in addresses],
                port=self.port, properties={"id": self.instance_id, "version": self.version},
                server=f"nexora-{self.instance_id}.local.")
            publisher = Zeroconf(ip_version=IPVersion.V4Only)
            try:
                publisher.register_service(service)
            except Exception:
                publisher.close()
                LOG.exception("局域网发现广播失败，客户端仍可使用手动地址连接")
                return
            self._zeroconf = publisher
            self._service = service
            self._addresses = addresses
            LOG.info("已发布局域网发现记录，地址：%s", ", ".join(addresses))

    def close(self) -> None:
        # 关闭与网卡变更可能发生在不同线程，避免对同一 Zeroconf 实例重复释放。
        with self._lock:
            if self._zeroconf is not None:
                try:
                    if self._service is not None:
                        self._zeroconf.unregister_service(self._service)
                finally:
                    self._zeroconf.close()
            self._service = None
            self._zeroconf = None
            self._addresses = ()
