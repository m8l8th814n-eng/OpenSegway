#!/usr/bin/env python3

"""Patches an apktool-decoded BleTool 3.9.23 directory."""

import argparse
import glob
import os
import re

DEFAULT_DEV_KEY = "4BKNwi77"
DEFAULT_DEV_TYPE = "60"
DEFAULT_UPD_KEY = "C7qn"
DEFAULT_DEV_VER = "1.0"


DEV_KEY = DEFAULT_DEV_KEY
DEV_TYPE = DEFAULT_DEV_TYPE
UPD_KEY = DEFAULT_UPD_KEY
DEV_VER = DEFAULT_DEV_VER

ROOT = "decoded_patched"
SM = os.path.join(ROOT, "smali/com/omni/production/check")


BATCH_KEY = "Vgz7"

ROWS = [
    ("NB key 4BKNwi77", "scooter_nb", "autounlock", "4BKNwi77"),
    ("NB key 4BKNwi77 manual", "scooter_nb", "1.0", "4BKNwi77"),
    ("NB key yOTmK50z", "scooter_nb", "autounlock", "yOTmK50z"),
    ("NB key OmniW4GX", "scooter_nb", "autounlock", "OmniW4GX"),
    ("NB key Vgz7", "scooter_nb", "autounlock", "Vgz7"),
    ("NB key C7qn", "scooter_nb", "autounlock", "C7qn"),
    ("NB online 4BKNwi77", "scooter_nb", "srv", "4BKNwi77"),
    ("NB 4BKNwi77 8A", "scooter_nb_upgrade", "autounlock", "4BKNwi77"),
    ("NB yOTmK50z 8A", "scooter_nb_upgrade", "autounlock", "yOTmK50z"),
    ("NB OmniW4GX 8A", "scooter_nb_upgrade", "autounlock", "OmniW4GX"),
    ("NB Vgz7 8A", "scooter_nb_upgrade", "autounlock", "Vgz7"),
    ("NB C7qn 8A", "scooter_nb_upgrade", "autounlock", "C7qn"),
    ("U 4BKNwi77", "u_lock", "autounlock", "4BKNwi77"),
    ("U yOTmK50z", "u_lock", "autounlock", "yOTmK50z"),
    ("U OmniW4GX", "u_lock", "autounlock", "OmniW4GX"),
    ("U Vgz7", "u_lock", "autounlock", "Vgz7"),
    ("U C7qn", "u_lock", "autounlock", "C7qn"),
    ("Scooter1", "scooter_nb", "1.0", "4BKNwi77"),
    ("Scooter XM", "scooter_xm"),
    ("Scooter NB", "scooter_nb"),
    ("NB Show", "scooter_nb_show"),
    ("NB Cable tool", "scooter_nb_tool1"),
    ("Scooter NB upgr", "scooter_nb_upgrade"),
    ("U-Lock", "u_lock"),
    ("Personal lock", "personal_lock"),
    ("Bike lock 3-in-1", "bike_gprs_ble"),
    ("Bike lock BT", "bike_ble"),
    ("Cable/Bloom", "cable_lock"),
    ("Bloom HJ", "bloom_lock_hj"),
    ("Battery lock HJ", "battery_lock_hj"),
    ("Key box", "keybox"),
    ("Carport", "park_lock"),
    ("Carport Plus", "park_lock_plus"),
    ("Carport Plus 485", "park_lock_485"),
    ("Transmission", "transmission"),
    ("Accompanying bed", "Accompanying_bed_lock"),
    ("BF meter", "meter_bf"),
    ("BF meter BLE", "BF_IOT_BLE"),
    ("Geomagnetic", "omni_dici"),
]


def _row(i, name, product_key, ver=None, key=None):

    return (
        '{"id":"%04d","name":"%s","bleKey":"%s","iotCode":"%s","upgradeKey":"%s",'
        '"bleVersion":"%s","carFactoryName":"","empowerNumber":"","productKey":"%s",'
        '"productionType":"","code":"","note":""}'
        % (i, name, key or DEV_KEY, DEV_TYPE, UPD_KEY, ver or DEV_VER, product_key)
    )


KEYS = [
    "DEVICE_KEY",
    "DEVICE_TYPE",
    "CUSTOMER_ID",
    "CUSTOMER_NAME",
    "UPDATE_KEY",
    "BLE_VERSION",
    "FIRMWARE_VERSION",
    "FIRMWARE_NAME",
    "FIRMWARE_NODE",
    "LOCK_FILE",
    "QR_FILEPATH",
    "QRCODE_START",
    "QRCODE_END",
    "QRCODE_LENGTH",
]


