import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Luthan Investimentos", page_icon="🏢", layout="wide")

# ==========================================
# FUNÇÕES FINANCEIRAS (substituem numpy_financial)
# ==========================================
def vpl(taxa, fluxos):
    """Valor Presente Líquido. fluxos[0] é o ano 0 (não descontado)."""
    return sum(fc / (1 + taxa) ** i for i, fc in enumerate(fluxos))


def tir(fluxos, estimativa=0.10):
    """Taxa Interna de Retorno via Newton-Raphson."""
    taxa = estimativa
    for _ in range(1000):
        f = sum(fc / (1 + taxa) ** i for i, fc in enumerate(fluxos))
        df = sum(-i * fc / (1 + taxa) ** (i + 1) for i, fc in enumerate(fluxos))
        if abs(df) < 1e-12:
            break
        nova_taxa = taxa - f / df
        if abs(nova_taxa - taxa) < 1e-10:
            taxa = nova_taxa
            break
        taxa = nova_taxa
    return taxa


def payback_descontado(fluxos, taxa):
    """Retorna o ano em que o fluxo acumulado descontado vira positivo,
    com interpolação fracionária. Retorna None se nunca recuperar."""
    acumulado = 0
    for i, fc in enumerate(fluxos):
        vp = fc / (1 + taxa) ** i
        acumulado_anterior = acumulado
        acumulado += vp
        if acumulado >= 0 and i > 0 and acumulado_anterior < 0:
            fracao = -acumulado_anterior / vp if vp != 0 else 0
            return (i - 1) + fracao
    return None


def simular_fluxos(dados, horizonte, aluguel_mensal, taxa_valorizacao, ipca=0.045,
                    taxa_adm=0.10, manutencao_pct=0.05, taxa_juros=0.16, prazo_financ=10,
                    entrada_pct=0.30, irpj=0.15, csll=0.09):
    """Constrói, ano a ano, o Fluxo de Caixa do Empreendimento (sem financiamento)
    e o Fluxo de Caixa do Acionista (com financiamento SAC), replicando a lógica
    validada nas planilhas originais. Retorna um dicionário com as duas séries de
    fluxo, a tabela SAC e o detalhamento linha a linha de cada um."""
    invest_total = dados['investimento']
    entrada = invest_total * entrada_pct
    financiado = invest_total * (1 - entrada_pct)
    anos_carencia = dados['anos_carencia']
    aluguel_anual_base = aluguel_mensal * 12

    # --- Tabela SAC ---
    amortizacao = financiado / prazo_financ
    tabela_sac = []
    saldo_devedor = financiado
    for ano in range(1, prazo_financ + 1):
        juros = saldo_devedor * taxa_juros
        prestacao = amortizacao + juros
        saldo_anterior = saldo_devedor
        saldo_devedor -= amortizacao
        tabela_sac.append({
            'Ano': ano, 'Saldo Inicial': saldo_anterior, 'Amortização': amortizacao,
            'Juros': juros, 'Prestação': prestacao, 'Saldo Final': max(saldo_devedor, 0)
        })
    df_sac = pd.DataFrame(tabela_sac)

    # --- Fluxos ano a ano ---
    linhas_empreendimento = [{
        'Ano': 0, 'Receita Aluguel': 0.0, 'Despesa Operacional': 0.0, 'Lucro Antes do Imposto': 0.0,
        'Impostos (IRPJ+CSLL)': 0.0, 'Valor da Venda': 0.0, 'Fluxo Empreendimento': -invest_total
    }]
    linhas_acionista = [{
        'Ano': 0, 'Receita Aluguel': 0.0, 'Despesa Operacional': 0.0, 'Lucro Antes do Imposto': 0.0,
        'Impostos (IRPJ+CSLL)': 0.0, 'Fluxo Operacional': 0.0, 'Valor da Venda': 0.0,
        'Prestação Financiamento': 0.0, 'Quitação Saldo Devedor': 0.0, 'Fluxo Acionista': -entrada
    }]
    fluxo_empreendimento = [-invest_total]
    fluxo_acionista = [-entrada]

    for ano in range(1, horizonte + 1):
        ano_operacao = ano - anos_carencia
        if ano_operacao <= 0:
            receita = 0.0
        elif ano_operacao == 1:
            if anos_carencia > 0:
                receita = aluguel_anual_base * (1 + ipca)
            else:
                receita = aluguel_anual_base / 2
        else:
            expoente = (ano_operacao - 1) + (1 if anos_carencia > 0 else 0)
            receita = aluguel_anual_base * (1 + ipca) ** expoente

        despesa = 0.0 if receita == 0 else (
            dados['seguro_anual'] + dados['iptu_anual'] + receita * (taxa_adm + manutencao_pct)
        )
        lucro_trib = receita - despesa
        impostos = lucro_trib * (irpj + csll) if lucro_trib > 0 else 0.0
        fluxo_op_sem_financ = receita - despesa - impostos

        venda = (invest_total * dados.get('fator_valorizacao_entrega', 1.0)
                 * (1 + taxa_valorizacao) ** horizonte) if ano == horizonte else 0.0

        # --- Fluxo do Empreendimento (sem financiamento) ---
        fe = fluxo_op_sem_financ + venda
        fluxo_empreendimento.append(fe)
        linhas_empreendimento.append({
            'Ano': ano, 'Receita Aluguel': receita, 'Despesa Operacional': despesa,
            'Lucro Antes do Imposto': lucro_trib, 'Impostos (IRPJ+CSLL)': impostos,
            'Valor da Venda': venda, 'Fluxo Empreendimento': fe
        })

        # --- Fluxo do Acionista (com financiamento) ---
        juros_ano = df_sac.loc[df_sac['Ano'] == ano, 'Juros'].values[0] if ano <= prazo_financ else 0.0
        amort_ano = df_sac.loc[df_sac['Ano'] == ano, 'Amortização'].values[0] if ano <= prazo_financ else 0.0
        prestacao_ano = juros_ano + amort_ano
        quitacao = df_sac.loc[df_sac['Ano'] == ano, 'Saldo Final'].values[0] if (ano == horizonte and horizonte < prazo_financ) else 0.0

        fa = fluxo_op_sem_financ + venda - prestacao_ano - quitacao
        fluxo_acionista.append(fa)
        linhas_acionista.append({
            'Ano': ano, 'Receita Aluguel': receita, 'Despesa Operacional': despesa,
            'Lucro Antes do Imposto': lucro_trib, 'Impostos (IRPJ+CSLL)': impostos,
            'Fluxo Operacional': fluxo_op_sem_financ, 'Valor da Venda': venda,
            'Prestação Financiamento': prestacao_ano, 'Quitação Saldo Devedor': quitacao,
            'Fluxo Acionista': fa
        })

    return {
        'df_sac': df_sac,
        'df_empreendimento': pd.DataFrame(linhas_empreendimento),
        'df_acionista': pd.DataFrame(linhas_acionista),
        'fluxo_empreendimento': fluxo_empreendimento,
        'fluxo_acionista': fluxo_acionista,
        'entrada': entrada,
        'financiado': financiado,
    }


