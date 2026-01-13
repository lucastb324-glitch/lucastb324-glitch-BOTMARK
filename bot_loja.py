from discord.ext import commands
import discord
import json
import os
from datetime import datetime
import asyncio
import subprocess
import threading

# Fuzzy matching (instale com: pip install fuzzywuzzy python-Levenshtein)
from fuzzywuzzy import fuzz

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# === CONFIGURAÇÕES ===
LOJA_JSON_PATH = r"C:\Users\PC-NOVO\Desktop\PROJETO\loja_itens.json"
ALERTAS_FILE = r"C:\Users\PC-NOVO\Desktop\PROJETO\alertas.json"
EXPORTAR_PATH = r"C:\Users\PC-NOVO\Desktop\PROJETO\exportar.py"

# CANAL ONDE OS ALERTAS SERÃO ENVIADOS
ALERT_CHANNEL_ID = 1460408167132430356  # ← MUDE PARA O ID REAL DO CANAL DE ALERTAS !!

# Variáveis globais
itens_atuais = []
alertas = {}

bot.remove_command("help")


def formatar_preco(preco):
    try:
        preco_limpo = str(preco).replace(" Coin", "").replace(",", "").replace(".", "")
        valor = int(preco_limpo)
    except:
        return str(preco)

    if valor >= 1_000_000:
        return f"{valor // 1_000_000} Tera"
    elif valor >= 1_000:
        return f"{valor // 1_000} M"
    else:
        return f"{valor:,}".replace(",", ".")


def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def carregar_itens():
    global itens_atuais
    itens_atuais_antigos = itens_atuais.copy()
    novos_itens = load_json(LOJA_JSON_PATH, [])
    
    if novos_itens != itens_atuais:
        itens_atuais = novos_itens
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loja atualizada! {len(itens_atuais)} itens.")
        return True, itens_atuais_antigos
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sem mudanças na loja.")
        return False, itens_atuais_antigos


def carregar_alertas():
    global alertas
    alertas = load_json(ALERTAS_FILE, {})


def executar_exportar():
    def rodar():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Executando exportar.py...")
        try:
            resultado = subprocess.run(
                ["python", EXPORTAR_PATH],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(EXPORTAR_PATH)
            )
            if resultado.returncode == 0:
                print("✅ exportar.py concluído!")
            else:
                print(f"⚠️ Erro no exportar.py:\n{resultado.stderr}")
        except Exception as e:
            print(f"❌ Falha ao executar exportar.py: {e}")

    thread = threading.Thread(target=rodar, daemon=True)
    thread.start()


@bot.event
async def on_ready():
    print(f"Bot online como {bot.user} | Servidores: {len(bot.guilds)}")
    await bot.change_presence(activity=discord.Game(name="!loja | Alertas de itens DMW"))
    
    carregar_alertas()
    executar_exportar()
    
    await asyncio.sleep(3)
    carregar_itens()

    bot.loop.create_task(atualizador_periodico())


async def atualizador_periodico():
    while True:
        await asyncio.sleep(120)  # 2 minutos
        atualizou, itens_antigos = carregar_itens()
        if atualizou:
            itens_novos = [i for i in itens_atuais if i not in itens_antigos]
            if itens_novos:
                await disparar_alertas(itens_novos)


