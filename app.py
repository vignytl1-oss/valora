import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="Valora | Finance Intelligence",
    page_icon="📊",
    layout="wide"
)

st.title("Valora")
st.caption(
    "Company Valuation & M&A Intelligence Platform"
)

# --------------------------------------------------
# DCF ENGINE
# --------------------------------------------------

def calculate_dcf(
    revenue,
    ebit_margin,
    tax_rate,
    growth_rate,
    da_pct,
    capex_pct,
    nwc_pct,
    wacc,
    terminal_growth,
    forecast_years,
    debt,
    cash,
    shares
):
    if revenue <= 0:
        raise ValueError("Revenue must be positive.")

    if wacc <= terminal_growth:
        raise ValueError(
            "WACC must be greater than terminal growth."
        )

    if wacc <= 0:
        raise ValueError("WACC must be positive.")

    if shares <= 0:
        raise ValueError("Shares outstanding must be positive.")

    years = []
    revenues = []
    ebit_values = []
    nopat_values = []
    da_values = []
    capex_values = []
    nwc_changes = []
    fcff_values = []
    pv_fcff_values = []

    previous_revenue = revenue

    for year in range(1, forecast_years + 1):
        forecast_revenue = revenue * (1 + growth_rate) ** year
        ebit = forecast_revenue * ebit_margin
        taxes = max(ebit, 0) * tax_rate
        nopat = ebit - taxes

        da = forecast_revenue * da_pct
        capex = forecast_revenue * capex_pct

        change_nwc = (
            forecast_revenue - previous_revenue
        ) * nwc_pct

        fcff = nopat + da - capex - change_nwc
        pv_fcff = fcff / ((1 + wacc) ** year)

        years.append(year)
        revenues.append(forecast_revenue)
        ebit_values.append(ebit)
        nopat_values.append(nopat)
        da_values.append(da)
        capex_values.append(capex)
        nwc_changes.append(change_nwc)
        fcff_values.append(fcff)
        pv_fcff_values.append(pv_fcff)

        previous_revenue = forecast_revenue

    if wacc <= terminal_growth:
     raise ValueError(
        "WACC must be greater than the terminal growth rate."
    )

    terminal_value = (
    fcff_values[-1] * (1 + terminal_growth)
    / (wacc - terminal_growth)
)

    pv_terminal_value = (
        terminal_value / ((1 + wacc) ** forecast_years)
    )

    enterprise_value = sum(pv_fcff_values) + pv_terminal_value
    equity_value = enterprise_value - debt + cash
    implied_share_price = equity_value / shares

    forecast = pd.DataFrame({
        "Year": years,
        "Revenue": revenues,
        "EBIT": ebit_values,
        "NOPAT": nopat_values,
        "D&A": da_values,
        "CapEx": capex_values,
        "Change in NWC": nwc_changes,
        "FCFF": fcff_values,
        "Present Value of FCFF": pv_fcff_values
    })

    return {
        "forecast": forecast,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "implied_share_price": implied_share_price,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "pv_fcff": sum(pv_fcff_values)
    }


# --------------------------------------------------
# MARKET DATA
# --------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def get_company_data(ticker):
    info = yf.Ticker(ticker).info

    revenue = info.get("totalRevenue")
    ebitda = info.get("ebitda")
    ebit = info.get("operatingIncome")
    debt = info.get("totalDebt") or 0
    cash = info.get("totalCash") or 0
    shares = info.get("sharesOutstanding")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    currency = info.get("currency") or "USD"

    if not revenue or revenue <= 0:
        raise ValueError(
            "Revenue data is unavailable for this ticker."
        )

    ebit_margin = (
        ebit / revenue
        if ebit is not None
        else info.get("operatingMargins")
    )

    if ebit_margin is None:
        raise ValueError(
            "Operating margin is unavailable. "
            "Try manual financial inputs."
        )

    da = info.get("depreciationAndAmortization")
    da_pct = (
        da / revenue
        if da is not None and revenue
        else 0.03
    )

    return {
        "name": info.get("longName") or ticker.upper(),
        "currency": currency,
        "revenue": float(revenue),
        "ebitda": ebitda,
        "ebit_margin": float(ebit_margin),
        "debt": float(debt),
        "cash": float(cash),
        "shares": float(shares or 0),
        "price": float(price or 0),
        "da_pct": max(float(da_pct), 0)
    }


