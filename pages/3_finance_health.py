import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import numpy as np
import os
import glob
import pdfplumber
import re
import unicodedata

# Configuração da página
st.set_page_config(
    page_title="Saúde Financeira - Análise de Cartão de Crédito",
    page_icon="💳",
    layout="wide"
)

st.title("💳 Análise de Saúde Financeira")
st.markdown("### Raio X dos Gastos e Detalhamento do Cartão de Crédito")


@st.cache_data
def load_credit_card_data():
    """Carrega e processa os dados de múltiplas faturas do cartão de crédito (CSV e PDF, padrão Itaú)"""
    try:
        fatura_files = glob.glob("data/faturas/fatura_*.csv") + glob.glob("data/faturas/fatura_*.pdf")
        if not fatura_files:
            st.error("Nenhum arquivo de fatura encontrado em data/faturas/")
            return None
        all_dataframes = []
        for file_path in fatura_files:
            filename = os.path.basename(file_path)
            parts = filename.replace('.csv', '').replace('.pdf', '').split('_')
            if len(parts) >= 3:
                mes = parts[1]
                cartao = parts[2]
            else:
                mes = "Desconhecido"
                cartao = "Desconhecido"
            if file_path.endswith('.csv'):
                try:
                    # Tentar diferentes encodings e separadores
                    encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
                    df = None
                    
                    for encoding in encodings:
                        try:
                            df = pd.read_csv(file_path, sep=";", encoding=encoding)
                            break
                        except:
                            continue
                    
                    if df is None:
                        # Se nenhum encoding funcionou, tentar com separador automático
                        for encoding in encodings:
                            try:
                                df = pd.read_csv(file_path, encoding=encoding)
                                break
                            except:
                                continue
                    
                    if df is None:
                        st.error(f"Não foi possível ler o arquivo {file_path} com nenhum encoding")
                        continue
                    
                    # Limpar a coluna Valor se existir
                    if 'Valor' in df.columns:
                        df['Valor'] = df['Valor'].astype(str).str.strip()
                        # Remover caracteres especiais e quebras de linha
                        df['Valor'] = df['Valor'].str.replace('\n', '').str.replace('\r', '').replace('\t', '')
                        df['Valor'] = df['Valor'].str.replace('′', '').replace('″', '').replace(' ', ' ')
                        # Remover espaços extras
                        df['Valor'] = df['Valor'].str.strip()
                    
                    # Para arquivos XP, ignorar linhas com "Pagamento de fatura"
                    if 'xp' in filename.lower():
                        # Verificar se existe uma coluna de descrição ou estabelecimento
                        desc_columns = ['Descrição', 'Estabelecimento', 'Descricao', 'Local', 'Local da Compra']
                        for col in desc_columns:
                            if col in df.columns:
                                df = df[~df[col].astype(str).str.contains('Pagamento de fatura', case=False, na=False)]
                                break
                    
                    df['Arquivo_Fonte'] = filename
                    df['Mes_Fatura'] = mes
                    df['Cartao'] = cartao
                    all_dataframes.append(df)
                except Exception as e:
                    st.warning(f"Erro ao carregar {file_path}: {e}")
                    continue
            elif file_path.endswith('.pdf'):
                try:
                    with pdfplumber.open(file_path) as pdf:
                        rows = []
                        portador = None
                        final_cartao = None
                        
                        for page in pdf.pages:
                            text = page.extract_text()
                            if not text:
                                continue
                            
                            for line in text.split('\n'):
                                # Detectar portador pelo padrão Itaú
                                m_portador = re.match(r"Titular\s+([A-Z\s]+)", line.strip())
                                if m_portador:
                                    portador = m_portador.group(1).strip()
                                    continue
                                
                                # Detectar final do cartão pelo padrão Itaú
                                m_cartao = re.match(r"Cart[aã]o\s+.*(\d{4})", line.strip())
                                if m_cartao:
                                    final_cartao = m_cartao.group(1)
                                    continue
                                
                                ano = datetime.now().year
                                transacoes = extract_transactions(line, portador, final_cartao, filename, mes, ano)
                                rows.extend(transacoes)
                        
                        if rows:
                            df = pd.DataFrame(rows)
                            df['Valor'] = df['Valor'].astype(float)
                            all_dataframes.append(df)
                        else:
                            st.warning(f"Nenhuma transação encontrada em {file_path}")
                            # Tentar extrair transações sem verificar portador/cartão
                            alt_rows = []
                            for page in pdf.pages:
                                text = page.extract_text()
                                if not text:
                                    continue
                                for line in text.split('\n'):
                                    # Tentar extrair transações mesmo sem portador/cartão
                                    alt_transacoes = extract_transactions_alternative(line, filename, mes, datetime.now().year)
                                    alt_rows.extend(alt_transacoes)
                            
                            if alt_rows:
                                df = pd.DataFrame(alt_rows)
                                df['Valor'] = df['Valor'].astype(float)
                                all_dataframes.append(df)
                                
                except Exception as e:
                    st.warning(f"Erro ao processar PDF {file_path}: {e}")
                    continue
        if not all_dataframes:
            st.error("Nenhum arquivo foi carregado com sucesso")
            return None
        df_combined = pd.concat(all_dataframes, ignore_index=True)
        
        # Converter a coluna Data para datetime
        df_combined['Data'] = pd.to_datetime(df_combined['Data'], format='%d/%m/%Y', errors='coerce')
        
        # Limpar e converter a coluna Valor (se vier como string)
        if df_combined['Valor'].dtype == object:
            try:
                # Usar a função normaliza_valor para cada valor
                df_combined['Valor'] = df_combined['Valor'].astype(str).apply(normaliza_valor).astype(float)
            except Exception as e:
                st.error(f"Erro na conversão da coluna Valor: {e}")
                raise e
        # Extrair informações de parcelamento
        df_combined['É_Parcelado'] = df_combined['Parcela'].str.contains(r'\d+ de \d+', na=False)
        df_combined['Parcela_Atual'] = df_combined['Parcela'].str.extract(r'(\d+) de \d+').astype(float)
        df_combined['Total_Parcelas'] = df_combined['Parcela'].str.extract(r'\d+ de (\d+)').astype(float)
        # Calcular valor total da compra para itens parcelados
        df_combined['Valor_Total'] = df_combined.apply(
            lambda row: row['Valor'] * row['Total_Parcelas'] 
            if pd.notna(row['Total_Parcelas']) else row['Valor'], 
            axis=1
        )
        # Categorizar estabelecimentos
        def categorize_establishment(estabelecimento):
            estabelecimento_lower = estabelecimento.lower()
            if any(keyword in estabelecimento_lower for keyword in ['uber', 'restaurante', 'pizza', 'cafe', 'padaria', 'supermercado', 'atacadao', 'carrefour', 'havan', 'farmácia']):
                return 'Alimentação'
            elif any(keyword in estabelecimento_lower for keyword in ['posto', 'gasolina', 'combustível', 'uber* trip', 'uber* pending']):
                return 'Transporte'
            elif any(keyword in estabelecimento_lower for keyword in ['vivo', 'starlink', 'openai', 'chatgpt', 'youtube', 'godaddy', 'wondershare', 'academia', 'fitness']):
                return 'Serviços'
            elif any(keyword in estabelecimento_lower for keyword in ['amazon', 'mercadolivre', 'shopee', 'ebay']):
                return 'Compras Online'
            elif any(keyword in estabelecimento_lower for keyword in ['renner', 'modas', 'vestuário', 'roupa', 'sapato']):
                return 'Vestuário'
            elif any(keyword in estabelecimento_lower for keyword in ['farmacia', 'clinica', 'medico', 'saude']):
                return 'Saúde'
            else:
                return 'Outros'
        df_combined['Categoria'] = df_combined['Estabelecimento'].apply(categorize_establishment)
        return df_combined
    except Exception as e:
        st.error(f"Erro ao carregar os dados: {e}")
        return None


