import os
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta
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

    try:

        with open(
            ARQUIVO_EVENTOS,
            "r",
            encoding="utf-8"
        ) as f:

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
# HORÁRIO
# ============================================================

def horario_atual():

    return datetime.now(FUSO_HORARIO)


def formatar_horario(data_iso):

    try:

        data = datetime.fromisoformat(
            data_iso
        )

        return data.strftime("%H:%M")

    except:

        return "--:--"


def formatar_data_horario(data_iso):

    try:

        data = datetime.fromisoformat(
            data_iso
        )

        return data.strftime(
            "%d/%m/%Y às %H:%M"
        )

    except:

        return "Data inválida"


# ============================================================
# CONVERTER DATA DO COMANDO
# ============================================================

def converter_data_evento(
    data,
    horario
):

    try:

        data_hora = datetime.strptime(
            f"{data} {horario}",
            "%d/%m/%Y %H:%M"
        )

        return data_hora.replace(
            tzinfo=FUSO_HORARIO
        )

    except ValueError:

        return None


# ============================================================
# NORMALIZAR PARTICIPANTE
# ============================================================

def normalizar_participante(
    user_id,
    dados
):

    # Formato novo
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

    # Compatibilidade com eventos antigos
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

    participantes.sort(
        key=lambda x: x["horario"] or "9999"
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

    pt_formada = confirmados[
        :LIMITE_PT
    ]

    reservas = confirmados[
        LIMITE_PT:
    ]

    return (
        pt_formada,
        reservas
    )


# ============================================================
# FORMATAR PARTICIPANTE
# ============================================================

def formatar_participante(
    participante
):

    return (
        f"<@{participante['user_id']}> "
        f"({participante['classe']}) "
        f"— 🕐 "
        f"{formatar_horario(participante['horario'])}"
    )


# ============================================================
# FORMATAR LISTA
# ============================================================

def formatar_lista_participantes(
    lista
):

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

async def atualizar_mensagem(channel, nome_evento):

    evento = eventos.get(nome_evento)

    if not evento:
        return

    canal_id = evento.get("canal_id")
    mensagem_id = evento.get("mensagem_id")

    canal = bot.get_channel(canal_id) if canal_id else channel

    if canal is None:
        canal = channel

    if canal is None:
        print(f"❌ Canal não encontrado para o evento {nome_evento}.")
        return

    mensagem = None

    try:
        # Primeiro tenta usar o ID salvo.
        if mensagem_id:
            try:
                mensagem = await canal.fetch_message(int(mensagem_id))
            except (discord.NotFound, discord.HTTPException):
                mensagem = None

        # Compatibilidade com eventos antigos que ainda não possuem mensagem_id.
        if mensagem is None:
            async for msg in canal.history(limit=100):
                if not msg.embeds:
                    continue

                titulo = msg.embeds[0].title
                if titulo == f"📅 Evento: {nome_evento}":
                    mensagem = msg
                    evento["mensagem_id"] = msg.id
                    salvar_eventos()
                    print(f"🔎 Mensagem do evento encontrada: {nome_evento}")
                    break

        if mensagem is None:
            print(f"⚠️ Mensagem do evento não encontrada: {nome_evento}")
            return

        pt_formada, reservas = separar_participantes(evento)
        ausentes = ordenar_participantes(evento.get("nao_vou", {}))

        embed = discord.Embed(
            title=f"📅 Evento: {nome_evento}",
            color=0x00BFFF
        )

        horario_inicio = evento.get("horario_inicio")

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
                "Os 12 primeiros confirmados formam a PT. "
                "Os demais ficam como reserva."
            )
        )

        await mensagem.edit(
            embed=embed,
            view=PresencaView(nome_evento)
        )

        print(f"✅ Evento atualizado: {nome_evento}")

    except Exception as e:
        print(f"❌ Erro ao atualizar mensagem do evento {nome_evento}: {e}")


# ============================================================
# AVISO 10 MINUTOS
# ============================================================

