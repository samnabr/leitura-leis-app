import streamlit as st
import json
import os
import bleach
import re
from supabase import create_client, Client
from collections import defaultdict, Counter
from datetime import datetime
import time
import uuid

# Carregar variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(page_title="Leitura de Leis por Cards", layout="centered")

# Configuração do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Erro: As credenciais do Supabase (SUPABASE_URL e SUPABASE_KEY) devem ser configuradas como variáveis de ambiente.")
    st.stop()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Função para carregar os dados do Supabase
def carregar_dados(usuario_completo):
    response = supabase.table("cards").select("*").eq("usuario", usuario_completo).execute()
    dados = response.data if response.data else []
    return dados

# Função para salvar um card no Supabase
def salvar_card(usuario_completo, card):
    data = {
        "usuario": usuario_completo,
        "concurso": card["concurso"],
        "lei": card["lei"],
        "pergunta": card["pergunta"],
        "resposta": card["resposta"],
        "referencia": card["referencia"],
        "vezes_lido": card["vezes_lido"]
    }
    supabase.table("cards").insert(data).execute()

# Função para atualizar um card no Supabase
def atualizar_card(usuario_completo, card_antigo, card_novo):
    supabase.table("cards").update({
        "concurso": card_novo["concurso"],
        "lei": card_novo["lei"],
        "pergunta": card_novo["pergunta"],
        "resposta": card_novo["resposta"],
        "referencia": card_novo["referencia"],
        "vezes_lido": card_novo["vezes_lido"]
    }).eq("usuario", usuario_completo).eq("pergunta", card_antigo["pergunta"]).execute()

# Função para excluir um card do Supabase usando o id
def excluir_card(card_id):
    supabase.table("cards").delete().eq("id", card_id).execute()

# Função para carregar dados de um arquivo JSON (para importação)
def carregar_dados_json(arquivo):
    with open(arquivo, "r", encoding="utf-8") as f:
        return json.load(f)

# Função para criar backup dos dados em formato JSON
def criar_backup(dados, usuario_completo, session_id):
    if dados:
        os.makedirs("backup", exist_ok=True)
        nome_backup = f"backup/{usuario_completo}_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(nome_backup, "w", encoding="utf-8") as f_backup:
            json.dump(dados, f_backup, ensure_ascii=False, indent=2)

# Função para validar o nome de usuário
def validar_usuario(usuario):
    usuario = usuario.strip().lower()
    if not re.match(r'^[a-z0-9_]+$', usuario):
        return None
    return usuario

