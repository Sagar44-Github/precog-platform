"""Plain-English sentences for alerts. Fixed templates only: no outside service, nothing invented.

NIDS also invents 'threat actor', ASN and location values. They are SIMULATED, so they are never used here.
"""

SERVICE_NAMES = {
    21: "FTP, file transfer", 22: "SSH, remote login", 23: "Telnet, remote login", 53: "DNS, name lookup",
    80: "web, HTTP", 135: "Windows RPC", 137: "NetBIOS name service", 138: "NetBIOS datagram service",
    139: "NetBIOS session service", 443: "secure web, HTTPS", 445: "SMB, Windows file sharing",
    3389: "Remote Desktop", 4444: "a port often used by attack tools", 6666: "a port often used by backdoors",
    31337: "a port often used by backdoors",
}

SEVERITY_WORDS = {"HIGH": "high risk", "MEDIUM": "medium risk", "LOW": "low risk"}


def service_name(port):
    return SERVICE_NAMES.get(port)


def tactic_words(technique):
    return ", ".join(t.replace("-", " ") for t in technique["tactics"])


def explain_packet(src_name, dst_name, protocol, port, size, severity, technique=None):
    """One alert raised by NIDS's detector for a single packet."""
    where = "port %s" % port if port else "no port"
    service = service_name(port) if port else None
    if service:
        where += " (%s)" % service
    text = "%s sent a %s-byte %s packet to %s on %s. NIDS rated it %s." % (
        src_name, size, protocol, where, dst_name, SEVERITY_WORDS.get(severity, "unrated"))
    if technique:
        text += " Traffic like this can be a sign of %s (%s), a %s technique." % (
            technique["name"], technique["id"], tactic_words(technique))
    return text


def explain_technique(host_name, technique, note=None, compromise=False):
    """One scripted technique event (imitating output from an attack simulation tool)."""
    text = "%s shows activity matching %s (%s), part of the %s stage of an attack." % (
        host_name, technique["name"], technique["id"], tactic_words(technique))
    if note:
        text += " %s." % note.strip().rstrip(".")
    if compromise:
        text += " %s is now treated as compromised." % host_name
    return text
