"""服务端在窗口退出后仍应自行发布发现记录。"""

from types import SimpleNamespace

from app.service import discovery


def test_only_lan_ipv4_addresses_are_announced(monkeypatch):
    adapters = [SimpleNamespace(ips=[SimpleNamespace(ip=value) for value in (
        "127.0.0.1", "192.168.1.12", "10.0.0.7", "172.31.2.4", "8.8.8.8",
        ("fe80::1", 0, 1))])]
    monkeypatch.setattr(discovery.ifaddr, "get_adapters", lambda: adapters)
    assert discovery.lan_addresses() == ("10.0.0.7", "172.31.2.4", "192.168.1.12")


def test_publisher_tracks_network_changes_and_releases_registration(monkeypatch):
    addresses = ["192.168.1.12"]
    instances = []

    class FakeZeroconf:
        def __init__(self, **_):
            self.registered = []
            self.unregistered = []
            self.closed = False
            instances.append(self)

        def register_service(self, info):
            self.registered.append(info)

        def unregister_service(self, info):
            self.unregistered.append(info)

        def close(self):
            self.closed = True

    monkeypatch.setattr(discovery, "Zeroconf", FakeZeroconf)
    publisher = discovery.DiscoveryPublisher("instance-1", "0.1.0", 8000,
        lambda: tuple(addresses))
    publisher.sync()
    assert len(instances) == 1
    assert instances[0].registered[0].port == 8000
    assert instances[0].registered[0].properties[b"id"] == b"instance-1"
    publisher.sync()
    assert len(instances) == 1

    addresses[:] = ["192.168.1.13"]
    publisher.sync()
    assert instances[0].closed
    assert len(instances[0].unregistered) == 1
    assert len(instances) == 2

    addresses.clear()
    publisher.sync()
    assert instances[1].closed
    assert len(instances[1].unregistered) == 1