@st.cache_data
def normaliza_valor(valor):
    valor_original = valor
    valor = str(valor).strip()
    
    # Remover caracteres especiais e quebras de linha
    valor = valor.replace('\n', '').replace('\r', '').replace('\t', '')
    valor = valor.replace('′', '').replace('″', '').replace(' ', ' ')
    valor = valor.replace('R$', '').replace('R', '').replace('$', '')
    
    # Remover espaços extras
    valor = valor.strip()
    
    # Se o valor estiver vazio ou não contiver números, retornar 0
    if not valor or not re.search(r'\d', valor):
        return '0'
    
    # Remove qualquer caractere que não seja número, ponto, vírgula ou sinal de menos
    valor = re.sub(r'[^0-9.,-]', '', valor)
    
    # Handle negative values
    is_negative = valor.startswith('-')
    if is_negative:
        valor = valor[1:]  # Remove the minus sign temporarily
    
    # Handle Brazilian number format (dots as thousands separators, comma as decimal)
    if ',' in valor:
        # If there's a comma, it's the decimal separator
        valor = valor.replace('.', '').replace(',', '.')
    elif valor.count('.') > 1:
        # Multiple dots means dots are thousands separators
        last_dot = valor.rfind('.')
        valor = valor[:last_dot].replace('.', '') + '.' + valor[last_dot+1:]
    elif valor.count('.') == 1:
        # Single dot - check if it's decimal or thousands separator
        # If the part after dot has 3 digits, it's likely thousands separator
        parts = valor.split('.')
        if len(parts) == 2 and len(parts[1]) == 3:
            # Likely thousands separator (e.g., 1.374)
            valor = valor.replace('.', '')
        # Otherwise, assume it's decimal separator
    
    # Restore negative sign if needed
    if is_negative:
        valor = '-' + valor
    
    # Debug: Log valores problemáticos
    try:
        float_val = float(valor)
        # Se o valor for muito pequeno (menos de 1 real), pode ser um erro de formatação
        if 0 < float_val < 1 and valor_original != valor:
            st.sidebar.warning(f"Valor suspeito: {valor_original} -> {valor} -> {float_val}")
    except:
        st.sidebar.error(f"Erro ao converter valor: {valor_original} -> {valor}")
    
    return valor


