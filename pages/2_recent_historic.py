import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(
    page_title="Análise dos Últimos 3 Meses",
    page_icon="📊",
    layout="wide"
)

@st.cache_resource(show_spinner="Carregando dados...", ttl=3600)
def load_excel_data():
    return pd.ExcelFile("data/data.xlsx")

# Load data
excel_file = load_excel_data()
if excel_file is not None:
    year_from_excel = excel_file.sheet_names
    df_years = [
        year for year in year_from_excel if any(str(num).isdigit() for num in year)
    ]

# Sidebar for month selection
st.sidebar.title("📅 Seleção de Período")
st.sidebar.markdown("---")

# Create a selectbox for choosing the starting month
if len(df_years) >= 3:
    # Show available months for selection (excluding the first 2 months to ensure we have 2 months before to analyze)
    available_end_months = df_years[2:] if len(df_years) > 2 else df_years
    
    selected_end_month = st.sidebar.selectbox(
        "Selecione o mês final para análise:",
        available_end_months,
        index=len(available_end_months) - 1,  # Default to the last available month
        help="Escolha o mês final para analisar esse mês e os 2 meses anteriores"
    )
    
    # Find the index of the selected month
    end_index = df_years.index(selected_end_month)
    
    # Get the 3 months ending with the selected month (selected month and 2 before)
    if end_index >= 2:
        last_3_months = df_years[end_index-2:end_index+1]
    else:
        # If we don't have 2 months before the selected month, use the first 3 months
        last_3_months = df_years[:3]
        st.sidebar.warning("⚠️ Período ajustado para os primeiros 3 meses disponíveis.")
else:
    last_3_months = df_years
    st.sidebar.warning("⚠️ Dados insuficientes. Mostrando todos os meses disponíveis.")

# Display the selected period in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Período Selecionado")
st.sidebar.write(f"**Início:** {last_3_months[0]}")
st.sidebar.write(f"**Fim:** {last_3_months[-1]}")
st.sidebar.write(f"**Total:** {len(last_3_months)} meses")

st.title("📊 Análise Completa dos Últimos 3 Meses")
st.markdown("---")

st.subheader(f"📅 Período Analisado: {last_3_months[0]} a {last_3_months[-1]}")

# Load data for all 3 months
monthly_data = {}
for month in last_3_months:
    monthly_data[month] = pd.read_excel(excel_file, sheet_name=month)

# Calculate summary metrics for each month
summary_data = []
for month in last_3_months:
    df = monthly_data[month]
    income = df["Rendimento"].sum()
    expenses = df[df["Valor"].notna()]["Valor"].sum()
    paid_bills = df[df["Pago"] == "Sim"]["Valor"].sum()
    savings = income - expenses
    savings_rate = (savings / income * 100) if income > 0 else 0
    
    summary_data.append({
        'Mês': month,
        'Renda': income,
        'Despesas': expenses,
        'Bills Pagas': paid_bills,
        'Economia': savings,
        'Taxa de Economia (%)': savings_rate
    })

summary_df = pd.DataFrame(summary_data)

# Key Metrics Section
st.subheader("🎯 Métricas Principais")

# Calculate 3-month totals and averages
total_3m_income = summary_df['Renda'].sum()
total_3m_expenses = summary_df['Despesas'].sum()
total_3m_savings = summary_df['Economia'].sum()
avg_monthly_income = summary_df['Renda'].mean()
avg_monthly_expenses = summary_df['Despesas'].mean()
avg_savings_rate = summary_df['Taxa de Economia (%)'].mean()

# Calculate trends (comparing first vs last month)
first_month = summary_df.iloc[0]
last_month = summary_df.iloc[-1]
income_trend = ((last_month['Renda'] - first_month['Renda']) / first_month['Renda'] * 100) if first_month['Renda'] > 0 else 0
expense_trend = ((last_month['Despesas'] - first_month['Despesas']) / first_month['Despesas'] * 100) if first_month['Despesas'] > 0 else 0

# Display metrics in columns
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Renda Total (3 meses)",
        f"R$ {total_3m_income:,.2f}",
        delta=f"R$ {avg_monthly_income:,.0f}/mês",
        delta_color="normal"
    )

with col2:
    st.metric(
        "Despesas Totais (3 meses)",
        f"R$ {total_3m_expenses:,.2f}",
        delta=f"R$ {avg_monthly_expenses:,.0f}/mês",
        delta_color="inverse"
    )