async def verificar_eventos_10_minutos():

    agora = horario_atual()

    for nome_evento, evento in list(
        eventos.items()
    ):

        horario_inicio_str = evento.get(
            "horario_inicio"
        )

        if not horario_inicio_str:
            continue

        try:

            horario_inicio = datetime.fromisoformat(
                horario_inicio_str
            )

        except Exception:

            continue

        # ====================================================
        # VERIFICAR SE ESTÁ NO MOMENTO DO AVISO
        # ====================================================

        diferenca = (
            horario_inicio - agora
        )

        # Entre 10 minutos antes e o horário de início
        if (
            timedelta(0)
            <= diferenca
            <= timedelta(minutes=10)
        ):

            # Já enviou?
            if evento.get(
                "aviso_10_minutos",
                False
            ):

                continue

            canal_id = evento.get(
                "canal_id"
            )

            if not canal_id:
                continue

            canal = bot.get_channel(
                canal_id
            )

            if canal is None:
                continue

            pt_formada, reservas = (
                separar_participantes(
                    evento
                )
            )

            if not pt_formada:

                mensagem = (
                    f"🚨 **ATENÇÃO!**\n\n"
                    f"📅 **{nome_evento}** "
                    f"começa às "
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
                    f"⏰ **Início:** "
                    f"{horario_inicio.strftime('%H:%M')}\n\n"
                    f"🟢 **PT FORMADA:**\n"
                    f"{mencoes}\n\n"
                    f"⚔️ A PT está sendo chamada para o evento."
                )

            try:

                await canal.send(
                    mensagem
                )

                evento[
                    "aviso_10_minutos"
                ] = True

                salvar_eventos()

                print(
                    f"⏰ Aviso de 10 minutos enviado: "
                    f"{nome_evento}"
                )

            except Exception as e:

                print(
                    f"Erro ao enviar aviso: {e}"
                )


# ============================================================
# LOOP DE VERIFICAÇÃO
# ============================================================

@tasks.loop(seconds=30)
async def verificar_eventos():

    await verificar_eventos_10_minutos()


# ============================================================
# SELECT DE CLASSE
# ============================================================

