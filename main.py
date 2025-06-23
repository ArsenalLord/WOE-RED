import os
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands
import json

# --- Flask para manter o Replit ativo ---
app = Flask('')

@app.route('/')
def home():
    return "Estou vivo!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()

# --- Bot Discord ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

ARQUIVO_EVENTOS = "eventos.json"

# Carrega eventos do arquivo se existir
if os.path.exists(ARQUIVO_EVENTOS):
    with open(ARQUIVO_EVENTOS, "r", encoding="utf-8") as f:
        eventos = json.load(f)
else:
    eventos = {}

CLASSES_FIXAS = [
    "Shura", "RK", "RG", "GX", "AB", "Musa", "Trovador",
    "Sorc", "WL", "SL", "Ranger", "Mecha", "Bio", "Renegado"
]

def salvar_eventos():
    with open(ARQUIVO_EVENTOS, "w", encoding="utf-8") as f:
        json.dump(eventos, f, indent=4, ensure_ascii=False)

class ClasseSelect(discord.ui.Select):
    def __init__(self, nome_evento, user_id, tipo):
        self.nome_evento = nome_evento
        self.user_id = str(user_id)
        self.tipo = tipo

        options = [discord.SelectOption(label=classe) for classe in CLASSES_FIXAS]
        super().__init__(placeholder="Escolha sua classe", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        escolha = self.values[0]
        if self.nome_evento not in eventos:
            eventos[self.nome_evento] = {"presentes": {}, "nao_vou": {}}

        evento = eventos[self.nome_evento]

        if self.tipo == "presente":
            evento["presentes"][self.user_id] = escolha
            evento["nao_vou"].pop(self.user_id, None)
            await interaction.response.send_message(f"✅ Presença confirmada como {escolha}.", ephemeral=True)
        else:
            evento["nao_vou"][self.user_id] = escolha
            evento["presentes"].pop(self.user_id, None)
            await interaction.response.send_message(f"❌ Ausência registrada como {escolha}.", ephemeral=True)

        salvar_eventos()
        await atualizar_mensagem(interaction.channel, self.nome_evento)

class ClasseView(discord.ui.View):
    def __init__(self, nome_evento, user_id, tipo):
        super().__init__(timeout=30)
        self.add_item(ClasseSelect(nome_evento, user_id, tipo))

class PresencaView(discord.ui.View):
    def __init__(self, nome_evento):
        super().__init__(timeout=None)
        self.nome_evento = nome_evento

    @discord.ui.button(label="✅ Marcar Presença", style=discord.ButtonStyle.green)
    async def marcar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Selecione sua classe:",
            view=ClasseView(self.nome_evento, interaction.user.id, "presente"),
            ephemeral=True
        )

    @discord.ui.button(label="❌ Não vou", style=discord.ButtonStyle.red)
    async def nao_vou(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Selecione sua classe:",
            view=ClasseView(self.nome_evento, interaction.user.id, "nao_vou"),
            ephemeral=True
        )

def formatar_lista(dados):
    return [f"- <@{uid}> ({classe})" for uid, classe in dados.items()]

async def atualizar_mensagem(channel, nome_evento):
    async for msg in channel.history(limit=50):
        if msg.embeds and msg.embeds[0].title == f"📅 Evento: {nome_evento}":
            evento = eventos.get(nome_evento, {"presentes": {}, "nao_vou": {}})
            embed = discord.Embed(title=f"📅 Evento: {nome_evento}", color=0x00BFFF)
            embed.add_field(name="✅ Confirmados", value=str(len(evento["presentes"])), inline=True)
            embed.add_field(name="❌ Não vão", value=str(len(evento["nao_vou"])), inline=True)
            embed.set_footer(text="Clique abaixo para confirmar ou recusar.")
            await msg.edit(embed=embed, view=PresencaView(nome_evento))
            break

@bot.event
async def on_ready():
    print(f"🤖 Bot online como {bot.user}")

@bot.command(name="criar_evento")
async def criar_evento(ctx, *, nome_evento):
    if nome_evento in eventos:
        await ctx.send("⚠️ Este evento já existe.")
        return

    eventos[nome_evento] = {"presentes": {}, "nao_vou": {}}
    salvar_eventos()

    embed = discord.Embed(title=f"📅 Evento: {nome_evento}", color=0x00BFFF)
    embed.add_field(name="✅ Confirmados", value="0", inline=True)
    embed.add_field(name="❌ Não vão", value="0", inline=True)
    embed.set_footer(text="Clique abaixo para confirmar ou recusar.")
    await ctx.send(embed=embed, view=PresencaView(nome_evento))

@bot.command(name="lista")
async def lista(ctx, *, nome_evento):
    if nome_evento not in eventos:
        await ctx.send("❌ Evento não encontrado.")
        return

    evento = eventos[nome_evento]
    confirmados = formatar_lista(evento["presentes"])
    ausentes = formatar_lista(evento["nao_vou"])

    embed = discord.Embed(title=f"📋 Lista de {nome_evento}", color=0x1E90FF)
    embed.add_field(name="✅ Confirmados", value="\n".join(confirmados) or "Ninguém", inline=False)
    embed.add_field(name="❌ Não vão", value="\n".join(ausentes) or "Ninguém", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="apagar_evento")
async def apagar_evento(ctx, *, nome_evento):
    if nome_evento not in eventos:
        await ctx.send("❌ Evento não encontrado.")
        return

    del eventos[nome_evento]
    salvar_eventos()
    await ctx.send(f"🗑️ Evento **{nome_evento}** removido.")

# Rodar o bot
bot.run(os.getenv('TOKEN'))