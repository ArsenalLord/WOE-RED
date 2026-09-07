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
    "Guns"
    "TK"
]

LIMITE_PT = 12

# Horário de Brasília
FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


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


# ============================================================
# HORÁRIO ATUAL
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
# NORMALIZAR PARTICIPANTES
# ============================================================

def normalizar_participante(user_id, dados):

    """
    Permite que eventos antigos continuem funcionando.

    Formato antigo:
        "123456": "LK"

    Formato novo:
        "123456": {
            "classe": "LK",
            "horario": "2026-09-07T16:00:00..."
        }
    """

    if isinstance(dados, dict):

        return {
            "user_id": str(user_id),
            "classe": dados.get(
                "classe",
                "Sem classe"
            ),
            "horario": dados.get(
                "horario",
                ""
            )
        }

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

    for user_id, dados in dados.items():

        participante = normalizar_participante(
            user_id,
            dados
        )

        participantes.append(
            participante
        )

    # Quem não possui horário fica no final
    participantes.sort(
        key=lambda x: x["horario"] or "9999-99-99"
    )

    return participantes


# ============================================================
# SEPARAR PT E RESERVAS
# ============================================================

def separar_participantes(evento):

    confirmados = ordenar_participantes(
        evento.get(
            "presentes",
            {}
        )
    )

    pt_formada = confirmados[:LIMITE_PT]

    reservas = confirmados[LIMITE_PT:]

    return pt_formada, reservas


# ============================================================
# FORMATAR PARTICIPANTE
# ============================================================

def formatar_participante(participante):

    return (
        f"<@{participante['user_id']}> "
        f"({participante['classe']}) "
        f"— 🕐 {formatar_horario(participante['horario'])}"
    )


# ============================================================
# FORMATAR LISTA
# ============================================================

def formatar_lista_participantes(lista):

    if not lista:

        return "Ninguém"

    linhas = []

    for numero, participante in enumerate(
        lista,
        start=1
    ):

        linhas.append(
            f"**{numero}.** "
            f"{formatar_participante(participante)}"
        )

    return "\n".join(linhas)


# ============================================================
# ATUALIZAR MENSAGEM DO EVENTO
# ============================================================

async def atualizar_mensagem(
    channel,
    nome_evento
):

    if channel is None:

        return

    try:

        async for msg in channel.history(
            limit=100
        ):

            if (
                msg.embeds
                and msg.embeds[0].title
                == f"📅 Evento: {nome_evento}"
            ):

                evento = eventos.get(
                    nome_evento,
                    {
                        "presentes": {},
                        "nao_vou": {}
                    }
                )

                # Separar PT e reservas
                pt_formada, reservas = separar_participantes(
                    evento
                )

                # Lista de ausentes
                ausentes = ordenar_participantes(
                    evento.get(
                        "nao_vou",
                        {}
                    )
                )

                # Criar embed
                embed = discord.Embed(
                    title=f"📅 Evento: {nome_evento}",
                    color=0x00BFFF
                )

                # ------------------------------------------------
                # PT FORMADA
                # ------------------------------------------------

                embed.add_field(
                    name=(
                        f"🟢 PT FORMADA — "
                        f"{len(pt_formada)}/{LIMITE_PT}"
                    ),
                    value=formatar_lista_participantes(
                        pt_formada
                    ),
                    inline=False
                )

                # ------------------------------------------------
                # RESERVAS
                # ------------------------------------------------

                embed.add_field(
                    name=(
                        f"🟡 RESERVAS — "
                        f"{len(reservas)}"
                    ),
                    value=formatar_lista_participantes(
                        reservas
                    ),
                    inline=False
                )

                # ------------------------------------------------
                # NÃO VÃO
                # ------------------------------------------------

                embed.add_field(
                    name=(
                        f"❌ NÃO VÃO — "
                        f"{len(ausentes)}"
                    ),
                    value=formatar_lista_participantes(
                        ausentes
                    ),
                    inline=False
                )

                embed.set_footer(
                    text=(
                        "Os 12 primeiros confirmados "
                        "formam a PT. Os demais ficam "
                        "como reserva."
                    )
                )

                await msg.edit(
                    embed=embed,
                    view=PresencaView(
                        nome_evento
                    )
                )

                break

    except Exception as e:

        print(
            f"Erro ao atualizar evento: {e}"
        )


# ============================================================
# SELECT DE CLASSE
# ============================================================