SDCARD_DIR = "/sdcard/omni"
QR_FILENAME = "omni_qr.csv"
FW_FILENAME = "omni_fw.bin"


def build_config():

    global CUSTOMER_CONFIG, PAYLOAD, VALS
    CUSTOMER_CONFIG = (
        "["
        + ",".join(
            _row(
                i + 1,
                r[0],
                r[1],
                r[2] if len(r) > 2 else None,
                r[3] if len(r) > 3 else None,
            )
            for i, r in enumerate(ROWS)
        )
        + "]"
    )
    PAYLOAD = (
        "{"
        + ",".join(
            [
                '"token":"offline"',
                '"expiredTimeStamp":4102444800000',
                '"user":{"id":1,"nickname":"offline","role":5,"lang":"sv"}',
                '"customerConfig":%s' % CUSTOMER_CONFIG,
                '"lockFile":[]',
                '"qrFile":[]',
            ]
        )
        + "}"
    )

    VALS = [
        DEV_KEY,
        DEV_TYPE,
        "0001",
        "OFFLINE",
        UPD_KEY,
        DEV_VER,
        "1.0",
        FW_FILENAME,
        "offline",
        FW_FILENAME,
        QR_FILENAME,
        "",
        "",
        "",
    ]


build_config()


OLD_BASE = "https://scootercracking.duckdns.org/omni-api/"
NEW_BASE = "http://brainfisting:18080/"


def q(v):
    return '"%s"' % v.replace("\\", "\\\\").replace('"', '\\"')


def inject_block(done):

    L = []

    def add(x=""):
        L.append(x)

    def put_str(key, val):
        add("    const-string v1, %s" % q(val))
        add()
        add('    const-string v2, "%s"' % key)
        add()
        add(
            "    invoke-virtual {v0, v2, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->putSP(Ljava/lang/String;Ljava/lang/String;)V"
        )
        add()

    add(
        "    invoke-static {}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->getSp()Lcom/omni/production/check/utils/SharedPreferencesUtil;"
    )
    add()
    add("    move-result-object v0")
    add()
    add('    const-string v1, "LOGIN_JSON"')
    add()
    add(
        "    invoke-virtual {v0, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->getSP(Ljava/lang/String;)Ljava/lang/String;"
    )
    add()
    add("    move-result-object v1")
    add()
    add(
        "    invoke-static {v1}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z"
    )
    add()
    add("    move-result v1")
    add()
    add("    if-eqz v1, %s" % done)
    add()
    put_str("LOGIN_JSON", PAYLOAD)
    put_str("TOKEN", "offline")
    add("    const-wide v1, 0x3ddb8a00000L")
    add()
    add("    invoke-static {v1, v2}, Ljava/lang/Long;->valueOf(J)Ljava/lang/Long;")
    add()
    add("    move-result-object v1")
    add()
    add('    const-string v2, "LOGIN_DATE"')
    add()
    add(
        "    invoke-virtual {v0, v2, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->putSP(Ljava/lang/String;Ljava/lang/Long;)V"
    )
    add()
    for k, v in zip(KEYS, VALS):
        put_str(k, v)
    add("    %s" % done)
    add()
    return "\n".join(L)


def assert_fresh(root):

    marker = os.path.join(
        root, "smali/com/omni/production/check/activity/HomeActivity.smali"
    )
    if os.path.exists(marker) and ":seed_done" in open(marker, encoding="utf-8").read():
        raise SystemExit(
            "DIRECTORY IS ALREADY PATCHED (%s) - make a fresh copy of decoded/" % root
        )


def write(path, t):
    open(path, "w", encoding="utf-8").write(t)


def patch_app(path):
    t0 = open(path, encoding="utf-8").read()
    anchor = (
        "   invoke-static {p0}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->init"
        "(Landroid/content/Context;)V\n\n"
    )
    if anchor not in t0:
        raise SystemExit("TApplication: could not find SP init")
    t = t0.replace(
        ".method public onCreate()V\n    .locals 2\n",
        ".method public onCreate()V\n    .locals 3\n",
    )
    t = t.replace(anchor, anchor + inject_block(":app_done"))
    assert t != t0
    write(path, t)
    print("patched:", path)


