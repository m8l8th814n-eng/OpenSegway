#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch av com.omni.production.check (BleTool 3.9.23).

Tva lagen, styrda av konstanterna nedan:
  * Offline-laget (alltid pa): syntetisk session i SharedPreferences, ingen login,
    inga natverksanrop fran HomeActivity.
  * Bas-URL: byt omni-api-strangen duckdns -> tailnet (NEW_BASE=None for att hoppa over).

Punkter:
  1. TApplication.onCreate  -> injicerar syntetisk LoginBean i SP om LOGIN_JSON ar tom.
  2. WelcomeActivity.nav     -> startar alltid HomeActivity.
  3. AccountUtils.logout     -> aterstaller offline-sessionen, gar till HomeActivity.
  4. HomeActivity.refresh    -> no-op (originalet kvar som refresh_orig).
  5. RetrofitUtils + ApiService -> bas-URL duckdns -> NEW_BASE.

Kor:  python3 patch_offline.py <decoded-dir>
"""
import os, re, sys, argparse

# Inbyggda, fungerande standardnycklar ur appen (FwInfoActivity: SPUtils default
# "fw_device_key"; samma strang bygger ScooterSession med deviceType 60 + updateKey C7qn).
# Kan overridas pa kommandoraden UTAN att redigera filen:
#   python3 patch_offline.py <dec> --dev-key XXXX --upd-key YYYY [--dev-type 60] [--dev-ver 1.0]
# Utan flaggor anvands dessa, dvs identiskt resultat som tidigare.
DEFAULT_DEV_KEY  = "4BKNwi77"
DEFAULT_DEV_TYPE = "60"        # ProductionSetting.getDeviceType() tolkar detta som hex
DEFAULT_UPD_KEY  = "C7qn"
DEFAULT_DEV_VER  = "1.0"

# Live-varden (satts om av CLI i main). Modulnivan behaller standard sa importerande
# kod/aldre anrop fortsatter fungera.
DEV_KEY  = DEFAULT_DEV_KEY
DEV_TYPE = DEFAULT_DEV_TYPE
UPD_KEY  = DEFAULT_UPD_KEY
DEV_VER  = DEFAULT_DEV_VER

ROOT = "decoded_patched"
SM = os.path.join(ROOT, "smali/com/omni/production/check")

# En rad per enhetstyp sa man kommer in i ratt BLE-verktyg (productKey styr
# NavigationUtils.nav). Alla pekar pa samma inbyggda nyckel.
# Nyckeln for raden "Connect NB as Batch". Andra har for att testa en annan
# losenordskandidat - den skrivs till installningarna vid klick och anvands
# som deviceKey i handskakningen.
BATCH_KEY = "Vgz7"

ROWS = [
    ("NB key 4BKNwi77",     "scooter_nb", "autounlock", "4BKNwi77"),
    ("NB key 4BKNwi77 manual", "scooter_nb", "1.0", "4BKNwi77"),
    ("NB key yOTmK50z",     "scooter_nb", "autounlock", "yOTmK50z"),
    ("NB key OmniW4GX",     "scooter_nb", "autounlock", "OmniW4GX"),
    ("NB key Vgz7",        "scooter_nb", "autounlock", "Vgz7"),
    ("NB key C7qn",        "scooter_nb", "autounlock", "C7qn"),
    # "srv" = autounlock MEN med server uppladdning kvar (online-lasning).
    # Nyckeln: 4BKNwi77 - den fran forsta versionen som bekraftat fungerar.
    ("NB online 4BKNwi77", "scooter_nb", "srv", "4BKNwi77"),
    ("NB 4BKNwi77 8A",    "scooter_nb_upgrade", "autounlock", "4BKNwi77"),
    ("NB yOTmK50z 8A",    "scooter_nb_upgrade", "autounlock", "yOTmK50z"),
    ("NB OmniW4GX 8A",    "scooter_nb_upgrade", "autounlock", "OmniW4GX"),
    ("NB Vgz7 8A",        "scooter_nb_upgrade", "autounlock", "Vgz7"),
    ("NB C7qn 8A",        "scooter_nb_upgrade", "autounlock", "C7qn"),
    ("U 4BKNwi77",        "u_lock", "autounlock", "4BKNwi77"),
    ("U yOTmK50z",        "u_lock", "autounlock", "yOTmK50z"),
    ("U OmniW4GX",        "u_lock", "autounlock", "OmniW4GX"),
    ("U Vgz7",            "u_lock", "autounlock", "Vgz7"),
    ("U C7qn",            "u_lock", "autounlock", "C7qn"),
    ("Scooter1",          "scooter_nb", "1.0", "4BKNwi77"),
    ("Scooter XM",        "scooter_xm"),
    ("Scooter NB",        "scooter_nb"),
    ("NB Show",           "scooter_nb_show"),
    ("NB Cable tool",     "scooter_nb_tool1"),
    ("Scooter NB upgr",   "scooter_nb_upgrade"),
    ("U-Lock",            "u_lock"),
    ("Personal lock",     "personal_lock"),
    ("Bike lock 3-in-1",  "bike_gprs_ble"),
    ("Bike lock BT",      "bike_ble"),
    ("Cable/Bloom",       "cable_lock"),
    ("Bloom HJ",          "bloom_lock_hj"),
    ("Battery lock HJ",   "battery_lock_hj"),
    ("Key box",           "keybox"),
    ("Carport",           "park_lock"),
    ("Carport Plus",      "park_lock_plus"),
    ("Carport Plus 485",  "park_lock_485"),
    ("Transmission",      "transmission"),
    ("Accompanying bed",  "Accompanying_bed_lock"),
    ("BF meter",          "meter_bf"),
    ("BF meter BLE",      "BF_IOT_BLE"),
    ("Geomagnetic",       "omni_dici"),
]


def _row(i, name, product_key, ver=None, key=None):
    """ver: per-rad bleVersion (markor). key: per-rad bleKey - appen skriver den
    till installningarna vid klick, och aktiviteten anvander den som deviceKey.
    Alltsa: en rad med annan nyckel testar en annan losenordskandidat."""
    return ('{"id":"%04d","name":"%s","bleKey":"%s","iotCode":"%s","upgradeKey":"%s",'
            '"bleVersion":"%s","carFactoryName":"","empowerNumber":"","productKey":"%s",'
            '"productionType":"","code":"","note":""}'
            % (i, name, key or DEV_KEY, DEV_TYPE, UPD_KEY, ver or DEV_VER, product_key))


KEYS = ["DEVICE_KEY", "DEVICE_TYPE", "CUSTOMER_ID", "CUSTOMER_NAME", "UPDATE_KEY",
        "BLE_VERSION", "FIRMWARE_VERSION", "FIRMWARE_NAME", "FIRMWARE_NODE",
        "LOCK_FILE", "QR_FILEPATH", "QRCODE_START", "QRCODE_END", "QRCODE_LENGTH"]


SDCARD_DIR = "/sdcard/omni"
QR_FILENAME = "omni_qr.csv"
FW_FILENAME = "omni_fw.bin"

def build_config():
    """Bygg payload/VALS fran de aktuella DEV_*-vardena. Anropas efter CLI-parsning
    sa ett nyckelbyte slar igenom bade i JSON:ens per-rad bleKey och i skalar-SP."""
    global CUSTOMER_CONFIG, PAYLOAD, VALS
    CUSTOMER_CONFIG = "[" + ",".join(
        _row(i + 1, r[0], r[1],
             r[2] if len(r) > 2 else None,
             r[3] if len(r) > 3 else None)
        for i, r in enumerate(ROWS)) + "]"
    PAYLOAD = "{" + ",".join([
        '"token":"offline"',
        '"expiredTimeStamp":4102444800000',
        '"user":{"id":1,"nickname":"offline","role":5,"lang":"sv"}',
        '"customerConfig":%s' % CUSTOMER_CONFIG,
        '"lockFile":[]',
        '"qrFile":[]',
    ]) + "}"
    # index: 0 DEVICE_KEY 1 DEVICE_TYPE 2 CUSTOMER_ID 3 CUSTOMER_NAME 4 UPDATE_KEY
    #        5 BLE_VERSION 6 FIRMWARE_VERSION 7 FIRMWARE_NAME 8 FIRMWARE_NODE
    #        9 LOCK_FILE 10 QR_FILEPATH 11 QRCODE_START 12 QRCODE_END 13 QRCODE_LENGTH
    VALS = [DEV_KEY, DEV_TYPE, "0001", "OFFLINE", UPD_KEY,
            DEV_VER, "1.0", FW_FILENAME, "offline", FW_FILENAME, QR_FILENAME,
            "", "", ""]


# Standardvarden sa moduldirekta anvandningar fungerar aven utan build_config().
build_config()

# omni-api-bas-URL. NEW_BASE=None -> lamna originalet.
OLD_BASE = "https://scootercracking.duckdns.org/omni-api/"
NEW_BASE = "http://brainfisting:18080/"   # egen stub: misc/omni_api_stub.py


def q(v):
    return '"%s"' % v.replace("\\", "\\\\").replace('"', '\\"')


def inject_block(done):
    """Smali: om LOGIN_JSON ar tom -> skriv in offline-sessionen i SP.
    Kraver >=3 lediga lokala register (v0/v1/v2)."""
    L = []

    def add(x=""):
        L.append(x)

    def put_str(key, val):
        add('    const-string v1, %s' % q(val))
        add()
        add('    const-string v2, "%s"' % key)
        add()
        add('    invoke-virtual {v0, v2, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->putSP(Ljava/lang/String;Ljava/lang/String;)V')
        add()

    add('    invoke-static {}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->getSp()Lcom/omni/production/check/utils/SharedPreferencesUtil;')
    add()
    add('    move-result-object v0')
    add()
    add('    const-string v1, "LOGIN_JSON"')
    add()
    add('    invoke-virtual {v0, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->getSP(Ljava/lang/String;)Ljava/lang/String;')
    add()
    add('    move-result-object v1')
    add()
    add('    invoke-static {v1}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z')
    add()
    add('    move-result v1')
    add()
    add('    if-eqz v1, %s' % done)
    add()
    put_str("LOGIN_JSON", PAYLOAD)
    put_str("TOKEN", "offline")
    add('    const-wide v1, 0x3ddb8a00000L')
    add()
    add('    invoke-static {v1, v2}, Ljava/lang/Long;->valueOf(J)Ljava/lang/Long;')
    add()
    add('    move-result-object v1')
    add()
    add('    const-string v2, "LOGIN_DATE"')
    add()
    add('    invoke-virtual {v0, v2, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->putSP(Ljava/lang/String;Ljava/lang/Long;)V')
    add()
    for k, v in zip(KEYS, VALS):
        put_str(k, v)
    add('    %s' % done)
    add()
    return "\n".join(L)


def assert_fresh(root):
    """Skydda mot att skriptet kors tva ganger pa samma traff (dubbelinjektion)."""
    marker = os.path.join(root, "smali/com/omni/production/check/activity/HomeActivity.smali")
    if os.path.exists(marker) and ":seed_done" in open(marker, encoding="utf-8").read():
        raise SystemExit("TRAFFET AR REDAN PATCHAT (%s) - gor en farsk kopia av decoded/" % root)


def write(path, t):
    open(path, "w", encoding="utf-8").write(t)


def patch_app(path):
    t0 = open(path, encoding="utf-8").read()
    anchor = ('   invoke-static {p0}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->init'
              '(Landroid/content/Context;)V\n\n')
    if anchor not in t0:
        raise SystemExit("TApplication: hittar inte SP-init")
    t = t0.replace(".method public onCreate()V\n    .locals 2\n",
                   ".method public onCreate()V\n    .locals 3\n")
    t = t.replace(anchor, anchor + inject_block(":app_done"))
    assert t != t0
    write(path, t)
    print("patchad:", path)


def patch_welcome(path):
    t0 = open(path, encoding="utf-8").read()
    n = t0.count("const-class v1, Lcom/omni/production/check/activity/LoginActivity;")
    if n < 1:
        raise SystemExit("WelcomeActivity: hittar inga LoginActivity-refs")
    t = t0.replace("const-class v1, Lcom/omni/production/check/activity/LoginActivity;",
                   "const-class v1, Lcom/omni/production/check/activity/HomeActivity;")
    if "if-lez v0, :cond_0" not in t:
        raise SystemExit("WelcomeActivity: hittar inte utgangen-grenen")
    t = t.replace("if-lez v0, :cond_0", "goto :cond_0")
    write(path, t)
    print("patchad:", path, "(%d LoginActivity -> HomeActivity, utgangen-gren borttagen)" % n)


def patch_account(path):
    """Laggs EFTER removeSP-kedjan, och med 3 lediga register (.locals 2 -> 5)."""
    t0 = open(path, encoding="utf-8").read()
    if t0.count("const-class v1, Lcom/omni/production/check/activity/LoginActivity;") != 1:
        raise SystemExit("AccountUtils: vantade 1 LoginActivity-ref")
    t = t0.replace(".method public static logout(Landroid/app/Activity;)V\n    .locals 2\n",
                   ".method public static logout(Landroid/app/Activity;)V\n    .locals 5\n")
    t = t.replace("const-class v1, Lcom/omni/production/check/activity/LoginActivity;",
                  "const-class v1, Lcom/omni/production/check/activity/HomeActivity;")
    marker = ('    invoke-virtual {v0, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->removeSP(Ljava/lang/String;)V\n\n'
              '    .line 34\n')
    if marker not in t:
        raise SystemExit("AccountUtils: hittar inte slutet pa removeSP-kedjan")
    t = t.replace(marker,
                  '    invoke-virtual {v0, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->removeSP(Ljava/lang/String;)V\n\n'
                  + inject_block(":logout_done") + "\n    .line 34\n")
    assert t != t0
    write(path, t)
    print("patchad:", path)


def patch_home(path):
    t0 = open(path, encoding="utf-8").read()
    m = re.search(r"\.method private refresh\(\)V\n    \.locals \d+\n\n", t0)
    if not m:
        raise SystemExit("HomeActivity: hittar inte refresh()")
    t = t0.replace(m.group(0),
                   ".method private refresh()V\n    .locals 4\n\n    return-void\n.end method\n\n"
                   ".method private refresh_orig()V\n    .locals 4\n\n")
    assert t != t0
    write(path, t)
    print("patchad:", path, "(refresh() -> no-op, originalet kvar som refresh_orig)")


def patch_base_url(path):
    """Byt omni-api-bas-URL (duckdns -> tailnet)."""
    if not NEW_BASE:
        print("hoppar over bas-URL (NEW_BASE=None):", path)
        return
    t0 = open(path, encoding="utf-8").read()
    n = t0.count(OLD_BASE)
    if n < 1:
        raise SystemExit("%s: hittar inte %s" % (path, OLD_BASE))
    write(path, t0.replace(OLD_BASE, NEW_BASE))
    print("patchad:", path, "(%d x %s -> %s)" % (n, OLD_BASE, NEW_BASE))



def patch_initdata(path):
    """HomeActivity.initData(): seeda listan fran den lokala LOGIN_JSON-sessionen.
    Anropar den befintliga bryggan access$200 -> setData(LoginBean) (undviker
    private-atkomst mellan klasser). refresh() lamnas som no-op."""
    t0 = open(path, encoding="utf-8").read()
    old = ('.method private initData()V\n    .locals 0\n\n'
           '    .line 304\n'
           '    invoke-direct {p0}, Lcom/omni/production/check/activity/HomeActivity;->refresh()V\n\n'
           '    return-void\n.end method\n')
    if old not in t0:
        raise SystemExit("HomeActivity: initData() matchar inte")
    seed = (
        '    invoke-static {}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->getSp()Lcom/omni/production/check/utils/SharedPreferencesUtil;\n\n'
        '    move-result-object v0\n\n'
        '    const-string v1, "LOGIN_JSON"\n\n'
        '    invoke-virtual {v0, v1}, Lcom/omni/production/check/utils/SharedPreferencesUtil;->getSP(Ljava/lang/String;)Ljava/lang/String;\n\n'
        '    move-result-object v0\n\n'
        '    invoke-static {v0}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z\n\n'
        '    move-result v1\n\n'
        '    if-nez v1, :seed_done\n\n'
        '    new-instance v1, Lcom/google/gson/Gson;\n\n'
        '    invoke-direct {v1}, Lcom/google/gson/Gson;-><init>()V\n\n'
        '    const-class v2, Lcom/omni/production/check/bean/LoginBean;\n\n'
        '    invoke-virtual {v1, v0, v2}, Lcom/google/gson/Gson;->fromJson(Ljava/lang/String;Ljava/lang/Class;)Ljava/lang/Object;\n\n'
        '    move-result-object v0\n\n'
        '    check-cast v0, Lcom/omni/production/check/bean/LoginBean;\n\n'
        '    invoke-static {p0, v0}, Lcom/omni/production/check/activity/HomeActivity;->access$200(Lcom/omni/production/check/activity/HomeActivity;Lcom/omni/production/check/bean/LoginBean;)V\n\n'
        '    :seed_done\n\n'
    )
    new = ('.method private initData()V\n    .locals 3\n\n'
           '    .line 304\n'
           '    invoke-direct {p0}, Lcom/omni/production/check/activity/HomeActivity;->refresh()V\n\n'
           + seed + '    return-void\n.end method\n')
    write(path, t0.replace(old, new))
    print("patchad:", path, "(initData seedar listan fran LOGIN_JSON)")



def patch_logpath(path):
    """LogUpgradeUtils.uploadLogFile: appens loggfil lagrades i appens PRIVATA
    Download-mapp (getExternalFilesDir) -> den raderas vid uninstall, vilket
    kostade oss insamlade loggar. Flytta till publik /sdcard/Download
    (getExternalStoragePublicDirectory) som overlever ominstallation.
    targetSdk 29 + requestLegacyExternalStorage gor att det funkar;
    MANAGE_EXTERNAL_STORAGE laggs dessutom i manifestet for nyare telefoner."""
    t0 = open(path, encoding="utf-8").read()
    if "getExternalStoragePublicDirectory" in t0:
        print("   loggsokvagen ar redan publik, hoppar over")
        return
    old = ("    invoke-virtual {v0, v1}, Landroid/content/Context;"
           "->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;")
    if old not in t0:
        raise SystemExit("hittar inte getExternalFilesDir-anropet")
    new = ("    invoke-static {v1}, Landroid/os/Environment;"
           "->getExternalStoragePublicDirectory(Ljava/lang/String;)Ljava/io/File;")
    write(path, t0.replace(old, new, 1))
    print("patchad:", path, "(loggfil -> /sdcard/Download, overlever uninstall)")


def patch_manifest_storage(path):
    """Manifestet: lag till MANAGE_EXTERNAL_STORAGE sa Android 12+ far
    'atkomst till alla filer' (behover godkannas i Installningar en gang)."""
    t0 = open(path, encoding="utf-8").read()
    if "MANAGE_EXTERNAL_STORAGE" in t0:
        print("   MANAGE_EXTERNAL_STORAGE finns redan, hoppar over")
        return
    old = ('    <uses-permission android:name='
           '"android.permission.WRITE_EXTERNAL_STORAGE"/>')
    if old not in t0:
        raise SystemExit("hittar inte WRITE_EXTERNAL_STORAGE-raden i manifestet")
    new = (old + "\n" +
           '    <uses-permission android:name='
           '"android.permission.MANAGE_EXTERNAL_STORAGE"/>')
    write(path, t0.replace(old, new, 1))
    print("patchad:", path, "(+MANAGE_EXTERNAL_STORAGE)")


def patch_scandialog(path):
    """ScanDialog: visa ALLT. Tre andringar:
    1) onLeScan: hoppa over namnkravet, namnfiltret OCH rssi-filtret. Adaptern faller
       tillbaka pa MAC nar namnet ar null, sa aven namnlosa enheter listas.
    2) initView: rssi-standard 30 -> 60 (-100 dBm) sa inget doljs aven om reglaget rors.
    3) ScanDialog$2.onGranted: scan-tiden 10 s -> 5 min sa listan inte dor mitt i."""
    t0 = open(path, encoding="utf-8").read()
    old = ('    if-eqz p3, :cond_2\n\n'
           '    if-eqz v0, :cond_2\n\n'
           '    .line 197\n'
           '    iget-object v1, p0, Lcom/omni/production/check/dialog/ScanDialog;->filterName:Ljava/lang/String;\n\n'
           '    invoke-static {v1}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z\n\n'
           '    move-result v1\n\n'
           '    if-nez v1, :cond_0\n\n'
           '    iget-object v1, p0, Lcom/omni/production/check/dialog/ScanDialog;->filterName:Ljava/lang/String;\n\n'
           '    invoke-virtual {v1, p3}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z\n\n'
           '    move-result p3\n\n'
           '    if-eqz p3, :cond_2\n\n'
           '    :cond_0\n'
           '    iget p3, p0, Lcom/omni/production/check/dialog/ScanDialog;->filterRSSI:I\n\n'
           '    if-ge p2, p3, :cond_1\n\n'
           '    goto :goto_0\n\n'
           '    .line 200\n'
           '    :cond_1\n')
    new = ('    if-eqz v0, :cond_2\n\n'
           '    if-nez p3, :cond_9\n\n'
           '    move-object p3, v0\n\n'
           '    :cond_9\n'
           '    :cond_1\n')
    if old not in t0:
        raise SystemExit("ScanDialog: hittar inte filterblocket i onLeScan")
    t = t0.replace(old, new)
    k = t.count('    const-string v1, "rssi_progress"\n\n    const/16 v2, 0x1e\n')
    if k != 1:
        raise SystemExit("ScanDialog: vantade 1 rssi-default, hittade %d" % k)
    t = t.replace('    const-string v1, "rssi_progress"\n\n    const/16 v2, 0x1e\n',
                  '    const-string v1, "rssi_progress"\n\n    const/16 v2, 0x3c\n')
    write(path, t)
    print("patchad:", path, "(visar allt: inget namn-/rssi-filer, MAC som fallback, rssi-golv -100)")


def patch_scandialog_timeout(path):
    """ScanDialog$2.onGranted: 10 s skanning -> 5 minuter."""
    t0 = open(path, encoding="utf-8").read()
    if t0.count("    const-wide/16 v2, 0x2710\n") != 1:
        raise SystemExit("ScanDialog$2: hittar inte 10 s-timeout")
    t = t0.replace("    const-wide/16 v2, 0x2710\n", "    const-wide v2, 0x493e0L\n")
    write(path, t)
    print("patchad:", path, "(skanningstid 10 s -> 5 min)")





def patch_fwinfo_filter(path):
    """FwInfoActivity onSearch satte filterName="Scooter|Segway IoT". Koden gor en raw
    strangsokning, inte regex-alternativ, sa bade "Scooter1" och "Segway IoT" faller bort.
    Tom strang = inget namnfiler (samma som ovriga BLE-aktiviteter)."""
    t0 = open(path, encoding="utf-8").read()
    old = '    const-string v1, "Scooter|Segway IoT"\n'
    if old not in t0:
        raise SystemExit("FwInfoActivity: hittar inte filter-strangen")
    write(path, t0.replace(old, '    const-string v1, ""\n'))
    print("patchad:", path, '(filterName "Scooter|Segway IoT" -> "" (inget namnfiler))')



# ------------------------------------------------------------------ U-Lock
def patch_ulock_nodownload(path):
    """ULockTestActivity.initData(): ta bort den automatiska OSS-nedladdningen
    (getOssKey -> natverk) och visa 'Inte nedladdad' i stallet for en felruta."""
    t0 = open(path, encoding="utf-8").read()
    old = ('    invoke-direct {p0}, Lcom/omni/production/check/activity/ULockTestActivity;->download()V\n\n'
           '    return-void\n.end method\n')
    if old not in t0:
        raise SystemExit("ULockTestActivity: hittar inte download()-anropet i initData")
    new = ('    iget-object v0, p0, Lcom/omni/production/check/activity/ULockTestActivity;->tvFile:Landroid/widget/TextView;\n\n'
           '    new-instance v1, Ljava/lang/StringBuilder;\n\n'
           '    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V\n\n'
           '    const-string v2, "qr_file: "\n\n'
           '    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n'
           '    const-string v2, "not_downloaded (offline)"\n\n'
           '    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n\n'
           '    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;\n\n'
           '    move-result-object v1\n\n'
           '    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V\n\n'
           '    return-void\n.end method\n')
    # behover ett extra lokalt register
    t = t0.replace(".method private initData()V\n    .locals 2\n",
                   ".method private initData()V\n    .locals 3\n")
    t = t.replace(old, new)
    if t == t0:
        raise SystemExit("ULockTestActivity: ingen andring")
    write(path, t)
    print("patchad:", path, "(ingen auto-nedladdning i initData)")


def patch_ulock_connect_button(path):
    """ULockTestActivity.searchQrCode(): anropa aldrig natet. Om QR-faltet har en
    MAC-adress, anslut direkt; annars visa 'ange MAC'."""
    t0 = open(path, encoding="utf-8").read()
    m = re.search(r"\.method private searchQrCode\(\)V\n    \.locals \d+\n", t0)
    if not m:
        raise SystemExit("ULockTestActivity: hittar inte searchQrCode()")
    # klipp ut hela metoden
    i = m.start()
    j = t0.find("\n.end method", t0.find(".line 1050", i)) + len("\n.end method\n")
    body = t0[i:j]
    if "getMacNumMap" not in body:
        raise SystemExit("ULockTestActivity: searchQrCode ser inte ut som vantat")
    new = ('.method private searchQrCode()V\n'
           '    .locals 2\n\n'
           '    iget-object v0, p0, Lcom/omni/production/check/activity/ULockTestActivity;->etQrCode:Landroid/widget/EditText;\n\n'
           '    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;\n\n'
           '    move-result-object v0\n\n'
           '    invoke-virtual {v0}, Ljava/lang/Object;->toString()Ljava/lang/String;\n\n'
           '    move-result-object v0\n\n'
           '    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;\n\n'
           '    move-result-object v0\n\n'
           '    invoke-static {v0}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z\n\n'
           '    move-result v1\n\n'
           '    if-nez v1, :ulock_connect\n\n'
           '    iget-object v1, p0, Lcom/omni/production/check/activity/ULockTestActivity;->etScanMac:Landroid/widget/EditText;\n\n'
           '    invoke-virtual {v1, v0}, Landroid/widget/EditText;->setText(Ljava/lang/CharSequence;)V\n\n'
           '    :ulock_connect\n'
           '    iget-object v0, p0, Lcom/omni/production/check/activity/ULockTestActivity;->etScanMac:Landroid/widget/EditText;\n\n'
           '    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;\n\n'
           '    move-result-object v0\n\n'
           '    invoke-virtual {v0}, Ljava/lang/Object;->toString()Ljava/lang/String;\n\n'
           '    move-result-object v0\n\n'
           '    invoke-virtual {v0}, Ljava/lang/String;->trim()Ljava/lang/String;\n\n'
           '    move-result-object v0\n\n'
           '    invoke-static {v0}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z\n\n'
           '    move-result v1\n\n'
           '    if-nez v1, :ulock_done\n\n'
           '    iget-object v1, p0, Lcom/omni/production/check/activity/ULockTestActivity;->tvMac:Landroid/widget/TextView;\n\n'
           '    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V\n\n'
           '    iget-object v1, p0, Lcom/omni/production/check/activity/ULockTestActivity;->bikeServiceProxy:Lcom/omni/ble/library/proxy/BLEBikeServiceProxy;\n\n'
           '    invoke-virtual {v1, v0}, Lcom/omni/ble/library/proxy/BLEBikeServiceProxy;->connect(Ljava/lang/String;)V\n\n'
           '    iget-object v0, p0, Lcom/omni/production/check/activity/ULockTestActivity;->dialogUtils:Lcom/omni/production/check/utils/DialogUtils;\n\n'
           '    invoke-virtual {v0}, Lcom/omni/production/check/utils/DialogUtils;->showLoadDialog()V\n\n'
           '    :ulock_done\n'
           '    return-void\n.end method\n')
    write(path, t0[:i] + new + t0[j:])
    print("patchad:", path, "(searchQrCode ansluter pa MAC, ingen server)")



def patch_download_calls(act_dir):
    """Ta bort den automatiska OssUtils-downloaden ur initData i alla BLE-aktiviteter.
    Anropet ligger alltid sist i metoden (foljt av return-void), sa borttagningen
    paverkar inga register eller grenar. BLE-knapparna ror sig inte."""
    import glob, os as _os
    n = 0
    for f in sorted(glob.glob(_os.path.join(act_dir, "*.smali"))):
        base = _os.path.basename(f)
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
        # bara om den ligger sist (bara return-void efter)
        i = m.group(1).find(call)
        after = m.group(1)[i + len(call):].strip()
        if after not in ("return-void",):
            print("   HOPPAR (inte sist):", base)
            continue
        write(f, t0.replace(call, ""))
        n += 1
    print("patchad: %d aktiviteter (auto-nedladdning borttagen)" % n)


def patch_builtin_keys(sm):
    """Synka appens EGNA inbyggda default-nyckel/upgrade-nyckel sa ett nyckelbyte galler
    aven firmware-flodet, som inte laser var injicerade SP-session:
      FwInfoActivity  SPUtils.getString("fw_device_key", "4BKNwi77")  (rad ~617)
      FwInfoActivity  UPDATE_KEY-faltet + const-string "C7qn"          (rad ~84/332)
      FwMenuActivity  const-string "C7qn"                              (rad ~160)
    Byter bara ut de distinkta nyckelstrangarna (som string-literaler), och gor
    INGENTING nar standardnycklarna anvands -> default-bygget blir bit-identiskt."""
    repl = []
    if DEV_KEY != DEFAULT_DEV_KEY:
        repl.append((DEFAULT_DEV_KEY, DEV_KEY))
    if UPD_KEY != DEFAULT_UPD_KEY:
        repl.append((DEFAULT_UPD_KEY, UPD_KEY))
    if not repl:
        print("inbyggda nycklar: standard (ingen synk behovs)")
        return
    import glob
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
        print("inbyggd nyckel: %s -> %s" % (old, new))
    print("   synkade %d fil(er)" % n)



# ------------------------------------------------------------------ lokal fil-fallback

def patch_oss_getfile(path):
    """OssUtils.getFile(url): peka pa en fast katalog pa /sdcard i stallet for appens
    externa filkatalog. Da kan man lagga QR-tabellen och firmware-filen dit med adb push,
    och appens inbyggda fallback (nar natet misslyckas) hittar dem."""
    t0 = open(path, encoding="utf-8").read()
    old = ('    invoke-static {}, Lcom/omni/production/check/TApplication;->getAppContext()Landroid/content/Context;\n\n'
           '    move-result-object v0\n\n'
           '    sget-object v1, Landroid/os/Environment;->DIRECTORY_DOWNLOADS:Ljava/lang/String;\n\n'
           '    invoke-virtual {v0, v1}, Landroid/content/Context;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;\n\n'
           '    move-result-object v0\n')
    new = ('    new-instance v0, Ljava/io/File;\n\n'
           '    const-string v1, "%s"\n\n'
           '    invoke-direct {v0, v1}, Ljava/io/File;-><init>(Ljava/lang/String;)V\n' % SDCARD_DIR)
    if old not in t0:
        raise SystemExit("OssUtils: hittar inte getExternalFilesDir-kedjan i getFile()")
    write(path, t0.replace(old, new))
    print("patchad:", path, "(getFile -> %s)" % SDCARD_DIR)



def patch_oss_download_local(path):
    """OssUtils.downloadFile: ersatt natverksvagen med enbart lokal fil.
    Laddar /sdcard/omni/<filnamn> direkt (samma filnamn som getFile raknar fram),
    anropar onSuccess utan natverk, eller onError om filerna saknas."""
    import os as _os
    t0 = open(path, encoding="utf-8").read()
    m = re.search(r"\.method public downloadFile\(Lcom/omni/production/check/utils/"
                  r"OssUtils\$OnOssFileDownloadListener;\)V\n.*?\n\.end method", t0, re.S)
    if not m:
        raise SystemExit("OssUtils: hittar inte downloadFile()")
    new = open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                             "assets", "downloadFile_local.smali"), encoding="utf-8").read()
    write(path, t0[:m.start()] + new.rstrip("\n") + t0[m.end():])
    print("patchad:", path, "(downloadFile -> enbart lokal fil, inget natverk)")



def patch_versioninfo_skip(path):
    """UpgradeUtils.getVersionInfo: hoppa over natverkskollen helt och kalla
    listener.no() direkt. Darmed oppnas verktyget pa ett klick i stallet for att
    appen vantar pa servern (och visar uppdateringsdialogen om en nod svarar)."""
    t0 = open(path, encoding="utf-8").read()
    m = re.search(r"\.method public static getVersionInfo\(Landroid/app/Activity;"
                  r"Ljava/lang/String;Lcom/omni/production/check/utils/"
                  r"UpgradeUtils\$IsUpgradeListener;\)V\n.*?\n\.end method", t0, re.S)
    if not m:
        raise SystemExit("UpgradeUtils: hittar inte getVersionInfo()")
    new = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "assets", "getVersionInfo_skip.smali"), encoding="utf-8").read()
    write(path, t0[:m.start()] + new.rstrip("\n") + t0[m.end():])
    print("patchad:", path, "(getVersionInfo -> no(), oppnar verktyget direkt)")


def patch_hasolddata(path):
    """ScooterLockInfoResult.setBuffer: hasOldData = (status | 0x40) == 1 kan aldrig
    bli sant (OR satter alltid bit 6, sa uttrycket ar alltid >= 0x40, aldrig 1).
    Byt till ett riktigt bittest: hasOldData = (status & 0x40) != 0.
    Grenen v1 (=1) anvands inte langre; v2 ar fortfarande 0-initierad som tidigare."""
    t0 = open(path, encoding="utf-8").read()
    old = ("    or-int/lit8 p1, p1, 0x40\n\n"
           "    if-ne p1, v1, :cond_2\n")
    new = ("    and-int/lit8 p1, p1, 0x40\n\n"
           "    if-eqz p1, :cond_2\n")
    if t0.count(old) != 1:
        raise SystemExit("ScooterLockInfoResult: hittar inte hasOldData-blocket (eller flera traffar)")
    write(path, t0.replace(old, new, 1))
    print("patchad:", path, "(hasOldData: (status|0x40)==1 -> (status&0x40)!=0)")


def verify_polarity(root, online_login=False):
    """Sparr: kontrollera att isEmpty-grenarna har ratt polaritet.
    Detta var buggen som gav tom lista tva ganger. Fel -> avbryt.
    Vid --online-login patchas seedningen medvetet inte, sa dessa tre
    kontroller galler inte - hoppas over dem da."""
    if online_login:
        print("polaritetskontroll: ej tillamplig (online-login, seedning avstangd)")
        return
    checks = [
        ("smali/com/omni/production/check/TApplication.smali",
         "if-eqz v1, :app_done",
         "skriva sessionen nar den ar TOM"),
        ("smali/com/omni/production/check/utils/AccountUtils.smali",
         "if-eqz v1, :logout_done",
         "aterstalla sessionen nar den ar TOM"),
        ("smali/com/omni/production/check/activity/HomeActivity.smali",
         "if-nez v1, :seed_done",
         "parsa nar den INTE ar tom"),
    ]
    for rel, want, why in checks:
        path = os.path.join(root, rel)
        body = open(path, encoding="utf-8").read()
        if want in body:
            continue
        other = (want.replace("if-eqz", "if-nez") if want.startswith("if-eqz")
                 else want.replace("if-nez", "if-eqz"))
        extra = "  (hittade motsatsen: %s)" % other if other in body else ""
        raise SystemExit("POLARITETSKONTROLL MISSLYCKADES i %s\n"
                         "  saknar: %s  (%s)%s" % (rel, want, why, extra))
    print("polaritetskontroll: OK (TApplication/AccountUtils if-eqz, HomeActivity if-nez)")


def patch_noserver_log(act_path):
    """NBScooterToolActivity.onBLEScooterLogData: om radens bleVersion ar "nosrv",
    avbryt direkt. Da visas aldrig loggdialogen och upload()/closeBle() kor aldrig -
    hela det serverberoende efterflodet stangs av for den raden."""
    t0 = open(act_path, encoding="utf-8").read()
    if ":ns_ok" in t0:
        print("   nosrv-sparren finns redan, hoppar over")
        return
    old = ".method protected onBLEScooterLogData([B)V\n    .locals 3\n"
    if old not in t0:
        raise SystemExit("hittar inte onBLEScooterLogData-header")
    guard = ('.method protected onBLEScooterLogData([B)V\n    .locals 3\n\n'
             '    invoke-static {}, Lcom/omni/production/check/utils/'
             'ProductionSetting;->getBleVersion()Ljava/lang/String;\n\n'
             '    move-result-object v0\n\n'
             '    const-string v1, "nosrv"\n\n'
             '    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n\n'
             '    move-result v1\n\n'
             '    if-eqz v1, :ns_check2\n\n'
             '    return-void\n\n'
             '    :ns_check2\n\n'
             '    const-string v1, "autounlock"\n\n'
             '    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n\n'
             '    move-result v0\n\n'
             '    if-eqz v0, :ns_ok\n\n'
             '    return-void\n\n'
             '    :ns_ok\n')
    t = t0.replace(old, guard, 1)
    write(act_path, t)
    print("patchad:", act_path, "(nosrv-markerad rad hoppar over logg-uppladdningen)")



def patch_autounlock(act_path):
    """NBScooterToolActivity.onBLEGetKey: om radens bleVersion ar "autounlock", skicka
    upplasningskommandot direkt nar nyckelhandskakningen ar klar - i stallet for att
    vanta pa att anvandaren trycker. Scannar/valjer enhet gors som vanligt."""
    t0 = open(act_path, encoding="utf-8").read()
    if ":au_check" in t0:
        print("   autounlock-sparren finns redan, hoppar over")
        return
    old = ".method protected onBLEGetKey(Ljava/lang/String;B)V\n    .locals 6\n"
    if old not in t0:
        raise SystemExit("hittar inte onBLEGetKey-header")
    guard = ('.method protected onBLEGetKey(Ljava/lang/String;B)V\n    .locals 6\n\n'
             '    invoke-static {}, Lcom/omni/production/check/utils/'
             'ProductionSetting;->getBleVersion()Ljava/lang/String;\n\n'
             '    move-result-object v0\n\n'
             '    const-string v1, "autounlock"\n\n'
             '    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n\n'
             '    move-result v1\n\n'
             '    if-nez v1, :au_send\n\n'
             '    const-string v1, "srv"\n\n'
             '    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n\n'
             '    move-result v1\n\n'
             '    if-eqz v1, :au_done\n\n'
             '    :au_send\n\n'
             '    const/4 v0, 0x0\n\n'
             '    invoke-virtual {p0, v0}, Lcom/omni/production/check/activity/'
             'NBScooterToolActivity;->sendScooterOpenCommand(I)V\n\n'
             '    :au_done\n')
    t = t0.replace(old, guard, 1)
    write(act_path, t)
    print("patchad:", act_path, "(autounlock-raden laser upp automatiskt)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Patcha BleTool 3.9.23 (com.omni.production.check) -> offline.")
    ap.add_argument("decoded", nargs="?", default="decoded_patched",
                    help="apktool-dekodad katalog (default: decoded_patched)")
    ap.add_argument("--dev-key", default=DEFAULT_DEV_KEY,
                    help="BLE-nyckel (default: inbyggd fungerande nyckel)")
    ap.add_argument("--dev-type", default=DEFAULT_DEV_TYPE, help="deviceType hex (default 60)")
    ap.add_argument("--upd-key", default=DEFAULT_UPD_KEY, help="upgrade-nyckel (default C7qn)")
    ap.add_argument("--dev-ver", default=DEFAULT_DEV_VER, help="bleVersion (default 1.0)")
    ap.add_argument("--base", default=NEW_BASE,
                    help="omni-api bas-URL; 'none' lamnar originalet orort")
    ap.add_argument("--online-login", action="store_true",
                    help="stang av offline-seedningen (TApplication/Welcome/"
                         "AccountUtils/HomeActivity refresh+initdata) sa den "
                         "RIKTIGA inloggningsskarmen kors mot egen server")
    a = ap.parse_args()

    DEV_KEY, DEV_TYPE, UPD_KEY, DEV_VER = a.dev_key, a.dev_type, a.upd_key, a.dev_ver
    NEW_BASE = None if str(a.base).strip().lower() in ("none", "") else a.base
    ROOT = a.decoded
    SM = os.path.join(ROOT, "smali/com/omni/production/check")
    assert os.path.isdir(SM), "hittar inte %s" % SM
    build_config()

    assert_fresh(ROOT)
    if not a.online_login:
        patch_app(os.path.join(SM, "TApplication.smali"))
        patch_welcome(os.path.join(SM, "activity/WelcomeActivity.smali"))
        patch_account(os.path.join(SM, "utils/AccountUtils.smali"))
        patch_home(os.path.join(SM, "activity/HomeActivity.smali"))
        patch_initdata(os.path.join(SM, "activity/HomeActivity.smali"))
    else:
        print("online-login: seedning avstangd - riktig login-skarm anvands")
    patch_base_url(os.path.join(SM, "network/RetrofitUtils.smali"))
    patch_base_url(os.path.join(SM, "network/ApiService.smali"))
    patch_scandialog(os.path.join(SM, "dialog/ScanDialog.smali"))
    patch_scandialog_timeout(os.path.join(SM, "dialog/ScanDialog$2.smali"))
    patch_fwinfo_filter(os.path.join(SM, "activity/FwInfoActivity$initListener$1$1.smali"))
    patch_ulock_connect_button(os.path.join(SM, "activity/ULockTestActivity.smali"))
    import patch_qrbutton
    patch_qrbutton.patch_add_qr_button(
        os.path.join(SM, "activity/ULockTestActivity.smali"),
        os.path.join(ROOT, "res/values/strings.xml"), write)
    patch_versioninfo_skip(os.path.join(SM, "utils/UpgradeUtils.smali"))
    patch_noserver_log(os.path.join(SM, "activity/NBScooterToolActivity.smali"))
    patch_autounlock(os.path.join(SM, "activity/NBScooterToolActivity.smali"))
    patch_oss_download_local(os.path.join(SM, "utils/OssUtils.smali"))
    patch_oss_getfile(os.path.join(SM, "utils/OssUtils.smali"))
    patch_logpath(os.path.join(SM, "utils/LogUpgradeUtils.smali"))
    patch_manifest_storage(os.path.join(ROOT, "AndroidManifest.xml"))
    patch_builtin_keys(SM)
    patch_hasolddata(os.path.join(
        ROOT, "smali/com/omni/support/ble/protocol/scooter/model/ScooterLockInfoResult.smali"))
    verify_polarity(ROOT, online_login=a.online_login)
    print("\nnyckel:", DEV_KEY, "| typ:", DEV_TYPE, "| upd:", UPD_KEY, "| ver:", DEV_VER)
    print("bas-URL:", NEW_BASE or "(orort)")
