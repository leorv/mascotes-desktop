# Clips — Mascote do PC

O Clips é um mascote de desktop feito em Python e PyQt5. Ele acompanha o mouse, reage aos cliques, cochila depois de um período sem atividade e pode ser arrastado pela tela.

Os mascotes disponíveis são Clippy, Pretí (gato preto), Marla (golden), Mochi (panda), Louro José (papagaio) e Zoe (Yorkshire). Para trocar de mascote, clique com o botão direito no personagem e abra **Trocar bichinho**. A escolha fica salva para a próxima abertura.

## Linux

O Linux precisa estar em uma sessão gráfica X11. O programa consulta o cursor por meio do X11; em uma sessão Wayland, entre em uma sessão “Xorg” ou “X11” antes de iniciar.

1. Instale o Python 3 e o suporte a ambientes virtuais. No Ubuntu ou Debian:

   ```bash
   sudo apt update
   sudo apt install python3 python3-venv
   ```

   Em outras distribuições, instale os pacotes equivalentes de Python 3, `pip` e `venv` pelo gerenciador de pacotes da distribuição.

2. Abra um terminal na pasta do projeto e crie um ambiente virtual:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip PyQt5
   ```

3. Inicie o mascote:

   ```bash
   python mascote.py
   ```

   Deixe o terminal aberto enquanto o mascote estiver sendo executado. Para encerrar pelo terminal, pressione `Ctrl+C`. Também é possível usar **botão direito → Sair**.

## Windows

1. Instale o Python 3 pelo [site oficial do Python](https://www.python.org/downloads/windows/). Durante a instalação, marque **Add Python to PATH**.

2. Abra o PowerShell na pasta do projeto e crie um ambiente virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip PyQt5
   ```

   Se o PowerShell bloquear a ativação do ambiente, execute uma vez:

   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```

   Depois, repita o comando de ativação.

3. Inicie o mascote:

   ```powershell
   python mascote.py
   ```

   Para encerrar, use **botão direito → Sair**. Se quiser executar sem manter uma janela do terminal aberta, use `pythonw mascote.py`.

## Controles

- Botão esquerdo: arrasta o mascote.
- Botão direito: abre as opções, troca o bichinho, pausa reações, esconde o personagem ou encerra o programa.
- **Iniciar com o computador**: cria a configuração de inicialização automática para o usuário atual. A opção pode ser desmarcada no mesmo menu.
- O ícone na bandeja do sistema permite mostrar o mascote novamente depois de escondê-lo.

As imagens em `referencias-mascotes/` são os modelos de base. O programa funciona localmente, não lê teclas, não captura telas e não usa internet.
