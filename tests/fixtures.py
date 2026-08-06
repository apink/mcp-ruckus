"""Sample fixture data mimicking real vSZ and ICX responses.

Used by mock adapters to provide deterministic test data.
All data anonymized — no real MACs, IPs, or secrets.
"""
from __future__ import annotations

# ── vSZ AP Fixtures ────────────────────────────────────────────────

SAMPLE_APS = [
    {
        "deviceName": "FTIS-AP01-01",
        "deviceMac": "aa:bb:cc:11:22:01",
        "apMac": "aa:bb:cc:11:22:01",
        "serialNumber": "SN-AP001",
        "model": "R750",
        "firmwareVersion": "6.1.2.0.1455",
        "status": "Online",
        "numClients": 23,
        "numClients24G": 8,
        "numClients5G": 15,
        "location": "Gedung FTI Lantai 1",
        "zoneName": "FTI-Campus",
        "zoneId": "zone-fti-001",
        "deviceIp": "10.60.172.101",
        "channel24G": "6 (20MHz)",
        "channel5G": "36 (80MHz)",
        "airtime24G": 35,
        "airtime5G": 42,
        "capacity": 15,
        "capacity24G": 10,
        "capacity50G": 20,
        "noise24G": -88,
        "noise5G": -92,
        "uptimeInSec": 2592000,
        "meshRole": "Root",
    },
    {
        "deviceName": "FTIS-AP01-02",
        "deviceMac": "aa:bb:cc:11:22:02",
        "apMac": "aa:bb:cc:11:22:02",
        "serialNumber": "SN-AP002",
        "model": "R750",
        "firmwareVersion": "6.1.2.0.1455",
        "status": "Online",
        "numClients": 45,
        "numClients24G": 12,
        "numClients5G": 33,
        "location": "Gedung FTI Lantai 1",
        "zoneName": "FTI-Campus",
        "zoneId": "zone-fti-001",
        "deviceIp": "10.60.172.102",
        "channel24G": "1 (20MHz)",
        "channel5G": "149 (80MHz)",
        "airtime24G": 55,
        "airtime5G": 68,
        "capacity": 60,
        "capacity24G": 45,
        "capacity50G": 75,
        "noise24G": -85,
        "noise5G": -90,
        "uptimeInSec": 1209600,
        "meshRole": "Root",
    },
    {
        "deviceName": "FTIS-AP02-03",
        "deviceMac": "aa:bb:cc:11:33:03",
        "apMac": "aa:bb:cc:11:33:03",
        "serialNumber": "SN-AP003",
        "model": "R650",
        "firmwareVersion": "6.1.2.0.1455",
        "status": "Online",
        "numClients": 12,
        "numClients24G": 3,
        "numClients5G": 9,
        "location": "Gedung FTI Lantai 2",
        "zoneName": "FTI-Campus",
        "zoneId": "zone-fti-001",
        "deviceIp": "10.60.172.201",
        "channel24G": "11 (20MHz)",
        "channel5G": "52 (40MHz)",
        "airtime24G": 18,
        "airtime5G": 25,
        "capacity": 25,
        "capacity24G": 20,
        "capacity50G": 30,
        "noise24G": -90,
        "noise5G": -94,
        "uptimeInSec": 864000,
        "meshRole": "Root",
    },
    {
        "deviceName": "FTIS-AP03-04",
        "deviceMac": "aa:bb:cc:11:44:04",
        "apMac": "aa:bb:cc:11:44:04",
        "serialNumber": "SN-AP004",
        "model": "R750",
        "firmwareVersion": "6.1.1.0.1200",
        "status": "Disconnected",
        "numClients": 0,
        "numClients24G": 0,
        "numClients5G": 0,
        "location": "Gedung FTI Lantai 3",
        "zoneName": "FTI-Campus",
        "zoneId": "zone-fti-001",
        "deviceIp": "",
        "channel24G": "",
        "channel5G": "",
        "airtime24G": 0,
        "airtime5G": 0,
        "capacity": 0,
        "capacity24G": 0,
        "capacity50G": 0,
        "noise24G": 0,
        "noise5G": 0,
        "uptimeInSec": 0,
        "meshRole": "",
    },
    {
        "deviceName": "FTIS-AP03-05",
        "deviceMac": "aa:bb:cc:11:55:05",
        "apMac": "aa:bb:cc:11:55:05",
        "serialNumber": "SN-AP005",
        "model": "R650",
        "firmwareVersion": "6.1.2.0.1455",
        "status": "Online",
        "numClients": 67,
        "numClients24G": 22,
        "numClients5G": 45,
        "location": "Gedung FTI Lantai 3",
        "zoneName": "FTI-Campus",
        "zoneId": "zone-fti-001",
        "deviceIp": "10.60.172.301",
        "channel24G": "6 (20MHz)",
        "channel5G": "40 (80MHz)",
        "airtime24G": 72,
        "airtime5G": 88,
        "capacity": 85,
        "capacity24G": 70,
        "capacity50G": 95,
        "noise24G": -82,
        "noise5G": -89,
        "uptimeInSec": 5184000,
        "meshRole": "Root",
    },
]