@st.cache_data
def extract_transactions(line, portador, final_cartao, filename, mes, ano):
    import re
    # Ignorar se portador ou cartão não foram detectados
    if not portador or not final_cartao:
        return []
    
    # Padrão mais específico para transações: DATA + ESTABELECIMENTO + VALOR
    # Procurar por padrões como: "28/11 APPLE.COM/BILL 7,99" ou "APPLE.COM/BILL 28/11 7,99"
    transacoes = []
    
    # Padrão 1: DATA + ESTABELECIMENTO + VALOR
    pattern1 = r'(\d{2}/\d{2})\s+([A-Z][A-Z\s\.\*\-/]+?)\s+(\d+(?:,\d{2})?)'
    matches1 = re.finditer(pattern1, line)
    
    for match in matches1:
        try:
            data = match.group(1)
            estab = match.group(2).strip()
            valor = match.group(3)
            
            # Verificar se é uma transação válida
            if is_valid_transaction(estab, valor):
                dia, mes_ = data.split('/')
                data_full = f"{dia}/{mes_}/{ano}"
                
                try:
                    valor_float = float(normaliza_valor(valor))
                    
                    transacoes.append({
                        'Data': data_full,
                        'Estabelecimento': estab,
                        'Portador': 'Jorge Leite' if 'itau' in filename.lower() else portador.title(),
                        'Valor': valor_float,
                        'Parcela': '-',
                        'Arquivo_Fonte': filename,
                        'Mes_Fatura': mes,
                        'Cartao': 'Itaú' if 'itau' in filename.lower() else final_cartao
                    })
                except Exception as e:
                    continue
        except Exception as e:
            continue
    
    # Padrão 2: ESTABELECIMENTO + DATA + VALOR (mais flexível)
    pattern2 = r'([A-Z][A-Z\s\.\*\-/]+?)\s+(\d{2}/\d{2})\s+(\d+(?:,\d{2})?)'
    matches2 = re.finditer(pattern2, line)
    
    for match in matches2:
        try:
            estab = match.group(1).strip()
            data = match.group(2)
            valor = match.group(3)
            
            # Verificar se é uma transação válida
            if is_valid_transaction(estab, valor):
                dia, mes_ = data.split('/')
                data_full = f"{dia}/{mes_}/{ano}"
                
                try:
                    valor_float = float(normaliza_valor(valor))
                    
                    transacoes.append({
                        'Data': data_full,
                        'Estabelecimento': estab,
                        'Portador': 'Jorge Leite' if 'itau' in filename.lower() else portador.title(),
                        'Valor': valor_float,
                        'Parcela': '-',
                        'Arquivo_Fonte': filename,
                        'Mes_Fatura': mes,
                        'Cartao': 'Itaú' if 'itau' in filename.lower() else final_cartao
                    })
                except Exception as e:
                    continue
        except Exception as e:
            continue
    
    return transacoes

