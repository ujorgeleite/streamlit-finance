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
    page_title="Evolução Mensal - Análise de Cartão de Crédito",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Evolução Mensal Financeira")
st.markdown("### Análise da Evolução dos Gastos ao Longo do Tempo")


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
                        
                        # Debug: Log do arquivo sendo processado
                        st.sidebar.write(f"Processando PDF: {filename}")
                        
                        for page in pdf.pages:
                            text = page.extract_text()
                            if not text:
                                continue
                            
                            # Debug: Mostrar mais linhas do texto extraído
                            if portador is None:
                                st.sidebar.write(f"Primeiras linhas do PDF:")
                                for i, line in enumerate(text.split('\n')[:10]):
                                    st.sidebar.write(f"  {i+1}: {line}")
                            
                            # Debug: Mostrar linhas que contêm datas
                            linhas_com_data = []
                            for i, line in enumerate(text.split('\n')):
                                if re.search(r'\d{2}/\d{2}', line):
                                    linhas_com_data.append((i+1, line))
                            
                            if linhas_com_data:
                                st.sidebar.write(f"Linhas com datas encontradas:")
                                for num, linha in linhas_com_data[:5]:  # Mostrar primeiras 5
                                    st.sidebar.write(f"  {num}: {linha}")
                            
                            for line in text.split('\n'):
                                # Detectar portador pelo padrão Itaú
                                m_portador = re.match(r"Titular\s+([A-Z\s]+)", line.strip())
                                if m_portador:
                                    portador = m_portador.group(1).strip()
                                    st.sidebar.write(f"Portador detectado: {portador}")
                                    continue
                                
                                # Detectar final do cartão pelo padrão Itaú
                                m_cartao = re.match(r"Cart[aã]o\s+.*(\d{4})", line.strip())
                                if m_cartao:
                                    final_cartao = m_cartao.group(1)
                                    st.sidebar.write(f"Final do cartão detectado: {final_cartao}")
                                    continue
                                
                                ano = datetime.now().year
                                transacoes = extract_transactions(line, portador, final_cartao, filename, mes, ano)
                                rows.extend(transacoes)
                        
                        # Debug: Log do resultado
                        st.sidebar.write(f"Portador final: {portador}")
                        st.sidebar.write(f"Final do cartão final: {final_cartao}")
                        st.sidebar.write(f"Total de transações extraídas: {len(rows)}")
                        
                        if rows:
                            df = pd.DataFrame(rows)
                            df['Valor'] = df['Valor'].astype(float)
                            all_dataframes.append(df)
                        else:
                            st.warning(f"Nenhuma transação encontrada em {file_path}")
                            # Debug: Tentar extrair transações sem verificar portador/cartão
                            st.sidebar.write("Tentando extração alternativa...")
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
                                st.sidebar.write(f"Transações alternativas encontradas: {len(alt_rows)}")
                                df = pd.DataFrame(alt_rows)
                                df['Valor'] = df['Valor'].astype(float)
                                all_dataframes.append(df)
                            else:
                                st.sidebar.write("Nenhuma transação encontrada mesmo com método alternativo")
                                
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
    
    # Gráfico principal: Evolução agregada do valor total das faturas mensalmente (barras por cartão + barra total)
    st.header("📊 Evolução Mensal por Cartão e Total Agregado")
    
    # Usar o mês da fatura para agrupamento, não a data da transação - COM FILTROS aplicados
    barras = df_filtered.groupby(['Mes_Fatura', 'Cartao'])['Valor'].sum().reset_index()
    total_agg = df_filtered.groupby('Mes_Fatura')['Valor'].sum().reset_index()

    barras['Mes_Normalizado'] = barras['Mes_Fatura'].apply(normaliza_mes)
    barras['Mes_Ordem'] = barras['Mes_Normalizado'].map(meses_ordem)
    total_agg['Mes_Normalizado'] = total_agg['Mes_Fatura'].apply(normaliza_mes)
    total_agg['Mes_Ordem'] = total_agg['Mes_Normalizado'].map(meses_ordem)

    barras = barras.sort_values('Mes_Ordem')
    total_agg = total_agg.sort_values('Mes_Ordem')

    fig = go.Figure()
    for cartao in barras['Cartao'].unique():
        df_cartao = barras[barras['Cartao'] == cartao]
        fig.add_trace(go.Bar(
            x=df_cartao['Mes_Fatura'],
            y=df_cartao['Valor'],
            name=f"Cartão: {cartao}"
        ))
    fig.add_trace(go.Bar(
        x=total_agg['Mes_Fatura'],
        y=total_agg['Valor'],
        name="Total Agregado",
        marker_color='black',
        opacity=0.7
    ))
    fig.update_layout(
        barmode='group',
        xaxis_title='Mês da Fatura',
        yaxis_title='Valor Total (R$)',
        title='Evolução Mensal do Valor Total das Faturas por Cartão e Total Agregado',
        height=500,
        xaxis=dict(categoryorder='array', categoryarray=[m.capitalize() for m in meses_labels])
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Análise de tendência
    st.header("📈 Análise de Tendência")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Calcular crescimento mensal
        total_agg['Crescimento_Mensal'] = total_agg['Valor'].pct_change() * 100
        
        fig_crescimento = px.line(
            total_agg,
            x='Mes_Fatura',
            y='Crescimento_Mensal',
            title="Crescimento Mensal (%)",
            labels={'Crescimento_Mensal': 'Crescimento (%)', 'Mes_Fatura': 'Mês da Fatura'}
        )
        fig_crescimento.add_hline(y=0, line_dash="dash", line_color="red")
        fig_crescimento.update_layout(height=400)
        st.plotly_chart(fig_crescimento, use_container_width=True)
    
    with col2:
        # Média móvel
        total_agg['Media_Movel'] = total_agg['Valor'].rolling(window=3, min_periods=1).mean()
        
        fig_media_movel = go.Figure()
        fig_media_movel.add_trace(go.Scatter(
            x=total_agg['Mes_Fatura'],
            y=total_agg['Valor'],
            mode='lines+markers',
            name='Valor Real',
            line=dict(color='blue')
        ))
        fig_media_movel.add_trace(go.Scatter(
            x=total_agg['Mes_Fatura'],
            y=total_agg['Media_Movel'],
            mode='lines',
            name='Média Móvel (3 meses)',
            line=dict(color='red', dash='dash')
        ))
        fig_media_movel.update_layout(
            title="Evolução com Média Móvel",
            xaxis_title='Mês da Fatura',
            yaxis_title='Valor Total (R$)',
            height=400
        )
        st.plotly_chart(fig_media_movel, use_container_width=True)
    
    # Estatísticas mensais
    st.header("📊 Estatísticas Mensais")
    
    # Calcular estatísticas por mês
    stats_mensais = total_agg.copy()
    stats_mensais['Mes_Numero'] = stats_mensais['Mes_Ordem']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        mes_maior_gasto = stats_mensais.loc[stats_mensais['Valor'].idxmax(), 'Mes_Fatura']
        valor_maior_gasto = stats_mensais['Valor'].max()
        st.metric(
            "Mês com Maior Gasto",
            mes_maior_gasto,
            f"R$ {valor_maior_gasto:,.2f}"
        )
    
    with col2:
        mes_menor_gasto = stats_mensais.loc[stats_mensais['Valor'].idxmin(), 'Mes_Fatura']
        valor_menor_gasto = stats_mensais['Valor'].min()
        st.metric(
            "Mês com Menor Gasto",
            mes_menor_gasto,
            f"R$ {valor_menor_gasto:,.2f}"
        )
    
    with col3:
        media_mensal = stats_mensais['Valor'].mean()
        st.metric(
            "Média Mensal",
            f"R$ {media_mensal:,.2f}"
        )
    
    with col4:
        desvio_padrao = stats_mensais['Valor'].std()
        st.metric(
            "Desvio Padrão",
            f"R$ {desvio_padrao:,.2f}"
        )
    
    # Tabela detalhada mensal
    st.header("📋 Detalhamento Mensal")
    
    # Preparar dados para exibição
    df_exibicao = stats_mensais[['Mes_Fatura', 'Valor', 'Crescimento_Mensal', 'Media_Movel']].copy()
    df_exibicao['Valor'] = df_exibicao['Valor'].apply(lambda x: f"R$ {x:,.2f}")
    df_exibicao['Crescimento_Mensal'] = df_exibicao['Crescimento_Mensal'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "-")
    df_exibicao['Media_Movel'] = df_exibicao['Media_Movel'].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "-")
    df_exibicao.columns = ['Mês da Fatura', 'Valor Total', 'Crescimento (%)', 'Média Móvel']
    
    st.dataframe(df_exibicao, use_container_width=True)
    
    # Download dos dados
    st.header("💾 Exportar Dados")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV
        csv = stats_mensais.to_csv(index=False, sep=';', encoding='utf-8-sig')
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"evolucao_mensal_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Excel
        buffer = pd.ExcelWriter('temp_evolucao_mensal.xlsx', engine='openpyxl')
        stats_mensais.to_excel(buffer, index=False, sheet_name='Dados')
        
        # Criar aba de resumo
        resumo = pd.DataFrame({
            'Métrica': ['Maior Gasto Mensal', 'Menor Gasto Mensal', 'Média Mensal', 'Desvio Padrão'],
            'Valor': [valor_maior_gasto, valor_menor_gasto, media_mensal, desvio_padrao]
        })
        resumo.to_excel(buffer, index=False, sheet_name='Resumo')
        
        buffer.close()
        
        with open('temp_evolucao_mensal.xlsx', 'rb') as f:
            excel_data = f.read()
        
        st.download_button(
            label="📥 Download Excel",
            data=excel_data,
            file_name=f"evolucao_mensal_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.error("Não foi possível carregar os dados das faturas. Verifique se existem arquivos CSV ou PDF na pasta 'data/faturas/' com o padrão 'fatura_[mes]_[cartao].csv' ou 'fatura_[mes]_[cartao].pdf'.")