# ── vSZ Zone Fixtures ──────────────────────────────────────────────

SAMPLE_ZONES = [
    {
        "id": "zone-fti-001",
        "name": "FTI-Campus",
        "description": "Gedung FTI Selatan",
        "apCount": 5,
        "clientCount": 147,
        "status": "Active",
    },
    {
        "id": "zone-fti-002",
        "name": "FTI-Lab",
        "description": "Lab Komputer",
        "apCount": 2,
        "clientCount": 15,
        "status": "Active",
    },
]

# ── vSZ WLAN Fixtures ──────────────────────────────────────────────

SAMPLE_WLANS_ZONE1 = [
    {"ssid": "FTI-Secure", "name": "FTI Secure", "id": "wlan-001", "zoneId": "zone-fti-001"},
    {"ssid": "FTI-Guest", "name": "FTI Guest", "id": "wlan-002", "zoneId": "zone-fti-001"},
    {"ssid": "FTI-IoT", "name": "FTI IoT", "id": "wlan-003", "zoneId": "zone-fti-001"},
]

SAMPLE_WLAN_DETAIL = {
    "ssid": "FTI-Secure",
    "name": "FTI Secure",
    "id": "wlan-001",
    "zoneId": "zone-fti-001",
    "type": "standard",
    "encryption": {"method": "WPA2", "algorithm": "AES"},
    "authServiceOrProfile": {"name": "FTI-RADIUS"},
    "vlan": {"accessVlan": 100, "aaaVlanOverride": False},
    "advancedOptions": {"maxClientsPerRadio": 100, "clientIdleTimeoutSec": 120, "userSessionTimeout": 0},
    "schedule": {"type": "AlwaysOn"},
}

# ── vSZ Client Fixtures ────────────────────────────────────────────