def is_valid_transaction(estab, valor):
    """Verifica se a transação é válida baseada no estabelecimento e valor"""
    import re
    
    # Ignorar estabelecimentos vazios ou só símbolos
    if not estab or not re.search(r'[A-Za-z]', estab):
        return False
    
    # Lista de termos a ignorar
    termos_ignorar = [
        "lançamentos", "lançamentosnocartão", "lançamentosinternacionais", 
        "total", "saldo", "pagamento", "fatura", "seguro", "iof", "cet", 
        "juros", "multa", "anterior", "atual", "proximo", "vencimento", 
        "limite", "disponivel", "produtos", "serviços", "compras", 
        "parceladas", "demais", "faturas", "próximas", "estorno", 
        "anuidade", "diferencia", "previsão", "período", "processo",
        "seguradora", "corretora", "cnpj", "cpf", "documento", "número"
    ]
    
    if any(x in estab.lower() for x in termos_ignorar):
        return False
    
    # Verificar se o valor é válido (não é apenas números de data)
    try:
        valor_float = float(normaliza_valor(valor))
        # Ignorar valores muito pequenos (menos de 1 real) ou muito grandes (mais de 10000)
        if valor_float < 1.0 or valor_float > 10000.0:
            return False
    except:
        return False
    
    return True


