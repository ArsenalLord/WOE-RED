import os
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random

# ============================================================
# FLASK
# ============================================================

app = Flask("")


@app.route("/")
def home():
    return "Estou vivo!"


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


Thread(target=run, daemon=True).start()


# ============================================================
# BOT DISCORD
# ============================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ============================================================
# ARQUIVO DE EVENTOS
# ============================================================

ARQUIVO_EVENTOS = "eventos.json"

if os.path.exists(ARQUIVO_EVENTOS):
    try:
        with open(ARQUIVO_EVENTOS, "r", encoding="utf-8") as f:
            eventos = json.load(f)
    except Exception:
        eventos = {}
else:
    eventos = {}


# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Cada classe tem: o arquivo de imagem (emoji da aplicação) e um
# emoji unicode de reserva, usado enquanto o upload não acontece.
CLASSES = [
    {"nome": "Mestre",             "arquivo": "MONK.webp",           "fallback": "👊"},
    {"nome": "Sumo Sacerdote",     "arquivo": "SUMO.webp",           "fallback": "🙏"},
    {"nome": "Lorde",              "arquivo": "LK.webp",             "fallback": "⚔️"},
    {"nome": "Paladino",           "arquivo": "PALADIN.webp",        "fallback": "🛡️"},
    {"nome": "Algoz",              "arquivo": "SINX.webp",           "fallback": "🗡️"},
    {"nome": "Desordeiro",         "arquivo": "STALKER.webp",        "fallback": "🗝️"},
    {"nome": "Cigana",             "arquivo": "DANCER.webp",         "fallback": "💃"},
    {"nome": "Bardo",              "arquivo": "MENESTREL.png",       "fallback": "🎻"},
    {"nome": "Atirador de Elite",  "arquivo": "SNIPER.webp",         "fallback": "🏹"},
    {"nome": "Professor",          "arquivo": "PROFESSOR.webp",      "fallback": "📘"},
    {"nome": "Arquimago",          "arquivo": "WIZARD.webp",         "fallback": "🔥"},
    {"nome": "Mestre-Ferreiro",    "arquivo": "FERREIRO.webp",       "fallback": "🔨"},
    {"nome": "Criador",            "arquivo": "CREATOR.webp",        "fallback": "⚗️"},
    {"nome": "Justiceiro",         "arquivo": "GUNS.png",            "fallback": "🔫"},
    {"nome": "Mestre Taekon",      "arquivo": "MTK.png",             "fallback": "🥋"},
    {"nome": "Espiritualista",     "arquivo": "ESPIRITUALISTA.png",  "fallback": "🔮"},
    {"nome": "Ninja",              "arquivo": "NINJA.png",           "fallback": "🥷"},
    {"nome": "Super Aprendiz",     "arquivo": "SUPER APRENDIZ.png",  "fallback": "🎓"},
]

CLASSES_FIXAS = [classe["nome"] for classe in CLASSES]

PASTA_EMOJIS = "emojis"

# Preenchido no on_ready com os emojis enviados para a aplicação.
EMOJIS_CLASSES = {}

LIMITE_PT = 12
FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")

# Banner exibido no rodapé de todos os painéis de evento.
# Deixe como None para não mostrar imagem nenhuma.
IMAGEM_EVENTO = (
    "https://assets.gnjoyamericas.com/static/upload/notice/2026/09/"
    "EVENTO_PTBR%20(1)_7101c78a.gif"
)

# ------------------------------------------------------------------
# TIPOS DE EVENTO
# ------------------------------------------------------------------
# Cada comando de criação usa um preset daqui. Para acrescentar um
# tipo novo: adicione a entrada abaixo e registre o comando no bloco
# "COMANDOS DE CRIAÇÃO DE EVENTO", no fim do arquivo.
#
#   rotulo      -> nome do tipo, usado nas mensagens de confirmação
#   nome_padrao -> nome sugerido do evento (None = sempre digitar)
#   thumbnail   -> ícone no canto superior direito do painel
#   imagem      -> banner próprio (None = usa IMAGEM_EVENTO)

def letras_emoji(texto):
    """
    Escreve um texto com as letras em emoji: "ESGOTO" -> 🇪 🇸 🇬 🇴 🇹 🇴

    Duas coisas importantes acontecem aqui:

    1. Os códigos `:regional_indicator_e:` só funcionam quando UMA PESSOA
       digita na caixa de mensagem — é o app do Discord que troca pelo
       emoji. O bot precisa mandar o caractere de verdade, senão aparece
       o texto `:regional_indicator_e:` cru na tela.

    2. Duas dessas letras coladas viram BANDEIRA. "ESGOTO REAL" sem
       separador vira 🇪🇸 (Espanha) + 🇹🇴 (Tonga) + 🇷🇪 + 🇦🇱 (Albânia).
       Por isso cada letra sai separada por um espaço.
    """
    partes = []

    for letra in texto.upper():
        if "A" <= letra <= "Z":
            # 0x1F1E6 é o 🇦; o resto do alfabeto vem em sequência.
            partes.append(chr(0x1F1E6 + ord(letra) - ord("A")))
        elif letra == " ":
            partes.append(" ")      # separação maior entre palavras
        else:
            partes.append(letra)

    return " ".join(partes)


TIPO_PADRAO = "padrao"

TIPOS_EVENTO = {
    "padrao": {
        "rotulo": "Evento",
        "nome_padrao": None,
        "thumbnail": (
            "https://wiki.aureumro.com/images/6/65/FogueiraZeny_npc.gif?v=2"
        ),
        "imagem": None,
    },
    "esgoto": {
        "rotulo": "Esgoto Real",
        "nome_padrao": letras_emoji("Esgoto Real"),
        "thumbnail": (
            "https://wiki.aureumro.com/images/8/8e/EsgMob_esporo_real_v2.gif"
        ),
        "imagem": None,
    },
    "torre": {
        "rotulo": "Torre Sem Fim",
        "nome_padrao": letras_emoji("Torre Sem Fim"),
        "thumbnail": (
            "https://wiki.aureumro.com/images/9/94/TorreSemFim_npc.gif"
        ),
        "imagem": None,
    },
}


def preset_evento(evento):
    """Preset visual do evento, caindo no padrão se o tipo não existir."""
    tipo = (evento or {}).get("tipo") or TIPO_PADRAO
    return TIPOS_EVENTO.get(tipo, TIPOS_EVENTO[TIPO_PADRAO])


# ============================================================
# MIGRAÇÃO / COMPATIBILIDADE
# ============================================================

TAMANHO_ID_EVENTO = 4


def id_valido(texto):
    """Um ID bom é só dígitos e do tamanho combinado."""
    texto = str(texto)
    return texto.isdigit() and len(texto) == TAMANHO_ID_EVENTO