def patch_welcome(path):
    t0 = open(path, encoding="utf-8").read()
    n = t0.count("const-class v1, Lcom/omni/production/check/activity/LoginActivity;")
    if n < 1:
        raise SystemExit("WelcomeActivity: found no LoginActivity references")
    t = t0.replace(
        "const-class v1, Lcom/omni/production/check/activity/LoginActivity;",
        "const-class v1, Lcom/omni/production/check/activity/HomeActivity;",
    )
    if "if-lez v0, :cond_0" not in t:
        raise SystemExit("WelcomeActivity: could not find the expired-token branch")
    t = t.replace("if-lez v0, :cond_0", "goto :cond_0")
    write(path, t)
    print(
        "patched:",
        path,
        "(%d LoginActivity -> HomeActivity, expired-token branch removed)" % n,
    )


def patch_account(path):

    t0 = open(path, encoding="utf-8").read()
    if (
        t0.count("const-class v1, Lcom/omni/production/check/activity/LoginActivity;")
        != 1
    ):
        raise SystemExit("AccountUtils: expected 1 LoginActivity reference")
    t = t0.replace(
        ".method public static logout(Landroid/app/Activity;)V\n    .locals 2\n",
        ".method public static logout(Landroid/app/Activity;)V\n    .locals 5\n",
    )
    t = t.replace(
        "const-class v1, Lcom/omni/production/check/activity/LoginActivity;",
        "const-class v1, Lcom/omni/production/check/activity/HomeActivity;",
    )
    marker = (
        "    invoke-virtual {v0, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->removeSP(Ljava/lang/String;)V\n\n"
        "    .line 34\n"
    )
    if marker not in t:
        raise SystemExit("AccountUtils: could not find the end of the removeSP chain")
    t = t.replace(
        marker,
        "    invoke-virtual {v0, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->removeSP(Ljava/lang/String;)V\n\n"
        + inject_block(":logout_done")
        + "\n    .line 34\n",
    )
    assert t != t0
    write(path, t)
    print("patched:", path)


def patch_home(path):
    t0 = open(path, encoding="utf-8").read()
    m = re.search(r"\.method private refresh\(\)V\n    \.locals \d+\n\n", t0)
    if not m:
        raise SystemExit("HomeActivity: could not find refresh()")
    t = t0.replace(
        m.group(0),
        ".method private refresh()V\n    .locals 4\n\n    return-void\n.end method\n\n"
        ".method private refresh_orig()V\n    .locals 4\n\n",
    )
    assert t != t0
    write(path, t)
    print("patched:", path, "(refresh() -> no-op, original preserved as refresh_orig)")


def patch_base_url(path):

    if not NEW_BASE:
        print("skipping base URL (NEW_BASE=None):", path)
        return
    t0 = open(path, encoding="utf-8").read()
    n = t0.count(OLD_BASE)
    if n < 1:
        raise SystemExit("%s: could not find %s" % (path, OLD_BASE))
    write(path, t0.replace(OLD_BASE, NEW_BASE))
    print("patched:", path, "(%d x %s -> %s)" % (n, OLD_BASE, NEW_BASE))


def patch_initdata(path):

    t0 = open(path, encoding="utf-8").read()
    old = (
        ".method private initData()V\n    .locals 0\n\n"
        "    .line 304\n"
        "    invoke-direct {p0}, Lcom/omni/production/check/activity/HomeActivity;->refresh()V\n\n"
        "    return-void\n.end method\n"
    )
    if old not in t0:
        raise SystemExit("HomeActivity: initData() does not match")
    seed = (
        "    invoke-static {}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->getSp()Lcom/omni/production/check/utils/SharedPreferencesUtil;\n\n"
        "    move-result-object v0\n\n"
        '    const-string v1, "LOGIN_JSON"\n\n'
        "    invoke-virtual {v0, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->getSP(Ljava/lang/String;)Ljava/lang/String;\n\n"
        "    move-result-object v0\n\n"
        "    invoke-static {v0}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z\n\n"
        "    move-result v1\n\n"
        "    if-nez v1, :seed_done\n\n"
        "    new-instance v1, Lcom/google/gson/Gson;\n\n"
        "    invoke-direct {v1}, Lcom/google/gson/Gson;-><init>()V\n\n"
        "    const-class v2, Lcom/omni/production/check/bean/LoginBean;\n\n"
        "    invoke-virtual {v1, v0, v2}, Lcom/google/gson/Gson;->fromJson(Ljava/lang/String;Ljava/lang/Class;)Ljava/lang/Object;\n\n"
        "    move-result-object v0\n\n"
        "    check-cast v0, Lcom/omni/production/check/bean/LoginBean;\n\n"
        "    invoke-static {p0, v0}, Lcom/omni/production/check/activity/HomeActivity;->access$200(Lcom/omni/production/check/activity/HomeActivity;Lcom/omni/production/check/bean/LoginBean;)V\n\n"
        "    :seed_done\n\n"
    )
    new = (
        ".method private initData()V\n    .locals 3\n\n"
        "    .line 304\n"
        "    invoke-direct {p0}, Lcom/omni/production/check/activity/HomeActivity;->refresh()V\n\n"
        + seed
        + "    return-void\n.end method\n"
    )
    write(path, t0.replace(old, new))
    print("patched:", path, "(initData seeds the list from LOGIN_JSON)")


