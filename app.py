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

with screening_tab:
    st.header("M&A Target Screening")

    st.warning(
        "The initial target universe below is fictional sample "
        "data for demonstrating the screening methodology. "
        "It does not identify actual acquisition targets."
    )

    sample = pd.DataFrame([
        ["Target A", "Food & Beverage", 450, 0.08, 0.18, 1.2, 9.0, 5],
        ["Target B", "Food & Beverage", 700, 0.12, 0.15, 1.8, 11.0, 4],
        ["Target C", "Consumer Goods", 320, 0.15, 0.20, 0.8, 10.0, 4],
        ["Target D", "Food & Beverage", 900, 0.04, 0.12, 2.5, 8.0, 3],
        ["Target E", "Packaging", 280, 0.10, 0.17, 1.0, 7.5, 4],
        ["Target F", "Consumer Goods", 600, 0.06, 0.14, 1.4, 9.5, 5],
        ["Target G", "Food & Beverage", 150, 0.18, 0.22, 0.5, 12.0, 3],
        ["Target H", "Packaging", 500, 0.09, 0.16, 1.1, 8.5, 4],
        ["Target I", "Personal Care", 380, 0.13, 0.19, 0.7, 10.0, 4],
        ["Target J", "Food & Beverage", 1100, 0.05, 0.11, 2.0, 7.0, 5],
        ["Target K", "Consumer Goods", 240, 0.11, 0.13, 1.6, 8.0, 3],
        ["Target L", "Personal Care", 750, 0.07, 0.21, 0.9, 13.0, 4],
    ], columns=[
        "Target", "Sector", "Revenue", "Growth",
        "EBITDA_Margin", "Net_Debt_EBITDA",
        "EV_EBITDA", "Strategic_Fit"
    ])

    st.caption(
        "Revenue is in illustrative currency millions. "
        "Strategic Fit is a sample score from 1 to 5."
    )

    f1, f2, f3 = st.columns(3)

    with f1:
        acquirer = st.selectbox(
            "Acquirer profile",
            ["Coca-Cola", "PepsiCo", "Other / Custom"]
        )

        sectors = st.multiselect(
            "Target sectors",
            options=sorted(sample["Sector"].unique()),
            default=sorted(sample["Sector"].unique())
        )

    with f2:
        min_revenue = st.number_input(
            "Minimum revenue (millions)",
            min_value=0,
            value=100,
            step=50
        )

        min_growth = st.slider(
            "Minimum revenue growth (%)",
            0, 25, 5
        ) / 100

    with f3:
        min_margin = st.slider(
            "Minimum EBITDA margin (%)",
            0, 40, 12
        ) / 100

        max_leverage = st.slider(
            "Maximum Net Debt / EBITDA",
            0.0, 5.0, 2.5, 0.1
        )

    max_multiple = st.slider(
        "Maximum EV / EBITDA",
        4.0, 20.0, 12.0, 0.5
    )

    st.markdown("#### Scoring weights")

    w1, w2, w3, w4, w5 = st.columns(5)

    with w1:
        growth_weight = st.number_input(
            "Growth (%)", 0, 100, 25
        )
    with w2:
        margin_weight = st.number_input(
            "Profitability (%)", 0, 100, 25
        )
    with w3:
        leverage_weight = st.number_input(
            "Leverage (%)", 0, 100, 15
        )
    with w4:
        valuation_weight = st.number_input(
            "Valuation (%)", 0, 100, 15
        )
    with w5:
        fit_weight = st.number_input(
            "Strategic fit (%)", 0, 100, 20
        )

    weights = [
        growth_weight, margin_weight, leverage_weight,
        valuation_weight, fit_weight
    ]

    if sum(weights) == 0:
        st.error("At least one scoring weight must be positive.")
    else:
        filtered = sample[
            sample["Sector"].isin(sectors)
            & (sample["Revenue"] >= min_revenue)
            & (sample["Growth"] >= min_growth)
            & (sample["EBITDA_Margin"] >= min_margin)
            & (sample["Net_Debt_EBITDA"] <= max_leverage)
            & (sample["EV_EBITDA"] <= max_multiple)
        ].copy()

        def normalize(series):
            low = series.min()
            high = series.max()

            if high == low:
                return pd.Series(
                    1.0, index=series.index
                )

            return (series - low) / (high - low)

        if not filtered.empty:
            # Score relative to the candidates that pass the filters.
            growth_score = normalize(filtered["Growth"])
            margin_score = normalize(filtered["EBITDA_Margin"])
            leverage_score = 1 - normalize(
                filtered["Net_Debt_EBITDA"]
            )
            valuation_score = 1 - normalize(
                filtered["EV_EBITDA"]
            )
            fit_score = (
                filtered["Strategic_Fit"] - 1
            ) / 4

            weight_total = sum(weights)

            filtered["Score"] = 100 * (
                growth_score * growth_weight
                + margin_score * margin_weight
                + leverage_score * leverage_weight
                + valuation_score * valuation_weight
                + fit_score * fit_weight
            ) / weight_total

            filtered = filtered.sort_values(
                "Score", ascending=False
            ).reset_index(drop=True)

            filtered.insert(
                0, "Rank", np.arange(1, len(filtered) + 1)
            )

            st.subheader(
                f"Shortlist for {acquirer}"
            )
            st.write(
                f"{len(filtered)} fictional candidates meet "
                "the current filters."
            )

            display_df = filtered.copy()
            display_df["Growth"] *= 100
            display_df["EBITDA_Margin"] *= 100

            st.dataframe(
                display_df.style.format({
                    "Revenue": "{:,.1f}",
                    "Growth": "{:.1f}%",
                    "EBITDA_Margin": "{:.1f}%",
                    "Net_Debt_EBITDA": "{:.2f}x",
                    "EV_EBITDA": "{:.1f}x",
                    "Score": "{:.1f}"
                }),
                use_container_width=True,
                hide_index=True
            )

            fig = px.bar(
                filtered.head(5),
                x="Target",
                y="Score",
                title="Top-ranked sample candidates",
                text_auto=".1f"
            )
            st.plotly_chart(
                fig, use_container_width=True
            )

            st.download_button(
                "Download M&A shortlist (CSV)",
                data=filtered.to_csv(index=False).encode("utf-8"),
                file_name="valora_ma_shortlist.csv",
                mime="text/csv"
            )

        else:
            st.info(
                "No sample companies meet all the current filters. "
                "Try relaxing one or more criteria."
            )

    st.caption(
        "Scores are screening aids, not acquisition "
        "recommendations. The current sample companies and "
        "their financial data are fictional."
    )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()
st.caption(
    "Valora is an educational financial analysis prototype. "
    "Verify all financial inputs and assumptions independently. "
    "It does not constitute investment advice."
)