def gerar_evento_id(ja_usados=None):
    """
    Código aleatório de 4 dígitos, único entre os eventos existentes.

    São 10 mil combinações para uma agenda que costuma ter poucos
    eventos ao mesmo tempo, então a colisão é rara — mas quando
    acontece, sorteia de novo em vez de sobrescrever o evento antigo.
    """
    ocupados = set(eventos)

    if ja_usados:
        ocupados |= set(ja_usados)

    for _ in range(500):
        codigo = f"{random.randint(0, 9999):0{TAMANHO_ID_EVENTO}d}"

        if codigo not in ocupados:
            return codigo

    # Só chega aqui se quase todos os 10 mil códigos estiverem em uso.
    return f"{random.randint(10000, 99999)}"


def migrar_eventos_antigos():
    """
    Converte o formato antigo, em que o nome do evento era a chave,
    para o novo formato, em que cada evento possui um ID próprio.

    Isso permite vários eventos com o mesmo nome sem apagar os antigos.
    """
    global eventos

    if not isinstance(eventos, dict):
        eventos = {}
        return

    novos = {}
    alterou = False

    for chave, evento in eventos.items():
        if not isinstance(evento, dict):
            continue

        # Já está no formato novo.
        if "nome_evento" in evento and "evento_id" in evento:
            evento_id = str(evento["evento_id"])

            # IDs longos do formato antigo viram códigos de 4 dígitos.
            if not id_valido(evento_id) or evento_id in novos:
                evento_id = gerar_evento_id(novos)

            evento["evento_id"] = evento_id
            evento.setdefault("reservas", {})
            evento.setdefault("presentes", {})
            evento.setdefault("nao_vou", {})
            evento.setdefault("tipo", TIPO_PADRAO)
            novos[evento_id] = evento
            continue

        # Formato antigo: a chave era o nome do evento.
        evento_id = gerar_evento_id(novos)

        evento["evento_id"] = evento_id
        evento["nome_evento"] = str(chave)
        evento.setdefault("presentes", {})
        evento.setdefault("nao_vou", {})
        evento.setdefault("reservas", {})
        evento.setdefault("mensagem_id", None)
        evento.setdefault("canal_id", None)
        evento.setdefault("aviso_10_minutos", False)
        evento.setdefault("tipo", TIPO_PADRAO)

        # Reservas manuais não existiam no formato antigo.
        novos[evento_id] = evento
        alterou = True

    if novos != eventos:
        eventos = novos
        alterou = True

    if alterou:
        salvar_eventos()


# ============================================================
# SALVAR EVENTOS
# ============================================================

def salvar_eventos():
    with open(
        ARQUIVO_EVENTOS,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            eventos,
            f,
            indent=4,
            ensure_ascii=False
        )


migrar_eventos_antigos()


# ============================================================
# EMOJIS DAS CLASSES
# ============================================================

def nome_emoji_discord(arquivo):
    """MONK.webp -> ro_monk (nomes de emoji só aceitam letras/números/_)."""
    base = os.path.splitext(arquivo)[0].lower()
    limpo = "".join(c if c.isalnum() else "_" for c in base)
    return f"ro_{limpo}"[:32]


def emoji_classe(nome_classe):
    """Emoji da aplicação quando disponível, senão o unicode de reserva."""
    if nome_classe in EMOJIS_CLASSES:
        return EMOJIS_CLASSES[nome_classe]

    for classe in CLASSES:
        if classe["nome"] == nome_classe:
            return classe["fallback"]

    return "❔"


async def sincronizar_emojis_classes():
    """
    Envia as imagens das classes como emojis DA APLICAÇÃO.

    Emojis de aplicação funcionam em qualquer servidor onde o bot esteja
    e não ocupam os slots de emoji do servidor. O envio acontece só uma
    vez: nas próximas inicializações os emojis já existentes são reusados.
    """
    try:
        existentes = {
            emoji.name: emoji
            for emoji in await bot.fetch_application_emojis()
        }
    except Exception as e:
        print(f"⚠️ Não foi possível listar os emojis da aplicação: {e}")
        return

    enviados = 0

    for classe in CLASSES:
        arquivo = classe["arquivo"]

        if not arquivo:
            continue

        nome_emoji = nome_emoji_discord(arquivo)

        # Já foi enviado em uma execução anterior.
        if nome_emoji in existentes:
            EMOJIS_CLASSES[classe["nome"]] = str(existentes[nome_emoji])
            continue

        caminho = os.path.join(PASTA_EMOJIS, arquivo)

        if not os.path.exists(caminho):
            print(f"⚠️ Imagem não encontrada: {caminho}")
            continue

        try:
            with open(caminho, "rb") as f:
                imagem = f.read()

            emoji = await bot.create_application_emoji(
                name=nome_emoji,
                image=imagem
            )

            EMOJIS_CLASSES[classe["nome"]] = str(emoji)
            enviados += 1

        except Exception as e:
            print(
                f"⚠️ Falha ao enviar o emoji de {classe['nome']}: {e}"
            )

    total = len(EMOJIS_CLASSES)

    if enviados:
        print(f"🎨 {enviados} emoji(s) de classe enviados para a aplicação.")

    print(f"🎨 {total}/{len(CLASSES)} classes com emoji próprio.")


# ============================================================
# HORÁRIO
# ============================================================

def horario_atual():
    return datetime.now(FUSO_HORARIO)


def formatar_horario(data_iso):
    try:
        data = datetime.fromisoformat(data_iso)
        return data.strftime("%H:%M")
    except Exception:
        return "--:--"


def formatar_data_horario(data_iso):
    try:
        data = datetime.fromisoformat(data_iso)
        return data.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        return "Data inválida"


# ============================================================
# CONVERTER DATA DO COMANDO
# ============================================================

def converter_data_evento(data, horario):
    try:
        data_hora = datetime.strptime(
            f"{data} {horario}",
            "%d/%m/%Y %H:%M"
        )
        return data_hora.replace(tzinfo=FUSO_HORARIO)
    except ValueError:
        return None


# ============================================================
# BUSCAR EVENTOS
# ============================================================

def obter_evento(evento_id):
    return eventos.get(str(evento_id))


def normalizar_id_evento(texto):
    """
    Aceita 427, 0427 ou #0427 e devolve sempre 0427.
    Devolve None quando não há dígito nenhum no que foi digitado.
    """
    digitos = "".join(c for c in str(texto or "") if c.isdigit())

    if not digitos:
        return None

    return digitos.zfill(TAMANHO_ID_EVENTO)


def eventos_por_nome(nome_evento):
    nome = nome_evento.strip().casefold()
    encontrados = []

    for evento_id, evento in eventos.items():
        if evento.get("nome_evento", "").strip().casefold() == nome:
            encontrados.append((evento_id, evento))

    encontrados.sort(
        key=lambda item: item[1].get("horario_inicio", "9999")
    )
    return encontrados