SAMPLE_CLIENTS = {
    "totalCount": 3,
    "list": [
        {
            "hostname": "LAPTOP-USER01",
            "userName": "user01",
            "osType": "Windows 11",
            "deviceType": "Laptop",
            "ipAddress": "10.60.172.50",
            "ipv6Address": "",
            "clientMac": "cc:dd:ee:11:22:01",
            "ssid": "FTI-Secure",
            "bssid": "aa:bb:cc:11:22:01",
            "vlan": 100,
            "rssi": -55,
            "snr": 35,
            "channel": "36",
            "radioType": "5GHz",
            "txRatebps": 866700000,
            "authMethod": "WPA2-Enterprise",
            "encryptionMethod": "AES",
            "apName": "FTIS-AP01-01",
            "apMac": "aa:bb:cc:11:22:01",
            "apLocation": "Gedung FTI Lantai 1",
            "txBytes": 500000000,
            "rxBytes": 2000000000,
            "uplink": 500000000,
            "downlink": 2000000000,
            "medianTxMCSRate": 7,
            "medianRxMCSRate": 8,
            "sessionStartTime": 1720000000,
        },
        {
            "hostname": "PHONE-USER02",
            "userName": "user02",
            "osType": "Android 14",
            "deviceType": "Phone",
            "ipAddress": "10.60.172.51",
            "ipv6Address": "",
            "clientMac": "cc:dd:ee:11:22:02",
            "ssid": "FTI-Secure",
            "bssid": "aa:bb:cc:11:22:02",
            "vlan": 100,
            "rssi": -48,
            "snr": 42,
            "channel": "149",
            "radioType": "5GHz",
            "txRatebps": 433300000,
            "authMethod": "WPA2-Enterprise",
            "encryptionMethod": "AES",
            "apName": "FTIS-AP01-02",
            "apMac": "aa:bb:cc:11:22:02",
            "apLocation": "Gedung FTI Lantai 1",
            "txBytes": 100000000,
            "rxBytes": 500000000,
            "uplink": 100000000,
            "downlink": 500000000,
            "medianTxMCSRate": 5,
            "medianRxMCSRate": 6,
            "sessionStartTime": 1720000000,
        },
        {
            "hostname": "TABLET-USER03",
            "userName": "user03",
            "osType": "iPadOS 17",
            "deviceType": "Tablet",
            "ipAddress": "10.60.172.52",
            "ipv6Address": "",
            "clientMac": "cc:dd:ee:11:22:03",
            "ssid": "FTI-Guest",
            "bssid": "aa:bb:cc:11:33:03",
            "vlan": 200,
            "rssi": -62,
            "snr": 28,
            "channel": "52",
            "radioType": "5GHz",
            "txRatebps": 195000000,
            "authMethod": "WPA2-PSK",
            "encryptionMethod": "AES",
            "apName": "FTIS-AP02-03",
            "apMac": "aa:bb:cc:11:33:03",
            "apLocation": "Gedung FTI Lantai 2",
            "txBytes": 50000000,
            "rxBytes": 300000000,
            "uplink": 50000000,
            "downlink": 300000000,
            "medianTxMCSRate": 3,
            "medianRxMCSRate": 4,
            "sessionStartTime": 1720000000,
        },
    ],
}

# ── vSZ Alert Events ───────────────────────────────────────────────

SAMPLE_EVENTS = {
    "totalCount": 4,
    "firstIndex": 0,
    "hasMore": False,
    "list": [
        {
            "id": "evt-001",
            "insertionTime": 1722850000000,
            "eventType": "AP Down",
            "eventCode": 301,
            "severity": "Critical",
            "category": "AP",
            "activity": "AP FTIS-AP03-04@aa:bb:cc:11:44:04 is down",
        },
        {
            "id": "evt-002",
            "insertionTime": 1722840000000,
            "eventType": "Client Roam",
            "eventCode": 201,
            "severity": "Informational",
            "category": "Client",
            "activity": "Client user01@cc:dd:ee:11:22:01@10.60.172.50@ roamed from AP [FTIS-AP01-02@aa:bb:cc:11:22:02] to AP [FTIS-AP01-01@aa:bb:cc:11:22:01] on WLAN [FTI-Secure]",
        },
        {
            "id": "evt-003",
            "insertionTime": 1722830000000,
            "eventType": "Client Join",
            "eventCode": 200,
            "severity": "Informational",
            "category": "Client",
            "activity": "Client user02@cc:dd:ee:11:22:02@10.60.172.51@ joined AP [FTIS-AP01-02@aa:bb:cc:11:22:02] on WLAN [FTI-Secure]",
        },
        {
            "id": "evt-004",
            "insertionTime": 1722820000000,
            "eventType": "High Channel Utilization",
            "eventCode": 401,
            "severity": "Warning",
            "category": "AP",
            "activity": "AP FTIS-AP01-02 channel 5GHz utilization 88% exceeds threshold",
        },
    ],
}

# ── vSZ Rogue AP Fixtures ──────────────────────────────────────────

SAMPLE_ROGUE_CLIENTS = {
    "totalCount": 1,
    "rawDataTotalCount": 1,
    "hasMore": False,
    "list": [
        {
            "rogueMac": "ff:ee:dd:cc:bb:aa",
            "ssid": "FreeWiFi",
            "type": "INFRASTRUCTURE",
            "encryption": "Open",
            "channel": "6",
            "rogueAPMac": "ff:ee:dd:cc:bb:aa",
            "lastDetected": 1722850000000,
            "classification": "Rogue",
            "detectedByAP": [
                {"apName": "FTIS-AP01-01", "rssi": "-65", "zoneName": "FTI-Campus", "mainDetector": True},
                {"apName": "FTIS-AP01-02", "rssi": "-78", "zoneName": "FTI-Campus", "mainDetector": False},
            ],
        }
    ],
}

