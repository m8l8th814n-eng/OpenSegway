"""Injecterar appendQrRow-hjalpen och kopplar QR-knappen till den.

Ligger i egen fil for att undvika citeringskrockar i patch_offline.py.
Anropas fran patch_offline.py:s main.
"""
import os

HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "appendQrRow.smali")

OLD_COND3 = (
    '    :cond_3\n'
    '    iget-object p1, p0, Lcom/omni/production/check/activity/ULockTestActivity;->dialogUtils:'
    'Lcom/omni/production/check/utils/DialogUtils;\n\n'
    '    const p2, 0x7f0f010e\n\n'
    '    invoke-virtual {p0, p2}, Lcom/omni/production/check/activity/ULockTestActivity;->'
    'getString(I)Ljava/lang/String;\n\n'
    '    move-result-object p2\n\n'
    '    invoke-virtual {p1, p2}, Lcom/omni/production/check/utils/DialogUtils;->'
    'showHint(Ljava/lang/String;)V\n'
)

NEW_COND3 = (
    '    :cond_3\n'
    '    iget-object p1, p0, Lcom/omni/production/check/activity/ULockTestActivity;->'
    'etScanMac:Landroid/widget/EditText;\n\n'
    '    invoke-virtual {p1}, Landroid/widget/EditText;->getText()Landroid/text/Editable;\n\n'
    '    move-result-object p1\n\n'
    '    invoke-virtual {p1}, Ljava/lang/Object;->toString()Ljava/lang/String;\n\n'
    '    move-result-object p1\n\n'
    '    invoke-virtual {p1}, Ljava/lang/String;->trim()Ljava/lang/String;\n\n'
    '    move-result-object p1\n\n'
    '    invoke-direct {p0, p2, p1}, Lcom/omni/production/check/activity/ULockTestActivity;->'
    'appendQrRow(Ljava/lang/String;Ljava/lang/String;)V\n'
)

OLD_STR = '<string name="tool_scan_qr">Scan QR_Code</string>'
NEW_STR = '<string name="tool_scan_qr">ADD QR TO CSV</string>'


def patch_add_qr_button(act_path, strings_path, write):
    t0 = open(act_path, encoding="utf-8").read()

    if "appendQrRow" in t0:
        print("   appendQrRow finns redan, hoppar over")
        return

    anchor = ".method protected onActivityResult(IILandroid/content/Intent;)V"
    if anchor not in t0:
        raise SystemExit("ULockTestActivity: hittar inte onActivityResult")

    helper = open(HELPER, encoding="utf-8").read()
    t = t0.replace(anchor, helper + anchor, 1)

    if OLD_COND3 not in t:
        raise SystemExit("ULockTestActivity: hittar inte cond_3-grenen")
    t = t.replace(OLD_COND3, NEW_COND3)

    write(act_path, t)
    print("patchad:", act_path, "(ADD QR TO CSV -> appendQrRow)")

    s0 = open(strings_path, encoding="utf-8").read()
    if OLD_STR not in s0:
        raise SystemExit("strings.xml: hittar inte tool_scan_qr")
    write(strings_path, s0.replace(OLD_STR, NEW_STR))
    print("patchad:", strings_path, "(knapptext -> ADD QR TO CSV)")
