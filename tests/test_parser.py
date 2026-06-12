"""Unit tests for the pure SSH-output parser.

Fixtures use anonymized example data (the parser is value-agnostic).
"""
import parser  # noqa: E402  (path injected by conftest)

SYS_BLOCK = """\
122749.42 183.28
0.00 0.00 0.00 1/55 3243
              total         used         free       shared      buffers
  Mem:        61156        41656        19500            0         3988
 Swap:            0            0            0
Total:        61156        41656        19500"""

IW_BLOCK = """\
ath0      IEEE 802.11ng  ESSID:"ExampleCPE"  Nickname:"CPE220"
          Mode:Master  Frequency:2.447 GHz  Access Point: AA:BB:CC:11:22:33
          Bit Rate:150 Mb/s   Tx-Power=30 dBm
          RTS thr=1000 B   Fragment thr:off
          Power Management:off
          Link Quality=94/94  Signal level=-96 dBm  Noise level=-95 dBm"""

STA_BLOCK = """\
ADDR               AID CHAN TXRATE RXRATE RSSI IDLE  TXSEQ  RXSEQ CAPS ACAPS ERP    STATE HTCAPS
aa:bb:cc:00:00:01    3    8  90M   6M   25    0   6051  65008 EPSs         0       1f WPS    RSN WME
aa:bb:cc:00:00:02    4    8  45M   6M   31    0   6216  62368 EPSs         0       1f WPS    RSN WME
aa:bb:cc:00:00:03    5    8  43M  39M   18    0   1893   1648 EPSs         0        f AQ     RSN WME
aa:bb:cc:00:00:04    6    8  58M  18M   18    0   2432   7792 EPSs         0        f P      RSN WME
aa:bb:cc:00:00:05    7    8  72M  65M   43    0  37071  37984 EPSs         0        f AQ     RSN WME
aa:bb:cc:00:00:06    9    8  72M  72M   41    0   5716  52448 EPSs         0        f AQ     RSN WME
aa:bb:cc:00:00:07   10    8  72M  65M   29    0  59870  36816 EPSs         0        f AQ     RSN WME
aa:bb:cc:00:00:08   11    8  72M  72M   33    0  24177  52864 EPSs         0        f AQ     RSN WME
aa:bb:cc:00:00:09   12    8  11M  65M   23    0  44221  50512 EPSs         0        f AQ     RSN WME
aa:bb:cc:00:00:0a   15    8 150M   6M   32    0  44809  25328 EPSs         0       1f WPS    RSN WME
aa:bb:cc:00:00:0b   16    8  90M   6M   20    0  44209  19328 EPSs         0       1f WPS    RSN WME
aa:bb:cc:00:00:0c   14    8 120M   6M   21    0  25275  30832 EPSs         0       1f WPS    RSN WME
aa:bb:cc:00:00:0d    1    8  60M   6M   17   15   2487  33760 EPSs         0       1f WPS    RSN WME
aa:bb:cc:00:00:0e    2    8  45M   6M   23    0    101  12512 EPSs         0        f WPS    RSN WME
aa:bb:cc:00:00:0f    8    8  21M  19M    9    0   1801   3200 EPSs         0        f AQ     RSN WME"""

STA_EMPTY = "ADDR               AID CHAN TXRATE RXRATE RSSI IDLE  TXSEQ  RXSEQ CAPS"

STA_CPE510 = """\
ADDR               AID CHAN RATE RSSI IDLE  TXSEQ  RXSEQ CAPS ACAPS ERP    STATE HTCAPS
aa:bb:cc:00:00:20    1   48 270M   29    0   5604  39200 EcPs         0      80b AWPS   RSN WME"""

NET_BLOCK = """\
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 5601868   80239    0    0    0     0          0         0  5601868   80239    0    0    0     0       0          0
  eth0:276565113 2476865    1    1    0     0          0    242124 1881625977 2602548    0    0    0     0       0          0
  ath0:2117389018 8505283    3    3    0     0          0         0 1046949824 8116054    0    8    0     0       0          0"""

IF_BLOCK = """\
ath0      Link encap:Ethernet  HWaddr AA:BB:CC:11:22:33
          UP BROADCAST RUNNING MULTICAST  MTU:2290  Metric:1
br0       Link encap:Ethernet  HWaddr AA:BB:CC:11:22:33
          inet addr:192.168.1.2  Bcast:192.168.1.255  Mask:255.255.255.0"""

IWCONFIG_ALL = """\
ath0      IEEE 802.11ng  ESSID:"ExampleCPE"  Nickname:"CPE220"
          Mode:Master  Frequency:2.447 GHz
lo        no wireless extensions.
eth0      no wireless extensions.
br0       no wireless extensions."""


