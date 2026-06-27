import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import matplotlib.pyplot as plt

# Configuração da página para ocupar a tela toda
st.set_page_config(page_title="Luthan Investimentos", page_icon="🏢", layout="wide")

# ==========================================
# 0. SISTEMA DE LOGIN (PÁGINA INICIAL)
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    col_imagem, col_login = st.columns([1.2, 1], gap="large")
    
    with col_imagem:
        # Caminho da imagem da tela inicial que você já configurou
        caminho_da_imagem = r"C:\Users\Nathan\Desktop\Luthan_Investimentos\capa.png.png"
        
        try:
            st.image(caminho_da_imagem, use_container_width=True)
        except:
            st.warning(f"⚠️ Imagem de capa não encontrada. Verifique o caminho: {caminho_da_imagem}")
            
    with col_login:
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #C5A059;'>LUTHAN</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #FAFAFA;'>Private Access</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #A0A0A0;'>Portal de Análise de Viabilidade Econômica</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        nome_cliente = st.text_input("Identificação do Investidor:", placeholder="Ex: Thiago Moreno")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Acessar Projeções 📊", use_container_width=True):
            if nome_cliente.strip().lower() == "thiago moreno":
                st.session_state['autenticado'] = True
                st.rerun()
            elif nome_cliente == "":
                st.warning("Por favor, digite o seu nome.")
            else:
                st.error("❌ Acesso Negado: Cliente não localizado em nossa base ativa.")

