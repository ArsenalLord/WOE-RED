import os
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands
import json
from datetime import datetime
from zoneinfo import ZoneInfo

# ============================================================
# FLASK
# ============================================================

app = Flask('')

@app.route('/')
def home():
    return "Estou vivo!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()


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
    with open(ARQUIVO_EVENTOS, "r", encoding="utf-8") as f:
        eventos = json.load(f)
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
    "Desordeiro"
]

LIMITE_PT = 12

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


# ============================================================
# SALVAR EVENTOS
# ============================================================

def salvar_eventos():
    with open(ARQUIVO_EVENTOS, "w", encoding="utf-8") as f:
        json.dump(
            eventos,
            f,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# HORÁRIO
# ============================================================

def horario_atual():
    return datetime.now(FUSO_HORARIO)


def formatar_horario(data_iso):
    try:
        data = datetime.fromisoformat(data_iso)
        return data.strftime("%H:%M")
    except:
        return "--:--"


# ============================================================
# ORGANIZAR PARTICIPANTES
# ============================================================

def ordenar_participantes(dados):
    """
    Ordena os jogadores pelo horário em que confirmaram.
    """

    participantes = []

    for user_id, dados_usuario in dados.items():

        # Novo formato
        if isinstance(dados_usuario, dict):

            classe = dados_usuario.get("classe", "Sem classe")
            horario = dados_usuario.get("horario", "")

        # Compatibilidade com eventos antigos
        else:

            classe = dados_usuario
            horario = ""

        participantes.append({
            "user_id": user_id,
            "classe": classe,
            "horario": horario
        })

    participantes.sort(
        key=lambda x: x["horario"] or "9999"
    )

    return participantes


# ============================================================
# SEPARAR PT FORMADA E RESERVAS
# ============================================================

def separar_participantes(evento):

    confirmados = ordenar_participantes(
        evento.get("presentes", {})
    )

    pt_formada = confirmados[:LIMITE_PT]

    reservas = confirmados[LIMITE_PT:]

    return pt_formada, reservas


# ============================================================
# FORMATAR PARTICIPANTES
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

    for i, participante in enumerate(lista, start=1):

        linhas.append(
            f"**{i}.** {formatar_participante(participante)}"
        )

    return "\n".join(linhas)


# ============================================================
# ATUALIZAR MENSAGEM DO EVENTO
# ============================================================

async def atualizar_mensagem(channel, nome_evento):

    if channel is None:
        return

    async for msg in channel.history(limit=100):

        if (
            msg.embeds
            and msg.embeds[0].title == f"📅 Evento: {nome_evento}"
        ):

            evento = eventos.get(
                nome_evento,
                {
                    "presentes": {},
                    "nao_vou": {}
                }
            )

            pt_formada, reservas = separar_participantes(evento)

            embed = discord.Embed(
                title=f"📅 Evento: {nome_evento}",
                color=0x00BFFF
            )

            # ------------------------------------------------
            # PT FORMADA
            # ------------------------------------------------

            embed.add_field(
                name=f"🟢 PT FORMADA — {len(pt_formada)}/{LIMITE_PT}",
                value=formatar_lista_participantes(pt_formada),
                inline=False
            )

            # ------------------------------------------------
            # RESERVAS
            # ------------------------------------------------

            embed.add_field(
                name=f"🟡 RESERVAS — {len(reservas)}",
                value=formatar_lista_participantes(reservas),
                inline=False
            )

            # ------------------------------------------------
            # NÃO VÃO
            # ------------------------------------------------

            ausentes = ordenar_participantes(
                evento.get("nao_vou", {})
            )

            embed.add_field(
                name=f"❌ NÃO VÃO — {len(ausentes)}",
                value=formatar_lista_participantes(ausentes),
                inline=False
            )

            embed.set_footer(
                text="Os 12 primeiros confirmados formam a PT. Os demais ficam como reserva."
            )

            await msg.edit(
                embed=embed,
                view=PresencaView(nome_evento)
            )

            break


# ============================================================
# SELECT DE CLASSE
# ============================================================

class ClasseSelect(discord.ui.Select):

    def __init__(self, nome_evento, user_id, tipo):

        self.nome_evento = nome_evento
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

    async def callback(self, interaction: discord.Interaction):

        escolha = self.values[0]

        if self.nome_evento not in eventos:

            eventos[self.nome_evento] = {
                "presentes": {},
                "nao_vou": {}
            }

        evento = eventos[self.nome_evento]

        # ====================================================
        # CONFIRMOU PRESENÇA
        # ====================================================

        if self.tipo == "presente":

            agora = horario_atual()

            evento["presentes"][self.user_id] = {
                "classe": escolha,
                "horario": agora.isoformat()
            }

            evento["nao_vou"].pop(
                self.user_id,
                None
            )

            await interaction.response.send_message(
                f"✅ Presença confirmada como **{escolha}** às **{agora.strftime('%H:%M')}**.",
                ephemeral=True
            )

        # ====================================================
        # NÃO VAI
        # ====================================================

        else:

            # Mantém horário caso seja necessário ordenar
            agora = horario_atual()

            evento["nao_vou"][self.user_id] = {
                "classe": escolha,
                "horario": agora.isoformat()
            }

            evento["presentes"].pop(
                self.user_id,
                None
            )

            await interaction.response.send_message(
                f"❌ Ausência registrada como **{escolha}**.",
                ephemeral=True
            )

        salvar_eventos()

        await atualizar_mensagem(
            interaction.channel,
            self.nome_evento
        )


# ============================================================
# VIEW DA SELEÇÃO DE CLASSE
# ============================================================

class ClasseView(discord.ui.View):

    def __init__(self, nome_evento, user_id, tipo):

        super().__init__(timeout=30)

        self.add_item(
            ClasseSelect(
                nome_evento,
                user_id,
                tipo
            )
        )


# ============================================================
# BOTÕES DO EVENTO
# ============================================================

class PresencaView(discord.ui.View):

    def __init__(self, nome_evento):

        super().__init__(timeout=None)

        self.nome_evento = nome_evento

    @discord.ui.button(
        label="✅ Marcar Presença",
        style=discord.ButtonStyle.green
    )
    async def marcar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "Selecione sua classe:",
            view=ClasseView(
                self.nome_evento,
                interaction.user.id,
                "presente"
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="❌ Não vou",
        style=discord.ButtonStyle.red
    )
    async def nao_vou(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "Selecione sua classe:",
            view=ClasseView(
                self.nome_evento,
                interaction.user.id,
                "nao_vou"
            ),
            ephemeral=True
        )


# ============================================================
# COMANDO CRIAR EVENTO
# ============================================================

@bot.command(name="criar_evento")
async def criar_evento(ctx, *, nome_evento):

    if nome_evento in eventos:

        await ctx.send(
            "⚠️ Este evento já existe."
        )

        return

    eventos[nome_evento] = {
        "presentes": {},
        "nao_vou": {}
    }

    salvar_eventos()

    embed = discord.Embed(
        title=f"📅 Evento: {nome_evento}",
        color=0x00BFFF
    )

    embed.add_field(
        name=f"🟢 PT FORMADA — 0/{LIMITE_PT}",
        value="Ninguém",
        inline=False
    )

    embed.add_field(
        name="🟡 RESERVAS — 0",
        value="Ninguém",
        inline=False
    )

    embed.add_field(
        name="❌ NÃO VÃO — 0",
        value="Ninguém",
        inline=False
    )

    embed.set_footer(
        text="Os 12 primeiros confirmados formam a PT. Os demais ficam como reserva."
    )

    await ctx.send(
        embed=embed,
        view=PresencaView(nome_evento)
    )


# ============================================================
# COMANDO LISTA
# ============================================================

@bot.command(name="lista")
async def lista(ctx, *, nome_evento):

    if nome_evento not in eventos:

        await ctx.send(
            "❌ Evento não encontrado."
        )

        return

    evento = eventos[nome_evento]

    pt_formada, reservas = separar_participantes(evento)

    ausentes = ordenar_participantes(
        evento.get("nao_vou", {})
    )

    embed = discord.Embed(
        title=f"📋 Lista de {nome_evento}",
        color=0x1E90FF
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

    await ctx.send(embed=embed)


# ============================================================
# COMANDO APAGAR EVENTO
# ============================================================

@bot.command(name="apagar_evento")
async def apagar_evento(ctx, *, nome_evento):

    if nome_evento not in eventos:

        await ctx.send(
            "❌ Evento não encontrado."
        )

        return

    del eventos[nome_evento]

    salvar_eventos()

    await ctx.send(
        f"🗑️ Evento **{nome_evento}** removido."
    )


# ============================================================
# BOT ONLINE
# ============================================================

@bot.event
async def on_ready():

    print(
        f"🤖 Bot online como {bot.user}"
    )


# ============================================================
# INICIAR BOT
# ============================================================

bot.run(
    os.getenv('TOKEN')
)