def patch_logpath(path):

    t0 = open(path, encoding="utf-8").read()
    if "getExternalStoragePublicDirectory" in t0:
        print("   log path is already public, skipping")
        return
    old = (
        "    invoke-virtual {v0, v1}, Landroid/content/Context;"
        "->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;"
    )
    if old not in t0:
        raise SystemExit("could not find the getExternalFilesDir call")
    new = (
        "    invoke-static {v1}, Landroid/os/Environment;"
        "->getExternalStoragePublicDirectory(Ljava/lang/String;)Ljava/io/File;"
    )
    write(path, t0.replace(old, new, 1))
    print("patched:", path, "(log file -> /sdcard/Download, survives uninstall)")


def patch_manifest_storage(path):

    t0 = open(path, encoding="utf-8").read()
    if "MANAGE_EXTERNAL_STORAGE" in t0:
        print("   MANAGE_EXTERNAL_STORAGE already exists, skipping")
        return
    old = (
        "    <uses-permission android:name="
        '"android.permission.WRITE_EXTERNAL_STORAGE"/>'
    )
    if old not in t0:
        raise SystemExit("could not find the WRITE_EXTERNAL_STORAGE line in the manifest")
    new = (
        old + "\n" + "    <uses-permission android:name="
        '"android.permission.MANAGE_EXTERNAL_STORAGE"/>'
    )
    write(path, t0.replace(old, new, 1))
    print("patched:", path, "(+MANAGE_EXTERNAL_STORAGE)")


def patch_scandialog(path):

    t0 = open(path, encoding="utf-8").read()
    old = (
        "    if-eqz p3, :cond_2\n\n"
        "    if-eqz v0, :cond_2\n\n"
        "    .line 197\n"
        "    iget-object v1, p0, Lcom/omni/production/check/dialog/ScanDialog;->filterName:Ljava/lang/String;\n\n"
        "    invoke-static {v1}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z\n\n"
        "    move-result v1\n\n"
        "    if-nez v1, :cond_0\n\n"
        "    iget-object v1, p0, Lcom/omni/production/check/dialog/ScanDialog;->filterName:Ljava/lang/String;\n\n"
        "    invoke-virtual {v1, p3}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z\n\n"
        "    move-result p3\n\n"
        "    if-eqz p3, :cond_2\n\n"
        "    :cond_0\n"
        "    iget p3, p0, Lcom/omni/production/check/dialog/ScanDialog;->filterRSSI:I\n\n"
        "    if-ge p2, p3, :cond_1\n\n"
        "    goto :goto_0\n\n"
        "    .line 200\n"
        "    :cond_1\n"
    )
    new = (
        "    if-eqz v0, :cond_2\n\n"
        "    if-nez p3, :cond_9\n\n"
        "    move-object p3, v0\n\n"
        "    :cond_9\n"
        "    :cond_1\n"
    )
    if old not in t0:
        raise SystemExit("ScanDialog: could not find the filter block in onLeScan")
    t = t0.replace(old, new)
    k = t.count('    const-string v1, "rssi_progress"\n\n    const/16 v2, 0x1e\n')
    if k != 1:
        raise SystemExit("ScanDialog: expected 1 RSSI default, found %d" % k)
    t = t.replace(
        '    const-string v1, "rssi_progress"\n\n    const/16 v2, 0x1e\n',
        '    const-string v1, "rssi_progress"\n\n    const/16 v2, 0x3c\n',
    )
    write(path, t)
    print(
        "patched:",
        path,
        "(shows everything: no name/RSSI filter, MAC fallback, RSSI floor -100)",
    )


def patch_scandialog_timeout(path):

    t0 = open(path, encoding="utf-8").read()
    if t0.count("    const-wide/16 v2, 0x2710\n") != 1:
        raise SystemExit("ScanDialog$2: could not find the 10 s timeout")
    t = t0.replace("    const-wide/16 v2, 0x2710\n", "    const-wide v2, 0x493e0L\n")
    write(path, t)
    print("patched:", path, "(scan time 10 s -> 5 min)")


