# app/core/cloudflare.py
import ipaddress
from fastapi import Request, HTTPException

# IPs oficiales de Cloudflare — actualizar periódicamente desde https://www.cloudflare.com/ips/
CLOUDFLARE_IPV4 = [
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22",
    "103.31.4.0/22",   "141.101.64.0/18", "108.162.192.0/18",
    "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22",
    "198.41.128.0/17", "162.158.0.0/15",  "104.16.0.0/13",
    "104.24.0.0/14",   "172.64.0.0/13",   "131.0.72.0/22",
]
CLOUDFLARE_IPV6 = [
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32",
    "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29",
    "2c0f:f248::/32",
]

_CF_NETWORKS = [
    ipaddress.ip_network(cidr)
    for cidr in CLOUDFLARE_IPV4 + CLOUDFLARE_IPV6
]

# IPs internas permitidas — Hetzner internal, localhost, etc.
_REDES_INTERNAS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

def es_ip_cloudflare(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        # Permitir IPs internas — para comunicación interna entre servicios
        if any(addr in red for red in _REDES_INTERNAS):
            return True
        return any(addr in red for red in _CF_NETWORKS)
    except ValueError:
        return False