@st.cache_data
def extract_transactions_alternative(line, filename, mes, ano):
    """Função alternativa para extrair transações sem verificar portador/cartão"""
    import re
    
    # Usar a mesma lógica melhorada da função principal
    transacoes = []
    
    # Padrão 1: DATA + ESTABELECIMENTO + VALOR
    pattern1 = r'(\d{2}/\d{2})\s+([A-Z][A-Z\s\.\*\-/]+?)\s+(\d+(?:,\d{2})?)'
    matches1 = re.finditer(pattern1, line)
    
    for match in matches1:
        try:
            data = match.group(1)
            estab = match.group(2).strip()
            valor = match.group(3)
            
            # Verificar se é uma transação válida
            if is_valid_transaction(estab, valor):
                dia, mes_ = data.split('/')
                data_full = f"{dia}/{mes_}/{ano}"
                
                try:
                    valor_float = float(normaliza_valor(valor))
                    
                    transacoes.append({
                        'Data': data_full,
                        'Estabelecimento': estab,
                        'Portador': 'Jorge Leite' if 'itau' in filename.lower() else 'Desconhecido',
                        'Valor': valor_float,
                        'Parcela': '-',
                        'Arquivo_Fonte': filename,
                        'Mes_Fatura': mes,
                        'Cartao': 'Itaú' if 'itau' in filename.lower() else 'Desconhecido'
                    })
                except Exception as e:
                    continue
        except Exception as e:
            continue
    
    # Padrão 2: ESTABELECIMENTO + DATA + VALOR (mais flexível)
    pattern2 = r'([A-Z][A-Z\s\.\*\-/]+?)\s+(\d{2}/\d{2})\s+(\d+(?:,\d{2})?)'
    matches2 = re.finditer(pattern2, line)
    
    for match in matches2:
        try:
            estab = match.group(1).strip()
            data = match.group(2)
            valor = match.group(3)
            
            # Verificar se é uma transação válida
            if is_valid_transaction(estab, valor):
                dia, mes_ = data.split('/')
                data_full = f"{dia}/{mes_}/{ano}"
                
                try:
                    valor_float = float(normaliza_valor(valor))
                    
                    transacoes.append({
                        'Data': data_full,
                        'Estabelecimento': estab,
                        'Portador': 'Jorge Leite' if 'itau' in filename.lower() else 'Desconhecido',
                        'Valor': valor_float,
                        'Parcela': '-',
                        'Arquivo_Fonte': filename,
                        'Mes_Fatura': mes,
                        'Cartao': 'Itaú' if 'itau' in filename.lower() else 'Desconhecido'
                    })
                except Exception as e:
                    continue
        except Exception as e:
            continue
    
    return transacoes


@st.cache_data
def normaliza_mes(mes):
    if not isinstance(mes, str):
        return mes
    mes = mes.lower().strip()
    mes = ''.join(c for c in unicodedata.normalize('NFD', mes) if unicodedata.category(c) != 'Mn')
    return mes

meses_ordem = {
    'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'abril': 4, 'maio': 5, 'junho': 6,
    'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
}
meses_labels = ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

# Carregar dados
df = load_credit_card_data()

