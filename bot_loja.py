from discord.ext import commands
import discord  # ← Mantenha, mas o PyCord usa o mesmo nome
import json
import os
from datetime import datetime
import asyncio
import subprocess  # ← Novo import
import threading

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# === CONFIGURAÇÕES ===
LOJA_JSON_PATH = r"C:\Users\PC-NOVO\Desktop\PROJETO\loja_itens.json"
ALERTAS_FILE = r"C:\Users\PC-NOVO\Desktop\PROJETO\alertas.json"
EXPORTAR_PATH = r"C:\Users\PC-NOVO\Desktop\PROJETO\exportar.py"  # ← Caminho do exportar.py

# Variáveis globais
itens_atuais = []
alertas = {}

# Carregar/Salvar JSON
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

# Carrega itens do JSON
def carregar_itens():
    global itens_atuais
    itens_atuais_antigos = itens_atuais.copy()
    novos_itens = load_json(LOJA_JSON_PATH, [])
    
    if novos_itens != itens_atuais:
        itens_atuais = novos_itens
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loja atualizada! {len(itens_atuais)} itens carregados.")
        return True, itens_atuais_antigos
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sem mudanças na loja.")
        return False, itens_atuais_antigos

# Carrega alertas
def carregar_alertas():
    global alertas
    alertas = load_json(ALERTAS_FILE, {})

# Executa o exportar.py
# Executa o exportar.py em uma thread separada (não bloqueia o bot)
def executar_exportar():
    def rodar():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Executando exportar.py em segundo plano...")
        try:
            resultado = subprocess.run(
                ["python", EXPORTAR_PATH],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(EXPORTAR_PATH)
            )
            if resultado.returncode == 0:
                print("✅ exportar.py concluído com sucesso!")
            else:
                print(f"⚠️ Erro no exportar.py:\n{resultado.stderr}")
        except Exception as e:
            print(f"❌ Falha ao executar exportar.py: {e}")

    # Roda em thread separada
    thread = threading.Thread(target=rodar, daemon=True)
    thread.start()

@bot.event
async def on_ready():
    print(f"Bot online como {bot.user} | Servidores: {len(bot.guilds)}")
    await bot.change_presence(activity=discord.Game(name="!loja | Alertas de itens DMW"))
    
    carregar_alertas()
    
    # Executa o exportar em background (não bloqueia)
    executar_exportar()
    
    # Pequeno delay pra dar tempo do exportar começar
    await asyncio.sleep(3)
    carregar_itens()  # Carrega o JSON (pode ainda estar vazio na primeira vez)

    # Tarefa de fundo continua normal
    bot.loop.create_task(atualizador_periodico())

async def atualizador_periodico():
    while True:
        await asyncio.sleep(30)  # 5 minutos
        atualizou, itens_antigos = carregar_itens()
        if atualizou:
            itens_novos = [i for i in itens_atuais if i not in itens_antigos]
            if itens_novos:
                await disparar_alertas(itens_novos)

# Atualiza a função disparar_alertas pra respeitar preço máximo
async def disparar_alertas(itens_novos):
    for user_id, user_alertas in alertas.items():
        user = bot.get_user(int(user_id))
        if not user:
            continue
        itens_do_alerta = []
        
        for item_novo in itens_novos:
            nome_item = item_novo.get("nome", "")
            nome_item_lower = nome_item.lower()
            preco_str = item_novo.get("preco", "0 Coin").replace(" Coin", "").replace(",", "")
            preco_item = int(preco_str) if preco_str.isdigit() else 999999999  # preço alto se inválido
            
            for alerta in user_alertas:
                if alerta["item"].lower() in nome_item_lower:
                    if alerta.get("preco_max") is None or preco_item <= alerta["preco_max"]:
                        itens_do_alerta.append(f"{nome_item} - {item_novo['preco']} (Quant: {item_novo.get('quantidade','N/A')})")
                        break  # evita duplicar se tiver mais de um alerta
        
        if itens_do_alerta:
            try:
                embed = discord.Embed(title="🛒 Item no seu alerta apareceu na loja!", color=0xff9900)
                embed.description = "\n".join(set(itens_do_alerta[:10]))  # remove duplicatas
                embed.set_footer(text="Digital Masters World | Loja Atualizada")
                await user.send(embed=embed)
            except:
                pass  # DM fechada
