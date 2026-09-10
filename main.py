import os
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4

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

CLASSES_FIXAS = [
    "Mestre",
    "LK",
    "Pala",
    "Cross",
    "Sumo",
    "Cigana",
    "Menestrel",
    "Professor",
    "Arquimago",
    "SL",
    "Sniper",
    "MestreFerreiro",
    "Criador",
    "Desordeiro",
    "TK",
    "Guns"
]

LIMITE_PT = 12
FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


# ============================================================
# MIGRAÇÃO / COMPATIBILIDADE
# ============================================================

def gerar_evento_id():
    return uuid4().hex


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
            evento["evento_id"] = evento_id
            evento.setdefault("reservas", {})
            evento.setdefault("presentes", {})
            evento.setdefault("nao_vou", {})
            novos[evento_id] = evento
            continue

        # Formato antigo: a chave era o nome do evento.
        evento_id = gerar_evento_id()
        while evento_id in novos:
            evento_id = gerar_evento_id()

        evento["evento_id"] = evento_id
        evento["nome_evento"] = str(chave)
        evento.setdefault("presentes", {})
        evento.setdefault("nao_vou", {})
        evento.setdefault("reservas", {})
        evento.setdefault("mensagem_id", None)
        evento.setdefault("canal_id", None)
        evento.setdefault("aviso_10_minutos", False)

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

def formatar_participante(participante):
    return (
        f"<@{participante['user_id']}> "
        f"({participante['classe']}) "
        f"— 🕐 {formatar_horario(participante['horario'])}"
    )


def formatar_lista_participantes(lista):
    if not lista:
        return "Ninguém"

    linhas = []

    for numero, participante in enumerate(lista, start=1):
        linhas.append(
            f"**{numero}.** {formatar_participante(participante)}"
        )

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


# ============================================================
# CRIAR EMBED DO EVENTO
# ============================================================

def criar_embed_evento(evento, titulo_prefixo="📅 Evento"):
    nome_evento = evento.get("nome_evento", "Evento")
    horario_inicio = evento.get("horario_inicio")

    pt_formada, reservas = separar_participantes(evento)
    ausentes = ordenar_participantes(evento.get("nao_vou", {}))

    embed = discord.Embed(
        title=f"{titulo_prefixo}: {nome_evento}",
        color=0x00BFFF
    )

    if horario_inicio:
        embed.add_field(
            name="⏰ Início",
            value=formatar_data_horario(horario_inicio),
            inline=False
        )

    embed.add_field(
        name=f"🟢 PT FORMADA — {len(pt_formada)}/{LIMITE_PT}",
        value=formatar_lista_participantes(pt_formada),
        inline=False
    )

    embed.add_field(
        name=f"🟡 RESERVAS — {len(reservas)}",
        value=formatar_lista_participantes(reservas),
        inline=False
    )

    embed.add_field(
        name=f"❌ NÃO VÃO — {len(ausentes)}",
        value=formatar_lista_participantes(ausentes),
        inline=False
    )

    embed.set_footer(
        text=(
            f"Os {LIMITE_PT} primeiros confirmados formam a PT. "
            "Quem usar 'Entrar na Reserva' entra diretamente na fila de reserva."
        )
    )

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

                titulo = msg.embeds[0].title or ""
                if titulo != f"📅 Evento: {nome_evento}":
                    continue

                # Se houver mais de um evento com o mesmo nome, confira a data.
                if horario_inicio:
                    encontrou_horario = any(
                        field.name == "⏰ Início"
                        and field.value == formatar_data_horario(horario_inicio)
                        for field in msg.embeds[0].fields
                    )
                    if not encontrou_horario:
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
# LOOP DE VERIFICAÇÃO
# ============================================================

@tasks.loop(seconds=30)
async def verificar_eventos():
    await verificar_eventos_10_minutos()


# ============================================================
# SELECT DE CLASSE
# ============================================================