if df is not None:
    # Filtros
    st.sidebar.header("🔍 Filtros")
    
    # Filtro por período
    min_date = df['Data'].min()
    max_date = df['Data'].max()
    
    date_range = st.sidebar.date_input(
        "Período de Análise",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date()
    )
    
    # Filtro por portador
    portadores = ['Todos'] + list(df['Portador'].unique())
    portador_selecionado = st.sidebar.selectbox("Portador", portadores)
    
    # Filtro por cartão
    cartoes = ['Todos'] + list(df['Cartao'].unique())
    cartao_selecionado = st.sidebar.selectbox("Cartão", cartoes)
    
    # Filtro por mês da fatura
    meses_fatura = ['Todos'] + list(df['Mes_Fatura'].unique())
    mes_fatura_selecionado = st.sidebar.selectbox("Mês da Fatura", meses_fatura)
    
    # Aplicar filtros
    if len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df[
            (df['Data'].dt.date >= start_date) & 
            (df['Data'].dt.date <= end_date)
        ]
    else:
        df_filtered = df.copy()
    
    if portador_selecionado != 'Todos':
        df_filtered = df_filtered[df_filtered['Portador'] == portador_selecionado]
    
    if cartao_selecionado != 'Todos':
        df_filtered = df_filtered[df_filtered['Cartao'] == cartao_selecionado]
    
    if mes_fatura_selecionado != 'Todos':
        df_filtered = df_filtered[df_filtered['Mes_Fatura'] == mes_fatura_selecionado]
    
    # 📊 Métricas Principais
    st.header("📊 Métricas Principais")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_gasto = df_filtered['Valor'].sum()
        st.metric(
            "Total Gasto",
            f"R$ {total_gasto:,.2f}",
            help="Soma de todos os gastos no período"
        )
    with col2:
        total_transacoes = len(df_filtered)
        st.metric(
            "Total Transações",
            f"{total_transacoes:,}",
            help="Número total de transações"
        )
    with col3:
        gasto_medio = df_filtered['Valor'].mean()
        st.metric(
            "Gasto Médio",
            f"R$ {gasto_medio:,.2f}",
            help="Valor médio por transação"
        )
    with col4:
        transacoes_parceladas = df_filtered['É_Parcelado'].sum()
        st.metric(
            "Transações Parceladas",
            f"{transacoes_parceladas}",
            help="Número de transações parceladas"
        )
    
    # Análise por Cartão
    st.header("💳 Análise por Cartão")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de pizza por cartão
        gastos_por_cartao = df_filtered.groupby('Cartao')['Valor'].sum().sort_values(ascending=False)
        
        fig_cartao = px.pie(
            values=gastos_por_cartao.values,
            names=gastos_por_cartao.index,
            title="Distribuição de Gastos por Cartão"
        )
        fig_cartao.update_layout(height=400)
        st.plotly_chart(fig_cartao, use_container_width=True)
    
    with col2:
        # Tabela detalhada por cartão
        resumo_cartao = df_filtered.groupby('Cartao').agg({
            'Valor': ['sum', 'count', 'mean'],
            'É_Parcelado': 'sum'
        }).round(2)
        
        resumo_cartao.columns = ['Total Gasto', 'Nº Transações', 'Gasto Médio', 'Transações Parceladas']
        resumo_cartao = resumo_cartao.sort_values('Total Gasto', ascending=False)
        
        st.subheader("Resumo por Cartão")
        st.dataframe(resumo_cartao, use_container_width=True)
    
    # Análise por Portador
    st.header("👥 Análise por Portador")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de pizza por portador
        gastos_por_portador = df_filtered.groupby('Portador')['Valor'].sum().sort_values(ascending=False)
        
        fig_portador = px.pie(
            values=gastos_por_portador.values,
            names=gastos_por_portador.index,
            title="Distribuição de Gastos por Portador"
        )
        fig_portador.update_layout(height=400)
        st.plotly_chart(fig_portador, use_container_width=True)
    
    with col2:
        # Tabela detalhada por portador
        resumo_portador = df_filtered.groupby('Portador').agg({
            'Valor': ['sum', 'count', 'mean'],
            'É_Parcelado': 'sum'
        }).round(2)
        
        resumo_portador.columns = ['Total Gasto', 'Nº Transações', 'Gasto Médio', 'Transações Parceladas']
        resumo_portador = resumo_portador.sort_values('Total Gasto', ascending=False)
        
        st.subheader("Resumo por Portador")
        st.dataframe(resumo_portador, use_container_width=True)
    
    # Análise por Categoria
    st.header("📂 Análise por Categoria")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de barras por categoria
        gastos_por_categoria = df_filtered.groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
        
        fig_categoria = px.bar(
            x=gastos_por_categoria.index,
            y=gastos_por_categoria.values,
            title="Gastos por Categoria",
            labels={'x': 'Categoria', 'y': 'Valor (R$)'}
        )
        fig_categoria.update_layout(height=400)
        st.plotly_chart(fig_categoria, use_container_width=True)
    
    with col2:
        # Gráfico de pizza por categoria
        fig_categoria_pie = px.pie(
            values=gastos_por_categoria.values,
            names=gastos_por_categoria.index,
            title="Distribuição por Categoria"
        )
        fig_categoria_pie.update_layout(height=400)
        st.plotly_chart(fig_categoria_pie, use_container_width=True)
    
    # Análise Temporal
    st.header("📅 Análise Temporal")
    
    # Agrupar por mês
    df_filtered['Mes'] = df_filtered['Data'].dt.to_period('M')
    gastos_mensais = df_filtered.groupby('Mes')['Valor'].sum().reset_index()
    gastos_mensais['Mes'] = gastos_mensais['Mes'].astype(str)
    
    fig_temporal = px.line(
        gastos_mensais,
        x='Mes',
        y='Valor',
        title="Evolução dos Gastos ao Longo do Tempo",
        labels={'Mes': 'Mês', 'Valor': 'Valor (R$)'}
    )
    fig_temporal.update_layout(height=400)
    st.plotly_chart(fig_temporal, use_container_width=True)
    
    # Análise por Mês da Fatura
    st.header("📋 Análise por Mês da Fatura")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de barras por mês da fatura
        gastos_por_mes_fatura = df_filtered.groupby('Mes_Fatura')['Valor'].sum().sort_values(ascending=False)
        
        fig_mes_fatura = px.bar(
            x=gastos_por_mes_fatura.index,
            y=gastos_por_mes_fatura.values,
            title="Gastos por Mês da Fatura",
            labels={'x': 'Mês da Fatura', 'y': 'Valor (R$)'}
        )
        fig_mes_fatura.update_layout(height=400)
        st.plotly_chart(fig_mes_fatura, use_container_width=True)
    
    with col2:
        # Tabela detalhada por mês da fatura
        resumo_mes_fatura = df_filtered.groupby('Mes_Fatura').agg({
            'Valor': ['sum', 'count', 'mean'],
            'É_Parcelado': 'sum'
        }).round(2)
        
        resumo_mes_fatura.columns = ['Total Gasto', 'Nº Transações', 'Gasto Médio', 'Transações Parceladas']
        resumo_mes_fatura = resumo_mes_fatura.sort_values('Total Gasto', ascending=False)
        
        st.subheader("Resumo por Mês da Fatura")
        st.dataframe(resumo_mes_fatura, use_container_width=True)
    
    # Análise de Parcelamento
    st.header("💳 Análise de Parcelamento")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Estatísticas de parcelamento
        parceladas = df_filtered[df_filtered['É_Parcelado'] == True]
        nao_parceladas = df_filtered[df_filtered['É_Parcelado'] == False]
        
        fig_parcelamento = go.Figure(data=[go.Pie(
            labels=['Parceladas', 'À Vista'],
            values=[len(parceladas), len(nao_parceladas)],
            marker_colors=['#ff6b6b', '#4ecdc4']
        )])
        fig_parcelamento.update_layout(
            title="Distribuição: Parceladas vs À Vista",
            height=400
        )
        st.plotly_chart(fig_parcelamento, use_container_width=True)
    
    with col2:
        # Valor total em parcelas
        if len(parceladas) > 0:
            valor_total_parcelas = parceladas['Valor_Total'].sum()
            valor_atual_parcelas = parceladas['Valor'].sum()
            
            st.subheader("Resumo de Parcelamento")
            st.metric("Valor Total em Parcelas", f"R$ {valor_total_parcelas:,.2f}")
            st.metric("Valor Atual das Parcelas", f"R$ {valor_atual_parcelas:,.2f}")
            st.metric("Valor Restante", f"R$ {valor_total_parcelas - valor_atual_parcelas:,.2f}")
        else:
            st.info("Nenhuma transação parcelada encontrada no período selecionado.")
    
    # Top Estabelecimentos
    st.header("🏪 Top Estabelecimentos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top 10 por valor
        top_estabelecimentos_valor = df_filtered.groupby('Estabelecimento')['Valor'].sum().sort_values(ascending=False).head(10)
        
        fig_top_valor = px.bar(
            x=top_estabelecimentos_valor.values,
            y=top_estabelecimentos_valor.index,
            orientation='h',
            title="Top 10 Estabelecimentos por Valor",
            labels={'x': 'Valor (R$)', 'y': 'Estabelecimento'}
        )
        fig_top_valor.update_layout(height=500)
        st.plotly_chart(fig_top_valor, use_container_width=True)
    
    with col2:
        # Top 10 por frequência
        top_estabelecimentos_freq = df_filtered['Estabelecimento'].value_counts().head(10)
        
        fig_top_freq = px.bar(
            x=top_estabelecimentos_freq.values,
            y=top_estabelecimentos_freq.index,
            orientation='h',
            title="Top 10 Estabelecimentos por Frequência",
            labels={'x': 'Número de Transações', 'y': 'Estabelecimento'}
        )
        fig_top_freq.update_layout(height=500)
        st.plotly_chart(fig_top_freq, use_container_width=True)
    
    # Tabela detalhada
    st.header("📋 Detalhamento Completo")
    
    # Adicionar filtros para a tabela
    col1, col2, col3 = st.columns(3)
    
    with col1:
        categorias = ['Todas'] + list(df_filtered['Categoria'].unique())
        categoria_filtro = st.selectbox("Filtrar por Categoria", categorias)
    
    with col2:
        parcelamento_filtro = st.selectbox("Filtrar por Parcelamento", ['Todos', 'Parceladas', 'À Vista'])
    
    with col3:
        # Ordenação
        ordenacao = st.selectbox("Ordenar por", ['Data', 'Valor', 'Estabelecimento', 'Portador', 'Cartao'])
    
    # Aplicar filtros à tabela
    df_tabela = df_filtered.copy()
    
    if categoria_filtro != 'Todas':
        df_tabela = df_tabela[df_tabela['Categoria'] == categoria_filtro]
    
    if parcelamento_filtro == 'Parceladas':
        df_tabela = df_tabela[df_tabela['É_Parcelado'] == True]
    elif parcelamento_filtro == 'À Vista':
        df_tabela = df_tabela[df_tabela['É_Parcelado'] == False]
    
    # Ordenar
    if ordenacao == 'Data':
        df_tabela = df_tabela.sort_values('Data', ascending=False)
    elif ordenacao == 'Valor':
        df_tabela = df_tabela.sort_values('Valor', ascending=False)
    elif ordenacao == 'Estabelecimento':
        df_tabela = df_tabela.sort_values('Estabelecimento')
    elif ordenacao == 'Portador':
        df_tabela = df_tabela.sort_values('Portador')
    elif ordenacao == 'Cartao':
        df_tabela = df_tabela.sort_values('Cartao')
    
    # Formatar para exibição
    df_exibicao = df_tabela[['Data', 'Estabelecimento', 'Portador', 'Cartao', 'Valor', 'Categoria', 'Parcela', 'Mes_Fatura']].copy()
    df_exibicao['Data'] = df_exibicao['Data'].dt.strftime('%d/%m/%Y')
    df_exibicao['Valor'] = df_exibicao['Valor'].apply(lambda x: f"R$ {x:,.2f}")
    
    st.dataframe(df_exibicao, use_container_width=True)
    
    # Download dos dados
    st.header("💾 Exportar Dados")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV
        csv = df_tabela.to_csv(index=False, sep=';', encoding='utf-8-sig')
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"analise_cartao_credito_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Excel
        buffer = pd.ExcelWriter('temp_analise.xlsx', engine='openpyxl')
        df_tabela.to_excel(buffer, index=False, sheet_name='Dados')
        
        # Criar aba de resumo
        resumo = pd.DataFrame({
            'Métrica': ['Total Gasto', 'Total Transações', 'Gasto Médio', 'Transações Parceladas'],
            'Valor': [total_gasto, total_transacoes, gasto_medio, transacoes_parceladas]
        })
        resumo.to_excel(buffer, index=False, sheet_name='Resumo')
        
        buffer.close()
        
        with open('temp_analise.xlsx', 'rb') as f:
            excel_data = f.read()
        
        st.download_button(
            label="📥 Download Excel",
            data=excel_data,
            file_name=f"analise_cartao_credito_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.error("Não foi possível carregar os dados das faturas. Verifique se existem arquivos CSV ou PDF na pasta 'data/faturas/' com o padrão 'fatura_[mes]_[cartao].csv' ou 'fatura_[mes]_[cartao].pdf'.")

