import streamlit as st
import pandas as pd
import http.client
import json
import os
import matplotlib.pyplot as plt
import altair as alt
from datetime import datetime, timedelta
import requests
import re
# Set page configuration
st.set_page_config(page_title="Stock Data Analysis", layout="wide", 
                   initial_sidebar_state="expanded",
                   menu_items={
                       'Get Help': 'https://www.nse.com/',
                       'Report a bug': "mailto:support@stockanalysis.com",
                       'About': "# Stock Analysis Dashboard\nA comprehensive tool for analyzing Indian stocks"
                   })

# Apply custom CSS for better UI
st.markdown("""
    <style>
    .main {
        background-color: #f5f8fa;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        padding: 10px 20px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4e7aa2 !important;
        color: white !important;
    }
    h1, h2, h3 {
        color: #1e3d59;
    }
    .metric-card {
        background-color: white;
        border: 1px solid #e6e6e6;
        border-radius: 5px;
        padding: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .sidebar .sidebar-content {
        background-color: #1e3d59;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Function to load data
@st.cache_data
def load_stock_data():
    try:
        return pd.read_csv(r'D:\Downloads\deliverable\scripts\EQUITY_L1.csv')
    except FileNotFoundError:
        st.error("stock_data.csv not found. Please make sure the file exists in the current directory.")
        return pd.DataFrame({'Symbol': [], 'Company Name': []})

# Function to make API calls
def fetch_api_data(endpoint, symbol, host="yahoo-finance15.p.rapidapi.com", api_key=None):
    conn = http.client.HTTPSConnection(host)
    if not api_key:
        api_key = user_api_key
    
    headers = {
        'x-rapidapi-key': f"{user_api_key}",
        'x-rapidapi-host': host
    }
    
    try:
        conn.request("GET", endpoint.format(symbol=symbol), headers=headers)
        res = conn.getresponse()
        data = res.read()
        if isinstance(data, bytes):
            return json.loads(data.decode('utf-8'))
        elif isinstance(data, str):
            return json.loads(data)
        return data
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

# Function to fetch EPS data
def fetch_eps_data(symbol,api_key):
    conn = http.client.HTTPSConnection("indian-stock-exchange-api2.p.rapidapi.com")
    if not api_key:
        api_key = user_api_key
    headers = {
        'x-rapidapi-key': f"{user_api_key}",
        'x-rapidapi-host': "indian-stock-exchange-api2.p.rapidapi.com"
    }
    
    try:
        conn.request("GET", f"/stock_forecasts?stock_id={symbol}&measure_code=EPS&period_type=Annual&data_type=Actuals&age=Current", headers=headers)
        res = conn.getresponse()
        data = res.read()
        if isinstance(data, bytes):
            return json.loads(data.decode('utf-8'))
        else:
            return data
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

# Function to fetch price target data
def fetch_price_target_data(symbol,api_key):
    conn = http.client.HTTPSConnection("indian-stock-exchange-api2.p.rapidapi.com")
    if not api_key:
        api_key = user_api_key
    headers = {
        'x-rapidapi-key': f"{user_api_key}",
        'x-rapidapi-host': "indian-stock-exchange-api2.p.rapidapi.com"
    }
    
    try:
        conn.request("GET", f"/stock_target_price?stock_id={symbol}", headers=headers)
        res = conn.getresponse()
        data = res.read()
        if isinstance(data, bytes):
            return json.loads(data.decode('utf-8'))
        else:
            return data
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

# Function to parse income statement data
def parse_financial_data(financial_data):
    records = []
    for record in financial_data:
        end_date = record.get('endDate', {}).get('fmt', 'N/A')
        total_revenue = record.get('totalRevenue', {}).get('raw', 0)
        net_income = record.get('netIncome', {}).get('raw', 0)
        ebit = record.get('ebit', {}).get('raw', 0)
        gross_profit = record.get('grossProfit', {}).get('raw', 0) if 'grossProfit' in record else total_revenue-net_income
        
        records.append({
            'End Date': end_date,
            'Total Revenue': total_revenue,
            'Net Income': net_income,
            'EBIT': ebit,
            'Gross Profit': gross_profit
        })
    return records

# Function to parse balance sheet data
def parse_balance_sheet(balance_data):
    records = []
    key_metrics = [
        'totalAssets', 'totalLiab', 'totalStockholderEquity', 
        'cash', 'shortTermInvestments', 'longTermDebt',
        'propertyPlantEquipment', 'goodWill', 'intangibleAssets'
    ]
    for record in balance_data:
        parsed_record = {
            'Max Age': record.get('maxAge', 'N/A'),
            'End Date (Raw)': record.get('endDate', {}).get('raw', 'N/A'),
            'End Date (Formatted)': record.get('endDate', {}).get('fmt', 'N/A'),
        }
        for metric in key_metrics:
            value = record.get(metric, {}).get('raw', 0)
            if value in [None, 'N/A']:
                value = 0
            parsed_record[metric] = value
        records.append(parsed_record)
    return records

# Function to format numbers for display
def format_large_number(num):
    if num is None or num == 'N/A':
        return 'N/A'
    
    # Convert to numeric value if it's a string
    try:
        num = float(num)
    except (ValueError, TypeError):
        return str(num)  # Return as string if conversion fails
    
    if abs(num) >= 1_000_000_000:
        return f"{num/1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000:
        return f"{num/1_000_000:.2f}M"
    elif abs(num) >= 1_000:
        return f"{num/1_000:.2f}K"
    else:
        return f"{num:.2f}"

# Function to extract EPS data
def parse_eps_data(eps_data):
    # Extract Actuals
    actuals_list = []
    for period in eps_data.get('periods', []):
        if period.get("Actuals") and period["Actuals"].get("Actual"):
            for actual in period["Actuals"]["Actual"]:
                actuals_list.append({
                    "FiscalYear": period["FiscalPeriod"]["Year"],
                    "ReportedEPS": actual.get("Reported"),
                    "SurprisePercent": actual.get("SurprisePercent"),
                    "SurpriseMean": actual.get("SurpriseMean"),
                    "SUE": actual.get("StandardizedUnexpectedEarnings"),
                    "NumberOfEstimates": actual.get("NumberOfEstimates"),
                    "ReportedDate": actual.get("ReportedDate")
                })

    # Extract Estimates
    estimates_list = []
    for period in eps_data.get('periods', []):
        if period.get("Estimates") and period["Estimates"].get("Estimate"):
            for est in period["Estimates"]["Estimate"]:
                estimates_list.append({
                    "FiscalYear": period["FiscalPeriod"]["Year"],
                    "Mean": est.get("Mean"),
                    "High": est.get("High"),
                    "Low": est.get("Low"),
                    "Median": est.get("Median"),
                    "StandardDeviation": est.get("StandardDeviation"),
                    "SmartEstimate": est.get("SmartEstimate"),
                    "NumberOfEstimates": est.get("NumberOfEstimates"),
                })
    
    return pd.DataFrame(actuals_list), pd.DataFrame(estimates_list)

# Function to parse price target data
def parse_price_target_data(price_data):
    if not price_data:
        return pd.DataFrame(), pd.DataFrame()
        
    # Convert price target snapshots to DataFrame
    try:
        price_df = pd.DataFrame(price_data.get('priceTargetSnapshots', {}).get('PriceTargetSnapshot', []))
        if not price_df.empty:
            price_df['Age'] = pd.Categorical(
                price_df['Age'], 
                categories=['NinetyDaysAgo', 'SixtyDaysAgo', 'ThirtyDaysAgo', 'OneWeekAgo'], 
                ordered=True
            )
            price_df = price_df.sort_values("Age")
            
        # Convert recommendation snapshots to DataFrame
        recommend_snapshots = price_data.get('recommendationSnapshots', {}).get('RecommendationSnapshot', [])
        recommend_data = []
        
        for snap in recommend_snapshots:
            buy_count = 0
            hold_count = 0
            sell_count = 0
            
            if 'Statistics' in snap and 'Statistic' in snap['Statistics']:
                for stat in snap['Statistics']['Statistic']:
                    if stat.get('Recommendation') in [1, 2]:
                        buy_count += stat.get('NumberOfAnalysts', 0)
                    elif stat.get('Recommendation') == 3:
                        hold_count += stat.get('NumberOfAnalysts', 0)
                    elif stat.get('Recommendation') in [4, 5]:
                        sell_count += stat.get('NumberOfAnalysts', 0)
            
            recommend_data.append({
                'Age': snap.get('Age'),
                'Mean': snap.get('Mean'),
                'Buy': buy_count,
                'Hold': hold_count,
                'Sell': sell_count,
            })
            
        recommend_df = pd.DataFrame(recommend_data)
        if not recommend_df.empty:
            recommend_df['Age'] = pd.Categorical(
                recommend_df['Age'], 
                categories=['NinetyDaysAgo', 'SixtyDaysAgo', 'ThirtyDaysAgo', 'OneWeekAgo'], 
                ordered=True
            )
            recommend_df = recommend_df.sort_values("Age")
        
        return price_df, recommend_df
        
    except Exception as e:
        st.error(f"Error parsing price target data: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# Function to fetch latest file from GitHub
def fetch_latest_file_from_github(repo_owner, repo_name, file_path, token=None):
    """
    Fetch file content from GitHub repository
    """
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    
    # GitHub API endpoint for getting file content
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{file_path}"
    
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            content = response.json()
            # Get the raw content URL
            download_url = content['download_url']
            # Download the actual file content
            file_content = requests.get(download_url).content
            return file_content
        else:
            return None
    except Exception as e:
        st.error(f"Error fetching file from GitHub: {str(e)}")
        return None

# Function to fetch latest stock screener file
def fetch_latest_stock_screener_file(repo_owner, repo_name, token=None):
    """Fetch the latest Stock-Screener file from GitHub"""
    # First, get the list of files in the repository
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents"
    
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        files = response.json()
        
        # Filter for Stock-Screener files and extract their numbers
        screener_files = []
        for file in files:
            if isinstance(file, dict) and file.get('name', '').startswith('Stock-Screener'):
                match = re.search(r'Stock-Screener(\d+)\.xlsx', file['name'])
                if match:
                    number = int(match.group(1))
                    screener_files.append((number, file['name']))
        
        if not screener_files:
            return None
            
        # Sort by the number and get the latest
        latest_file = max(screener_files, key=lambda x: x[0])[1]
        
        # Now fetch the content of the latest file
        file_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{latest_file}"
        response = requests.get(file_url, headers=headers)
        response.raise_for_status()
        file_data = response.json()
        
        # Get the download URL and fetch the actual content
        download_url = file_data.get('download_url')
        if download_url:
            content_response = requests.get(download_url)
            content_response.raise_for_status()
            return content_response.content
            
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest Stock-Screener file: {str(e)}")
        return None

# Load the stock data
df_stocks = load_stock_data()
if not df_stocks.empty:
    df_stocks = df_stocks[df_stocks['Symbol'].str.isalpha()]

# App title and description
with st.container():
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title('🚀 Stock Data Analysis Dashboard')
        st.markdown("""
        <div style="background-color: #e0e7f1; padding: 10px; border-radius: 5px; margin-bottom: 20px;">
        This application provides comprehensive stock data and analysis for selected companies on the Indian stock market.
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.image("https://via.placeholder.com/150x150.png?text=Stock+Analysis", width=150)

# Sidebar for selections
with st.sidebar:
    st.image("https://via.placeholder.com/250x80.png?text=Stock+Analysis", width=250)
    st.markdown("## 📈 Select Stock")
    # User-provided API Key from sidebar
    st.sidebar.markdown("## 🔐 API Key Configuration")
    user_api_key = st.sidebar.text_input("Enter your RapidAPI Key", type="password")

    # Fallback if no key is entered
    if not user_api_key:
        st.sidebar.warning("Using default API key. For better security, enter your own key.")
        user_api_key = "8b0ab77af5mshc73fbfdbec7278ap1422fejsnb77c07072aca"

    if not df_stocks.empty:
        stock_name = st.selectbox('Choose a Company', df_stocks['Company Name'].unique(), index=0)
        
        # Fetch the symbol for the selected stock name
        symbol = df_stocks[(df_stocks['Company Name'] == stock_name) & 
                          (df_stocks['Symbol'].str.isalpha())]['Symbol'].values[0]
        
        st.markdown(f"**Selected Symbol:** `{symbol}`")
        
        # Add .NS suffix for Indian stocks with a more visual selector
        suffix = st.radio("Stock Exchange", ["NS (NSE)", "BO (BSE)"], index=0, horizontal=True,
                          help="Select the exchange where you want to analyze this stock")
                          
        if suffix == "NS (NSE)":
            api_symbol = f"{symbol}.NS"
        else:
            api_symbol = f"{symbol}.BO"
            
        st.markdown(f"**API Symbol:** `{api_symbol}`")
        
        st.markdown("---")
        st.markdown("### 🔍 Analysis Options")
        analysis_depth = st.select_slider(
            "Analysis Depth",
            options=["Basic", "Standard", "Detailed"],
            value="Standard",
            help="Select the level of detail for your analysis"
        )
        
        # Additional sidebar info
        with st.expander("About This App"):
            st.markdown("""
            This dashboard provides:
            - Company profiles
            - Financial metrics
            - Income statements
            - Balance sheets
            - EPS data and forecasts
            - Price targets and analyst recommendations
            - Latest market news
            - FII & bulk deals data
            """)
    else:
        st.error("No stock data available")
 
# Main content area with tabs
if not df_stocks.empty:
    # Replace tabs list with direct radio button selection
    selected_view = st.radio(
        "Select Analysis View",
        [
            "📊 Overview", 
            "💼 Company Profile", 
            "💰 Financial Data", 
            "📝 Income Statement", 
            "📒 Balance Sheet",
            "📈 EPS Analysis",
            "🎯 Price Targets",
            "📰 Market News",
            "🏦 FII & Bulk Deals",
            "🌟 Top Performers",
            "🧠 Stock Recommendation Analysis"
        ],
        horizontal=True
    )
    st.markdown("---")

    # Replace all "with tabs[index]:" blocks with if/elif statements
    if selected_view == "📊 Overview":
        st.header(f"Quick Overview: {stock_name} ({symbol})")
        overview_col1, overview_col2 = st.columns([2, 1])
        
        with overview_col1:
            with st.spinner("Loading company data..."):
                financial_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=financial-data", api_symbol,api_key=user_api_key)
                profile_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=asset-profile", api_symbol,api_key=user_api_key)
                
                if financial_data and isinstance(financial_data, dict) and 'body' in financial_data:
                    body = financial_data['body']
                    
                    # Key metrics to display in overview
                    st.subheader("Key Metrics")
                    metric_cols = st.columns(3)
                    
                    with metric_cols[0]:
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        current_price = body.get('currentPrice', {}).get('fmt', 'N/A')
                        st.metric("Current Price", current_price)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with metric_cols[1]:
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        recommendation = body.get('recommendationKey', 'N/A').capitalize()
                        st.metric("Analyst Recommendation", recommendation)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with metric_cols[2]:
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        revenue_growth = body.get('revenueGrowth', {}).get('fmt', 'N/A')
                        st.metric("Revenue Growth", revenue_growth)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
        with overview_col2:
            st.subheader("Company Industry")
            if profile_data and 'body' in profile_data:
                industry = profile_data.get('body', {}).get('industry', 'N/A')
                sector = profile_data.get('body', {}).get('sector', 'N/A')
                employees = profile_data.get('body', {}).get('fullTimeEmployees', 'N/A')
                
                st.markdown(f"""
                <div class="metric-card">
                <p><strong>Industry:</strong> {industry}</p>
                <p><strong>Sector:</strong> {sector}</p>
                <p><strong>Employees:</strong> {employees}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Quick summary
        st.subheader("Brief Description")
        if profile_data and 'body' in profile_data:
            summary = profile_data.get('body', {}).get('longBusinessSummary', 'No description available')
            st.markdown(f'<div style="background-color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">{summary[:300]}...</div>', unsafe_allow_html=True)
            if st.button("Read Full Description"):
                st.markdown(f'<div style="background-color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">{summary}</div>', unsafe_allow_html=True)
    
    elif selected_view == "💼 Company Profile":
        st.header("Company Profile")
        with st.spinner("Fetching company profile..."):
            profile_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=asset-profile", api_symbol,api_key=user_api_key)
            
            if profile_data and 'body' in profile_data:
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("Basic Info")
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    info_data = {
                        "Symbol": profile_data.get('meta', {}).get('symbol', 'N/A'),
                        "Address": profile_data.get('body', {}).get('address1', 'N/A'),
                        "Website": profile_data.get('body', {}).get('website', 'N/A'),
                        "Industry": profile_data.get('body', {}).get('industry', 'N/A'),
                        "Sector": profile_data.get('body', {}).get('sector', 'N/A'),
                        "Employees": profile_data.get('body', {}).get('fullTimeEmployees', 'N/A')
                    }
                    
                    for key, value in info_data.items():
                        if key == "Website" and value != 'N/A':
                            st.markdown(f"**{key}:** [{value}]({value})")
                        else:
                            st.markdown(f"**{key}:** {value}")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col2:
                    st.subheader("Company Description")
                    description = profile_data.get('body', {}).get('longBusinessSummary', 'No description available')
                    st.markdown(f'<div class="metric-card" style="height: 300px; overflow-y: auto;">{description}</div>', unsafe_allow_html=True)
                
                # Company Officers section with expandable details
                st.subheader("Company Officers")
                officers = profile_data.get('body', {}).get('companyOfficers', [])
                
                if officers:
                    officer_cols = st.columns(3)
                    for i, officer in enumerate(officers[:6]):  # Display top 6 officers
                        with officer_cols[i % 3]:
                            name = officer.get('name', 'N/A')
                            title = officer.get('title', 'N/A')
                            
                            with st.expander(f"{name} - {title}"):
                                st.markdown(f"**Age:** {officer.get('age', 'N/A')}")
                                if 'totalPay' in officer:
                                    pay = officer['totalPay'].get('fmt', 'N/A')
                                    st.markdown(f"**Total Pay:** {pay}")
                else:
                    st.info("No company officer information available.")
    
    elif selected_view == "💰 Financial Data":
        st.header("Financial Data")
        with st.spinner("Fetching financial data..."):
            try:
                financial_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=financial-data", api_symbol,api_key=user_api_key)
                
                if financial_data and isinstance(financial_data, dict) and 'body' in financial_data:
                    body = financial_data['body']
                    
                    # Financial highlights in a card layout
                    st.subheader("Financial Highlights")
                    
                    highlight_cols = st.columns(4)
                    with highlight_cols[0]:
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        current_price = body.get('currentPrice', {}).get('fmt', 'N/A')
                        st.metric("Current Price", current_price)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with highlight_cols[1]:
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        target_mean = body.get('targetMeanPrice', {}).get('fmt', 'N/A')
                        st.metric("Target Mean Price", target_mean)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with highlight_cols[2]:
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        recommendation = body.get('recommendationKey', 'N/A').capitalize()
                        st.metric("Recommendation", recommendation)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with highlight_cols[3]:
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        analyst_count = body.get('numberOfAnalystOpinions', {}).get('fmt', 'N/A')
                        st.metric("Analyst Count", analyst_count)
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Detailed Financial Data
                    st.subheader("Detailed Financial Data")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("##### Balance Sheet Metrics")
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        
                        fin_metrics = {
                            "Total Cash": body.get('totalCash', {}).get('fmt', 'N/A'),
                            "Total Debt": body.get('totalDebt', {}).get('fmt', 'N/A'),
                            # "Quick Ratio": body.get('quickRatio', {}).get('fmt', 'N/A'),
                            #"Current Ratio": body.get('currentRatio', {}).get('fmt', 'N/A'),
                            #"Debt to Equity": body.get('debtToEquity', {}).get('fmt', 'N/A')
                        }
                        
                        for key, value in fin_metrics.items():
                            st.markdown(f"**{key}:** {value}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("##### Income Metrics")
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        
                        income_metrics = {
                            "Total Revenue": body.get('totalRevenue', {}).get('fmt', 'N/A'),
                            #"EBITDA": body.get('ebitda', {}).get('fmt', 'N/A'),
                            "Gross Profits": body.get('grossProfits', {}).get('fmt', 'N/A'),
                            #"Operating Cash Flow": body.get('operatingCashflow', {}).get('fmt', 'N/A'),
                            #"Free Cash Flow": body.get('freeCashflow', {}).get('fmt', 'N/A')
                        }
                        
                        for key, value in income_metrics.items():
                            st.markdown(f"**{key}:** {value}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Growth metrics visualization
                    st.subheader("Growth & Margins")
                    
                    # Create a more interactive visualization using columns with metrics
                    growth_cols = st.columns(4)
                    
                    with growth_cols[0]:
                        earnings_growth = body.get('earningsGrowth', {}).get('fmt', 'N/A')
                        earnings_raw = body.get('earningsGrowth', {}).get('raw', 0)
                        st.metric("Earnings Growth", earnings_growth, 
                                delta=f"{earnings_raw*100:.1f}%" if isinstance(earnings_raw, (int, float)) else None)
                    
                    with growth_cols[1]:
                        revenue_growth = body.get('revenueGrowth', {}).get('fmt', 'N/A')
                        revenue_raw = body.get('revenueGrowth', {}).get('raw', 0)
                        st.metric("Revenue Growth", revenue_growth, 
                                delta=f"{revenue_raw*100:.1f}%" if isinstance(revenue_raw, (int, float)) else None)
                    
                    with growth_cols[2]:
                        gross_margins = body.get('grossMargins', {}).get('fmt', 'N/A')
                        gross_raw = body.get('grossMargins', {}).get('raw', 0)
                        st.metric("Gross Margins", gross_margins, 
                                delta=f"{gross_raw*100:.1f}%" if isinstance(gross_raw, (int, float)) else None)
                    
                    with growth_cols[3]:
                        profit_margins = body.get('profitMargins', {}).get('fmt', 'N/A')
                        profit_raw = body.get('profitMargins', {}).get('raw', 0)
                        st.metric("Profit Margins", profit_margins, 
                                delta=f"{profit_raw*100:.1f}%" if isinstance(profit_raw, (int, float)) else None)
            except Exception as e:
                st.error(f"Error: {e}")
    
    elif selected_view == "📝 Income Statement":
        st.header("Income Statement")
        statement_type = st.radio("Select Period", ["Quarterly", "Yearly"], horizontal=True)
        
        with st.spinner("Fetching income statement data..."):
            try:
                income_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=income-statement", api_symbol,api_key= user_api_key)
                
                if income_data and 'body' in income_data:
                    if statement_type == "Quarterly" and 'incomeStatementHistoryQuarterly' in income_data['body']:
                        quarterly_data = income_data['body']['incomeStatementHistoryQuarterly']['incomeStatementHistory']
                        df_income = pd.DataFrame(parse_financial_data(quarterly_data))
                    else:
                        yearly_data = income_data['body']['incomeStatementHistory']['incomeStatementHistory']
                        df_income = pd.DataFrame(parse_financial_data(yearly_data))
                    
                    if not df_income.empty:
                        # Format the numbers for display
                        display_df = df_income.copy()
                        for col in display_df.columns:
                            if col != 'End Date':
                                display_df[col] = display_df[col].apply(format_large_number)
                        
                        # Add visual styling to dataframe
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        st.dataframe(display_df, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Create more interactive charts
                        st.subheader("Financial Performance Visualization")
                        
                        # Chart selection
                        chart_type = st.radio("Select Chart Type", ["Bar Chart", "Line Chart", "Area Chart"], horizontal=True)
                        metric_to_show = st.selectbox("Select Metric to Visualize", 
                                                    ["Total Revenue", "Net Income", "Gross Profit", "EBIT"])
                        
                        # Prepare chart data
                        chart_data = df_income[['End Date', metric_to_show]].copy()
                        chart_data = chart_data.sort_values('End Date')
                        
                        # Create different chart types based on selection
                        if chart_type == "Bar Chart":
                            chart = alt.Chart(chart_data).mark_bar().encode(
                                x=alt.X('End Date:N', title='Period'),
                                y=alt.Y(f'{metric_to_show}:Q', title=metric_to_show),
                                tooltip=['End Date', metric_to_show]
                            ).properties(
                                height=400
                            ).interactive()
                            st.altair_chart(chart, use_container_width=True)
                        
                        elif chart_type == "Line Chart":
                            chart = alt.Chart(chart_data).mark_line(point=True).encode(
                                x=alt.X('End Date:N', title='Period'),
                                y=alt.Y(f'{metric_to_show}:Q', title=metric_to_show),
                                tooltip=['End Date', metric_to_show]
                            ).properties(
                                height=400
                            ).interactive()
                            st.altair_chart(chart, use_container_width=True)
                        
                        else:  # Area Chart
                            chart = alt.Chart(chart_data).mark_area(opacity=0.7).encode(
                                x=alt.X('End Date:N', title='Period'),
                                y=alt.Y(f'{metric_to_show}:Q', title=metric_to_show),
                                tooltip=['End Date', metric_to_show]
                                ).properties(
                                height=400
                            ).interactive()
                            st.altair_chart(chart, use_container_width=True)
                        
                        # Add financial insights section
                        if not df_income.empty and len(df_income) > 1:
                            st.subheader("Financial Insights")
                            
                            try:
                                # Calculate period-over-period growth for the selected metric
                                df_income_sorted = df_income.sort_values('End Date')
                                last_period = df_income_sorted.iloc[-1]
                                previous_period = df_income_sorted.iloc[-2]
                                
                                growth_rate = (last_period[metric_to_show] - previous_period[metric_to_show]) / previous_period[metric_to_show] * 100
                                
                                growth_color = "green" if growth_rate > 0 else "red"
                                
                                st.markdown(f"""
                                <div class="metric-card">
                                    <h5>{metric_to_show} Growth Analysis</h5>
                                    <p>Latest Period ({last_period['End Date']}): <b>{format_large_number(last_period[metric_to_show])}</b></p>
                                    <p>Previous Period ({previous_period['End Date']}): <b>{format_large_number(previous_period[metric_to_show])}</b></p>
                                    <p>Growth Rate: <span style="color:{growth_color};"><b>{growth_rate:.2f}%</b></span></p>
                                </div>
                                """, unsafe_allow_html=True)
                            except:
                                st.info("Insufficient data to calculate growth rates.")
                    else:
                        st.warning("No income statement data available.")
            except Exception as e:
                st.error(f"An error occurred Api doesn't bring data: {str(e)}")
    
    elif selected_view == "📒 Balance Sheet":
        st.header("Balance Sheet")
        bs_statement_type = st.radio("Select Balance Sheet Period", ["Quarterly", "Yearly"], horizontal=True)
        
        with st.spinner("Fetching balance sheet data..."):
            try:
                balance_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=balance-sheet", api_symbol,api_key=user_api_key)
                
                if balance_data and 'body' in balance_data:
                    if bs_statement_type == "Quarterly" and 'balanceSheetHistoryQuarterly' in balance_data['body']:
                        quarterly_bs = balance_data['body']['balanceSheetHistoryQuarterly']['balanceSheetStatements']
                        df_bs = pd.DataFrame(parse_balance_sheet(quarterly_bs))
                    else:
                        yearly_bs = balance_data['body']['balanceSheetHistory']['balanceSheetStatements']
                        df_bs = pd.DataFrame(parse_balance_sheet(yearly_bs))
                    
                    if not df_bs.empty:
                        # Format the numbers for display
                        display_bs = df_bs.copy()
                        for col in display_bs.columns:
                            if col not in ['End Date (Formatted)', 'End Date (Raw)', 'Max Age']:
                                # Make sure we're only formatting numeric columns
                                if display_bs[col].dtype in [int, float] or pd.api.types.is_numeric_dtype(display_bs[col]):
                                    display_bs[col] = display_bs[col].apply(format_large_number)
                        
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        st.dataframe(display_bs, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Calculate and display key ratios
                        if 'totalAssets' in df_bs.columns and 'totalLiab' in df_bs.columns:
                            st.subheader("Key Financial Ratios")
                            ratio_cols = st.columns(3)
                            
                            with ratio_cols[0]:
                                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                                # Calculate current ratio (if we have the data)
                                if 'cash' in df_bs.columns and 'totalLiab' in df_bs.columns:
                                    try:
                                        current_ratio = df_bs['cash'] / df_bs['totalLiab']
                                        st.metric("Cash to Total Liabilities", 
                                                f"{current_ratio.iloc[0]:.2f}" if not current_ratio.empty else "N/A")
                                    except:
                                        st.metric("Cash to Total Liabilities", "N/A")
                                st.markdown('</div>', unsafe_allow_html=True)
                            
                            with ratio_cols[1]:
                                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                                # Calculate debt-to-equity ratio
                                if 'totalLiab' in df_bs.columns and 'totalStockholderEquity' in df_bs.columns:
                                    try:
                                        debt_equity = df_bs['totalLiab'] / df_bs['totalStockholderEquity']
                                        st.metric("Debt to Equity", 
                                                f"{debt_equity.iloc[0]:.2f}" if not debt_equity.empty else "N/A")
                                    except:
                                        st.metric("Debt to Equity", "N/A")
                                st.markdown('</div>', unsafe_allow_html=True)
                            
                            with ratio_cols[2]:
                                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                                # Calculate asset turnover or another relevant ratio
                                if 'totalAssets' in df_bs.columns:
                                    try:
                                        asset_equity = df_bs['totalAssets'] / df_bs['totalStockholderEquity']
                                        st.metric("Assets to Equity", 
                                                f"{asset_equity.iloc[0]:.2f}" if not asset_equity.empty else "N/A")
                                    except:
                                        st.metric("Assets to Equity", "N/A")
                                st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Additional balance sheet analysis
                            if len(df_bs) > 1:
                                st.subheader("Balance Sheet Analysis")
                                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                                
                                if 'totalAssets' in df_bs.columns:
                                    # Sort by date to get latest and previous period
                                    df_bs_sorted = df_bs.sort_values('End Date (Raw)', ascending=False)
                                    
                                    if len(df_bs_sorted) >= 2:
                                        latest = df_bs_sorted.iloc[0]
                                        previous = df_bs_sorted.iloc[1]
                                        
                                        # Calculate asset growth
                                        if 'totalAssets' in latest and 'totalAssets' in previous:
                                            try:
                                                asset_growth = (latest['totalAssets'] - previous['totalAssets']) / previous['totalAssets'] * 100
                                                growth_color = "green" if asset_growth > 0 else "red"
                                                
                                                st.markdown(f"""
                                                <h5>Total Assets Growth</h5>
                                                <p>Latest Period: <b>{format_large_number(latest['totalAssets'])}</b></p>
                                                <p>Previous Period: <b>{format_large_number(previous['totalAssets'])}</b></p>
                                                <p>Growth Rate: <span style="color:{growth_color};"><b>{asset_growth:.2f}%</b></span></p>
                                                """, unsafe_allow_html=True)
                                            except:
                                                st.info("Could not calculate asset growth rate.")
                                
                                st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.warning("No balance sheet data available.")
            except Exception as e:
                st.warning('Api request failed. Please try again later.')
    
    elif selected_view == "📈 EPS Analysis":
        st.header("Earnings Per Share (EPS) Analysis")
        with st.spinner("Fetching EPS data..."):
            try:
                eps_data = fetch_eps_data(symbol,api_key= user_api_key)
                
                if eps_data:
                    eps_actuals_df, eps_estimates_df = parse_eps_data(eps_data)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("EPS Actuals")
                        if not eps_actuals_df.empty:
                            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                            st.dataframe(eps_actuals_df, use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Create visualization for EPS actuals
                            if 'FiscalYear' in eps_actuals_df.columns and 'ReportedEPS' in eps_actuals_df.columns:
                                st.markdown("##### Historical EPS Trend")
                                
                                chart_data = eps_actuals_df[['FiscalYear', 'ReportedEPS']].copy()
                                chart_data = chart_data.sort_values('FiscalYear')
                                
                                eps_chart = alt.Chart(chart_data).mark_line(point=True).encode(
                                    x=alt.X('FiscalYear:O', title='Fiscal Year'),
                                    y=alt.Y('ReportedEPS:Q', title='EPS (₹)'),
                                    tooltip=['FiscalYear', 'ReportedEPS']
                                ).properties(
                                    height=250
                                ).interactive()
                                
                                st.altair_chart(eps_chart, use_container_width=True)
                        else:
                            st.info("No EPS actuals data available.")
                    
                    with col2:
                        st.subheader("EPS Estimates")
                        if not eps_estimates_df.empty:
                            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                            st.dataframe(eps_estimates_df, use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Create visualization for EPS estimates
                            if 'FiscalYear' in eps_estimates_df.columns:
                                st.markdown("##### EPS Estimates Range")
                                
                                if 'High' in eps_estimates_df.columns and 'Low' in eps_estimates_df.columns and 'Mean' in eps_estimates_df.columns:
                                    chart_data = eps_estimates_df[['FiscalYear', 'High', 'Low', 'Mean']].copy()
                                    chart_data = chart_data.sort_values('FiscalYear')
                                    
                                    # Convert to long format for better visualization
                                    chart_data_long = pd.melt(
                                        chart_data, 
                                        id_vars=['FiscalYear'],
                                        value_vars=['High', 'Low', 'Mean'],
                                        var_name='Estimate Type',
                                        value_name='Value'
                                    )
                                    
                                    estimate_chart = alt.Chart(chart_data_long).mark_line(point=True).encode(
                                        x=alt.X('FiscalYear:O', title='Fiscal Year'),
                                        y=alt.Y('Value:Q', title='EPS Estimate (₹)'),
                                        color='Estimate Type:N',
                                        tooltip=['FiscalYear', 'Estimate Type', 'Value']
                                    ).properties(
                                        height=250
                                    ).interactive()
                                    
                                    st.altair_chart(estimate_chart, use_container_width=True)
                        else:
                            st.info("No EPS estimates data available.")
                    
                    # EPS Surprise Analysis
                    if not eps_actuals_df.empty and 'SurprisePercent' in eps_actuals_df.columns:
                        st.subheader("EPS Surprise Analysis")
                        
                        surprise_data = eps_actuals_df[['FiscalYear', 'SurprisePercent']].copy().dropna()
                        if not surprise_data.empty:
                            surprise_data = surprise_data.sort_values('FiscalYear')
                            
                            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                            
                            # Calculate average surprise
                            avg_surprise = surprise_data['SurprisePercent'].mean()
                            surprise_color = "green" if avg_surprise > 0 else "red"
                            
                            st.markdown(f"""
                            <h5>EPS Surprise Performance</h5>
                            <p>Average Surprise: <span style="color:{surprise_color};"><b>{avg_surprise:.2f}%</b></span></p>
                            <p>Latest Surprise: <span style="color:{'green' if surprise_data['SurprisePercent'].iloc[-1] > 0 else 'red'};"><b>{surprise_data['SurprisePercent'].iloc[-1]:.2f}%</b></span></p>
                            <p>Number of Quarters Analyzed: <b>{len(surprise_data)}</b></p>
                            """, unsafe_allow_html=True)
                            
                            surprise_chart = alt.Chart(surprise_data).mark_bar().encode(
                                x=alt.X('FiscalYear:O', title='Fiscal Year'),
                                y=alt.Y('SurprisePercent:Q', title='Surprise (%)'),
                                color=alt.condition(
                                    alt.datum.SurprisePercent > 0,
                                    alt.value('green'),
                                    alt.value('red')
                                ),
                                tooltip=['FiscalYear', 'SurprisePercent']
                            ).properties(
                                height=300,
                                title='EPS Surprise Percentage by Fiscal Year'
                            ).interactive()
                            
                            st.altair_chart(surprise_chart, use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                        else:
                            st.info("No EPS surprise data available.")
                else:
                    st.error("Failed to fetch EPS data. Please try again later.")
            except Exception as e:
                st.error(f"Failed to fetch EPS data: {str(e)}")
    
    elif selected_view == "🎯 Price Targets":
        st.header("Price Targets & Analyst Recommendations")
        with st.spinner("Fetching price target data..."):
            try:
                price_target_data = fetch_price_target_data(symbol,api_key = user_api_key)
                
                if price_target_data:
                    price_df, recommend_df = parse_price_target_data(price_target_data)
                    
                    # Price Target Analysis
                    st.subheader("Price Target Trends")
                    
                    if not price_df.empty:
                        # Display the data in a table
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        
                        # Rename the columns for better display
                        display_price_df = price_df.copy()
                        display_price_df['Age'] = display_price_df['Age'].map({
                            'NinetyDaysAgo': '90 Days Ago',
                            'SixtyDaysAgo': '60 Days Ago',
                            'ThirtyDaysAgo': '30 Days Ago',
                            'OneWeekAgo': '1 Week Ago'
                        })
                        
                        st.dataframe(display_price_df, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Create a visualization for price targets over time
                        try:
                            chart_data = price_df[['Age', 'Mean', 'High', 'Low']].copy()
                            
                            # Add current price for comparison if available
                            financial_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=financial-data", api_symbol)
                            if financial_data and 'body' in financial_data:
                                current_price = financial_data['body'].get('currentPrice', {}).get('raw', None)
                                
                                if current_price:
                                    # Add current price to all rows for comparison
                                    chart_data['Current Price'] = current_price
                            
                            # Convert to long format for visualization
                            chart_data_long = pd.melt(
                                chart_data, 
                                id_vars=['Age'],
                                value_vars=[col for col in chart_data.columns if col != 'Age'],
                                var_name='Price Type',
                                value_name='Price'
                            )
                            
                            # Map age to numeric order for sorting
                            age_order = {
                                'NinetyDaysAgo': 0,
                                'SixtyDaysAgo': 1,
                                'ThirtyDaysAgo': 2,
                                'OneWeekAgo': 3
                            }
                            
                            chart_data_long['Age_Order'] = chart_data_long['Age'].map(age_order)
                            chart_data_long = chart_data_long.sort_values('Age_Order')
                            
                            # Create the chart
                            price_chart = alt.Chart(chart_data_long).mark_line(point=True).encode(
                                x=alt.X('Age:O', sort=['NinetyDaysAgo', 'SixtyDaysAgo', 'ThirtyDaysAgo', 'OneWeekAgo'], 
                                    title='Time Period'),
                                y=alt.Y('Price:Q', title='Price (₹)'),
                                color='Price Type:N',
                                tooltip=['Age', 'Price Type', 'Price']
                            ).properties(
                                height=350,
                                title='Price Target Trends Over Time'
                            ).interactive()
                            
                            st.altair_chart(price_chart, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error creating price target chart: {str(e)}")
                    else:
                        st.info("No price target data available.")
                    
                    # Recommendation Analysis
                    st.subheader("Analyst Recommendations")
                    
                    if not recommend_df.empty:
                        # Display the data in a table
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        
                        # Rename the columns for better display
                        display_recommend_df = recommend_df.copy()
                        display_recommend_df['Age'] = display_recommend_df['Age'].map({
                            'NinetyDaysAgo': '90 Days Ago',
                            'SixtyDaysAgo': '60 Days Ago',
                            'ThirtyDaysAgo': '30 Days Ago',
                            'OneWeekAgo': '1 Week Ago'
                        })
                        
                        st.dataframe(display_recommend_df, use_container_width=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Create visualizations for recommendations
                        try:
                            # Prepare data for the stacked bar chart
                            latest_recommend = recommend_df.iloc[-1]
                            
                            # Create data for pie chart
                            pie_data = pd.DataFrame({
                                'Recommendation': ['Buy', 'Hold', 'Sell'],
                                'Count': [latest_recommend['Buy'], latest_recommend['Hold'], latest_recommend['Sell']]
                            })
                            
                            # Show recommendation distribution
                            st.subheader("Latest Recommendation Distribution")
                            
                            col1, col2 = st.columns([1, 2])
                            
                            with col1:
                                # Calculate total analysts
                                total_analysts = latest_recommend['Buy'] + latest_recommend['Hold'] + latest_recommend['Sell']
                                
                                # Display latest recommendation score with interpretation
                                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                                recommendation_score = latest_recommend['Mean']
                                
                                if recommendation_score <= 1.5:
                                    recommendation_text = "Strong Buy"
                                    recommendation_color = "green"
                                elif recommendation_score <= 2.5:
                                    recommendation_text = "Buy"
                                    recommendation_color = "lightgreen"
                                elif recommendation_score <= 3.5:
                                    recommendation_text = "Hold"
                                    recommendation_color = "orange"
                                elif recommendation_score <= 4.5:
                                    recommendation_text = "Sell"
                                    recommendation_color = "red"
                                else:
                                    recommendation_text = "Strong Sell"
                                    recommendation_color = "darkred"
                                
                                st.markdown(f"""
                                <h4>Consensus Recommendation</h4>
                                <p style="font-size:24px; color:{recommendation_color}"><b>{recommendation_text}</b></p>
                                <p>Mean Score: <b>{recommendation_score:.2f}</b> (1=Strong Buy, 5=Strong Sell)</p>
                                <p>Total Analysts: <b>{total_analysts}</b></p>
                                """, unsafe_allow_html=True)
                                st.markdown('</div>', unsafe_allow_html=True)
                            
                            with col2:
                                # Create pie chart of recommendations
                                fig, ax = plt.subplots(figsize=(7, 5))
                                colors = ['green', 'orange', 'red']
                                
                                pie = ax.pie(
                                    pie_data['Count'], 
                                    labels=pie_data['Recommendation'], 
                                    autopct='%1.1f%%',
                                    colors=colors,
                                    startangle=90,
                                    explode=(0.03, 0.03, 0.03)
                                )
                                
                                # Equal aspect ratio ensures that pie is drawn as a circle
                                ax.axis('equal')
                                plt.title('Analyst Recommendation Distribution', fontsize=14)
                                
                                st.pyplot(fig)
                            
                            # Show recommendation trend over time
                            st.subheader("Recommendation Trend Over Time")
                            
                            # Prepare data for stacked bar chart
                            trend_data = recommend_df.copy()
                            trend_data['Age'] = trend_data['Age'].map({
                                'NinetyDaysAgo': '90 Days Ago',
                                'SixtyDaysAgo': '60 Days Ago',
                                'ThirtyDaysAgo': '30 Days Ago',
                                'OneWeekAgo': '1 Week Ago'
                            })
                            
                            # Melt the data for proper stacking
                            trend_data_long = pd.melt(
                                trend_data,
                                id_vars=['Age', 'Mean'],
                                value_vars=['Buy', 'Hold', 'Sell'],
                                var_name='Recommendation',
                                value_name='Count'
                            )
                            
                            # Create stacked bar chart
                            recommend_chart = alt.Chart(trend_data_long).mark_bar().encode(
                                x=alt.X('Age:O', sort=['90 Days Ago', '60 Days Ago', '30 Days Ago', '1 Week Ago'],
                                    title='Time Period'),
                                y=alt.Y('Count:Q', title='Number of Analysts'),
                                color=alt.Color('Recommendation:N', scale=alt.Scale(
                                    domain=['Buy', 'Hold', 'Sell'],
                                    range=['green', 'orange', 'red']
                                )),
                                tooltip=['Age', 'Recommendation', 'Count']
                            ).properties(
                                height=350,
                                title='Analyst Recommendation Distribution Over Time'
                            )
                            
                            # Add a line for mean score
                            mean_line = alt.Chart(trend_data).mark_line(color='blue', point=True).encode(
                                x=alt.X('Age:O', sort=['90 Days Ago', '60 Days Ago', '30 Days Ago', '1 Week Ago']),
                                y=alt.Y('Mean:Q', title='Mean Score', scale=alt.Scale(domain=[1, 5])),
                                tooltip=['Age', 'Mean']
                            )
                            
                            # Combine the charts
                            combined_chart = alt.layer(recommend_chart, mean_line).resolve_scale(
                                y='independent'
                            )
                            
                            st.altair_chart(combined_chart, use_container_width=True)
                            
                            # Stock Decision Support
                            st.subheader("Stock Decision Support")
                            
                            latest_price_target = price_target_data.get('priceTarget', {}).get('Mean', 'N/A')
                            latest_recommend_mean = price_target_data.get('recommendation', {}).get('Mean', 'N/A')
                            
                            if latest_price_target != 'N/A' and latest_recommend_mean != 'N/A':
                                # Get current price
                                current_price = None
                                if financial_data and 'body' in financial_data:
                                    current_price = financial_data['body'].get('currentPrice', {}).get('raw', None)
                                
                                if current_price:
                                    # Calculate upside potential
                                    upside_potential = ((latest_price_target - current_price) / current_price) * 100
                                    
                                    # Determine decision
                                    if latest_recommend_mean <= 2.0:
                                        decision = "BUY (Strong recommendation)"
                                        decision_color = "green"
                                    elif latest_recommend_mean <= 3.0:
                                        decision = "HOLD (Neutral to Positive outlook)"
                                        decision_color = "orange"
                                    else:
                                        decision = "SELL (Negative outlook)"
                                        decision_color = "red"
                                    
                                    st.markdown(f"""
                                    <div class="metric-card">
                                    <h4>Investment Decision Analysis</h4>
                                    <p>Current Price: <b>₹{current_price:.2f}</b></p>
                                    <p>Target Price: <b>₹{latest_price_target:.2f}</b></p>
                                    <p>Price Upside: <b style="color:{'green' if upside_potential > 0 else 'red'}">{upside_potential:.2f}%</b></p>
                                    <p>Recommendation Score: <b>{latest_recommend_mean:.2f}</b></p>
                                    <p>Suggested Action: <b style="color:{decision_color}">{decision}</b></p>
                                    </div>
                                    """, unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Error creating recommendation charts: {str(e)}")
                    else:
                        st.info("No recommendation data available.")
                else:
                    st.error("Failed to fetch price target data. Please try again later.")
            except Exception as e: 
                st.error("Failed to fetch price target data. Please try again later.")
    
    elif selected_view == "📰 Market News":
        st.header("Market News")
        try:
            with st.spinner("Fetching market news..."):
            
                conn = http.client.HTTPSConnection("yahoo-finance160.p.rapidapi.com")
                # if not api_key:
                #     api_key = user_api_key 
                payload = f'{{"stock":"{api_symbol}"}}'

                headers = {
                    'x-rapidapi-key': f"{user_api_key}",
                    'x-rapidapi-host': "yahoo-finance160.p.rapidapi.com",
                    'Content-Type': "application/json"
                }

                conn.request("POST", "/stocknews", payload, headers)

                res = conn.getresponse()
                data = res.read()
                news_data = json.loads(data.decode("utf-8"))
                
                if news_data:
                    # Add a search/filter option
                    search_term = st.text_input("Search news by keyword")
                    
                    filtered_news = news_data
                    if search_term:
                        filtered_news = [
                            news for news in news_data 
                            if search_term.lower() in news.get("content", {}).get("title", "").lower() or
                            search_term.lower() in news.get("content", {}).get("summary", "").lower()
                        ]
                    
                    # Display number of news items found
                    # st.markdown(f"#### Found {len(filtered_news)} news articles")
                    
                    # Create a more visually appealing news layout
                    for i, news in enumerate(filtered_news):
                        content = news.get("content", {})

                        title = content.get("title", "News Item")
                        source = content.get("provider", {}).get("displayName", "Unknown")
                        published = content.get("pubDate", "Unknown")
                        summary = content.get("summary", "No content available")
                        url = content.get("canonicalUrl", {}).get("url", None)
                        thumbnail_url = content.get("thumbnail", {}).get("originalUrl", None)

                        # Create a card-like layout for each news item
                        st.markdown(f"""
                        <div style="background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                            <h3>{title}</h3>
                            <p style="color: #666;"><strong>Source:</strong> {source} | <strong>Published:</strong> {published}</p>
                        """, unsafe_allow_html=True)
                        
                        # Display the news content in columns if there's a thumbnail
                        if thumbnail_url:
                            col1, col2 = st.columns([1, 3])
                            
                            with col1:
                                st.image(thumbnail_url, use_container_width=True)
                            
                            with col2:
                                st.markdown(f"<p>{summary}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p>{summary}</p>", unsafe_allow_html=True)
                        
                        if url:
                            st.markdown(f"<a href='{url}' target='_blank'>Read full article</a>", unsafe_allow_html=True)
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.warning("No news data available for this stock.")
        except Exception as e:
            st.info(f"No News Data Available or API doesn't fetching market news data")

    elif selected_view == "🏦 FII & Bulk Deals":
        st.header("FII & Bulk Deals")
        
        # GitHub repository details
        repo_owner = "RDE0509"  # Replace with actual GitHub username
        repo_name = "stock_analysis"        # Replace with actual repository name
        github_token = "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"  # Optional: Configure in Streamlit secrets
        
        # FII Data section
        st.subheader("FII Data")
        try:
            # Fetch latest FII data file from GitHub
            fii_file_content = fetch_latest_stock_screener_file(
                repo_owner,
                repo_name,
                token=github_token
            )
            
            if fii_file_content:
                # Create a temporary file to read Excel content
                with open("temp_fii.xlsx", "wb") as f:
                    f.write(fii_file_content)
                
                fii_data = pd.read_excel("temp_fii.xlsx")
                if not fii_data.empty:
                    st.dataframe(fii_data)
                else:
                    st.warning("FII data file is empty.")
                
                # Clean up temporary file
                import os
                os.remove("temp_fii.xlsx")
            else:
                st.error("Failed to fetch FII data from GitHub repository.")
        except Exception as e:
            st.error(f"Error loading FII data: {str(e)}")
        
        # Bulk Deals section
        st.subheader("Bulk Deals")
        try:
            # Get current date and previous dates (in case current date file isn't available yet)
            dates_to_try = [
                datetime.now() - timedelta(days=i) for i in range(5)  # Try last 5 days
            ]
            
            bulk_data = None
            for date in dates_to_try:
                formatted_date = date.strftime('%d-%b-%Y')
                file_name = f"Large-deals-BULK-{formatted_date}.csv"
                
                # Fetch bulk deals file from GitHub
                bulk_file_content = fetch_latest_file_from_github(
                    repo_owner,
                    repo_name,
                    file_name,
                    token=github_token
                )
                
                if bulk_file_content:
                    # Create a temporary file to read CSV content
                    with open("temp_bulk.csv", "wb") as f:
                        f.write(bulk_file_content)
                    
                    bulk_data = pd.read_csv("temp_bulk.csv")
                    
                    # Clean up temporary file
                    import os
                    os.remove("temp_bulk.csv")
                    
                    if not bulk_data.empty:
                        st.success(f"Showing bulk deals data for {formatted_date}")
                        break
            
            if bulk_data is not None and not bulk_data.empty:
                st.dataframe(bulk_data)
            else:
                st.warning("No bulk deals data available for the recent dates.")
            
        except Exception as e:
            st.error(f"Error loading bulk deals data: {str(e)}")
    
    elif selected_view == "🌟 Top Performers":
        st.header("🌟 Top Performing Stocks (Trending)")
        try:
            conn = http.client.HTTPSConnection("indian-stock-exchange-api2.p.rapidapi.com")

            headers = {
                'x-rapidapi-key': f"{user_api_key}",
                'x-rapidapi-host': "indian-stock-exchange-api2.p.rapidapi.com"
            }

            conn.request("GET", "/trending", headers=headers)
            res = conn.getresponse()
            data = res.read()
            trending_data = json.loads(data.decode("utf-8"))

            if "trending_stocks" in trending_data and "top_gainers" in trending_data["trending_stocks"]:
                df = pd.DataFrame(trending_data["trending_stocks"]["top_gainers"])

                relevant_columns = [
                    "company_name", "price", "percent_change", "net_change", "volume",
                    "overall_rating", "short_term_trends", "long_term_trends",
                    "year_low", "year_high", "high", "low", "open", "close"
                ]

                df_filtered = df[relevant_columns]

                # Convert numeric columns
                numeric_cols = ["price", "percent_change", "net_change", "volume",
                                "year_low", "year_high", "high", "low", "open", "close"]
                df_filtered[numeric_cols] = df_filtered[numeric_cols].apply(pd.to_numeric, errors='coerce')

                st.dataframe(df_filtered, use_container_width=True)
            else:
                st.warning("Top performers data is currently unavailable.")

        except Exception as e:
            st.error(f"Error fetching top performers: {str(e)}")
    
    elif selected_view == "🧠 Stock Recommendation Analysis":
        st.header("🧠 Stock Recommendation Analysis")
        try:
            conn = http.client.HTTPSConnection("yahoo-finance160.p.rapidapi.com")
            payload = f'{{"stock":"{api_symbol}"}}'


            headers = {
                'x-rapidapi-key': f"{user_api_key}",
                'x-rapidapi-host': "yahoo-finance160.p.rapidapi.com",
                'Content-Type': "application/json"
            }

            conn.request("POST", "/recommnedations", payload, headers)

            res = conn.getresponse()
            data = res.read()
            data = data.decode('utf-8')

            recommendation_data = json.loads(data)

            rec_df = pd.DataFrame(recommendation_data['history'])

            # Rename columns for readability
            rec_df.rename(columns={
                'buy_suggestion_percentage': 'Buy %',
                'hold_suggestion_percentage': 'Hold %',
                'sell_suggestion_percentage': 'Sell %'
            }, inplace=True)

            st.subheader(f"Current Recommendation: 🟢 {recommendation_data['recommendation'].capitalize()}")

            st.dataframe(rec_df, use_container_width=True)

            # Prepare long-form data for stacked bar chart
            long_df = rec_df.melt(id_vars='period',
                                value_vars=['Buy %', 'Hold %', 'Sell %'],
                                var_name='Recommendation', value_name='Percentage')

            chart = alt.Chart(long_df).mark_bar().encode(
                x=alt.X('period:N', title='Period'),
                y=alt.Y('Percentage:Q', stack='normalize', title='Recommendation %'),
                color=alt.Color('Recommendation:N', scale=alt.Scale(
                    domain=['Buy %', 'Hold %', 'Sell %'],
                    range=['green', 'orange', 'red']
                )),
                tooltip=['period', 'Recommendation', 'Percentage']
            ).properties(
                height=400,
                title='Recommendation Trends Over Time'
            )

            st.altair_chart(chart, use_container_width=True)
            
        except Exception as e:
                    st.warning(f"Error fetching recommendation analysis: {str(e)}")

# def create_financial_metrics_chart(financial_data):
#     try:
#         # Convert dictionary data to DataFrame if needed
#         if isinstance(financial_data, dict):
#             df = pd.DataFrame([financial_data])
#         else:
#             df = pd.DataFrame(financial_data)
            
#         # Create a line chart for key financial metrics
#         metrics_chart = alt.Chart(df.melt(
#             id_vars=['End Date'],
#             value_vars=['Total Revenue', 'Net Income', 'EBIT', 'Gross Profit']
#         )).mark_line(point=True).encode(
#             x='End Date:T',
#             y=alt.Y('value:Q', title='Amount'),
#             color=alt.Color('variable:N', title='Metric'),
#             tooltip=['End Date', 'variable', 'value']
#         ).properties(
#             height=400,
#             title='Key Financial Metrics Over Time'
#         )
        
#         return metrics_chart
#     except Exception as e:
#         st.error(f"Error creating financial metrics chart: {str(e)}")
#         return None

# def create_balance_sheet_chart(balance_data):
#     try:
#         if isinstance(balance_data, dict):
#             df = pd.DataFrame([balance_data])
#         else:
#             df = pd.DataFrame(balance_data)
#         st.write("DEBUG: Balance Sheet DataFrame", df)  # Add this line

#         # Ensure required columns exist and are numeric
#         required_cols = ['totalAssets', 'cash', 'propertyPlantEquipment', 'intangibleAssets']
#         for col in required_cols:
#             if col not in df.columns:
#                 df[col] = 0
#             # Convert to numeric, coerce errors to NaN, then fill NaN with 0
#             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
#         # Also ensure 'End Date (Formatted)' is present and parseable
#         if 'End Date (Formatted)' in df.columns:
#             df['End Date (Formatted)'] = pd.to_datetime(df['End Date (Formatted)'], errors='coerce')
#         else:
#             st.warning("No 'End Date (Formatted)' column in balance sheet data.")
#             return None

#         # Remove rows where all required columns are zero (optional, for cleaner chart)
#         if df[required_cols].sum(axis=1).eq(0).all():
#             st.warning("No valid balance sheet data to display.")
#             st.dataframe(df)  # Show the DataFrame for debugging
#             return None

#         # Create a stacked bar chart for assets composition
#         assets_chart = alt.Chart(df).transform_fold(
#             required_cols,
#             as_=['Category', 'Value']
#         ).mark_bar().encode(
#             x=alt.X('End Date (Formatted):T', title='Date'),
#             y=alt.Y('Value:Q', title='Amount'),
#             color=alt.Color('Category:N', title='Category'),
#             tooltip=['Category', 'Value', 'End Date (Formatted)']
#         ).properties(
#             height=400,
#             title='Assets Composition Over Time'
#         )
        
#         return assets_chart
#     except Exception as e:
#         st.error(f"Error creating balance sheet chart: {str(e)}")
#         return None

# def create_eps_trend_chart(eps_data):
#     try:
#         # Convert dictionary data to DataFrame if needed
#         if isinstance(eps_data, dict):
#             df = pd.DataFrame([eps_data])
#         else:
#             df = pd.DataFrame(eps_data)
            
#         # Create a dual-axis chart for EPS and Surprise %
#         base = alt.Chart(df).encode(x='ReportedDate:T')
        
#         eps_line = base.mark_line(color='blue').encode(
#             y=alt.Y('ReportedEPS:Q', title='EPS'),
#             tooltip=['ReportedDate', 'ReportedEPS', 'SurprisePercent']
#         )
        
#         surprise_bars = base.mark_bar(color='orange', opacity=0.5).encode(
#             y=alt.Y('SurprisePercent:Q', title='Surprise %')
#         )
        
#         combined_chart = alt.layer(eps_line, surprise_bars).resolve_scale(
#             y='independent'
#         ).properties(
#             height=400,
#             title='EPS Trend with Surprise Percentage'
#         )
        
#         return combined_chart
#     except Exception as e:
#         st.error(f"Error creating EPS trend chart: {str(e)}")
#         return None

# def create_financial_ratios_chart(balance_data, financial_data):
#     try:
#         # Convert dictionary data to DataFrame if needed
#         if isinstance(balance_data, dict):
#             balance_df = pd.DataFrame([balance_data])
#         else:
#             balance_df = pd.DataFrame(balance_data)
            
#         if isinstance(financial_data, dict):
#             financial_df = pd.DataFrame([financial_data])
#         else:
#             financial_df = pd.DataFrame(financial_data)
        
#         # Calculate key ratios
#         balance_df['Current Ratio'] = balance_df['totalAssets'] / balance_df['totalLiab']
#         balance_df['Debt to Equity'] = balance_df['totalLiab'] / balance_df['totalStockholderEquity']
        
#         ratios_df = balance_df[['End Date (Formatted)', 'Current Ratio', 'Debt to Equity']]
        
#         # Create a multi-line chart for financial ratios
#         ratios_chart = alt.Chart(ratios_df.melt(
#             id_vars=['End Date (Formatted)'],
#             value_vars=['Current Ratio', 'Debt to Equity']
#         )).mark_line(point=True).encode(
#             x='End Date (Formatted):T',
#             y='value:Q',
#             color='variable:N',
#             tooltip=['End Date (Formatted)', 'variable', 'value']
#         ).properties(
#             height=400,
#             title='Key Financial Ratios Over Time'
#         )
        
#         return ratios_chart
#     except Exception as e:
#         st.error(f"Error creating financial ratios chart: {str(e)}")
#         return None

# if __name__ == "__main__":
#     st.title("Enhanced Stock Analysis Dashboard")
    
#     try:
#         # Get the financial data from the existing API call in the Financial Data tab
#         with st.spinner("Loading financial data..."):
#             financial_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=financial-data", api_symbol, api_key=user_api_key)
#             balance_data = fetch_api_data(f"/api/v1/markets/stock/modules?ticker={api_symbol}&module=balance-sheet", api_symbol, api_key=user_api_key)
#             eps_data = fetch_eps_data(symbol, api_key=user_api_key)

#             # Parse the data
#             if financial_data and isinstance(financial_data, dict) and 'body' in financial_data:
#                 if 'incomeStatementHistory' in financial_data['body']:
#                     financial_records = parse_financial_data(financial_data['body']['incomeStatementHistory']['incomeStatementHistory'])
#                 else:
#                     financial_records = []
#             else:
#                 financial_records = []

#             if balance_data and isinstance(balance_data, dict) and 'body' in balance_data:
#                 if 'balanceSheetHistory' in balance_data['body']:
#                     balance_records = parse_balance_sheet(balance_data['body']['balanceSheetHistory']['balanceSheetStatements'])
#                 else:
#                     balance_records = []
#             else:
#                 balance_records = []

#             if eps_data:
#                 eps_actuals, _ = parse_eps_data(eps_data)
#             else:
#                 eps_actuals = pd.DataFrame()

#             # Create tabs for different visualizations
#             tabs = st.tabs(["Financial Metrics", "Balance Sheet", "EPS Analysis", "Financial Ratios"])
            
#             with tabs[0]:
#                 if financial_records:
#                     financial_chart = create_financial_metrics_chart(financial_records)
#                     if financial_chart:
#                         st.altair_chart(financial_chart, use_container_width=True)
#                 else:
#                     st.warning("No financial metrics data available")
            
#             with tabs[1]:
#                 if balance_records:
#                     balance_chart = create_balance_sheet_chart(balance_records)
#                     if balance_chart:
#                         st.altair_chart(balance_chart, use_container_width=True)
#                         st.write("DEBUG: Balance Sheet DataFrame", df_bs)
#                 else:
#                     st.warning("No balance sheet data available")
            
#             with tabs[2]:
#                 if not eps_actuals.empty:
#                     eps_chart = create_eps_trend_chart(eps_actuals)
#                     if eps_chart:
#                         st.altair_chart(eps_chart, use_container_width=True)
#                 else:
#                     st.warning("No EPS data available")
            
#             with tabs[3]:
#                 if balance_records and financial_records:
#                     ratios_chart = create_financial_ratios_chart(balance_records, financial_records)
#                     if ratios_chart:
#                         st.altair_chart(ratios_chart, use_container_width=True)
#                 else:
#                     st.warning("No financial ratios data available")

#     except Exception as e:
#         st.error(f"Error in visualization: {str(e)}")