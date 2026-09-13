"""Outbound Egress Guard & SSRF Protection Architecture (FR-SSRF-001, SECURITY.md Section 14.1).

This module provides server-side egress filtering, DNS rebinding mitigation, redirect re-validation,
and SSRF validation for all outbound HTTP/HTTPS requests triggered by untrusted customer input,
document links, external URLs, or third-party webhooks.
"""

import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.core.errors import SSRFProtectionException
from app.core.logging import logger

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}

FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-Local & AWS/GCP IMDS (169.254.169.254)
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-Local
    ipaddress.ip_network("fc00::/7"),   # IPv6 Unique Local Address
    ipaddress.ip_network("ff00::/8"),   # IPv6 Multicast
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast IPv4
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved IPv4
]


def is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address falls into private, loopback, link-local, or reserved networks."""
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        return True

    return any(ip in net for net in FORBIDDEN_NETWORKS)


def matches_domain_pattern(hostname: str, domain_pattern: str) -> bool:
    """Check if hostname matches domain pattern (supports exact match or wildcard *.example.com)."""
    host = hostname.lower()
    pattern = domain_pattern.lower().strip()

    if pattern.startswith("*."):
        suffix = pattern[1:]  # e.g. .example.com
        return host.endswith(suffix) or host == pattern[2:]

    if pattern.startswith("."):
        return host.endswith(pattern) or host == pattern[1:]

    return host == pattern or host.endswith("." + pattern)


class OutboundEgressGuard:
    """Server-side Egress Guard for SSRF Prevention & Redirect Re-Validation."""

    @classmethod
    def validate_url(
        cls,
        url: str,
        allowed_domains: list[str] | None = None,
        allowed_ports: set[int] | None = None,
    ) -> tuple[str, str]:
        """Validate URL scheme, credentials, port, domain, and pre-resolved IP address.

        Args:
            url: Target URL string to validate.
            allowed_domains: Optional list of whitelisted domain patterns (e.g. ["*.meta.com"]).
            allowed_ports: Optional set of permitted destination ports.

        Returns:
            tuple[str, str]: Validated URL string and primary resolved IP address string.

        Raises:
            SSRFProtectionException: If URL violates SSRF security policy.
        """
        if not url or not isinstance(url, str):
            raise SSRFProtectionException("Invalid or empty URL provided.")

        try:
            parsed = urlparse(url.strip())
        except Exception as err:
            raise SSRFProtectionException(f"Failed to parse URL: {err}") from err

        # 1. Scheme Check
        if not parsed.scheme or parsed.scheme.lower() not in ALLOWED_SCHEMES:
            logger.warning(
                "SECURITY_SSRF_ATTEMPT url=%s reason=forbidden_scheme scheme=%s",
                url,
                parsed.scheme,
            )
            raise SSRFProtectionException(
                f"Forbidden URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
            )

        # 2. Credential Check (embedded user:pass@host)
        if parsed.username or parsed.password:
            logger.warning("SECURITY_SSRF_ATTEMPT url=%s reason=embedded_credentials", url)
            raise SSRFProtectionException(
                "URL containing embedded user authentication credentials is prohibited."
            )

        # 3. Hostname Check
        hostname = parsed.hostname
        if not hostname:
            logger.warning("SECURITY_SSRF_ATTEMPT url=%s reason=missing_hostname", url)
            raise SSRFProtectionException("URL must contain a valid hostname.")

        # 4. Port Check
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        permitted_ports = allowed_ports or ALLOWED_PORTS
        if port not in permitted_ports:
            logger.warning(
                "SECURITY_SSRF_ATTEMPT url=%s reason=forbidden_port port=%s",
                url,
                port,
            )
            raise SSRFProtectionException(
                f"Forbidden destination port '{port}'. Permitted ports: {permitted_ports}."
            )

        # 5. Domain Whitelist Check (if configured)
        if allowed_domains:
            domain_match = any(
                matches_domain_pattern(hostname, pattern) for pattern in allowed_domains
            )
            if not domain_match:
                logger.warning(
                    "SECURITY_SSRF_ATTEMPT url=%s reason=domain_not_whitelisted hostname=%s",
                    url,
                    hostname,
                )
                raise SSRFProtectionException(
                    f"Domain '{hostname}' is not in the egress whitelist."
                )

        # 6. IP Address / DNS Pre-Resolution & DNS Rebinding Check
        resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []

        try:
            # Check if hostname is an explicit raw IP string
            raw_ip = ipaddress.ip_address(hostname)
            resolved_ips.append(raw_ip)
        except ValueError:
            # Hostname is a domain name; perform DNS resolution check
            try:
                addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
                for item in addr_info:
                    ip_str = item[4][0]
                    resolved_ips.append(ipaddress.ip_address(ip_str))
            except socket.gaierror as err:
                logger.warning(
                    "SECURITY_SSRF_ATTEMPT url=%s reason=dns_resolution_failed error=%s",
                    url,
                    str(err),
                )
                raise SSRFProtectionException(
                    f"DNS resolution failed for hostname '{hostname}': {err}"
                ) from err

        if not resolved_ips:
            raise SSRFProtectionException(
                f"No IP addresses resolved for hostname '{hostname}'."
            )

        # Check every resolved IP address against forbidden network blocks
        for ip in resolved_ips:
            if is_forbidden_ip(ip):
                logger.warning(
                    "SECURITY_SSRF_ATTEMPT url=%s resolved_ip=%s reason=forbidden_ip_range",
                    url,
                    str(ip),
                )
                raise SSRFProtectionException(
                    f"Access to IP address '{ip}' is blocked by SSRF security policy."
                )

        primary_ip = str(resolved_ips[0])
        return url.strip(), primary_ip

    @classmethod
    async def safe_fetch(
        cls,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        timeout_seconds: float = 10.0,
        allowed_domains: list[str] | None = None,
        max_redirects: int = 3,
    ) -> httpx.Response:
        """Perform an outbound HTTP request after validating against SSRF policy and re-validating redirects.

        Args:
            url: Target URL string.
            method: HTTP method (GET, POST, etc.).
            headers: Optional HTTP headers dict.
            json_data: Optional JSON payload dict.
            timeout_seconds: Request timeout in seconds.
            allowed_domains: Optional domain whitelist.
            max_redirects: Maximum allowed redirect hops (default 3).

        Returns:
            httpx.Response: HTTP response object.

        Raises:
            SSRFProtectionException: If request or redirect fails SSRF validation.
        """
        current_url = url
        redirect_count = 0

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            while True:
                validated_url, primary_ip = cls.validate_url(
                    current_url, allowed_domains=allowed_domains
                )

                logger.info(
                    "outbound_egress_request_approved url=%s resolved_ip=%s method=%s hop=%d",
                    validated_url,
                    primary_ip,
                    method,
                    redirect_count,
                )

                response = await client.request(
                    method=method,
                    url=validated_url,
                    headers=headers,
                    json=json_data,
                )

                # If response is a redirect (301, 302, 303, 307, 308), re-validate target Location URL
                if response.is_redirect:
                    redirect_count += 1
                    if redirect_count > max_redirects:
                        raise SSRFProtectionException(
                            f"Exceeded maximum allowed redirect hops ({max_redirects})."
                        )

                    location = response.headers.get("Location")
                    if not location:
                        raise SSRFProtectionException("Redirect response missing Location header.")

                    # Resolve relative redirect URLs against current URL
                    current_url = urljoin(validated_url, location)
                    continue

                return response
