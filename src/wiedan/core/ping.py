"""Windows ICMP ping helpers for background reachability checks."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess


def _ping_host(address: str) -> bool:
    result = subprocess.run(
        ["ping", "-n", "1", "-w", "2000", address],
        capture_output=True,
        check=False,
        timeout=3,
    )
    return result.returncode == 0


def ping_devices(addresses: dict[str, str], on_result=None) -> dict[str, bool]:
    """Ping each device concurrently; map device IDs to reachability.

    on_result(device_id, ok) wird aus einem Hilfsthread je fertigem Ping aufgerufen.
    """
    if not addresses:
        return {}

    results = {}
    with ThreadPoolExecutor(max_workers=min(16, len(addresses))) as executor:
        futures = {
            executor.submit(_ping_host, address): device_id
            for device_id, address in addresses.items()
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
            if on_result:
                on_result(futures[future], results[futures[future]])
    return results