# ── vSZ Radio Stats (SCG apdetail) ─────────────────────────────────

SAMPLE_AP_RADIO_STATS = {
    "success": True,
    "data": {
        "radios": {
            "list": [
                {
                    "radioId": "0",
                    "channel": 6,
                    "channelWidth": 1,
                    "mode": "ng",
                    "txPower": "Full",
                    "chainmask": "0x0f",
                    "numOfAuthorizedClients": 8,
                    "noiseFloor": -88,
                    "total": 35,
                    "busy": 25,
                    "rx": 15,
                    "tx": 10,
                    "txBytes": 50000000000,
                    "rxBytes": 20000000000,
                    "retry": 120,
                    "drop": 5,
                    "backgroundScan": "enabled",
                    "autoCellSizing": "enabled",
                },
                {
                    "radioId": "1",
                    "channel": 36,
                    "channelWidth": 3,
                    "mode": "ac",
                    "txPower": "Full",
                    "chainmask": "0x0f",
                    "numOfAuthorizedClients": 15,
                    "noiseFloor": -92,
                    "total": 42,
                    "busy": 30,
                    "rx": 18,
                    "tx": 12,
                    "txBytes": 150000000000,
                    "rxBytes": 80000000000,
                    "retry": 80,
                    "drop": 2,
                    "backgroundScan": "enabled",
                    "autoCellSizing": "enabled",
                },
            ]
        }
    },
}

# ── ICX Device Fixtures ────────────────────────────────────────────

SAMPLE_ICX_DEVICES = [
    {"host": "10.60.172.1", "name": "FTIS-SA02-SVR03", "vendor": "ruckus", "role": "distribution", "location": "gedung fti selatan", "rack": "a"},
    {"host": "10.60.172.3", "name": "FTIS-SD02-SVR01", "vendor": "ruckus", "role": "access", "location": "gedung fti selatan", "rack": "a"},
]

SAMPLE_DEVICE_INFO = {
    "host": "10.60.172.1",
    "name": "FTIS-SA02-SVR03",
    "vendor": "ruckus",
    "model": "ICX 7550-48ZP",
    "serial": "FTI7550-001",
    "version": "09.0.10j",
    "uptime": "30 days, 5 hours",
}

SAMPLE_DEVICE_STATUS = {
    "host": "10.60.172.1",
    "cpu_pct": 15,
    "memory_pct": 42,
    "temperature_c": 45,
    "uptime": "30 days, 5 hours",
}

SAMPLE_INTERFACES = [
    {"port": "1/1/1", "status": "up", "speed": "10G", "type": "SFP+", "description": "Uplink to Core"},
    {"port": "1/1/2", "status": "down", "speed": "N/A", "type": "SFP+", "description": "Spare"},
    {"port": "1/2/1", "status": "up", "speed": "1G", "type": "RJ45", "description": "AP Port 01"},
]

SAMPLE_VLAN_SUMMARY = {
    "total_vlans": 20,
    "vlans": [
        {"id": 1, "name": "DEFAULT-VLAN", "ports": 48},
        {"id": 100, "name": "FTI-Users", "ports": 24},
        {"id": 200, "name": "FTI-Guest", "ports": 12},
    ],
}

SAMPLE_IP_ROUTES = {
    "total": 15,
    "routes": [
        {"destination": "0.0.0.0/0", "next_hop": "10.60.172.254", "type": "Static", "metric": 1},
        {"destination": "10.60.172.0/24", "next_hop": "direct", "type": "Connected", "metric": 0},
        {"destination": "10.60.173.0/24", "next_hop": "10.60.172.1", "type": "OSPF", "metric": 110},
    ],
}

SAMPLE_CONFIG = {
    "config": "hostname FTIS-SA02-SVR03\n!\ninterface ethernet 1/1/1\n port-name Uplink to Core\n!\nend",
    "sha256": "abc123def456",
    "size_bytes": 2048,
    "line_count": 45,
}
