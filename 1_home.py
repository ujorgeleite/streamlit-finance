import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

excel_file = None
df_years = []


@st.cache_resource(show_spinner="Loading data...", ttl=3600)
def load_excel_data():
    return pd.ExcelFile("data/data.xlsx")


excel_file = load_excel_data()
st.session_state.excel_file = excel_file

if excel_file is not None:
    year_from_excel = excel_file.sheet_names
    df_years = [
        year for year in year_from_excel if any(str(num).isdigit() for num in year)
    ]

st.sidebar.title("Menu")
period_selected = st.sidebar.selectbox("Select a period", df_years)
period_index = df_years.index(period_selected)
period_selected_minus_1 = str(period_index - 1)
print(f"Selected period index: {period_index}")

# Get specific items from df_years using index
if period_index > 0:
    previous_period = df_years[period_index - 1]  # Get previous period
    print(f"Previous period: {previous_period}")

current_period = df_years[period_index]  # Get current period
print(f"Current period: {current_period}")

if period_index < len(df_years) - 1:
    next_period = df_years[period_index + 1]  # Get next period
    print(f"Next period: {next_period}")

st.title(f"Data Analysis for {period_selected}")
# st.dataframe(excel_file.parse(period_selected))

df = pd.read_excel(excel_file, sheet_name=period_selected)
total_incomes = df["Rendimento"].sum()
total_bills = df[df["Valor"].notna()]["Valor"].sum()
total_paid_bills = df[df["Pago"] == "Sim"]["Valor"].sum()

print(total_incomes)
# Calculate delta for income comparison
income_delta = 0
bills_delta = 0
if period_index > 0:
    df_previous = pd.read_excel(excel_file, sheet_name=previous_period)
    previous_incomes = df_previous["Rendimento"].sum()
    previous_bills = df_previous[df_previous["Valor"].notna()]["Valor"].sum()
    income_delta = (
        ((total_incomes - previous_incomes) / previous_incomes * 100)
        if previous_incomes > 0
        else 0
    )
    bills_delta = (
        ((total_bills - previous_bills) / previous_bills * 100)
        if previous_bills > 0
        else 0
    )

print(total_paid_bills)

col1, col2 = st.columns(2)
with col1:
    # Green for income increase, red for decrease
    print(income_delta >= 0)

    st.metric(
        "Renda Total",
        f"R$ {total_incomes:,.2f}",
        delta=f"{income_delta:+.1f}%",
        delta_color="normal",
    )
with col2:
    # Red for expense increase, green for decrease
    st.metric(
        "Despesa Total",
        f"R$ {total_bills:,.2f}",
        delta=f"{bills_delta:+.1f}%",
        delta_color="inverse",
    )

# Calculate savings
total_savings = total_incomes - total_bills
savings_rate = (total_savings / total_incomes * 100) if total_incomes > 0 else 0

# Add savings metric
col3, col4 = st.columns(2)
with col3:
    st.metric(
        "Economia",
        f"R$ {total_savings:,.2f}",
        delta=f"{savings_rate:.1f}% da renda",
        delta_color="normal" if total_savings >= 0 else "inverse",
    )
with col4:
    st.metric(
        "Bills Pagas",
        f"R$ {total_paid_bills:,.2f}",
        delta=f"{(total_paid_bills/total_bills*100):.1f}% das despesas" if total_bills > 0 else "0%",
        delta_color="normal",
    )

# Charts Section
st.markdown("---")
st.subheader("📊 Análise Visual")

# 1. Income vs Expenses Bar Chart
fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    x=['Renda', 'Despesa'],
    y=[total_incomes, total_bills],
    marker_color=['#00ff88', '#ff6b6b'],
    text=[f'R$ {total_incomes:,.0f}', f'R$ {total_bills:,.0f}'],
    textposition='auto',
    name='Valores'
))

fig_bar.update_layout(
    title='Renda vs Despesa',
    xaxis_title='Categoria',
    yaxis_title='Valor (R$)',
    height=400,
    showlegend=False
)

st.plotly_chart(fig_bar, use_container_width=True)

# 2. Expense Breakdown (if category data exists)
if 'Categoria' in df.columns or 'Category' in df.columns:
    category_col = 'Categoria' if 'Categoria' in df.columns else 'Category'
    expense_by_category = df[df['Valor'].notna()].groupby(category_col)['Valor'].sum().sort_values(ascending=False)
    
    fig_pie = px.pie(
        values=expense_by_category.values,
        names=expense_by_category.index,
        title='Despesas por Categoria'
    )
    fig_pie.update_layout(height=400)
    st.plotly_chart(fig_pie, use_container_width=True)

# 3. Paid vs Unpaid Bills
paid_bills = df[df['Pago'] == 'Sim']['Valor'].sum()
unpaid_bills = df[df['Pago'] != 'Sim']['Valor'].sum()

fig_paid = go.Figure(data=[go.Pie(
    labels=['Pagas', 'Não Pagas'],
    values=[paid_bills, unpaid_bills],
    marker_colors=['#00ff88', '#ff6b6b']
)])
fig_paid.update_layout(
    title='Status dos Pagamentos',
    height=400
)
st.plotly_chart(fig_paid, use_container_width=True)

# 4. Financial Trend (if multiple periods available)
if len(df_years) > 1:
    st.subheader("📈 Tendência Financeira")
    
    # Get data for last 5 periods (or all if less than 5)
    periods_to_show = df_years[-5:] if len(df_years) > 5 else df_years
    
    trend_data = []
    for period in periods_to_show:
        period_df = pd.read_excel(excel_file, sheet_name=period)
        income = period_df['Rendimento'].sum()
        expenses = period_df[period_df['Valor'].notna()]['Valor'].sum()
        trend_data.append({
            'Periodo': period,
            'Renda': income,
            'Despesa': expenses,
            'Economia': income - expenses
        })
    
    trend_df = pd.DataFrame(trend_data)
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend_df['Periodo'],
        y=trend_df['Renda'],
        mode='lines+markers',
        name='Renda',
        line=dict(color='#00ff88', width=3)
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_df['Periodo'],
        y=trend_df['Despesa'],
        mode='lines+markers',
        name='Despesa',
        line=dict(color='#ff6b6b', width=3)
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_df['Periodo'],
        y=trend_df['Economia'],
        mode='lines+markers',
        name='Economia',
        line=dict(color='#4ecdc4', width=3)
    ))
    
    fig_trend.update_layout(
        title='Evolução Financeira',
        xaxis_title='Período',
        yaxis_title='Valor (R$)',
        height=400
    )
    
    st.plotly_chart(fig_trend, use_container_width=True)

# 5. Savings Rate Gauge
fig_gauge = go.Figure(go.Indicator(
    mode = "gauge+number+delta",
    value = savings_rate,
    domain = {'x': [0, 1], 'y': [0, 1]},
    title = {'text': "Taxa de Economia (%)"},
    delta = {'reference': 20},  # 20% is a good savings rate
    gauge = {
        'axis': {'range': [None, 100]},
        'bar': {'color': "darkblue"},
        'steps': [
            {'range': [0, 10], 'color': "lightgray"},
            {'range': [10, 20], 'color': "yellow"},
            {'range': [20, 100], 'color': "green"}
        ],
        'threshold': {
            'line': {'color': "red", 'width': 4},
            'thickness': 0.75,
            'value': 90
        }
    }
))

fig_gauge.update_layout(height=300)
st.plotly_chart(fig_gauge, use_container_width=True)
