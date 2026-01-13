import subprocess
import os
from datetime import datetime, timedelta
import re
import json
import time

# ===============================
# VARIÁVEIS DE AMBIENTE (RENDER)
# ===============================
CLI_PATH = os.getenv("CLI_PATH")
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
LOG_PATH = os.getenv("LOG_PATH", "./logs/loja.log")
JSON_PATH = os.getenv("JSON_PATH", "./loja_itens.json")
INTERVALO = int(os.getenv("INTERVALO", 60))

# Validações
if not all([CLI_PATH, TOKEN, CHANNEL_ID]):
    raise RuntimeError("❌ Variáveis de ambiente obrigatórias não definidas!")

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
TEMP_FILE = os.path.join(os.path.dirname(LOG_PATH), "temp_novas.txt")

print("Bot de Loja DMW - Auto Atualização ATIVADA")
print(f"Atualizando a cada {INTERVALO // 60} minutos")
print("Ctrl + C para parar\n")

while True:
    try:
        # Data base
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

        print(f"[{datetime.now().strftime('%H:%M:%S')}] A buscar mensagens...")
        subprocess.run(comando, capture_output=True, text=True, check=True)

        if os.path.exists(TEMP_FILE) and os.path.getsize(TEMP_FILE) > 0:
            with open(TEMP_FILE, "r", encoding="utf-8") as f:
                novas = f.read()

            antigo = ""
            if os.path.exists(LOG_PATH):
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    antigo = f.read().rstrip("\n") + "\n"

            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.write(antigo + novas)

            print(f"✅ {len(novas.splitlines())} linhas adicionadas")
            os.remove(TEMP_FILE)
        else:
            print("ℹ️ Nenhuma mensagem nova")

        # === GERA JSON DA LOJA ===
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            log = f.read()

        def extrair_itens(texto):
            itens = []
            padrao = r"```.*?\n(.*?)```"
            for bloco in re.findall(padrao, texto, re.DOTALL):
                for linha in bloco.split("\n"):
                    if linha.startswith("|") and linha.count("|") >= 3:
                        p = [x.strip() for x in linha.split("|")[1:-1]]
                        if len(p) >= 2 and p[1].replace(",", "").isdigit():
                            itens.append({
                                "nome": p[0],
                                "preco": f"{p[1]} Coin",
                                "quantidade": p[2] if len(p) > 2 else "N/A"
                            })
            return itens

        itens = extrair_itens(log)

        unicos = {}
        for i in itens:
            unicos[f"{i['nome']}|{i['preco']}"] = i

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(list(unicos.values()), f, ensure_ascii=False, indent=2)

        print(f"🛒 Loja atualizada ({len(unicos)} itens)\n")

    except Exception as e:
        print(f"❌ Erro: {e}")

    time.sleep(INTERVALO)
