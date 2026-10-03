"""Windows ICMP ping helpers for background reachability checks."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess


def _ping_host(address: str) -> bool:
    result = subprocess.run(
        ["ping", "-n", "1", "-w", "1000", address],
        capture_output=True,
        check=False,
        timeout=3,
    )
    return result.returncode == 0


def ping_devices(addresses: dict[str, str]) -> dict[str, bool]:
    """Ping each device concurrently; map device IDs to reachability."""
    if not addresses:
        return {}

    with ThreadPoolExecutor(max_workers=min(16, len(addresses))) as executor:
        futures = {
            executor.submit(_ping_host, address): device_id
            for device_id, address in addresses.items()
        }
        return {futures[future]: future.result() for future in as_completed(futures)}