def money(value, currency):
    if pd.isna(value):
        return "N/A"
    return f"{currency} {value:,.2f}"


# --------------------------------------------------
# NAVIGATION
# --------------------------------------------------

valuation_tab, screening_tab = st.tabs([
    "Company Valuation",
    "M&A Target Screening"
])


# ==================================================
# TAB 1: COMPANY VALUATION
# ==================================================

with valuation_tab:
    st.header("Company Valuation")

    source = st.radio(
        "Financial data source",
        ["Public company ticker", "Manual financial inputs"],
        horizontal=True
    )

    company = None

    if source == "Public company ticker":
        ticker = st.text_input(
            "Company ticker",
            value="KO",
            help="Examples: KO, PEP, MDLZ, AAPL"
        ).strip()

        if st.button("Load company data", type="primary"):
            try:
                st.session_state["valora_company"] = (
                    get_company_data(ticker)
                )
                st.session_state["valora_ticker"] = ticker.upper()
            except Exception as exc:
                st.error(f"Could not load company data: {exc}")

        company = st.session_state.get("valora_company")

        if company is None:
            st.info(
                "Enter a ticker and click Load company data. "
                "You can also choose manual financial inputs."
            )

    else:
        st.caption(
            "Enter financial figures in millions, except share "
            "price and shares outstanding. Use one consistent "
            "currency throughout."
        )

        with st.form("manual_financials"):
            manual_name = st.text_input(
                "Company name", "My Company"
            )
            currency = st.text_input("Currency code", "USD")
            revenue = st.number_input(
                "Annual revenue (millions)",
                min_value=0.01,
                value=1000.0
            )
            ebit_margin = st.number_input(
                "EBIT margin (%)",
                min_value=-100.0,
                max_value=100.0,
                value=15.0
            )
            debt = st.number_input(
                "Total debt (millions)",
                min_value=0.0,
                value=200.0
            )
            cash = st.number_input(
                "Cash (millions)",
                min_value=0.0,
                value=100.0
            )
            shares = st.number_input(
                "Shares outstanding (millions)",
                min_value=0.001,
                value=100.0
            )
            da_pct = st.number_input(
                "D&A as % of revenue",
                min_value=0.0,
                max_value=100.0,
                value=3.0
            )
            capex_pct = st.number_input(
                "CapEx as % of revenue",
                min_value=0.0,
                max_value=100.0,
                value=4.0
            )
            nwc_pct = st.number_input(
                "Net working capital as % of revenue",
                min_value=-100.0,
                max_value=100.0,
                value=1.0
            )

            submitted = st.form_submit_button(
                "Use these financials",
                type="primary"
            )

        if submitted:
            company = {
                "name": manual_name,
                "currency": currency.upper(),
                "revenue": revenue,
                "ebit_margin": ebit_margin / 100,
                "debt": debt,
                "cash": cash,
                "shares": shares,
                "price": 0,
                "da_pct": da_pct / 100
            }
            st.session_state["valora_company"] = company
            st.session_state["valora_ticker"] = "Manual input"

        company = st.session_state.get("valora_company")

    if company:
        st.divider()
        st.subheader(company["name"])

        currency = company["currency"]

        if source == "Public company ticker":
            st.caption(
                "Market data is supplied by Yahoo Finance and "
                "may be missing, delayed, or stale. Verify inputs "
                "before relying on the valuation."
            )

        st.markdown("#### DCF assumptions")

        c1, c2, c3 = st.columns(3)

        with c1:
            growth = st.slider(
                "Annual revenue growth (%)",
                min_value=-10.0,
                max_value=30.0,
                value=5.0,
                step=0.5
            ) / 100

            ebit_margin = st.slider(
                "EBIT margin (%)",
                min_value=-20.0,
                max_value=50.0,
                value=float(
                    np.clip(
                        company["ebit_margin"] * 100,
                        -20, 50
                    )
                ),
                step=0.5
            ) / 100

            tax_rate = st.slider(
                "Tax rate (%)", 0.0, 40.0, 21.0, 1.0
            ) / 100

        with c2:
            da_pct = st.slider(
                "D&A (% of revenue)",
                0.0, 15.0,
                float(np.clip(company["da_pct"] * 100, 0, 15)),
                0.5
            ) / 100

            capex_pct = st.slider(
                "CapEx (% of revenue)",
                0.0, 20.0, 4.0, 0.5
            ) / 100

            nwc_pct = st.slider(
                "NWC (% of revenue)",
                -10.0, 20.0, 1.0, 0.5
            ) / 100

        with c3:
            wacc = st.slider(
                "WACC (%)", 4.0, 20.0, 8.0, 0.25
            ) / 100

            terminal_growth = st.slider(
                "Terminal growth (%)",
                0.0, 5.0, 2.5, 0.25
            ) / 100

            forecast_years = st.selectbox(
                "Forecast period (years)", [3, 5, 7, 10], index=1
            )

        debt = company["debt"]
        cash = company["cash"]
        shares = company["shares"]

        st.caption(
            "Revenue, debt, cash and shares are taken from the "
            "selected source. In manual mode, the entered figures "
            "are used. Monetary financials are in millions."
        )

        try:
            result = calculate_dcf(
                revenue=company["revenue"],
                ebit_margin=ebit_margin,
                tax_rate=tax_rate,
                growth_rate=growth,
                da_pct=da_pct,
                capex_pct=capex_pct,
                nwc_pct=nwc_pct,
                wacc=wacc,
                terminal_growth=terminal_growth,
                forecast_years=forecast_years,
                debt=debt,
                cash=cash,
                shares=shares
            )

            st.divider()
            st.subheader("Valuation results")

            m1, m2, m3 = st.columns(3)

            m1.metric(
                "Enterprise value",
                money(result["enterprise_value"], currency)
            )
            m2.metric(
                "Equity value",
                money(result["equity_value"], currency)
            )

            if shares > 0:
                m3.metric(
                    "Implied value per share",
                    money(result["implied_share_price"], currency)
                )
            else:
                m3.metric("Implied value per share", "N/A")

            forecast = result["forecast"]

            fig = px.line(
                forecast,
                x="Year",
                y="FCFF",
                markers=True,
                title="Forecast Free Cash Flow to Firm"
            )
            fig.update_layout(
                xaxis_title="Forecast year",
                yaxis_title=f"FCFF ({currency} millions)"
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Forecast detail")
            st.dataframe(
                forecast.style.format({
                    col: "{:,.2f}"
                    for col in forecast.select_dtypes(
                        include="number"
                    ).columns
                }),
                use_container_width=True,
                hide_index=True
            )

            csv = forecast.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download DCF forecast (CSV)",
                data=csv,
                file_name="valora_dcf_forecast.csv",
                mime="text/csv"
            )

            st.markdown("#### WACC and terminal growth sensitivity")

            wacc_values = sorted(set([
                max(0.01, wacc - 0.02),
                max(0.01, wacc - 0.01),
                wacc,
                wacc + 0.01,
                wacc + 0.02
            ]))

            growth_values = sorted(set([
                max(0.0, terminal_growth - 0.01),
                max(0.0, terminal_growth - 0.005),
                terminal_growth,
                terminal_growth + 0.005,
                terminal_growth + 0.01
            ]))

            sensitivity = []

            for w in wacc_values:
                row = {"WACC": f"{w:.2%}"}

                for g in growth_values:
                    if g >= w:
                        row[f"Growth {g:.2%}"] = np.nan
                        continue

                    try:
                        sens = calculate_dcf(
                            revenue=company["revenue"],
                            ebit_margin=ebit_margin,
                            tax_rate=tax_rate,
                            growth_rate=growth,
                            da_pct=da_pct,
                            capex_pct=capex_pct,
                            nwc_pct=nwc_pct,
                            wacc=w,
                            terminal_growth=g,
                            forecast_years=forecast_years,
                            debt=debt,
                            cash=cash,
                            shares=shares
                        )
                        row[f"Growth {g:.2%}"] = (
                            sens["enterprise_value"]
                        )
                    except ValueError:
                        row[f"Growth {g:.2%}"] = np.nan

                sensitivity.append(row)

            sens_df = pd.DataFrame(sensitivity).set_index("WACC")
            st.dataframe(
                sens_df.style.format("{:,.2f}", na_rep="N/A"),
                use_container_width=True
            )

            st.caption(
                "Sensitivity values are enterprise values in "
                f"{currency} millions. These are model estimates, "
                "not market price targets or investment advice."
            )

        except ValueError as exc:
            st.error(str(exc))