def encontrar_evento_por_nome_data(nome_evento, data, horario):
    data_hora = converter_data_evento(data, horario)
    if data_hora is None:
        return None

    alvo = data_hora.isoformat()

    for evento_id, evento in eventos_por_nome(nome_evento):
        if evento.get("horario_inicio") == alvo:
            return evento_id, evento

    return None


# ============================================================
# NORMALIZAR PARTICIPANTE
# ============================================================

def normalizar_participante(user_id, dados):
    if isinstance(dados, dict):
        return {
            "user_id": str(user_id),
            "classe": dados.get("classe", "Sem classe"),
            "horario": dados.get("horario", "")
        }

    # Compatibilidade com eventos antigos.
    return {
        "user_id": str(user_id),
        "classe": dados,
        "horario": ""
    }


# ============================================================
# ORDENAR PARTICIPANTES
# ============================================================

def ordenar_participantes(dados):
    participantes = []

    for user_id, dados in (dados or {}).items():
        participante = normalizar_participante(user_id, dados)
        participantes.append(participante)

    participantes.sort(
        key=lambda x: x["horario"] or "9999"
    )

    return participantes


# ============================================================
# SEPARAR PT E RESERVAS
# ============================================================

def separar_participantes(evento):
    """
    PT = primeiros 12 usuários que marcaram presença.

    Reservas = todos os que ficaram fora da PT + todos que usaram
    explicitamente o botão "Entrar na Reserva".
    """
    confirmados = ordenar_participantes(
        evento.get("presentes", {})
    )

    pt_formada = confirmados[:LIMITE_PT]
    reservas_confirmacao = confirmados[LIMITE_PT:]

    reservas_manuais = ordenar_participantes(
        evento.get("reservas", {})
    )

    reservas = reservas_confirmacao + reservas_manuais
    reservas.sort(
        key=lambda x: x["horario"] or "9999"
    )

    return pt_formada, reservas


# ============================================================
# PARTICIPANTES EM RESERVA
# ============================================================

def usuario_esta_em_reserva(evento, user_id):
    user_id = str(user_id)

    if user_id in evento.get("reservas", {}):
        return True

    confirmados = ordenar_participantes(
        evento.get("presentes", {})
    )

    ids_reserva = {
        p["user_id"]
        for p in confirmados[LIMITE_PT:]
    }

    return user_id in ids_reserva


def obter_dados_usuario(evento, user_id):
    user_id = str(user_id)

    for grupo in ("presentes", "reservas", "nao_vou"):
        dados = evento.get(grupo, {}).get(user_id)
        if dados is not None:
            return normalizar_participante(user_id, dados)

    return None


# ============================================================
# PROMOVER PRÓXIMA RESERVA
# ============================================================

def promover_proxima_reserva(evento):
    """
    Preenche uma vaga da PT usando a reserva mais antiga.

    Reservas vindas do excesso de confirmações já estão em
    evento["presentes"] e entram automaticamente na PT.
    Reservas manuais precisam ser movidas para "presentes".
    """
    pt_formada, reservas = separar_participantes(evento)

    if len(pt_formada) >= LIMITE_PT or not reservas:
        return None

    proximo = reservas[0]
    user_id = proximo["user_id"]

    if user_id in evento.get("reservas", {}):
        dados = normalizar_participante(
            user_id,
            evento["reservas"][user_id]
        )

        evento.setdefault("reservas", {}).pop(user_id, None)
        evento.setdefault("presentes", {})[user_id] = {
            "classe": dados["classe"],
            "horario": dados["horario"]
        }

        salvar_eventos()

    return proximo


# ============================================================
# FORMATAR PARTICIPANTE
# ============================================================

def timestamp_discord(data_iso, estilo="F"):
    """
    Timestamp nativo do Discord: cada pessoa vê no próprio fuso e o
    estilo "R" vira uma contagem regressiva que se atualiza sozinha.
    """
    try:
        data = datetime.fromisoformat(data_iso)
        return f"<t:{int(data.timestamp())}:{estilo}>"
    except Exception:
        return "`--`"


def barra_progresso(atual, total):
    atual = max(0, min(atual, total))
    return "▰" * atual + "▱" * (total - atual)


def formatar_participante(participante, numero=None):
    emoji = emoji_classe(participante["classe"])
    prefixo = f"`{numero:02d}` " if numero is not None else ""

    return (
        f"{prefixo}{emoji} <@{participante['user_id']}> · "
        f"**{participante['classe']}** · "
        f"`{formatar_horario(participante['horario'])}`"
    )


def formatar_lista_participantes(lista, numerar=True, vagas_livres=0):
    linhas = []

    for numero, participante in enumerate(lista, start=1):
        linhas.append(
            formatar_participante(
                participante,
                numero if numerar else None
            )
        )

    # Vagas ainda abertas na PT, para deixar claro quanto falta.
    for numero in range(len(lista) + 1, len(lista) + 1 + vagas_livres):
        linhas.append(f"`{numero:02d}` ◽ *vaga aberta*")

    if not linhas:
        return "*— ninguém por aqui —*"

    return "\n".join(linhas)


def dividir_texto_discord(texto, limite=1000):
    if len(texto) <= limite:
        return [texto]

    partes = []
    atual = ""

    for linha in texto.split("\n"):
        tentativa = f"{atual}\n{linha}" if atual else linha

        if len(tentativa) <= limite:
            atual = tentativa
        else:
            if atual:
                partes.append(atual)
            atual = linha

    if atual:
        partes.append(atual)

    return partes


def adicionar_campo_lista(embed, titulo, texto, maximo_partes=3):
    """
    Cada campo de embed aceita no máximo 1024 caracteres. Listas maiores
    são quebradas em campos de continuação em vez de derrubar a mensagem.
    """
    partes = dividir_texto_discord(texto, 1024)
    excedente = partes[maximo_partes:]

    for indice, parte in enumerate(partes[:maximo_partes]):
        embed.add_field(
            name=titulo if indice == 0 else "\u200b",
            value=parte,
            inline=False
        )

    if excedente:
        restantes = sum(
            parte.count("\n") + 1
            for parte in excedente
        )
        embed.add_field(
            name="\u200b",
            value=f"*… e mais {restantes} pessoa(s).*",
            inline=False
        )


# ============================================================
# CRIAR EMBED DO EVENTO
# ============================================================