def patch_fwinfo_filter(path):

    t0 = open(path, encoding="utf-8").read()
    old = '    const-string v1, "Scooter|Segway IoT"\n'
    if old not in t0:
        raise SystemExit("FwInfoActivity: could not find the filter string")
    write(path, t0.replace(old, '    const-string v1, ""\n'))
    print("patched:", path, '(filterName "Scooter|Segway IoT" -> "" (no name filter))')


def patch_ulock_nodownload(path):

    t0 = open(path, encoding="utf-8").read()
    old = (
        "    invoke-direct {p0}, Lcom/omni/production/check/activity/ULockTestActivity;->download()V\n\n"
        "    return-void\n.end method\n"
    )
    if old not in t0:
        raise SystemExit("ULockTestActivity: could not find the download() call in initData")
    new = (
        "    iget-object v0, p0, Lcom/omni/production/check/activity/ULockTestActivity;->tvFile:Landroid/widget/TextView;\n\n"
        "    new-instance v1, Ljava/lang/StringBuilder;\n\n"
        "    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V\n\n"
        '    const-string v2, "qr_file: "\n\n'
        "    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n"
        '    const-string v2, "not_downloaded (offline)"\n\n'
        "    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n"
        "    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;\n\n"
        "    move-result-object v1\n\n"
        "    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V\n\n"
        "    return-void\n.end method\n"
    )

    t = t0.replace(
        ".method private initData()V\n    .locals 2\n",
        ".method private initData()V\n    .locals 3\n",
    )
    t = t.replace(old, new)
    if t == t0:
        raise SystemExit("ULockTestActivity: no change")
    write(path, t)
    print("patched:", path, "(no automatic download in initData)")


def patch_ulock_connect_button(path):

    t0 = open(path, encoding="utf-8").read()
    m = re.search(r"\.method private searchQrCode\(\)V\n    \.locals \d+\n", t0)
    if not m:
        raise SystemExit("ULockTestActivity: could not find searchQrCode()")

    i = m.start()
    j = t0.find("\n.end method", t0.find(".line 1050", i)) + len("\n.end method\n")
    body = t0[i:j]
    if "getMacNumMap" not in body:
        raise SystemExit("ULockTestActivity: searchQrCode does not look as expected")
    new = (
        ".method private searchQrCode()V\n"
        "    .locals 2\n\n"
        "    iget-object v0, p0, Lcom/omni/production/check/activity/ULockTestActivity;->etQrCode:Landroid/widget/EditText;\n\n"
        "    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;\n\n"
        "    move-result-object v0\n\n"
        "    invoke-virtual {v0}, Ljava/lang/Object;->toString()Ljava/lang/String;\n\n"
        "    move-result-object v0\n\n"
        "    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;\n\n"
        "    move-result-object v0\n\n"
        "    invoke-static {v0}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z\n\n"
        "    move-result v1\n\n"
        "    if-nez v1, :ulock_connect\n\n"
        "    iget-object v1, p0, Lcom/omni/production/check/activity/ULockTestActivity;->etScanMac:Landroid/widget/EditText;\n\n"
        "    invoke-virtual {v1, v0}, Landroid/widget/EditText;->setText(Ljava/lang/CharSequence;)V\n\n"
        "    :ulock_connect\n"
        "    iget-object v0, p0, Lcom/omni/production/check/activity/ULockTestActivity;->etScanMac:Landroid/widget/EditText;\n\n"
        "    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;\n\n"
        "    move-result-object v0\n\n"
        "    invoke-virtual {v0}, Ljava/lang/Object;->toString()Ljava/lang/String;\n\n"
        "    move-result-object v0\n\n"
        "    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;\n\n"
        "    move-result-object v0\n\n"
        "    invoke-static {v0}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z\n\n"
        "    move-result v1\n\n"
        "    if-nez v1, :ulock_done\n\n"
        "    iget-object v1, p0, Lcom/omni/production/check/activity/ULockTestActivity;->tvMac:Landroid/widget/TextView;\n\n"
        "    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V\n\n"
        "    iget-object v1, p0, Lcom/omni/production/check/activity/ULockTestActivity;->bikeServiceProxy:Lcom/omni/ble/library/proxy/BLEBikeServiceProxy;\n\n"
        "    invoke-virtual {v1, v0}, Lcom/omni/ble/library/proxy/BLEBikeServiceProxy;->connect(Ljava/lang/String;)V\n\n"
        "    iget-object v0, p0, Lcom/omni/production/check/activity/ULockTestActivity;->dialogUtils:Lcom/omni/production/check/utils/DialogUtils;\n\n"
        "    invoke-virtual {v0}, Lcom/omni/production/check/utils/DialogUtils;->showLoadDialog()V\n\n"
        "    :ulock_done\n"
        "    return-void\n.end method\n"
    )
    write(path, t0[:i] + new + t0[j:])
    print("patched:", path, "(searchQrCode connects using MAC, no server)")