class ClasseSelect(
    discord.ui.Select
):

    def __init__(
        self,
        nome_evento,
        user_id,
        tipo
    ):

        self.nome_evento = nome_evento

        self.user_id = str(
            user_id
        )

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
        interaction
    ):

        escolha = self.values[0]

        evento = eventos.get(
            self.nome_evento
        )

        if not evento:

            await interaction.response.send_message(
                "❌ Evento não encontrado.",
                ephemeral=True
            )

            return

        agora = horario_atual()

        # ====================================================
        # CONFIRMAR PRESENÇA
        # ====================================================

        if self.tipo == "presente":

            # ------------------------------------------------
            # Verificar se já está confirmado
            # ------------------------------------------------

            if self.user_id in evento.get(
                "presentes",
                {}
            ):

                await interaction.response.send_message(
                    "⚠️ Você já está confirmado.",
                    ephemeral=True
                )

                return

            evento["presentes"][
                self.user_id
            ] = {

                "classe": escolha,

                "horario": agora.isoformat()
            }

            # Remover de não vou
            evento["nao_vou"].pop(
                self.user_id,
                None
            )

            salvar_eventos()

            await interaction.response.send_message(
                (
                    f"✅ Presença confirmada como "
                    f"**{escolha}** às "
                    f"**{agora.strftime('%H:%M')}**.\n\n"
                    "📋 Sua posição será definida "
                    "pela ordem de confirmação."
                ),
                ephemeral=True
            )

            await atualizar_mensagem(
                interaction.channel,
                self.nome_evento
            )

        # ====================================================
        # NÃO VOU
        # ====================================================

        else:

            # ------------------------------------------------
            # Verificar se já está como não vou
            # ------------------------------------------------

            if self.user_id in evento.get(
                "nao_vou",
                {}
            ):

                await interaction.response.send_message(
                    "⚠️ Você já está como **Não vou**.",
                    ephemeral=True
                )

                return

            # ------------------------------------------------
            # Verificar se estava confirmado
            # ------------------------------------------------

            estava_confirmado = (
                self.user_id
                in evento.get(
                    "presentes",
                    {}
                )
            )

            if estava_confirmado:

                dados_antigos = normalizar_participante(
                    self.user_id,
                    evento["presentes"][
                        self.user_id
                    ]
                )

                classe_final = dados_antigos[
                    "classe"
                ]

            else:

                classe_final = escolha

            # ------------------------------------------------
            # VERIFICAR PT ANTES
            # ------------------------------------------------

            pt_antes, reservas_antes = (
                separar_participantes(
                    evento
                )
            )

            ids_pt_antes = [
                p["user_id"]
                for p in pt_antes
            ]

            # ------------------------------------------------
            # Registrar ausência
            # ------------------------------------------------

            evento["nao_vou"][
                self.user_id
            ] = {

                "classe": classe_final,

                "horario": agora.isoformat()
            }

            evento["presentes"].pop(
                self.user_id,
                None
            )

            salvar_eventos()

            # ------------------------------------------------
            # VERIFICAR PT DEPOIS
            # ------------------------------------------------

            pt_depois, reservas_depois = (
                separar_participantes(
                    evento
                )
            )

            # ------------------------------------------------
            # ENCONTRAR QUEM SUBIU
            # ------------------------------------------------

            ids_pt_depois = [
                p["user_id"]
                for p in pt_depois
            ]

            promovidos = [
                p
                for p in pt_depois
                if p["user_id"]
                not in ids_pt_antes
            ]

            # ------------------------------------------------
            # MENSAGEM PARA QUEM SAIU
            # ------------------------------------------------

            await interaction.response.send_message(
                (
                    f"❌ Sua ausência foi registrada "
                    f"às **{agora.strftime('%H:%M')}**.\n"
                    f"Classe: **{classe_final}**"
                ),
                ephemeral=True
            )

            # ------------------------------------------------
            # AVISAR RESERVA PROMOVIDO
            # ------------------------------------------------

            if promovidos:

                nomes_promovidos = " ".join(
                    f"<@{p['user_id']}>"
                    for p in promovidos
                )

                await interaction.channel.send(
                    (
                        f"🔄 **VAGA DISPONÍVEL!**\n\n"
                        f"❌ <@{self.user_id}> "
                        f"deixou a PT.\n\n"
                        f"🟢 O próximo reserva assumiu "
                        f"a vaga:\n"
                        f"{nomes_promovidos}\n\n"
                        f"⚔️ **Você está na PT FORMADA!**"
                    )
                )

            await atualizar_mensagem(
                interaction.channel,
                self.nome_evento
            )


# ============================================================
# VIEW SELEÇÃO DE CLASSE
# ============================================================

class ClasseView(
    discord.ui.View
):

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