# ==================================================
# TAB 2: M&A TARGET SCREENING
# ==================================================
@st.cache_data(ttl=86400, show_spinner=False)
def get_russell3000_universe():
    """Load a Russell 3000 proxy from IWV ETF holdings."""
    import requests
    import io

    url = "https://tickerinside.com/api/v1/fund/iwv.csv"

    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    if not response.text.strip():
        raise ValueError("The holdings source returned an empty file.")

    holdings = pd.read_csv(io.StringIO(response.text))
    holdings.columns = (
        holdings.columns.astype(str).str.strip().str.lower()
    )

    # Identify ticker, company name, and sector columns.
    ticker_col = next(
        (c for c in ["ticker", "symbol"] if c in holdings.columns),
        None,
    )
    name_col = next(
        (c for c in ["name", "company", "company_name"] if c in holdings.columns),
        None,
    )
    sector_col = next(
        (c for c in ["sector", "gics_sector"] if c in holdings.columns),
        None,
    )

    if ticker_col is None or name_col is None:
        raise ValueError(
            "The holdings CSV does not contain recognizable ticker "
            "and company-name columns. Columns received: "
            + ", ".join(holdings.columns)
        )

    result = pd.DataFrame({
        "Ticker": holdings[ticker_col].astype(str).str.strip(),
        "Company": holdings[name_col].astype(str).str.strip(),
        "Sector": (
            holdings[sector_col].astype(str).str.strip()
            if sector_col is not None
            else "Unknown"
        ),
    })

    result = result[
        result["Ticker"].ne("")
        & result["Ticker"].ne("nan")
        & result["Company"].ne("")
        & result["Company"].ne("nan")
    ].copy()

    result["Ticker"] = result["Ticker"].str.replace(
        ".", "-", regex=False
    )

    result = result.drop_duplicates(subset=["Ticker"])

    if len(result) < 2000:
        raise ValueError(
            f"Only {len(result)} holdings loaded; expected at least "
            "2,000. The downloaded data may be incomplete."
        )

    return result.reset_index(drop=True)
       
with screening_tab:
    st.header("Russell 3000 M&A Target Screening")
    st.info("M&A screening section is running.")
    st.write("Loading company universe...")

try:
        universe = get_russell3000_universe()

st.success(
            f"Universe loaded: {len(universe):,} companies."
        )

    st.dataframe(
            universe.head(25),
            use_container_width=True,
            hide_index=True,
        )

    st.download_button(
            "Download company universe (CSV)",
            data=universe.to_csv(index=False).encode("utf-8"),
            file_name="valora_russell3000_universe.csv",
            mime="text/csv",
        )

except Exception as e:
    st.error("Could not load the company universe.")
    st.exception(e)
# --------------------------------------------------
# FOOTER
# --------------------------------------------------
    st.divider()
    st.caption(
    "Valora is an educational financial analysis prototype. "
    "Verify all financial inputs and assumptions independently. "
    "It does not constitute investment advice."
   )