def criar_embed_evento(evento, titulo_prefixo=None):
    nome_evento = evento.get("nome_evento", "Evento")
    horario_inicio = evento.get("horario_inicio")

    pt_formada, reservas = separar_participantes(evento)
    ausentes = ordenar_participantes(evento.get("nao_vou", {}))

    vagas_livres = max(0, LIMITE_PT - len(pt_formada))
    lotado = vagas_livres == 0

    ja_comecou = False
    if horario_inicio:
        try:
            ja_comecou = (
                datetime.fromisoformat(horario_inicio) <= horario_atual()
            )
        except Exception:
            ja_comecou = False

    if ja_comecou:
        cor = 0x4E5058      # cinza — evento já iniciado
    elif lotado:
        cor = 0x2ECC71      # verde — PT completa
    else:
        cor = 0x5865F2      # azul — em formação

    titulo = f"  {nome_evento.upper()}"
    if titulo_prefixo:
        titulo = f"{titulo_prefixo}  ·  {nome_evento.upper()}"

    descricao = []

    if horario_inicio:
        descricao.append(
            f"🗓️  **Início**  ·  {timestamp_discord(horario_inicio, 'F')}"
        )
        descricao.append(
            f"⏳  **{'Começou' if ja_comecou else 'Começa'}**  ·  "
            f"{timestamp_discord(horario_inicio, 'R')}"
        )
        descricao.append("")

    descricao.append(
        f"`{barra_progresso(len(pt_formada), LIMITE_PT)}`  "
        f"**{len(pt_formada)}/{LIMITE_PT}**"
        + ("  ·  🔒 **PT COMPLETA**" if lotado else f"  ·  {vagas_livres} vaga(s)")
    )

    embed = discord.Embed(
        title=titulo,
        description="\n".join(descricao),
        color=cor
    )

    preset = preset_evento(evento)

    if preset.get("thumbnail"):
        embed.set_thumbnail(url=preset["thumbnail"])

    imagem = preset.get("imagem") or IMAGEM_EVENTO

    if imagem:
        embed.set_image(url=imagem)

    adicionar_campo_lista(
        embed,
        f"👥  GRUPO  ·  {len(pt_formada)}/{LIMITE_PT}",
        formatar_lista_participantes(
            pt_formada,
            vagas_livres=vagas_livres
        )
    )

    adicionar_campo_lista(
        embed,
        f"🪑  RESERVAS  ·  {len(reservas)}",
        formatar_lista_participantes(reservas)
    )

    adicionar_campo_lista(
        embed,
        f"🔴  AUSENTES  ·  {len(ausentes)}",
        formatar_lista_participantes(ausentes, numerar=False)
    )

    embed.set_footer(
        text=(
            f"ID {evento.get('evento_id', '----')}  ·  "
            f"Os {LIMITE_PT} primeiros confirmados formam a PT  ·  "
            "Atualizado"
        )
    )

    embed.timestamp = horario_atual()

    return embed


# ============================================================
# ATUALIZAR MENSAGEM DO EVENTO
# ============================================================

async def atualizar_mensagem(evento_id, channel=None):
    evento = obter_evento(evento_id)

    if not evento:
        return

    canal_id = evento.get("canal_id")
    mensagem_id = evento.get("mensagem_id")

    canal = bot.get_channel(canal_id) if canal_id else channel

    if canal is None:
        canal = channel

    if canal is None:
        print(f"❌ Canal não encontrado para o evento {evento_id}.")
        return

    mensagem = None

    try:
        if mensagem_id:
            try:
                mensagem = await canal.fetch_message(int(mensagem_id))
            except (discord.NotFound, discord.HTTPException):
                mensagem = None

        # Compatibilidade com eventos antigos que não tenham mensagem_id.
        if mensagem is None:
            nome_evento = evento.get("nome_evento", "")
            horario_inicio = evento.get("horario_inicio")

            async for msg in canal.history(limit=200):
                if not msg.embeds:
                    continue

                embed_antigo = msg.embeds[0]
                titulo = embed_antigo.title or ""

                # Aceita o layout novo e o antigo, para não perder os
                # painéis já publicados antes desta atualização.
                titulos_validos = (
                    f"  {nome_evento.upper()}",
                    f"📅 Evento: {nome_evento}",
                )

                if titulo not in titulos_validos:
                    continue

                # Se houver mais de um evento com o mesmo nome, confira a data.
                if horario_inicio:
                    marcas_horario = (
                        formatar_data_horario(horario_inicio),
                        timestamp_discord(horario_inicio, "F"),
                    )

                    texto_embed = (embed_antigo.description or "") + "".join(
                        field.value or "" for field in embed_antigo.fields
                    )

                    if not any(marca in texto_embed for marca in marcas_horario):
                        continue

                mensagem = msg
                evento["mensagem_id"] = msg.id
                salvar_eventos()
                break

        if mensagem is None:
            print(
                f"⚠️ Mensagem não encontrada para o evento "
                f"{evento.get('nome_evento', evento_id)}"
            )
            return

        await mensagem.edit(
            embed=criar_embed_evento(evento),
            view=PresencaView(evento_id)
        )

        print(
            f"✅ Evento atualizado: "
            f"{evento.get('nome_evento', evento_id)}"
        )

    except Exception as e:
        print(
            f"❌ Erro ao atualizar evento "
            f"{evento.get('nome_evento', evento_id)}: {e}"
        )


# ============================================================
# AVISO 10 MINUTOS
# ============================================================

async def verificar_eventos_10_minutos():
    agora = horario_atual()

    for evento_id, evento in list(eventos.items()):
        horario_inicio_str = evento.get("horario_inicio")

        if not horario_inicio_str:
            continue

        try:
            horario_inicio = datetime.fromisoformat(horario_inicio_str)
        except Exception:
            continue

        diferenca = horario_inicio - agora

        if timedelta(0) <= diferenca <= timedelta(minutes=10):
            if evento.get("aviso_10_minutos", False):
                continue

            canal_id = evento.get("canal_id")
            canal = bot.get_channel(canal_id) if canal_id else None

            if canal is None:
                continue

            pt_formada, _ = separar_participantes(evento)
            nome_evento = evento.get("nome_evento", "Evento")

            if not pt_formada:
                mensagem = (
                    f"🚨 **ATENÇÃO!**\n\n"
                    f"📅 **{nome_evento}** começa às "
                    f"**{horario_inicio.strftime('%H:%M')}**.\n\n"
                    f"⚠️ A PT ainda está vazia."
                )
            else:
                mencoes = " ".join(
                    f"<@{p['user_id']}>"
                    for p in pt_formada
                )

                mensagem = (
                    f"🚨 **ATENÇÃO — FALTAM 10 MINUTOS!**\n\n"
                    f"📅 **Evento:** {nome_evento}\n"
                    f"⏰ **Início:** {horario_inicio.strftime('%H:%M')}\n\n"
                    f"🟢 **PT FORMADA:**\n"
                    f"{mencoes}\n\n"
                    f"⚔️ A PT está sendo chamada para o evento."
                )

            try:
                await canal.send(mensagem)
                evento["aviso_10_minutos"] = True
                salvar_eventos()

                print(
                    f"⏰ Aviso de 10 minutos enviado: "
                    f"{nome_evento}"
                )

            except Exception as e:
                print(f"Erro ao enviar aviso: {e}")