# Função para exibir os cards filtrados e paginados
def exibir_cards(dados, concurso_escolhido, lei_escolhida, fonte, usuario_completo):
    filtro_leituras = st.selectbox(
        "Filtrar cards por número de leituras:",
        ["Todos", "Nunca lidos", "1 ou mais", "5 ou mais", "10 ou mais"]
    )

    busca = st.text_input("🔍 Buscar por palavra-chave, artigo, lei ou concurso:")

    # FILTRAGEM DOS CARDS
    perguntas_filtradas = []
    for i, item in enumerate(dados):
        vezes = item.get("vezes_lido", 0)
        if (
            item["concurso"] == concurso_escolhido and
            item["lei"] == lei_escolhida and
            (
                busca.lower() in item["pergunta"].lower() or
                busca.lower() in item["referencia"].lower()
            ) and (
                filtro_leituras == "Todos" or
                (filtro_leituras == "Nunca lidos" and vezes == 0) or
                (filtro_leituras == "1 ou mais" and vezes >= 1) or
                (filtro_leituras == "5 ou mais" and vezes >= 5) or
                (filtro_leituras == "10 ou mais" and vezes >= 10)
            )
        ):
            perguntas_filtradas.append((i, item))

    # Paginação
    PER_PAGE = 5
    total_paginas = (len(perguntas_filtradas) - 1) // PER_PAGE + 1 if perguntas_filtradas else 1

    if 'pagina' not in st.session_state:
        st.session_state['pagina'] = 1

    pagina_atual = st.sidebar.number_input(
        "Página", min_value=1, max_value=total_paginas, value=st.session_state['pagina'], step=1
    )

    inicio = (pagina_atual - 1) * PER_PAGE
    fim = inicio + PER_PAGE
    perguntas_pagina = perguntas_filtradas[inicio:fim]

    # EXIBIÇÃO DOS CARDS
    if perguntas_filtradas:
        st.markdown(f"### 📑 Cards Cadastrados ({len(perguntas_pagina)} de {len(perguntas_filtradas)} cards)")

        for i, item in perguntas_pagina:
            pergunta_sanitizada = bleach.clean(
                item['pergunta'],
                tags=['b', 'i', 'u', 'br'],
                strip=True
            )
            resposta_sanitizada = bleach.clean(
                item['resposta'],
                tags=['b', 'i', 'u', 'br'],
                strip=True
            )

            pergunta_label = bleach.clean(item['pergunta'], tags=[], strip=True)

            with st.expander(f"📌 Pergunta (assunto): {pergunta_label}"):
                st.markdown(f"<div style='font-size: {fonte}px;'>{pergunta_sanitizada}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: {fonte}px;'><b>Resposta (conteúdo):</b> {resposta_sanitizada}</div>", unsafe_allow_html=True)
                st.caption(f"📖 Referência: {item['referencia']}  \n📘 Lei: {item['lei']}  \n🎯 Concurso: {item.get('concurso', '[Sem Concurso]')}")
                col1, col2, col3 = st.columns([1, 1, 1])

                with col1:
                    if st.button(f"✅ Lido ({item.get('vezes_lido', 0)}x)", key=f"btn_lido_{i}"):
                        card_antigo = dados[i].copy()
                        dados[i]["vezes_lido"] = item.get("vezes_lido", 0) + 1
                        atualizar_card(usuario_completo, card_antigo, dados[i])
                        st.rerun()

                with col2:
                    if st.button("✏️ Editar", key=f"editar_{i}"):
                        st.session_state["editar_index"] = i

                with col3:
                    if st.button("🗑️ Excluir", key=f"excluir_{i}"):
                        if "id" in item:
                            excluir_card(item["id"])
                            dados.pop(i)
                            st.warning("❌ Card excluído.")
                            st.rerun()
                        else:
                            st.error("❌ Erro: ID do card não encontrado.")

        # Botões de navegação entre páginas
        col_pag1, col_pag2 = st.columns(2)
        with col_pag1:
            if pagina_atual > 1 and st.button("⬅️ Página Anterior"):
                st.session_state['pagina'] = pagina_atual - 1
                st.rerun()
        with col_pag2:
            if pagina_atual < total_paginas and st.button("➡️ Próxima Página"):
                st.session_state['pagina'] = pagina_atual + 1
                st.rerun()

    return perguntas_filtradas

# Inicializar estado de login e sessão
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['usuario'] = None
    st.session_state['usuario_completo'] = None
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = str(uuid.uuid4())

# 🔐 Login do usuário
if not st.session_state['logged_in']:
    usuario = st.text_input("🔐 Nome de usuário:")
    if usuario:
        usuario_valido = validar_usuario(usuario)
        if usuario_valido:
            # Combinar o nome de usuário com o session_id
            session_id = st.session_state['session_id']
            usuario_completo = f"{usuario_valido}_{session_id}"
            st.session_state['logged_in'] = True
            st.session_state['usuario'] = usuario_valido
            st.session_state['usuario_completo'] = usuario_completo
            st.rerun()
        else:
            st.error("❌ Nome de usuário inválido! Use apenas letras, números e sublinhados (ex.: joao123).")
    else:
        st.warning("Digite seu nome para continuar.")
    st.stop()

# Usuário logado
usuario = st.session_state['usuario']
usuario_completo = st.session_state['usuario_completo']
session_id = st.session_state['session_id']

# Carregar os dados
dados = carregar_dados(usuario_completo)

# Garantir que todos os cards tenham o campo "vezes_lido"
for d in dados:
    if "vezes_lido" not in d:
        d["vezes_lido"] = 0

# Interface do Sidebar
st.sidebar.markdown("---")
fonte = st.sidebar.slider("🔠 Tamanho da Fonte (px):", 12, 30, 16)

# Botão de Logout
if st.sidebar.button("🚪 Sair"):
    st.session_state['logged_in'] = False
    st.session_state['usuario'] = None
    st.session_state['usuario_completo'] = None
    st.session_state['session_id'] = str(uuid.uuid4())
    st.session_state.clear()
    st.rerun()

st.markdown(f"<h1 style='font-size: {fonte + 20}px;'>📚 Leitura de Leis por Cards</h1>", unsafe_allow_html=True)
st.markdown(f"**Usuário logado:** {usuario}")