async def disparar_alertas(itens_novos):
    channel = bot.get_channel(ALERT_CHANNEL_ID)
    
    if not channel:
        print(f"ERRO: Canal de alertas ({ALERT_CHANNEL_ID}) não encontrado!")
        # Pode continuar mesmo sem canal, para tentar mandar no PV depois

    alertas_por_usuario = {}

    for item_novo in itens_novos:
        nome_item = item_novo.get("nome", "").strip()
        nome_item_lower = nome_item.lower()
        
        # Pegamos o nome da loja (agora deve existir no JSON!)
        nome_loja = item_novo.get("loja", "Loja Desconhecida")
        
        preco_str = item_novo.get("preco", "0 Coin").replace(" Coin", "").replace(",", "").replace(".", "")
        try:
            preco_item = int(preco_str)
        except:
            preco_item = 999999999

        # Aqui criamos a linha no formato desejado
        linha_item = f'"{nome_item}" /shopfinder "{nome_loja}"'

        # Opcional: se quiser mostrar também o preço no alerta
        # linha_item = f'"{nome_item}" • **{formatar_preco(item_novo.get("preco", "0"))}**   /shopfinder "{nome_loja}"'

        for user_id, user_alertas in alertas.items():
            for alerta in user_alertas:
                alerta_lower = alerta["item"].lower()

                if (fuzz.token_sort_ratio(alerta_lower, nome_item_lower) > 75 or
                    any(word in nome_item_lower for word in alerta_lower.split())):

                    if alerta.get("preco_max") is None or preco_item <= alerta["preco_max"]:
                        if user_id not in alertas_por_usuario:
                            alertas_por_usuario[user_id] = []
                        alertas_por_usuario[user_id].append(linha_item)
                        break  # evita duplicar o mesmo item para o mesmo usuário

    # Envia para cada usuário que teve match
    for user_id, itens in alertas_por_usuario.items():
        user = bot.get_user(int(user_id))
        if not user:
            print(f"Usuário {user_id} não encontrado")
            continue

        mention = user.mention
        itens_unicos = list(set(itens))[:10]  # remove duplicatas e limita

        try:
            embed = discord.Embed(
                title="🛒 ALERTA DE ITEM ENCONTRADO!",
                description=f"{mention}\n\nItens do seu alerta apareceram na loja:\n\n" +
                            "\n".join(itens_unicos),
                color=0x00ff88
            )
            embed.set_footer(text="Use o comando /shopfinder para localizar • Loja atualizada")
            
            # Envia no canal
            await channel.send(embed=embed)
            print(f"Alerta enviado no canal para {user}")

        except Exception as e:
            print(f"Erro ao enviar no canal para {user_id}: {e}")

        # Opcional: envio no privado (como você pediu antes)
        try:
            embed_pv = embed.copy()
            embed_pv.description = f"Olá {user.mention}! Encontrei item(s) do seu alerta:\n\n" + \
                                  "\n".join(itens_unicos)
            await user.send(embed=embed_pv)
            print(f"✅ Alerta enviado no PV para {user}")
        except:
            print(f"Não foi possível enviar PV para {user} (DMs fechadas?)")


# ======================== COMANDOS ========================


@bot.command(name="loja")
async def loja(ctx):
    carregar_itens()
    if not itens_atuais:
        await ctx.send("🔄 Loja vazia ou ainda carregando...")
        return
    embed = discord.Embed(title="🛒 Loja Atual - Digital Masters World", color=0x00ff00)
    for item in itens_atuais[-20:]:
        preco_formatado = formatar_preco(item.get('preco', '0'))
        texto = f"{item.get('nome','')} - **{preco_formatado}** (Quant: {item.get('quantidade','N/A')})"
        embed.add_field(name="Item", value=texto, inline=False)
    embed.set_footer(text=f"Total: {len(itens_atuais)} itens | Use !buscar <nome>")
    await ctx.send(embed=embed)


@bot.command()
async def buscar(ctx, *, termo):
    carregar_itens()
    termo = termo.lower()
    encontrados = [i for i in itens_atuais if termo in i.get("nome","").lower()]
    if not encontrados:
        await ctx.send(f"❌ Nenhum item encontrado com '{termo}'.")
        return
    embed = discord.Embed(title=f"🔍 Resultados para '{termo}'", color=0x0099ff)
    for item in encontrados[:15]:
        preco_formatado = formatar_preco(item.get('preco', '0'))
        texto = f"{item.get('nome','')} - **{preco_formatado}** (Quant: {item.get('quantidade','N/A')})"
        embed.add_field(name="Item", value=texto, inline=False)
    await ctx.send(embed=embed)