# ==========================================
# 0. SISTEMA DE LOGIN (PÁGINA INICIAL)
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    col_imagem, col_login = st.columns([1.2, 1], gap="large")

    with col_imagem:
        caminho_da_imagem = "capa.png"
        try:
            st.image(caminho_da_imagem, use_container_width=True)
        except Exception:
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
    # ------------------------------------------------------------
    # 1. DADOS DE ENTRADA — valores confirmados nas 4 planilhas
    #    (DADOS DE ENTRADA / FINANCIAMENTO SAC / FLUXO ACIONISTA / RESULTADOS)
    # ------------------------------------------------------------
    imoveis = {
        'Casa na Armação': {
            'investimento': 1052000.0,
            'valor_terreno': 350000.0,
            'valor_construcao': 702000.0,
            'aluguel_mensal': 6500.0,
            'seguro_anual': 2000.0,
            'iptu_anual': 3500.0,
            'condominio_mensal': 0.0,
            'anos_carencia': 0,
            'foto1': "CASA_1_.png",
            'foto2': "casa_2_.png",
            'fonte': "Terreno na Armação (anúncio OLX) + construção padrão médio, CUB/SC mai-2025, R$4.500/m², 156 m²",
        },
        'Apto na Planta (Jurerê)': {
            'investimento': 1064646.0,
            'valor_terreno': 1064646.0,
            'valor_construcao': 0.0,
            'aluguel_mensal': 8500.0,
            'seguro_anual': 2000.0,
            'iptu_anual': 3500.0,
            'condominio_mensal': 1200.0,
            'anos_carencia': 2,          # na planta: 2 anos de obra sem renda de aluguel
            'fator_valorizacao_entrega': 1.30,  # apto pronto vale 30% mais do que na planta
            'foto1': "jurere1.png",
            'foto2': "jurere2.png",
            'fonte': "Apartamento na planta, anúncio OLX, 77,33 m², 2 anos de execução",
        },
        'Sala Comercial (Centro)': {
            'investimento': 950000.0,
            'valor_terreno': 950000.0,
            'valor_construcao': 0.0,
            'aluguel_mensal': 7800.0,
            'seguro_anual': 1500.0,
            'iptu_anual': 1500.0,
            'condominio_mensal': 1200.0,
            'anos_carencia': 0,
            'foto1': "sala1.png",
            'foto2': "sala2.png",
            'fonte': "Sala comercial, anúncio OLX, 212,65 m²",
        },
        'Apto (Trindade)': {
            'investimento': 950000.0,
            'valor_terreno': 950000.0,
            'valor_construcao': 0.0,
            'aluguel_mensal': 6500.0,
            'seguro_anual': 2000.0,
            'iptu_anual': 1799.0,
            'condominio_mensal': 1200.0,
            'anos_carencia': 0,
            'foto1': "trindade1.png",
            'foto2': "trindade2.png",
            'fonte': "Apartamento na Trindade, anúncio OLX, 88,63 m²",
        }
    }

    # Premissas fixas confirmadas nas 4 planilhas (DADOS DE ENTRADA)
    IPCA = 0.045                # reajuste anual do aluguel
    TAXA_ADM_LOCACAO = 0.10     # 10% sobre o aluguel recebido
    MANUTENCAO_PCT = 0.05       # 5% sobre o aluguel recebido
    TAXA_JUROS_FINANC = 0.16    # a.a. SAC
    PRAZO_FINANCIAMENTO = 10    # anos
    ENTRADA_PCT = 0.30
    IRPJ = 0.15
    CSLL = 0.09
    TMA_PADRAO = 0.1475         # SELIC vigente usada como TMA nas planilhas

    # Cenários de valorização na revenda (mercado)
    CENARIOS_VALORIZACAO = {
        'Conservador (4,5% a.a.)': 0.045,
        'Base (6,5% a.a.)': 0.065,
        'Otimista (8,5% a.a.)': 0.085,
    }

    # ------------------------------------------------------------
    # 2. MENU LATERAL E PREMISSAS
    # ------------------------------------------------------------
    st.sidebar.markdown("### 👤 Área do Cliente")

    try:
        st.sidebar.image("professor.png", width=120, caption="Thiago Moreno")
    except Exception:
        st.sidebar.info("📷 Espaço para Foto do Cliente")

    st.sidebar.success("Bem-vindo, **Thiago Moreno**!")

    if st.sidebar.button("Sair do Sistema"):
        st.session_state['autenticado'] = False
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🏢 Luthan Investimentos")
    imovel_selecionado = st.sidebar.selectbox("Selecione o Imóvel:", list(imoveis.keys()))

    st.sidebar.subheader("Horizonte de Análise")
    horizonte_str = st.sidebar.radio("Tempo até a venda (Anos):", ["5", "10"], horizontal=True)
    horizonte = int(horizonte_str)

    st.sidebar.subheader("Cenário de Valorização na Venda")
    cenario_label = st.sidebar.selectbox("Cenário de mercado:", list(CENARIOS_VALORIZACAO.keys()), index=1)
    taxa_valorizacao = CENARIOS_VALORIZACAO[cenario_label]

    st.sidebar.subheader("Análise de Sensibilidade")
    var_aluguel = st.sidebar.slider("Variação do Aluguel (%)", -15.0, 15.0, 0.0, 1.0)
    tma_base = st.sidebar.slider("TMA — Taxa Mínima de Atratividade (% a.a.)", 4.0, 20.0, TMA_PADRAO * 100, 0.25)
    var_valorizacao = st.sidebar.slider("Ajuste fino na valorização de revenda (p.p.)", -5.0, 5.0, 0.0, 0.5)

    with st.sidebar.expander("ℹ️ Premissas fixas do modelo"):
        st.markdown(f"""
        - **IPCA (reajuste do aluguel):** {IPCA*100:.1f}% a.a.
        - **Taxa de administração da locação:** {TAXA_ADM_LOCACAO*100:.0f}% sobre o aluguel recebido
        - **Manutenção:** {MANUTENCAO_PCT*100:.0f}% sobre o aluguel recebido
        - **Financiamento:** SAC, {PRAZO_FINANCIAMENTO} anos, {TAXA_JUROS_FINANC*100:.0f}% a.a.
        - **Entrada:** {ENTRADA_PCT*100:.0f}% do valor do imóvel
        - **IRPJ + CSLL:** {IRPJ*100:.0f}% + {CSLL*100:.0f}% sobre o lucro operacional do aluguel
        - *(a venda do imóvel não é tributada neste modelo)*
        """)

    dados = imoveis[imovel_selecionado]
    invest_total = dados['investimento']
    entrada = invest_total * ENTRADA_PCT
    financiado = invest_total * (1 - ENTRADA_PCT)
    aluguel_mensal_ajustado = dados['aluguel_mensal'] * (1 + var_aluguel / 100)
    aluguel_anual_base = aluguel_mensal_ajustado * 12
    tma_decimal = tma_base / 100
    taxa_valorizacao_ajustada = taxa_valorizacao + (var_valorizacao / 100)
    anos_carencia = dados['anos_carencia']

    # ------------------------------------------------------------
    # 3 e 4. SAC + FLUXO DE CAIXA (Empreendimento e Acionista)
    #    Lógica validada e fiel às planilhas originais:
    #    - Carência de aluguel (Jurerê: 2 anos em obra; demais: 0). O IPCA continua
    #      correndo durante a obra: o aluguel de mercado já chega reajustado pelos
    #      anos de espera quando o imóvel fica pronto.
    #    - Imóvel pronto (sem carência): 1º ano recebe só 6 meses de aluguel, sem
    #      correção ainda (o relógio do IPCA começa a contar daquele ano).
    #    - Imóvel na planta (com carência): 1º ano de operação já entra com o aluguel
    #      cheio, reajustado pelo tempo de construção.
    #    - A partir do 2º ano de operação: aluguel cheio, corrigido pelo IPCA acumulado.
    #    - Despesa operacional = Seguro + IPTU + Aluguel recebido x (Taxa Adm + Manutenção)
    #    - IRPJ/CSLL incidem só sobre o lucro do aluguel (a venda não é tributada)
    #    - Fluxo do Empreendimento: NÃO tem financiamento (sai o investimento total na hora 0)
    #    - Fluxo do Acionista: COM financiamento (sai a entrada; prestações e quitação
    #      do saldo devedor, se a venda ocorrer antes do fim do financiamento)
    # ------------------------------------------------------------
    resultado_sim = simular_fluxos(
        dados, horizonte, aluguel_mensal_ajustado, taxa_valorizacao_ajustada,
        ipca=IPCA, taxa_adm=TAXA_ADM_LOCACAO, manutencao_pct=MANUTENCAO_PCT,
        taxa_juros=TAXA_JUROS_FINANC, prazo_financ=PRAZO_FINANCIAMENTO,
        entrada_pct=ENTRADA_PCT, irpj=IRPJ, csll=CSLL
    )
    df_sac = resultado_sim['df_sac']
    df_fe = resultado_sim['df_empreendimento']
    df_fc = resultado_sim['df_acionista']
    fluxo_empreendimento = resultado_sim['fluxo_empreendimento']
    fluxo_acionista = resultado_sim['fluxo_acionista']

    # ------------------------------------------------------------
    # 5. INDICADORES ECONÔMICOS
    # ------------------------------------------------------------
    vpl_valor = vpl(tma_decimal, fluxo_acionista)
    tir_valor = tir(fluxo_acionista) * 100
    payback = payback_descontado(fluxo_acionista, tma_decimal)

    vpl_empreendimento = vpl(tma_decimal, fluxo_empreendimento)
    tir_empreendimento = tir(fluxo_empreendimento) * 100
    payback_empreendimento = payback_descontado(fluxo_empreendimento, tma_decimal)

    # ------------------------------------------------------------
    # 6. INTERFACE DO DASHBOARD
    # ------------------------------------------------------------
    st.markdown(f"<h1 style='color: #C5A059;'>🏢 Análise de Viabilidade - {imovel_selecionado}</h1>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("✉️ Personalized Messages from our Team")
    col_nathan, col_luiza = st.columns(2)
    with col_nathan:
        with st.expander("👤 Message from Nathan"):
            st.markdown("**Hello, Mr. Thiago Moreno.** I have prepared a brief message detailing the strategy for your selected assets.")
            try:
                st.audio("explicacao.mp3", format="audio/mp3")
            except Exception:
                st.warning("⚠️ Nathan's message unavailable.")
    with col_luiza:
        with st.expander("👤 Mensagem de Luiza"):
            st.markdown("**Para Thiago,** Oi, aqui é a Luiza da LUTHAN acessoria, este audio explica melhor os resultados obtidos.")
            try:
                st.audio("mensagem_luiza.mp3", format="audio/mp3")
            except Exception:
                st.warning("⚠️ Luiza's message unavailable.")
    st.markdown("---")

    col_foto1, col_foto2 = st.columns(2)
    with col_foto1:
        try:
            st.image(dados['foto1'], use_container_width=True)
        except Exception:
            st.info("🖼️ Espaço reservado para a Foto 1")
    with col_foto2:
        try:
            st.image(dados['foto2'], use_container_width=True)
        except Exception:
            st.info("🖼️ Espaço reservado para a Foto 2")
    st.caption(f"📍 Fonte: {dados['fonte']}")
    st.markdown("---")

    if anos_carencia > 0:
        st.info(f"🏗️ **Imóvel na planta:** {anos_carencia} anos de execução. A receita de aluguel só começa a partir do ano {anos_carencia + 1}.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Investimento Total", f"R$ {invest_total:,.2f}")
    col2.metric("Valor Financiado (70%)", f"R$ {financiado:,.2f}")
    col3.metric("Entrada (30%)", f"R$ {entrada:,.2f}")
    col4.metric("Aluguel Mensal (base)", f"R$ {aluguel_mensal_ajustado:,.2f}")

    st.markdown("### 📊 Indicadores Financeiros (Ótica do Acionista)")
    col_gauge, col_metrics = st.columns([1, 1.4], gap="large")

    with col_gauge:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=tir_valor,
            number={'suffix': "%", 'font': {'color': '#FAFAFA', 'size': 36}},
            delta={'reference': tma_base, 'increasing': {'color': '#4CAF50'}, 'decreasing': {'color': '#E57373'}},
            title={'text': "TIR vs TMA exigida", 'font': {'color': '#FAFAFA', 'size': 16}},
            gauge={
                'axis': {'range': [0, max(20, tir_valor + 5)], 'tickcolor': '#FAFAFA'},
                'bar': {'color': '#C5A059'},
                'bgcolor': '#121212',
                'borderwidth': 1,
                'bordercolor': '#333333',
                'threshold': {'line': {'color': '#4CAF50', 'width': 4}, 'thickness': 0.85, 'value': tma_base},
            }
        ))
        fig_gauge.update_layout(
            paper_bgcolor='#1E1E1E', font={'color': '#FAFAFA'}, height=260,
            margin=dict(l=20, r=20, t=50, b=10)
        )
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.caption("A linha verde marca a TMA exigida. Se a barra dourada passar da linha, o retorno supera o mínimo exigido.")

    with col_metrics:
        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("VPL", f"R$ {vpl_valor:,.0f}")
        ic2.metric("TIR", f"{tir_valor:.2f}%")
        ic3.metric("Payback Desc.", f"{payback:.1f} anos" if payback is not None else "Não recupera")

        if vpl_valor > 0:
            st.success(f"✅ **Análise Luthan:** Projeto ECONOMICAMENTE VIÁVEL para a TMA de {tma_base:.2f}%.")
        else:
            st.error(f"❌ **Análise Luthan:** Projeto NÃO VIÁVEL para a TMA de {tma_base:.2f}% (TIR de {tir_valor:.2f}% fica abaixo do exigido).")

        diferenca_pp = tir_valor - tma_base
        st.caption(
            f"A TIR deste projeto está **{abs(diferenca_pp):.2f} p.p. "
            f"{'acima' if diferenca_pp >= 0 else 'abaixo'}** da TMA exigida."
        )

    # ------------------------------------------------------------
    # 7. ABAS COM DETALHAMENTO
    # ------------------------------------------------------------
    st.markdown("---")
    tab_fluxo, tab_sac, tab_sensibilidade, tab_comparativo, tab_resumo = st.tabs(
        ["📈 Fluxo de Caixa", "🏦 Financiamento (SAC)", "📉 Sensibilidade VPL x TMA",
         "⚖️ Comparar os 4 imóveis", "🧾 Resumo Executivo"]
    )

    with tab_fluxo:
        st.markdown(f"#### Fluxo de Caixa do Empreendimento x Acionista — Horizonte: {horizonte} anos | IPCA: {IPCA*100:.1f}% a.a.")
        st.caption(
            "O **Fluxo do Empreendimento** considera o imóvel como se fosse pago 100% à vista (sem financiamento). "
            "O **Fluxo do Acionista** considera a entrada de 30% e o financiamento SAC do saldo. "
            "A diferença entre os dois evidencia o efeito (alavancagem) do financiamento sobre a rentabilidade."
        )

        ic_fe1, ic_fe2, ic_fe3, ic_fa1, ic_fa2, ic_fa3 = st.columns(6)
        ic_fe1.metric("VPL Empreend.", f"R$ {vpl_empreendimento:,.0f}")
        ic_fe2.metric("TIR Empreend.", f"{tir_empreendimento:.2f}%")
        ic_fe3.metric("Payback Empreend.", f"{payback_empreendimento:.1f}a" if payback_empreendimento is not None else "—")
        ic_fa1.metric("VPL Acionista", f"R$ {vpl_valor:,.0f}")
        ic_fa2.metric("TIR Acionista", f"{tir_valor:.2f}%")
        ic_fa3.metric("Payback Acionista", f"{payback:.1f}a" if payback is not None else "—")

        efeito_alavancagem = tir_valor - tir_empreendimento
        if efeito_alavancagem > 0:
            st.success(f"📈 O financiamento **eleva** a TIR em {efeito_alavancagem:.2f} p.p. (alavancagem positiva: o custo da dívida é menor que o retorno do projeto).")
        else:
            st.warning(f"📉 O financiamento **reduz** a TIR em {abs(efeito_alavancagem):.2f} p.p. (alavancagem negativa: o custo da dívida supera o retorno do projeto).")

        fig_fc_comp = go.Figure()
        fig_fc_comp.add_trace(go.Bar(
            x=df_fe['Ano'], y=df_fe['Fluxo Empreendimento'], name='Fluxo Empreendimento (sem financ.)',
            marker_color='#8a8a8a', hovertemplate='Ano %{x}<br>R$ %{y:,.2f}<extra></extra>'
        ))
        fig_fc_comp.add_trace(go.Bar(
            x=df_fc['Ano'], y=df_fc['Fluxo Acionista'], name='Fluxo Acionista (com financ.)',
            marker_color='#C5A059', hovertemplate='Ano %{x}<br>R$ %{y:,.2f}<extra></extra>'
        ))
        fig_fc_comp.add_hline(y=0, line_dash="dash", line_color="#FAFAFA")
        fig_fc_comp.update_layout(
            barmode='group', paper_bgcolor='#1E1E1E', plot_bgcolor='#121212', font={'color': '#FAFAFA'},
            xaxis_title='Ano', yaxis_title='Fluxo de Caixa (R$)', height=400,
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            margin=dict(l=10, r=10, t=40, b=10)
        )
        fig_fc_comp.update_xaxes(gridcolor='#333333')
        fig_fc_comp.update_yaxes(gridcolor='#333333')
        st.plotly_chart(fig_fc_comp, use_container_width=True)

        col_chart, col_pie = st.columns([2, 1], gap="medium")
        with col_chart:
            cores_fc = ['#E57373' if v < 0 else '#4CAF50' for v in df_fc['Fluxo Acionista']]
            fig_fc = go.Figure(go.Bar(
                x=df_fc['Ano'], y=df_fc['Fluxo Acionista'], marker_color=cores_fc,
                hovertemplate='Ano %{x}<br>R$ %{y:,.2f}<extra></extra>'
            ))
            fig_fc.add_hline(y=0, line_dash="dash", line_color="#FAFAFA")
            fig_fc.update_layout(
                paper_bgcolor='#1E1E1E', plot_bgcolor='#121212', font={'color': '#FAFAFA'},
                xaxis_title='Ano', yaxis_title='Fluxo Acionista (R$)', height=380,
                margin=dict(l=10, r=10, t=30, b=10)
            )
            fig_fc.update_xaxes(gridcolor='#333333')
            fig_fc.update_yaxes(gridcolor='#333333')
            st.markdown("##### Fluxo Acionista — detalhado")
            st.plotly_chart(fig_fc, use_container_width=True)

        with col_pie:
            anos_com_receita = df_fc[df_fc['Receita Aluguel'] > 0]
            if len(anos_com_receita) > 0:
                desp_total = anos_com_receita['Despesa Operacional'].sum()
                imp_total = anos_com_receita['Impostos (IRPJ+CSLL)'].sum()
                liquido_total = anos_com_receita['Fluxo Operacional'].sum()
                fig_pie = go.Figure(go.Pie(
                    labels=['Fluxo Operacional Líquido', 'Despesas Operacionais', 'Impostos (IRPJ+CSLL)'],
                    values=[max(liquido_total, 0), desp_total, imp_total],
                    marker_colors=['#4CAF50', '#E57373', '#C5A059'],
                    hole=0.45,
                    hovertemplate='%{label}<br>R$ %{value:,.2f}<extra></extra>'
                ))
                fig_pie.update_layout(
                    paper_bgcolor='#1E1E1E', font={'color': '#FAFAFA'}, height=380,
                    margin=dict(l=10, r=10, t=30, b=10), showlegend=True,
                    legend=dict(orientation='h', yanchor='bottom', y=-0.3)
                )
                st.markdown("##### Para onde foi a receita de aluguel")
                st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("##### Tabela — Fluxo de Caixa do Empreendimento (sem financiamento)")
        st.dataframe(
            df_fe.style.format({c: "R$ {:,.2f}" for c in df_fe.columns if c != 'Ano'}),
            use_container_width=True
        )

        st.markdown("##### Tabela — Fluxo de Caixa do Acionista (com financiamento)")
        st.dataframe(
            df_fc.style.format({c: "R$ {:,.2f}" for c in df_fc.columns if c != 'Ano'}),
            use_container_width=True
        )

    with tab_sac:
        st.markdown(f"#### Tabela de Financiamento (SAC - {PRAZO_FINANCIAMENTO} Anos a {TAXA_JUROS_FINANC*100:.0f}% a.a.)")

        fig_sac = go.Figure()
        fig_sac.add_trace(go.Bar(x=df_sac['Ano'], y=df_sac['Amortização'], name='Amortização', marker_color='#4CAF50',
                                  hovertemplate='Ano %{x}<br>Amortização: R$ %{y:,.2f}<extra></extra>'))
        fig_sac.add_trace(go.Bar(x=df_sac['Ano'], y=df_sac['Juros'], name='Juros', marker_color='#E57373',
                                  hovertemplate='Ano %{x}<br>Juros: R$ %{y:,.2f}<extra></extra>'))
        fig_sac.add_trace(go.Scatter(x=df_sac['Ano'], y=df_sac['Saldo Final'], name='Saldo Devedor',
                                      mode='lines+markers', line=dict(color='#C5A059', width=3), yaxis='y2',
                                      hovertemplate='Ano %{x}<br>Saldo: R$ %{y:,.2f}<extra></extra>'))
        fig_sac.update_layout(
            barmode='stack', paper_bgcolor='#1E1E1E', plot_bgcolor='#121212', font={'color': '#FAFAFA'},
            xaxis_title='Ano', yaxis_title='Prestação (R$)',
            yaxis2=dict(title='Saldo Devedor (R$)', overlaying='y', side='right'),
            height=400, legend=dict(orientation='h', yanchor='bottom', y=1.02),
            margin=dict(l=10, r=10, t=40, b=10)
        )
        fig_sac.update_xaxes(gridcolor='#333333')
        fig_sac.update_yaxes(gridcolor='#333333')
        st.plotly_chart(fig_sac, use_container_width=True)

        st.dataframe(
            df_sac.style.format({c: "R$ {:,.2f}" for c in df_sac.columns if c != 'Ano'}),
            use_container_width=True
        )
        st.caption(f"Total de juros pagos: R$ {df_sac['Juros'].sum():,.2f}  |  Total pago ao banco: R$ {df_sac['Prestação'].sum():,.2f}")


    with tab_sensibilidade:
        st.markdown("#### Sensibilidade do VPL em relação à TMA")
        tmas = np.arange(0.01, 0.25, 0.005)
        vpls = [vpl(t, fluxo_acionista) for t in tmas]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=tmas * 100, y=vpls, mode='lines', line=dict(color='#C5A059', width=3),
            fill='tozeroy', fillcolor='rgba(197,160,89,0.15)',
            hovertemplate='TMA %{x:.2f}%<br>VPL R$ %{y:,.2f}<extra></extra>'
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="#FAFAFA")
        fig.add_vline(x=tma_base, line_dash="dot", line_color="#4CAF50",
                       annotation_text="TMA selecionada", annotation_font_color="#4CAF50")
        fig.add_vline(x=tir_valor, line_dash="dot", line_color="#E57373",
                       annotation_text="TIR do projeto", annotation_font_color="#E57373")
        fig.update_layout(
            paper_bgcolor='#1E1E1E', plot_bgcolor='#121212', font={'color': '#FAFAFA'},
            xaxis_title='TMA (% a.a.)', yaxis_title='VPL (R$)', height=420,
            margin=dict(l=10, r=10, t=30, b=10)
        )
        fig.update_xaxes(gridcolor='#333333')
        fig.update_yaxes(gridcolor='#333333')
        st.plotly_chart(fig, use_container_width=True)
        st.caption("A linha verde marca a TMA escolhida no menu lateral; a linha vermelha marca a TIR do projeto neste cenário. Onde a curva cruza zero é a TMA máxima que o projeto consegue pagar.")

        st.markdown("---")
        st.markdown("#### 🎯 Análise de Sensibilidade Univariada")
        st.caption(
            "Cada variável é alterada isoladamente (Pessimista / Base / Otimista), mantendo as demais "
            "fixas no valor de referência (cenário Base), conforme a Tabela 1 do enunciado."
        )

        def fluxo_acionista_param(aluguel_mensal_p, tma_p, valorizacao_p):
            """Recalcula o fluxo do acionista variando só os 3 parâmetros de sensibilidade,
            mantendo todas as demais premissas do imóvel selecionado fixas."""
            resultado = simular_fluxos(
                dados, horizonte, aluguel_mensal_p, valorizacao_p,
                ipca=IPCA, taxa_adm=TAXA_ADM_LOCACAO, manutencao_pct=MANUTENCAO_PCT,
                taxa_juros=TAXA_JUROS_FINANC, prazo_financ=PRAZO_FINANCIAMENTO,
                entrada_pct=ENTRADA_PCT, irpj=IRPJ, csll=CSLL
            )
            fc = resultado['fluxo_acionista']
            v = vpl(tma_p, fc)
            t = tir(fc) * 100
            pb = payback_descontado(fc, tma_p)
            return v, t, pb

        aluguel_ref = dados['aluguel_mensal']
        tma_ref = tma_decimal
        valoriz_ref = taxa_valorizacao

        cenarios_sensibilidade = {
            'Receita de Aluguel': [
                ('Pessimista (-15%)', dict(aluguel_mensal_p=aluguel_ref * 0.85, tma_p=tma_ref, valorizacao_p=valoriz_ref)),
                ('Base (referência)', dict(aluguel_mensal_p=aluguel_ref, tma_p=tma_ref, valorizacao_p=valoriz_ref)),
                ('Otimista (+15%)', dict(aluguel_mensal_p=aluguel_ref * 1.15, tma_p=tma_ref, valorizacao_p=valoriz_ref)),
            ],
            'TMA': [
                ('Pessimista (+2 p.p.)', dict(aluguel_mensal_p=aluguel_ref, tma_p=tma_ref + 0.02, valorizacao_p=valoriz_ref)),
                ('Base (referência)', dict(aluguel_mensal_p=aluguel_ref, tma_p=tma_ref, valorizacao_p=valoriz_ref)),
                ('Otimista (-2 p.p.)', dict(aluguel_mensal_p=aluguel_ref, tma_p=max(tma_ref - 0.02, 0.001), valorizacao_p=valoriz_ref)),
            ],
            'Valorização do Imóvel': [
                ('Pessimista (-10 p.p.)', dict(aluguel_mensal_p=aluguel_ref, tma_p=tma_ref, valorizacao_p=valoriz_ref - 0.10)),
                ('Base (referência)', dict(aluguel_mensal_p=aluguel_ref, tma_p=tma_ref, valorizacao_p=valoriz_ref)),
                ('Otimista (+10 p.p.)', dict(aluguel_mensal_p=aluguel_ref, tma_p=tma_ref, valorizacao_p=valoriz_ref + 0.10)),
            ],
        }

        for nome_var, cenarios in cenarios_sensibilidade.items():
            st.markdown(f"##### {nome_var}")
            linhas_sens = []
            for label_cen, params in cenarios:
                v, t, pb = fluxo_acionista_param(**params)
                linhas_sens.append({
                    'Cenário': label_cen, 'VPL': v, 'TIR (%)': t,
                    'Payback Descontado': f"{pb:.1f} anos" if pb is not None else "Não recupera",
                    'Viável?': "✅ Sim" if v > 0 else "❌ Não",
                })
            df_sens = pd.DataFrame(linhas_sens)

            col_tab, col_graf = st.columns([1.1, 1], gap="medium")
            with col_tab:
                st.dataframe(
                    df_sens.style.format({'VPL': "R$ {:,.2f}", 'TIR (%)': "{:.2f}%"}),
                    use_container_width=True, hide_index=True
                )
            with col_graf:
                cores_sens = ['#E57373' if v < 0 else '#4CAF50' for v in df_sens['VPL']]
                fig_sens = go.Figure(go.Bar(
                    x=df_sens['Cenário'], y=df_sens['VPL'], marker_color=cores_sens,
                    hovertemplate='%{x}<br>VPL: R$ %{y:,.2f}<extra></extra>'
                ))
                fig_sens.add_hline(y=0, line_dash="dash", line_color="#FAFAFA")
                fig_sens.update_layout(
                    paper_bgcolor='#1E1E1E', plot_bgcolor='#121212', font={'color': '#FAFAFA'},
                    yaxis_title='VPL (R$)', height=260, margin=dict(l=10, r=10, t=10, b=10)
                )
                fig_sens.update_xaxes(gridcolor='#333333')
                fig_sens.update_yaxes(gridcolor='#333333')
                st.plotly_chart(fig_sens, use_container_width=True)

        st.caption(
            "Cenário Base = premissas de referência do imóvel selecionado, sem os ajustes dos sliders de "
            "sensibilidade do menu lateral (que servem para exploração livre, fora da tabela padronizada do enunciado)."
        )

    with tab_comparativo:
        st.markdown(f"#### Comparativo dos 4 imóveis — Horizonte: {horizonte} anos | TMA: {tma_base:.2f}% | Cenário: {cenario_label}")
        linhas_comp = []
        for nome, d in imoveis.items():
            res_c = simular_fluxos(
                d, horizonte, d['aluguel_mensal'], taxa_valorizacao,
                ipca=IPCA, taxa_adm=TAXA_ADM_LOCACAO, manutencao_pct=MANUTENCAO_PCT,
                taxa_juros=TAXA_JUROS_FINANC, prazo_financ=PRAZO_FINANCIAMENTO,
                entrada_pct=ENTRADA_PCT, irpj=IRPJ, csll=CSLL
            )
            fc_c = res_c['fluxo_acionista']
            fe_c = res_c['fluxo_empreendimento']

            vpl_c = vpl(tma_decimal, fc_c)
            tir_c = tir(fc_c) * 100
            pb_c = payback_descontado(fc_c, tma_decimal)
            vpl_e_c = vpl(tma_decimal, fe_c)
            tir_e_c = tir(fe_c) * 100

            linhas_comp.append({
                'Imóvel': nome,
                'Investimento': d['investimento'],
                'VPL Acionista': vpl_c,
                'TIR Acionista (%)': tir_c,
                'VPL Empreend.': vpl_e_c,
                'TIR Empreend. (%)': tir_e_c,
                'Payback Descontado': f"{pb_c:.1f} anos" if pb_c is not None else "Não recupera",
                'Viável?': "✅ Sim" if vpl_c > 0 else "❌ Não",
            })

        df_comp = pd.DataFrame(linhas_comp).sort_values('VPL Acionista', ascending=False).reset_index(drop=True)
        st.dataframe(
            df_comp.style.format({
                'Investimento': "R$ {:,.2f}", 'VPL Acionista': "R$ {:,.2f}", 'TIR Acionista (%)': "{:.2f}%",
                'VPL Empreend.': "R$ {:,.2f}", 'TIR Empreend. (%)': "{:.2f}%"
            }),
            use_container_width=True
        )

        cores_comp = ['#4CAF50' if v > 0 else '#E57373' for v in df_comp['VPL Acionista']]
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            x=df_comp['VPL Empreend.'], y=df_comp['Imóvel'], orientation='h', name='VPL Empreendimento',
            marker_color='#8a8a8a', hovertemplate='%{y}<br>VPL Empreend.: R$ %{x:,.2f}<extra></extra>'
        ))
        fig_comp.add_trace(go.Bar(
            x=df_comp['VPL Acionista'], y=df_comp['Imóvel'], orientation='h', name='VPL Acionista',
            marker_color=cores_comp, hovertemplate='%{y}<br>VPL Acionista: R$ %{x:,.2f}<extra></extra>'
        ))
        fig_comp.add_vline(x=0, line_dash="dash", line_color="#FAFAFA")
        fig_comp.update_layout(
            barmode='group', paper_bgcolor='#1E1E1E', plot_bgcolor='#121212', font={'color': '#FAFAFA'},
            xaxis_title='VPL (R$)', height=340, margin=dict(l=10, r=10, t=20, b=10),
            legend=dict(orientation='h', yanchor='bottom', y=1.02)
        )
        fig_comp.update_xaxes(gridcolor='#333333')
        st.plotly_chart(fig_comp, use_container_width=True)

        col_tir_comp, col_inv_comp = st.columns(2)
        with col_tir_comp:
            fig_tir_comp = go.Figure(go.Bar(
                x=df_comp['Imóvel'], y=df_comp['TIR Acionista (%)'], marker_color='#C5A059',
                hovertemplate='%{x}<br>TIR: %{y:.2f}%<extra></extra>'
            ))
            fig_tir_comp.add_hline(y=tma_base, line_dash="dot", line_color="#4CAF50",
                                    annotation_text="TMA exigida", annotation_font_color="#4CAF50")
            fig_tir_comp.update_layout(
                paper_bgcolor='#1E1E1E', plot_bgcolor='#121212', font={'color': '#FAFAFA'},
                yaxis_title='TIR Acionista (%)', height=320, margin=dict(l=10, r=10, t=20, b=10)
            )
            fig_tir_comp.update_xaxes(gridcolor='#333333')
            fig_tir_comp.update_yaxes(gridcolor='#333333')
            st.plotly_chart(fig_tir_comp, use_container_width=True)
            st.caption("TIR de cada imóvel comparada à TMA exigida (linha verde).")

        with col_inv_comp:
            fig_inv_comp = go.Figure(go.Bar(
                x=df_comp['Imóvel'], y=df_comp['Investimento'], marker_color='#8a8a8a',
                hovertemplate='%{x}<br>Investimento: R$ %{y:,.2f}<extra></extra>'
            ))
            fig_inv_comp.update_layout(
                paper_bgcolor='#1E1E1E', plot_bgcolor='#121212', font={'color': '#FAFAFA'},
                yaxis_title='Investimento Total (R$)', height=320, margin=dict(l=10, r=10, t=20, b=10)
            )
            fig_inv_comp.update_xaxes(gridcolor='#333333')
            fig_inv_comp.update_yaxes(gridcolor='#333333')
            st.plotly_chart(fig_inv_comp, use_container_width=True)
            st.caption("Tamanho do investimento necessário em cada opção.")

        st.caption(
            "Comparativo calculado com a mesma TMA e cenário de valorização selecionados no menu lateral, "
            "mantendo o aluguel-base de cada planilha (sem o ajuste de sensibilidade aplicado ao imóvel selecionado acima)."
        )

    with tab_resumo:
        st.markdown(f"#### Resumo Executivo — {imovel_selecionado}")
        st.markdown(f"""
        **Cenário analisado:** horizonte de **{horizonte} anos**, TMA de **{tma_base:.2f}%**,
        valorização de revenda **{cenario_label}**{f", variação de aluguel de {var_aluguel:+.0f}%" if var_aluguel != 0 else ""}.
        """)

        resumo_cols = st.columns(4)
        resumo_cols[0].metric("VPL", f"R$ {vpl_valor:,.0f}")
        resumo_cols[1].metric("TIR", f"{tir_valor:.2f}%")
        resumo_cols[2].metric("TMA exigida", f"{tma_base:.2f}%")
        resumo_cols[3].metric("Payback Desc.", f"{payback:.1f} anos" if payback is not None else "Não recupera")

        st.markdown("##### O que isso significa, em termos simples:")
        if vpl_valor > 0 and payback is not None:
            st.markdown(f"""
            - O projeto **gera mais valor do que custaria deixar o dinheiro rendendo na TMA** ({tma_base:.2f}%):
              o VPL positivo de R$ {vpl_valor:,.0f} é esse excedente, já trazido a valores de hoje.
            - O investimento se paga (em termos de valor presente) em aproximadamente **{payback:.1f} anos**.
            - A TIR de {tir_valor:.2f}% supera a TMA em {tir_valor - tma_base:.2f} pontos percentuais.
            """)
        elif vpl_valor > 0:
            st.markdown(f"""
            - O VPL é positivo (R$ {vpl_valor:,.0f}), mas o investimento só se paga (em valor presente)
              **no próprio ano da venda**, perto do fim do horizonte analisado.
            """)
        else:
            st.markdown(f"""
            - Pela ótica do VPL, este investimento **rende menos do que a TMA exigida** ({tma_base:.2f}%):
              o "buraco" de R$ {abs(vpl_valor):,.0f} é quanto valor é destruído frente a essa régua de exigência.
            - A TIR de {tir_valor:.2f}% fica **{tma_base - tir_valor:.2f} pontos percentuais abaixo** da TMA.
            - Isso não quer dizer que o projeto dá prejuízo contábil — ele ainda pode gerar caixa positivo no total —
              mas o retorno não compensa o custo de oportunidade do capital investido nessa régua de exigência.
            """)

        st.markdown("##### Principais premissas usadas neste cálculo:")
        st.markdown(f"""
        - Aluguel mensal-base: R$ {dados['aluguel_mensal']:,.2f} (ajustado para R$ {aluguel_mensal_ajustado:,.2f} com a sensibilidade aplicada)
        - Seguro + IPTU anuais: R$ {dados['seguro_anual'] + dados['iptu_anual']:,.2f}
        - Taxa de administração da locação + manutenção: {(TAXA_ADM_LOCACAO + MANUTENCAO_PCT) * 100:.0f}% sobre o aluguel recebido
        - Financiamento SAC: {PRAZO_FINANCIAMENTO} anos a {TAXA_JUROS_FINANC * 100:.0f}% a.a., entrada de {ENTRADA_PCT * 100:.0f}%
        - Venda ao final do horizonte com valorização **{cenario_label}**
        {f"- Imóvel na planta: {anos_carencia} anos de carência sem renda de aluguel" if anos_carencia > 0 else ""}
        """)

        st.info(
            "💡 Use as abas anteriores para ver o detalhamento ano a ano do fluxo de caixa, "
            "da tabela de financiamento, da sensibilidade do VPL à TMA e da comparação entre os 4 imóveis."
        )