if 'leituras' not in st.session_state:
    st.session_state.leituras = {}

# Restaurar backup
st.sidebar.markdown("🛠️ **Restaurar Backup**")
# Verificar se a pasta backup existe antes de listar os arquivos
if os.path.exists("backup"):
    arquivos_backup = sorted(
        [f for f in os.listdir("backup") if f.startswith(f"{usuario_completo}_{session_id}")],
        reverse=True
    )
else:
    arquivos_backup = []

if arquivos_backup:
    escolha_backup = st.sidebar.selectbox("Selecione um backup para restaurar", arquivos_backup)
    if st.sidebar.button("♻️ Restaurar este backup"):
        caminho = os.path.join("backup", escolha_backup)
        dados_importados = carregar_dados_json(caminho)
        # Limpar dados atuais do usuário no Supabase
        supabase.table("cards").delete().eq("usuario", usuario_completo).execute()
        # Salvar dados importados
        for item in dados_importados:
            salvar_card(usuario_completo, item)
        dados = carregar_dados(usuario_completo)
        st.sidebar.success("✅ Backup restaurado com sucesso!")
        st.rerun()
else:
    st.sidebar.caption("Nenhum backup encontrado.")

# Importar arquivo JSON
st.sidebar.markdown("📥 **Importar arquivo JSON personalizado**")
arquivo_json = st.sidebar.file_uploader("Escolha um arquivo .json", type="json")

if arquivo_json:
    # Limitar tamanho do arquivo a 2MB
    if arquivo_json.size > 2 * 1024 * 1024:  # 2MB
        st.sidebar.error("❌ Arquivo muito grande! Limite: 2MB")
    elif st.sidebar.button("📂 Importar este arquivo"):
        criar_backup(dados, usuario_completo, session_id)
        dados_importados = json.load(arquivo_json)
        # Limpar dados atuais do usuário no Supabase
        supabase.table("cards").delete().eq("usuario", usuario_completo).execute()
        # Salvar dados importados
        for item in dados_importados:
            salvar_card(usuario_completo, item)
        dados = carregar_dados(usuario_completo)
        st.sidebar.success("✅ Arquivo importado com sucesso!")
        st.rerun()

st.markdown("## 🎯 Selecione um concurso para começar")

concursos_disponiveis = sorted(set(d["concurso"] for d in dados if d.get("concurso")))
concurso_escolhido = st.selectbox("Concurso:", ["Selecionar"] + concursos_disponiveis)

if concurso_escolhido != "Selecionar":
    leis_do_concurso = sorted(set(d["lei"] for d in dados if d.get("concurso") == concurso_escolhido))
    lei_escolhida = st.selectbox("📘 Lei do concurso:", ["Selecionar"] + leis_do_concurso)

    if lei_escolhida != "Selecionar":
        st.markdown(f"### Cards da Lei **{lei_escolhida}** para o Concurso **{concurso_escolhido}**")
        perguntas_filtradas = exibir_cards(dados, concurso_escolhido, lei_escolhida, fonte, usuario_completo)

        # ✏️ Editar Card
        if "editar_index" in st.session_state:
            idx = st.session_state["editar_index"]
            st.markdown("---")
            st.subheader("✧️ Editar Card")
            item = dados[idx]

            concursos_cadastrados = sorted(set(d["concurso"] for d in dados if d.get("concurso")))
            leis_cadastradas = sorted(set(d["lei"] for d in dados if d.get("lei")))

            with st.form(f"form_editar_{idx}"):
                nova_pergunta = st.text_area("Pergunta (assunto)", value=item["pergunta"])
                nova_resposta = st.text_area("Resposta (conteúdo)", value=item["resposta"])
                nova_referencia = st.text_input("Referência", value=item["referencia"])
                nova_concurso = st.text_input("Concurso", value=item["concurso"])
                nova_lei = st.text_input("Lei", value=item["lei"])
                confirmar = st.form_submit_button("Salvar alterações")

                if confirmar:
                    if not nova_concurso or not nova_lei or not nova_pergunta or not nova_resposta:
                        st.error("❌ Todos os campos obrigatórios devem ser preenchidos!")
                    else:
                        nova_pergunta_sanitizada = bleach.clean(
                            nova_pergunta,
                            tags=['b', 'i', 'u', 'br'],
                            strip=True
                        )
                        nova_resposta_sanitizada = bleach.clean(
                            nova_resposta,
                            tags=['b', 'i', 'u', 'br'],
                            strip=True
                        )

                        novo_card = {
                            "usuario": usuario_completo,
                            "pergunta": nova_pergunta_sanitizada,
                            "resposta": nova_resposta_sanitizada,
                            "referencia": nova_referencia,
                            "concurso": nova_concurso,
                            "lei": nova_lei,
                            "vezes_lido": item.get("vezes_lido", 0)
                        }
                        atualizar_card(usuario_completo, item, novo_card)
                        dados[idx] = novo_card
                        del st.session_state["editar_index"]
                        st.success("✅ Sucesso ao alterar!")
                        time.sleep(1)
                        st.rerun()

