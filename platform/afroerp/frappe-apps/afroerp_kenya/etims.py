"""
AfroERP Kenya — KRA eTIMS e-invoicing integration for ERPNext.

Submits tax invoices to KRA eTIMS (Kenya Revenue Authority Electronic Tax Invoice Management System)
on Sales Invoice submit. Handles:
  - Device initialisation
  - Invoice submission (OSCU — Online Sales Control Unit API)
  - Credit note submission
  - Tax receipt number storage on the ERPNext Invoice

Environment (frappe.conf or env vars):
  KRA_ETIMS_URL     — https://etims-api.kra.go.ke/etims-api (production)
                      https://etims-api.kra.go.ke/etims-api (sandbox uses same base with test PIN)
  KRA_DEVICE_SERIAL — OSCU device serial number
  KRA_PIN           — Taxpayer KRA PIN (e.g. P051999999Z)
  KRA_BRANCH_ID     — Branch ID (default: 00)
"""

import frappe
import requests
import json
import os
from datetime import datetime


def _conf(key: str, default: str = "") -> str:
    return frappe.conf.get(key, os.getenv(key, default))


ETIMS_BASE   = _conf("KRA_ETIMS_URL",     "https://etims-api.kra.go.ke/etims-api")
DEVICE_SERIAL = _conf("KRA_DEVICE_SERIAL", "")
KRA_PIN       = _conf("KRA_PIN",           "")
BRANCH_ID     = _conf("KRA_BRANCH_ID",     "00")


def _headers() -> dict:
    return {
        "Content-Type":  "application/json",
        "tin":           KRA_PIN,
        "bhfId":         BRANCH_ID,
        "cmcKey":        DEVICE_SERIAL,
    }


def _etims_post(path: str, payload: dict) -> dict:
    resp = requests.post(
        f"{ETIMS_BASE}{path}",
        json=payload,
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── Initialise device ─────────────────────────────────────────
@frappe.whitelist()
def initialise_device():
    """Initialise the OSCU device with KRA. Run once on setup."""
    payload = {
        "tin":          KRA_PIN,
        "bhfId":        BRANCH_ID,
        "dvcSrlNo":     DEVICE_SERIAL,
        "initOtpDt":    datetime.now().strftime("%Y%m%d%H%M%S"),
    }
    return _etims_post("/initializer/selectInitOtpInfo", payload)


# ── Submit invoice ────────────────────────────────────────────
def submit_invoice_to_etims(sales_invoice_name: str) -> dict:
    """
    Build eTIMS invoice payload from ERPNext Sales Invoice and submit to KRA.
    Called from on_submit hook.
    """
    inv = frappe.get_doc("Sales Invoice", sales_invoice_name)
    if inv.custom_etims_receipt_number:
        return {"already_submitted": True}

    # Build item lines
    item_list = []
    for idx, item in enumerate(inv.items, start=1):
        tax_type_code = "B"   # B = VAT 16% standard; A = exempt
        item_list.append({
            "itemSeq":   idx,
            "itemCd":    item.item_code[:20] if item.item_code else f"ITEM{idx:04d}",
            "itemClsCd": "5020230602",    # Goods category — adjust per item
            "itemNm":    item.item_name[:100],
            "bcd":       "",
            "pkgUnitCd": "U",             # Unit of measure code
            "pkg":       1,
            "qtyUnitCd": "U",
            "qty":       item.qty,
            "prc":       float(item.rate),
            "splyAmt":   float(item.amount),
            "dcRt":      0,
            "dcAmt":     0,
            "isrccCd":   "",
            "isrccNm":   "",
            "isrcRt":    0,
            "isrcAmt":   0,
            "vatCatCd":  tax_type_code,
            "exciseTxCatCd": "",
            "vatAmt":    float(item.amount) * 0.16,
            "exciseTxAmt": 0,
            "totAmt":    float(item.amount) * 1.16,
        })

    # Tax summary
    vat_total   = sum(float(i.amount) * 0.16 for i in inv.items)
    taxable     = float(inv.net_total or inv.grand_total)

    payload = {
        "tin":          KRA_PIN,
        "bhfId":        BRANCH_ID,
        "orgInvcNo":    0,
        "cisInvcNo":    inv.name.replace("-", ""),
        "custTin":      "",
        "custNm":       inv.customer_name[:100] if inv.customer_name else "",
        "rcptTyCd":     "S",        # S = Sale
        "pmtTyCd":      "01",       # 01 = Cash; 02 = Credit
        "salesSttsCd":  "02",       # 02 = completed
        "cfmDt":        inv.posting_date.strftime("%Y%m%d%H%M%S") if hasattr(inv.posting_date, "strftime") else datetime.now().strftime("%Y%m%d%H%M%S"),
        "salesDt":      (inv.posting_date or datetime.now()).strftime("%Y%m%d") if hasattr(inv.posting_date, "strftime") else datetime.now().strftime("%Y%m%d"),
        "stockRlsDt":   None,
        "cnclReqDt":    None,
        "cnclDt":       None,
        "rfdDt":        None,
        "rfdRsnCd":     None,
        "totItemCnt":   len(item_list),
        "taxblAmtA":    0,
        "taxblAmtB":    taxable,
        "taxblAmtC":    0,
        "taxblAmtD":    0,
        "taxRtA":       0,
        "taxRtB":       16,
        "taxRtC":       0,
        "taxRtD":       0,
        "taxAmtA":      0,
        "taxAmtB":      round(vat_total, 2),
        "taxAmtC":      0,
        "taxAmtD":      0,
        "totTaxblAmt":  taxable,
        "totTaxAmt":    round(vat_total, 2),
        "totAmt":       float(inv.grand_total),
        "prchrAcptcYn": "N",
        "remark":       "",
        "regrId":       frappe.session.user or "admin",
        "regrNm":       frappe.session.user or "admin",
        "modrId":       frappe.session.user or "admin",
        "modrNm":       frappe.session.user or "admin",
        "receipt": {
            "custTin":      "",
            "custMblNo":    "",
            "rptNo":        0,
            "rcptPbctDt":   "",
            "trdeNm":       "",
            "adrs":         "",
            "topMsg":       "Thank you for your business",
            "btmMsg":       "Powered by AfroERP",
            "prchrAcptcYn": "N",
        },
        "itemList": item_list,
    }

    result = _etims_post("/trnsSales/saveSales", payload)

    # Persist receipt number on invoice
    receipt_no = (
        result.get("data", {}).get("rcptNo")
        or result.get("resultCd")
        or "submitted"
    )
    frappe.db.set_value("Sales Invoice", sales_invoice_name, "custom_etims_receipt_number", receipt_no)
    frappe.db.commit()

    return result


# ── Sales Invoice submit hook ─────────────────────────────────
def on_sales_invoice_submit(doc, method):
    """Auto-submit to eTIMS on invoice submission if KRA PIN is configured."""
    if not KRA_PIN or not DEVICE_SERIAL:
        return
    try:
        submit_invoice_to_etims(doc.name)
    except Exception as exc:
        frappe.log_error(str(exc), "eTIMS Submission Failed")
        # Non-fatal — log but don't block the submit


# ── WhiteList for manual retry from UI ───────────────────────
@frappe.whitelist()
def retry_etims_submission(docname: str) -> dict:
    return submit_invoice_to_etims(docname)