# ============================================================
# FINALIZAÇÃO AUTOMÁTICA DOS EVENTOS
# ============================================================

TEMPO_FINALIZACAO_EVENTO = timedelta(hours=2)


async def finalizar_eventos_expirados():
    """
    Finaliza automaticamente cada evento 2 horas após seu início.

    - Apaga o painel do Discord quando possível.
    - Remove o evento do eventos.json.
    - Se a mensagem já tiver sido apagada, considera o evento finalizado.
    - Se houver erro temporário de API/permissão, mantém o evento no JSON
      para tentar novamente no próximo ciclo.
    """
    agora = horario_atual()

    for evento_id, evento in list(eventos.items()):
        horario_inicio_str = evento.get("horario_inicio")

        if not horario_inicio_str:
            continue

        try:
            horario_inicio = datetime.fromisoformat(horario_inicio_str)
        except Exception:
            print(
                f"⚠️ Não foi possível interpretar a data do evento "
                f"{evento_id}: {horario_inicio_str}"
            )
            continue

        horario_finalizacao = horario_inicio + TEMPO_FINALIZACAO_EVENTO

        if agora < horario_finalizacao:
            continue

        nome_evento = evento.get("nome_evento", f"Evento {evento_id}")
        canal_id = evento.get("canal_id")
        mensagem_id = evento.get("mensagem_id")

        # Se não existe painel conhecido para apagar, apenas finaliza
        # o registro local para não manter eventos antigos indefinidamente.
        if not canal_id or not mensagem_id:
            eventos.pop(evento_id, None)
            salvar_eventos()
            print(
                f"🗑️ Evento finalizado (sem painel registrado): "
                f"{nome_evento} | ID={evento_id}"
            )
            continue

        try:
            canal = bot.get_channel(int(canal_id))

            if canal is None:
                try:
                    canal = await bot.fetch_channel(int(canal_id))
                except discord.NotFound:
                    canal = None

            if canal is None:
                # O canal não existe mais. Não há painel para apagar.
                eventos.pop(evento_id, None)
                salvar_eventos()
                print(
                    f"🗑️ Evento finalizado (canal não encontrado): "
                    f"{nome_evento} | ID={evento_id}"
                )
                continue

            try:
                mensagem = await canal.fetch_message(int(mensagem_id))
                await mensagem.delete()
                print(
                    f"🗑️ Painel apagado após 2h: "
                    f"{nome_evento} | ID={evento_id}"
                )

            except discord.NotFound:
                print(
                    f"🗑️ Painel já não existia: "
                    f"{nome_evento} | ID={evento_id}"
                )

            # Só remove do JSON depois de apagar a mensagem ou confirmar
            # que ela já não existe.
            eventos.pop(evento_id, None)
            salvar_eventos()

            print(
                f"🏁 Evento finalizado: "
                f"{nome_evento} | ID={evento_id}"
            )

        except discord.Forbidden:
            print(
                f"⚠️ Sem permissão para finalizar o evento "
                f"{nome_evento} | ID={evento_id}. "
                f"Nova tentativa em 30s."
            )

        except discord.HTTPException as e:
            print(
                f"⚠️ Erro HTTP ao finalizar o evento "
                f"{nome_evento} | ID={evento_id}: {e}. "
                f"Nova tentativa em 30s."
            )

        except Exception as e:
            print(
                f"⚠️ Erro ao finalizar o evento "
                f"{nome_evento} | ID={evento_id}: {e}"
            )


# ============================================================
# LOOP DE VERIFICAÇÃO
# ============================================================

@tasks.loop(seconds=30)
async def verificar_eventos():
    await verificar_eventos_10_minutos()
    await finalizar_eventos_expirados()


# ============================================================
# SELECT DE CLASSE
# ============================================================

class ClasseSelect(discord.ui.Select):

    def __init__(self, evento_id, user_id, tipo):
        self.evento_id = str(evento_id)
        self.user_id = str(user_id)
        self.tipo = tipo

        options = [
            discord.SelectOption(
                label=classe["nome"],
                emoji=emoji_classe(classe["nome"])
            )
            for classe in CLASSES
        ]

        super().__init__(
            placeholder="Escolha sua classe",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction):
        escolha = self.values[0]
        evento = obter_evento(self.evento_id)

        if not evento:
            await interaction.response.send_message(
                "❌ Evento não encontrado.",
                ephemeral=True
            )
            return

        agora = horario_atual()
        self_user = self.user_id

        # ====================================================
        # CONFIRMAR PRESENÇA
        # ====================================================
        if self.tipo == "presente":
            if self_user in evento.get("presentes", {}):
                await interaction.response.send_message(
                    "⚠️ Você já está confirmado neste evento.",
                    ephemeral=True
                )
                return

            # Se estava em reserva manual, volta para a fila de presença.
            evento.setdefault("reservas", {}).pop(self_user, None)

            # Se estava como NÃO VOU, retorna ao final da fila mantendo a classe escolhida.
            evento.setdefault("nao_vou", {}).pop(self_user, None)

            evento.setdefault("presentes", {})[self_user] = {
                "classe": escolha,
                "horario": agora.isoformat()
            }

            salvar_eventos()

            await interaction.response.send_message(
                (
                    f"✅ Presença confirmada como **{escolha}** às "
                    f"**{agora.strftime('%H:%M')}**.\n\n"
                    "📋 Sua posição será definida pela ordem de confirmação."
                ),
                ephemeral=True
            )

            await atualizar_mensagem(self.evento_id, interaction.channel)
            return

        # ====================================================
        # ENTRAR NA RESERVA
        # ====================================================
        if self.tipo == "reserva":
            if self_user in evento.get("presentes", {}):
                if usuario_esta_em_reserva(evento, self_user):
                    await interaction.response.send_message(
                        "⚠️ Você já está na lista de reservas.",
                        ephemeral=True
                    )
                    return

                await interaction.response.send_message(
                    "⚠️ Você já faz parte da PT. Use '❌ Não vou' para sair da PT.",
                    ephemeral=True
                )
                return

            if self_user in evento.get("reservas", {}):
                await interaction.response.send_message(
                    "⚠️ Você já está na lista de reservas.",
                    ephemeral=True
                )
                return

            evento.setdefault("nao_vou", {}).pop(self_user, None)
            evento.setdefault("reservas", {})[self_user] = {
                "classe": escolha,
                "horario": agora.isoformat()
            }

            salvar_eventos()

            await interaction.response.send_message(
                (
                    f"🟡 Você entrou na **RESERVA** como **{escolha}** às "
                    f"**{agora.strftime('%H:%M')}**.\n\n"
                    "📋 Você ficará no final da fila de reservas."
                ),
                ephemeral=True
            )

            await atualizar_mensagem(self.evento_id, interaction.channel)
            return

        # ====================================================
        # NÃO VOU
        # ====================================================
        if self_user in evento.get("nao_vou", {}):
            await interaction.response.send_message(
                "⚠️ Você já está registrado como **Não vou**.",
                ephemeral=True
            )
            return

        dados_atuais = obter_dados_usuario(evento, self_user)
        classe_final = (
            dados_atuais["classe"]
            if dados_atuais is not None
            else escolha
        )

        pt_antes, _ = separar_participantes(evento)
        ids_pt_antes = {p["user_id"] for p in pt_antes}

        # Remove da PT/presença ou da reserva manual.
        evento.setdefault("presentes", {}).pop(self_user, None)
        evento.setdefault("reservas", {}).pop(self_user, None)

        evento.setdefault("nao_vou", {})[self_user] = {
            "classe": classe_final,
            "horario": agora.isoformat()
        }

        salvar_eventos()

        proximo_promovido = None
        if len(pt_antes) > len(separar_participantes(evento)[0]):
            proximo_promovido = promover_proxima_reserva(evento)

        promovidos = [proximo_promovido] if proximo_promovido else []

        await interaction.response.send_message(
            (
                f"❌ Sua ausência foi registrada às "
                f"**{agora.strftime('%H:%M')}**.\n"
                f"Classe: **{classe_final}**"
            ),
            ephemeral=True
        )

        if promovidos:
            mencoes = " ".join(
                f"<@{p['user_id']}>"
                for p in promovidos
            )

            await interaction.channel.send(
                (
                    f"🔄 **VAGA DISPONÍVEL!**\n\n"
                    f"❌ <@{self_user}> deixou a PT.\n\n"
                    f"🟢 **Novo membro da PT:**\n"
                    f"{mencoes}\n\n"
                    f"⚔️ **Você assumiu a vaga!**"
                )
            )

        await atualizar_mensagem(self.evento_id, interaction.channel)