# ESTATÍSTICAS
leituras_por_lei = Counter()
mais_lido_por_lei = {}

for item in dados:
    lei = item.get("lei", "[Sem Lei]")
    leituras_por_lei[lei] += item.get("vezes_lido", 0)
    if lei not in mais_lido_por_lei or item.get("vezes_lido", 0) > mais_lido_por_lei[lei].get("vezes_lido", 0):
        mais_lido_por_lei[lei] = item

mais_lidas = leituras_por_lei.most_common(5)

st.sidebar.markdown("---")
st.sidebar.markdown("📊 **Ranking de Leis Mais Lidas**")
for lei, total in mais_lidas:
    st.sidebar.markdown(f"**{lei}** — {total} leituras")

st.sidebar.markdown("---")
st.sidebar.markdown("🔥 **Card mais lido por lei**")
for lei, item in mais_lido_por_lei.items():
    st.sidebar.markdown(f"**{lei}** → *{item['pergunta'][:50]}...* ({item['vezes_lido']}x)")

# Exportar para Word
st.sidebar.markdown("📄 **Exportar para Word**")
if st.sidebar.button("⬇️ Baixar meus cards em Word"):
    from docx import Document

    doc = Document()
    doc.add_heading("Cards de Estudo", 0)

    for item in dados:
        doc.add_heading(item.get("concurso", "[Concurso]"), level=1)
        doc.add_heading(item.get("lei", "[Lei]"), level=2)
        doc.add_paragraph(f"Pergunta: {item['pergunta']}")
        doc.add_paragraph(f"Resposta: {item['resposta']}")
        doc.add_paragraph(f"Referência: {item['referencia']}")
        doc.add_paragraph("")

    caminho_word = f"cards_{usuario}.docx"
    doc.save(caminho_word)
    with open(caminho_word, "rb") as file:
        st.download_button(
            label="📥 Clique aqui para baixar",
            data=file,
            file_name=caminho_word,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

st.sidebar.markdown("---")
st.sidebar.markdown("➕ **Cadastrar Novo Card**")

with st.sidebar.form("form_novo_card"):
    novo_concurso = st.text_input("Concurso")
    nova_lei = st.text_input("Lei")
    nova_pergunta = st.text_area("Pergunta (assunto)")
    nova_resposta = st.text_area("Resposta (conteúdo)")
    nova_referencia = st.text_input("Referência")
    st.caption("Nota: Você pode colar texto com formatação HTML básica (ex.: <b>negrito</b>, <i>itálico</i>) e ela será preservada.")
    cadastrar = st.form_submit_button("📌 Adicionar Card")

    if cadastrar:
        if not novo_concurso or not nova_lei or not nova_pergunta or not nova_resposta:
            st.sidebar.error("❌ Todos os campos obrigatórios devem ser preenchidos!")
        else:
            nova_pergunta_sanitizada = bleach.clean(
                nova_pergunta,
                tags=['b', 'i', 'u', 'br'],
                strip=True
            )
            nova_resposta_sanitizada = bleach.clean(
                nova_resposta,
                tags=['b', 'i', 'u', 'br'],
                strip=True
            )

            novo_card = {
                "usuario": usuario_completo,
                "concurso": novo_concurso,
                "lei": nova_lei,
                "pergunta": nova_pergunta_sanitizada,
                "resposta": nova_resposta_sanitizada,
                "referencia": nova_referencia,
                "vezes_lido": 0
            }
            dados.append(novo_card)
            salvar_card(usuario_completo, novo_card)
            st.sidebar.success("✅ Card adicionado com sucesso!")
            time.sleep(1)
            st.rerun()

st.sidebar.markdown("---")