class PresencaView(
    discord.ui.View
):

    def __init__(
        self,
        nome_evento
    ):

        super().__init__(
            timeout=None
        )

        self.nome_evento = nome_evento


    # ========================================================
    # MARCAR PRESENÇA
    # ========================================================

    @discord.ui.button(
        label="✅ Marcar Presença",
        style=discord.ButtonStyle.green
    )
    async def marcar(
        self,
        interaction,
        button
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
        # Já está confirmado
        # ------------------------------------------------

        if user_id in evento.get(
            "presentes",
            {}
        ):

            await interaction.response.send_message(
                "⚠️ Você já está confirmado neste evento.",
                ephemeral=True
            )

            return

        # ------------------------------------------------
        # Estava como NÃO VOU
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
                    "📋 Você entrou novamente no "
                    "final da fila."
                ),
                ephemeral=True
            )

            await atualizar_mensagem(
                interaction.channel,
                self.nome_evento
            )

            return

        # ------------------------------------------------
        # Novo participante
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
    # NÃO VOU
    # ========================================================

    @discord.ui.button(
        label="❌ Não vou",
        style=discord.ButtonStyle.red
    )
    async def nao_vou(
        self,
        interaction,
        button
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
        # Já está como não vou
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
        # Está confirmado
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

            # PT antes da saída
            pt_antes, reservas_antes = (
                separar_participantes(
                    evento
                )
            )

            evento["nao_vou"][user_id] = {

                "classe": classe,

                "horario": agora.isoformat()
            }

            evento["presentes"].pop(
                user_id,
                None
            )

            salvar_eventos()

            # PT depois da saída
            pt_depois, reservas_depois = (
                separar_participantes(
                    evento
                )
            )

            ids_antes = {
                p["user_id"]
                for p in pt_antes
            }

            promovidos = [
                p
                for p in pt_depois
                if p["user_id"]
                not in ids_antes
            ]

            await interaction.response.send_message(
                (
                    f"❌ Sua ausência foi registrada "
                    f"às **{agora.strftime('%H:%M')}**.\n"
                    f"Classe: **{classe}**"
                ),
                ephemeral=True
            )

            # ------------------------------------------------
            # PROMOVER RESERVA
            # ------------------------------------------------

            if promovidos:

                mencoes = " ".join(
                    f"<@{p['user_id']}>"
                    for p in promovidos
                )

                await interaction.channel.send(
                    (
                        f"🔄 **VAGA DISPONÍVEL!**\n\n"
                        f"❌ <@{user_id}> "
                        f"deixou a PT.\n\n"
                        f"🟢 **Novo membro da PT:**\n"
                        f"{mencoes}\n\n"
                        f"⚔️ **Você assumiu a vaga!**"
                    )
                )

            await atualizar_mensagem(
                interaction.channel,
                self.nome_evento
            )

            return

        # ------------------------------------------------
        # Nunca confirmou
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
    argumentos
):

    partes = argumentos.rsplit(
        " ",
        2
    )

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

    nome_evento = partes[0]
    data = partes[1]
    horario = partes[2]

    # ========================================================
    # VERIFICAR DATA
    # ========================================================

    data_hora = converter_data_evento(
        data,
        horario
    )

    if data_hora is None:

        await ctx.send(
            (
                "❌ Data ou horário inválido.\n"
                "Use o formato:\n"
                "`DD/MM/AAAA HH:MM`"
            )
        )

        return

    # ========================================================
    # NÃO PERMITIR EVENTO NO PASSADO
    # ========================================================

    if data_hora <= horario_atual():

        await ctx.send(
            "❌ O horário do evento precisa ser no futuro."
        )

        return

    # ========================================================
    # EVENTO JÁ EXISTE
    # ========================================================

    if nome_evento in eventos:

        await ctx.send(
            "⚠️ Este evento já existe."
        )

        return

    # ========================================================
    # CRIAR EVENTO
    # ========================================================

    eventos[nome_evento] = {

        "presentes": {},

        "nao_vou": {},

        "horario_inicio": data_hora.isoformat(),

        "canal_id": ctx.channel.id,

        "mensagem_id": None,

        "aviso_10_minutos": False
    }

    salvar_eventos()

    # ========================================================
    # EMBED
    # ========================================================

    embed = discord.Embed(
        title=f"📅 Evento: {nome_evento}",
        color=0x00BFFF
    )

    embed.add_field(
        name="⏰ Início",
        value=data_hora.strftime(
            "%d/%m/%Y às %H:%M"
        ),
        inline=False
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
            "Os 12 primeiros confirmados formam "
            "a PT. O aviso será enviado 10 minutos "
            "antes do início."
        )
    )

    mensagem = await ctx.send(
        embed=embed,
        view=PresencaView(
            nome_evento
        )
    )

    # Guarda o ID da mensagem para que o painel possa ser atualizado.
    eventos[nome_evento]["mensagem_id"] = mensagem.id
    salvar_eventos()


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

    pt_formada, reservas = (
        separar_participantes(
            evento
        )
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

    horario_inicio = evento.get(
        "horario_inicio"
    )

    if horario_inicio:

        embed.add_field(
            name="⏰ Início",
            value=formatar_data_horario(
                horario_inicio
            ),
            inline=False
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

    # Evitar iniciar o loop duas vezes
    if not verificar_eventos.is_running():

        verificar_eventos.start()

        print(
            "⏰ Sistema de avisos de eventos iniciado."
        )


# ============================================================
# INICIAR BOT
# ============================================================

bot.run(
    os.getenv("TOKEN")
)