def patch_download_calls(act_dir):
    n = 0
    for f in sorted(glob.glob(os.path.join(act_dir, "*.smali"))):
        base = os.path.basename(f)
        if "$" in base:
            continue
        t0 = open(f, encoding="utf-8").read()
        m = re.search(r"\.method private initData\(\)V\n(.*?)\n\.end method", t0, re.S)
        if not m:
            continue
        cls = re.search(r"\.class[^\n]* (L[^;]+;)", t0).group(1)
        call = "    invoke-direct {p0}, %s->download()V\n\n" % cls
        if call not in m.group(1):
            continue

        i = m.group(1).find(call)
        after = m.group(1)[i + len(call) :].strip()
        if after not in ("return-void",):
            print("   SKIPPING (not last):", base)
            continue
        write(f, t0.replace(call, ""))
        n += 1
    print("patched: %d activities (automatic download removed)" % n)


def patch_builtin_keys(sm):

    repl = []
    if DEV_KEY != DEFAULT_DEV_KEY:
        repl.append((DEFAULT_DEV_KEY, DEV_KEY))
    if UPD_KEY != DEFAULT_UPD_KEY:
        repl.append((DEFAULT_UPD_KEY, UPD_KEY))
    if not repl:
        print("built-in keys: defaults (no sync needed)")
        return
    n = 0
    for f in glob.glob(os.path.join(sm, "**/*.smali"), recursive=True):
        t0 = open(f, encoding="utf-8").read()
        t = t0
        for old, new in repl:
            t = t.replace('"%s"' % old, '"%s"' % new)
        if t != t0:
            write(f, t)
            n += 1
    for old, new in repl:
        print("built-in key: %s -> %s" % (old, new))
    print("   synchronized %d file(s)" % n)


def patch_oss_getfile(path):

    t0 = open(path, encoding="utf-8").read()
    old = (
        "    invoke-static {}, Lcom/omni/production/check/TApplication;->getAppContext()Landroid/content/Context;\n\n"
        "    move-result-object v0\n\n"
        "    sget-object v1, Landroid/os/Environment;->DIRECTORY_DOWNLOADS:Ljava/lang/String;\n\n"
        "    invoke-virtual {v0, v1}, Landroid/content/Context;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;\n\n"
        "    move-result-object v0\n"
    )
    new = (
        "    new-instance v0, Ljava/io/File;\n\n"
        '    const-string v1, "%s"\n\n'
        "    invoke-direct {v0, v1}, Ljava/io/File;-><init>(Ljava/lang/String;)V\n"
        % SDCARD_DIR
    )
    if old not in t0:
        raise SystemExit("OssUtils: could not find the getExternalFilesDir chain in getFile()")
    write(path, t0.replace(old, new))
    print("patched:", path, "(getFile -> %s)" % SDCARD_DIR)


def patch_oss_download_local(path):
    t0 = open(path, encoding="utf-8").read()
    m = re.search(
        r"\.method public downloadFile\(Lcom/omni/production/check/utils/"
        r"OssUtils\$OnOssFileDownloadListener;\)V\n.*?\n\.end method",
        t0,
        re.S,
    )
    if not m:
        raise SystemExit("OssUtils: could not find downloadFile()")
    new = open(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "downloadFile_local.smali",
        ),
        encoding="utf-8",
    ).read()
    write(path, t0[: m.start()] + new.rstrip("\n") + t0[m.end() :])
    print("patched:", path, "(downloadFile -> local file only, no network)")


def patch_versioninfo_skip(path):

    t0 = open(path, encoding="utf-8").read()
    m = re.search(
        r"\.method public static getVersionInfo\(Landroid/app/Activity;"
        r"Ljava/lang/String;Lcom/omni/production/check/utils/"
        r"UpgradeUtils\$IsUpgradeListener;\)V\n.*?\n\.end method",
        t0,
        re.S,
    )
    if not m:
        raise SystemExit("UpgradeUtils: could not find getVersionInfo()")
    new = open(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "getVersionInfo_skip.smali",
        ),
        encoding="utf-8",
    ).read()
    write(path, t0[: m.start()] + new.rstrip("\n") + t0[m.end() :])
    print("patched:", path, "(getVersionInfo -> no(), opens the tool directly)")