# ==========================================
# CÓDIGO DO DASHBOARD (SÓ APARECE SE AUTENTICADO)
# ==========================================
else:
    # 1. DADOS DE ENTRADA E CAMINHOS DAS FOTOS DOS ANÚNCIOS
    imoveis = {
        'Casa na Armação': {
            'investimento': 1027000, 'aluguel_mensal': 5500, 'despesa_anual': 5000,
            'foto1': r"C:\Users\Nathan\Desktop\Luthan_Investimentos\CASA_1_.png.png", 
            'foto2': r"C:\Users\Nathan\Desktop\Luthan_Investimentos\casa_2_.png.png"
        },
        'Apto na Planta (Jurerê)': {
            'investimento': 1064000, 'aluguel_mensal': 6000, 'despesa_anual': 8000,
            'foto1': r"C:\Users\Nathan\Desktop\Luthan_Investimentos\jurere1.png.png", 
            'foto2': r"C:\Users\Nathan\Desktop\Luthan_Investimentos\jurere2.png.png"
        },
        'Sala Comercial (Centro)': {
            'investimento': 950000, 'aluguel_mensal': 6500, 'despesa_anual': 10000,
            'foto1': r"C:\Users\Nathan\Desktop\Luthan_Investimentos\sala1.png.png", 
            'foto2': r"C:\Users\Nathan\Desktop\Luthan_Investimentos\sala2.png.png"
        },
        'Apto (Trindade)': {
            'investimento': 1000000, 'aluguel_mensal': 5000, 'despesa_anual': 7000,
            'foto1': r"C:\Users\Nathan\Desktop\Luthan_Investimentos\trindade1.png.png", 
            'foto2': r"C:\Users\Nathan\Desktop\Luthan_Investimentos\trindade2.png"
        }
    }

   # 2. MENU LATERAL E PREMISSAS
    st.sidebar.markdown("### 👤 Área do Cliente")
    
    # --- NOVO: ESPAÇO PARA A FOTO DO PROFESSOR ---
    try:
        # Tenta carregar a foto do professor da pasta do projeto
        st.sidebar.image("professor.png", width=120, caption="Thiago Moreno")
    except:
        # Caso a foto não seja encontrada, exibe um ícone de placeholder
        st.sidebar.info("📷 Espaço para Foto do Cliente")
    # ---------------------------------------------
    
    st.sidebar.success("Bem-vindo, **Thiago Moreno**!")
    
    if st.sidebar.button("Sair do Sistema"):
        st.session_state['autenticado'] = False
        st.rerun()
        
    st.sidebar.markdown("---")
    st.sidebar.header("🏢 Luthan Investimentos")
    imovel_selecionado = st.sidebar.selectbox("Selecione o Imóvel:", list(imoveis.keys()))

    st.sidebar.subheader("Horizonte de Análise")
    horizonte_str = st.sidebar.radio("Tempo até a venda (Anos):", ["5", "10"])
    horizonte = int(horizonte_str)

    st.sidebar.subheader("Análise de Sensibilidade")
    var_aluguel = st.sidebar.slider("Variação do Aluguel (%)", -15.0, 15.0, 0.0, 1.0)
    tma_base = st.sidebar.slider("TMA Base (% a.a.)", 8.0, 20.0, 10.0, 0.5)
    var_valorizacao = st.sidebar.slider("Valorização na Revenda (%)", -10.0, 10.0, 0.0, 1.0)

    inflacao = 0.045
    taxa_juros = 0.16
    aliquota_irpj = 0.15
    aliquota_csll = 0.09
    prazo_financiamento = 10

    dados = imoveis[imovel_selecionado]
    invest_total = dados['investimento']
    entrada = invest_total * 0.30
    financiado = invest_total * 0.70

    aluguel_anual_base = (dados['aluguel_mensal'] * 12) * (1 + (var_aluguel / 100))
    despesa_anual_base = dados['despesa_anual']

    # 3. CÁLCULO DA TABELA SAC
    amortizacao = financiado / prazo_financiamento
    tabela_sac = []
    saldo_devedor = financiado

    for ano in range(1, prazo_financiamento + 1):
        juros = saldo_devedor * taxa_juros
        prestacao = amortizacao + juros
        saldo_anterior = saldo_devedor
        saldo_devedor -= amortizacao
        tabela_sac.append({
            'Ano': ano,
            'Saldo Inicial': saldo_anterior,
            'Amortização': amortizacao,
            'Juros': juros,
            'Prestação': prestacao,
            'Saldo Final': saldo_devedor
        })

    df_sac = pd.DataFrame(tabela_sac)

    # 4. FLUXO DE CAIXA E TRIBUTAÇÃO
    fluxo_caixa = []
    fator_inflacao_revenda = (1 + inflacao) ** horizonte
    valor_revenda_base = invest_total * fator_inflacao_revenda
    valor_revenda_final = valor_revenda_base * (1 + (var_valorizacao / 100))

    fluxo_caixa.append({
        'Ano': 0, 'Receita (Aluguel + Venda)': 0, 'Despesa Operacional': 0,
        'Fluxo Empreendimento (S/ Finan.)': -invest_total, 'Juros SAC': 0, 'Amortização SAC': 0,
        'Impostos (IRPJ + CSLL)': 0, 'Fluxo Acionista (C/ Finan.)': -entrada
    })

    for ano in range(1, horizonte + 1):
        fator_inflacao = (1 + inflacao) ** ano
        rec_aluguel = aluguel_anual_base * fator_inflacao
        desp_op = despesa_anual_base * fator_inflacao
        
        rec_venda = valor_revenda_final if ano == horizonte else 0
        receita_total = rec_aluguel + rec_venda
        fluxo_emp = receita_total - desp_op
        
        juros_ano = df_sac.loc[df_sac['Ano'] == ano, 'Juros'].values[0] if ano <= prazo_financiamento else 0
        amort_ano = df_sac.loc[df_sac['Ano'] == ano, 'Amortização'].values[0] if ano <= prazo_financiamento else 0
        
        lucro_tributavel = receita_total - desp_op - juros_ano
        impostos = lucro_tributavel * (aliquota_irpj + aliquota_csll) if lucro_tributavel > 0 else 0
        
        quitacao = df_sac.loc[df_sac['Ano'] == ano, 'Saldo Final'].values[0] if ano == horizonte and horizonte < prazo_financiamento else 0
        fluxo_acionista = receita_total - desp_op - juros_ano - amort_ano - impostos - quitacao
        
        lucro_trib_emp = receita_total - desp_op
        impostos_emp = lucro_trib_emp * (aliquota_irpj + aliquota_csll) if lucro_trib_emp > 0 else 0
        fluxo_emp_liquido = fluxo_emp - impostos_emp
        
        fluxo_caixa.append({
            'Ano': ano, 'Receita (Aluguel + Venda)': receita_total, 'Despesa Operacional': desp_op,
            'Fluxo Empreendimento (S/ Finan.)': fluxo_emp_liquido, 'Juros SAC': juros_ano,
            'Amortização SAC': amort_ano, 'Impostos (IRPJ + CSLL)': impostos, 'Fluxo Acionista (C/ Finan.)': fluxo_acionista
        })

    df_fc = pd.DataFrame(fluxo_caixa)
    fc_acionista = df_fc['Fluxo Acionista (C/ Finan.)'].values

    # 5. INDICADORES ECONÔMICOS
    tma_decimal = tma_base / 100
    vpl = npf.npv(tma_decimal, fc_acionista)
    tir = npf.irr(fc_acionista) * 100 if not np.isnan(npf.irr(fc_acionista)) else 0
    fc_acumulado = np.cumsum(fc_acionista)
    payback = next((i for i, v in enumerate(fc_acumulado) if v >= 0), "Não se paga")

    # 6. INTERFACE DO DASHBOARD
    st.markdown(f"<h1 style='color: #C5A059;'>🏢 Análise de Viabilidade - {imovel_selecionado}</h1>", unsafe_allow_html=True)

    
  # --- MENSAGEM DOS SÓCIOS (ÁUDIOS) ---
    st.markdown("---")
    st.subheader("✉️ Personalized Messages from our Team")
    
    col_nathan, col_luiza = st.columns(2)
    
    with col_nathan:
        with st.expander("👤 Message from Nathan"):
            st.markdown("""
            **Hello, Mr. Thiago Moreno.** I have prepared a brief message detailing the strategy for your selected assets. 
            """)
            try:
                st.audio("explicacao.mp3", format="audio/mp3")
            except:
                st.warning("⚠️ Nathan's message unavailable.")

    with col_luiza:
        with st.expander("👤 Mensagem de Luiza"):
            st.markdown("""
            **Para Thiago,** Oi, aqui é a Luiza da LUTHAN acessoria, este audio explica melhor os resultados obtidos.
            """)
            try:
                # Certifique-se de gravar e salvar o áudio da Luiza como 'mensagem_luiza.mp3'
                st.audio("mensagem_luiza.mp3", format="audio/mp3")
            except:
                st.warning("⚠️ Luiza's message unavailable.")
    st.markdown("---")
    # --------------------------------------------------------
    # --------------------------------------------------------
    # ----------------------------------------
    # --- NOVA SEÇÃO: GALERIA DE FOTOS ---
    col_foto1, col_foto2 = st.columns(2)
    with col_foto1:
        try:
            st.image(dados['foto1'], use_container_width=True)
        except:
            st.info("🖼️ Espaço reservado para a Foto 1 (Insira o caminho no código)")
            
    with col_foto2:
        try:
            st.image(dados['foto2'], use_container_width=True)
        except:
            st.info("🖼️ Espaço reservado para a Foto 2 (Insira o caminho no código)")
    
    st.markdown("---")
    # ------------------------------------

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Investimento Total", f"R$ {invest_total:,.2f}")
    col2.metric("Valor Financiado (70%)", f"R$ {financiado:,.2f}")
    col3.metric("Entrada (30%)", f"R$ {entrada:,.2f}")
    col4.metric("Aluguel Inicial (Mês)", f"R$ {aluguel_anual_base/12:,.2f}")

    st.markdown("### 📊 Indicadores Financeiros (Ótica do Acionista)")
    ic1, ic2, ic3 = st.columns(3)
    ic1.metric("Valor Presente Líquido (VPL)", f"R$ {vpl:,.2f}")
    ic2.metric("Taxa Interna de Retorno (TIR)", f"{tir:.2f}%")
    ic3.metric("Payback", f"{payback} Anos" if isinstance(payback, int) else payback)

    if vpl > 0:
        st.success(f"✅ **Análise Luthan:** O projeto é ECONOMICAMENTE VIÁVEL para a sua TMA exigida de {tma_base}%.")
    else:
        st.error(f"❌ **Análise Luthan:** O projeto NÃO É VIÁVEL financeiramente para a TMA exigida de {tma_base}%.")

    st.markdown("---")
    st.markdown(f"### 🏦 Tabela de Financiamento (SAC - 10 Anos a 16% a.a.)")
    st.dataframe(df_sac.style.format("R$ {:,.2f}"))

    st.markdown("---")
    st.markdown(f"### 📈 Fluxo de Caixa (Horizonte: {horizonte} Anos | Inflação: 4,5% a.a.)")
    st.dataframe(df_fc.style.format("R$ {:,.2f}"))

    # 7. GRÁFICO VPL x TMA COM TEMA ESCURO
    st.markdown("---")
    st.markdown("### 📉 Sensibilidade do VPL em relação à TMA")
    tmas = np.arange(0.01, 0.25, 0.01)
    vpls = [npf.npv(t, fc_acionista) for t in tmas]

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#121212')
    ax.plot(tmas * 100, vpls, color='#C5A059', linewidth=2)
    ax.axhline(0, color='#FAFAFA', linestyle='--')
    ax.axvline(tma_base, color='#4CAF50', linestyle=':', label='TMA Base Selecionada')
    
    ax.set_xlabel('TMA (% a.a.)', color='#FAFAFA')
    ax.set_ylabel('VPL (R$)', color='#FAFAFA')
    ax.tick_params(colors='#FAFAFA')
    ax.grid(True, color='#333333', alpha=0.5)
    
    legend = ax.legend(facecolor='#1E1E1E', edgecolor='#333333')
    for text in legend.get_texts():
        text.set_color('#FAFAFA')
        
    st.pyplot(fig)