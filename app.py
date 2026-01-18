import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="Solana DeFi Adoption Dashboard",
    layout="wide"
)

# ==================================================
# SOLANA BRAND STYLING
# ==================================================
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0b0b0f;
        color: #ffffff;
    }
    h1, h2, h3 {
        color: #9d5cff;
    }
    .stMetric {
        background-color: #11111a;
        border-radius: 12px;
        padding: 12px;
    }
    div[data-testid="stMetricValue"] {
        color: #14f195;
    }
    </style>
    """,
    unsafe_allow_html=True
)

SOLANA_COLORS = ["#9d5cff", "#14f195", "#00ffa3", "#c77dff", "#7f6cff"]

# ==================================================
# HARD-DEFINED SOLANA PROTOCOLS (STABLE)
# ==================================================
SOLANA_PROTOCOLS = [
    {"name": "Raydium", "slug": "raydium"},
    {"name": "Orca", "slug": "orca"},
    {"name": "Jupiter", "slug": "jupiter"},
    {"name": "Marinade", "slug": "marinade"},
    {"name": "Drift", "slug": "drift"}
]

# ==================================================
# DATA FUNCTIONS
# ==================================================
@st.cache_data
def load_protocol_tvl(slug):
    url = f"https://api.llama.fi/protocol/{slug}"
    r = requests.get(url)

    if r.status_code != 200:
        return None

    data = r.json()

    if "tvl" not in data or not isinstance(data["tvl"], list):
        return None

    df = pd.DataFrame(data["tvl"])

    if df.empty or "totalLiquidityUSD" not in df.columns:
        return None

    df["date"] = pd.to_datetime(df["date"], unit="s")
    return df


@st.cache_data
def build_protocol_snapshot():
    rows = []

    for p in SOLANA_PROTOCOLS:
        hist = load_protocol_tvl(p["slug"])
        if hist is not None:
            rows.append({
                "name": p["name"],
                "slug": p["slug"],
                "tvl": hist["totalLiquidityUSD"].iloc[-1]
            })

    return pd.DataFrame(rows)


@st.cache_data
def compute_adoption_metrics():
    rows = []

    for p in SOLANA_PROTOCOLS:
        hist = load_protocol_tvl(p["slug"])
        if hist is None or len(hist) < 14:
            continue

        hist = hist.sort_values("date")
        hist["daily_change"] = hist["totalLiquidityUSD"].pct_change()

        growth_rate = (
            hist["totalLiquidityUSD"].iloc[-1]
            / hist["totalLiquidityUSD"].iloc[0]
            - 1
        )

        volatility = hist["daily_change"].rolling(7).std().mean()

        rows.append({
            "protocol": p["name"],
            "growth_rate": growth_rate,
            "volatility": volatility
        })

    return pd.DataFrame(rows)

# ==================================================
# LOAD DATA
# ==================================================
df_solana = build_protocol_snapshot()

# ==================================================
# HEADER
# ==================================================
st.title("🟣 Solana DeFi Adoption & User Behavior Dashboard")

st.markdown(
    """
This dashboard evaluates **adoption quality** across major Solana DeFi protocols.

Instead of relying solely on TVL, we analyze:
- **Growth momentum**
- **Capital stability**
- **Volatility risk**