# ============================================================
# VIEW SELEÇÃO DE CLASSE
# ============================================================

class ClasseView(discord.ui.View):

    def __init__(self, evento_id, user_id, tipo):
        super().__init__(timeout=30)

        self.add_item(
            ClasseSelect(
                evento_id,
                user_id,
                tipo
            )
        )


# ============================================================
# BOTÃO DO EVENTO
# ============================================================

class EventoButton(discord.ui.Button):

    def __init__(self, evento_id, tipo, label, style, emoji):
        self.evento_id = str(evento_id)
        self.tipo = tipo

        super().__init__(
            label=label,
            style=style,
            emoji=emoji,
            custom_id=f"evento:{self.evento_id}:{tipo}"
        )

    async def callback(self, interaction):
        evento = obter_evento(self.evento_id)

        if not evento:
            await interaction.response.send_message(
                "❌ Este evento não existe mais.",
                ephemeral=True
            )
            return

        user_id = str(interaction.user.id)

        # ----------------------------------------------------
        # MARCAR PRESENÇA
        # ----------------------------------------------------
        if self.tipo == "presente":
            if user_id in evento.get("presentes", {}):
                await interaction.response.send_message(
                    "⚠️ Você já está confirmado neste evento.",
                    ephemeral=True
                )
                return

            # Quem estava como NÃO VOU volta mantendo a classe.
            if user_id in evento.get("nao_vou", {}):
                dados = normalizar_participante(
                    user_id,
                    evento["nao_vou"][user_id]
                )
                classe = dados["classe"]
                agora = horario_atual()

                evento.setdefault("nao_vou", {}).pop(user_id, None)
                evento.setdefault("reservas", {}).pop(user_id, None)
                evento.setdefault("presentes", {})[user_id] = {
                    "classe": classe,
                    "horario": agora.isoformat()
                }

                salvar_eventos()

                await interaction.response.send_message(
                    (
                        f"✅ Você voltou para a lista como **{classe}** às "
                        f"**{agora.strftime('%H:%M')}**.\n\n"
                        "📋 Você entrou novamente no final da fila."
                    ),
                    ephemeral=True
                )

                await atualizar_mensagem(self.evento_id, interaction.channel)
                return

            # Quem estava em reserva manual vai para a fila normal.
            if user_id in evento.get("reservas", {}):
                dados = normalizar_participante(
                    user_id,
                    evento["reservas"][user_id]
                )
                classe = dados["classe"]
                agora = horario_atual()

                evento.setdefault("reservas", {}).pop(user_id, None)
                evento.setdefault("presentes", {})[user_id] = {
                    "classe": classe,
                    "horario": agora.isoformat()
                }

                salvar_eventos()

                await interaction.response.send_message(
                    (
                        f"✅ Você saiu da reserva e entrou na fila de presença "
                        f"como **{classe}** às **{agora.strftime('%H:%M')}**."
                    ),
                    ephemeral=True
                )

                await atualizar_mensagem(self.evento_id, interaction.channel)
                return

            await interaction.response.send_message(
                "Selecione sua classe:",
                view=ClasseView(
                    self.evento_id,
                    user_id,
                    "presente"
                ),
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # ENTRAR NA RESERVA
        # ----------------------------------------------------
        if self.tipo == "reserva":
            if user_id in evento.get("presentes", {}):
                if usuario_esta_em_reserva(evento, user_id):
                    await interaction.response.send_message(
                        "⚠️ Você já está na lista de reservas.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "⚠️ Você já faz parte da PT. Use '❌ Não vou' para sair.",
                        ephemeral=True
                    )
                return

            if user_id in evento.get("reservas", {}):
                await interaction.response.send_message(
                    "⚠️ Você já está na lista de reservas.",
                    ephemeral=True
                )
                return

            if user_id in evento.get("nao_vou", {}):
                dados = normalizar_participante(
                    user_id,
                    evento["nao_vou"][user_id]
                )
                classe = dados["classe"]
                agora = horario_atual()

                evento.setdefault("nao_vou", {}).pop(user_id, None)
                evento.setdefault("reservas", {})[user_id] = {
                    "classe": classe,
                    "horario": agora.isoformat()
                }

                salvar_eventos()

                await interaction.response.send_message(
                    (
                        f"🟡 Você entrou na **RESERVA** como **{classe}** às "
                        f"**{agora.strftime('%H:%M')}**.\n\n"
                        "📋 Você entrou no final da fila de reservas."
                    ),
                    ephemeral=True
                )

                await atualizar_mensagem(self.evento_id, interaction.channel)
                return

            await interaction.response.send_message(
                "Selecione sua classe para entrar na reserva:",
                view=ClasseView(
                    self.evento_id,
                    user_id,
                    "reserva"
                ),
                ephemeral=True
            )
            return

        # ----------------------------------------------------
        # NÃO VOU
        # ----------------------------------------------------
        if user_id in evento.get("nao_vou", {}):
            await interaction.response.send_message(
                "⚠️ Você já está registrado como **Não vou**.",
                ephemeral=True
            )
            return

        if user_id in evento.get("presentes", {}):
            dados = normalizar_participante(
                user_id,
                evento["presentes"][user_id]
            )
            classe = dados["classe"]
        elif user_id in evento.get("reservas", {}):
            dados = normalizar_participante(
                user_id,
                evento["reservas"][user_id]
            )
            classe = dados["classe"]
        else:
            await interaction.response.send_message(
                "Selecione sua classe:",
                view=ClasseView(
                    self.evento_id,
                    user_id,
                    "nao_vou"
                ),
                ephemeral=True
            )
            return

        agora = horario_atual()
        pt_antes, _ = separar_participantes(evento)
        ids_pt_antes = {p["user_id"] for p in pt_antes}

        evento.setdefault("presentes", {}).pop(user_id, None)
        evento.setdefault("reservas", {}).pop(user_id, None)
        evento.setdefault("nao_vou", {})[user_id] = {
            "classe": classe,
            "horario": agora.isoformat()
        }

        salvar_eventos()

        proximo_promovido = None
        if len(pt_antes) > len(separar_participantes(evento)[0]):
            proximo_promovido = promover_proxima_reserva(evento)

        promovidos = [proximo_promovido] if proximo_promovido else []

        await interaction.response.send_message(
            (
                f"❌ Sua ausência foi registrada às "
                f"**{agora.strftime('%H:%M')}**.\n"
                f"Classe: **{classe}**"
            ),
            ephemeral=True
        )

        if promovidos:
            mencoes = " ".join(
                f"<@{p['user_id']}>"
                for p in promovidos
            )

            await interaction.channel.send(
                (
                    f"🔄 **VAGA DISPONÍVEL!**\n\n"
                    f"❌ <@{user_id}> deixou a PT.\n\n"
                    f"🟢 **Novo membro da PT:**\n"
                    f"{mencoes}\n\n"
                    f"⚔️ **Você assumiu a vaga!**"
                )
            )

        await atualizar_mensagem(self.evento_id, interaction.channel)


# ============================================================
# VIEW PRINCIPAL DO EVENTO
# ============================================================

class PresencaView(discord.ui.View):

    def __init__(self, evento_id):
        super().__init__(timeout=None)
        self.evento_id = str(evento_id)

        self.add_item(
            EventoButton(
                evento_id,
                "presente",
                "Marcar Presença",
                discord.ButtonStyle.green,
                "✅"
            )
        )

        self.add_item(
            EventoButton(
                evento_id,
                "reserva",
                "Entrar na Reserva",
                discord.ButtonStyle.blurple,
                "🟡"
            )
        )

        self.add_item(
            EventoButton(
                evento_id,
                "nao_vou",
                "Não vou",
                discord.ButtonStyle.red,
                "❌"
            )
        )


# ============================================================
# REGISTRAR VIEWS PERSISTENTES
# ============================================================

async def registrar_views_persistentes():
    """
    Registra as Views persistentes de todos os eventos existentes.

    O message_id é informado quando disponível para associar a View
    diretamente ao painel antigo correspondente.
    """
    registrados = 0

    for evento_id, evento in list(eventos.items()):
        try:
            mensagem_id = evento.get("mensagem_id")

            if mensagem_id:
                bot.add_view(
                    PresencaView(evento_id),
                    message_id=int(mensagem_id)
                )
                print(
                    f"🔘 View registrada: evento={evento_id} | "
                    f"mensagem={mensagem_id}"
                )
            else:
                bot.add_view(PresencaView(evento_id))
                print(
                    f"🔘 View registrada: evento={evento_id} | "
                    f"sem message_id"
                )

            registrados += 1

        except Exception as e:
            print(
                f"⚠️ Não foi possível registrar a View do evento "
                f"{evento_id}: {e}"
            )

    print(
        f"🔘 Views persistentes registradas: "
        f"{registrados}/{len(eventos)}."
    )


async def atualizar_paineis_ao_iniciar():
    """
    Recoloca os três botões nos eventos já existentes.
    Isso também faz com que eventos antigos recebam o novo botão
    "Entrar na Reserva" e usem o ID correto do evento.
    """
    for evento_id in list(eventos):
        try:
            await atualizar_mensagem(evento_id)
        except Exception as e:
            print(
                f"⚠️ Erro ao reconstruir painel do evento "
                f"{evento_id}: {e}"
            )


# ============================================================
# COMANDOS DE CRIAÇÃO DE EVENTO
# ============================================================

async def criar_evento_do_tipo(ctx, argumentos, tipo):
    """
    Fluxo de criação compartilhado por todos os comandos.
    O que muda entre eles é apenas o preset visual em TIPOS_EVENTO.
    """
    preset = TIPOS_EVENTO.get(tipo, TIPOS_EVENTO[TIPO_PADRAO])
    comando = ctx.invoked_with or "criar_evento"
    nome_padrao = preset.get("nome_padrao")

    partes = (argumentos or "").strip().rsplit(" ", 2)

    if len(partes) == 3:
        nome_evento = partes[0].strip()
        data = partes[1]
        horario = partes[2]
    elif len(partes) == 2 and nome_padrao:
        # Tipos com nome próprio aceitam só a data e o horário.
        nome_evento = nome_padrao
        data = partes[0]
        horario = partes[1]
    else:
        nome_evento = ""
        data = ""
        horario = ""

    if not nome_evento or not data or not horario:
        linhas = ["❌ Formato incorreto.", "", "Use:"]

        if nome_padrao:
            linhas.append(
                f"`!{comando} DD/MM/AAAA HH:MM` — cria **{nome_padrao}**"
            )
            linhas.append(
                f"`!{comando} Nome do Evento DD/MM/AAAA HH:MM` — com outro nome"
            )
            linhas.append("")
            linhas.append("Exemplo:")
            linhas.append(f"`!{comando} 15/09/2026 20:00`")
        else:
            linhas.append(f"`!{comando} Nome do Evento DD/MM/AAAA HH:MM`")
            linhas.append("")
            linhas.append("Exemplo:")
            linhas.append(f"`!{comando} Guerra do Emperium 15/09/2026 20:00`")

        await ctx.send("\n".join(linhas))
        return

    data_hora = converter_data_evento(data, horario)

    if data_hora is None:
        await ctx.send(
            (
                "❌ Data ou horário inválido.\n"
                "Use: `DD/MM/AAAA HH:MM`"
            )
        )
        return

    if data_hora <= horario_atual():
        await ctx.send("❌ O horário do evento precisa ser no futuro.")
        return

    # Permite o MESMO NOME em datas/horários diferentes.
    # Só bloqueia uma duplicação exata de nome + data + horário.
    if encontrar_evento_por_nome_data(nome_evento, data, horario):
        await ctx.send(
            (
                "⚠️ Já existe um evento com o mesmo nome, data e horário.\n"
                "Você pode criar outro com o mesmo nome em outra data/horário."
            )
        )
        return

    evento_id = gerar_evento_id()

    eventos[evento_id] = {
        "evento_id": evento_id,
        "nome_evento": nome_evento,
        "tipo": tipo,
        "presentes": {},
        "reservas": {},
        "nao_vou": {},
        "horario_inicio": data_hora.isoformat(),
        "canal_id": ctx.channel.id,
        "mensagem_id": None,
        "aviso_10_minutos": False
    }

    salvar_eventos()

    evento = eventos[evento_id]
    mensagem = await ctx.send(
        embed=criar_embed_evento(evento),
        view=PresencaView(evento_id)
    )

    eventos[evento_id]["mensagem_id"] = mensagem.id
    salvar_eventos()

    await ctx.send(
        (
            f"✅ **{preset['rotulo']}** — **{nome_evento}** criado para "
            f"**{data_hora.strftime('%d/%m/%Y às %H:%M')}**.\n"
            f"🆔 ID do evento: `{evento_id}`  ·  apague com `!apagar_evento {evento_id}`\n"
            f"🟢 A PT terá até {LIMITE_PT} membros.\n"
            "🟡 O botão **Entrar na Reserva** permite entrar diretamente "
            "na fila de reservas."
        ),
        delete_after=10
    )


@bot.command(name="criar_evento")
async def criar_evento(ctx, *, argumentos=""):
    await criar_evento_do_tipo(ctx, argumentos, "padrao")


@bot.command(name="criar_esgoto")
async def criar_esgoto(ctx, *, argumentos=""):
    await criar_evento_do_tipo(ctx, argumentos, "esgoto")


@bot.command(name="criar_torre")
async def criar_torre(ctx, *, argumentos=""):
    await criar_evento_do_tipo(ctx, argumentos, "torre")


# ============================================================
# COMANDO LISTA
# ============================================================

@bot.command(name="lista")
async def lista(ctx, *, argumentos):
    partes = argumentos.rsplit(" ", 2)

    evento_alvo = None

    # Permite !lista Nome DD/MM/AAAA HH:MM quando existem nomes repetidos.
    if len(partes) == 3:
        candidato = encontrar_evento_por_nome_data(
            partes[0],
            partes[1],
            partes[2]
        )
        if candidato:
            evento_alvo = candidato

    if evento_alvo:
        _, evento = evento_alvo
        await ctx.send(embed=criar_embed_evento(evento, "📋 Lista"))
        return

    nome_evento = argumentos.strip()
    encontrados = eventos_por_nome(nome_evento)

    if not encontrados:
        await ctx.send("❌ Evento não encontrado.")
        return

    if len(encontrados) == 1:
        _, evento = encontrados[0]
        await ctx.send(embed=criar_embed_evento(evento, "📋 Lista"))
        return

    linhas = [
        f"**{i}.** {evento.get('nome_evento', 'Evento')} — "
        f"{formatar_data_horario(evento.get('horario_inicio', ''))}"
        for i, (_, evento) in enumerate(encontrados, start=1)
    ]

    await ctx.send(
        (
            f"⚠️ Existem **{len(encontrados)} eventos** com o nome "
            f"**{nome_evento}**.\n\n"
            + "\n".join(linhas)
            + "\n\n"
            "Para ver um específico, use:\n"
            "`!lista Nome do Evento DD/MM/AAAA HH:MM`"
        )
    )


# ============================================================
# COMANDO APAGAR EVENTO
# ============================================================

def listar_eventos_com_id(limite=15):
    """Eventos cadastrados com o ID de cada um, do mais próximo ao mais distante."""
    if not eventos:
        return "*Nenhum evento cadastrado no momento.*"

    ordenados = sorted(
        eventos.items(),
        key=lambda item: item[1].get("horario_inicio", "9999")
    )

    linhas = []

    for evento_id, evento in ordenados[:limite]:
        linhas.append(
            f"`{evento_id}`  —  {evento.get('nome_evento', 'Evento')}  ·  "
            f"{formatar_data_horario(evento.get('horario_inicio', ''))}"
        )

    if len(ordenados) > limite:
        linhas.append(f"*… e mais {len(ordenados) - limite} evento(s).*")

    return "\n".join(linhas)


@bot.command(name="apagar_evento")
async def apagar_evento(ctx, *, argumentos=""):
    evento_id = normalizar_id_evento(argumentos)
    evento = obter_evento(evento_id) if evento_id else None

    if evento is None:
        if evento_id:
            aviso = f"❌ Não existe nenhum evento com o ID `{evento_id}`."
        else:
            aviso = "❌ Informe o ID do evento."

        await ctx.send(
            aviso
            + "\n\nUse: `!apagar_evento 0427`"
            + "\nO ID fica no rodapé do painel do evento."
            + "\n\n**Eventos cadastrados:**\n"
            + listar_eventos_com_id()
        )
        return

    nome_evento = evento.get("nome_evento", "Evento")
    horario_inicio = evento.get("horario_inicio", "")

    del eventos[evento_id]
    salvar_eventos()

    await ctx.send(
        (
            f"🗑️ Evento **{nome_evento}** (ID `{evento_id}`) de "
            f"**{formatar_data_horario(horario_inicio)}** removido."
        )
    )


# ============================================================
# DIAGNÓSTICO DAS INTERAÇÕES DOS BOTÕES
# ============================================================

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = (interaction.data or {}).get("custom_id")

        print(
            f"🧩 INTERAÇÃO RECEBIDA | "
            f"usuário={interaction.user} | "
            f"custom_id={custom_id}"
        )


# ============================================================
# SETUP DO BOT
# ============================================================

async def setup_hook():
    """
    Registra as Views persistentes antes da conexão completa
    com o Gateway.
    """
    await registrar_views_persistentes()
    print("🔘 Views persistentes registradas no setup_hook.")


bot.setup_hook = setup_hook


# ============================================================
# BOT ONLINE
# ============================================================

BOT_INICIALIZADO = False


@bot.event
async def on_ready():
    global BOT_INICIALIZADO

    print(f"🤖 Bot online como {bot.user}")

    # O Discord pode chamar on_ready novamente após uma reconexão.
    # Evitamos reconstruir os painéis repetidamente.
    if BOT_INICIALIZADO:
        return

    BOT_INICIALIZADO = True

    await sincronizar_emojis_classes()

    # Remove primeiro os eventos que já passaram de 2 horas.
    await finalizar_eventos_expirados()

    # Reconstroi os painéis dos eventos que ainda estão ativos/futuros.
    await atualizar_paineis_ao_iniciar()

    if not verificar_eventos.is_running():
        verificar_eventos.start()
        print("⏰ Sistema de avisos e finalização de eventos iniciado.")


# ============================================================
# INICIAR BOT
# ============================================================

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError(
        "❌ A variável de ambiente TOKEN não foi encontrada na Railway."
    )

bot.run(TOKEN)
