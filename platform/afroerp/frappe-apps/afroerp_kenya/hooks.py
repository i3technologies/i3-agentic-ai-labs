from . import mpesa, etims

app_name        = "afroerp_kenya"
app_title       = "AfroERP Kenya"
app_publisher   = "i3 Technologies"
app_description = "Kenya-specific ERPNext extensions: M-Pesa Daraja + KRA eTIMS"
app_version     = "1.0.0"
app_license     = "MIT"

# ── Doc Events ───────────────────────────────────────────────
doc_events = {
    "Sales Invoice": {
        "on_submit": [
            "afroerp_kenya.mpesa.on_sales_invoice_submit",
            "afroerp_kenya.etims.on_sales_invoice_submit",
        ],
    },
}

# ── Custom Fields ─────────────────────────────────────────────
# Applied via fixtures/custom_field.json — see fixtures/ directory
fixtures = ["Custom Field", "Custom Script"]