def patch_hasolddata(path):

    t0 = open(path, encoding="utf-8").read()
    old = "    or-int/lit8 p1, p1, 0x40\n\n" "    if-ne p1, v1, :cond_2\n"
    new = "    and-int/lit8 p1, p1, 0x40\n\n" "    if-eqz p1, :cond_2\n"
    if t0.count(old) != 1:
        raise SystemExit(
            "ScooterLockInfoResult: could not find the hasOldData block (or found multiple matches)"
        )
    write(path, t0.replace(old, new, 1))
    print("patched:", path, "(hasOldData: (status|0x40)==1 -> (status&0x40)!=0)")


def verify_polarity(root, online_login=False):

    if online_login:
        print("polarity check: not applicable (online login, seeding disabled)")
        return
    checks = [
        (
            "smali/com/omni/production/check/TApplication.smali",
            "if-eqz v1, :app_done",
            "write the session when it is EMPTY",
        ),
        (
            "smali/com/omni/production/check/utils/AccountUtils.smali",
            "if-eqz v1, :logout_done",
            "restore the session when it is EMPTY",
        ),
        (
            "smali/com/omni/production/check/activity/HomeActivity.smali",
            "if-nez v1, :seed_done",
            "parse when it is NOT empty",
        ),
    ]
    for rel, want, why in checks:
        path = os.path.join(root, rel)
        body = open(path, encoding="utf-8").read()
        if want in body:
            continue
        other = (
            want.replace("if-eqz", "if-nez")
            if want.startswith("if-eqz")
            else want.replace("if-nez", "if-eqz")
        )
        extra = "  (found the opposite: %s)" % other if other in body else ""
        raise SystemExit(
            "POLARITY CHECK FAILED in %s\n"
            "  missing: %s  (%s)%s" % (rel, want, why, extra)
        )
    print(
        "polarity check: OK (TApplication/AccountUtils if-eqz, HomeActivity if-nez)"
    )


def patch_noserver_log(act_path):

    t0 = open(act_path, encoding="utf-8").read()
    if ":ns_ok" in t0:
        print("   nosrv guard already exists, skipping")
        return
    old = ".method protected onBLEScooterLogData([B)V\n    .locals 3\n"
    if old not in t0:
        raise SystemExit("could not find the onBLEScooterLogData header")
    guard = (
        ".method protected onBLEScooterLogData([B)V\n    .locals 3\n\n"
        "    invoke-static {}, Lcom/omni/production/check/utils/"
        "ProductionSetting;->getBleVersion()Ljava/lang/String;\n\n"
        "    move-result-object v0\n\n"
        '    const-string v1, "nosrv"\n\n'
        "    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n\n"
        "    move-result v1\n\n"
        "    if-eqz v1, :ns_check2\n\n"
        "    return-void\n\n"
        "    :ns_check2\n\n"
        '    const-string v1, "autounlock"\n\n'
        "    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n\n"
        "    move-result v0\n\n"
        "    if-eqz v0, :ns_ok\n\n"
        "    return-void\n\n"
        "    :ns_ok\n"
    )
    t = t0.replace(old, guard, 1)
    write(act_path, t)
    print("patched:", act_path, "(nosrv row skips log upload)")