# === COMANDOS ===
@bot.command(name="loja")
async def loja(ctx):
    carregar_itens()
    if not itens_atuais:
        await ctx.send("🔄 Loja vazia ou ainda carregando... (aguarde a primeira atualização)")
        return
    embed = discord.Embed(title="🛒 Loja Atual - Digital Masters World", color=0x00ff00)
    for item in itens_atuais[-20:]:
        texto = f"{item.get('nome','')} - {item.get('preco','')} (Quant: {item.get('quantidade','N/A')})"
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
        texto = f"{item.get('nome','')} - {item.get('preco','')} (Quant: {item.get('quantidade','N/A')})"
        embed.add_field(name="Item", value=texto, inline=False)
    await ctx.send(embed=embed)


@bot.command()
async def meusalertas(ctx):
    user_id = str(ctx.author.id)
    if user_id not in alertas or not alertas[user_id]:
        await ctx.send("Você não tem alertas cadastrados. Use `!alerta <nome>`")
        return
    lista = "\n".join([f"**{a['id']}** - {a['item']}" for a in alertas[user_id]])
    await ctx.send(f"🔔 Seus alertas:\n{lista}")

@bot.command()
async def removeralerta(ctx, alerta_id: int):
    user_id = str(ctx.author.id)
    if user_id not in alertas or not any(a["id"] == alerta_id for a in alertas[user_id]):
        await ctx.send("Alerta não encontrado.")
        return
    alertas[user_id] = [a for a in alertas[user_id] if a["id"] != alerta_id]
    save_json(ALERTAS_FILE, alertas)
    await ctx.send(f"🗑️ Alerta {alerta_id} removido.")
    
@bot.command()
async def alerta(ctx, *, texto_comando):
    user_id = str(ctx.author.id)
    if user_id not in alertas:
        alertas[user_id] = []

    partes = texto_comando.strip().split()
    preco_max = None
    
    # Verifica se o último termo é número (preço máximo)
    if len(partes) > 1 and partes[-1].replace(".", "").replace(",", "").isdigit():
        preco_max = int(partes[-1].replace(".", "").replace(",", ""))
        item_nome = " ".join(partes[:-1])
    else:
        item_nome = texto_comando
    
    item_nome_lower = item_nome.lower()
    
    # Verifica duplicata
    for a in alertas[user_id]:
        if a["item"].lower() == item_nome_lower and a.get("preco_max") == preco_max:
            await ctx.send("⚠️ Você já tem esse alerta!")
            return
    
    alertas[user_id].append({
        "item": item_nome,
        "preco_max": preco_max,
        "id": len(alertas[user_id]) + 1
    })
    save_json(ALERTAS_FILE, alertas)
    
    if preco_max:
        await ctx.send(f"✅ Alerta criado para **{item_nome}** até **{preco_max:,} Coin**!")
    else:
        await ctx.send(f"✅ Alerta criado para **{item_nome}** (qualquer preço)!")
        
# Novo comando: lista itens ordenados por preço
@bot.command()
async def preco(ctx, *, termo):
    carregar_itens()
    termo = termo.lower()
    
    encontrados = [i for i in itens_atuais if termo in i.get("nome","").lower()]
    
    if not encontrados:
        await ctx.send(f"❌ Nenhum item encontrado com '{termo}'.")
        return
    
    # Ordena do mais barato pro mais caro
    def get_preco(item):
        preco_str = item.get("preco", "0 Coin").replace(" Coin", "").replace(",", "")
        return int(preco_str) if preco_str.isdigit() else 0
    
    encontrados.sort(key=get_preco)
    
    embed = discord.Embed(title=f"💰 Preços para '{termo}' (mais barato primeiro)", color=0xffd700)
    for item in encontrados[:20]:  # limita a 20
        texto = f"{item.get('nome','')} - **{item.get('preco','N/A')}** (Quant: {item.get('quantidade','N/A')})"
        embed.add_field(name="Item", value=texto, inline=False)
    
    embed.set_footer(text=f"{len(encontrados)} itens encontrados")
    await ctx.send(embed=embed)

# TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ ERRO: Variável de ambiente DISCORD_BOT_TOKEN não encontrada!")

bot.run(TOKEN)