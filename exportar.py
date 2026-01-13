import subprocess
import os
from datetime import datetime, timedelta
import re
import json
import time

# Caminhos
CLI_PATH = r"C:\Users\PC-NOVO\Desktop\PROJETO\DiscordChatExporter.Cli.win-x64\DiscordChatExporter.Cli.exe"

if not os.path.exists(CLI_PATH):
    print("ERRO: DiscordChatExporter.Cli.exe não encontrado!")
    input("Pressione Enter para fechar...")
    exit()

# Config
config_path = os.path.join(os.path.dirname(__file__), "config.txt")
config = {}
with open(config_path, "r", encoding="utf-8") as f:
    for line in f:
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.strip().split("=", 1)
            config[key] = value

TOKEN = config["TOKEN"].strip()
CHANNEL_ID = config["CHANNEL_ID"].strip()
LOG_PATH = config["LOG_PATH"].strip()
JSON_PATH = r"C:\Users\PC-NOVO\Desktop\PROJETO\loja_itens.json"

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
TEMP_FILE = os.path.join(os.path.dirname(LOG_PATH), "temp_novas.txt")

# Intervalo de atualização em segundos (5 minutos = 300, 10 minutos = 600)
INTERVALO = 60# Mude aqui pra quanto quiser (ex: 180 = 3 minutos)

print("Bot de Loja DMW - Auto Atualizacao ATIVADA")
print(f"Atualizando a cada {INTERVALO // 60} minutos")
print("Pressione Ctrl + C para parar\n")

while True:
    try:
        # Data de busca
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 0:
            ultima_mod = datetime.fromtimestamp(os.path.getmtime(LOG_PATH))
            after_date = (ultima_mod - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            after_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        comando = [
            CLI_PATH,
            "export",
            "-t", TOKEN,
            "-c", CHANNEL_ID,
            "-f", "PlainText",
            "-o", TEMP_FILE,
            "--after", after_date
        ]

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando novas mensagens da loja...")

        resultado = subprocess.run(comando, capture_output=True, text=True, check=True)

        novas_mensagens = ""
        if os.path.exists(TEMP_FILE) and os.path.getsize(TEMP_FILE) > 0:
            with open(TEMP_FILE, "r", encoding="utf-8") as f:
                novas_mensagens = f.read()

            # Atualiza log completo
            antigo = ""
            if os.path.exists(LOG_PATH):
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    antigo = f.read().rstrip("\n") + "\n"

            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.write(antigo + novas_mensagens)

            print(f"✅ +{len(novas_mensagens.splitlines())} linhas novas adicionadas ao log")
            os.remove(TEMP_FILE)
        else:
            print("ℹ️  Nenhuma mensagem nova.")

        # === EXTRA: Gera loja_itens.json limpo ===
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                log_completo = f.read()

            def extrair_itens_tabela(texto_completo):
                itens = []
                padrao_bloco = r"```(?:Shop Name.*?\n)?\|.*?Item.*?\|.*?Cost.*?(?:\n\|.*?\|\n(.*?))```"
                matches = re.finditer(padrao_bloco, texto_completo, re.DOTALL | re.IGNORECASE)
                
                for match in matches:
                    bloco_itens = match.group(1) or ""
                    linhas = bloco_itens.split("\n")
                    for linha in linhas:
                        linha = linha.strip()
                        if not linha.startswith("|") or linha.count("|") < 3:
                            continue
                        partes = [p.strip() for p in linha.split("|")[1:-1]]
                        if len(partes) >= 2:
                            nome = partes[0].strip()
                            preco_str = partes[1].strip().replace(",", "")
                            quantidade = partes[2].strip().replace(",", "") if len(partes) > 2 else "N/A"
                            if nome and preco_str.isdigit():
                                itens.append({
                                    "nome": nome,
                                    "preco": f"{preco_str} Coin",
                                    "quantidade": quantidade
                                })
                return itens

            itens_extraidos = extrair_itens_tabela(log_completo)

            # Remove duplicatas
            itens_unicos = []
            vistos = set()
            for item in itens_extraidos:
                chave = f"{item['nome']}|{item['preco']}"
                if chave not in vistos:
                    vistos.add(chave)
                    itens_unicos.append(item)

            with open(JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(itens_unicos, f, ensure_ascii=False, indent=2)

            print(f"🛒 Loja atualizada: {len(itens_unicos)} itens únicos salvos em loja_itens.json\n")
        else:
            print("Log vazio, aguardando primeira atualização...\n")

    except subprocess.CalledProcessError as e:
        print(f"Erro ao baixar mensagens: {e.stderr.strip()}")
    except Exception as e:
        print(f"Erro inesperado: {e}")

    # Espera até a próxima execução
    print(f"Aguardando {INTERVALO // 60} minutos para próxima atualização...\n")
    time.sleep(INTERVALO)