"""
AfroERP Kenya — M-Pesa Daraja API integration for ERPNext.

Hooks into:
  - Sales Invoice (on_submit)  → initiate STK Push
  - Payment Entry (on_submit)  → verify M-Pesa transaction
  - Custom DocType: MPesa Transaction

Environment (from ERPNext Site Config or frappe.conf):
  MPESA_CONSUMER_KEY
  MPESA_CONSUMER_SECRET
  MPESA_SHORTCODE
  MPESA_PASSKEY
  MPESA_ENV   (sandbox | production)
"""

import frappe
import requests
import base64
import json
import os
from datetime import datetime


# ── Daraja Auth ───────────────────────────────────────────────
def get_mpesa_token() -> str:
    """Obtain Daraja OAuth2 bearer token."""
    key    = frappe.conf.get("MPESA_CONSUMER_KEY",    os.getenv("MPESA_CONSUMER_KEY", ""))
    secret = frappe.conf.get("MPESA_CONSUMER_SECRET", os.getenv("MPESA_CONSUMER_SECRET", ""))
    env    = frappe.conf.get("MPESA_ENV", "production")

    base_url = (
        "https://sandbox.safaricom.co.ke"
        if env == "sandbox"
        else "https://api.safaricom.co.ke"
    )
    credentials = base64.b64encode(f"{key}:{secret}".encode()).decode()
    resp = requests.get(
        f"{base_url}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {credentials}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def generate_password(shortcode: str, passkey: str, timestamp: str) -> str:
    raw = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(raw.encode()).decode()


# ── STK Push ──────────────────────────────────────────────────
@frappe.whitelist()
def initiate_stk_push(phone_number: str, amount: float, account_ref: str, description: str = "Payment"):
    """
    Initiate Lipa na M-Pesa STK push.
    Call from Sales Invoice submit hook or directly from UI.
    """
    shortcode = frappe.conf.get("MPESA_SHORTCODE", os.getenv("MPESA_SHORTCODE", ""))
    passkey   = frappe.conf.get("MPESA_PASSKEY",   os.getenv("MPESA_PASSKEY",   ""))
    env       = frappe.conf.get("MPESA_ENV", "production")
    callback_url = frappe.conf.get(
        "MPESA_CALLBACK_URL",
        f"{frappe.utils.get_url()}/api/method/afroerp_kenya.mpesa.callback"
    )
    base_url  = "https://sandbox.safaricom.co.ke" if env == "sandbox" else "https://api.safaricom.co.ke"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password  = generate_password(shortcode, passkey, timestamp)
    token     = get_mpesa_token()

    # Normalise phone: 07XXXXXXXX → 2547XXXXXXXX
    phone = str(phone_number).strip().replace(" ", "").replace("-", "")
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("+"):
        phone = phone[1:]

    payload = {
        "BusinessShortCode": shortcode,
        "Password":          password,
        "Timestamp":         timestamp,
        "TransactionType":   "CustomerPayBillOnline",
        "Amount":            int(amount),
        "PartyA":            phone,
        "PartyB":            shortcode,
        "PhoneNumber":       phone,
        "CallBackURL":       callback_url,
        "AccountReference":  account_ref[:12],
        "TransactionDesc":   description[:13],
    }

    resp = requests.post(
        f"{base_url}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        timeout=30,
    )
    data = resp.json()

    # Log to MPesa Transaction doctype
    doc = frappe.get_doc({
        "doctype":              "MPesa Transaction",
        "merchant_request_id":  data.get("MerchantRequestID"),
        "checkout_request_id":  data.get("CheckoutRequestID"),
        "phone_number":         phone,
        "amount":               amount,
        "account_reference":    account_ref,
        "response_code":        data.get("ResponseCode"),
        "response_description": data.get("ResponseDescription"),
        "status":               "pending",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return data


# ── STK Callback ──────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def callback():
    """Safaricom STK Push result callback."""
    data = frappe.request.get_json()
    stk_callback = data.get("Body", {}).get("stkCallback", {})

    checkout_id   = stk_callback.get("CheckoutRequestID")
    result_code   = stk_callback.get("ResultCode")
    result_desc   = stk_callback.get("ResultDesc")

    if not checkout_id:
        return {"ResultCode": 1, "ResultDesc": "Missing CheckoutRequestID"}

    # Find the pending transaction
    existing = frappe.db.get_value(
        "MPesa Transaction",
        {"checkout_request_id": checkout_id},
        "name",
    )
    if not existing:
        return {"ResultCode": 0, "ResultDesc": "OK"}

    doc = frappe.get_doc("MPesa Transaction", existing)

    if result_code == 0:
        # Success — extract metadata
        items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        meta  = {i["Name"]: i.get("Value") for i in items}
        doc.mpesa_receipt_number = meta.get("MpesaReceiptNumber")
        doc.transaction_date     = str(meta.get("TransactionDate", ""))
        doc.paid_by_phone        = str(meta.get("PhoneNumber", ""))
        doc.status               = "completed"
    else:
        doc.status               = "failed"
        doc.response_description = result_desc

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ResultCode": 0, "ResultDesc": "Accepted"}


# ── Sales Invoice hook ────────────────────────────────────────
def on_sales_invoice_submit(doc, method):
    """Auto-initiate STK push if customer has a phone number on the invoice."""
    if not frappe.conf.get("MPESA_AUTO_STK", False):
        return
    customer_phone = frappe.db.get_value("Customer", doc.customer, "mobile_no")
    if customer_phone and doc.grand_total > 0:
        try:
            initiate_stk_push(
                phone_number=customer_phone,
                amount=doc.grand_total,
                account_ref=doc.name,
                description=f"Invoice {doc.name}",
            )
        except Exception as exc:
            frappe.log_error(str(exc), "M-Pesa STK Push Failed")