class ClasseSelect(discord.ui.Select):

    def __init__(
        self,
        nome_evento,
        user_id,
        tipo
    ):

        self.nome_evento = nome_evento
        self.user_id = str(user_id)
        self.tipo = tipo

        options = [
            discord.SelectOption(
                label=classe
            )
            for classe in CLASSES_FIXAS
        ]

        super().__init__(
            placeholder="Escolha sua classe",
            options=options,
            min_values=1,
            max_values=1
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        escolha = self.values[0]

        # Criar evento caso não exista
        if self.nome_evento not in eventos:

            eventos[self.nome_evento] = {
                "presentes": {},
                "nao_vou": {}
            }

        evento = eventos[
            self.nome_evento
        ]

        # ========================================================
        # MARCAR PRESENÇA
        # ========================================================

        if self.tipo == "presente":

            agora = horario_atual()

            # --------------------------------------------
            # NOVA CONFIRMAÇÃO
            # --------------------------------------------

            evento["presentes"][
                self.user_id
            ] = {
                "classe": escolha,
                "horario": agora.isoformat()
            }

            # Remover de NÃO VOU
            evento["nao_vou"].pop(
                self.user_id,
                None
            )

            await interaction.response.send_message(
                (
                    f"✅ Presença confirmada como "
                    f"**{escolha}** às "
                    f"**{agora.strftime('%H:%M')}**."
                ),
                ephemeral=True
            )

        # ========================================================
        # NÃO VOU
        # ========================================================

        else:

            agora = horario_atual()

            # ------------------------------------------------
            # VERIFICAR SE JÁ ESTAVA CONFIRMADO
            # ------------------------------------------------

            participante_anterior = evento[
                "presentes"
            ].get(
                self.user_id
            )

            if participante_anterior:

                dados_anteriores = normalizar_participante(
                    self.user_id,
                    participante_anterior
                )

                classe_final = dados_anteriores[
                    "classe"
                ]

            else:

                classe_final = escolha

            # ------------------------------------------------
            # COLOCAR EM NÃO VÃO
            # ------------------------------------------------

            evento["nao_vou"][
                self.user_id
            ] = {
                "classe": classe_final,
                "horario": agora.isoformat()
            }

            # Remover dos confirmados
            evento["presentes"].pop(
                self.user_id,
                None
            )

            await interaction.response.send_message(
                (
                    f"❌ Ausência registrada às "
                    f"**{agora.strftime('%H:%M')}**.\n"
                    f"Classe: **{classe_final}**"
                ),
                ephemeral=True
            )

        # Salvar
        salvar_eventos()

        # Atualizar mensagem
        await atualizar_mensagem(
            interaction.channel,
            self.nome_evento
        )


# ============================================================
# VIEW DA SELEÇÃO DE CLASSE
# ============================================================

class ClasseView(discord.ui.View):

    def __init__(
        self,
        nome_evento,
        user_id,
        tipo
    ):

        super().__init__(
            timeout=30
        )

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

    def __init__(
        self,
        nome_evento
    ):

        super().__init__(
            timeout=None
        )

        self.nome_evento = nome_evento


    # ========================================================
    # BOTÃO MARCAR PRESENÇA
    # ========================================================

    @discord.ui.button(
        label="✅ Marcar Presença",
        style=discord.ButtonStyle.green
    )
    async def marcar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        evento = eventos.get(
            self.nome_evento
        )

        if not evento:

            await interaction.response.send_message(
                "❌ Evento não encontrado.",
                ephemeral=True
            )

            return

        user_id = str(
            interaction.user.id
        )

        # ------------------------------------------------
        # VERIFICAR SE JÁ ESTÁ CONFIRMADO
        # ------------------------------------------------

        if user_id in evento.get(
            "presentes",
            {}
        ):

            await interaction.response.send_message(
                (
                    "⚠️ Você já está confirmado "
                    "neste evento."
                ),
                ephemeral=True
            )

            return

        # ------------------------------------------------
        # Se estava em NÃO VOU, permitir voltar
        # ------------------------------------------------

        if user_id in evento.get(
            "nao_vou",
            {}
        ):

            dados = normalizar_participante(
                user_id,
                evento["nao_vou"][user_id]
            )

            classe = dados["classe"]

            agora = horario_atual()

            evento["presentes"][user_id] = {
                "classe": classe,
                "horario": agora.isoformat()
            }

            evento["nao_vou"].pop(
                user_id,
                None
            )

            salvar_eventos()

            await interaction.response.send_message(
                (
                    f"✅ Você voltou para a lista "
                    f"como **{classe}** às "
                    f"**{agora.strftime('%H:%M')}**.\n\n"
                    "Você entrou novamente no final "
                    "da fila de confirmação."
                ),
                ephemeral=True
            )

            await atualizar_mensagem(
                interaction.channel,
                self.nome_evento
            )

            return

        # ------------------------------------------------
        # NOVA CONFIRMAÇÃO
        # ------------------------------------------------

        await interaction.response.send_message(
            "Selecione sua classe:",
            view=ClasseView(
                self.nome_evento,
                interaction.user.id,
                "presente"
            ),
            ephemeral=True
        )


    # ========================================================
    # BOTÃO NÃO VOU
    # ========================================================

    @discord.ui.button(
        label="❌ Não vou",
        style=discord.ButtonStyle.red
    )
    async def nao_vou(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        evento = eventos.get(
            self.nome_evento
        )

        if not evento:

            await interaction.response.send_message(
                "❌ Evento não encontrado.",
                ephemeral=True
            )

            return

        user_id = str(
            interaction.user.id
        )

        # ------------------------------------------------
        # SE JÁ ESTÁ COMO NÃO VOU
        # ------------------------------------------------

        if user_id in evento.get(
            "nao_vou",
            {}
        ):

            await interaction.response.send_message(
                (
                    "⚠️ Você já está registrado "
                    "como **Não vou**."
                ),
                ephemeral=True
            )

            return

        # ------------------------------------------------
        # SE JÁ ESTÁ CONFIRMADO
        # ------------------------------------------------

        if user_id in evento.get(
            "presentes",
            {}
        ):

            dados = normalizar_participante(
                user_id,
                evento["presentes"][user_id]
            )

            classe = dados["classe"]

            agora = horario_atual()

            evento["nao_vou"][user_id] = {
                "classe": classe,
                "horario": agora.isoformat()
            }

            evento["presentes"].pop(
                user_id,
                None
            )

            salvar_eventos()

            await interaction.response.send_message(
                (
                    f"❌ Sua ausência foi registrada "
                    f"às **{agora.strftime('%H:%M')}**.\n"
                    f"Classe: **{classe}**"
                ),
                ephemeral=True
            )

            await atualizar_mensagem(
                interaction.channel,
                self.nome_evento
            )

            return

        # ------------------------------------------------
        # AINDA NÃO ESTÁ NA LISTA
        # ------------------------------------------------

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

@bot.command(
    name="criar_evento"
)
async def criar_evento(
    ctx,
    *,
    nome_evento
):

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
        text=(
            "Os 12 primeiros confirmados "
            "formam a PT. Os demais ficam "
            "como reserva."
        )
    )

    await ctx.send(
        embed=embed,
        view=PresencaView(
            nome_evento
        )
    )


# ============================================================
# COMANDO LISTA
# ============================================================

@bot.command(
    name="lista"
)
async def lista(
    ctx,
    *,
    nome_evento
):

    if nome_evento not in eventos:

        await ctx.send(
            "❌ Evento não encontrado."
        )

        return

    evento = eventos[
        nome_evento
    ]

    pt_formada, reservas = separar_participantes(
        evento
    )

    ausentes = ordenar_participantes(
        evento.get(
            "nao_vou",
            {}
        )
    )

    embed = discord.Embed(
        title=f"📋 Lista de {nome_evento}",
        color=0x1E90FF
    )

    embed.add_field(
        name=(
            f"🟢 PT FORMADA — "
            f"{len(pt_formada)}/{LIMITE_PT}"
        ),
        value=formatar_lista_participantes(
            pt_formada
        ),
        inline=False
    )

    embed.add_field(
        name=(
            f"🟡 RESERVAS — "
            f"{len(reservas)}"
        ),
        value=formatar_lista_participantes(
            reservas
        ),
        inline=False
    )

    embed.add_field(
        name=(
            f"❌ NÃO VÃO — "
            f"{len(ausentes)}"
        ),
        value=formatar_lista_participantes(
            ausentes
        ),
        inline=False
    )

    await ctx.send(
        embed=embed
    )


# ============================================================
# COMANDO APAGAR EVENTO
# ============================================================

@bot.command(
    name="apagar_evento"
)
async def apagar_evento(
    ctx,
    *,
    nome_evento
):

    if nome_evento not in eventos:

        await ctx.send(
            "❌ Evento não encontrado."
        )

        return

    del eventos[
        nome_evento
    ]

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
    os.getenv("TOKEN")
)