with col3:
    st.metric(
        "Economia Total (3 meses)",
        f"R$ {total_3m_savings:,.2f}",
        delta=f"{avg_savings_rate:.1f}% média",
        delta_color="normal" if total_3m_savings >= 0 else "inverse"
    )

with col4:
    st.metric(
        "Tendência Renda",
        f"{income_trend:+.1f}%",
        delta="vs primeiro mês",
        delta_color="normal" if income_trend >= 0 else "inverse"
    )

# Monthly Comparison Chart
st.markdown("---")
st.subheader("📈 Comparação Mensal")

fig_monthly = go.Figure()

fig_monthly.add_trace(go.Bar(
    x=summary_df['Mês'],
    y=summary_df['Renda'],
    name='Renda',
    marker_color='#00ff88',
    text=[f'R$ {val:,.0f}' for val in summary_df['Renda']],
    textposition='auto'
))

fig_monthly.add_trace(go.Bar(
    x=summary_df['Mês'],
    y=summary_df['Despesas'],
    name='Despesas',
    marker_color='#ff6b6b',
    text=[f'R$ {val:,.0f}' for val in summary_df['Despesas']],
    textposition='auto'
))

fig_monthly.update_layout(
    title='Renda vs Despesas por Mês',
    barmode='group',
    height=500,
    xaxis_title='Mês',
    yaxis_title='Valor (R$)'
)

st.plotly_chart(fig_monthly, use_container_width=True)

# Savings Trend
col1, col2 = st.columns(2)

with col1:
    fig_savings = go.Figure()
    fig_savings.add_trace(go.Scatter(
        x=summary_df['Mês'],
        y=summary_df['Economia'],
        mode='lines+markers',
        name='Economia',
        line=dict(color='#4ecdc4', width=4),
        marker=dict(size=10)
    ))
    
    fig_savings.update_layout(
        title='Evolução da Economia',
        height=400,
        xaxis_title='Mês',
        yaxis_title='Economia (R$)'
    )
    
    st.plotly_chart(fig_savings, use_container_width=True)

with col2:
    fig_savings_rate = go.Figure()
    fig_savings_rate.add_trace(go.Scatter(
        x=summary_df['Mês'],
        y=summary_df['Taxa de Economia (%)'],
        mode='lines+markers',
        name='Taxa de Economia',
        line=dict(color='#ffa726', width=4),
        marker=dict(size=10)
    ))
    
    # Add reference line for 20% savings rate
    fig_savings_rate.add_hline(
        y=20, 
        line_dash="dash", 
        line_color="green",
        annotation_text="Meta: 20%"
    )
    
    fig_savings_rate.update_layout(
        title='Taxa de Economia por Mês',
        height=400,
        xaxis_title='Mês',
        yaxis_title='Taxa de Economia (%)'
    )
    
    st.plotly_chart(fig_savings_rate, use_container_width=True)

# Detailed Analysis Section
st.markdown("---")
st.subheader("🔍 Análise Detalhada")

