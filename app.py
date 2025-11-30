import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# ---------- DB SETUP ----------
def get_connection():
    conn = sqlite3.connect("fitness_expenses.db", check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            category TEXT,
            description TEXT,
            amount REAL,
            payment_method TEXT,
            frequency TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_expense(date, category, desc, amount, payment_method, frequency, notes):
    conn = get_connection()
    conn.execute("""
        INSERT INTO expenses (date, category, description, amount, payment_method, frequency, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (date, category, desc, amount, payment_method, frequency, notes))
    conn.commit()
    conn.close()

def get_expenses(start_date=None, end_date=None, category=None):
    conn = get_connection()
    query = "SELECT * FROM expenses WHERE 1=1"
    params = []

    if start_date:
        query += " AND date >= ?"
        params.append(str(start_date))
    if end_date:
        query += " AND date <= ?"
        params.append(str(end_date))
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY date DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# ---------- STREAMLIT UI ----------
def main():
    st.set_page_config(page_title="Fitness Expense Tracker", page_icon="💪")

    init_db()

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
                "Other"
            ])
        with col2:
            payment_method = st.selectbox("Payment Method", ["UPI", "Card", "Cash", "Other"])
            frequency = st.selectbox("Frequency", ["One-time", "Monthly", "Yearly"])
        
        description = st.text_input("Description", placeholder="e.g. Monthly gym fee, Whey protein 1kg")
        notes = st.text_area("Notes (optional)")

        if st.button("Save Expense"):
            if amount > 0:
                add_expense(str(exp_date), category, description, amount, payment_method, frequency, notes)
                st.success("Expense saved ✅")
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
                    "Other"
                ]
            )

        df = get_expenses(start_date, end_date, filter_category)

        if not df.empty:
            st.subheader("Results")
            st.dataframe(df)

            total = df["amount"].sum()
            st.write(f"**Total in this view: ₹{total:,.2f}**")

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download as CSV", data=csv, file_name="fitness_expenses.csv", mime="text/csv")
        else:
            st.info("No expenses found for the selected filters.")

    else:  # Dashboard
        st.header("📊 Dashboard")

        df = get_expenses()
        if df.empty:
            st.info("No data yet. Add some expenses first.")
            return

        df["date"] = pd.to_datetime(df["date"])
        df["month"] = df["date"].dt.to_period("M").astype(str)

        col1, col2 = st.columns(2)
        with col1:
            by_month = df.groupby("month")["amount"].sum().reset_index()
            st.subheader("Monthly Total Spend")
            st.bar_chart(by_month.set_index("month"))

        with col2:
            by_cat = df.groupby("category")["amount"].sum().reset_index()
            st.subheader("Spend by Category")
            st.bar_chart(by_cat.set_index("category"))

        st.subheader("Raw Data")
        st.dataframe(df)

if __name__ == "__main__":
    main()