def test_parse_sys():
    out = parser.parse_sys(SYS_BLOCK)
    assert out[parser.KEY_UPTIME] == 122749.42
    assert out[parser.KEY_LOAD_1] == 0.0
    assert out[parser.KEY_LOAD_5] == 0.0
    assert out[parser.KEY_LOAD_15] == 0.0
    assert out[parser.KEY_MEM_TOTAL] == 61156
    assert out[parser.KEY_MEM_USED] == 41656
    assert out[parser.KEY_MEM_PCT] == 68.1


def test_parse_iwconfig():
    out = parser.parse_iwconfig(IW_BLOCK)
    assert out[parser.KEY_ESSID] == "ExampleCPE"
    assert out[parser.KEY_MODE] == "Master"
    assert out[parser.KEY_FREQ] == 2.447
    assert out[parser.KEY_CHANNEL] == 8
    assert out[parser.KEY_BITRATE] == 150.0
    assert out[parser.KEY_TXPOWER] == 30
    assert out[parser.KEY_SIGNAL] == -96
    assert out[parser.KEY_NOISE] == -95
    assert out[parser.KEY_QUALITY] == 100.0


def test_parse_stations_full():
    out = parser.parse_stations(STA_BLOCK)
    assert out[parser.KEY_CLIENTS] == 15
    assert out[parser.KEY_RSSI_MIN] == 9
    assert out[parser.KEY_RSSI_AVG] == 25.5


def test_parse_stations_cpe510_rssi_column():
    # Older firmware: single RATE column -> RSSI is at index 4, not 5.
    out = parser.parse_stations(STA_CPE510)
    assert out[parser.KEY_CLIENTS] == 1
    assert out[parser.KEY_RSSI_MIN] == 29
    assert out[parser.KEY_RSSI_AVG] == 29.0


def test_parse_stations_empty():
    out = parser.parse_stations(STA_EMPTY)
    assert out[parser.KEY_CLIENTS] == 0
    assert parser.KEY_RSSI_AVG not in out
    assert parser.KEY_RSSI_MIN not in out


def test_parse_proc_net_dev():
    out = parser.parse_proc_net_dev(NET_BLOCK)
    assert out["eth0"]["rx_bytes"] == 276565113
    assert out["eth0"]["tx_bytes"] == 1881625977
    assert out["ath0"]["rx_bytes"] == 2117389018
    assert out["ath0"]["tx_bytes"] == 1046949824
    assert "lo" in out


def test_parse_mac():
    assert parser.parse_mac(IF_BLOCK) == "AA:BB:CC:11:22:33"


def test_detect_wifi_if():
    assert parser.detect_wifi_if(IWCONFIG_ALL) == "ath0"


def test_pharos_login_encoded():
    # Frozen vector: user + ":" + MD5(MD5(pw).upper() + ":" + nonce).upper()
    assert (
        parser.pharos_login_encoded("admin", "examplepass", "NONCE123")
        == "admin:C9C5B8F3787A9D297A0A08F8D891B029"
    )


def test_compute_throughput():
    prev = {"ath0": {"rx_bytes": 1000, "tx_bytes": 2000}}
    cur = {"ath0": {"rx_bytes": 1000 + 1_250_000, "tx_bytes": 2000 + 625_000}}
    out = parser.compute_throughput(prev, cur, 10.0)
    assert out["ath0"]["rx_mbps"] == 1.0
    assert out["ath0"]["tx_mbps"] == 0.5


def test_compute_throughput_counter_reset():
    prev = {"ath0": {"rx_bytes": 5000, "tx_bytes": 5000}}
    cur = {"ath0": {"rx_bytes": 10, "tx_bytes": 10}}  # rebooted, counter reset
    out = parser.compute_throughput(prev, cur, 10.0)
    assert "ath0" not in out


def test_parse_all_integration():
    raw = (
        "@@SYS\n" + SYS_BLOCK + "\n"
        "@@IW\n" + IW_BLOCK + "\n"
        "@@STA\n" + STA_BLOCK + "\n"
        "@@NET\n" + NET_BLOCK + "\n"
        "@@IF\n" + IF_BLOCK
    )
    data = parser.parse_all(raw, "ath0")
    assert data[parser.KEY_UPTIME] == 122749.42
    assert data[parser.KEY_MODE] == "Master"
    assert data[parser.KEY_CLIENTS] == 15
    assert data[parser.KEY_MAC] == "AA:BB:CC:11:22:33"
    assert data[parser.KEY_IFACES]["eth0"]["tx_bytes"] == 1881625977