# Category Analysis (if available)
if 'Categoria' in monthly_data[last_3_months[-1]].columns or 'Category' in monthly_data[last_3_months[-1]].columns:
    category_col = 'Categoria' if 'Categoria' in monthly_data[last_3_months[-1]].columns else 'Category'
    
    # Aggregate expenses by category across all 3 months
    all_expenses = pd.concat([
        monthly_data[month][monthly_data[month]['Valor'].notna()][[category_col, 'Valor']]
        for month in last_3_months
    ])
    
    category_totals = all_expenses.groupby(category_col)['Valor'].sum().sort_values(ascending=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_category = px.pie(
            values=category_totals.values,
            names=category_totals.index,
            title='Despesas por Categoria (3 meses)'
        )
        fig_category.update_layout(height=400)
        st.plotly_chart(fig_category, use_container_width=True)
    
    with col2:
        # Top 5 categories
        st.subheader("🏆 Top 5 Categorias de Despesa")
        for i, (category, amount) in enumerate(category_totals.head().items(), 1):
            percentage = (amount / category_totals.sum()) * 100
            st.metric(
                f"{i}. {category}",
                f"R$ {amount:,.2f}",
                delta=f"{percentage:.1f}% do total"
            )

# Payment Status Analysis
st.markdown("---")
st.subheader("💳 Análise de Pagamentos")

payment_data = []
for month in last_3_months:
    df = monthly_data[month]
    paid = df[df['Pago'] == 'Sim']['Valor'].sum()
    unpaid = df[df['Pago'] != 'Sim']['Valor'].sum()
    payment_data.append({
        'Mês': month,
        'Pagas': paid,
        'Não Pagas': unpaid,
        'Taxa de Pagamento (%)': (paid / (paid + unpaid) * 100) if (paid + unpaid) > 0 else 0
    })

payment_df = pd.DataFrame(payment_data)

col1, col2 = st.columns(2)

with col1:
    fig_payment_status = go.Figure()
    fig_payment_status.add_trace(go.Bar(
        x=payment_df['Mês'],
        y=payment_df['Pagas'],
        name='Pagas',
        marker_color='#00ff88'
    ))
    fig_payment_status.add_trace(go.Bar(
        x=payment_df['Mês'],
        y=payment_df['Não Pagas'],
        name='Não Pagas',
        marker_color='#ff6b6b'
    ))
    
    fig_payment_status.update_layout(
        title='Status dos Pagamentos por Mês',
        barmode='stack',
        height=400
    )
    
    st.plotly_chart(fig_payment_status, use_container_width=True)

with col2:
    fig_payment_rate = go.Figure()
    fig_payment_rate.add_trace(go.Scatter(
        x=payment_df['Mês'],
        y=payment_df['Taxa de Pagamento (%)'],
        mode='lines+markers',
        name='Taxa de Pagamento',
        line=dict(color='#2196f3', width=4),
        marker=dict(size=10)
    ))
    
    fig_payment_rate.add_hline(
        y=90, 
        line_dash="dash", 
        line_color="green",
        annotation_text="Meta: 90%"
    )
    
    fig_payment_rate.update_layout(
        title='Taxa de Pagamento por Mês',
        height=400,
        yaxis_title='Taxa de Pagamento (%)'
    )
    
    st.plotly_chart(fig_payment_rate, use_container_width=True)

# Insights and Recommendations
st.markdown("---")
st.subheader("💡 Insights e Recomendações")

# Calculate insights
avg_monthly_savings = summary_df['Economia'].mean()
savings_volatility = summary_df['Economia'].std()
income_volatility = summary_df['Renda'].std()
expense_volatility = summary_df['Despesas'].std()

col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Estatísticas Importantes")
    
    st.metric("Economia Média Mensal", f"R$ {avg_monthly_savings:,.2f}")
    st.metric("Volatilidade da Economia", f"R$ {savings_volatility:,.2f}")
    st.metric("Volatilidade da Renda", f"R$ {income_volatility:,.2f}")
    st.metric("Volatilidade das Despesas", f"R$ {expense_volatility:,.2f}")

with col2:
    st.subheader("🎯 Recomendações")
    
    # Generate recommendations based on data
    if avg_savings_rate < 20:
        st.warning("⚠️ Sua taxa de economia está abaixo da meta de 20%. Considere reduzir despesas desnecessárias.")
    
    if expense_volatility > income_volatility * 0.5:
        st.info("ℹ️ Suas despesas são muito voláteis. Tente estabilizar seus gastos mensais.")
    
    if income_trend < 0:
        st.error("❌ Sua renda está diminuindo. Considere buscar fontes adicionais de renda.")
    elif income_trend > 5:
        st.success("✅ Excelente! Sua renda está crescendo consistentemente.")
    
    if avg_monthly_savings > 0:
        st.success(f"✅ Você está economizando R$ {avg_monthly_savings:,.2f} por mês em média!")
    
    # Payment recommendations
    avg_payment_rate = payment_df['Taxa de Pagamento (%)'].mean()
    if avg_payment_rate < 90:
        st.warning(f"⚠️ Sua taxa de pagamento é de {avg_payment_rate:.1f}%. Tente pagar mais contas em dia.")

# Summary Table
st.markdown("---")
st.subheader("📋 Resumo dos Últimos 3 Meses")

# Format the summary table
display_df = summary_df.copy()
display_df['Renda'] = display_df['Renda'].apply(lambda x: f"R$ {x:,.2f}")
display_df['Despesas'] = display_df['Despesas'].apply(lambda x: f"R$ {x:,.2f}")
display_df['Bills Pagas'] = display_df['Bills Pagas'].apply(lambda x: f"R$ {x:,.2f}")
display_df['Economia'] = display_df['Economia'].apply(lambda x: f"R$ {x:,.2f}")
display_df['Taxa de Economia (%)'] = display_df['Taxa de Economia (%)'].apply(lambda x: f"{x:.1f}%")

st.dataframe(display_df, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("*Análise gerada automaticamente com base nos dados financeiros dos últimos 3 meses.*")