@bot.command()
async def meusalertas(ctx):
    user_id = str(ctx.author.id)
    if user_id not in alertas or not alertas[user_id]:
        await ctx.send("Você não tem alertas cadastrados. Use `!alerta <nome>`")
        return
    lista = "\n".join([f"**{a['id']}** - {a['item']}" + 
                      (f" (≤ {formatar_preco(a['preco_max'])})" if a.get('preco_max') else "")
                      for a in alertas[user_id]])
    await ctx.send(f"🔔 Seus alertas:\n{lista}")


@bot.command()
async def removeralerta(ctx, alerta_id: int):
    user_id = str(ctx.author.id)
    if user_id not in alertas or not any(a["id"] == alerta_id for a in alertas[user_id]):
        await ctx.send("Alerta não encontrado.")
        return
    alertas[user_id] = [a for a in alertas[user_id] if a["id"] != alerta_id]
    save_json(ALERTAS_FILE, alertas)
    await ctx.send(f"🗑️ Alerta **{alerta_id}** removido.")


@bot.command()
async def alerta(ctx, *, texto_comando):
    user_id = str(ctx.author.id)
    if user_id not in alertas:
        alertas[user_id] = []

    partes = texto_comando.strip().split()
    preco_max = None
    
    if len(partes) > 1 and partes[-1].replace(".", "").replace(",", "").isdigit():
        preco_max = int(partes[-1].replace(".", "").replace(",", ""))
        item_nome = " ".join(partes[:-1])
    else:
        item_nome = texto_comando
    
    item_nome_lower = item_nome.lower()
    
    for a in alertas[user_id]:
        if a["item"].lower() == item_nome_lower and a.get("preco_max") == preco_max:
            await ctx.send("⚠️ Você já tem esse alerta exatamente igual!")
            return
    
    alertas[user_id].append({
        "item": item_nome,
        "preco_max": preco_max,
        "id": len(alertas[user_id]) + 1
    })
    save_json(ALERTAS_FILE, alertas)
    
    if preco_max:
        await ctx.send(f"✅ Alerta criado para **{item_nome}** até **{formatar_preco(preco_max)}**!")
    else:
        await ctx.send(f"✅ Alerta criado para **{item_nome}** (qualquer preço)!")


@bot.command()
async def preco(ctx, *, termo):
    carregar_itens()
    termo = termo.lower()
    
    encontrados = [i for i in itens_atuais if termo in i.get("nome","").lower()]
    
    if not encontrados:
        await ctx.send(f"❌ Nenhum item encontrado com '{termo}'.")
        return
    
    def get_preco(item):
        preco_str = item.get("preco", "0 Coin").replace(" Coin", "").replace(",", "").replace(".", "")
        try:
            return int(preco_str)
        except:
            return 0
    
    encontrados.sort(key=get_preco)
    
    embed = discord.Embed(title=f"💰 Preços para '{termo}' (mais barato primeiro)", color=0xffd700)
    for item in encontrados[:20]:
        preco_formatado = formatar_preco(item.get('preco', '0'))
        texto = f"{item.get('nome','')} - **{preco_formatado}** (Quant: {item.get('quantidade','N/A')})"
        embed.add_field(name="Item", value=texto, inline=False)
    
    embed.set_footer(text=f"{len(encontrados)} itens encontrados")
    await ctx.send(embed=embed)


@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="📖 Ajuda | Comandos do Bot",
        description="Lista completa de comandos disponíveis\nPrefixo: **!**",
        color=0x5865F2
    )

    embed.add_field(
        name="🛒 Loja",
        value="**!loja**\nMostra os itens atuais\n\n**!buscar <nome>**\nProcura itens\n\n**!preco <nome>**\nOrdena por preço (barato → caro)",
        inline=False
    )

    embed.add_field(
        name="🔔 Alertas",
        value="**!alerta <item> [preço_max]**\nCria alerta\nEx: `!alerta Digiegg 500000`\n\n**!meusalertas**\nLista seus alertas\n\n**!removeralerta <id>**\nRemove um alerta",
        inline=False
    )

    embed.set_footer(text="Digital Masters World | Alertas no canal configurado")
    await ctx.send(embed=embed)


# TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TOKEN = ""

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("❌ ERRO: Token não encontrado!")
    bot.run(TOKEN)