The goal is to separate **real usage** from **short-term speculative capital**.
"""
)

# ==================================================
# SAFETY CHECK
# ==================================================
if df_solana.empty:
    st.error("No Solana DeFi protocol data could be loaded.")
    st.stop()

# ==================================================
# OVERVIEW METRICS
# ==================================================
st.subheader("Protocol Overview")

col1, col2, col3 = st.columns(3)

col1.metric("Protocols Analyzed", len(df_solana))

top_protocol = df_solana.sort_values(
    "tvl", ascending=False
).iloc[0]["name"]

col2.metric("Top TVL Protocol", top_protocol)

col3.metric(
    "Average TVL ($)",
    f"{df_solana['tvl'].mean():,.0f}"
)

# ==================================================
# TVL COMPARISON
# ==================================================
st.subheader("Protocol TVL Comparison")

fig_tvl = px.bar(
    df_solana.sort_values("tvl", ascending=False),
    x="name",
    y="tvl",
    color="name",
    color_discrete_sequence=SOLANA_COLORS,
    labels={"name": "Protocol", "tvl": "TVL (USD)"},
    title="Total Value Locked (TVL) Across Solana DeFi"
)

fig_tvl.update_layout(showlegend=False)
st.plotly_chart(fig_tvl, use_container_width=True)

# ==================================================
# PROTOCOL SELECTION
# ==================================================
st.subheader("Protocol Adoption Over Time")

protocol_map = dict(zip(df_solana["name"], df_solana["slug"]))

selected_protocol = st.selectbox(
    "Select a protocol",
    list(protocol_map.keys())
)

df_hist = load_protocol_tvl(protocol_map[selected_protocol])

# ==================================================
# TVL TREND + VOLATILITY
# ==================================================
if df_hist is None:
    st.warning("TVL history not available for this protocol.")
else:
    fig_trend = px.line(
        df_hist,
        x="date",
        y="totalLiquidityUSD",
        title=f"{selected_protocol} — TVL Trend",
        labels={"totalLiquidityUSD": "TVL (USD)"},
        color_discrete_sequence=["#14f195"]
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    df_hist["daily_change"] = df_hist["totalLiquidityUSD"].pct_change()
    df_hist["rolling_volatility"] = df_hist["daily_change"].rolling(7).std()

    fig_vol = px.line(
        df_hist,
        x="date",
        y="rolling_volatility",
        title=f"{selected_protocol} — TVL Volatility (7-Day)",
        labels={"rolling_volatility": "Volatility"},
        color_discrete_sequence=["#9d5cff"]
    )
    st.plotly_chart(fig_vol, use_container_width=True)

# ==================================================
# ADOPTION QUALITY SCORE
# ==================================================
st.subheader("Adoption Quality Score (AQS)")

metrics_df = compute_adoption_metrics()

if not metrics_df.empty:
    metrics_df["norm_growth"] = (
        metrics_df["growth_rate"] - metrics_df["growth_rate"].min()
    ) / (
        metrics_df["growth_rate"].max() - metrics_df["growth_rate"].min()
    )

    metrics_df["norm_volatility"] = (
        metrics_df["volatility"] - metrics_df["volatility"].min()
    ) / (
        metrics_df["volatility"].max() - metrics_df["volatility"].min()
    )

    metrics_df["adoption_quality_score"] = (
        metrics_df["norm_growth"] * 0.6 +
        (1 - metrics_df["norm_volatility"]) * 0.4
    )

    ranking_df = metrics_df.sort_values(
        "adoption_quality_score",
        ascending=False
    )

    st.dataframe(
        ranking_df[
            ["protocol", "growth_rate", "volatility", "adoption_quality_score"]
        ],
        use_container_width=True
    )

    fig_score = px.bar(
        ranking_df,
        x="protocol",
        y="adoption_quality_score",
        color="protocol",
        color_discrete_sequence=SOLANA_COLORS,
        title="Adoption Quality Score by Protocol"
    )

    fig_score.update_layout(showlegend=False)
    st.plotly_chart(fig_score, use_container_width=True)

# ==================================================
# INTERPRETATION
# ==================================================
st.subheader("How to Interpret This Dashboard")

st.markdown(
    """
### 🧠 Key Takeaways
- **High AQS** → Sustainable adoption and sticky capital  
- **High growth + high volatility** → Speculative inflows  
- **Low volatility + steady growth** → Mature protocol usage  

This framework mirrors how professional Web3 analysts evaluate
**protocol health**, not hype.
"""
)

st.caption(
    "Data Source: DefiLlama | Framework: Growth–Stability Adoption Model"
)