def patch_autounlock(act_path):

    t0 = open(act_path, encoding="utf-8").read()
    if ":au_check" in t0:
        print("   autounlock guard already exists, skipping")
        return
    old = ".method protected onBLEGetKey(Ljava/lang/String;B)V\n    .locals 6\n"
    if old not in t0:
        raise SystemExit("could not find the onBLEGetKey header")
    guard = (
        ".method protected onBLEGetKey(Ljava/lang/String;B)V\n    .locals 6\n\n"
        "    invoke-static {}, Lcom/omni/production/check/utils/"
        "ProductionSetting;->getBleVersion()Ljava/lang/String;\n\n"
        "    move-result-object v0\n\n"
        '    const-string v1, "autounlock"\n\n'
        "    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n\n"
        "    move-result v1\n\n"
        "    if-nez v1, :au_send\n\n"
        '    const-string v1, "srv"\n\n'
        "    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n\n"
        "    move-result v1\n\n"
        "    if-eqz v1, :au_done\n\n"
        "    :au_send\n\n"
        "    const/4 v0, 0x0\n\n"
        "    invoke-virtual {p0, v0}, Lcom/omni/production/check/activity/"
        "NBScooterToolActivity;->sendScooterOpenCommand(I)V\n\n"
        "    :au_done\n"
    )
    t = t0.replace(old, guard, 1)
    write(act_path, t)
    print("patched:", act_path, "(autounlock row unlocks automatically)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Patch BleTool 3.9.23 (com.omni.production.check) for offline use."
    )
    ap.add_argument(
        "decoded",
        nargs="?",
        default="decoded_patched",
        help="apktool-decoded directory (default: decoded_patched)",
    )
    ap.add_argument(
        "--dev-key",
        default=DEFAULT_DEV_KEY,
        help="BLE key (default: working built-in key)",
    )
    ap.add_argument(
        "--dev-type", default=DEFAULT_DEV_TYPE, help="deviceType hex (default 60)"
    )
    ap.add_argument(
        "--upd-key", default=DEFAULT_UPD_KEY, help="upgrade key (default C7qn)"
    )
    ap.add_argument(
        "--dev-ver", default=DEFAULT_DEV_VER, help="bleVersion (default 1.0)"
    )
    ap.add_argument(
        "--base",
        default=NEW_BASE,
        help="omni-api base URL; 'none' leaves the original unchanged",
    )
    ap.add_argument(
        "--online-login",
        action="store_true",
        help="disable offline seeding (TApplication/Welcome/"
        "AccountUtils/HomeActivity refresh+initdata) so the "
        "REAL login screen runs against your own server",
    )
    a = ap.parse_args()

    DEV_KEY, DEV_TYPE, UPD_KEY, DEV_VER = a.dev_key, a.dev_type, a.upd_key, a.dev_ver
    NEW_BASE = None if str(a.base).strip().lower() in ("none", "") else a.base
    ROOT = a.decoded
    SM = os.path.join(ROOT, "smali/com/omni/production/check")
    assert os.path.isdir(SM), "could not find %s" % SM
    build_config()

    assert_fresh(ROOT)
    if not a.online_login:
        patch_app(os.path.join(SM, "TApplication.smali"))
        patch_welcome(os.path.join(SM, "activity/WelcomeActivity.smali"))
        patch_account(os.path.join(SM, "utils/AccountUtils.smali"))
        patch_home(os.path.join(SM, "activity/HomeActivity.smali"))
        patch_initdata(os.path.join(SM, "activity/HomeActivity.smali"))
    else:
        print("online login: seeding disabled - real login screen used")
    patch_base_url(os.path.join(SM, "network/RetrofitUtils.smali"))
    patch_base_url(os.path.join(SM, "network/ApiService.smali"))
    patch_scandialog(os.path.join(SM, "dialog/ScanDialog.smali"))
    patch_scandialog_timeout(os.path.join(SM, "dialog/ScanDialog$2.smali"))
    patch_fwinfo_filter(
        os.path.join(SM, "activity/FwInfoActivity$initListener$1$1.smali")
    )
    patch_ulock_connect_button(os.path.join(SM, "activity/ULockTestActivity.smali"))
    import patch_qrbutton

    patch_qrbutton.patch_add_qr_button(
        os.path.join(SM, "activity/ULockTestActivity.smali"),
        os.path.join(ROOT, "res/values/strings.xml"),
        write,
    )
    patch_versioninfo_skip(os.path.join(SM, "utils/UpgradeUtils.smali"))
    patch_noserver_log(os.path.join(SM, "activity/NBScooterToolActivity.smali"))
    patch_autounlock(os.path.join(SM, "activity/NBScooterToolActivity.smali"))
    patch_oss_download_local(os.path.join(SM, "utils/OssUtils.smali"))
    patch_oss_getfile(os.path.join(SM, "utils/OssUtils.smali"))
    patch_logpath(os.path.join(SM, "utils/LogUpgradeUtils.smali"))
    patch_manifest_storage(os.path.join(ROOT, "AndroidManifest.xml"))
    patch_builtin_keys(SM)
    patch_hasolddata(
        os.path.join(
            ROOT,
            "smali/com/omni/support/ble/protocol/scooter/model/ScooterLockInfoResult.smali",
        )
    )
    verify_polarity(ROOT, online_login=a.online_login)
    print(
        "\nkey:", DEV_KEY, "| type:", DEV_TYPE, "| upd:", UPD_KEY, "| ver:", DEV_VER
    )
    print("base URL:", NEW_BASE or "(unchanged)")