class ClasseSelect(discord.ui.Select):

    def __init__(self, evento_id, user_id, tipo):
        self.evento_id = str(evento_id)
        self.user_id = str(user_id)
        self.tipo = tipo

        options = [
            discord.SelectOption(label=classe)
            for classe in CLASSES_FIXAS
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
    for evento_id in eventos:
        try:
            bot.add_view(PresencaView(evento_id))
        except Exception as e:
            print(
                f"⚠️ Não foi possível registrar a view do evento "
                f"{evento_id}: {e}"
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
# COMANDO CRIAR EVENTO
# ============================================================

@bot.command(name="criar_evento")
async def criar_evento(ctx, *, argumentos):
    partes = argumentos.rsplit(" ", 2)

    if len(partes) != 3:
        await ctx.send(
            (
                "❌ Formato incorreto.\n\n"
                "Use:\n"
                "`!criar_evento Nome do Evento DD/MM/AAAA HH:MM`\n\n"
                "Exemplo:\n"
                "`!criar_evento Torre 08/09/2026 20:00`"
            )
        )
        return

    nome_evento = partes[0].strip()
    data = partes[1]
    horario = partes[2]

    if not nome_evento:
        await ctx.send("❌ O nome do evento não pode ficar vazio.")
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
            f"✅ Evento **{nome_evento}** criado para "
            f"**{data_hora.strftime('%d/%m/%Y às %H:%M')}**.\n"
            "🟢 A PT terá até 12 membros.\n"
            "🟡 O botão **Entrar na Reserva** permite entrar diretamente na fila de reservas."
        ),
        delete_after=10
    )


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

@bot.command(name="apagar_evento")
async def apagar_evento(ctx, *, argumentos):
    partes = argumentos.rsplit(" ", 2)

    evento_alvo = None

    if len(partes) == 3:
        evento_alvo = encontrar_evento_por_nome_data(
            partes[0],
            partes[1],
            partes[2]
        )

    if evento_alvo:
        evento_id, evento = evento_alvo
        nome_evento = evento.get("nome_evento", "Evento")
        horario_inicio = evento.get("horario_inicio", "")

        del eventos[evento_id]
        salvar_eventos()

        await ctx.send(
            (
                f"🗑️ Evento **{nome_evento}** de "
                f"**{formatar_data_horario(horario_inicio)}** removido."
            )
        )
        return

    nome_evento = argumentos.strip()
    encontrados = eventos_por_nome(nome_evento)

    if not encontrados:
        await ctx.send("❌ Evento não encontrado.")
        return

    if len(encontrados) > 1:
        linhas = [
            f"**{i}.** {formatar_data_horario(evento.get('horario_inicio', ''))}"
            for i, (_, evento) in enumerate(encontrados, start=1)
        ]

        await ctx.send(
            (
                f"⚠️ Existem vários eventos chamados **{nome_evento}**.\n\n"
                + "\n".join(linhas)
                + "\n\n"
                "Informe a data e o horário para apagar apenas um:\n"
                "`!apagar_evento Nome do Evento DD/MM/AAAA HH:MM`"
            )
        )
        return

    evento_id, evento = encontrados[0]
    horario_inicio = evento.get("horario_inicio", "")

    del eventos[evento_id]
    salvar_eventos()

    await ctx.send(
        (
            f"🗑️ Evento **{nome_evento}** de "
            f"**{formatar_data_horario(horario_inicio)}** removido."
        )
    )


# ============================================================
# BOT ONLINE
# ============================================================

@bot.event
async def on_ready():
    print(f"🤖 Bot online como {bot.user}")

    await registrar_views_persistentes()
    await atualizar_paineis_ao_iniciar()

    if not verificar_eventos.is_running():
        verificar_eventos.start()
        print("⏰ Sistema de avisos de eventos iniciado.")


# ============================================================
# INICIAR BOT
# ============================================================

bot.run(os.getenv("TOKEN"))
