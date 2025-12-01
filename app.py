import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

# ---------- CONFIG ----------
COLUMNS = ["date", "category", "description", "amount",
           "payment_method", "frequency", "notes"]

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ---------- GOOGLE SHEETS HELPERS ----------

@st.cache_resource
def get_worksheet():
    # Credentials from Streamlit secrets
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    client = gspread.authorize(creds)

    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    sh = client.open_by_key(sheet_id)

    ws = sh.sheet1

    # Do NOT trust what is there; just ensure header in A1:G1
    values = ws.get_all_values()
    if not values:
        # completely empty sheet
        ws.update("A1:G1", [COLUMNS])
    else:
        # force header to be correct
        ws.update("A1:G1", [COLUMNS])

    return ws


def add_expense(date_val, category, desc, amount, payment_method, frequency, notes):
    ws = get_worksheet()

    # Get existing values to know next row index
    values = ws.get_all_values()
    if not values:
        # should not happen because get_worksheet sets header,
        # but just in case:
        ws.update("A1:G1", [COLUMNS])
        next_row = 2
    else:
        next_row = len(values) + 1  # next empty row

    # Build row exactly matching A..G
    row = [
        str(date_val),
        category,
        desc or "",
        float(amount),
        payment_method,
        frequency,
        notes or "",
    ]

    # FORCE write to columns A..G of that row
    ws.update(f"A{next_row}:G{next_row}", [row])


def get_expenses(start_date=None, end_date=None, category=None):
    ws = get_worksheet()

    values = ws.get_all_values()

    # Nothing in sheet
    if not values or len(values) == 1:
        return pd.DataFrame(columns=COLUMNS)

    header = values[0]
    data_rows = values[1:]

    # If somehow header is wrong, treat all rows as data
    normalized_header = [str(x).strip().lower() for x in header]
    if normalized_header != COLUMNS:
        data_rows = values  # ignore header row
        header = COLUMNS
    else:
        header = COLUMNS

    # Normalise rows to correct length
    normalized_rows = []
    for row in data_rows:
        row = list(row)
        if len(row) < len(COLUMNS):
            row = row + [""] * (len(COLUMNS) - len(row))
        else:
            row = row[:len(COLUMNS)]
        normalized_rows.append(row)

    if not normalized_rows:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(normalized_rows, columns=COLUMNS)

    # Types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

    # Drop rows with no valid date
    df = df.dropna(subset=["date"])

    # Filters
    if start_date:
        df = df[df["date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["date"] <= pd.to_datetime(end_date)]
    if category and category != "All":
        df = df[df["category"] == category]

    # Latest first
    df = df.sort_values(by="date", ascending=False)

    return df


# ---------- STREAMLIT UI ----------

def main():
    st.set_page_config(page_title="Fitness Expense Tracker", page_icon="💪")

    st.title("💪 Fitness & Gym Expense Tracker")

    menu = ["Add Expense", "View Expenses", "Dashboard"]
    choice = st.sidebar.selectbox("Navigate", menu)

    if choice == "Add Expense":
        st.header("➕ Add Expense")

        col1, col2 = st.columns(2)
        with col1:
            exp_date = st.date_input("Date", value=date.today())
            amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0)
            category = st.selectbox("Category", [
                "Gym Membership",
                "Supplements",
                "Protein",
                "Equipment",
                "Travel to Gym",
                "Coaching",
                "Medical/Physio",
                "Luxury Items (Shoes/Clothes etc.)",
                "Other",
            ])
        with col2:
            payment_method = st.selectbox(
                "Payment Method", ["UPI", "Card", "Cash", "Other"]
            )
            frequency = st.selectbox("Frequency", ["One-time", "Monthly", "Yearly"])

        description = st.text_input(
            "Description", placeholder="e.g. Monthly gym fee, Whey protein 1kg"
        )
        notes = st.text_area("Notes (optional)")

        if st.button("Save Expense"):
            if amount > 0:
                add_expense(exp_date, category, description,
                            amount, payment_method, frequency, notes)
                st.success("Expense saved ✅ (stored in Google Sheets)")
            else:
                st.error("Amount must be greater than 0.")

    elif choice == "View Expenses":
        st.header("📋 View Expenses")

        col1, col2, col3 = st.columns(3)
        with col1:
            from_default = date.today().replace(day=1)
            start_date = st.date_input("From date", value=from_default)
        with col2:
            end_date = st.date_input("To date", value=date.today())
        with col3:
            filter_category = st.selectbox(
                "Filter by category",
                [
                    "All",
                    "Gym Membership",
                    "Supplements",
                    "Protein",
                    "Equipment",
                    "Travel to Gym",
                    "Coaching",
                    "Medical/Physio",
                    "Luxury Items (Shoes/Clothes etc.)",
                    "Other",
                ],
            )

        df = get_expenses(start_date, end_date, filter_category)

        if not df.empty:
            st.subheader("Results")
            st.dataframe(df)

            total = df["amount"].sum()
            st.write(f"**Total in this view: ₹{total:,.2f}**")

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download as CSV",
                data=csv,
                file_name="fitness_expenses.csv",
                mime="text/csv",
            )
        else:
            st.info("No expenses found for the selected filters.")

    else:  # Dashboard
        st.header("📊 Dashboard")

        df = get_expenses()
        if df.empty:
            st.info("No data yet. Add some expenses first.")
            return

        df_dash = df.copy()
        df_dash["month"] = df_dash["date"].dt.to_period("M").astype(str)

        col1, col2 = st.columns(2)
        with col1:
            by_month = df_dash.groupby("month")["amount"].sum().reset_index()
            st.subheader("Monthly Total Spend")
            st.bar_chart(by_month.set_index("month"))

        with col2:
            by_cat = df_dash.groupby("category")["amount"].sum().reset_index()
            st.subheader("Spend by Category")
            st.bar_chart(by_cat.set_index("category"))

        st.subheader("Raw Data")
        st.dataframe(df)


if __name__ == "__main__":
    main()
